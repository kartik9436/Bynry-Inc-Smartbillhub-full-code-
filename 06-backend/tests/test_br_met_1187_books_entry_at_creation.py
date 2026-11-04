# ── Trace ──────────────────────────────────────────────
# Change:   `CR-150-BRC09` task `B1` — PO ruling 2026-09-28, verbatim: *"we
#           create entries in books"* and, asked when, *"do it at creation once
#           submitted"*, over the sentence shown to them and accepted: *"It is
#           one act: if the books entry cannot be written, the connection is not
#           created either."* Decision log answer 18.
# Rules:    BR-MET-1187 (this ruling) · BR-MET-112 (nothing is written until the
#           last button; BOTH OR NEITHER) · BR-MET-1178 (a build prices itself;
#           the client sends a COUNT, never a figure) · BR-BIL-024 (payment
#           terms carry NO DEFAULT) · BR-PAY-1186 (a hand tender needs an open
#           till) · BR-PAY-010 (an overpayment carries as credit, never
#           dropped) · CLAUDE.md hard rule 2 (money 4dp, priced on the server,
#           rounded once) · hard rule 4 (no UPDATE/DELETE on an issued invoice
#           or a payment) · hard rule 5 (balanced pairs, ledger service only) ·
#           hard rule 6 (idempotency) · hard rule 7 (audit) · hard-won law 14
# Defect:   DEF-MET-7641 — the behaviour this file replaces
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**THE BOOKS ENTRY IS PART OF THE ACT — so it goes in, or nothing does.**

WHAT THE CODE DID BEFORE A LINE CHANGED, MEASURED RATHER THAN RECALLED
-----------------------------------------------------------------------
`commit_connection`'s quote block ended:

    else:
        client_total = data.get("quote_total")
        if client_total is not None:
            connection.quote_total = Decimal(str(client_total))
            connection.save(update_fields=["quote_total", "updated_at"])
        made["one_time_charges"] = str(connection.quote_total or "")
        absences.append(quote["absence"])

So a build whose charges could not be posted was **created anyway**, with the
money remembered as a figure **the client sent** and
`one_time_charge_invoice_no` NULL. Nothing reached Billing, nothing reached
Finance, nobody was ever asked for it. On a build the size of the drawn example
that is `$1,035.00` that exists on one screen and in no ledger (`DEF-MET-7641`).

⚠ **AND NO TEST ASSERTED THAT A COMMITTED BUILD HAS AN INVOICE.** Both cases
covering this path asserted the ABSENCE — `test_w6_connections.py:1831` and
`test_po20260921_a_build_prices_itself.py:303` — so the suite DEFENDED the
commit-anyway behaviour and went green over a build with no receivable. That is
this file's reason for existing, and it is the escape reason on the defect row.

WHY THIS FILE IS POSTGRESQL-ONLY, AND IT IS HARD-WON LAW 14
------------------------------------------------------------
Half of what is under test is a ROLLBACK. `config/settings/test.py` hardcodes
in-memory SQLite, which has no aborted-transaction state and no row-level
security, so *"the whole act rolls back"* and *"tenant B cannot see it"* are
both unprovable there. Run it against a real server::

    cd 06-backend
    DATABASE_URL=postgres://... JOBS_EAGER=false \\
      python -m pytest tests/test_br_met_1187_books_entry_at_creation.py -q \\
      --ds=config.settings.pgtest --reuse-db

⚠ **A SKIP IS NOT A PASS.** `requires_postgres` skips the whole module off
PostgreSQL, and law 7 already records what that costs: `G5` ran the isolation
suite on SQLite and *"called 192 skips a pass"*. Read the count.

WHAT WOULD MAKE THESE PASS WRONGLY — law 7's second habit, per case
--------------------------------------------------------------------
* **A rollback case passes trivially if the build never got far.** So every
  rollback case first asserts the SAME payload with terms present commits and
  writes N units, and only then asserts that the failing payload leaves ZERO —
  a count of zero over work that was never attempted proves nothing.
* **"One invoice on a double press" passes on a path that raises no invoice at
  all.** So it asserts ONE, by number, and that the number is the same one both
  times.
* **An audit assertion passes on a table that was already full.** So every
  audit count is a DELTA around the act, never a total.
* **A tenant-isolation case passes when the second tenant simply has no data.**
  So it asserts the first tenant CAN see its own invoice in the same breath.
* **The payment case could pass on money allocated to some other bill.** So it
  asserts the allocation lands on THIS invoice, by amount, through payments'
  own read.
"""

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import seams as metering_seams
from apps.payments import models as payment_models
from core import errors
from tests import identity_fixtures
from tests.isolation_helpers import (  # noqa: F401
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, requires_postgres]

OWNER_NAME = "Balcones Development LLC"

#: The build's own charge lines — a code the clerk picked from the tenant's
#: catalogue and a count step 3 took. **Transcribed rather than imported from
#: the code under test**, which would assert that the code equals itself. The
#: prices are the seeded catalogue's and the basis strings are billing's own
#: spellings (`fee_bill.BASIS_UNITS`, with spaces).
BUILD_LINES = (
    ("CONN", Decimal("6"), Decimal("45.0000"), "per unit"),
    ("METER-TEST", Decimal("20"), Decimal("25.0000"), "per meter"),
    ("INSPECT", Decimal("1"), Decimal("30.0000"), "per premise"),
)
#: 6 × 45 + 20 × 25 + 1 × 30. Worked here so a reader can check the arithmetic
#: without opening the catalogue, and asserted as a figure so a catalogue that
#: moves goes RED rather than quietly agreeing with itself.
BUILD_TOTAL = Decimal("800.0000")
POSTING_DATE = "2026-09-21"
DUE_DAYS = 30
#: 2026-09-21 + 30 days. `BR-BIL-024`: the due date is the posting date plus the
#: terms the clerk TYPED, and there is no default.
DUE_DATE = "2026-10-21"


def _payload_lines():
    return [
        {"charge_code": code, "quantity": str(qty), "basis": basis}
        for code, qty, _price, basis in BUILD_LINES
    ]


def _build_with_an_owner_account(actor):
    """A build a developer started, with the payer step 4 opens already on it.

    Everything goes through the real services — no ORM shortcuts — because what
    is under test is whether five modules' doors line up in one act.
    """
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    account = customers_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "contact": {"full_name": OWNER_NAME},
            "customer": identity_fixtures.customer_block(OWNER_NAME, account_type="commercial"),
        },
    )
    w6.tag_charges_to_account(actor, connection.id, account["id"])
    connection.refresh_from_db()
    return connection, unit, account


def _commit(actor, connection, **extra):
    payload = {
        "units": [{"label": "Unit 1"}],
        "quote_due_days": DUE_DAYS,
        "quote_posting_date": POSTING_DATE,
        "quote_lines": _payload_lines(),
    }
    payload.update(extra)
    return w6.commit_connection(actor, connection.id, payload)


def _units_at(premises_id):
    return metering_models.Unit.objects.filter(premises_id=premises_id).count()


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE INVOICE — the assertion nobody had written
# ═══════════════════════════════════════════════════════════════════════════
def test_a_build_with_charges_gets_an_invoice_with_its_lines_on_the_owners_account(brazos, dana):
    """`BR-MET-1187`: pressing *Create connection* writes **an invoice on the
    owner's account for the one-time charges**, in the same act.

    ⚠ **THE LINES AND THE ACCOUNT ARE ASSERTED, NOT JUST THE TOTAL.** A total
    can be right while the bill names the wrong payer or collapses three coded
    lines into one — and the Charges tab draws a row per charge.
    """
    with tenant_ctx(brazos):
        connection, _unit, account = _build_with_an_owner_account(dana)
        result = _commit(dana, connection)

        invoice_no = result["manifest"]["one_time_charge_invoice_no"]
        assert invoice_no, "a committed build with charges names the invoice it raised"
        invoice = billing_models.Invoice.objects.get(invoice_no=invoice_no)

        assert invoice.total == BUILD_TOTAL
        assert str(invoice.account_id) == str(account["id"]), "billed to the OWNER's account"
        assert result["manifest"]["one_time_charges"] == str(BUILD_TOTAL)

        # One line per charge, each priced by BILLING from the tenant's own row
        # (`BR-BIL-007`/`BR-BIL-020`): the payload carried no amount anywhere.
        #
        # ⚠ **KEYED ON `line.charge.code`, THE FK, NOT ON THE DESCRIPTION.**
        # `charge_code_line` sets `charge_id` deliberately — `DEF-714`, because
        # `issue._gl_account_for` refuses a line without it and the bill dies
        # at release — so the FK is the assertion that says WHICH code was
        # billed. A description is free text and would pass on a line pointing
        # at the wrong charge.
        lines = {line.charge.code: line for line in invoice.lines.select_related("charge")}
        assert set(lines) == {code for code, _q, _p, _b in BUILD_LINES}
        for code, qty, price, _basis in BUILD_LINES:
            assert lines[code].quantity == qty
            assert lines[code].amount == qty * price

        # The bill is findable FROM the build — a build's own lines leave no
        # `service_request_fees` row, so this column is the only durable link
        # and it is what the detail page's Charges tab reads.
        connection.refresh_from_db()
        assert str(connection.quote_invoice_id) == str(invoice.pk)
        assert connection.quote_total == BUILD_TOTAL


def test_the_due_date_is_the_posting_date_plus_the_terms_the_clerk_typed(brazos, dana):
    """`BR-BIL-024`, PO ruling 2026-08-23. 2026-09-21 + 30 days = 2026-10-21."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        result = _commit(dana, connection)
        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )
        # `service_date` is what `raise_quote_bill` sets from `on_date` — *"a
        # quote is charged ON a day, not OVER a window"* — and it is the
        # posting date the clerk typed on step 4. `issued_at` is the INSTANT
        # the document was released and is a different fact.
        assert str(invoice.service_date) == POSTING_DATE
        assert str(invoice.due_date) == DUE_DATE


def test_absent_payment_terms_refuse_the_build_rather_than_guessing_a_due_date(brazos, dana):
    """`BR-BIL-024` + `BR-MET-1187`. **A guessed due date starts a late-fee
    clock on a real customer**, and a build with charges nobody can date is a
    books entry that cannot be written — so the connection is not created.

    ⚠ **THE CONTROL CASE IS THE POINT.** The same payload WITH terms is asserted
    to commit and to write its unit first, so the zero below is a rollback and
    not a build that never started (law 7, habit 2).
    """
    with tenant_ctx(brazos):
        works, _unit, _account = _build_with_an_owner_account(dana)
        _commit(dana, works)
        assert _units_at(works.premises_id) == 2, "control: the same payload does commit"

        connection, _unit, _account = _build_with_an_owner_account(dana)
        before = _units_at(connection.premises_id)
        with pytest.raises(errors.BizError) as caught:
            _commit(dana, connection, quote_due_days=None)

        assert caught.value.br_ref == "BR-MET-1187"
        assert caught.value.message_key == "metering.connection_books_entry_required"
        assert caught.value.params["reason"] == "quote_payment_terms_not_captured"
        # ⚠ **THE REFUSAL NAMES THE STEP THAT OWNS THE FIELD**, so the wizard
        # opens it instead of leaving the clerk to hunt. `DEF-MET-6110` is the
        # row that made that the house habit on this path; a refusal with no
        # step is a sentence with nowhere to act on it.
        assert caught.value.params["step"] == w6.STEP_OF_THE_CHARGES

        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT, "a refused commit leaves the draft a draft"
        assert connection.quote_invoice_id is None
        assert connection.quote_total is None
        assert _units_at(connection.premises_id) == before, "the units rolled back"


def test_when_the_books_entry_fails_no_unit_no_invoice_and_no_payment_survive(brazos, dana):
    """**BOTH OR NEITHER, end to end and on real PostgreSQL** (`BR-MET-112`).

    The failing act here carries a payment as well, so the case proves the whole
    transaction unwinds rather than the units alone: no unit, no invoice, no
    payment, and the draft still a draft.
    """
    with tenant_ctx(brazos):
        connection, _unit, account = _build_with_an_owner_account(dana)
        invoices_before = billing_models.Invoice.objects.count()
        payments_before = payment_models.Payment.objects.count()
        units_before = _units_at(connection.premises_id)

        with pytest.raises(errors.BizError):
            _commit(
                dana,
                connection,
                quote_due_days=None,
                payment_method="card",
                payment_amount="800.0000",
            )

        assert billing_models.Invoice.objects.count() == invoices_before
        assert payment_models.Payment.objects.count() == payments_before
        assert _units_at(connection.premises_id) == units_before
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT


def test_a_build_that_names_no_charge_still_commits_and_records_no_figure(brazos, dana):
    """⚠ **THE BOUNDARY IS PART OF THE RULING.** `BR-MET-1187`: *"A BUILD THAT
    NAMES NO CHARGE HAS NOTHING TO WRITE AND IS UNAFFECTED — the rule bites
    where there IS an entry to write and it fails."* Read without that clause,
    *"the connection is not created"* would refuse every build that raises no
    fee, and a build with no one-time charge on it is lawful (`BR-MET-1178`).

    ⚠ **AND THE CLIENT'S FIGURE IS NOT RECORDED EVEN HERE.** This is the exact
    line `DEF-MET-7641` was filed for: the commit used to store
    `data["quote_total"]` on this path, which is a figure multiplied up off the
    server (hard rule 2) sitting on a build with no invoice behind it.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        result = _commit(dana, connection, quote_lines=[], quote_total="14435.0000")

        codes = {row["code"] for row in result["unavailable"]}
        assert "build_names_no_charge" in codes
        assert result["manifest"]["one_time_charge_invoice_no"] is None
        # `None`, not `""` and not `"0"`: a zero reads as *"this build was
        # free"* and an empty string is a figure-shaped hole.
        assert result["manifest"]["one_time_charges"] is None

        connection.refresh_from_db()
        assert connection.quote_total is None, "the client's $14,435.00 is written NOWHERE"
        assert connection.state != work_tables.DRAFT, "the build itself committed"


def test_a_total_the_bill_disagrees_with_refuses_and_is_never_posted(brazos, dana):
    """Hard rule 2: the client figure may REFUSE a commit and may never become
    one. A catalogue that moved between the preview and the press would
    otherwise bill a different figure from the one the clerk just read."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        with pytest.raises(errors.BizError) as caught:
            _commit(dana, connection, quote_total="999.0000")

        assert caught.value.message_key == "metering.connection_quote_total_moved"
        assert caught.value.params["shown"] == "999.0000"
        assert caught.value.params["raised"] == str(BUILD_TOTAL)
        connection.refresh_from_db()
        assert connection.quote_invoice_id is None
        assert connection.quote_total is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE PAYMENT — *"based on payment type we nedd to give all paymnet fields"*
# ═══════════════════════════════════════════════════════════════════════════
def test_a_payment_taken_is_recorded_against_that_invoice(brazos, dana):
    """`BR-MET-1187`: the payment is written **in the same act**, against the
    bill just raised.

    ⚠ **THE ALLOCATION IS ASSERTED THROUGH PAYMENTS' OWN READ**, not by the
    payment's existence: money recorded on the account and allocated to some
    other bill would leave this build outstanding while a receipt says
    otherwise. `allocated_for_invoices` is what the build record's *Taken* tile
    reads, so this asserts the figure the screen will show.
    """
    with tenant_ctx(brazos):
        connection, _unit, account = _build_with_an_owner_account(dana)
        result = _commit(
            dana,
            connection,
            payment_method="card",
            payment_amount="500.0000",
            payment_date=POSTING_DATE,
            # ⚠ **THE CLEARING DATE IS PART OF THE CASE AND NOT DECORATION.**
            # Without it `BR-PAY-021` makes the payment `processing` — the
            # money has not arrived — so it meets no bill and posts nothing.
            # A first draft of this case omitted it and the allocation map came
            # back EMPTY on real PostgreSQL, over a receipt the screen would
            # have shown. The sibling case below is that state, asserted.
            payment_cleared_date=POSTING_DATE,
            payment_reference="AUTH-19422",
        )

        payment_no = result["manifest"]["one_time_charge_payment_no"]
        assert payment_no, "a payment taken names its receipt"
        assert result["manifest"]["one_time_charge_paid"] == "500.0000"

        payment = payment_models.Payment.objects.get(payment_no=payment_no)
        assert payment.amount == Decimal("500.0000")
        assert str(payment.account_id) == str(account["id"])
        assert payment.confirmation == "AUTH-19422"

        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )
        # ⚠ **ASKED THROUGH THE SEAM THE SCREEN USES, NOT THROUGH PAYMENTS'
        # SELECTOR DIRECTLY.** `metering.seams.settled_against_bills` is what
        # `connection_record._money` calls for the build record's *Taken* tile,
        # and it normalises the map's keys to strings; a first draft called
        # payments' `allocated_for_invoices` and indexed it with a `UUID`,
        # which raised `KeyError` — a test asserting the right fact through a
        # reader no screen uses.
        allocated = metering_seams.settled_against_bills([invoice.pk])
        assert allocated is not None, "payments publishes no allocation read"
        assert allocated[str(invoice.pk)] == Decimal("500.0000"), "it met THIS bill"
        # And nothing on the commit says the money is still in the air.
        codes = {row["code"] for row in result["unavailable"]}
        assert "not_cleared_so_not_allocated" not in codes


def test_a_payment_with_no_clearing_date_is_PROCESSING_and_the_commit_says_so(brazos, dana):
    """`BR-PAY-021` / `US-LED-001`: **a payment with no clearing date has not
    arrived.** It meets no bill and posts no ledger pair, which is correct —
    a cheque handed over is not a cheque that cleared.

    ⚠ **WHAT MUST NOT HAPPEN IS SILENCE, AND THAT IS WHY THIS CASE EXISTS.**
    The build would otherwise commit with a receipt number on its manifest
    over an invoice still owing every cent, and nothing would say why. So the
    commit carries payments' OWN coded problem out to `unavailable[]`, and
    this asserts the code, the empty allocation and the receipt together —
    each alone is satisfiable by a path that simply did nothing.

    ⚠ **THE CLEARING DATE IS NEVER DEFAULTED TO THE POSTING DATE.** Doing so
    would take a bill out of arrears on money that has not arrived, and it is
    a rule nobody has given us: `BR-PAY-021` says the clerk states it, and the
    S22 Record-a-payment form asks for it exactly this way.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        result = _commit(
            dana,
            connection,
            # `ach` and not `check`: a cheque is a HAND tender and would be
            # refused here for want of an open till (`BR-PAY-1186`), which is
            # a different rule and would make this case prove that one
            # instead. A bank transfer initiated and not yet settled is the
            # plainest *processing* there is.
            payment_method="ach",
            payment_amount="500.0000",
            payment_date=POSTING_DATE,
            payment_reference="TRN-118420",
        )

        assert result["manifest"]["one_time_charge_payment_no"], "the receipt exists"
        codes = {row["code"] for row in result["unavailable"]}
        assert "not_cleared_so_not_allocated" in codes, (
            "a processing payment must SAY it met no bill; the codes were "
            f"{sorted(c for c in codes if c)}"
        )

        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )
        allocated = metering_seams.settled_against_bills([invoice.pk])
        assert allocated is not None
        # ABSENT from the map is payments' own way of saying *nothing has been
        # paid against it* — the seam's docstring, and a true answer over an
        # append-only table.
        assert str(invoice.pk) not in allocated


def test_a_build_with_no_payment_records_none_and_says_so(brazos, dana):
    """*No payment now* is the drawn default and it is not an edge case. The two
    manifest keys are `None` — never `0`, which reads as *"they paid nothing"*
    where the truth is *"nobody was asked to"*."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        before = payment_models.Payment.objects.count()
        result = _commit(dana, connection)

        assert result["manifest"]["one_time_charge_payment_no"] is None
        assert result["manifest"]["one_time_charge_paid"] is None
        assert payment_models.Payment.objects.count() == before


def test_an_amount_with_no_tender_is_refused_rather_than_banked_as_cash(brazos, dana):
    """`payments.method` is nullable, so this WOULD write — and the money would
    sit in the day's takings belonging to no drawer. It is `BR-BIL-024`'s shape
    on the other side of the receipt: a guessed tender is a real row on a real
    deposit."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        with pytest.raises(errors.ValidationError) as caught:
            _commit(dana, connection, payment_amount="500.0000")
        assert caught.value.message_key == "metering.connection_payment_method_required"
        assert caught.value.params["step"] == w6.STEP_OF_THE_CHARGES
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT


def test_a_tender_with_no_amount_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        with pytest.raises(errors.ValidationError) as caught:
            _commit(dana, connection, payment_method="card")
        assert caught.value.message_key == "metering.connection_payment_amount_required"


def test_a_tender_this_utility_does_not_run_answers_the_clerk_not_a_500(brazos, dana):
    """`DEF-MET-6110`'s shape, one module over.

    Payments refuses an unknown or DEACTIVATED method by RAISING
    `PaymentRuleError`, which is deliberately not a catalogue exception —
    `apps/billing/exceptions.py` gives the reason: a stage running over
    thousands of accounts is not answering a request. **The New Connect commit
    IS answering a request**, so a clerk who typed `cheque` where this utility
    spells it `check` would otherwise press *Create connection* after
    thirty-three acts and read *"Something went wrong on our side."*

    ⚠ **TWO ASSERTIONS AT TWO LAYERS, AND THE SPLIT IS THE POINT.** The
    SERVICE (`commit_connection`) lets payments' own class out unchanged — it
    swallows nothing — and the DOOR (`commit_new_connect`, and its twin for a
    raised draft) is where the translation belongs, exactly as the billing
    refusal is handled. A first draft asserted the translated refusal off the
    service and failed, correctly: the handler is not there and must not be.

    ⚠ **THE HANDLER IS OUTSIDE THE `atomic()` BLOCK** (law 14), so by the time
    it runs everything has rolled back — which both halves assert, because a
    refusal over a half-written build would be worse than the 500.

    ⚠ **THE CONTROL IS THE SPELLING.** `check` and `card` are asserted to work
    in the sibling cases; only the word changes here, so this is an assertion
    about the TENDER and not about payments being unreachable.
    """
    payment_refusal = metering_seams.payment_refusal_class()

    with tenant_ctx(brazos):
        # 1 · THE SERVICE — payments' own refusal, out unchanged.
        connection, _unit, _account = _build_with_an_owner_account(dana)
        units_before = _units_at(connection.premises_id)
        with pytest.raises(payment_refusal) as raw:
            _commit(dana, connection, payment_method="cheque", payment_amount="500.0000")
        assert "cheque" in str(raw.value)
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT
        assert connection.quote_invoice_id is None
        assert _units_at(connection.premises_id) == units_before

        # 2 · THE DOOR — the same press, translated onto the step that owns it.
        with pytest.raises(errors.BizError) as caught:
            w6.commit_new_connect(
                dana,
                {
                    "connection_id": str(connection.id),
                    "units": [{"label": "Unit 1"}],
                    "quote_due_days": DUE_DAYS,
                    "quote_posting_date": POSTING_DATE,
                    "quote_lines": _payload_lines(),
                    "payment_method": "cheque",
                    "payment_amount": "500.0000",
                },
            )
        assert caught.value.message_key == "metering.connection_payment_refused"
        assert caught.value.params["step"] == w6.STEP_OF_THE_CHARGES
        assert "cheque" in caught.value.params["detail"]
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT
        assert _units_at(connection.premises_id) == units_before


def test_a_payment_of_zero_is_refused(brazos, dana):
    """A receipt for `$0.00` states that money changed hands when none did."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        with pytest.raises(errors.ValidationError) as caught:
            _commit(dana, connection, payment_method="card", payment_amount="0")
        assert caught.value.message_key == "metering.connection_payment_amount_invalid"


def test_cash_with_no_till_open_is_refused_and_the_build_is_not_created(brazos, dana):
    """`BR-PAY-1186`, PO ruling 2026-09-23 §3.4: *"Refuse it. 'Start your
    counter first.' … It is the only option where every cash dollar belongs to
    somebody"*. The rule has ONE implementation, in `payments.counters`; this
    asserts New Connect is a CALL SITE of it and not a way around it.

    ⚠ **THE CARD CONTROL CASE IS BESIDE IT ON PURPOSE.** `card` is one of the
    four tenders that never reach a drawer, so it commits with no till — which
    is what makes the cash refusal an assertion about the TENDER rather than
    about payments being unreachable.
    """
    with tenant_ctx(brazos):
        card, _unit, _account = _build_with_an_owner_account(dana)
        _commit(dana, card, payment_method="card", payment_amount="500.0000")

        connection, _unit, _account = _build_with_an_owner_account(dana)
        with pytest.raises(errors.BizError) as caught:
            _commit(dana, connection, payment_method="cash", payment_amount="500.0000")
        assert caught.value.message_key == "payments.counter.till_required"
        connection.refresh_from_db()
        assert connection.state == work_tables.DRAFT
        assert connection.quote_invoice_id is None


# ═══════════════════════════════════════════════════════════════════════════
# 3 · IDEMPOTENCY — hard rule 6
# ═══════════════════════════════════════════════════════════════════════════
def test_pressing_create_twice_writes_one_invoice_and_one_payment(brazos, dana):
    """**Two guards, and this asserts both.**

    The first is structural: `commit_connection` refuses any connection that is
    not `DRAFT`, so a second press on one build never reaches the money at all.
    The second is `payments.webhook_key`, `UNIQUE (tenant_id, webhook_key)` —
    B2 §2 and DB-12's second row — composed from `entry` and
    `new-connect:<connection id>`, which covers the retry the state cannot:
    a request that wrote and lost its answer.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        first = _commit(dana, connection, payment_method="card", payment_amount="500.0000")

        with pytest.raises(errors.BizError) as caught:
            _commit(dana, connection, payment_method="card", payment_amount="500.0000")
        assert caught.value.br_ref == "BR-MET-112"
        assert caught.value.message_key == "metering.connection_already_committed"

        invoice_no = first["manifest"]["one_time_charge_invoice_no"]
        assert (
            billing_models.Invoice.objects.filter(account_id=connection.owner_account_id).count()
            == 1
        ), "one press, one bill"
        assert billing_models.Invoice.objects.filter(invoice_no=invoice_no).count() == 1
        assert (
            payment_models.Payment.objects.filter(account_id=connection.owner_account_id).count()
            == 1
        ), "one press, one payment"


def test_the_payment_key_is_the_connection_and_a_replay_writes_nothing(brazos, dana):
    """The KEY, asserted as a string, and the replay it exists for.

    ⚠ **A CLIENT TOKEN WOULD NOT DO THIS AND THAT IS THE WHOLE POINT** —
    payments' own idempotency docstring: a key the caller invents is *"different
    on the second submit and would dedupe nothing while looking like it did"*.
    The connection's id is stable across every retry of one build.

    The replay is driven through payments' own door rather than through a second
    commit, because the state guard would stop a second commit first — and a
    test that cannot reach the thing it names is law 7's *looking at the wrong
    thing*.
    """
    from apps.metering import seams as metering_seams

    with tenant_ctx(brazos):
        connection, _unit, account = _build_with_an_owner_account(dana)
        result = _commit(dana, connection, payment_method="card", payment_amount="500.0000")
        payment = payment_models.Payment.objects.get(
            payment_no=result["manifest"]["one_time_charge_payment_no"]
        )
        assert payment.webhook_key == f"entry|{w6.PAYMENT_KEY_PREFIX}{connection.id}"

        before = payment_models.Payment.objects.count()
        replay = metering_seams.payment_door()(
            dana,
            account_id=account["id"],
            amount=Decimal("500.0000"),
            posted_at=w6._moment_of(payment.posted_at.date()),
            method_code="card",
            idempotency_source=metering_seams.payment_entry_source(),
            idempotency_reference=f"{w6.PAYMENT_KEY_PREFIX}{connection.id}",
        )
        assert replay.created is False, "the same key finds the same row"
        assert str(replay.payment_id) == str(payment.pk)
        assert payment_models.Payment.objects.count() == before, "no second payment"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE AUDIT TRAIL — hard rule 7
# ═══════════════════════════════════════════════════════════════════════════
def test_every_money_action_in_the_act_writes_audit(brazos, dana, audit_rows):
    """Hard rule 7: **every money action writes `audit_log`.**

    ⚠ **READ THROUGH THE CAPTURE SINK, NOT OFF THE TABLE, AND THE FIRST DRAFT
    OF THIS CASE GOT IT WRONG — WHICH IS WHY IT SAYS SO.** `test_us_met_helpers`
    installs an AUTOUSE sink that appends every row to a list instead of
    inserting it, so `AuditLog.objects.filter(...)` is EMPTY in this whole
    family of tests. A first draft counted the table, read `0`, and would have
    been a check that can only ever fail — the mirror of law 7's *incapable of
    passing*. The rows are all here; they are just in the list.

    **Counted as a DELTA around the act**, never as a total: an assertion
    against a sink that already held rows passes on an empty write.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        before = len(audit_rows)
        result = _commit(dana, connection, payment_method="card", payment_amount="500.0000")

        written = audit_rows[before:]
        assert written, "the act wrote no audit row at all"
        actions = {row["action"] for row in written}
        assert "connection.committed" in actions, "the build says what it made"
        assert (
            "invoice.drafted" in actions
        ), f"the bill left no trail; actions were {sorted(actions)}"
        assert any(
            action.startswith("payment.") for action in actions
        ), f"the payment left no audit row; actions were {sorted(actions)}"
        assert result["manifest"]["one_time_charge_payment_no"]
        # Every captured row names the tenant it belongs to (BR-AUD-007: the
        # kernel refuses a write with no tenant context).
        assert {str(row["tenant_id"]) for row in written} == {str(brazos.id)}


# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT ISOLATION — hard rule 1, and only real PostgreSQL can show it
# ═══════════════════════════════════════════════════════════════════════════
def test_the_build_the_invoice_and_the_payment_are_all_rls_scoped(brazos, lonestar, dana, rls):
    """Hard rule 1, `RLS FORCE` — **asserted through the DATABASE, under a role
    the policy actually applies to.**

    ⚠⚠ **THE FIRST DRAFT OF THIS CASE COULD NOT HAVE FAILED, AND IT IS EXACTLY
    THE TRAP CLAUDE.md's LAW 7 NAMES.** It did the obvious thing — build in
    Brazos, then assert `Invoice.objects.filter(...)` finds nothing under
    `tenant_ctx(lonestar)` — and it FAILED on real PostgreSQL by finding the
    row. The reason is not a leak: **the app role this suite connects as is a
    SUPERUSER** (`select rolsuper from pg_roles where rolname='smartbillhub'`
    → `t`), and a superuser bypasses every row-level-security policy. So the
    ORM-only version proves nothing in either direction — it cannot pass
    honestly and it cannot fail informatively. `isolation_helpers` records the
    same measurement from 2026-09-05: *"as the superuser app role: 36 failed,
    201 passed"* against *"NOSUPERUSER NOBYPASSRLS: 19 failed, 96 passed"* —
    **"Neither run proves anything."**

    **So it uses the repo's own probe**, which runs the read as
    `sbh_rls_probe` (`NOLOGIN NOSUPERUSER NOBYPASSRLS`) on this test's own
    connection and **self-verifies**: `RlsProbe.assert_is_a_real_proof()` fails
    rather than skips if the role could bypass. `assert_rls_scoped` carries the
    positive half in the same call — it refuses to pass unless the OWNER can
    see at least one row of its own, so a second tenant simply having no data
    cannot satisfy it.

    Three tables, because the ruling writes to three modules in one act.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _build_with_an_owner_account(dana)
        result = _commit(dana, connection, payment_method="card", payment_amount="500.0000")
        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )
        payment = payment_models.Payment.objects.get(
            payment_no=result["manifest"]["one_time_charge_payment_no"]
        )

    assert_rls_scoped(
        rls, "connections", owner=brazos, intruder=lonestar, owner_ids={connection.pk}
    )
    assert_rls_scoped(rls, "invoices", owner=brazos, intruder=lonestar, owner_ids={invoice.pk})
    assert_rls_scoped(rls, "payments", owner=brazos, intruder=lonestar, owner_ids={payment.pk})


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-150-BRC09 task B1 (BR-MET-1187, decision log 2026-09-28 answer 18)
# generated: 2026-09-28 by the MONEY lane
# gates: ruff✔ black✔ · **PROVED RED FIRST, 16 of 16**, by restoring the
#        pre-fix `connections.py` and `seams.py` from the branch tip and
#        running this file against real PostgreSQL: four `DID NOT RAISE
#        BizError`, three `DID NOT RAISE ValidationError`, four
#        `KeyError: 'one_time_charge_payment_no'`, `assert '14435.0000' is
#        None`, `AssertionError: one press, one payment`, and two of this
#        lane's own first-draft faults. Then 17 of 17 green on the same server
#        (the seventeenth, the `processing` payment, was written after the
#        first green run found the fault it covers).
# exceptions: the whole module carries `requires_postgres`, so the DEFAULT
#        SQLite suite reports **17 skips and zero cases**. That is deliberate —
#        half of what is under test is a rollback and an RLS policy, neither of
#        which exists on SQLite (law 14) — and it is stated because a skip
#        reads as a pass: `G5` once called 192 of them one. The shape refusals
#        (an amount with no tender, a zero) would run anywhere and are here
#        rather than in a second file, so nothing in the ordinary suite
#        exercises them.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
