# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2852 — the issued bill headed its charge blocks
#          `Service 01a046d3-090d-7eca-a4ac-87723f3a9e3f`. The customer should
#          read *Water*. Reported by the PO from their own live bill
#          BL-2608-000048, which showed two such headings (water and sewer).
# Rules:   B14 rule 31 (PO 2026-08-30, verbatim *"no Databse ID on screen -
#          that is a rule"*) · BR-BIL-030 (the document renders from the LOCKED
#          snapshot and joins nothing live) · BR-BIL-069 (a line names its
#          service) · B14 rule 32 (no internal code in the copy a human reads)
# Tests:   this file
# Impacts: apps/billing/documents.py · apps/billing/stages/assemble_document.py
#          · apps/billing/tenancy_seam.py · apps/tenancy/selectors.py
# ───────────────────────────────────────────────────────
"""The bill names its services, and it never prints a database id.

THE FIX IS A STAMP, NOT A JOIN, and that distinction is the whole file.

`documents._groups` grouped by `invoice_lines.service_id` and had no way to
turn that id into a word, so it printed the id. The obvious repair — look the
name up in `tenancy.services` while rendering — is the one BR-BIL-030 forbids:
a service renamed after issue would re-title a bill already sent, and
`tc2` in `test_us_bil_022_documents.py` pins the render to TWO queries so a
third would go red anyway. `tc_render_makes_no_extra_query` below asserts that
the fix did not buy its way out of the defect with a query.

So the name is stamped into `bill_payload["services"][n]` at DRAFT time, beside
the `code` that was already there, and the document reads the frozen word.

`tc_a_bill_issued_before_the_stamp` is the case that decides how good the fix
is. Those bills exist — the PO is holding one — and their payloads carry no id
at all. They print a NEUTRAL heading and a named absence, and never the id: a
bill that does not name a service is a worse bill, and a bill that shows a
customer a UUID is a broken one.
"""

import re
import uuid

import pytest

from apps.billing import documents, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill, a_stage6_payload, pdf_text

pytestmark = pytest.mark.django_db

#: Any UUID, in the canonical hyphenated form the defect printed.
UUID_ANYWHERE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _electric_id():
    from apps.tenancy import models as tenancy_models

    return str(tenancy_models.Service.objects.get(code="electric").id)


def a_payload_with_the_service_stamped(**overrides):
    """The payload stage 6 stamps SINCE this defect — id and name beside code."""
    payload = a_stage6_payload()
    payload["services"] = [
        {
            "code": "electric",
            "id": _electric_id(),
            "name": "Electric",
            "measured": True,
            "estimated": False,
            "absent_reason": None,
        }
    ]
    payload.update(overrides)
    return payload


def test_def_2852__the_charge_block_is_headed_by_the_service_name(brazos, dana):
    """The defect itself. `Service <uuid>` becomes `Electric`."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_the_service_stamped())

        document = documents.render_invoice(bill)

        headings = [group.heading for group in document.groups]
        assert "Electric" in headings, headings
        assert not any("Service " in heading for heading in headings), headings


def test_def_2852__no_database_id_reaches_the_page_or_the_screen(brazos, dana):
    """B14 rule 31 on the most public surface the product has.

    Asserted on BOTH serialisations, because the customer holds the page and
    the dispute reads the screen — and on the group headings specifically, so
    that a UUID moving from the heading into some other field cannot pass.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_the_service_stamped())

        document = documents.render_invoice(bill)

        assert not UUID_ANYWHERE.search(pdf_text(document.pdf)), pdf_text(document.pdf)
        assert not UUID_ANYWHERE.search(document.body), document.body
        for group in document.groups:
            assert not UUID_ANYWHERE.search(group.heading), group.heading


def test_def_2852__a_bill_issued_before_the_stamp_prints_a_neutral_heading(brazos, dana):
    """No id in the payload — so no name, and NEVER the id as a fallback.

    Every bill this product has issued is in this state, the PO's own
    BL-2608-000048 among them. The heading degrades to the one the document
    already uses for a line that names no service at all, and the absence is
    recorded so the gap is reportable rather than invisible.
    """
    with tenant_ctx(brazos):
        # `a_stage6_payload` is deliberately the PRE-defect shape: code only.
        bill = an_issued_bill(brazos, dana)

        document = documents.render_invoice(bill)

        assert not UUID_ANYWHERE.search(pdf_text(document.pdf)), pdf_text(document.pdf)
        assert not UUID_ANYWHERE.search(document.body), document.body
        assert [group.heading for group in document.groups] == ["Charges this period"]
        assert "service_name" in {absent.field for absent in document.absent}


def test_def_2852__the_services_band_names_the_service_too(brazos, dana):
    """B14 rule 32 — the band beside the charges reads `Electric`, not `electric`."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_the_service_stamped())

        document = documents.render_invoice(bill)

        assert [field.label for field in document.services] == ["Electric"]


def test_def_2852__an_unnamed_stamp_falls_back_to_the_code_never_to_the_id(brazos, dana):
    """A payload carrying the id and no name still prints a WORD.

    `storm_water` is the case that decides the spelling: the catalog calls it
    *Storm water*, so the fallback capitalises rather than title-casing, and
    `Storm Water` would be a second name for one service.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        storm = tenancy_models.Service.objects.get(code="storm_water")
        payload = a_stage6_payload()
        payload["services"] = [
            {
                "code": "storm_water",
                "id": str(storm.id),
                "measured": True,
                "estimated": False,
                "absent_reason": None,
            }
        ]

        def stamp_the_line(draft):
            models.InvoiceLine.objects.filter(invoice=draft, kind="base").update(
                service_id=storm.id
            )

        bill = an_issued_bill(brazos, dana, bill_payload=payload, before_issue=stamp_the_line)

        document = documents.render_invoice(bill)

        assert "Storm water" in [group.heading for group in document.groups]


def test_def_2852__the_render_still_touches_only_two_rows(brazos, dana, django_assert_num_queries):
    """The fix must not become the live join BR-BIL-030 forbids.

    `test_us_bil_022_documents.py::…tc2` owns this guarantee; it is repeated
    here because the tempting repair for THIS defect is exactly the one that
    breaks it, and a lane reading only this file would not see that test.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_the_service_stamped())

        with django_assert_num_queries(2) as captured:
            documents.render_invoice(bill)

        touched = " ".join(entry["sql"] for entry in captured.captured_queries)
        assert " services " not in touched, touched


def test_def_2852__stage_6_stamps_the_id_and_the_name_into_the_payload():
    """The other half: what the payload CARRIES, asserted where it is written.

    Read as a unit on `_snapshot_payload` rather than through a whole run,
    because what this defect turns on is one key being present beside `code`.
    """
    from apps.billing.stages import assemble_document as stage6

    class _Sub:
        account_no = "A-1"
        currency = "USD"
        rate_plan_id = None
        rate_plan_name = "Residential Standard"
        rate_plan_version = 3
        tax_exempt = False
        snapshot: dict = {}

        class period:
            cycle_days = 30
            service_days = 30

    class _Service:
        service_code = "water"
        consumption = None
        estimated = False
        absent_reason = "no_reading_supplied"
        read_id = None

    class _Usage:
        subscription = _Sub()
        services = (_Service(),)

    class _Priced:
        total = 0
        lines = ()

    from datetime import date

    payload = stage6._snapshot_payload(
        _Usage(),
        _Priced(),
        date(2026, 6, 30),
        service_catalog={"water": ("11111111-1111-1111-1111-111111111111", "Water")},
    )

    assert payload["services"][0]["id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["services"][0]["name"] == "Water"
    assert payload["services"][0]["code"] == "water"


def test_def_2852__a_service_the_catalog_cannot_name_stamps_no_id():
    """An id is stamped only when the catalog answered. Never invented."""
    from datetime import date

    from apps.billing.stages import assemble_document as stage6

    class _Sub:
        account_no = "A-1"
        currency = "USD"
        rate_plan_id = None
        rate_plan_name = None
        rate_plan_version = None
        tax_exempt = False
        snapshot: dict = {}

        class period:
            cycle_days = 30
            service_days = 30

    class _Service:
        service_code = "unlisted"
        consumption = None
        estimated = False
        absent_reason = "no_reading_supplied"
        read_id = None

    class _Usage:
        subscription = _Sub()
        services = (_Service(),)

    class _Priced:
        total = 0
        lines = ()

    payload = stage6._snapshot_payload(_Usage(), _Priced(), date(2026, 6, 30), service_catalog={})

    assert payload["services"][0]["id"] is None
    assert payload["services"][0]["name"] is None


def test_def_2852__the_uuid_probe_can_actually_fail():
    """The check that proves the checks above are not vacuous (hard-won law 7)."""
    assert UUID_ANYWHERE.search(f"Service {uuid.uuid4()}")
