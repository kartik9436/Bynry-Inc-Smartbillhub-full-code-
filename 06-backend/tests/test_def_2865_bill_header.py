# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2865 — every field in the issued bill's header printed as an
#          em-dash: Utility, Address, Contact, Service address, Cycle and Bill
#          date. Reported by the PO from bill BL-2608-000048.
# Rules:   BR-BIL-030 (the locked instance carries 'tenant identity and branding
#          reference' — the rule listed these as stamped and nothing stamped
#          them) · BR-BIL-070 (the run's own bill date) · BR-TEN-043 (event
#          time — every date on a document is a stored date, never a clock)
# Tests:   this file
# Impacts: apps/billing/issue.py · apps/billing/gather.py ·
#          apps/billing/tenancy_seam.py · apps/tenancy/selectors.py
# ───────────────────────────────────────────────────────
"""A bill nobody can attribute to a utility is not a bill.

⚠ **THE ABSENCES WERE ALL CORRECTLY RECORDED, AND THAT IS WHY THIS LASTED.**
`documents._masthead` and `_meta` name every one of these gaps with its rule and
its reason, and `test_us_bil_022_documents.py::…tc8` asserts they ARE named
absences — which reads as a design decision made and honoured. It is the only
test on them and it passes whether the gap is a week old or permanent.

So the machinery was right and the thing it was hiding is that the customer
cannot see who sent the bill, what it is for, or when it was raised.

**WHAT IS STAMPED AND WHERE, because the two moments are not interchangeable:**

  * the UTILITY's name, address and contact, the BILL DATE and the CYCLE are
    stamped **at issue**, beside BR-BIL-035's arrears and BR-BIL-021's message.
    A draft may sit for days and these are facts about the bill that was SENT.
  * the SERVICE ADDRESS is stamped **at gather**, beside the customer's name and
    for the identical reason (BR-BIL-030): it is master data about the account,
    and a premises re-addressed between the run and the release must not print
    over a period billed at the old address.
"""

import pytest

from apps.billing import documents

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill, pdf_text

pytestmark = pytest.mark.django_db

DASH = documents.ABSENT_MARK


def a_utility_with_a_profile(tenant):
    """The tenant fields US-TEN-005's company tab writes, filled in."""
    tenant.legal_name = "Brazos Bend Utilities District"
    tenant.dba_name = "Brazos Bend Utilities"
    tenant.mailing_address = "104 Old Ferry Road, Needville, TX 77461"
    tenant.support_phone = "(979) 555-0142"
    tenant.support_email = "billing@brazosbendutilities.test"
    tenant.save(
        update_fields=[
            "legal_name",
            "dba_name",
            "mailing_address",
            "support_phone",
            "support_email",
        ]
    )
    return tenant


def field(fields, label):
    return next(f for f in fields if f.label == label)


def test_def_2865__the_masthead_names_the_utility_that_sent_the_bill(brazos, dana):
    """Utility · Address · Contact — three em-dashes on a real issued bill."""
    with tenant_ctx(brazos):
        a_utility_with_a_profile(brazos)

        document = documents.render_invoice(an_issued_bill(brazos, dana))

        assert field(document.masthead, "Utility").value == "Brazos Bend Utilities"
        assert (
            field(document.masthead, "Address").value
            == "104 Old Ferry Road, Needville, TX 77461"
        )
        contact = field(document.masthead, "Contact").value
        assert "(979) 555-0142" in contact
        assert "billing@brazosbendutilities.test" in contact
        assert not any(f.absent for f in document.masthead), [
            f.absent for f in document.masthead if f.absent
        ]


def test_def_2865__the_masthead_reaches_the_page_the_customer_holds(brazos, dana):
    """Not only the mapping — hard-won law 6, on the serialisation."""
    with tenant_ctx(brazos):
        a_utility_with_a_profile(brazos)

        document = documents.render_invoice(an_issued_bill(brazos, dana))

        page = pdf_text(document.pdf)
        assert "Brazos Bend Utilities" in page
        assert "104 Old Ferry Road" in page


def test_def_2865__the_bill_says_what_period_it_is_for_and_when_it_was_raised(brazos, dana):
    """Cycle and Bill date — both on the run, neither stamped until now.

    The bill date is the run's own (BR-BIL-070), which is what the due date is
    derived FROM, so a bill printing a due date and no bill date was showing a
    customer the conclusion without its premise.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)

        document = documents.render_invoice(bill)

        assert field(document.meta, "Bill date").value != DASH
        assert field(document.meta, "Cycle").value != DASH
        # And it is a STORED date, not today (BR-TEN-043): the fixture's cycle
        # bills in June, and the suite does not run in June 2026.
        assert field(document.meta, "Bill date").value.startswith("2026-0")


def test_def_2865__a_utility_that_has_filled_nothing_in_still_gets_a_named_absence(brazos, dana):
    """The other direction, and the reason the machinery stays.

    A tenant that has not completed its company profile must not print a blank
    line where its address belongs — it prints the dash and the document REPORTS
    the gap, which is what makes the S62 checklist item actionable. Nothing here
    composes an address out of fragments.

    ⚠ **THE NAME IS THE ONE THAT DOES NOT GO ABSENT HERE, AND THAT IS THE
    FALLBACK WORKING.** A tenant always has the name it signed up under, so the
    masthead falls back to it rather than to a dash — third in the chain after
    the trading name and the legal name. What it NEVER falls back to is the
    subdomain, which is a routing fact and not a name anybody chose.
    """
    with tenant_ctx(brazos):
        brazos.legal_name = None
        brazos.dba_name = None
        brazos.mailing_address = None
        brazos.support_phone = None
        brazos.support_email = None
        brazos.save(
            update_fields=[
                "legal_name",
                "dba_name",
                "mailing_address",
                "support_phone",
                "support_email",
            ]
        )

        document = documents.render_invoice(an_issued_bill(brazos, dana))

        assert field(document.masthead, "Utility").value == brazos.name
        assert brazos.subdomain not in field(document.masthead, "Utility").value
        assert field(document.masthead, "Address").value == DASH
        assert field(document.masthead, "Contact").value == DASH
        named = {absent.field for absent in document.absent}
        assert {"utility_address", "utility_contact"} <= named
        assert "utility_name" not in named


def test_def_2865__the_render_still_touches_only_two_rows(brazos, dana, django_assert_num_queries):
    """Stamped, not joined. The masthead must not become a live read.

    A tenant renamed after issue would re-title a bill already sent, which is
    the same rule (BR-BIL-030) that DEF-2852 turned on, and tc2 of
    `test_us_bil_022_documents.py` owns the guarantee.
    """
    with tenant_ctx(brazos):
        a_utility_with_a_profile(brazos)
        bill = an_issued_bill(brazos, dana)

        with django_assert_num_queries(2) as captured:
            documents.render_invoice(bill)

        touched = " ".join(entry["sql"] for entry in captured.captured_queries)
        assert " tenants " not in touched, touched
        assert " cycles " not in touched, touched


def no_contact_seam(monkeypatch):
    """`_snapshot_for` also asks customers for the primary contact's name.

    Stubbed rather than satisfied: these two cases are about ONE key composed
    from the premises facts, and giving the fake account enough shape to survive
    a real customers query would make them a test of the customers seam.
    """
    from apps.billing import gather

    monkeypatch.setattr(gather, "_resolve", lambda *_args, **_kw: None)


def test_def_2865__the_snapshot_carries_the_service_address_from_the_premises(monkeypatch):
    """Stamped at GATHER, beside the customer name, for the same reason.

    Read as a unit on `_snapshot_for`: what this half of the defect turns on is
    one key composed from the premises facts `gather_account` already holds, and
    driving a whole run to assert it would prove the run works.
    """
    no_contact_seam(monkeypatch)
    from apps.billing import gather

    class _Unit:
        id = "u-1"
        label = "Unit A"

    class _Account:
        account_no = "A-10432"

    snapshot = gather._snapshot_for(
        _Account(),
        _Unit(),
        {"id": None, "name": "Residential Standard", "version": 3},
        premises={
            "address_line": "18 Cypress Bend",
            "city": "Needville",
            "state": "TX",
            "postal_code": "77461",
        },
    )

    assert snapshot["service_address"] == "18 Cypress Bend, Needville, TX 77461"


def test_def_2865__a_premises_with_no_address_stamps_no_address(monkeypatch):
    """Never a partial string, never the word None, never a guess."""
    no_contact_seam(monkeypatch)
    from apps.billing import gather

    class _Unit:
        id = "u-1"
        label = "Unit A"

    class _Account:
        account_no = "A-10432"

    snapshot = gather._snapshot_for(
        _Account(),
        _Unit(),
        {"id": None, "name": "Residential Standard", "version": 3},
        premises={},
    )

    assert snapshot["service_address"] is None
