# ── Trace ──────────────────────────────────────────────
# Change:   CR-109 — the New Connect Charges step. PO 2026-09-16: "this step is
#           required", closing whether the money conversation could be dropped.
# Story:    US-BIL-012 (the one-time door) · task 6.10 (the build's commit)
#           Screens: New Connect step 6 · Charges
# Rules:    BR-BIL-020 (lines come ONLY from rules and charge codes; free-typed
#           amounts never exist on any bill) · BR-BIL-007 (the tenant's row
#           carries the figure) · BR-BIL-010 (a charge code carries its own GL)
#           · BR-MET-113 (charges are tagged to an account number) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7 · hard-won laws 7 and 14
# ───────────────────────────────────────────────────────
"""**What a build's quote WOULD post — written, and never yet observed.**

⚠ **THIS HEADER SAID *"No assertion here has ever passed"* UNTIL 2026-09-16 AND
IT IS NO LONGER TRUE — the sentence is replaced rather than left beside its
successor, which is this path's own lesson (hard-won law 1).** All ten cases
pass against real PostgreSQL, and the five things worth breaking were broken
first; the quoted failures are in the red-first section below. What had been
missing was never billing: it was the CALLER, reverted out of
`metering/connections.py` three minutes after it landed (`DEF-MET-5446`).

Until 2026-09-16 `commit_connection` recorded a build's quote total on the
`connections` row and posted it nowhere, saying so in a stated absence returned
on a perfectly successful commit (`quote_recorded_not_posted`). A utility could
build twenty-five units, quote thousands of dollars, press the button, and the
money reached **no book at all**.

**THE PAIRS ARE ASSERTED BY ACCOUNT CODE AND BY FIGURE** — that is how this
file is WRITTEN, which is the 🔒 sensitive-path requirement and the reason it
exists rather than a handful of state assertions — and break 2 below is why:
with all three lines forced onto one revenue account the tie-out passed at
`800 == 800` throughout, and only the per-account figures caught it.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE IS `_pg` AND MUST STAY SO — HARD-WON LAW 14
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. **SQLite has no aborted-transaction state**, so a posting path
that swallowed a database error and carried on would pass the entire suite,
green, on every machine, and lose the whole transaction the first time a real
row was refused in production. It also has no RLS and no freeze trigger, so
three of the guarantees asserted below cannot exist there at all.

Run it:

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL='postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub?sslmode=disable' \\
      JOBS_EAGER=false .venv/bin/python -m pytest tests/test_cr109_connection_quote_posts_pg.py -q

════════════════════════════════════════════════════════════════════════════
THE WORKED CASE, AND EVERY FIGURE IN IT COMES OUT OF THE PRODUCT
════════════════════════════════════════════════════════════════════════════
A developer's approved application quotes three coded lines. The tenant's own
charge-code catalogue carries the prices (`BR-BIL-007`) and the BUILD carries
the counts:

    CONN        Connection fee                per unit      6 x  $45.00 =  $270.00
    METER-TEST  Meter accuracy test           per meter    20 x  $25.00 =  $500.00
    INSPECT     Backflow inspection           per premise   1 x  $30.00 =   $30.00
                                                                 Quoted    $800.00

**THE REVENUE SPLITS BY CODE, WHICH IS THE WHOLE POINT OF LINES.** A single
lump would have credited one account; three coded lines credit the two accounts
their codes name (`BR-BIL-010`, `CR-066` table 1):

    DR 1200 Accounts receivable            800.0000
    CR 4600 Connection & new-service fees              270.0000   (CONN)
    CR 4630 Field-service & meter fees                 530.0000   (METER-TEST + INSPECT)

Debits equal credits, and the $530.00 is two lines that share an account being
posted as ONE credit rather than two — a journal entry says where money went,
not how many lines agreed about it.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST, AND EVERY FAILURE BELOW IS QUOTED FROM A RUN
════════════════════════════════════════════════════════════════════════════
⚠ **THIS SECTION ONCE HELD FIVE FABRICATED PROOFS AND THE LANE THAT WROTE THEM
DELETED THEM ITSELF.** They were that author's PLAN for the red-first runs,
written into the file before the runs were made, under a heading claiming they
were quoted. **A fabricated proof is worse than a missing one**: a missing proof
invites the next lane to do the work, and a fabricated one tells them it is
already done. The five below replace them and each was produced by breaking the
thing named, in a private `git worktree`, and running `pytest` against real
PostgreSQL — the harness that runs them, never a gate file directly.

**1 · THE WHOLE POINT OF THE FILE: the caller absent.** Before
`_post_connection_quote` was restored (`DEF-MET-5446`), with everything else in
place:

    assert result["manifest"]["one_time_charges"] == str(QUOTE_TOTAL)
    AssertionError: assert '' == '800.0000'

The build committed, the quote was $800.00, and the manifest reported nothing —
because there was nothing to report.

**2 · THE REVENUE SPLIT COLLAPSED TO ONE ACCOUNT — AND THIS IS THE FALSE PASS
THIS FILE IS SHAPED AROUND.** `rating.gl_account_id_for_charge` broken to answer
with the first code's GL account for every code, so all three lines credit
`4630` and **the total does not move**:

    test_the_quote_posts_a_balanced_pair                 PASSED
    test_revenue_splits_by_charge_code_not_by_lump       FAILED
    AssertionError: assert {'4630': Decimal('800.000000')}
                        == {'4600': Decimal('270.0000'), '4630': Decimal('530.0000')}

**The balanced-pair test passed throughout, at 800 == 800, over books that had
lost where the money went.** `sum(debits) == sum(credits)` is blind to the
account: only naming the accounts and their figures catches it. This is the
one measurement in this file worth more than the feature.

**3 · THE PRICE-DRIFT GUARD RETURNING WITHOUT COMPARING.** With
`_refuse_quote_price_drift` short-circuited, the commit no longer refuses; it
carries a quote priced at $40.00 into billing and dies two modules away:

    apps.billing.exceptions.BillingRuleError: charge code 'CONN' is counted
    6.0000 times on a basis of None, which is not one this product counts in

— an error with no `charge_code`/`quoted`/`current` a clerk could act on, in
place of the refusal that names both figures.

**4 · THE INVOICE STAMP NEVER REACHING CUSTOMERS' LINES.** With the
`mark_request_quote_invoiced` call removed:

    AssertionError: a raised line names its invoice
    assert False

The second commit would raise the same quote again.

**5 · THE PAYER'S CLASS NEVER ASKED (`DEF-MET-5472`).** With the
`payer_is_billable` check removed, a build whose payer is a pending-activation
account is destroyed by its own payer:

    apps.billing.gather.GatherProblem: account 'AC-2026-00001' is not in the
    billable set for its unit (BR-CUS-055).

— raised inside the one transaction that had already written the premises, the
units, the meters, the plan assignments and the work orders.

⚠ **WHAT WOULD MAKE EACH OF THESE PASS WRONGLY** (law 7's second habit — this
part was real analysis and is kept, because it shaped how the assertions are
written):

  * **The balanced-pair test is the easiest to fool.** `sum(debits) ==
    sum(credits)` is true of an EMPTY entry, and it was true of this path
    before the change — because there was no entry at all. So the test asserts
    the pair is **non-empty**, names **both account codes**, and asserts the
    **figure** on each side. A tie-out with no account codes in it proves only
    that zero equals zero.
  * **The absence test could pass on a build that posted nothing**, since a
    build with no request also does not report `quote_recorded_not_posted`. So
    it asserts the invoice EXISTS and carries the total, in the same case.
  * **The idempotency test could pass because the RUN's key refused the second
    attempt** rather than because the lines were stamped — the two guards look
    identical from outside. So it asserts `invoice_ref` is set on every line,
    which only the stamp can do.
"""

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.customers import service_request_service as sr
from tests import identity_fixtures
from apps.ledger import models as ledger_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors
from tests.fee_quote_helpers import price_charge_code  # DEF-CUS-6416
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, requires_postgres]


#: The quote, transcribed from this file's own docstring rather than read out of
#: the code under test. A test that imports its expectation from the thing it is
#: testing asserts that the code equals itself.
QUOTE = (
    # charge_code,  quantity, quoted unit price, basis
    ("CONN", Decimal("6"), Decimal("45.0000"), "per unit"),
    ("METER-TEST", Decimal("20"), Decimal("25.0000"), "per meter"),
    ("INSPECT", Decimal("1"), Decimal("30.0000"), "per premise"),
)
QUOTE_TOTAL = Decimal("800.0000")

#: `CR-066` table 1 as the PO approved it, transcribed from the CR.
REVENUE_BY_CODE = {"CONN": "4600", "METER-TEST": "4630", "INSPECT": "4630"}
AR_ACCOUNT = "1200"

#: The developer. One spelling, used by the application and by the account, so
#: that the account the charges are tagged to is demonstrably the same party the
#: quote was raised for.
OWNER_NAME = "Balcones Development LLC"


def _quoted_build(actor):
    """A build whose approved application carries the three-line quote above.

    Everything goes through the real services — no ORM shortcuts — because the
    thing under test is precisely whether these modules' doors line up.
    """
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"])

    # ⚠ **THIS PAYLOAD WAS REFUSED, AND IT IS WHY NOTHING IN THIS FILE HAD EVER
    # RUN (`DEF-BIL-5445`).** It read `"request_type": "new_service"` and
    # `"applicant": {"full_name": ...}`, and `_clean_capture` accepts NEITHER:
    # there is no `request_type` column at all, and the applicant is two FLAT
    # columns rather than a nested object. `create_request` raised
    # `VAL-005 (customers.serviceRequest.fieldNotAccepted)` naming `applicant`,
    # at `service_request_service.py:777`, so `_quoted_build` died in its first
    # statement and the balanced-pair assertion below was never evaluated —
    # which is a different thing from having been evaluated and failed, and is
    # the reason this file's docstring could say the pair "has never been
    # observed" while the product was in fact untested rather than broken.
    # The spellings below are `CAPTURE_FIELDS`' own.
    request = sr.create_request(
        actor,
        {
            "channel": "physical_form",
            "applicant_kind": "business",
            "applicant_name": OWNER_NAME,
            "address_as_given": "1408 Bluestem Ln, Katy TX",
        },
    )
    for code, qty, unit_amount, basis in QUOTE:
        sr.add_fee_line(
            actor,
            request.id,
            charge_code=code,
            unit_amount=unit_amount,
            quantity=qty,
            basis=basis,
        )

    created = w6.create_connection(
        actor,
        {"premises_id": premises["id"], "service_request_id": str(request.id)},
    )
    connection = work_tables.Connection.objects.get(pk=created["id"])

    from apps.customers import services as customers_services

    # ⚠ **THE SECOND HALF OF `DEF-BIL-5445`.** This call carried a `contact`
    # block and NO `customer` block, and `BR-CUS-1024` (PO 2026-09-01) refuses an
    # account whose customer identifies nobody:
    #   `BIZ-COMPLETENESS (customers.account.identity_kind_required)` at
    #   `services.py:2743`.
    # `tests/identity_fixtures.customer_block` is the ONE shape every fixture in
    # this suite uses for that block; hand-rolling a second one here is how the
    # two come to disagree.
    # ⚠ **THE THIRD HALF OF THE SAME FIXTURE FAULT, AND IT IS THE ONE THAT WAS
    # ABOUT THE PRODUCT (`DEF-MET-5472`).** This called `create_account` for an
    # ORDINARY account on a unit. An ordinary account opens
    # **pending activation**, which `BR-CUS-055` puts outside the billable class
    # set, so billing refused it — rightly — with
    # `GatherProblem: account 'AC-2026-00001' is not in the billable set for its
    # unit (BR-CUS-055)`, and that refusal rolled the whole build back.
    #
    # **The payer a build actually has is the owner's MASTER account**, which is
    # what step 4 of the wizard opens (`create_owner_account` → `create_master`,
    # ACTIVE by `BR-CUS-068`) and what `_quote_payer` reads off
    # `connections.owner_account`. `kind='master'`, `premises_id` set,
    # `unit_id` NULL — lawful under `ck_accounts_anchored` and, because
    # `ck_accounts_regular_has_unit` binds ordinary accounts to a unit, the ONLY
    # lawful shape for an address-anchored payer.
    #
    # The refusal the old fixture hit was real and is now a stated absence
    # rather than a lost build; `test_a_payer_that_cannot_be_billed_keeps_the_
    # build` below is the case that proves it, so this line is not deleting the
    # coverage, it is moving it to where it belongs.
    account = customers_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "contact": {"full_name": OWNER_NAME},
            "customer": identity_fixtures.customer_block(
                OWNER_NAME, account_type="commercial"
            ),
        },
    )
    w6.tag_charges_to_account(actor, connection.id, account["id"])
    connection.refresh_from_db()
    return connection, unit, account, request


def _commit(actor, connection, **extra):
    return w6.commit_connection(
        actor,
        connection.id,
        {
            "units": [{"label": "Unit 1"}],
            # CR-029 D8(3), PO 2026-08-23 — the terms are CAPTURED, never
            # guessed. A bill with no cycle has nowhere else to take them from.
            "quote_due_days": 30,
            "quote_posting_date": "2026-09-20",
            **extra,
        },
    )


def _entry_for(invoice):
    """The journal entry an issued invoice posted, or None."""
    return (
        ledger_models.JournalEntry.objects.filter(source_type="invoice", source_id=str(invoice.pk))
        .order_by("created_at")
        .first()
    )


def test_the_quote_posts_a_balanced_pair(brazos, dana):
    """**The money reaches a book, debits equal credits, and both sides are named.**

    `sum(debits) == sum(credits)` on its own is true of an empty entry and was
    true of this path before the change, because there was no entry. So the
    entry must EXIST, carry `$800.00` on each side, and name `1200` against the
    two revenue accounts the codes resolve to.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = _commit(dana, connection)

        assert result["manifest"]["one_time_charges"] == str(QUOTE_TOTAL)
        invoice_no = result["manifest"]["one_time_charge_invoice_no"]
        assert invoice_no, "a posted quote names the invoice it raised"

        invoice = billing_models.Invoice.objects.get(invoice_no=invoice_no)
        assert invoice.total == QUOTE_TOTAL

        entry = _entry_for(invoice)
        assert entry is not None, "an issued quote posts a journal entry (hard rule 5)"

        lines = list(entry.lines.select_related("ledger_account").all())
        assert lines, "an entry with no lines ties out trivially and proves nothing"
        # ⚠ **`JournalLine` HAS `side` AND `amount`, NOT `debit`/`credit`, AND
        # ITS GL ACCOUNT IS `ledger_account`.** `line.account` EXISTS and is the
        # CUSTOMER account dimension, so `line.account.code` read a real
        # attribute of the wrong thing — a test that dies on `AttributeError`
        # and a test that fails on its subject are different facts.
        debits = sum(
            (line.amount for line in lines if line.side == "debit"), Decimal("0")
        )
        credits = sum(
            (line.amount for line in lines if line.side == "credit"), Decimal("0")
        )
        assert debits == credits == QUOTE_TOTAL

        debit_codes = {
            line.ledger_account.code for line in lines if line.side == "debit"
        }
        assert debit_codes == {AR_ACCOUNT}


def test_revenue_splits_by_charge_code_not_by_lump(brazos, dana):
    """**Three coded lines credit the accounts their CODES name (`BR-BIL-010`).**

    This is what lines buy that a single total cannot. `$530.00` is two lines
    sharing one account posted as ONE credit — a journal entry says where money
    went, not how many lines agreed about it.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = _commit(dana, connection)
        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )

        expected: dict[str, Decimal] = {}
        for code, qty, unit_amount, _basis in QUOTE:
            account_code = REVENUE_BY_CODE[code]
            expected[account_code] = expected.get(account_code, Decimal("0")) + qty * unit_amount

        # `side`/`amount`/`ledger_account` — see the note in the balanced-pair
        # test above; `line.account` is the customer-account dimension.
        credited = {
            line.ledger_account.code: line.amount
            for line in _entry_for(invoice).lines.select_related("ledger_account").all()
            if line.side == "credit"
        }
        assert credited == expected
        assert sum(credited.values()) == QUOTE_TOTAL


def test_the_invoice_shows_its_arithmetic(brazos, dana):
    """**Every line carries its COUNT and its UNIT PRICE, so a customer can check it.**

    `6 x $45.00 = $270.00` on the document rather than a total nobody can
    verify. The blueprint draws QTY and UNIT as their own columns, and
    `RatedLine` has carried both fields all along.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = _commit(dana, connection)
        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )

        by_amount = {line.amount: line for line in invoice.lines.all()}
        for _code, qty, unit_amount, _basis in QUOTE:
            line = by_amount[qty * unit_amount]
            assert line.quantity == qty
            assert line.unit_price == unit_amount
            # Rounded ONCE, at four decimals (hard rule 2). Display rounds to
            # two and nothing in the money path does.
            assert line.amount == (unit_amount * qty).quantize(Decimal("0.0001"))


def test_the_stated_absence_is_gone_when_it_stops_being_true(brazos, dana):
    """**Hard-won law 1: an absence that outlives its cause is a lie.**

    `quote_recorded_not_posted` said the quote was *"recorded on the connection
    and posted by nothing"*. It must not survive the commit that posts it — and
    the invoice must exist in the SAME case, or this test would pass on a build
    that simply posted nothing.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = _commit(dana, connection)

        codes = {row["code"] for row in result["unavailable"]}
        assert "quote_recorded_not_posted" not in codes
        assert result["manifest"]["one_time_charge_invoice_no"]
        assert billing_models.Invoice.objects.filter(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        ).exists()


def test_a_second_commit_cannot_raise_the_same_quote_twice(brazos, dana):
    """**Every raised line is stamped `invoice_ref`, so no debt is charged twice.**

    Asserted on the STAMP rather than on an invoice count, because the run's
    idempotency key would refuse a same-day replay anyway and the two guards
    look identical from outside — a count would be measuring the wrong one.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, request = _quoted_build(dana)
        _commit(dana, connection)

        stamped = customers_models.ServiceRequestFee.objects.filter(request_id=request.id)
        assert stamped.count() == len(QUOTE)
        assert all(fee.invoice_ref for fee in stamped), "a raised line names its invoice"
        # Raising is not settling: the developer OWES this money.
        assert not any(fee.settled_at for fee in stamped)
        assert sr.quote_lines_for_request(request.id) == []


def test_a_moved_catalogue_price_refuses_rather_than_choosing(brazos, dana):
    """**`OQ-BIL-12376` — neither figure is taken silently.**

    The quote's stored `unit_amount` is a free-typed amount
    (`add_fee_line` takes it as an argument), so `BR-BIL-020` forbids billing
    it. Billing a DIFFERENT figure from the one the customer was shown is its
    own defect. So the commit refuses, naming the code and both figures.

    ⚠ Since `DEF-CUS-6416` (2026-09-23) the stored `unit_amount` is the
    catalogue's price AT THE ADD rather than a typed one; it is still a
    snapshot, so a catalogue that moves afterwards still disagrees with it, and
    this refusal is still the answer.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        request = sr.create_request(
            dana,
            {
                # `DEF-BIL-5445`'s payload again — `request_type` is not a column
                # and the applicant is two FLAT fields, so this refused with
                # `VAL-005 (customers.serviceRequest.fieldNotAccepted)` and the
                # test died in its fixture. The first occurrence was corrected
                # and these two were not, which is why the file still had reds
                # that said nothing about the product. `CAPTURE_FIELDS`' spellings.
                "channel": "walk_in",
                "applicant_kind": "business",
                "applicant_name": OWNER_NAME,
                "address_as_given": "1408 Bluestem Ln, Katy TX",
            },
        )
        # Quoted at $40.00 while the catalogue says $45.00 — a $30.00 difference
        # across six units, on a bill that would foot either way.
        # ⚠ `DEF-CUS-6416` (2026-09-23): the fee door now prices a line from the
        # catalogue AT THE ADD and refuses a different figure, so a $40.00 quote
        # against a $45.00 catalogue can no longer be typed in. The one way the
        # two come to disagree is the way this test's name says — the catalogue
        # MOVES after the quote — so the price is $40.00 when the line is added
        # and $45.00 again before the commit.
        price_charge_code("CONN", Decimal("40.0000"))
        sr.add_fee_line(
            dana, request.id, charge_code="CONN", unit_amount=Decimal("40.0000"), quantity=Decimal("6")
        )
        price_charge_code("CONN", Decimal("45.0000"))
        created = w6.create_connection(
            dana, {"premises_id": premises["id"], "service_request_id": str(request.id)}
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])

        from apps.customers import services as customers_services

        # The owner's MASTER account, as `_quoted_build` explains at length:
        # an ordinary account opens pending activation and `BR-CUS-055` puts it
        # outside the billable set, so the payer check would report an absence
        # and this test would never reach the price comparison it exists for.
        # It also carried no `customer` block, which `BR-CUS-1024` refuses
        # (`BIZ-COMPLETENESS customers.account.identity_kind_required`).
        account = customers_services.create_master_account(
            dana,
            {
                "premises_id": premises["id"],
                "account_type": "commercial",
                "opened_at": "2026-08-01",
                "contact": {"full_name": OWNER_NAME},
                "customer": identity_fixtures.customer_block(
                    OWNER_NAME, account_type="commercial"
                ),
            },
        )
        w6.tag_charges_to_account(dana, connection.id, account["id"])
        connection.refresh_from_db()

        with pytest.raises(errors.BizError) as caught:
            _commit(dana, connection)
        assert caught.value.params["charge_code"] == "CONN"
        assert caught.value.params["quoted"] == "40.0000"
        assert caught.value.params["current"] == "45.0000"

        # BOTH OR NEITHER: the refusal rolled the whole build back, so no units
        # were left behind by a commit that raised no charge.
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT


def test_an_owner_with_no_account_says_the_true_reason(brazos, dana):
    """**The blueprint's printed reason is stale and must not be repeated.**

    p090 says the payer path refuses because *"an account must name a unit"*.
    That expired on 2026-09-01 — `accounts.unit_id` is nullable and
    `ck_accounts_anchored` allows a premises-only anchor, which is asserted
    against the LIVE schema below rather than trusted from prose.
    `DEF-MET-5081` already had to correct eight surfaces of that false sentence.
    """
    from django.db import connection as db

    with db.cursor() as cur:
        cur.execute(
            "select pg_get_constraintdef(oid) from pg_constraint "
            "where conname = 'ck_accounts_anchored'"
        )
        definition = cur.fetchone()[0]
    assert "premises_id IS NOT NULL" in definition, (
        "the blueprint's reason rests on an account needing a unit; the live "
        "constraint allows a premises-only anchor, so that reason is dead"
    )

    with tenant_ctx(brazos):
        premises = make_premises(dana)
        request = sr.create_request(
            dana,
            {
                # `DEF-BIL-5445`'s payload again — `request_type` is not a column
                # and the applicant is two FLAT fields, so this refused with
                # `VAL-005 (customers.serviceRequest.fieldNotAccepted)` and the
                # test died in its fixture. The first occurrence was corrected
                # and these two were not, which is why the file still had reds
                # that said nothing about the product. `CAPTURE_FIELDS`' spellings.
                "channel": "walk_in",
                "applicant_kind": "business",
                "applicant_name": OWNER_NAME,
                "address_as_given": "1408 Bluestem Ln, Katy TX",
            },
        )
        sr.add_fee_line(
            dana, request.id, charge_code="CONN", unit_amount=Decimal("45.0000"), quantity=Decimal("6")
        )
        created = w6.create_connection(
            dana, {"premises_id": premises["id"], "service_request_id": str(request.id)}
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])

        result = _commit(dana, connection)
        rows = [
            row
            for row in result["unavailable"]
            if row["code"] == "quote_payer_owner_has_no_account"
        ]
        assert len(rows) == 1
        assert "BR-CUS-1024" in rows[0]["tracks"]
        assert "must name a unit" in rows[0]["detail"], (
            "the row names the stale reason in order to contradict it"
        )


def test_each_units_first_bill_is_refused_with_its_real_reason(brazos, dana):
    """**The drawn payer the product cannot honour says so, and says why.**

    Not built, and each reason is real: the unit accounts do not exist at
    commit, nothing carries a share of a quote forward to an account that opens
    later, and dividing `$800.00` across units is money arithmetic no signed
    document contains. A control the server would turn away is worse than an
    honest absence.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = _commit(dana, connection, quote_payer=w6.PAYER_EACH_UNIT_FIRST_BILL)

        rows = [
            row for row in result["unavailable"] if row["code"] == "quote_payer_per_unit_not_built"
        ]
        assert len(rows) == 1
        assert result["manifest"].get("one_time_charge_invoice_no") is None


def test_payment_terms_are_captured_and_never_guessed(brazos, dana):
    """**CR-029 D8(3), PO 2026-08-23 — and a guess would start a late-fee clock.**

    With no terms the build still commits (26 units must not be thrown away
    because nobody typed a number) and NOTHING is charged, which is stated.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account, _request = _quoted_build(dana)
        result = w6.commit_connection(
            dana, connection.id, {"units": [{"label": "Unit 1"}]}
        )
        codes = {row["code"] for row in result["unavailable"]}
        assert "quote_payment_terms_not_captured" in codes
        assert result["manifest"].get("one_time_charge_invoice_no") is None
        assert result["manifest"]["units"] == 1, "the build itself still committed"


def test_a_payer_that_cannot_be_billed_keeps_the_build(brazos, dana):
    """**`DEF-MET-5472` — a build is not thrown away by who the clerk named.**

    `BR-MET-113`'s `tag_charges_to_account` lets a clerk name ANY account as the
    payer, and `BR-CUS-055` puts a pending-activation or closed account outside
    the billable set. Billing refuses such an account by RAISING — correctly,
    for billing — and this call sits inside the ONE transaction that has already
    written the premises, the units, the meters, the plan assignments, the
    owner's account and the work orders. So the raise discarded a whole build
    over the payer.

    **The build is not wrong; only the charge cannot be raised yet**, which is
    the shape of every other absence on this path. The class is therefore asked
    through customers' own `billable_accounts()` BEFORE the door is called.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, and it is the reason for the last
    three assertions.** A build that posted nothing for some OTHER reason also
    reports no invoice — so *"no invoice"* alone proves nothing. This asserts
    the absence is THIS one by code, that the units were actually written, and
    that the connection left DRAFT. A commit that rolled back leaves the
    connection in `DRAFT` with no units, so those two together are what
    separate *"the charge was skipped"* from *"the build was lost"*.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        request = sr.create_request(
            dana,
            {
                "channel": "physical_form",
                "applicant_kind": "business",
                "applicant_name": OWNER_NAME,
                "address_as_given": "1408 Bluestem Ln, Katy TX",
            },
        )
        for code, qty, unit_amount, basis in QUOTE:
            sr.add_fee_line(
                dana,
                request.id,
                charge_code=code,
                unit_amount=unit_amount,
                quantity=qty,
                basis=basis,
            )
        created = w6.create_connection(
            dana, {"premises_id": premises["id"], "service_request_id": str(request.id)}
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])

        from apps.customers import services as customers_services

        # An ORDINARY account, which opens PENDING ACTIVATION — the exact shape
        # that used to take the build down with it.
        not_yet_billable = customers_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": "2026-08-01",
                "contact": {"full_name": OWNER_NAME},
                "customer": identity_fixtures.customer_block(
                    OWNER_NAME, account_type="residential"
                ),
            },
        )
        w6.tag_charges_to_account(dana, connection.id, not_yet_billable["id"])
        connection.refresh_from_db()

        result = _commit(dana, connection)

        rows = [
            row
            for row in result["unavailable"]
            if row["code"] == "quote_payer_account_not_billable"
        ]
        assert len(rows) == 1, "the reason is reported as ITSELF, not as a generic failure"
        assert result["manifest"].get("one_time_charge_invoice_no") is None

        # THE BUILD SURVIVED — which is the whole point, and the two assertions
        # a "no invoice" check cannot make on its own.
        assert result["manifest"]["units"] == 1
        connection.refresh_from_db()
        assert connection.state != work_tables.DRAFT
