# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-21 — `BR-MET-1178`. Verbatim: *"we are keeping
#           application process and new connect process seperate - applciation
#           is submitted - reviewed and approved or rejected - once that is
#           doen application life is completed. then approve applciation may
#           create a new conenct request - as draft request - this request is
#           new work and recognized seperately from applcaition and hence we
#           should not make it dependent on applciation #"*.
# Rules:    BR-MET-1178 · BR-MET-112 (nothing written until the commit) ·
#           BR-MET-113 (every connection charge is tagged to an ACCOUNT) ·
#           BR-BIL-007 / BR-BIL-020 (the TENANT's row carries the price; a
#           free-typed amount never reaches a bill) · BR-BIL-024 (payment
#           terms) · CLAUDE.md hard rule 2 (money 4dp, rounded once, on the
#           server) · hard rule 5 (balanced pairs) · hard rule 7 (audit)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A BUILD A DEVELOPER STARTED RAISES ITS OWN CHARGES.**

WHAT WAS MEASURED BEFORE A LINE CHANGED
----------------------------------------
`_post_connection_quote` opened by asking *does this build have a service
request* and reported an absence when it did not:

    "This build has no service request, so there is no quote to raise. A quote
     arrives with an approved application; a build a developer starts without
     one is priced by nobody and charges nothing."

**And the wizard sent `service_request_id` EMPTY on every commit**, so that
branch was the only one a screen could reach. Measured in the demo tenant: **not
one of the nine connections carries a quote total, and not one has an owner
account.** The payer, the payment terms and the posting date step 6 collects
were read by nothing at all.

⚠ **THE SENTENCE ABOVE IS SUPERSEDED, DATED 2026-09-21, AND `BR-MET-1178` IS
WHAT REPLACES IT.**

WHY THIS FILE IS `_pg`, AND IT IS HARD-WON LAW 14
--------------------------------------------------
The path under test raises a real invoice and posts a balanced pair inside ONE
transaction. `config/settings/test.py` hardcodes in-memory SQLite, which has no
aborted-transaction state, so a failure shape that matters here would pass green
there. Run it against a real server::

    cd 06-backend
    set -a; . ./.env; set +a
    JOBS_EAGER=false .venv/bin/python -m pytest \\
        tests/test_po20260921_a_build_prices_itself.py -q \\
        --ds=config.settings.pgtest --reuse-db

WHAT WOULD MAKE THESE PASS WRONGLY — law 7's second habit
-----------------------------------------------------------
* **"It posted" is the easiest thing to fool.** A build that posts NOTHING also
  fails to report the old absence, so every positive case here asserts the
  INVOICE exists, carries a total, and names the accounts its money went to. A
  tie-out with no account codes in it proves only that zero equals zero.
* **The basis case could pass because the line was rejected for something
  else.** It asserts the refusal by its own `message_key`, and a sibling case
  proves the SAME payload posts once the basis is billing's own spelling — so
  the assertion is about the basis and not about the shape of the payload.
* **The "request still wins" case could pass on a build that priced nothing at
  all.** It asserts the REQUEST's total, which the build's own lines would not
  produce, and those lines are deliberately different figures.
"""

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import services as customers_services
from apps.customers import service_request_service as sr
from apps.ledger import models as ledger_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors
from tests import identity_fixtures
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, requires_postgres]

OWNER_NAME = "Balcones Development LLC"
AR_ACCOUNT = "1200"

#: **THE BUILD'S OWN LINES** — a charge code the clerk picked out of the
#: tenant's catalogue and a quantity step 4 counted. Transcribed here rather
#: than imported from the code under test, which would assert that the code
#: equals itself.
#:
#: ⚠ **THE BASIS IS SPELLED THE WAY BILLING SPELLS IT** — `fee_bill.BASIS_UNITS`
#: keys on `"per unit"` · `"per meter"` · `"per premise"`, with spaces.
BUILD_LINES = (
    ("CONN", Decimal("6"), Decimal("45.0000"), "per unit"),
    ("METER-TEST", Decimal("20"), Decimal("25.0000"), "per meter"),
    ("INSPECT", Decimal("1"), Decimal("30.0000"), "per premise"),
)
BUILD_TOTAL = Decimal("800.0000")
REVENUE_BY_CODE = {"CONN": "4600", "METER-TEST": "4630", "INSPECT": "4630"}


def _payload_lines():
    return [
        {"charge_code": code, "quantity": str(qty), "basis": basis}
        for code, qty, _price, basis in BUILD_LINES
    ]


def _unrequested_build(actor):
    """A build a developer started: **no service request anywhere on it.**

    Everything goes through the real services, because what is under test is
    whether these modules' doors line up on a build that has no application.
    """
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    assert connection.service_request_id is None, "the case is a build with NO application"

    # The payer a build has is the owner's MASTER account — `kind='master'`,
    # `premises_id` set, `unit_id` NULL — which is the only lawful shape for an
    # address-anchored payer (`ck_accounts_regular_has_unit`) and what step 4 of
    # the wizard opens. `BR-MET-113`: every connection charge is tagged to it.
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
    return w6.commit_connection(
        actor,
        connection.id,
        {
            "units": [{"label": "Unit 1"}],
            "quote_due_days": 30,
            "quote_posting_date": "2026-09-21",
            **extra,
        },
    )


def _entry_for(invoice):
    return (
        ledger_models.JournalEntry.objects.filter(source_type="invoice", source_id=str(invoice.pk))
        .order_by("created_at")
        .first()
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE RULING ITSELF
# ═══════════════════════════════════════════════════════════════════════════
def test_a_build_with_no_application_raises_its_own_charges(brazos, dana):
    """`BR-MET-1178`. **This is the case that could not happen before today.**"""
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        result = _commit(dana, connection, quote_lines=_payload_lines())

        assert result["manifest"]["one_time_charges"] == str(BUILD_TOTAL)
        invoice_no = result["manifest"]["one_time_charge_invoice_no"]
        assert invoice_no, "a posted quote names the invoice it raised"

        invoice = billing_models.Invoice.objects.get(invoice_no=invoice_no)
        assert invoice.total == BUILD_TOTAL

        # ⚠ **THE BILL IS FINDABLE FROM THE BUILD.** A build's own lines leave
        # no `service_request_fees` row, so `quote_invoice_id` is the only
        # durable link — and without it the record's OUTSTANDING tile would be
        # underivable for ever.
        connection.refresh_from_db()
        assert str(connection.quote_invoice_id) == str(invoice.pk)


def test_the_money_reaches_the_books_and_both_sides_are_named(brazos, dana):
    """Hard rule 5. `sum(debits) == sum(credits)` is true of an EMPTY entry, so
    the entry must exist, carry the figure on each side, and name the accounts."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        result = _commit(dana, connection, quote_lines=_payload_lines())
        invoice = billing_models.Invoice.objects.get(
            invoice_no=result["manifest"]["one_time_charge_invoice_no"]
        )

        entry = _entry_for(invoice)
        assert entry is not None, "an issued quote posts a journal entry"
        lines = list(entry.lines.select_related("ledger_account").all())
        assert lines, "an entry with no lines ties out trivially and proves nothing"

        debits = sum((l.amount for l in lines if l.side == "debit"), Decimal("0"))
        credits = sum((l.amount for l in lines if l.side == "credit"), Decimal("0"))
        assert debits == credits == BUILD_TOTAL
        assert {l.ledger_account.code for l in lines if l.side == "debit"} == {AR_ACCOUNT}

        expected: dict[str, Decimal] = {}
        for code, qty, price, _basis in BUILD_LINES:
            account = REVENUE_BY_CODE[code]
            expected[account] = expected.get(account, Decimal("0")) + qty * price
        credited = {
            l.ledger_account.code: l.amount for l in lines if l.side == "credit"
        }
        assert credited == expected


def test_no_figure_is_sent_and_the_server_prices_it(brazos, dana):
    """`CLAUDE.md` hard rule 2 and `BR-BIL-020`: **what crosses the wire is a
    COUNT.** The payload carries no amount anywhere, and the total still comes
    out right — which is only possible if billing read the tenant's own price."""
    with tenant_ctx(brazos):
        payload = _payload_lines()
        for line in payload:
            assert set(line) == {"charge_code", "quantity", "basis"}
            assert "amount" not in line and "unit_amount" not in line

        connection, _unit, _account = _unrequested_build(dana)
        result = _commit(dana, connection, quote_lines=payload)
        assert result["manifest"]["one_time_charges"] == str(BUILD_TOTAL)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHAT THE RULING DOES NOT CHANGE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_build_WITH_an_application_still_takes_the_applications_quote(brazos, dana):
    """**The ruling removes a REQUIREMENT, not a source.**

    ⚠ **THE TWO SETS OF FIGURES ARE DELIBERATELY DIFFERENT.** The request is
    quoted ONE line at `$120.00`; the build's own lines would come to `$800.00`.
    Asserting `$120.00` is therefore an assertion about WHICH source won, which
    a matching pair of totals could never make."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        make_unit(dana, premises["id"])
        request = sr.create_request(
            dana,
            {
                "channel": "physical_form",
                "applicant_kind": "business",
                "applicant_name": OWNER_NAME,
                "address_as_given": "1408 Bluestem Ln, Katy TX",
            },
        )
        sr.add_fee_line(
            dana,
            request.id,
            charge_code="INSPECT",
            unit_amount=Decimal("30.0000"),
            quantity=Decimal("4"),
            basis="per premise",
        )
        created = w6.create_connection(
            dana, {"premises_id": premises["id"], "service_request_id": str(request.id)}
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])
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

        result = _commit(dana, connection, quote_lines=_payload_lines())
        assert result["manifest"]["one_time_charges"] == "120.0000"


def test_a_build_that_names_no_charge_says_so_rather_than_counting_zero(brazos, dana):
    """A build is still LAWFUL with no charge on it, and the absence says what
    it is. **`$0.00` would read as 'this build was free'.**

    ⚠ **THE REASON IS AMENDED AND THE FIGURE IS NOT — `CR-150-BRC09` task `B2`,
    2026-09-28.** `BR-MET-1187` makes the books entry part of the act: *"if the
    books entry cannot be written, the connection is not created either."* So
    `one_time_charge_invoice_no` being empty is **no longer a general truth
    about a build that posted nothing** — on every other unposted path the
    commit now REFUSES and there is no manifest to read.

    **This case survives unchanged because it is the exemption the ruling
    states in its own words:** *"A BUILD THAT NAMES NO CHARGE HAS NOTHING TO
    WRITE AND IS UNAFFECTED — the rule bites where there IS an entry to write
    and it fails."* Nobody put a charge on this build, so nothing was owed to
    the books.

    ⛔ **DO NOT WIDEN THIS CASE.** Reading it as *"an unposted quote commits
    anyway"* is `DEF-MET-7641` coming back: `$1,035.00` on a `connections` row
    with no invoice behind it. The refusing paths are covered in
    `tests/test_br_met_1187_books_entry_at_creation.py`.
    """
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        result = _commit(dana, connection)
        # The commit's absences travel under `unavailable` — the same key the
        # `CR-109` suite reads; `absences` is the local variable's name inside
        # `commit_connection` and is not what crosses the wire.
        codes = {row["code"] for row in result["unavailable"]}
        assert "build_names_no_charge" in codes
        # ⚠ **AND THE OLD SENTENCE IS GONE RATHER THAN REWORDED.** A stated
        # absence that outlives its cause is a lie the product tells about
        # itself (hard-won law 1).
        assert "no_quote_on_this_build" not in codes
        assert not result["manifest"]["one_time_charge_invoice_no"]


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE SHAPE REFUSALS — SHAPE, NEVER PRICE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_basis_billing_does_not_count_in_is_refused_HERE_and_by_name(brazos, dana):
    """⚠ **THE REFUSAL THIS CASE EXISTS FOR WAS A REAL FIRST DRAFT.**

    `QUOTE_BASES` was written `per_unit` with underscores; `fee_bill.BASIS_UNITS`
    keys on `"per unit"` with a space. Billing refuses the mismatch two modules
    away with *"basis of 'per_unit', which is not one this product counts in"* —
    no charge code, nothing a clerk can act on, **after a build has been
    written**. Refusing it here, by name, is the whole difference."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        bad = [{"charge_code": "CONN", "quantity": "6", "basis": "per_unit"}]
        with pytest.raises(errors.ValidationError) as caught:
            _commit(dana, connection, quote_lines=bad)
        assert "basis_unknown" in str(caught.value)


def test_a_line_counted_zero_is_refused_rather_than_billed_as_free(brazos, dana):
    """A line counted zero prices `$0.00` and prints on a real customer's bill
    as a charge that was free — the reading the absences above refuse to
    publish. It is a line the clerk should not have added."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        with pytest.raises(errors.ValidationError):
            _commit(
                dana,
                connection,
                quote_lines=[{"charge_code": "CONN", "quantity": "0", "basis": "per unit"}],
            )


def test_a_line_with_no_charge_code_is_refused(brazos, dana):
    """`BR-BIL-020` — a line without a code is a free-typed amount wearing a
    line's clothes."""
    with tenant_ctx(brazos):
        connection, _unit, _account = _unrequested_build(dana)
        with pytest.raises(errors.ValidationError):
            _commit(
                dana, connection, quote_lines=[{"quantity": "6", "basis": "per unit"}]
            )
