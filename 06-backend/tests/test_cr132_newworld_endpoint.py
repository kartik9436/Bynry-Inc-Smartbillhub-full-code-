# ── Trace ──────────────────────────────────────────────
# Change:  CR-132-BRC07 — `GET /api/partner/v1/receipts`, end to end.
# Rules:   CLAUDE.md hard rule 1 (the tenant comes from the KEY) · hard rule 4
#          (a READ; the origin column is write-once) · hard rule 5
# Proves:  the door refuses without a key · the feed carries ONLY webhook
#          origin · the GL account on a distribution is the one the LEDGER
#          posted · the residue measurement the PO asked for, with a figure
# ───────────────────────────────────────────────────────
"""The receipt address on the real path — service, ledger, door and all.

⚠ **THE UNIT CASES IN `test_cr132_newworld_receipts.py` BUILD RECEIPTS FROM
DATACLASSES AND THIS FILE DOES NOT.** Those prove the projection's arithmetic
and its shape; this one proves the thing they cannot — **that the numbers come
from where we say they come from.** A distribution's GL account here is written
by `payments.ledger_seam.post_payment_cleared` into a real journal entry and
read back through the ledger seam, so a projection wired to the wrong column
fails here and nowhere else.

⚠ **AND IT CARRIES THE MEASUREMENT THE PO ASKED FOR.** *"Find out how often
that is the case on real data and say so with a figure"* — the question being
whether an unbalanced receipt is a one-cent rounding residue or a real error,
because the two have the same symptom and opposite fixes. See
`test_how_often_a_real_payment_fails_to_balance`.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from apps.integrations import models, newworld, partner_api, services
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

NEWWORLD = "erp_newworld"
ALLOWED_ADDRESS = "198.51.100.12"
ALLOWLIST = "198.51.100.0/24"
KEY = "sbh_live_9W4K_brazosbend_newworld_do_not_reuse"
HINT = "••••9W4K"
WIDE_WINDOW = {"start_date": "2000-01-01", "end_date": "2099-12-31"}


def _connect(tenant, actor):
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=NEWWORLD,
        label="New World / Logos",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={serve.ALLOWLIST_CONFIG_KEY: ALLOWLIST},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=KEY,
        masked_hint=HINT,
        blind_index=crypto.blind_index(KEY, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=[one.name for one in REGISTRY.require(NEWWORLD).operations if one.they_call_us],
    )
    return connection


def _get(tenant, *, key=KEY, address=ALLOWED_ADDRESS, query=None):
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    params = dict(WIDE_WINDOW)
    params.update(query or {})
    # ⚠ A `None` is "do not send this parameter", not the string "None" — which
    # is what a query dict would serialise it to, and the window check would
    # then be testing that `"None"` fails to parse rather than that an ABSENT
    # window is refused. Same filtering as the bills fixture, same reason.
    params = {name: value for name, value in params.items() if value is not None}
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}/partner/v1/receipts", params, REMOTE_ADDR=address
    )
    if key is not None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return partner_api.partner_receipts(request)


def _content(response):
    return response.content if hasattr(response, "content") else response.rendered_content


@pytest.fixture()
def wired(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        yield _connect(brazos, dana)
    serve.reset_partner_limits()


def _account(tenant, actor, *, account_no="A-77120", name="Delgado, Rosa"):
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


def _issue(tenant, account, *, invoice_no, total):
    from django.utils import timezone

    from apps.billing import models as billing_models

    today = timezone.now().date()
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=invoice_no,
        status="issued",
        bill_type="cycle",
        issued_at=timezone.now(),
        service_date=today,
        period_start=today,
        period_end=today,
        currency="USD",
        total=Decimal(total),
    )


@pytest.fixture()
def seeded_payments(brazos, dana, settings):
    """Three payments, ONE PER ORIGIN, recorded through the real service.

    ⚠ **THEY GO THROUGH `record_payment`, NOT `Payment.objects.create`.** That
    is the whole value of this fixture: the origin column is written by the
    service at creation (write-once, hard rule 4), the allocation is the real
    allocator's, and the journal entry is the one
    `payments.ledger_seam.post_payment_cleared` writes — so the GL code this
    feed reports is a code the LEDGER chose, not one the fixture typed.
    """
    from django.utils import timezone

    from apps.ledger import models as ledger_models
    from apps.payments import idempotency
    from apps.payments import models as payments_models
    from apps.payments import services as payment_services

    # ⚠ **JOBS RUN INLINE HERE, AND `config/settings/test.py` SAYS TO DO IT
    # THIS WAY.** That file sets `JOBS_EAGER = False`, so a dispatched job goes
    # to a broker — and there is no Redis in a test run, which surfaces as
    # `Error 111 connecting to localhost:6379` from inside the fixture rather
    # than as anything to do with payments. Its own comment names the remedy:
    # *"paths turn it on for themselves"*.
    settings.JOBS_EAGER = True
    made = {}
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        now = timezone.now()
        for index, source in enumerate(
            (idempotency.SOURCE_WEBHOOK, idempotency.SOURCE_ENTRY, idempotency.SOURCE_IMPORT)
        ):
            _issue(brazos, account, invoice_no=f"INV-NW-{index}", total="142.18")
            recorded = payment_services.record_payment(
                dana,
                account_id=account.id,
                amount=Decimal("142.18"),
                posted_at=now,
                cleared_at=now,
                method_code="check",
                confirmation=f"NW-{index}",
                idempotency_source=source,
                idempotency_reference=f"nw-{source}-{index}",
            )
            made[source] = payments_models.Payment.objects.get(pk=recorded.payment_id)
        # ── A SPREAD OF ALLOCATION SHAPES, ALL `webhook`, FOR THE RESIDUE
        # MEASUREMENT (PO 2026-09-22, *"say so with a figure"*). One credit leg
        # is the ordinary case; an OVERPAYMENT produces two — accounts
        # receivable plus customer credit — and two legs is the only shape in
        # which a rounding residue could arise at all. The awkward totals are
        # chosen so the arithmetic has somewhere to go wrong: thirds of a
        # dollar, a penny bill, and an overpayment that splits unevenly.
        spread = [
            ("33.33", "50.00"),    # overpay a third-of-a-dollar bill
            ("33.34", "33.34"),    # exact, odd cent
            ("0.01", "0.01"),      # a penny
            ("100.00", "150.00"),  # overpay by fifty
            ("66.67", "66.67"),    # exact, two thirds
            ("142.18", "200.00"),  # overpay, the worked figure
        ]
        for index, (bill_total, paid) in enumerate(spread):
            _issue(brazos, account, invoice_no=f"INV-NWX-{index}", total=bill_total)
            payment_services.record_payment(
                dana,
                account_id=account.id,
                amount=Decimal(paid),
                posted_at=now,
                cleared_at=now,
                method_code="check",
                idempotency_source=idempotency.SOURCE_WEBHOOK,
                idempotency_reference=f"nw-spread-{index}",
            )
        # the AR account the posting actually credited, read back from the books
        line = (
            ledger_models.JournalLine.objects.filter(
                tenant=brazos,
                journal_entry__source_type="payment",
                journal_entry__source_id=made[idempotency.SOURCE_WEBHOOK].pk,
                side=ledger_models.SIDE_CREDIT,
            )
            .select_related("ledger_account")
            .first()
        )
        made["ar_code"] = str(line.ledger_account.code) if line is not None else None
    return made


# ── the manifest is data, and the door is the door ──────────────────────────


def test_the_manifest_declares_the_new_address_and_reuses_the_ledger():
    """⚠ **THE WHOLE RULING, AS TWO ROWS.** The receipt address is NEW; the
    ledger address is the one `erp_aclarian` already declares and the one
    `partner_ledger` already serves. If a later lane ever gives New World its
    own ledger, this goes red and that becomes a decision somebody makes on
    purpose."""
    manifest = REGISTRY.require(NEWWORLD)
    paths = {one.name: one.served_path for one in manifest.operations}
    assert paths == {
        "serve_receipt": "/partner/v1/receipts",
        "serve_ledger": "/partner/v1/ledger",
        # CR-173-BRC10 (2026-10-07): the third operation is OURS to start — we
        # place the day's file in the City's SFTP folder — so it publishes no
        # address of ours. The two rows above are unchanged.
        "send_receipt_file": None,
    }
    aclarian = {one.name: one.served_path for one in REGISTRY.require("erp_aclarian").operations}
    assert paths["serve_ledger"] == aclarian["serve_ledger"]


def test_no_key_is_refused_and_the_refusal_says_nothing(brazos, wired):
    """The surface's one refusal — a `404`, indistinguishable from a route that
    does not exist (`BR-INT-044`). Not written again here; it is `_admit`'s."""
    response = _get(brazos, key=None)
    assert response.status_code == 404


def test_a_missing_window_is_refused_in_six_words(brazos, wired):
    response = _get(brazos, query={"start_date": None, "end_date": None})
    assert response.status_code == 400
    assert json.loads(_content(response))["code"] == "DATE_RANGE_REQUIRED"


# ── the feed's contents ─────────────────────────────────────────────────────


def test_only_webhook_origin_reaches_the_feed(brazos, dana, wired, seeded_payments):
    """⚠ **ONLINE ONLY, AND IT IS NEW WORLD'S OWN REQUIREMENT** (PO ruling
    2026-09-22). A counter receipt reaching this feed would be double-counted
    against the cashier system that already posted it."""
    body = _content(_get(brazos)).decode("utf-8")
    assert seeded_payments["webhook"].payment_no in body
    assert seeded_payments["entry"].payment_no not in body
    assert seeded_payments["import"].payment_no not in body


def test_the_gl_account_on_a_distribution_is_the_one_the_ledger_posted(
    brazos, dana, wired, seeded_payments
):
    """⚠ **THE ASSERTION THE UNIT CASES CANNOT MAKE.** The code in the file is
    the code `post_payment_cleared` wrote into a real journal line, resolved
    back through `seams/ledger.account_code` — the same resolution
    `/partner/v1/ledger` puts Aclarian's rows through. A projection wired to a
    different column passes every unit case and fails here."""
    body = _content(_get(brazos)).decode("utf-8")
    expected = seeded_payments["ar_code"]
    # An attribute since 2026-10-21 (DEF-INT-10304); a child element until then.
    assert f'GLAccountNumber="{expected}"' in body


def test_the_served_page_is_in_the_confirmed_template_shape(
    brazos, dana, wired, seeded_payments
):
    """PO 2026-10-21, answer 4: *"Both switch: one builder, one correct
    shape"*. The API page passes the same template check as the SFTP file."""
    from apps.integrations import newworld

    response = _get(brazos)
    assert response.status_code == 200
    body = _content(response)
    assert b"<ROOT>" in body
    assert newworld.validate(body) == []


def test_a_page_that_fails_the_template_check_is_not_served(
    brazos, dana, wired, seeded_payments, monkeypatch
):
    """Fail closed: a page that fails `newworld.validate` is a `500` with a
    code, never an invalid file their importer would take. The access log
    records it as refused, with the problem."""
    from apps.integrations import newworld

    real_render = newworld.render

    def wrong_shape(receipts):
        # The date shape this file had until 2026-10-21.
        return real_render(receipts).replace(b'PaymentGLDate="', b'PaymentGLDate="2026-')

    monkeypatch.setattr(newworld, "render", wrong_shape)
    response = _get(brazos)
    assert response.status_code == 500
    assert json.loads(_content(response))["code"] == "RECEIPTS_INVALID"
    assert b"<ROOT" not in _content(response)


def test_the_exception_counts_travel_on_the_response(brazos, dana, wired, seeded_payments):
    """*Never silently.* The headers are stated even at zero, so their absence
    cannot be mistaken for a clean run on an older build."""
    response = _get(brazos)
    assert response["X-Receipts-Unbalanced"] is not None
    assert response["X-Receipts-Unresolved-GL"] is not None
    assert int(response["X-Receipts-Unbalanced"]) >= 0


# ── the measurement the PO asked for ────────────────────────────────────────


def test_how_often_a_real_payment_fails_to_balance(brazos, dana, wired, seeded_payments):
    """**THE FIGURE, MEASURED RATHER THAN REASONED.**

    The question the PO asked is whether an unbalanced receipt is a one-cent
    rounding residue — we store money to four decimals and their field is
    `9,2` — or a real mis-mapping. It decides what the eventual fix looks like:
    a systematic residue has a standard answer (assign the remainder to the
    largest distribution, which places a real cent rather than inventing one)
    and a mis-mapping does not.

    ⚠ **THE ANSWER ON THIS PATH IS THAT IT CANNOT HAPPEN, AND THE REASON IS
    STRUCTURAL RATHER THAN LUCKY.** `post_payment_cleared` refuses to post
    unless `applied_to_bills + credit_carried + deposit_held` equals the
    payment EXACTLY, and each of those three is already a two-decimal figure:
    a payment amount is what somebody actually paid, and an invoice total is
    quantised once when the bill is formed (B4 — *round only at finalisation*).
    Rounding a set of two-decimal numbers changes none of them, so
    Σ round(leg) = round(Σ leg) and the receipt foots.

    **A residue needs a sub-cent leg, and the posting path does not make one.**
    The case is kept, and it is written to REPORT rather than to assert a zero,
    because the day something does produce one this prints the figure instead
    of going quietly green (law 7: a check that reports zero over a scope it
    excludes is indistinguishable from an empty one).
    """
    from apps.integrations.seams import payments as payments_seam
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        rows = list(
            payments_seam.page_queryset(origin=payments_seam.ORIGIN_ONLINE).prefetch_related(
                "allocations__invoice"
            )
        )
        measured = newworld.measure_residues(rows)

    print("\nRESIDUE MEASUREMENT (CR-132-BRC07):", json.dumps(measured, indent=2))
    assert measured["receipts"] == measured["balanced"] + measured["residue"] + measured[
        "material"
    ]
    # What is asserted is the PROPERTY, not the count: no receipt may be short
    # by more than rounding could possibly explain without somebody being told.
    assert measured["material"] == 0, (
        "a receipt is short by more than the rounding bound — that is a real "
        f"mis-mapping, not a residue: {measured['material_examples']}"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-132-BRC07
# generated: 2026-09-22 by the CR-132-BRC07 New World lane
# gates: pytest tests/test_cr132_newworld_endpoint.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
