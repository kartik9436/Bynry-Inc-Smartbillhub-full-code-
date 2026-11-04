# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-4409 — *"every value on a customer receipt renders as an
#          em-dash"*. Reported by the Product Owner on the live product,
#          2026-09-07, opening a waiting receipt on Settings → Notifications →
#          Messages needing attention: *"email doe snot show the values they
#          are not resolved"*.   Screens: S22 (record payment) · S8
# Rules:   BR-PAY-024 (a receipt is auto-queued on a recorded payment) ·
#          BR-NOT-012 (the notification's own STORED render context) ·
#          BR-BIL-026 (the pin is stamped at queue time) · BR-CUS-015
#          (`accounts.balance` is a CACHE and is never the balance) ·
#          BR-TEN-017 (the utility's identity is stamped AT RENDER) ·
#          BR-PAY-010 (only what met a bill credits AR) · BR-PAY-021 (the
#          POSTING date is the business date) · CLAUDE.md rule 2 (money stored
#          to 4 decimals, DISPLAYED to 2, beside its CHAR(3)) · rule 4 (a
#          receipt never widens what the money transaction writes) ·
#          hard-won law 7 (every guard here was driven RED first)
# Impacts: apps/payments/receipts.py (the fix) · apps/payments/services.py (the
#          caller that now passes what it holds) ·
#          apps/notifications/services._context_gap (the guard this bought) ·
#          apps/notifications/rendering.RENDERER_SUPPLIED
# ───────────────────────────────────────────────────────
"""A receipt with seven absences is not a receipt.

WHAT WENT WRONG, AND WHY NOTHING SAW IT
----------------------------------------
The email the Product Owner opened read, in full:

    Hi ——,
    Thank you — we have received your payment.
    Amount ——      Date ——      Method ——      Confirmation ——
    Applied to ——
    Balance before this payment ——
    Balance after this payment ——

**Every part of the machine was working.** The seeded body is correct, the
renderer is correct, and `rendering.py` states the design in its own docstring:
the queue row does not hold the balance or the date, a caller supplies them at
queue time, and a catalogued token with no value becomes a NAMED ABSENCE rather
than an invented figure. `apps/payments/receipts.py` passed no context and had
no parameter for one — while two sibling callers of the same function pass one
and work. So no exception was raised, no test failed, the email was well
formed, and the output was a valid document with nothing in it.

WHAT THIS FILE ASSERTS, AND AT WHICH LAYER
-------------------------------------------
  1 · the queue ROW carries the figures (`outbound_messages.render_context`);
  2 · the RENDERED body shows them, at 2 decimal places beside the tenant's
      currency, with the em-dash gone from every line that has a value;
  3 · the BALANCES come from the ledger's own per-account Σ and not from the
      cached column, and the before/after pair differs by exactly what met a
      bill;
  4 · the GUARD reports a caller that supplies nothing, and stays silent for a
      caller that states a genuine absence — the two cases that make it worth
      having rather than noise.

EVERY GUARD HERE WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7),
through `python3.12 -m pytest`, which is the harness that runs it. The four
proofs are quoted in the lane report and each names the line it deleted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.notifications import models as notification_models
from apps.notifications import rendering, services as notification_services, template_service
from apps.payments import receipts, services as payment_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── PE-1, verbatim (08-payments/07-pre-session-model.md §13) ────────────────
# "ACC-1042: open BL-2607-018311 $45.00 (due Jul 22) + BL-2608-018410 $247.87.
#  PE-1 payment: check #8842, $292.87, Aug 8, 2026."
OLD_BILL = Decimal("45.00")
NEW_BILL = Decimal("247.87")
PE1_CHECK = Decimal("292.87")
POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)


def _put_the_bills_in_the_books(tenant, account, total):
    """DR accounts receivable / CR revenue — an ISSUE entry, in miniature.

    `an_issued_bill` writes billing's row directly, which is the right shortcut
    for an allocation test and the wrong one here: what a receipt prints is the
    LEDGER's answer to *what does this account owe* (BR-CUS-015 — the cached
    column is never the balance), and a bill that never reached the books owes
    nothing there. So the fixture posts it, through the one service allowed to
    write journal lines (CLAUDE.md rule 5).
    """
    from apps.ledger import chart, posting, selectors as ledger_selectors

    ar = ledger_selectors.gl_account_id_for_designation(chart.AR)
    # The OPENING-BALANCE clearing account, which is what this fixture is: a
    # customer's position put into the books without running a bill through the
    # rating engine. No revenue designation is invented for a test.
    opening = ledger_selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
    dimensions = {"source_type": "invoice", "source_id": account.pk, "account_id": account.pk}
    posting.post(
        posting.PostingRequest(
            posting_key=posting.posting_key(
                source_type="invoice", source_id=account.pk, event="issued"
            ),
            entry_date=date(2026, 8, 1),
            posted_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            currency="USD",
            source_type="invoice",
            source_id=account.pk,
            lines=(
                posting.PostingLine(
                    ledger_account_id=ar, side="debit", amount=total, **dimensions
                ),
                posting.PostingLine(
                    ledger_account_id=opening, side="credit", amount=total, **dimensions
                ),
            ),
        )
    )


def _pe1(actor, tenant, marcus):
    """PE-1 end to end: two open bills in the books, one $292.87 cheque.

    The CONTACT is part of the fixture and not scenery: `{first_name}` and
    `{customer_name}` are resolved through customers' published
    `delivery_recipients_for_account` — the same read notifications uses to put
    an address on the row — so an account with no contact would leave that path
    untested and the greeting would still say `Hi ——` in production
    (hard-won law 2).
    """
    from apps.customers import models as customer_models

    account = an_account(marcus, tenant)
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name="Maria Alvarez", email="maria@example.com"
    )
    an_issued_bill(
        tenant, account, number="BL-2607-018311", total=OLD_BILL, issued_on=date(2026, 7, 1)
    )
    an_issued_bill(
        tenant, account, number="BL-2608-018410", total=NEW_BILL, issued_on=date(2026, 8, 1)
    )
    _put_the_bills_in_the_books(tenant, account, OLD_BILL + NEW_BILL)
    recorded = payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=PE1_CHECK,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code="check",
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )
    return account, recorded


def _row(tenant, payment_id, channel):
    return notification_models.OutboundMessage.objects.get(
        tenant_id=tenant.pk, source_type="payment", source_id=payment_id, channel=channel
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE QUEUE ROW CARRIES THE FIGURES
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_4409__the_queued_receipt_row_holds_the_payments_own_facts(brazos, marcus):
    """RED PROOF: delete `render_context=render_context` from
    `receipts._queue_one` and this fails on the first assertion with
    `render_context is None` — which is exactly the state the Product Owner's
    receipt was queued in."""
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        row = _row(brazos, recorded.payment_id, "email")

        assert row.render_context, "a receipt queued with no context prints every field as ——"
        stored = rendering.decode_context(row.render_context)

    # The payment's own columns, typed — money as Decimal so the JSON round trip
    # gives `format_money` something to round (CLAUDE.md rule 2), never a string.
    assert stored["amount"] == PE1_CHECK
    assert isinstance(stored["amount"], Decimal)
    assert stored["date"] == POSTED_AT  # BR-PAY-021's POSTING date, not the clearing date
    assert stored["confirmation"] == "8842"
    assert stored["method"] == "Check"
    # The allocator's own bill numbers, oldest first (BR-PAY-010).
    assert stored["applied_to_bill"] == "BL-2607-018311, BL-2608-018410"


def test_def_pay_4409__every_token_the_body_names_is_stated_even_when_it_has_no_value(
    brazos, marcus
):
    """A key present with value None says *this document has none*; a key that
    is simply absent says *the caller forgot*. The guard turns on that
    difference, so the caller must state every token it could carry.

    RED PROOF: drop `"processed_by"` from `receipt_render_context` and this
    fails naming it."""
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        row = _row(brazos, recorded.payment_id, "email")
        pinned_body = template_service.load_pinned(
            template_id=row.template_id, version=row.template_version
        )
        declared = set(rendering.tokens_in(pinned_body.body)) | set(
            rendering.tokens_in(pinned_body.subject or "")
        )
        stated = set(rendering.decode_context(row.render_context))

    forgotten = sorted(declared - rendering.RENDERER_SUPPLIED - stated)
    assert forgotten == [], f"the emailed receipt names {forgotten} and the caller supplies none"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE RENDERED BODY — WHAT THE CUSTOMER ACTUALLY READS
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_4409__the_rendered_receipt_shows_the_figures_at_two_decimals(brazos, marcus):
    """The whole defect, at the layer the Product Owner was looking at.

    RED PROOF: the same deletion as case 1 — the body comes back with `Amount
    ——  Date ——  Method ——  Confirmation ——` and this fails on the first
    `in body` assertion."""
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        artifact = rendering.render_for_dispatch(_row(brazos, recorded.payment_id, "email"))

    body = artifact.body
    # CLAUDE.md rule 2: stored to 4 decimals, DISPLAYED to 2, beside the CHAR(3).
    assert "Amount $292.87" in body
    assert "292.870000" not in body and "292.8700" not in body
    assert "Confirmation 8842" in body
    assert "Method Check" in body
    assert "Applied to BL-2607-018311, BL-2608-018410" in body
    assert body.startswith("Hi Maria,")
    # The tenant's Regional date format, applied to the POSTING date.
    assert "2026" in body and "Date ——" not in body
    # And the line the Product Owner quoted is no longer an em-dash.
    assert "Balance before this payment ——" not in body
    assert "Balance after this payment ——" not in body


def test_def_pay_4409__the_only_absences_left_are_fields_this_payment_has_no_value_for(
    brazos, marcus
):
    """`rendering` counts its absences and, until this defect, nothing read the
    count. Read it: after the fix the emailed receipt's absences are the fields
    a Product Owner would expect to be blank on a demo tenant, and nothing
    else."""
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        artifact = rendering.render_for_dispatch(_row(brazos, recorded.payment_id, "email"))

    absent = {record["token"] for record in artifact.absences}
    # `{support_phone}` and `{utility_website}` are the utility's OWN details,
    # stamped at render from Settings → Company (BR-TEN-017) — a blank one is a
    # settings gap this module cannot close and `absence_detail` names the
    # screen. Everything the PAYMENT knows must be gone from this set.
    assert absent <= {"support_phone", "support_email", "utility_website", "utility_address"}, (
        f"the receipt still cannot state {sorted(absent)}"
    )
    # And the greeting the Product Owner read as `Hi ——,` now names the person.
    assert "Hi Maria," in artifact.body


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BALANCES COME FROM THE BOOKS
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_4409__the_balances_are_the_ledgers_and_differ_by_what_met_a_bill(brazos, marcus):
    """PE-1: the books hold 292.87 of AR, the cheque settles both bills, so the
    receipt reads **before 292.87 USD · after 0.00 USD**.

    Two separate claims, and the second is the one that would go wrong quietly:
    the figures are the LEDGER's per-account Σ (BR-CUS-015 — `accounts.balance`
    is a cache nothing writes and reading it told a customer owing 108.88 that
    they owed nothing), and `before − after` is exactly what credited AR.

    RED PROOF: make `_ar_balance` return `Decimal("0")` when the ledger says
    `available=False` — the DEF-127 substitution — and the pair collapses to
    0.00/0.00 while every other assertion in this file still passes."""
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        row = _row(brazos, recorded.payment_id, "email")
        stored = rendering.decode_context(row.render_context)
        artifact = rendering.render_for_dispatch(row)

    assert stored["balance_before"] == OLD_BILL + NEW_BILL == Decimal("292.87")
    assert stored["balance_after"] == Decimal("0")
    assert stored["balance_before"] - stored["balance_after"] == recorded.applied
    assert "Balance before this payment $292.87" in artifact.body
    assert "Balance after this payment $0.00" in artifact.body


def test_def_pay_4409__a_receipt_still_goes_out_when_a_figure_cannot_be_read(
    brazos, marcus, monkeypatch
):
    """OQ-117: a document with a NAMED absence goes out, because the customer
    needs the rest of it. So a ledger that cannot answer costs the receipt its
    two balance lines and NOTHING else — not the other six fields, and above
    all not the payment.

    This is also this module's one law under a new failure mode: the reads
    added for this defect are the first database reads it has ever done, and
    each runs in its own savepoint (CLAUDE.md hard-won law 14)."""

    def refuses(**_kwargs):
        raise RuntimeError("the books cannot be asked")

    monkeypatch.setattr(receipts, "_ar_balance", refuses)
    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        stored = rendering.decode_context(_row(brazos, recorded.payment_id, "email").render_context)

    assert recorded.payment_id  # the money is recorded whatever happened to its paperwork
    assert stored["amount"] == PE1_CHECK
    assert stored["confirmation"] == "8842"
    assert stored["balance_before"] is None and stored["balance_after"] is None
    codes = {problem["code"] for problem in recorded.problems}
    assert receipts.RECEIPT_FIGURE_UNREADABLE in codes
    assert receipts.RECEIPT_EMAIL_QUEUED in codes


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE GUARD — WHAT THE NEXT CALLER GETS THAT THIS ONE DID NOT
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_4409__the_queue_names_the_fields_a_caller_did_not_supply(brazos, marcus):
    """The check that would have caught this defect the day it was written.

    RED PROOF, run first: with `_context_gap` not yet called from
    `queue_document`, this fails with `render_context_missing_tokens not in
    set()`. With it called and the receipt fix in place, the SAME call made
    with no context reports all eight fields by name."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        written = notification_services.queue_document(
            source_type="payment",
            source_id=uuid.uuid4(),
            channels=("email",),
            template=receipts.SimpleNamespace(
                code="email_payment_receipt", template_id=None, version=None, language=None
            ),
            account_id=account.pk,
            actor=marcus,
        )

    gap = [
        problem
        for problem in written.problems
        if problem["code"] == notification_services.QUEUE_CONTEXT_GAP
    ]
    assert gap, "a document queued with no merge values at all must say so"
    assert set(gap[0]["tokens"]) == {
        "amount",
        "applied_to_bill",
        "balance_after",
        "balance_before",
        "confirmation",
        "date",
        "first_name",
        "method",
    }


def test_def_pay_4409__the_guard_is_silent_when_the_caller_states_a_genuine_absence(
    brazos, marcus
):
    """The false positive that would make the guard worthless — and the case
    that nearly went untested.

    A cash payment over the counter has NO confirmation number, and a payment
    on an account with no open bills meets no bill. The caller passes both keys
    with no value, which STATES that this document has none, and must not be
    told it forgot. The whole check turns on `key in context` rather than
    `context[key] is not None`, and this is the only case in the file that
    holds it there.

    ⚠ **THIS TEST WAS FIRST WRITTEN OVER THE PE-1 FIXTURE, WHERE EVERY VALUE IS
    PRESENT — so both readings of the check agreed and the red proof came back
    GREEN.** A test named after an assertion it does not make (hard-won law 7's
    fourth shape), found by running the proof rather than by reading it. The
    fixture is now a payment that genuinely has neither figure.

    RED PROOF: change the subtraction in `_context_gap` to drop keys whose
    value is None and this fails, reporting `applied_to_bill, confirmation` as
    a caller's mistake — which is every honest absence in the product turned
    into noise."""
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        customer_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Maria Alvarez", email="maria@example.com"
        )
        recorded = payment_services.record_payment(
            marcus,
            account_id=account.pk,
            amount=Decimal("40.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        stored = rendering.decode_context(_row(brazos, recorded.payment_id, "email").render_context)

    # The fixture is only worth anything if these two really are absent.
    assert stored["confirmation"] is None and stored["applied_to_bill"] is None
    codes = {problem["code"] for problem in recorded.problems}
    assert notification_services.QUEUE_CONTEXT_GAP not in codes, (
        "a stated absence is not a forgotten field — "
        f"{[p for p in recorded.problems if p['code'] == notification_services.QUEUE_CONTEXT_GAP]}"
    )


def test_def_pay_4409__the_guard_says_out_loud_when_it_could_not_look(brazos, marcus):
    """Hard-won law 7's fifth shape: a declared blind spot with no number
    attached is indistinguishable from an empty one. A row with no resolved pin
    has no body to compare against, and the queue says so rather than
    reporting nothing wrong."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        written = notification_services.queue_document(
            source_type="payment",
            source_id=uuid.uuid4(),
            channels=("email",),
            template=receipts.SimpleNamespace(
                code="a_class_nobody_published", template_id=None, version=None, language=None
            ),
            account_id=account.pk,
            actor=marcus,
        )

    codes = {problem["code"] for problem in written.problems}
    assert notification_services.QUEUE_CONTEXT_UNCHECKED in codes
    assert notification_services.QUEUE_CONTEXT_GAP not in codes


def test_def_pay_4409__the_renderer_supplied_set_is_derived_from_the_code_that_supplies_it(
    brazos,
):
    """Hard-won law 2, one layer up: a hand-typed second copy of a list is a
    list that goes stale, and this one decides whether a missing figure is
    reported as a caller's mistake. It is derived from `_identity_context`, so
    a token added there joins it on its own."""
    assert rendering.RENDERER_SUPPLIED == frozenset(rendering._identity_context({})) | {
        "rights_footer"
    }
    # `{utility_logo}` is deliberately NOT in it — no palette offers it and no
    # context fills it, so it is a real gap (DEF-195) rather than a supplied
    # value, and listing it would hide the thing the guard exists to find.
    assert "utility_logo" not in rendering.RENDERER_SUPPLIED


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE PANEL BESIDE THE LETTER — DEF-NOT-4413, found by walking this fix
# ══════════════════════════════════════════════════════════════════════════
def test_def_not_4413__the_waiting_panel_shows_money_at_two_decimals(brazos, marcus):
    """The screen the Product Owner opens shows the letter AND, under it, the
    facts the writer stamped. Giving receipts a render context put money and
    dates on that list for the first time, and it printed them raw:
    **`Balance 0.000000`** and **`Date 2026-09-07 00:00:00-05:00`**, two inches
    under a letter reading *your balance is now 0.00 USD*.

    CLAUDE.md hard rule 2: money is stored to 4 decimals and DISPLAYED to 2.
    BR-TEN-017: a date wears the tenant's Regional format. Both are already done
    by `rendering._rendered_value`, so the panel CALLS it rather than keeping a
    second copy — a second money formatter is how the letter and the panel
    beside it start disagreeing about one figure.

    RED PROOF: put `str(value)` back in `unsent_preview._facts` and this fails on
    `Balance before` reading `292.870000`."""
    from apps.notifications import unsent_preview

    with tenant_ctx(brazos):
        _account, recorded = _pe1(marcus, brazos, marcus)
        row = _row(brazos, recorded.payment_id, "email")
        facts = {one["label"]: one["value"] for one in unsent_preview._facts(row)}

    assert facts["Amount"] == "$292.87"
    assert facts["Balance before"] == "$292.87"
    assert facts["Balance after"] == "$0.00"
    # The tenant's OWN Regional format (BR-TEN-017), not a raw timestamp with a
    # timezone offset on it. Brazos Bend is MM/DD/YYYY; the assertion was first
    # written as ISO and the run corrected it — which is the point of the test.
    assert facts["Date"] == "08/08/2026", facts["Date"]
    # A token the caller STATED as absent is not a fact and is not listed.
    assert "Processed by" not in facts
