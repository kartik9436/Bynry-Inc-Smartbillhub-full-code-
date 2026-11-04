# ── Trace ──────────────────────────────────────────────
# Story:   CR-110-BRC04 phase 2 wave 5 — `GET /api/{utility}/partner/v1/ledger`.
#          Two of our rows into one of theirs, and the entry that does not
#          collapse at all.
# Rules:   CLAUDE.md hard rule 5 (balanced pairs) · hard rule 2 (money stored to
#          4 decimals, DISPLAYED to 2) · hard rule 1 (tenant scoping) ·
#          BR-LED-003 (a draft entry is not in the books) · BR-LED-021 (the
#          `JE-` number is stamped at post) · BR-INT-044 (the auth refusals are
#          ONE refusal) · BR-INT-054 (integrations lands and hands over) ·
#          hard-won law 7 (name the false pass and refuse it)
# ───────────────────────────────────────────────────────
"""THE BOOKS, IN A PARTNER'S SHAPE — and the proof that nothing moved.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
------------------------------------------------------------------
**(a) A FIXTURE OF ONLY TWO-LINE ENTRIES.** A balanced pair of one debit and
one credit collapses into Aclarian's row with no arithmetic at all, so a suite
built on one would be green over a transform that has never run. The fixture
here is a real bill — base, usage and tax, one debit against THREE credits —
and `test_a_three_credit_bill_becomes_three_rows_that_sum_to_the_debit` is the
case this file exists for. There is a one-debit-one-credit entry too, and it is
there to prove the N = 1 case still lands in their exact shape, never as the
only evidence.

**(b) A FIXTURE WHOSE SIDES ARE EQUAL BY CONSTRUCTION.** Asserting that debits
equal credits over rows built from a balanced entry is close to asserting that
addition works. So `test_the_balance_assertion_can_actually_fail` perturbs one
line's amount and asserts the SAME comparison goes the other way — the check is
shown red before it is trusted green, in `pytest`, which is the harness that
runs it.

**(c) A FIXTURE WHERE EVERY ENTRY HAS AN ACCOUNT.** `consumerNo` would then be
non-null everywhere and the null path would never run — and the null path is
the one that matters, because a period close and a bank fee are exactly the
entries a partner reconciling a month cannot do without. `bank_fee` carries no
account dimension and is asserted, not filtered.

**(d) A TOTAL COMPUTED THE SAME WAY TWICE.** `row_total` would agree with a
walk that used `row_total` to decide how far to walk. So the walk here pages
until a page comes back short and counts what it actually received.

RED PROVED FIRST, IN `pytest`
------------------------------
Every case below was run against a deliberately broken tree before it was
trusted green; the failures are quoted in the CR section and in this lane's
report. `python3 <module>` was not used anywhere — a red proof through an entry
point nothing uses is no proof of the thing that matters (`DEF-GOV-3733`).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.integrations import models as int_models
from apps.integrations import partner_api, services
from apps.integrations.runners import serve
from apps.integrations.seams import ledger as ledger_seam
from apps.ledger import models as led_models
from apps.ledger import posting
from core import crypto
from tests.test_cr110_phase2_partner_reference import (  # noqa: F401 — the door is lane A's
    ACLARIAN,
    ALLOWED_ADDRESS,
    ALLOWLIST,
    KEY,
    _body,
    _connect,
    _get,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

BOOK_DATE = date(2026, 7, 31)
POSTED_AT = datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc)
WINDOW = {"start_date": "2026-07-01", "end_date": "2026-07-31"}


# ── the smallest chart and the entries these cases need ────────────────────


def gl(tenant, code, type_="revenue"):
    row, _made = led_models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": f"GL {code}", "type": type_}
    )
    return row


def customer_account(tenant, actor):
    """The smallest lawful `customers.Account` — it exists so a journal line can
    carry the `account` DIMENSION and the payload can show a real `consumerNo`.

    ⚠ **A FIXTURE THAT CANNOT TELL A REAL VALUE FROM A MISSING ONE IS HOW A
    NULL HIDES** (law 7). Without a real account here every `consumerNo` in the
    payload would be null, and `test_an_entry_with_no_customer_is_served_with_a_
    null_consumer_no` would pass over a transform that never reads the column.

    The shape is `test_cr048_a1_rule_at_queue_time.an_account`'s, reused rather
    than reinvented — `ck_accounts_anchored` and `ck_accounts_regular_has_unit`
    both bite, and each was met by guessing once before this was copied from the
    helper that already knew.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="1408 Bluestem Ln")
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no="AC-2026-00001",
    )


def line(account, side, amount, *, account_id=None):
    return posting.PostingLine(
        ledger_account_id=account.id,
        side=side,
        amount=Decimal(amount),
        source_type="invoice_line",
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, f"cr110-w5/{account.code}/{side}/{amount}"),
        account_id=account_id,
    )


def post(tenant, lines, *, key, memo, entry_date=BOOK_DATE):
    return posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=POSTED_AT,
            currency="USD",
            lines=tuple(lines),
            source_type="invoice",
            source_id=uuid.uuid5(uuid.NAMESPACE_URL, f"cr110-w5/{key}"),
            memo=memo,
        )
    )


@pytest.fixture()
def books(brazos, dana):
    """A real bill, a real payment and an entry with no customer behind it.

    ⚠ **THE BILL IS THE POINT AND IT IS NOT A TWO-LINE ENTRY.** One debit to
    `1200 Accounts receivable` for 117.30 against THREE credits — 12.00 base,
    103.00 usage, 2.30 tax — which is the shape `BR-BIL-011`'s *one bill = one
    balanced journal entry* actually produces and the shape Aclarian's single
    row cannot hold.
    """
    with tenant_ctx(brazos):
        account = customer_account(brazos, dana)
        receivable = gl(brazos, "1200", "asset")
        base = gl(brazos, "4105")
        usage = gl(brazos, "4100")
        tax = gl(brazos, "2200-01", "liability")
        cash = gl(brazos, "1010", "asset")
        fees = gl(brazos, "6900", "expense")

        post(
            brazos,
            [
                line(receivable, "debit", "117.30", account_id=account.id),
                line(base, "credit", "12.00", account_id=account.id),
                line(usage, "credit", "103.00", account_id=account.id),
                line(tax, "credit", "2.30", account_id=account.id),
            ],
            key="invoice|w5-bill|issued",
            memo="Bill BL-2607-000014 issued",
        )
        post(
            brazos,
            [
                line(cash, "debit", "117.30", account_id=account.id),
                line(receivable, "credit", "117.30", account_id=account.id),
            ],
            key="payment|w5-pay|received",
            memo="Payment PY-260731-0001",
        )
        # ⚠ NO `account_id` ON EITHER LINE — a bank fee has no customer behind
        # it, and it is exactly the row a partner reconciling a month needs.
        post(
            brazos,
            [line(fees, "debit", "18.50"), line(cash, "credit", "18.50")],
            key="fee|w5-bank|charged",
            memo="Bank charge, July",
        )
        connection = _connect(brazos, dana)
    serve.reset_partner_limits()
    return connection


def _ledger(tenant, **query):
    params = dict(WINDOW)
    params.update(query)
    return _get(tenant, partner_api.partner_ledger, query=params, path="/partner/v1/ledger")


def _rows(response):
    return json.loads(_body(response))


def _sides(rows):
    """Σ debits and Σ credits ACROSS THE PARTNER'S ROWS — which is the only
    number that matters, because it is the one their GL will post."""
    debits = sum(
        (Decimal(one["amount"]) for one in rows if one["debitAccount"] is not None), Decimal(0)
    )
    credits = sum(
        (Decimal(one["amount"]) for one in rows if one["creditAccount"] is not None), Decimal(0)
    )
    return debits, credits


# ══════════════════════════════════════════════════════════════════════════
# THE COLLAPSE — the case this file exists for
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_three_credit_bill_becomes_three_rows_that_sum_to_the_debit(books, brazos) -> None:
    """⚠ **THE MULTI-LINE ENTRY, ASSERTED ON PURPOSE (law 7, false pass (a)).**

    One debit of 117.30 against three credits does not become one row and must
    not be made to. It becomes THREE, each pairing one credit against the single
    common debit, and each carrying that credit's OWN amount — so 12.00 + 103.00
    + 2.30 = 117.30 and the entry is handed over whole.

    **Picking the first credit and calling it THE credit — the obvious move —
    would hand over 12.00 and lose 105.30**, on a row that reads as settled.
    """
    body = _rows(_ledger(brazos))
    bill = [one for one in body["records"] if one["description"] == "Bill BL-2607-000014 issued"]
    assert len(bill) == 3, f"three credits, three rows: {bill}"
    assert {one["debitAccount"] for one in bill} == {"1200"}, "every row names the common debit"
    assert {one["creditAccount"] for one in bill} == {"4105", "4100", "2200-01"}
    assert sorted(one["amount"] for one in bill) == ["103.00", "12.00", "2.30"]
    assert sum((Decimal(one["amount"]) for one in bill), Decimal(0)) == Decimal("117.30")
    # `accountString` is the code of the line that GAVE the row its amount —
    # the revenue or tax account here, which is what the specification's own
    # sample draws (there `accountString` and `creditAccount` are one string).
    assert all(one["accountString"] == one["creditAccount"] for one in bill)


@pytest.mark.django_db
def test_the_balance_is_kept_across_every_row_of_every_entry(books, brazos) -> None:
    """Hard rule 5, restated over the transform: Σ debits = Σ credits, BEFORE
    and AFTER. Asserted over the whole window rather than one entry, because a
    transform can balance each entry and still lose one."""
    body = _rows(_ledger(brazos))
    debits, credits = _sides(body["records"])
    with tenant_ctx(brazos):
        ours = led_models.JournalLine.objects.filter(
            tenant=brazos, journal_entry__status=led_models.JE_POSTED
        )
        our_debits = sum(
            (one.amount for one in ours if one.side == led_models.SIDE_DEBIT), Decimal(0)
        )
        our_credits = sum(
            (one.amount for one in ours if one.side == led_models.SIDE_CREDIT), Decimal(0)
        )
    assert debits == credits, f"the partner's rows do not balance: {debits} vs {credits}"
    assert our_debits == our_credits, "our own books do not balance — the fixture is wrong"
    assert debits == our_debits.quantize(Decimal("0.01")), (
        f"the transform moved money: ours {our_debits}, theirs {debits}"
    )


@pytest.mark.django_db
def test_the_balance_assertion_can_actually_fail(books, brazos) -> None:
    """⚠ **LAW 7'S FALSE PASS (b), REFUSED — AND THE FIRST ATTEMPT AT THIS CASE
    WAS ITSELF INCAPABLE OF FAILING, WHICH IS THE FINDING WORTH KEEPING.**

    The obvious version moved one credit by a cent and asserted that Σ debits ≠
    Σ credits **across the partner's rows**. It stayed green, and it always
    would have: **a PAIRED row carries ONE amount that is both its debit and its
    credit**, so comparing the two sides of the partner's payload to each other
    compares a number with itself. It cannot see a lopsided entry at all.

    **The comparison that bites is against OUR OWN books**, which is what
    `test_the_balance_is_kept_across_every_row_of_every_entry` makes and what is
    re-made here over a deliberately broken entry. One credit of the three-credit
    bill is moved, the rows no longer sum to the debit they were paired against,
    and the check goes red. (Our database cannot actually reach this state —
    `migrations/0002`'s balance trigger refuses an unbalanced post — so the row
    is broken with an `.update()` that goes round it, which is the only way to
    show the check working.)
    """
    with tenant_ctx(brazos):
        entry = led_models.JournalEntry.objects.get(memo="Bill BL-2607-000014 issued")
        led_models.JournalLine.objects.filter(
            journal_entry=entry, ledger_account__code="4100"
        ).update(amount=Decimal("100.00"))  # was 103.00
        our_debits = sum(
            (
                one.amount
                for one in led_models.JournalLine.objects.filter(
                    tenant=brazos, journal_entry__status=led_models.JE_POSTED
                )
                if one.side == led_models.SIDE_DEBIT
            ),
            Decimal(0),
        )
    debits, _credits = _sides(_rows(_ledger(brazos))["records"])
    assert debits != our_debits.quantize(Decimal("0.01")), (
        "a credit was moved by three dollars and the check still agreed with our "
        "books — the balance assertion is structurally incapable of failing"
    )


@pytest.mark.django_db
def test_an_entry_with_many_lines_on_both_sides_is_not_paired(books, brazos) -> None:
    """⚠ **THE BRANCH NO ENTRY IN THE PRODUCT REACHES TODAY, WRITTEN NOW.**

    Which debit funds which credit across two-and-two is an ALLOCATION RULE,
    and the specification says in as many words that *"Final debit/credit
    handling and GL mapping should follow the accounting rules agreed with
    Aclarian"*. So nothing is paired: each line is its own row with its own
    side filled and the counter-account `null`, which a partner can SEE.

    Measured before this was written: all 168 entries on the demo tenant have
    exactly one line on one side, so this branch has no live traffic — which is
    precisely why it is proved here rather than met by a customer.
    """
    with tenant_ctx(brazos):
        post(
            brazos,
            [
                line(gl(brazos, "1010", "asset"), "debit", "40.00"),
                line(gl(brazos, "1200", "asset"), "debit", "60.00"),
                line(gl(brazos, "4100"), "credit", "70.00"),
                line(gl(brazos, "4105"), "credit", "30.00"),
            ],
            key="settlement|w5-both|split",
            memo="Two on both sides",
        )
    body = _rows(_ledger(brazos))
    rows = [one for one in body["records"] if one["description"] == "Two on both sides"]
    assert len(rows) == 4, "four lines, four rows — nothing was paired"
    for one in rows:
        named = [one["debitAccount"], one["creditAccount"]]
        assert named.count(None) == 1, f"a counter-account was guessed: {one}"
        assert one["accountString"] == (one["debitAccount"] or one["creditAccount"])
    debits, credits = _sides(rows)
    assert debits == credits == Decimal("100.00"), "the unpaired branch still balances"


@pytest.mark.django_db
def test_a_one_to_one_entry_is_exactly_the_specifications_row(books, brazos) -> None:
    """The N = 1 case of the same rule — one row, both accounts named. It is
    asserted so the pairing is known to COLLAPSE and not merely to fan out."""
    body = _rows(_ledger(brazos))
    payment = [one for one in body["records"] if one["description"] == "Payment PY-260731-0001"]
    assert len(payment) == 1
    assert payment[0]["debitAccount"] == "1010"
    assert payment[0]["creditAccount"] == "1200"
    assert payment[0]["amount"] == "117.30"


# ══════════════════════════════════════════════════════════════════════════
# THE FIELDS
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_an_entry_with_no_customer_is_served_with_a_null_consumer_no(books, brazos) -> None:
    """⚠ **LAW 7'S FALSE PASS (c).** A bank fee has no account dimension. It is
    SERVED with `consumerNo: null` and never filtered out — dropping it would
    make our books and theirs disagree by the amount of every such entry, and
    nothing on either side would raise."""
    body = _rows(_ledger(brazos))
    fee = [one for one in body["records"] if one["description"] == "Bank charge, July"]
    assert len(fee) == 1, "the entry with no customer is still handed over"
    assert fee[0]["consumerNo"] is None, "a null is an answer; a guess is not"
    assert fee[0]["debitAccount"] == "6900" and fee[0]["creditAccount"] == "1010"
    assert any(one["consumerNo"] for one in body["records"]), (
        "every consumerNo is null — the fixture cannot tell a real one from a missing one"
    )


@pytest.mark.django_db
def test_the_account_string_is_a_gl_code_and_never_composed(books, brazos) -> None:
    """PO 2026-09-16: *"this is already done using setting and plans and rates -
    bills are generated with gl code only"*. Checked and correct — so
    `accountString` is a `ledger_accounts.code` and this asserts it against the
    chart rather than against a string typed here."""
    body = _rows(_ledger(brazos))
    with tenant_ctx(brazos):
        chart = set(
            led_models.LedgerAccount.objects.filter(tenant=brazos).values_list("code", flat=True)
        )
    strings = {one["accountString"] for one in body["records"]}
    assert strings, "no rows — every assertion below would be vacuous"
    assert strings <= chart, f"a code that is in no chart: {strings - chart}"


@pytest.mark.django_db
def test_the_transaction_type_is_the_published_vocabulary_and_not_a_typed_one(
    books, brazos, monkeypatch
) -> None:
    """⚠ **IF A SEAM TYPES A VOCABULARY, THE PAYLOAD AND THE REFERENCE ENDPOINT
    CAN DISAGREE**, which is the one failure `GET /partner/v1/reference` exists
    to prevent. So the label is MOVED in the published list and the payload has
    to move with it. A seam holding its own copy stays green here."""
    from apps.integrations import reference

    monkeypatch.setitem(
        reference.TRANSACTION_TYPE_LABELS, "standard", "A label only this test wrote"
    )
    body = _rows(_ledger(brazos))
    assert body["records"], "no rows — this assertion would be vacuous"
    for one in body["records"]:
        assert one["transactionType"] == {
            "code": "standard",
            "label": "A label only this test wrote",
        }, f"the seam is not reading the published list: {one['transactionType']}"


@pytest.mark.django_db
def test_the_money_is_a_two_decimal_string(books, brazos) -> None:
    """Hard rule 2 — stored to 4, DISPLAYED to 2, and a STRING so the exactness
    survives every JSON parser on the far end. A float is the one thing the
    rule names by name."""
    body = _rows(_ledger(brazos))
    for one in body["records"]:
        assert isinstance(one["amount"], str), f"{one['amount']!r} is not a string"
        assert one["amount"] == str(Decimal(one["amount"]).quantize(Decimal("0.01")))
        assert one["currency"] == "USD"


@pytest.mark.django_db
def test_the_date_is_the_book_date(books, brazos) -> None:
    """`entry_date`, not `posted_at`. LE-9: July closes on Aug 5 and a payment
    dated Jul 30 posts INTO August — a partner's GL period is the book date's,
    and `posted_at` is when the entry became immutable, which is our fact."""
    body = _rows(_ledger(brazos))
    assert body["records"]
    for one in body["records"]:
        assert one["transactionDate"] == "2026-07-31T00:00:00Z"


@pytest.mark.django_db
def test_a_draft_entry_is_never_handed_over(books, brazos) -> None:
    """`BR-LED-003` makes a draft freely editable and freely deletable, so a
    finance system that collected one would post an entry that may still move
    or may never exist — and nothing in the payload could tell it apart."""
    with tenant_ctx(brazos):
        led_models.JournalEntry.objects.filter(memo="Bank charge, July").update(
            status=led_models.JE_DRAFT
        )
    body = _rows(_ledger(brazos))
    assert not [one for one in body["records"] if one["description"] == "Bank charge, July"]


# ══════════════════════════════════════════════════════════════════════════
# THE WINDOW, THE PAGE AND THE TOTAL
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_window_is_required(books, brazos) -> None:
    """The ledger is the largest set this product hands over — a month at the
    top of T5 is ~200,000 rows — and an unbounded walk over a moving table is
    the paging trap with nothing to bound it. A caller that forgets is told so.

    ⚠ It is a `400` and NOT the five-word refusal: it is reached only AFTER all
    nine checks, so it tells a caller nothing they do not already hold, and a
    refusal here would send them to look at their key."""
    for missing in ({"start_date": None}, {"end_date": None}, {"start_date": None, "end_date": None}):
        response = _ledger(brazos, **missing)
        assert response.status_code == 400, f"{missing} answered {response.status_code}"
        assert json.loads(_body(response))["code"] == "DATE_RANGE_REQUIRED"


@pytest.mark.django_db
def test_the_window_bounds_before_the_page_does(books, brazos) -> None:
    """Bounded by the BOOK date first, paged second — which is the half of the
    paging trap a tiebreaker cannot fix."""
    with tenant_ctx(brazos):
        post(
            brazos,
            [
                line(gl(brazos, "1010", "asset"), "debit", "5.00"),
                line(gl(brazos, "4100"), "credit", "5.00"),
            ],
            key="fee|w5-august|charged",
            memo="August, outside the window",
            entry_date=date(2026, 8, 1),
        )
    body = _rows(_ledger(brazos))
    assert not [one for one in body["records"] if "August" in (one["description"] or "")]
    wider = _rows(_ledger(brazos, end_date="2026-08-31"))
    assert [one for one in wider["records"] if "August" in (one["description"] or "")]


@pytest.mark.django_db
def test_the_total_is_the_rows_and_a_walk_of_the_pages_finds_exactly_that_many(
    books, brazos
) -> None:
    """⚠ **THE ENVELOPE'S TOTAL IS WHAT LETS A PARTNER PROVE NOTHING WAS
    SKIPPED**, so it has to be the number of things `records` holds and it has
    to be right.

    **Law 7's false pass (d):** a walk that used `total_records` to decide how
    far to go would agree with it by construction. This one pages until a page
    comes back short and counts what it actually received.
    """
    first = _rows(_ledger(brazos, page_size=1))
    total = first["total_records"]
    assert total == 5, f"3 bill rows + 1 payment + 1 bank fee: {total}"
    assert first["total_entries"] == 3, "three ENTRIES, which is what is paged"
    assert first["total_pages"] == 3

    seen: list[dict] = []
    page = 1
    while True:
        body = _rows(_ledger(brazos, page=page, page_size=1))
        seen.extend(body["records"])
        if len(body["records"]) == 0 or page >= body["total_pages"]:
            break
        page += 1
    assert len(seen) == total, f"walked {len(seen)} rows, the envelope promised {total}"
    debits, credits = _sides(seen)
    assert debits == credits, "the walk lost a side"


@pytest.mark.django_db
def test_a_page_boundary_never_falls_inside_an_entry(books, brazos) -> None:
    """⚠ **THE PAGE IS A PAGE OF ENTRIES AND THAT IS THE WHOLE REASON.**
    Pairing a debit with its credit reads a WHOLE entry. Page on lines and a
    boundary can fall between a debit and the credit it belongs to, leaving two
    half-postings that look perfectly healthy — and a fixture smaller than a
    page could never show it."""
    page = _rows(_ledger(brazos, page=1, page_size=1))
    descriptions = {one["description"] for one in page["records"]}
    assert len(descriptions) == 1, "one page of size one holds exactly one entry"
    debits, credits = _sides(page["records"])
    assert debits == credits, f"a single page does not balance: {page['records']}"


@pytest.mark.django_db
def test_the_order_carries_a_tiebreaker_that_never_repeats(books, brazos) -> None:
    """`entry_date` is a DATE, so a month's entries share a handful of values.
    Page over that with no second key and one entry can come back twice while
    another never comes back at all — **a missed journal entry is a missed
    posting**. The order therefore ends on the uuid7 primary key.
    """
    with tenant_ctx(brazos):
        ordering = ledger_seam.collectable(since=date(2026, 7, 1), until=BOOK_DATE).query.order_by
    assert ordering[-1] == "id", f"the order does not end on a unique key: {ordering}"
    walks = [
        [one["description"] for one in _rows(_ledger(brazos, page=n, page_size=1))["records"]]
        for n in (1, 2, 3)
    ]
    again = [
        [one["description"] for one in _rows(_ledger(brazos, page=n, page_size=1))["records"]]
        for n in (1, 2, 3)
    ]
    assert walks == again, "two identical walks returned different pages"
    # ⚠ **ROWS OF ONE ENTRY SHARE A DESCRIPTION BY DESIGN**, so uniqueness is
    # asked of the ENTRY SETS and not of the flat row list — the first draft
    # asked the flat question and went red on the bill's own three rows, which
    # is a test that cannot pass rather than a defect.
    entries_per_page = [set(page) for page in walks]
    seen: set[str] = set()
    for page in entries_per_page:
        assert not (page & seen), f"an entry came back on two pages: {page & seen}"
        seen |= page


@pytest.mark.django_db
def test_the_row_total_and_the_transform_cannot_drift_apart(books, brazos) -> None:
    """`row_total` applies `as_record`'s own rule in SQL. If one is changed and
    the other is not, a partner's job reports a shortfall it cannot explain —
    so they are compared against each other over a window holding BOTH branches
    of the collapse."""
    with tenant_ctx(brazos):
        post(
            brazos,
            [
                line(gl(brazos, "1010", "asset"), "debit", "40.00"),
                line(gl(brazos, "1200", "asset"), "debit", "60.00"),
                line(gl(brazos, "4100"), "credit", "70.00"),
                line(gl(brazos, "4105"), "credit", "30.00"),
            ],
            key="settlement|w5-drift|split",
            memo="Two on both sides",
        )
        queryset = ledger_seam.collectable(since=date(2026, 7, 1), until=BOOK_DATE)
        promised = ledger_seam.row_total(queryset)
        walked = sum(len(ledger_seam.as_record(one)) for one in queryset)
    assert promised == walked, f"row_total says {promised}, the transform makes {walked}"
    assert walked == 9, f"3 + 1 + 1 paired and 4 unpaired: {walked}"


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR — lane A's nine checks, asked of THIS address
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_key_with_only_the_ledger_tick_is_refused_on_the_other_three(brazos, dana) -> None:
    """⚠ **THE MIRROR OF LANE A'S THIRD PROOF.** A key granted `serve_ledger`
    alone reaches the ledger and is refused on accounts, bills and payments —
    with the ONE refusal, five words, `404`. A scope that widens the day its own
    wave lands is the failure `BR-INT-044` exists to close.

    ⚠ **THE FIRST ADDRESS READ `customers` UNTIL 2026-09-17 (`DEF-INT-5623`)**
    — the PO ruled the partner surface must call an account an account. The
    property under test did not move by a byte."""
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=["serve_ledger"])
    serve.reset_partner_limits()
    for what, view in (
        ("accounts", partner_api.partner_accounts),
        ("bills", partner_api.partner_bills),
        ("payments", partner_api.partner_v1_payments),
    ):
        response = _get(brazos, view, path=f"/partner/v1/{what}")
        assert response.status_code == 404, f"{what} answered {response.status_code}"
        assert _body(response) == (
            b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
        )
    assert _ledger(brazos).status_code == 200, "the tick this key holds reaches its address"


@pytest.mark.django_db
def test_a_bad_key_is_refused_here_exactly_as_everywhere_else(books, brazos) -> None:
    """Serving a payload is not a hole in the door: the nine checks run first."""
    response = _get(
        brazos,
        partner_api.partner_ledger,
        key="sbh_live_never_issued",
        query=WINDOW,
        path="/partner/v1/ledger",
    )
    assert response.status_code == 404
    assert _body(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


@pytest.mark.django_db
def test_another_utilitys_books_are_not_reachable_with_this_key(books, brazos, lonestar) -> None:
    """⚠ **HARD RULE 1, ASSERTED ON THE VENDOR THE SUITE ACTUALLY RUNS ON.**
    `config/settings/test.py` hardcases in-memory SQLite, which has no RLS — so
    the seam states the tenant a second time and this case can go red on either
    vendor. Written the other way round, a partner reading another utility's
    books would pass the entire suite (law 7)."""
    with tenant_ctx(lonestar):
        receivable = gl(lonestar, "1200", "asset")
        revenue = gl(lonestar, "4100")
        post(
            lonestar,
            [
                line(receivable, "debit", "999.99"),
                line(revenue, "credit", "999.99"),
            ],
            key="invoice|w5-lonestar|issued",
            memo="Lone Star bill, not Brazos Bend's",
        )
    body = _rows(_ledger(brazos))
    assert not [one for one in body["records"] if "Lone Star" in (one["description"] or "")]
    assert all(Decimal(one["amount"]) != Decimal("999.99") for one in body["records"])


@pytest.mark.django_db
def test_the_read_writes_a_row_a_manager_can_read(books, brazos) -> None:
    """S142's *What they took* column. It is written for a served page exactly
    as it is for a refusal, because a manager watching an unusual morning wants
    both in one list."""
    assert _ledger(brazos).status_code == 200
    with tenant_ctx(brazos):
        run = int_models.IntegrationRun.objects.order_by("-started_at").first()
    assert "Ledger" in run.summary, run.summary
    assert KEY not in (run.summary or ""), "a run record naming a secret is a leaked secret"


@pytest.mark.django_db
def test_a_posted_entry_carries_its_je_number_into_the_feed(books, brazos) -> None:
    """`P5.1` — *a partner quotes an entry number back and we can find it.*

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-24 AND WAS RED FOR A DAY
    (`DEF-INT-6602`).** It was called
    `test_the_envelope_names_the_missing_je_number_rather_than_composing_one`
    and it asserted `all(record["id"] is None)`, which was TRUE when it was
    written on 2026-09-17: `BR-LED-021` stamps the `JE-` number at post,
    `post_draft()` did it and `post()` — the path every bill and payment takes
    — did not. **`P0.3` (commit `b813394a6`) made `post()` allocate its own
    number**, and nothing in that change reached this file, so the suite went
    red on the fix rather than on a regression. **A test that asserts an
    ABSENCE goes red when the absence is closed**, which reads exactly like a
    break and is its opposite — CLAUDE.md law 7's *looking at the wrong thing*.

    It now asserts the thing worth protecting: post an entry the ordinary way
    and its number reaches the wire. A regression in the stamping turns this
    red, which is the direction a check should fail in.
    """
    body = _rows(_ledger(brazos))
    payment = next(
        one for one in body["records"] if one["description"] == "Payment PY-260731-0001"
    )
    assert payment["id"] is not None, (
        "posting.post() stamps BR-LED-021's number since P0.3 — a null here is the "
        "stamping regressing, not the product's known gap"
    )
    assert payment["id"].startswith("JE-"), payment["id"]
    assert payment["transactionId"] == f"{payment['id']}-1", (
        "one entry can be several rows, so the ROW reference carries its ordinal — "
        "a partner keying on a repeated value would collapse a bill's rows into one"
    )
    assert "records_note" not in body, (
        "every entry in this window is numbered, so there is no gap to name — an "
        "envelope apologising for a gap it does not have teaches a partner to ignore it"
    )


@pytest.mark.django_db
def test_an_entry_from_before_the_numbering_is_named_as_history_not_as_a_gap(
    books, brazos
) -> None:
    """`P5.1`'s other half — the 167 entries this product posted before `P0.3`.

    Nothing backfills them (measured on the demo tenant, PostgreSQL 16.13,
    2026-09-24: **167 posted entries, 0 numbered**), so a partner pulling a
    window that reaches back still meets nulls and the envelope still has to
    say why. **What changed is the SENTENCE, not the behaviour**: the code used
    to read `journal_entry_number_not_stamped_at_post`, naming a cause that has
    been fixed, and it now reads `some_entries_pre_date_journal_numbering`,
    which is true and ages out on its own.
    """
    with tenant_ctx(brazos):
        led_models.JournalEntry.objects.filter(memo="Bank charge, July").update(number=None)
    body = _rows(_ledger(brazos))
    fee = next(one for one in body["records"] if one["description"] == "Bank charge, July")
    assert fee["id"] is None
    assert body["records_note"] == partner_api.LEDGER_NUMBER_GAP
    assert partner_api.LEDGER_NUMBER_GAP == "some_entries_pre_date_journal_numbering", (
        "the code names the CONDITION a partner is in, never a cause we have since "
        "fixed — CLAUDE.md hard rule 4 records the same rename one module over"
    )
