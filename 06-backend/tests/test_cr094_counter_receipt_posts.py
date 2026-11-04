# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15.
# Story:    US-LED-001   Screens: capture step 5 · the finance books
# Rules:    CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · hard-won law 14 · BR-CUS-090
# ───────────────────────────────────────────────────────
"""**The counter fee posts — and the tie-out is what proves it.**

PO, 2026-09-15, shown Sarah Miller paying **$25.00** cash at the counter on
12 May against receipt `RCP-26-4471` and a four-row table proving the money
appeared in payments, in the ledger and on the finance screens as NOTHING:

    "payemnt should show in payments, in ledge and in fiannce books"
    "when it is approved you can attached it to account - if it is refuse then
     it is application fees non refundable - it stya in books"
    "if it is ask more then it stays in all 3 places in payment, in ledger and
     in finance"

**THE RATIFIED PAIR IS ASSERTED BY ACCOUNT CODE AND BY FIGURE**, so drift goes
RED rather than quiet — the 🔒 sensitive-path requirement, and the reason this
file exists at all rather than a handful of state assertions.

PROVED RED FIRST (hard-won law 7), each by breaking the named thing and running
THIS file through pytest, which is the harness that will run it. The failures
below are QUOTED FROM THE RUNS, not composed:

  1. `record_counter_receipt` with the `post_counter_receipt_collected` call
     switched off →
        FAILED ...::test_the_collection_posts_a_balanced_pair
        E  assert None is not None
  2. the collection debiting `cash` (1000) instead of the clearing account —
     which is the ruling row of 2026-09-15 as written, before it was amended →
        FAILED ...::test_the_collection_debits_undeposited_and_never_cash
        E  AssertionError: assert {'1000', '2400'} == {'1010', '2400'}
  3. `_revenue_targets` taking the whole receipt instead of capping at the
     quote →
        FAILED ...::test_over_collection_earns_only_the_quote
        E  AssertionError: assert Decimal('30.0000') == Decimal('25.0000')
  4. `release_counter_receipt`'s `state != HELD` early return removed →
        FAILED ...::test_a_second_terminal_outcome_posts_nothing
        E  assert datetime(2026, 9, 15, 18, 14, 53, 529354, …) ==
              datetime(2026, 9, 15, 18, 14, 53, 517529, …)
  5. the collection's replay branch removed →
        FAILED ...::test_payments_own_replay_guard_holds_when_called_directly
        E  django.db.utils.IntegrityError: UNIQUE constraint failed:
              counter_receipts.tenant_id, counter_receipts.source_type,
              counter_receipts.source_id
  6. `ask_for_more` wired to `_release_counter_fee`, which is the posting a
     lane reading only the approve and refuse clauses would invent →
        FAILED ...::test_ask_for_more_posts_nothing
        E  AssertionError: assert 'earned' == 'held'

⚠ **TWO OF THOSE SIX PASSED THE FIRST TIME THEY WERE BROKEN, AND THAT IS THE
PART WORTH READING.** Law 7's second habit — *ask what would make this check
pass wrongly* — was not hypothetical here:

  * Deleting the `state != HELD` early return left
    `test_a_second_terminal_outcome_posts_nothing` GREEN, because the LEDGER's
    posting key refuses the second entry, so the entry COUNT never moves. The
    count was measuring the ledger's guard while claiming to measure the
    service's. What the early return actually protects is the ROW — without it
    a second refusal rewrites `released_at` to today, and the books would say
    the $25.00 was earned on a date no entry was made. The assertion is now the
    DATE, and break 4 above is the re-run against it.
  * Deleting payments' replay branch left `test_a_replayed_collection_posts_once`
    GREEN, because that case goes through `collect_fee`, which has an
    idempotency guard of its OWN on `service_requests.fee_receipt_no` and
    returns before payments is ever reached. `DEF-058` is exactly this — one
    guard silently standing in for another — so the two are asserted separately
    now, and `test_payments_own_replay_guard_holds_when_called_directly` calls
    payments directly.

⚠ **HARD-WON LAW 14 — THE SAVEPOINT CASE MUST BE RUN ON REAL POSTGRESQL.**
`config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-
transaction state, so `test_an_unmapped_charge_code_does_not_block_a_refusal`
passes on the default suite whether or not the nested `transaction.atomic()` is
there. It carries `requires_postgres` and was run against the real database; the
lane report quotes the run.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.customers import payments_seam
from apps.customers import service_request_service as sr
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line
from apps.ledger import models as ledger_models
from apps.payments import counter_receipt_models as cr_models
from apps.payments import counter_receipts
from apps.payments import models as payments_models
from apps.rating import models as rating_models
from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The PO's own figure, and it is the number this whole file turns on.
TWENTY_FIVE = Decimal("25.00")
RECEIPT = "RCP-26-4471"
TAKEN_AT = datetime(2026, 5, 12, 10, 30, tzinfo=dt_timezone.utc)

CAPTURE = {
    "channel": "at_the_counter",
    "applicant_kind": "person",
    "applicant_name": "Miller, Sarah",
    "applicant_email": "s.miller@example.com",
    "applicant_phone": "(512) 555-0142",
    "address_as_given": "212 Balcones Dr",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "New connection",
}


def _gl(tenant, code):
    return ledger_models.LedgerAccount.objects.get(tenant=tenant, code=code)


def _map_request_fee(tenant, account_code="4600"):
    """Give `CC-REQFEE` a `charges` row pointed at an account — a TENANT act.

    ⚠ **THIS IS SETUP AND NOT A FIX.** A real tenant quoting a real code
    (`CONN`, `TAP`, `IMPACT` …) resolves fine; a code with no `charges` row does
    not, and `test_an_unmapped_charge_code_does_not_block_a_refusal` covers what
    happens then.

    ⚠ **THE PARAGRAPH THAT STOOD HERE IS OVERTAKEN AND IS NOT LEFT STANDING
    (2026-09-16, `DEF-RAT-5424`).** It read *"As of 2026-09-15 `CC-REQFEE`
    exists in the sample fixture and in NO tenant's charge-code catalogue —
    Brazos Bend holds 28 codes and that is not one of them … Seeding the code
    for a whole tenant is CR-066's table and the PO's, never a lane's."* The
    measurement was right and the conclusion has been overtaken by the PO
    asking for it — *"can you add this in seeder data"* — so
    `apps.rating.sample_data.seed_sample_request_fee_charge_code` now creates
    the code at `$25.00` on the SAMPLE-data button and
    `ledger.chart.CHARGE_CODE_ACCOUNTS` starts it at `4600 Connection &
    new-service fees`. `lookup_defaults.json` is still untouched, so CR-066's
    approved platform table is still the PO's.

    This helper stays, because a unit test must not depend on a whole sample
    load to have run.
    """
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code="CC-REQFEE",
        name="Application fee",
        charge_type="one_time",
        amount_rule="flat",
        amount=TWENTY_FIVE,
        gl_account_id=_gl(tenant, account_code).id,
    )


def _request_with_a_fee(tenant, actor, *, quoted=TWENTY_FIVE, charge=None):
    request = sr.create_request(actor, dict(CAPTURE))
    quote_fee(
        actor,
        request.id,
        charge_code="CC-REQFEE",
        unit_amount=quoted,
        basis="per request",
        description="Application fee",
        charge_code_id=charge.id if charge is not None else None,
    )
    return sr.request_row(request.id)


def _entries(tenant, receipt_id):
    return list(
        ledger_models.JournalEntry.objects.filter(
            tenant=tenant, source_type="counter_receipt", source_id=receipt_id
        ).order_by("posting_key")
    )


def _legs(entry):
    """`{account code: (side, amount)}` — the entry as a person reads it."""
    return {
        line.ledger_account.code: (line.side, line.amount)
        for line in ledger_models.JournalLine.objects.filter(journal_entry=entry).select_related(
            "ledger_account"
        )
    }


def _collect(actor, request, amount=TWENTY_FIVE, receipt_no=RECEIPT, **kw):
    return sr.collect_fee(
        actor, request.id, amount=amount, method="cash", receipt_no=receipt_no, **kw
    )


def _ready_to_decide(actor, request):
    """Walk a request to the point a clerk may refuse it. No money is moved.

    ⚠ **NO `pick_up` IN THE MIDDLE ANY MORE (PO ruling 2026-09-19).** The
    ruling left the request five states and retired nine moves, `pick_up`
    among them — *"not required- you map this state when it is submitted -
    dont take seperate approval / or confirmation - it is confusion for
    user."* Every decision names `SUBMITTED` in `rules.TRANSITIONS` now, so
    the walk is submit and then decide.
    """
    sr.submit(actor, request.id)
    return sr.request_row(request.id)


def _ready_to_approve(actor, request):
    """…and on to where a clerk may APPROVE it.

    Approval has blocking conditions of its own (`CR-031`): the address must be
    resolved and the arrears search must have been done. They are cleared here
    through the same doors a clerk uses, never by writing columns — a fixture
    that reached past the guards would prove the release fires on a request the
    product would never have approved.
    """
    _ready_to_decide(actor, request)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id)  # searched, nobody found
    sr.decide_outcome(actor, request.id, outcome="new_connection")
    return sr.request_row(request.id)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE COLLECTION — the tie-out, and the two accounts by CODE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_collection_posts_a_balanced_pair(brazos, dana):
    """**$25.00 at the counter makes ONE journal entry and it balances.**

    This is the whole of the ruling's first clause: before today the money sat
    on the request row and the books said nothing.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt is not None
        assert receipt.state == cr_models.RECEIPT_HELD
        assert receipt.amount == Decimal("25.0000")
        assert receipt.receipt_no == RECEIPT
        assert receipt.collection_entry_id is not None

        entries = _entries(brazos, receipt.id)
        assert len(entries) == 1
        entry = entries[0]
        lines = ledger_models.JournalLine.objects.filter(journal_entry=entry)
        debits = sum(line.amount for line in lines if line.side == "debit")
        credits = sum(line.amount for line in lines if line.side == "credit")
        assert debits == credits == Decimal("25.0000")


def test_the_collection_debits_undeposited_and_never_cash(brazos, dana):
    """**DR `1010 Undeposited funds` · CR `2400 Customer credit balances`.**

    ⚠ **THE RATIFIED PAIR, ASSERTED BY ACCOUNT CODE SO DRIFT GOES RED.**

    The ruling row of 2026-09-15 named `1000 Cash` and is AMENDED on that one
    account by the decision-log row of the same day. The PO named no account;
    `1000` was our rendering, and it collides with their own ruling of
    2026-08-11 closing OQ-143 — *"Cash is received but undeposted in such case
    payment will say csah but ledger will say undeposited - until bank record
    and reconcilaition confirm it it is not realised"*.

    Brazos Bend's seven payment methods all point `clearing_gl_account_id` at
    1010, so that is what the tender resolves to here. A tenant that maps a
    tender elsewhere gets that account — which is the point: the counter
    receipt carries no account rule of its own.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        legs = _legs(_entries(brazos, receipt.id)[0])

        assert set(legs) == {"1010", "2400"}
        assert legs["1010"] == ("debit", Decimal("25.0000"))
        assert legs["2400"] == ("credit", Decimal("25.0000"))
        assert "1000" not in legs


def test_the_collection_writes_an_audit_row(brazos, dana, audit_rows):  # noqa: F811
    """Hard rule 7 — every money action writes `audit_log`."""
    with tenant_ctx(brazos):
        charge = _map_request_fee(brazos)
        request = _request_with_a_fee(brazos, dana, charge=charge)
        audit_rows.clear()
        _collect(dana, request)
        mine = [r for r in audit_rows if r["action"] == counter_receipts.AUDIT_COLLECTED]
        assert mine, "a money action with no audit row is hard rule 7 broken"
        assert mine[-1]["after"]["amount"] == "25.0000"
        assert mine[-1]["after"]["receipt_no"] == RECEIPT


def test_a_replayed_collection_posts_once(brazos, dana):
    """**Hard rule 6, and p079's own sentence.** The desk is exactly where a
    double-click happens: *"The same receipt number again answers with what is
    already recorded."*"""
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        _collect(dana, request)  # the submit button, twice

        # ⚠ **SCOPED TO THIS REQUEST, NOT TO THE TENANT.** A tenant-wide count
        # passed on sqlite and FAILED on PostgreSQL, because the sample-data
        # plant runs eagerly there and `apps/customers/sample_data.py:2316`
        # calls `collect_fee` itself — so the demo utility legitimately carries
        # counter receipts of its own now. Counting the tenant was measuring
        # the fixture; counting the SOURCE measures the guard.
        receipts = cr_models.CounterReceipt.objects.filter(
            tenant=brazos, source_type="service_request", source_id=request.id
        )
        assert receipts.count() == 1
        assert len(_entries(brazos, receipts.first().id)) == 1


def test_payments_own_replay_guard_holds_when_called_directly(brazos, dana):
    """**The two guards are asserted SEPARATELY, because `DEF-058` is what
    happens when one silently stands in for another — and here one did.**

    `test_a_replayed_collection_posts_once` above goes through `collect_fee`,
    which has an idempotency guard of its OWN on `service_requests.
    fee_receipt_no`. Deleting payments' guard leaves that test GREEN, because
    the customers-side check returns before payments is ever reached. The red
    proof is what found that out.

    So this case calls payments directly, which is the only way to see its own
    guard work — and it is not a hypothetical caller: `attach_to_account` and
    `GET /counter-receipts` are already on this side of the seam.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        again = counter_receipts.record_counter_receipt(
            source_type="service_request",
            source_id=request.id,
            source_ref=request.request_no,
            receipt_no=RECEIPT,
            amount=TWENTY_FIVE,
            currency="USD",
            method_code="cash",
            taken_at=TAKEN_AT,
        )
        assert again["receipt_no"] == RECEIPT
        assert (
            cr_models.CounterReceipt.objects.filter(
                tenant=brazos, source_type="service_request", source_id=request.id
            ).count()
            == 1
        )
        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert len(_entries(brazos, receipt.id)) == 1


def test_a_different_receipt_number_is_refused_by_name(brazos, dana):
    """p079: *"a DIFFERENT one on a request that has already been collected is
    refused and names the receipt it already holds."* Two receipts against one
    application is a fact no rule describes, and summing them would move money
    on a guess."""
    from core import errors

    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        with pytest.raises(errors.BizError) as refusal:
            _collect(dana, request, receipt_no="RCP-26-9999")
        assert RECEIPT in str(refusal.value.params)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE TWO TERMINAL OUTCOMES — and the third door, which posts nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_refusing_earns_the_fee_and_the_money_stays_in_the_books(brazos, dana):
    """**PO: *"if it is refuse then it is application fees non refundable - it
    stya in books"*.**

    The liability is released to the charge code's OWN revenue account and the
    holding account is untouched — the cash is still there, it has simply
    stopped being owed to anybody.

    ⚠ p085's drawn hedge — *"holding `$25.00` that may have to be given back"* —
    is WITHDRAWN by this ruling and this test is what holds the reversal.
    """
    with tenant_ctx(brazos):
        charge = _map_request_fee(brazos)
        request = _request_with_a_fee(brazos, dana, charge=charge)
        _collect(dana, request)
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears at a previous address")

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.state == cr_models.RECEIPT_EARNED
        assert receipt.earned_amount == Decimal("25.0000")
        assert receipt.release_error is None

        entries = _entries(brazos, receipt.id)
        assert len(entries) == 2
        release = [e for e in entries if e.posting_key.endswith("|released")][0]
        legs = _legs(release)
        assert legs["2400"] == ("debit", Decimal("25.0000"))
        assert legs["4600"] == ("credit", Decimal("25.0000"))

        # THE TIE-OUT: the cash is still in the books, and 2400 nets to zero.
        assert _net(brazos, "1010") == Decimal("25.0000")
        assert _net(brazos, "2400") == Decimal("0.0000")
        assert _net(brazos, "4600") == Decimal("-25.0000")


def test_approving_earns_the_fee_the_same_way(brazos, dana):
    """**PO: *"when it is approved you can attached it to account"*.**

    The MONEY half of that sentence is this: the held credit is applied to the
    application fee, which is where it becomes revenue — the identical pair a
    refusal posts, because in double entry *applied to the fee* and *earned
    because it is non-refundable* are one act.

    ⚠ **THE ATTACH HALF IS `DEF-PAY-5394` AND IS NOT ASSERTED HERE**, because
    approval opens no account: `payment_id` is still None afterwards and this
    test says so out loud rather than leaving a reader to assume it was done.
    """
    with tenant_ctx(brazos):
        charge = _map_request_fee(brazos)
        request = _request_with_a_fee(brazos, dana, charge=charge)
        _collect(dana, request)
        _ready_to_approve(dana, request)
        sr.approve(dana, request.id)

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.state == cr_models.RECEIPT_APPLIED
        assert receipt.earned_amount == Decimal("25.0000")
        release = [e for e in _entries(brazos, receipt.id) if e.posting_key.endswith("|released")]
        assert _legs(release[0])["2400"] == ("debit", Decimal("25.0000"))
        assert _legs(release[0])["4600"] == ("credit", Decimal("25.0000"))
        # DEF-PAY-5394 — there is no account to attach to at approval.
        assert receipt.payment_id is None


def test_ask_for_more_posts_nothing(brazos, dana):
    """**PO: *"if it is ask more then it stays in all 3 places in payment, in
    ledger and in finance"*.**

    Ask for more is not a decision about the money. No entry is made and none is
    reversed — the liability is released only by the two TERMINAL outcomes, and
    this case exists because a lane reading only the approve and refuse clauses
    would reasonably wonder whether the third door needed a posting of its own,
    and would then invent one.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        _ready_to_decide(dana, request)
        sr.ask_for_more(dana, request.id, reason="The site plan will not open")

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.state == cr_models.RECEIPT_HELD
        assert receipt.released_at is None
        assert len(_entries(brazos, receipt.id)) == 1  # the collection, and nothing else
        assert _net(brazos, "2400") == Decimal("-25.0000")  # still a liability, credit side


def test_a_second_terminal_outcome_posts_nothing(brazos, dana):
    """A refusal, then a second release attempt, earn the fee ONCE.

    ⚠ **THE WALK THIS TEST USED TO MAKE NO LONGER EXISTS, AND THE GUARD IT
    PROTECTS STILL DOES.** It refused, called `reopen`, and refused again. The
    PO's ruling of 2026-09-19 retired `reopen` with eight other moves and made
    Refuse terminal, so that walk now stops at the state table and never
    reaches the money at all. **Whether `Reopen` comes back is an OPEN question
    put to the PO and is deliberately NOT answered here** (decision log,
    *THE REQUEST DETAIL PAGE AGAINST ITS DRAWING*; the drawing still names it on
    p088 of the 281-page edition), so this test asserts today's product and
    invents no replacement door.

    ⚠ **BOTH HALVES ARE ASSERTED ON PURPOSE.** Stopping at *the second refusal
    is refused* would leave the release guard untested — the transition now
    fails one layer ABOVE the money, so deleting the service's `state != held`
    early return would no longer turn this red. So the release is ALSO called
    directly, a second time, with a LATER timestamp: that is the exact call the
    old walk made on its way through, and the date assertion below is what
    catches the row being rewritten.
    """
    from core import errors

    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears")
        first_release = counter_receipts.receipt_for_source(
            "service_request", request.id
        ).released_at

        # The old door: a refused request is terminal and cannot be decided again.
        with pytest.raises(errors.BizError) as caught:
            sr.refuse_request(dana, request.id, reason="Still arrears")
        assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed"

        # The guard the walk used to reach, exercised where it actually lives.
        # ⚠ The REAL quote is handed over, not an empty list: an empty one fails
        # for a second reason (nothing to earn) and would hide whether the early
        # return is doing its job at all.
        payments_seam.release_counter_receipt(
            source_type=payments_seam.SOURCE_SERVICE_REQUEST,
            source_id=request.id,
            outcome="refused",
            fee_lines=sr._fee_lines_for_release(request.id),
            released_at=first_release + timedelta(days=1),
            released_by_id=None,
            actor=dana,
        )

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        released = [e for e in _entries(brazos, receipt.id) if e.posting_key.endswith("|released")]
        assert len(released) == 1
        assert receipt.earned_amount == Decimal("25.0000")
        # ⚠ **THE ENTRY COUNT ALONE DOES NOT HOLD THIS, AND THE RED PROOF IS
        # WHAT FOUND THAT OUT.** With the service's `state != held` early return
        # deleted, the count stays 1 — the LEDGER's posting key refuses the
        # second entry — and the test still passed. What the early return
        # actually protects is the ROW: without it the second refusal rewrites
        # `released_at` to today, and the books would say the $25.00 was earned
        # on a date no entry was made. So the assertion is the DATE.
        assert receipt.released_at == first_release


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE EDGES THE RULES DID NOT DESCRIBE, AND THE DECISIONS TAKEN
# ═══════════════════════════════════════════════════════════════════════════
def test_over_collection_earns_only_the_quote(brazos, dana):
    """**$30.00 handed over against a $25.00 application fee earns $25.0000 and
    leaves $5.0000 a liability** (decision log, 2026-09-15).

    `4xxx` is money EARNED and `2400` is money HELD. The PO ruled an APPLICATION
    FEE non-refundable; $5.00 above one is not an application fee, and earning
    it would be the mirror of the defect p085 warns about — instead of silently
    writing off a receipt, silently earning money we owe back.

    ⚠ **REACHED BY A WAIVE AFTER COLLECTION SINCE 2026-09-24.** The desk takes
    the WHOLE fee now (`OQ-CUS-12624`, `DEF-CUS-6455`), so $30.00 cannot be
    handed over against $25.00. It is taken against a $30.00 quote whose $5.00
    line is waived afterwards — the one road to more cash than quote that is
    left, and the one this rule still has to hold for.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        extra = quote_fee(
            dana,
            request.id,
            charge_code="CC-EXPED",
            unit_amount=Decimal("5.00"),
            basis="per request",
            description="Expedited handling",
        )
        _collect(dana, request, amount=Decimal("30.00"))
        sr.waive_fee_line(dana, extra.id, reason="Not expedited after all")
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears")

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.amount == Decimal("30.0000")
        assert receipt.earned_amount == Decimal("25.0000")
        assert counter_receipts.receipt_dict(receipt)["held_remaining"] == "5.0000"
        assert _net(brazos, "2400") == Decimal("-5.0000")  # still owed to somebody
        assert _net(brazos, "4600") == Decimal("-25.0000")


def test_a_part_payment_earns_only_what_was_taken(brazos, dana):
    """quoted **$130.00**, taken **$25.00**, refused → **$25.0000 released**.

    The $105.00 was never collected and posts nowhere. BR-CUS-090's own worked
    figure, carried through to the books.

    ⚠ **REACHED BY A LINE ADDED AFTER COLLECTION SINCE 2026-09-24.** The desk
    refuses $25.00 against $130.00 now (`OQ-CUS-12624`, `DEF-CUS-6455`), so the
    whole $25.00 fee is taken and a $105.00 line is quoted afterwards — the
    road to less cash than quote that is left (`fee_total_to_collect` serves
    `quoted_at_collection` beside the live quote for exactly this).
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        quote_fee(
            dana,
            request.id,
            charge_code="CC-EXPED",
            unit_amount=Decimal("105.00"),
            basis="per request",
            description="Expedited handling",
        )
        assert sr.fee_total_to_collect(request.id)["quoted"] == Decimal("130.0000")
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears")

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.earned_amount == Decimal("25.0000")
        assert _net(brazos, "4600") == Decimal("-25.0000")


@requires_postgres
def test_an_unmapped_charge_code_does_not_block_a_refusal(brazos, dana):
    """**A chart gap never traps a clerk at a counter — and law 14 is why this
    case carries `requires_postgres`.**

    `release_counter_receipt` catches the books' refusal and lets the terminal
    outcome stand. On PostgreSQL a failed statement aborts the WHOLE
    transaction, so without the nested `transaction.atomic()` SAVEPOINT the
    refusal would take the state change down with it at COMMIT. The suite's
    default SQLite has no aborted state and this passes there either way, which
    is the trap hard-won law 14 exists for.

    The liability STAYS and `release_error` says whose configuration to fix —
    `payment_import_rows.commit_error`'s rule: *"a row that skipped silently
    would be money nobody chased."*
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana)  # no `charges` row at all
        _collect(dana, request)
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears")

        assert sr.request_row(request.id).state == "refused"  # the clerk was not blocked
        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.state == cr_models.RECEIPT_EARNED
        assert receipt.earned_amount == Decimal("0.0000")
        assert "GL account" in (receipt.release_error or "")
        assert _net(brazos, "2400") == Decimal("-25.0000")  # visible, not written off
        assert len(_entries(brazos, receipt.id)) == 1  # the collection only


def test_the_tender_detail_is_kept_and_the_card_number_is_not(brazos, dana):
    """**PO: *"we need to allow to take payment detials, card detial scheck
    details here curerntly is is not taking inputs"*.**

    Three card facts and three cheque facts, and the model carries no column for
    a card number at all — which is the point. Last four, brand and the
    terminal's authorisation code match our line to the bank's; the number
    itself is read by nothing here and would put the whole database under
    card-industry rules.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        sr.collect_fee(
            dana,
            request.id,
            amount=TWENTY_FIVE,
            method="cheque",
            receipt_no=RECEIPT,
            cheque={"number": "10241", "bank": "First National", "date": "2026-05-12"},
        )
        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        assert receipt.cheque_no == "10241"
        assert receipt.drawer_bank == "First National"
        assert receipt.cheque_date == date(2026, 5, 12)
        # `cheque` on the capture screen is `check` in the tenant's method list.
        assert receipt.method.code == "check"
        assert not hasattr(receipt, "card_number")
        assert not any(
            f.name in ("card_number", "pan", "card_pan") for f in receipt._meta.get_fields()
        )


def test_the_card_detail_rides_the_same_door(brazos, dana):
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        sr.collect_fee(
            dana,
            request.id,
            amount=TWENTY_FIVE,
            method="card",
            receipt_no=RECEIPT,
            card={"last4": "4242", "brand": "visa", "auth_code": "A19422"},
        )
        served = sr.fee_total_to_collect(request.id)["counter_receipt"]
        assert served["card_last4"] == "4242"
        assert served["card_brand"] == "visa"
        assert served["card_auth_code"] == "A19422"
        assert served["amount"] == "25.0000"  # 4 dp stored; DISPLAY rounds to 2


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE FINANCE READ, AND THE ATTACH THAT HAS NO CALLER
# ═══════════════════════════════════════════════════════════════════════════
def test_the_finance_read_shows_the_money_and_its_held_total(brazos, dana):
    """`GET /counter-receipts` — the payments half of *"show in payments"*.

    `held` is the figure the screen exists for: what `2400` is still carrying.

    ⚠ **`by_method` WAS ADDED TO THIS SHAPE ON 2026-09-19 AND THIS ASSERTION
    WENT RED, WHICH IS THE ASSERTION DOING ITS JOB.** It pins `totals` by exact
    equality rather than by the keys somebody happens to check, so a member
    cannot be added to a published money shape without a human seeing it. The
    member was kept and this line moved — deliberately, and recorded here — so
    the next reader knows the shape grew by decision rather than by drift. What
    it carries is the day's takings split by tender, because a `taken` of
    `$55.0000` over cash AND cheque cannot be counted against a drawer that
    holds only the cash.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        rows = counter_receipts.list_queryset()
        assert rows.count() == 1
        totals = counter_receipts.list_totals(rows)
        assert totals == {
            "taken": "25.0000",
            "held": "25.0000",
            "currency": "USD",
            "count": 1,
            "by_method": [
                {
                    "method": "cash",
                    "method_name": totals["by_method"][0]["method_name"],
                    "taken": "25.0000",
                    "held": "25.0000",
                    "currency": "USD",
                    "count": 1,
                }
            ],
        }
        assert counter_receipts.list_queryset(state="earned").count() == 0


def test_attach_to_account_writes_one_payment_and_no_second_entry(brazos, dana):
    """**`DEF-PAY-5394` — this function has a test and NO production caller.**

    Approval raises WORK; it opens no account, and `customers.Account` carries
    no link back to a request, so nothing can call this yet. It is written and
    proved here so the account-opening lane does not discover the requirement as
    a surprise, and it is REPORTED as unwired rather than counted as built
    (hard-won law 2).

    The books are already right — the holding account was debited at collection
    and the revenue credited at release — so this posts NOTHING. It is a record.
    """
    from tests.test_w3_billing_models import an_account

    with tenant_ctx(brazos):
        charge = _map_request_fee(brazos)
        request = _request_with_a_fee(brazos, dana, charge=charge)
        _collect(dana, request)
        _ready_to_approve(dana, request)
        sr.approve(dana, request.id)

        receipt = counter_receipts.receipt_for_source("service_request", request.id)
        before = len(_entries(brazos, receipt.id))
        account = an_account(dana, brazos, account_no="A-26-0001")
        counter_receipts.attach_to_account(
            source_type="service_request",
            source_id=request.id,
            account_id=account.id,
            attached_at=TAKEN_AT,
        )
        receipt.refresh_from_db()
        assert receipt.payment_id is not None
        payment = payments_models.Payment.objects.get(id=receipt.payment_id)
        assert payment.account_id == account.id
        assert payment.amount == Decimal("25.0000")
        assert payment.purpose == payments_models.PURPOSE_PREPAY
        # No second posting: the money is already in the books.
        assert len(_entries(brazos, receipt.id)) == before


# ── helpers that read the books ─────────────────────────────────────────────
def _net(tenant, code):
    """Debits − credits for one account, over the whole tenant. The tie-out."""
    account = _gl(tenant, code)
    lines = ledger_models.JournalLine.objects.filter(tenant=tenant, ledger_account=account)
    debits = sum((line.amount for line in lines if line.side == "debit"), Decimal("0"))
    credits = sum((line.amount for line in lines if line.side == "credit"), Decimal("0"))
    return (debits - credits).quantize(Decimal("0.0001"))



# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE TWO GUARANTEES THE MODEL CLASS CANNOT GIVE — migration 0028
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **BOTH CARRY `requires_postgres` AND NEITHER IS OPTIONAL FOR A 🔒 PATH.**
# The suite's default is in-memory SQLite, which has neither row-level security
# nor the trigger, so a case written without the marker would pass over a table
# with no isolation at all — `DEF-101`'s shape, where twelve rating cases
# skipped on the one database that could have proved anything.


@requires_postgres
def test_a_counter_receipt_is_rls_scoped(rls, brazos, lonestar, dana):  # noqa: F811
    """**Hard rule 1.** A counter receipt names a person, the address they are
    applying for and the last four digits of their card. A cross-tenant read is
    somebody else's customer.

    Asserted through the NON-SUPERUSER probe role, because a plain ORM query
    inside `tenant_ctx` runs as the app's superuser and **bypasses RLS
    unconditionally** — an assertion made that way is vacuous and has fooled
    this repo before.
    """
    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        owned = counter_receipts.receipt_for_source("service_request", request.id)

    assert_rls_scoped(
        rls, "counter_receipts", owner=brazos, intruder=lonestar, owner_ids={str(owned.id)}
    )
    assert_no_foreign_rows_anywhere(rls, lonestar, ("counter_receipts",))


@requires_postgres
def test_the_freeze_trigger_refuses_an_edit_and_a_delete(brazos, dana):
    """**Hard rule 4, and the database is the guarantee — this class is not.**

    `migrations/0028` freezes what was handed over and opens exactly nine
    release columns. Three probes, each a different clause:

      * **the AMOUNT** cannot be rewritten — a receipt whose amount could change
        would stop being evidence of what was in the drawer;
      * **the RECEIPT NUMBER** cannot be rewritten — it is what a finance
        reconciliation matches on;
      * **DELETE is refused in every state** — *"a refusal that silently wrote
        off a receipt is how a cash drawer stops reconciling"* (p085), and
        deleting one is that sentence at its worst.

    And the release columns DO move, which is the other half: a check that
    refused everything would be a check that makes the feature impossible.
    """
    from django.db import connection, transaction as db_transaction

    with tenant_ctx(brazos):
        request = _request_with_a_fee(brazos, dana, charge=_map_request_fee(brazos))
        _collect(dana, request)
        row = counter_receipts.receipt_for_source("service_request", request.id)

        for column, value, what in (
            ("amount", "999.0000", "the amount"),
            ("receipt_no", "'RCP-FORGED'", "the receipt number"),
        ):
            with pytest.raises(Exception) as refusal:
                with db_transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE counter_receipts SET {column} = {value} WHERE id = %s", [row.id]
                    )
            assert "hard rule 4" in str(refusal.value), what

        with pytest.raises(Exception) as refusal:
            with db_transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("DELETE FROM counter_receipts WHERE id = %s", [row.id])
        assert "never deleted" in str(refusal.value)

        # …and the release half still moves, or the guard would be a wall.
        _ready_to_decide(dana, request)
        sr.refuse_request(dana, request.id, reason="Arrears")
        assert (
            counter_receipts.receipt_for_source("service_request", request.id).state
            == cr_models.RECEIPT_EARNED
        )
