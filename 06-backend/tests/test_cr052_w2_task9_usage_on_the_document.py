# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W2 task 9 — "Draw the twelve-month block on the bill document
#          and in the printable page". BLOCKED until 2026-08-31 by `DEF-2714`:
#          task 8 froze the block onto every bill and NOTHING served it, so the
#          frontend half had no lawful source to draw from.
# Rules:   A19 §1.7 (the twelve-month usage block) · BR-MET-106 (the stored
#          monthly grain — an unread month is ABSENT, never 0; estimates count
#          and are MARKED) · BR-BIL-030 (the bill is LOCKED at issue and the
#          document joins nothing live) · BR-BIL-055 (a break never blocks a
#          bill) · B14 rule 31 (no database id is the visible value of a field)
# Tests:   this file
# Impacts: apps/billing/documents.py (`_usage`, `DocumentUsageSeries`,
#          `LAYOUT_FIELDS`, `_html_for`, `_pdf_rows`) ·
#          apps/billing/documents_api.py (`_rendered_dict`)
# ───────────────────────────────────────────────────────
"""The frozen twelve months, served and drawn.

⚠ **WHY THE SOURCE MATTERS MORE THAN THE PICTURE, and why `DEF-2714` was filed
rather than worked around.** The tempting way to draw a twelve-month chart on a
bill screen is to ask the ACCOUNT for its usage history — one existing endpoint,
no backend work. That is exactly the live join `BR-BIL-030` forbids: a bill's
contents are frozen at issue, so a 2026 bill reopened in 2033 would draw 2033's
twelve months above 2026's charges and the page would disagree with itself.

So the only lawful source is `bill_payload.usage_history`, which
`issue._stamp_usage_history` froze at issue with the axis ending at the BILL's
own period end. `test_the_render_reads_the_payload_and_queries_nothing` is the
structural form of that promise, and `test_a_changed_stamp_changes_the_page`
is the behavioural one: the page follows the SNAPSHOT, wherever the world has
got to.

⚠ **THE ABSENT MONTH IS THE CASE THAT CARRIES THE RULE.** Nine of the twelve
months on the reference bill have no stored reading. Drawing them as `0` would
tell a customer their meter was read and showed no consumption — a statement
about their usage that this utility never made. Both serialisations are asserted
to leave them empty, and the frontend has the same case in
`billUsageBlock.dom.test.tsx` TC-2.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import documents, documents_api, models as billing_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


#: THE BILL FIXTURE'S OWN PERIOD END (`a_priced_draft`: 2026-06-30), and the
#: twelve-month axis therefore runs 2025-07 .. 2026-06. It is derived here
#: rather than hardcoded as "the last twelve months", because that is the rule:
#: `metering_seam.usage_history_for` is passed the BILL's `period_end` and never
#: a clock (BR-TEN-043), so this bill draws the same twelve months whenever it
#: is reprinted.
BILL_PERIOD_END = date(2026, 6, 30)


def axis_labels(period_end=BILL_PERIOD_END, months=12):
    labels = []
    year, month = period_end.year, period_end.month
    for _ in range(months):
        labels.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(labels))


#: A-10432's real shape, copied from `BL-2608-000095` on the development
#: database rather than idealised: three measured months and NINE unmeasured
#: ones. Nine absent months is the interesting case, not a blemish — it is where
#: BR-MET-106's *ABSENT, never 0* actually bites.
MEASURED = {-3: 412, -2: 842, -1: 628}


def measured_for(labels=None):
    labels = labels or axis_labels()
    return {labels[offset]: value for offset, value in MEASURED.items()}


def _store_months(tenant, account, *, estimated_month=None, mixed_units=False):
    """Write the measured months into `meter_read_monthly_usage` as heads.

    ⚠ **THE MONTHS ARE STORED ON THE ACCOUNT, NOT HANDED IN AS A PAYLOAD, AND
    THAT IS NOT FUSSINESS.** `issue._stamp_usage_history` runs INSIDE
    `issue_invoice` and OVERWRITES `payload["usage_history"]` with metering's
    own answer, so a fixture that passes the block in as a `bill_payload`
    override tests a bill the product cannot produce: the stamp replaces it and
    the document renders an empty section. (Measured — the first draft of this
    file did exactly that and died on `assert len(document.usage) == 1` with
    `document.usage == ()`.)

    Storing them means the chain under test is the real one, end to end:
    BR-MET-106's stored grain → `metering_seam.usage_history_for` → the stamp →
    the frozen payload → `documents._usage` → both serialisations.
    """
    from django.utils import timezone

    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code="electric")
    now = timezone.now()
    for label, quantity in measured_for().items():
        year, month = label.split("-")
        estimated = 1 if label == estimated_month else 0
        metering_models.MonthlyUsage.objects.create(
            tenant=tenant,
            account=account,
            service=service,
            period_month=date(int(year), int(month), 1),
            quantity=Decimal(quantity),
            # A window whose months disagree about their unit has no single
            # axis and no summable figure (hard rule 3 / OQ-358).
            unit=("kgal" if (mixed_units and label == axis_labels()[-1]) else "kWh"),
            read_count=1,
            estimated_read_count=estimated,
            source_read_ids=[],
            source_fingerprint=f"cr052-task9-{label}",
            computed_at=now,
        )


def a_bill_with_usage(tenant, dana, **kwargs):
    """An ISSUED bill carrying the block — through the real stamp, not around it."""
    account = an_account(dana, tenant)
    _store_months(tenant, account, **kwargs)
    return an_issued_bill(tenant, dana, account=account)


# ══════════════════════════════════════════════════════════════════════════
# The block reaches the document
# ══════════════════════════════════════════════════════════════════════════
def test_the_document_carries_the_twelve_frozen_months(brazos, dana):
    """A19 §1.7 — `DEF-2714`'s headline: it is stamped and served to nobody."""
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        assert len(document.usage) == 1
        series = document.usage[0]
        assert series.heading == "Electric"
        assert series.unit == "kWh"
        assert len(series.months) == 12
        assert series.months_present == 3
        assert [m.quantity_display for m in series.months[-3:]] == ["412", "842", "628"]


def test_usage_is_a_layout_field_so_every_layout_receives_it(brazos, dana):
    """The desync `LAYOUT_FIELDS`' own comment was written to prevent.

    `remarks` became the twelfth section and a hand-copied key list died on
    `KeyError: 'remarks'` inside a layout. `usage` is the thirteenth.
    """
    assert "usage" in documents.LAYOUT_FIELDS
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        mapping = documents.document_mapping(document)
        assert tuple(mapping) == tuple(documents.LAYOUT_FIELDS)
        assert mapping["usage"] == document.usage


def test_an_absent_month_is_never_drawn_as_a_zero(brazos, dana):
    """BR-MET-106 — *ABSENT, never 0*, in BOTH serialisations.

    A zero would be a claim that the meter was read and showed no consumption.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        absent = [m for m in document.usage[0].months if m.absent]
        assert len(absent) == 9
        assert {m.quantity for m in absent} == {""}
        assert {m.quantity_display for m in absent} == {""}

        # The HTML marks the state rather than printing a figure.
        assert document.body.count('data-absent="true"') == 9
        # DEF-BIL-10546 — the cell prints the page's dash, never a figure.
        assert f'<td data-absent="true">{documents.ABSENT_MARK}</td>' in document.body

        # The page prints a dash in the slot, and nowhere a fabricated 0.
        page = document.pdf.decode("latin-1")
        assert "USAGE HISTORY" in page
        assert "2025-09" in page


def test_both_serialisations_carry_the_same_months(brazos, dana):
    """`tc13`'s no-drift rule, extended to the new section.

    Two serialisations that disagreed about a customer's consumption would be
    two documents, and the customer holds one of them.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        page = document.pdf.decode("latin-1")
        for month in document.usage[0].months:
            assert month.label in document.body, f"{month.label} is not in the HTML"
            assert month.label in page, f"{month.label} is not on the PAGE"
            if not month.absent:
                assert month.quantity_display in document.body
                assert month.quantity_display in page


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-030 — the frozen block is the ONLY source
# ══════════════════════════════════════════════════════════════════════════
def test_the_render_reads_the_payload_and_queries_nothing_for_it(
    brazos, dana, django_assert_num_queries
):
    """BR-BIL-030 made structural — drawing the chart adds NO query.

    `tc2` already pins the render at two queries and names both. This asserts
    the same count with the usage block present, so the obvious "fix" for a
    missing chart — reach into `meter_read_monthly_usage` at render time — is a
    test failure rather than a silently wrong bill.
    """
    with tenant_ctx(brazos):
        bill = a_bill_with_usage(brazos, dana)
        with django_assert_num_queries(2) as captured:
            document = documents.render_invoice(bill)
        assert document.usage, "the block must be drawn from the payload alone"
        statements = [entry["sql"] for entry in captured.captured_queries]
        touched = " ".join(statements)
        for live in ("meter_read_monthly_usage", "meter_reads", "accounts", "services"):
            assert live not in touched, (
                f"the render reached into {live} to draw the usage block. BR-BIL-030 "
                f"freezes a bill's contents at issue, so a live read would redraw every "
                f"historical bill from today's data (DEF-2714). Queries: {statements}"
            )


def test_the_page_follows_the_snapshot_after_the_world_moves_on(brazos, dana):
    """The behavioural half of BR-BIL-030, and the case `DEF-2714` is about.

    **The world CHANGES after the bill is issued** — a late read restates a
    month, which `BR-MET-106` explicitly allows — and the already-issued bill
    must still draw the twelve months it was sent with. A live join would show
    the new figure on a bill printed before it existed, which is precisely the
    2033-reprint problem that made a frontend-only fix impossible.
    """
    from django.utils import timezone

    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        bill = a_bill_with_usage(brazos, dana)
        before = documents.render_invoice(bill)
        last = axis_labels()[-1]
        assert before.usage[0].months[-1].quantity_display == "628"

        # A late read restates the final month, long after the bill went out.
        head = metering_models.MonthlyUsage.objects.get(
            account_id=bill.account_id, period_month=date(2026, 6, 1)
        )
        head.quantity = Decimal(999)
        head.computed_at = timezone.now()
        head.save(update_fields=["quantity", "computed_at"])

        after = documents.render_invoice(
            billing_models.Invoice.objects.get(pk=bill.pk)
        )
        assert after.usage[0].months[-1].quantity_display == "628", (
            f"the bill redrew {last} from today's stored usage. BR-BIL-030 freezes a "
            "bill's contents at issue, so a reprint must show what was SENT."
        )
        assert "999" not in after.body


# ══════════════════════════════════════════════════════════════════════════
# What the block does NOT carry, and what it refuses to break over
# ══════════════════════════════════════════════════════════════════════════
def test_no_database_id_reaches_the_document(brazos, dana):
    """B14 rule 31 — *no database id is ever the visible value of a field*.

    The stamped block is metering's read model and carries `account_id` plus an
    `id` on every service. The document is a PROJECTION of it, so none of that
    travels: the series is named by the service NAME.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        served = documents_api._rendered_dict(document)
        blob = repr(served["usage"])
        assert "01a0549d-2383-78ec-86ea-567873336c4c" not in blob  # the account
        assert "01a0549c-e7c1-7bb2-9f6f-9e1c0a3d5f00" not in blob  # the service
        assert served["usage"][0]["heading"] == "Electric"
        assert "2025-09" not in document.body.split('class="usage"')[0]


def test_a_bill_with_no_block_has_no_section_at_all(brazos, dana):
    """Every bill issued before task 8 — omitted whole, never a heading over
    nothing (the `_remarks` posture)."""
    with tenant_ctx(brazos):
        document = documents.render_invoice(an_issued_bill(brazos, dana))
        assert document.usage == ()
        assert '<section class="usage">' not in document.body
        assert "USAGE HISTORY" not in document.pdf.decode("latin-1")
        assert documents_api._rendered_dict(document)["usage"] == []


def test_a_block_of_a_shape_nobody_stamped_never_refuses_a_bill():
    """BR-BIL-055 — the chart is a courtesy, the bill is the money.

    A19 marks this section OPTIONAL, so an unrecognised shape becomes one named
    absence and the bill still renders. Refusing here would turn a cosmetic
    surprise into an unprintable receivable.

    ⚠ Driven through `_usage` DIRECTLY rather than through a crafted
    `bill_payload`, for the reason `_store_months` gives: the stamp overwrites
    the payload at issue, so a malformed block cannot be planted on an issued
    bill at all. This is the projection's own contract, tested where it lives.
    """
    series, absent = documents._usage({"usage_history": {"window": {}, "series": "not a list"}})
    assert series == ()
    assert [entry.field for entry in absent] == ["usage_history"]
    assert "BR-MET-106" in absent[0].br_ref

    # A bill with no block at all is not a problem to report — it is simply a
    # bill issued before the stamp existed, and it states nothing.
    assert documents._usage({}) == ((), [])
    assert documents._usage({"usage_history": None}) == ((), [])


def test_a_mixed_unit_window_is_stated_and_not_summed(brazos, dana):
    """Hard rule 3 — months that disagree about their unit share no axis."""
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana, mixed_units=True))
        series = document.usage[0]
        assert series.unit is None
        assert series.absent is not None
        assert "OQ-358" in series.absent.br_ref


def test_an_estimated_month_is_marked(brazos, dana):
    """BR-MET-106 — *estimates count and are marked*."""
    with tenant_ctx(brazos):
        # ⚠ THE MONTH MUST BE ON THIS BILL'S AXIS. A first draft named
        # `2026-07`, which is one month AFTER the fixture bill's period end, so
        # nothing was stored on the axis at all and the case failed with
        # `assert [] == ['2026-07']` — a test bug that reads exactly like a
        # product bug. The axis is derived, so name a month from it.
        estimated = axis_labels()[-2]
        document = documents.render_invoice(
            a_bill_with_usage(brazos, dana, estimated_month=estimated)
        )
        marked = [m for m in document.usage[0].months if m.estimated]
        assert [m.label for m in marked] == [estimated]
        assert "* estimated" in document.pdf.decode("latin-1")


def test_the_withdrawn_absence_is_gone(brazos, dana):
    """Hard-won law 1 in both directions.

    `usage_history_stamped_but_not_drawn` said *"the printed page does not yet
    plot it"*. It does now, so the sentence is DELETED rather than left standing
    — the `pdf_not_rendered` precedent of 2026-08-11.
    """
    with tenant_ctx(brazos):
        document = documents.render_invoice(a_bill_with_usage(brazos, dana))
        codes = {entry["code"] for entry in document.unavailable}
        assert "usage_history_not_available" not in codes
        assert "usage_history_stamped_but_not_drawn" not in codes


def test_the_response_serialises_the_block_for_the_screen(brazos, dana):
    """`DEF-2714`'s other half — `_rendered_dict` served none of it."""
    with tenant_ctx(brazos):
        served = documents_api._rendered_dict(
            documents.render_invoice(a_bill_with_usage(brazos, dana))
        )
        assert "usage" in served
        months = served["usage"][0]["months"]
        assert len(months) == 12
        # The exact decimal travels beside the display text: a bar's HEIGHT is
        # computed from it, and a 2dp string would quantise every bar.
        assert months[-1]["quantity"] == "628.000000"
        assert months[-1]["quantity_display"] == "628"
        assert months[0]["absent"] is True
