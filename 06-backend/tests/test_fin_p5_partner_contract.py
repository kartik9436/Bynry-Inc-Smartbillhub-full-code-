# ── Trace ──────────────────────────────────────────────
# Story:   Finance blueprint `05-prototype/07 Finance Blueprint.pdf` p018 —
#          **Phase 5 · The partner contract**. `P5.2` the tax authority in the
#          feed · `P5.3` the document number rather than the internal id ·
#          `P5.5` the feed reconciles.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 5 (balanced
#          pairs — a pair is never split across a page) · hard rule 2 (money
#          stored to 4, DISPLAYED to 2) · hard rule 3 (an explicit unit) ·
#          B14 rule 31 in its WIRE form (no internal identifier leaves this
#          surface) · BR-LED-021 (the `JE-` number) · hard-won law 7 (name the
#          false pass and refuse it; prove red in the harness that will run it)
# ───────────────────────────────────────────────────────
"""THE PARTNER CONTRACT — can a partner tie every row back to a document?

That sentence is Phase 5's *Done when*, and these cases are what tests it.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
------------------------------------------------------------------
**(a) A FIXTURE WHOSE ENTRIES ARE ALL THE SAME KIND.** A window of nothing but
bills would prove `documentNo` resolves for `invoice` and say nothing about the
three other things a month holds. The fixture here posts a BILL, a PAYMENT and
an OPENING BALANCE — the last of which has no document at all and **must** come
back null. That null is the case a lane is most tempted to make go away.

**(b) A `documentNo` THAT FALLS BACK TO THE SOURCE ID.** The whole task is
*document number, not internal id*, so a fallback would put the exact value
being removed onto the field named for its replacement, and every assertion
that merely checks *is it non-null* would pass.
`test_a_row_with_no_document_number_is_null_and_never_the_uuid` asserts the
uuid is absent from the payload BY VALUE.

**(c) A PAGE-BOUNDARY CHECK ON A FIXTURE SMALLER THAN A PAGE.** `P5.5`'s real
question is whether a balanced pair can be split, and it cannot be asked at all
unless the window holds more entries than the page. Every paging case here
drives `page_size=1` over a multi-entry window, so the boundary is crossed on
every call rather than never.

**(d) A RECONCILIATION THAT ADDS UP BOTH SIDES THE SAME WAY.** `total_records`
agreeing with a walk that used `total_records` to decide how far to walk is
close to asserting that addition works. The walk here pages until a short page
arrives and counts what it actually received.

**(e) sqlite.** `config/settings/test.py` hardcodes in-memory SQLite, and the
paging guarantee is a statement about how a DATABASE orders and slices rows —
CLAUDE.md hard-won law 14's shape. `P5.5`'s cases were run against real
PostgreSQL 16.13 with `--ds=config.settings.pgtest` and the run is quoted in
this lane's report; they pass under both, which is the point of saying which
one was watched.

RED PROVED FIRST, IN `pytest`
------------------------------
Each case was run against a deliberately broken tree before it was trusted
green and the failures are quoted in this lane's report. `python3 <module>` was
not used anywhere — a red proof through an entry point nothing uses is no proof
of the thing that matters (`DEF-GOV-3733`).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.integrations import partner_api
from apps.integrations.runners import serve
from apps.integrations.seams import ledger as ledger_seam
from apps.ledger import models as led_models
from apps.ledger import posting
from tests.test_cr110_phase2_partner_reference import (  # noqa: F401 — the door is lane A's
    KEY,
    _body,
    _connect,
    _get,
)
from tests.test_cr110_wave5_partner_ledger import customer_account, gl
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

BOOK_DATE = date(2026, 7, 31)
POSTED_AT = datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc)
WINDOW = {"start_date": "2026-07-01", "end_date": "2026-07-31"}

#: The bill and the payment the fixture writes, so a case can name the number
#: it expects instead of fishing it out of the payload it is checking.
INVOICE_NO = "BL-2607-000014"
PAYMENT_NO = "PY-260731-0001"

#: The fixture's own tax jurisdiction. Deliberately NOT one of the seeded
#: names — `Local` already exists on a provisioned tenant.
AUTHORITY_NAME = "P5 Test County"


# ── the fixture: a bill, a payment, and something that is not a document ────


def _line(account, side, amount, *, account_id=None, source=None, authority_id=None):
    """⚠ **EVERY LINE NAMES A SOURCE BECAUSE `BR-LED-001` REFUSES ONE THAT DOES
    NOT** — *"an undimensioned money line can never be traced back to what
    created it"*, and `posting.post` raises on it.

    The default is the line's OWN `invoice_line`, which is the shape
    `apps/ledger/models.py` describes (*"one issue entry's lines trace to
    individual `invoice_line` rows"*). **That is not an accident of the fixture
    — it is the case `_source_document` exists for**: a bill's lines name a
    row this seam cannot resolve, so the resolution falls through to the
    ENTRY's `invoice`, which it can. A fixture whose lines named the invoice
    directly would never run that fallback.
    """
    source_type, source_id = source if source else ("invoice_line", uuid.uuid4())
    return posting.PostingLine(
        ledger_account_id=account.id,
        side=side,
        amount=Decimal(amount),
        source_type=source_type,
        source_id=source_id,
        account_id=account_id,
        tax_authority_id=authority_id,
    )


def _post(lines, *, key, memo, source_type=None, source_id=None):
    return posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=BOOK_DATE,
            posted_at=POSTED_AT,
            currency="USD",
            lines=tuple(lines),
            source_type=source_type,
            source_id=source_id,
            memo=memo,
        )
    )


@pytest.fixture()
def contract(brazos, dana):
    """A month with one of each thing a partner actually meets.

    ⚠ **THE THREE ENTRIES ARE DELIBERATELY DIFFERENT KINDS**, per (a) above: a
    BILL that points at a real `invoices` row, a PAYMENT that points at a real
    `payments` row, and an OPENING BALANCE that points at nothing because there
    is no such document. A fixture of three bills would be green over a
    transform that had never met the null.

    ⚠ **THE BILL'S TAX LINE CARRIES A REAL `tax_authority_id`, AND THAT IS THE
    ONLY WAY `P5.2` CAN BE TESTED AT ALL.** Measured on the demo tenant:
    **0 of 661 journal lines carry one**, because every row there was posted
    before `P0.3` published `rating.selectors.tax_authority_id_for_tax` for
    billing to stamp with. A fixture that reproduced that would prove nothing
    about the read.
    """
    from apps.billing import models as billing_models
    from apps.payments import models as payment_models
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        account = customer_account(brazos, dana)
        receivable = gl(brazos, "1200", "asset")
        usage = gl(brazos, "4100")
        tax_gl = gl(brazos, "2200-01", "liability")
        cash = gl(brazos, "1010", "asset")
        equity = gl(brazos, "3000", "equity")

        # ⚠ **NOT NAMED `Local`.** The seeded tenant already carries a `Local`
        # jurisdiction, and a fixture that reuses a seeded name makes every
        # lookup in this file ambiguous — `get(name="Local")` returned two.
        authority = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos,
            name=AUTHORITY_NAME,
            authority="Bexar County Tax Office",
            level="county",
            reference_no="BEX-114-9",
        )
        invoice = billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            invoice_no=INVOICE_NO,
            service_date=BOOK_DATE,
            period_start=date(2026, 7, 1),
            period_end=BOOK_DATE,
            total=Decimal("105.30"),
            currency="USD",
        )
        payment = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no=PAYMENT_NO,
            amount=Decimal("105.30"),
            currency="USD",
            status="posted",
            posted_at=POSTED_AT,
        )

        _post(
            [
                _line(receivable, "debit", "105.30", account_id=account.id),
                _line(usage, "credit", "103.00", account_id=account.id),
                _line(
                    tax_gl,
                    "credit",
                    "2.30",
                    account_id=account.id,
                    authority_id=authority.id,
                ),
            ],
            key="invoice|p5-bill|issued",
            memo=f"Bill {INVOICE_NO} issued",
            source_type="invoice",
            source_id=invoice.id,
        )
        _post(
            [
                _line(cash, "debit", "105.30", account_id=account.id),
                _line(receivable, "credit", "105.30", account_id=account.id),
            ],
            key="payment|p5-pay|received",
            memo=f"Payment {PAYMENT_NO}",
            source_type="payment",
            source_id=payment.id,
        )
        # ⚠ **NO DOCUMENT AT ALL — and `BR-LED-001` still demands a dimension,
        # so the lines name `opening_balance` rather than nothing.** That is
        # the honest shape: an opening balance is a real journal entry that no
        # printed document sits behind, which is precisely why `documentNo`
        # must be null on it and why `_DOCUMENT_SOURCES` has no route for the
        # kind. The demo tenant holds nineteen of these.
        opening = uuid.uuid4()
        _post(
            [
                _line(cash, "debit", "500.00", source=("opening_balance", opening)),
                _line(equity, "credit", "500.00", source=("opening_balance", opening)),
            ],
            key="opening_balance|p5-open|posted",
            memo="Opening balance, July",
            source_type="opening_balance",
            source_id=opening,
        )
        connection = _connect(brazos, dana)
    serve.reset_partner_limits()
    return {"connection": connection, "invoice": invoice, "payment": payment}


def _ledger(tenant, **query):
    params = dict(WINDOW)
    params.update(query)
    return _get(tenant, partner_api.partner_ledger, query=params, path="/partner/v1/ledger")


def _rows(response):
    return json.loads(_body(response))


def _row_for(body, memo_fragment):
    return [one for one in body["records"] if memo_fragment in (one["description"] or "")]


# ══════════════════════════════════════════════════════════════════════════
# P5.3 — THE DOCUMENT NUMBER, NOT THE INTERNAL ID
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_bill_row_carries_the_printed_invoice_number(contract, brazos) -> None:
    """`P5.3`'s outcome, in its own words: *a partner matches a journal line to
    a bill number they hold.*

    The number is the one PRINTED on the bill — `BL-2607-000014` — and it is
    the same string `/partner/v1/bills` already serves as that bill's `id`, so
    a partner that pulled the bills feed can join the two without asking us for
    anything.
    """
    body = _rows(_ledger(brazos))
    rows = _row_for(body, INVOICE_NO)
    assert rows, "the bill's rows are in the window"
    assert all(one["documentNo"] == INVOICE_NO for one in rows), [
        one["documentNo"] for one in rows
    ]
    assert all(one["documentType"] == "invoice" for one in rows)


@pytest.mark.django_db
def test_a_payment_row_carries_the_printed_payment_number(contract, brazos) -> None:
    """The same join on the other side of the books. `payments.payment_no` is
    *"the number a clerk and a customer both already use"*
    (`seams/payments.as_record`), which is what makes it the right thing to
    put on a ledger row a partner is trying to explain to somebody."""
    body = _rows(_ledger(brazos))
    rows = _row_for(body, PAYMENT_NO)
    assert rows
    assert all(one["documentNo"] == PAYMENT_NO for one in rows)
    assert all(one["documentType"] == "payment" for one in rows)


@pytest.mark.django_db
def test_a_row_with_no_document_number_is_null_and_never_the_uuid(
    contract, brazos
) -> None:
    """⚠ **THIS IS THE CASE THAT KEEPS THE FEATURE HONEST** — (b) above.

    Two different things are asserted and they are not the same assertion:

      1 · an OPENING BALANCE has no document, so `documentNo` is `null`. A
          product that filled it in would be naming a document that does not
          exist, on a row somebody is about to reconcile.
      2 · **no uuid appears ANYWHERE in the payload**, checked by value across
          the whole body rather than field by field. A fallback to the source
          id is the obvious shortcut and it would satisfy every *is it
          non-null* check ever written; this is the one that refuses it.
    """
    body = _rows(_ledger(brazos))
    opening = _row_for(body, "Opening balance")
    assert opening, "the opening balance is in the window"
    assert all(one["documentNo"] is None for one in opening)
    assert all(one["documentType"] is None for one in opening)

    raw = json.dumps(body)
    for absent in (str(contract["invoice"].id), str(contract["payment"].id)):
        assert absent not in raw, (
            f"{absent} is our storage key and it left the building — P5.3 exists to "
            "stop exactly this, and a fallback to the source id passes every other "
            "check in this file"
        )


# ══════════════════════════════════════════════════════════════════════════
# P5.2 — THE TAX AUTHORITY
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_tax_row_names_its_authority_and_the_revenue_rows_do_not(
    contract, brazos
) -> None:
    """`P5.2`'s outcome: *the per-authority split survives the boundary.*

    ⚠ **THE SECOND HALF OF THE NAME IS THE HALF THAT BITES.** A transform that
    stamped the entry's authority onto every row it produced would pass a check
    that only looked at the tax row — and it would tell a partner that
    `$103.00` of electricity revenue was levied by Bexar County. The authority
    belongs to the LINE that gave the row its amount, which is the same line
    `accountString` comes from.
    """
    body = _rows(_ledger(brazos))
    rows = _row_for(body, INVOICE_NO)
    tax = [one for one in rows if Decimal(one["amount"]) == Decimal("2.30")]
    revenue = [one for one in rows if Decimal(one["amount"]) == Decimal("103.00")]
    assert tax and revenue, [one["amount"] for one in rows]

    assert tax[0]["taxAuthority"] == {
        "name": AUTHORITY_NAME,
        "authority": "Bexar County Tax Office",
        "level": "county",
        "referenceNo": "BEX-114-9",
    }, tax[0]["taxAuthority"]
    assert revenue[0]["taxAuthority"] is None, (
        "a revenue line has no tax authority, and saying it has one is worse than "
        "saying nothing — a partner splitting a remittance would send the county "
        "money it is not owed"
    )


@pytest.mark.django_db
def test_the_authority_travels_as_its_name_and_never_as_our_key(
    contract, brazos
) -> None:
    """B14 rule 31 in its WIRE form. The rule's own words are about a screen;
    `seams/billing.as_record` states the wire half for this whole surface —
    *"a partner keyed on our uuid is coupled to our storage forever"*.

    A tax office is known by who it is, what level it sits at and the reference
    a utility files under. Our primary key is none of those and a partner has
    every reason not to store it.
    """
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        authority_id = str(rating_models.TaxJurisdiction.objects.get(name=AUTHORITY_NAME).id)
    raw = json.dumps(_rows(_ledger(brazos)))
    assert authority_id not in raw, authority_id


# ══════════════════════════════════════════════════════════════════════════
# P5.5 — THE FEED RECONCILES
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_total_records_is_the_rows_and_total_entries_is_the_paged_unit(
    contract, brazos
) -> None:
    """`P5.5`, first half. **Two totals because two things are being counted**,
    and a partner needs both: `total_records` is what its job will receive and
    can add up, `total_entries` is what `total_pages` is derived FROM.

    Conflating them is not cosmetic — with three entries producing four rows,
    a partner paging on `total_records` would ask for a page that does not
    exist and conclude rows are missing.
    """
    body = _rows(_ledger(brazos, page_size="100"))
    assert body["total_records"] == len(body["records"]), (
        body["total_records"],
        len(body["records"]),
    )
    with tenant_ctx(brazos):
        posted = led_models.JournalEntry.objects.filter(
            status=led_models.JE_POSTED, entry_date=BOOK_DATE
        ).count()
    assert body["total_entries"] == posted, (body["total_entries"], posted)
    assert body["total_records"] != body["total_entries"], (
        "the fixture must hold at least one entry that becomes MORE THAN ONE row, "
        "or this case cannot tell the two totals apart at all"
    )


@pytest.mark.django_db
def test_a_walk_of_the_pages_receives_exactly_total_records_rows(
    contract, brazos
) -> None:
    """`P5.5`, second half — and it is a walk rather than a second sum, per (d).

    The walk pages at ONE ENTRY A PAGE until a page comes back short, counting
    what it actually received. Nothing here consults `total_pages` to decide
    how far to go, because a count that used the number it is checking would
    agree with itself whatever either of them said.
    """
    seen: list[dict] = []
    page = 1
    while True:
        body = _rows(_ledger(brazos, page="1" if page == 1 else str(page), page_size="1"))
        seen.extend(body["records"])
        if page >= body["total_pages"]:
            expected = body["total_records"]
            break
        page += 1
    assert len(seen) == expected, (len(seen), expected)
    assert len({one["transactionId"] for one in seen}) == len(seen), (
        "every row the walk received is distinct — a repeated transactionId means "
        "the paging returned one row twice, and the row it returned twice is a row "
        "it never returned at all"
    )


@pytest.mark.django_db
def test_no_page_boundary_ever_falls_inside_an_entry(contract, brazos) -> None:
    """`P5.5`'s outcome, in its own words: **a balanced pair is never split
    across a page.**

    ⚠ **THIS IS THE ONE THAT MATTERS AND IT IS WHY THE PAGE IS A PAGE OF
    ENTRIES.** Pairing a debit with its credit reads a WHOLE entry. Page on
    ROWS instead and a three-row bill straddling a boundary gives a partner two
    rows on one page and one on the next — which is not a rounding error, it is
    two half-postings, and a partner's month would be out by the difference
    with nothing on either side raising.

    It is asserted by GROUPING the rows of every page by the entry they came
    from and checking no entry appears on two pages. At `page_size=1` every
    boundary in the window is crossed, so a transform that paged on rows would
    be caught on the first bill rather than on a fixture that happened to fit.
    """
    pages: list[list[dict]] = []
    page = 1
    while True:
        body = _rows(_ledger(brazos, page=str(page), page_size="1"))
        pages.append(body["records"])
        if page >= body["total_pages"]:
            break
        page += 1

    #: `transactionId` is `<entry number>-<ordinal>`, so the entry is the part
    #: before the last dash. Every row of one entry must be on ONE page.
    def entry_of(row: dict) -> str:
        return (row["transactionId"] or "").rsplit("-", 1)[0]

    where: dict[str, set[int]] = {}
    for index, rows in enumerate(pages):
        for row in rows:
            where.setdefault(entry_of(row), set()).add(index)
    split = {key: sorted(value) for key, value in where.items() if len(value) > 1}
    assert not split, f"these entries were split across pages: {split}"

    assert len(pages) > 1, (
        "the window must produce more than one page or this case asserts nothing — "
        "a boundary that is never crossed cannot fall anywhere"
    )
    assert any(len(rows) > 1 for rows in pages), (
        "at least one page must hold several rows of ONE entry, which is what "
        "'the page is a page of entries' actually means"
    )


@pytest.mark.django_db
def test_the_balanced_pair_survives_the_whole_walk(contract, brazos) -> None:
    """CLAUDE.md hard rule 5, measured over the pages rather than over one
    entry. Σ debits and Σ credits across everything the walk received must
    equal each other and must equal what OUR books hold.

    ⚠ **THE PARTNER'S OWN TWO SIDES CANNOT PROVE THIS**, which
    `seams/ledger.as_record` says in as many words: a paired row carries ONE
    amount that is both its debit and its credit, so Σ debits = Σ credits
    across paired rows **by construction**. The comparison that bites is
    against our own debit total, and that is the one made here.
    """
    rows: list[dict] = []
    page = 1
    while True:
        body = _rows(_ledger(brazos, page=str(page), page_size="1"))
        rows.extend(body["records"])
        if page >= body["total_pages"]:
            break
        page += 1

    debits = sum(
        (Decimal(one["amount"]) for one in rows if one["debitAccount"] is not None),
        Decimal(0),
    )
    credits = sum(
        (Decimal(one["amount"]) for one in rows if one["creditAccount"] is not None),
        Decimal(0),
    )
    with tenant_ctx(brazos):
        ours = led_models.JournalLine.objects.filter(
            journal_entry__status=led_models.JE_POSTED,
            journal_entry__entry_date=BOOK_DATE,
            side=led_models.SIDE_DEBIT,
        ).values_list("amount", flat=True)
        our_debits = sum((Decimal(str(one)) for one in ours), Decimal(0))

    assert debits == credits, (debits, credits)
    assert debits == our_debits.quantize(Decimal("0.01")), (debits, our_debits)


# ══════════════════════════════════════════════════════════════════════════
# THE PAGE READS — a constant, not a cost paid per row
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_document_and_authority_reads_do_not_grow_with_the_page(
    contract, brazos, django_assert_num_queries
) -> None:
    """⚠ **THE THING THAT WOULD LOOK PERFECTLY FAST ON A DEMO TENANT.**

    `collectable`'s own docstring sets the scale: a month at the top of this
    product's ICP is around 200,000 journal lines. Resolving the document
    number and the tax authority inside `as_record` is a query PER ROW, and on
    167 entries that is invisible.

    ⚠ **THE ASSERTION IS ABOUT GROWTH, NOT ABOUT A MAGIC NUMBER — AND THE
    FIRST DRAFT OF THIS CASE GOT THAT WRONG.** It asserted `2` and the answer
    was `3`, because the cost is *one tax read plus one read per distinct
    SOURCE KIND on the page* — and a number pinned to whatever the fixture
    happens to hold would go red the day a fourth kind of entry is written,
    which is not a defect. What must never change is that **the count does not
    move when the page gets bigger**, so this measures the fixture's page,
    triples the bills on it, and measures again.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        entries = list(ledger_seam.collectable(since=date(2026, 7, 1), until=BOOK_DATE))
        assert len(entries) >= 3, len(entries)

        captured: list[int] = []
        with django_assert_num_queries(3) as small:
            ledger_seam.page_context(entries)
        captured.append(len(small.captured_queries))

        receivable = gl(brazos, "1200", "asset")
        usage = gl(brazos, "4100")
        account_id = entries[0].lines.all()[0].account_id
        for n in range(3):
            extra = billing_models.Invoice.objects.create(
                tenant=brazos,
                account_id=account_id,
                invoice_no=f"BL-2607-9000{n}",
                service_date=BOOK_DATE,
                period_start=date(2026, 7, 1),
                period_end=BOOK_DATE,
                total=Decimal("10.00"),
                currency="USD",
            )
            _post(
                [
                    _line(receivable, "debit", "10.00", account_id=account_id),
                    _line(usage, "credit", "10.00", account_id=account_id),
                ],
                key=f"invoice|p5-bulk-{n}|issued",
                memo=f"Bill BL-2607-9000{n} issued",
                source_type="invoice",
                source_id=extra.id,
            )

        bigger = list(ledger_seam.collectable(since=date(2026, 7, 1), until=BOOK_DATE))
        assert len(bigger) == len(entries) + 3, len(bigger)
        with django_assert_num_queries(3) as large:
            ledger_seam.page_context(bigger)
        captured.append(len(large.captured_queries))

    assert captured[0] == captured[1], (
        f"the page read cost {captured[0]} queries on {len(entries)} entries and "
        f"{captured[1]} on {len(entries) + 3} — that is a per-row resolution, which "
        "is the thing page_context exists to prevent"
    )


@pytest.mark.django_db
def test_as_record_still_works_with_no_context_at_all(contract, brazos) -> None:
    """One composer, two callers, no second answer — `seams/billing`'s posture.

    A lane calling `as_record(entry)` with no page behind it (a test, a
    one-off, a future single-entry address) gets the same row the paged caller
    does, because it builds a context for the one entry it was handed. A
    second, thinner code path is how two callers start being told two different
    things about one bill.
    """
    with tenant_ctx(brazos):
        entry = ledger_seam.collectable(
            since=date(2026, 7, 1), until=BOOK_DATE
        ).filter(memo__contains=INVOICE_NO).first()
        bare = ledger_seam.as_record(entry)
        paged = ledger_seam.as_record(entry, ledger_seam.page_context([entry]))
    assert bare == paged
    assert all(one["documentNo"] == INVOICE_NO for one in bare)


# ══════════════════════════════════════════════════════════════════════════
# P5.7 — THE SYNC CONTRACT, PINNED RATHER THAN CHOSEN (OQ-INT-6620)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_later_entry_is_not_in_an_earlier_window_and_that_is_the_open_question(
    contract, brazos
) -> None:
    """`P5.7`'s OPEN half, **measured and pinned — not answered.**

    ⚠ **THIS CASE DELIBERATELY ASSERTS THE CURRENT BEHAVIOUR AND NOT A
    PREFERRED ONE.** `OQ-INT-6620` puts three answers to the Product Owner and
    they have not ruled; CLAUDE.md's prime directive says a lane implements to
    the boundary and never resolves an open question by choosing a value. So
    what this pins is the FACT a partner would meet today, so that the day
    somebody changes the semantics it goes red and names the question rather
    than sliding past as an improvement.

    **The fact:** the window bounds on `entry_date`, the BOOK date. A
    correction is a NEW entry (`BR-LED-003`, hard rule 4 — nothing is edited)
    and it carries the book date of the period it is MADE in. So an October
    correction against a September bill is in October's window and in no other,
    and a partner that pulled September on 1 October holds the original figure
    with nothing to supersede it.

    ⚠ **THE OTHER HALF OF `P5.7` IS BUILT AND IS ASSERTED BY THE SUITE THAT
    OWNS IT** — `serve.scope_permits` refuses a key that does not name the
    operation, and refuses a BLANK scope outright, which is stricter than the
    blueprint drew it. `test_cr110_phase2_partner_reference.py` is where that
    lives; it is not re-asserted here.
    """
    from apps.ledger import models as led

    with tenant_ctx(brazos):
        cash = gl(brazos, "1010", "asset")
        receivable = gl(brazos, "1200", "asset")
        correction = uuid.uuid4()
        posting.post(
            posting.PostingRequest(
                posting_key="invoice|p5-correction|reversed",
                # ⚠ OCTOBER, against a September bill. This is the whole case.
                entry_date=date(2026, 10, 8),
                posted_at=datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc),
                currency="USD",
                lines=(
                    _line(cash, "debit", "2.30", source=("invoice", correction)),
                    _line(receivable, "credit", "2.30", source=("invoice", correction)),
                ),
                source_type="invoice",
                source_id=correction,
                memo="Correction to Bill BL-2607-000014",
            )
        )

    september = _rows(_ledger(brazos))
    assert not _row_for(september, "Correction to"), (
        "an October correction is NOT in September's window — which is correct for a "
        "GL period and is exactly what OQ-INT-6620 asks about: a partner who already "
        "pulled September will never ask again and will never be handed this row"
    )

    october = _rows(
        _ledger(brazos, start_date="2026-10-01", end_date="2026-10-31")
    )
    assert _row_for(october, "Correction to"), "it IS in October's window"

    # And the fact that makes answer (c) available at all: the column a
    # *what changed since* cursor would select on already exists and already
    # holds a different value from the book date.
    with tenant_ctx(brazos):
        entry = led.JournalEntry.objects.get(memo="Correction to Bill BL-2607-000014")
    assert entry.entry_date == date(2026, 10, 8)
    assert entry.posted_at.date() == date(2026, 10, 8)
