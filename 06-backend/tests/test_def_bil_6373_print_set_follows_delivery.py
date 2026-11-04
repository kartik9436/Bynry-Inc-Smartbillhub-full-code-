# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-6373 — the print-shop archive held out a bill whose account
#          has no mailing address, while the delivery queue addressed the same
#          bill to the premises.
# Ruling:  decision log 2026-09-23 (*DECIDED, NOT ASKED*): the print set follows
#          the same fallback, per the PO's *"ensure you update correct address -
#          mailing or service"* and B2 §2 (an absent mailing row MEANS "same as
#          service").
# Rules:   BR-NOT-029 (a) discrete columns, never split · (b) an incomplete
#          address is held and reported · BR-CUS-674 (a read writes nothing) ·
#          BR-BIL-036 (a fact about the PLATFORM is not a fact about the
#          PROPERTY) · CLAUDE.md hard rule 8 (an address lives on premises; a
#          unit refines it by LABEL) · NFR-3 (no per-row reads)
# Tests:   this file
# Impacts: apps/customers/selectors.py (`print_address_for_account`,
#          `account_ids_without_print_address`, `_postal_snapshot`) ·
#          apps/billing/customers_seam.py · apps/billing/print_set.py
# ───────────────────────────────────────────────────────
"""One answer to *where does this bill go*, asked by the queue and the print set.

The load-bearing case is the FIRST: for the same account, the delivery queue's
print recipient and the print-shop manifest name the same street, town, state
and postcode. Everything after it is a leg of that answer — the mailing row
wins, a removed or streetless mailing row falls back, a hole is held and says
which record to fix, metering unable to answer is not an incomplete address —
and the last proves the bulk forecast read gives the single read's verdict for
every shape, because the tile and the archive must never disagree.

RED on the unchanged tip (hard-won law 7) is quoted in the lane report and in
the defect's close: the first case failed there with the bill HELD as
`address_incomplete` — *"this account's mailing address has no line1, city,
state, postal code"* — while the queue addressed it to 1408 Bluestem Ln.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone

import pytest

from apps.billing import customers_seam, print_set
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.customers import seams as customers_seams
from apps.customers import selectors as customer_selectors
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db

GENERATED_AT = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)


def a_mailing_row(tenant, account, **overrides):
    values = dict(
        tenant=tenant,
        account=account,
        kind="mailing",
        line1="PO Box 77",
        city="Sugar Land",
        state="TX",
        postal_code="77478",
    )
    values.update(overrides)
    return customer_models.Address.objects.create(**values)


def a_printable_bill(tenant, account, invoice_no):
    return an_invoice(
        tenant,
        account,
        invoice_no=invoice_no,
        status=billing_models.INVOICE_ISSUED,
        template_version=1,
        payload_version=1,
        bill_payload={"customer_name": "Miller, Sarah", "account_no": account.account_no},
    )


def manifest_rows(path):
    with zipfile.ZipFile(path) as archive:
        rows = list(
            csv.DictReader(io.StringIO(archive.read(print_set.MANIFEST_NAME).decode("utf-8")))
        )
    return {row["bill_no"]: row for row in rows}


def queued_to(account_id):
    """Where the DELIVERY QUEUE posts this account's letter — its snapshot."""
    answer = customer_selectors.delivery_recipients_for_account(
        account_id, channels=("pdf_print",)
    )["pdf_print"]
    return answer.get("snapshot"), answer.get("unavailable_reason")


# ══ 1 · THE DEFECT: THE QUEUE AND THE PRINT SET NAME THE SAME PLACE ═════════


def test_no_mailing_row_the_queue_and_the_print_set_both_post_to_the_premises(
    brazos, dana, tmp_path
):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6373", contact_name="Miller, Sarah")
        bill = a_printable_bill(brazos, account, "BL-2609-006373")
        queued, _ = queued_to(account.id)
        result = print_set.build_print_set([bill], tmp_path / "set.zip", generated_at=GENERATED_AT)
    row = manifest_rows(tmp_path / "set.zip").get("BL-2609-006373")

    assert queued["source"] == "service_address"
    assert result.held_count == 0, [entry.reason for entry in result.held]
    assert row is not None, "the bill the queue addresses is missing from the print file"
    assert (row["address_line_1"], row["city"], row["state"], row["postal_code"]) == (
        queued["line1"],
        queued["city"],
        queued["state"],
        queued["postal_code"],
    )
    assert row["address_line_2"] == queued["unit_label"] == "Unit A"


def test_a_mailing_row_wins_in_both(brazos, dana, tmp_path):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6374")
        a_mailing_row(brazos, account, line2="Suite 4", country="USA")
        bill = a_printable_bill(brazos, account, "BL-2609-006374")
        queued, _ = queued_to(account.id)
        print_set.build_print_set([bill], tmp_path / "set.zip", generated_at=GENERATED_AT)
        answer = customers_seam.print_address_for_account(account.id)
    row = manifest_rows(tmp_path / "set.zip")["BL-2609-006374"]

    assert queued["source"] == answer.source == "mailing_address"
    assert row["address_line_1"] == queued["line1"] == "PO Box 77"
    assert (row["address_line_2"], row["country"]) == ("Suite 4", "USA")


@pytest.mark.parametrize("shape", ["removed", "no_street"])
def test_a_mailing_row_that_cannot_be_posted_to_falls_back_in_both(brazos, dana, shape):
    """A soft-deleted row (how a clerk says *send it to the service address*) and
    a row with no street are both *no mailing address* to `_postal_snapshot`,
    so both go to the premises — in the queue AND in the print set."""
    from django.utils import timezone as dj_timezone

    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no=f"A-{shape}")
        if shape == "removed":
            a_mailing_row(brazos, account, deleted_at=dj_timezone.now())
        else:
            a_mailing_row(brazos, account, line1="   ")
        queued, _ = queued_to(account.id)
        answer = customers_seam.print_address_for_account(account.id)

    assert queued["source"] == answer.source == "service_address"
    assert answer.line1 == queued["line1"]
    assert answer.is_complete


# ══ 2 · A HOLE IS HELD, AND THE SENTENCE SAYS WHICH RECORD TO FIX ════════════


def test_a_mailing_row_with_a_hole_is_held_not_swapped_for_the_premises(brazos, dana, tmp_path):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6375")
        a_mailing_row(brazos, account, postal_code="")
        bill = a_printable_bill(brazos, account, "BL-2609-006375")
        result = print_set.build_print_set([bill], tmp_path / "set.zip", generated_at=GENERATED_AT)

    assert result.held_count == 1
    held = result.held[0]
    assert held.reason_code == print_set.HELD_ADDRESS_INCOMPLETE
    assert "mailing address has no postal code" in held.reason


def test_a_premises_with_a_hole_is_held_and_names_the_property(brazos, dana, tmp_path):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6376")
        unit = metering_models.Unit.objects.get(pk=account.unit_id)
        metering_models.Premises.objects.filter(pk=unit.premises_id).update(postal_code="")
        bill = a_printable_bill(brazos, account, "BL-2609-006376")
        result = print_set.build_print_set([bill], tmp_path / "set.zip", generated_at=GENERATED_AT)
        forecast = print_set.forecast_print_set({})

    assert result.held_count == 1
    held = result.held[0]
    assert held.reason_code == print_set.HELD_ADDRESS_INCOMPLETE
    assert "service address has no postal code" in held.reason
    assert "property's address" in held.reason
    assert forecast.held_by_reason == ((print_set.HELD_ADDRESS_INCOMPLETE, 1),)


def test_metering_unable_to_answer_is_unreadable_not_incomplete(brazos, dana, monkeypatch):
    """`BR-BIL-036`: the PLATFORM could not be asked. Held as UNREADABLE by the
    archive, and counted as held by the forecast so the tile never promises it."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6377")
        real = customers_seams.resolve

        def unpublished(module, attribute, kind="services"):
            if attribute == "envelope_addresses":
                return None
            return real(module, attribute, kind)

        monkeypatch.setattr(customers_seams, "resolve", unpublished)
        answer = customers_seam.print_address_for_account(account.id)
        gap = set(customer_selectors.account_ids_without_print_address())

    assert answer.readable is False
    assert answer.problem["code"] == "customers_service_address_unanswerable"
    assert account.id in gap


# ══ 3 · THE BULK FORECAST READ GIVES THE SINGLE READ'S VERDICT ══════════════


def test_the_bulk_gap_and_the_single_read_agree_on_every_shape(brazos, dana):
    """The tile and the archive must hold the same bills. Six shapes, one each."""
    from django.utils import timezone as dj_timezone

    with tenant_ctx(brazos):
        shapes = {}
        shapes["mailing_complete"] = an_account(brazos, dana, account_no="S-1", label="U1")
        a_mailing_row(brazos, shapes["mailing_complete"])
        shapes["mailing_holed"] = an_account(brazos, dana, account_no="S-2", label="U2")
        a_mailing_row(brazos, shapes["mailing_holed"], city="")
        shapes["no_mailing_complete_premises"] = an_account(
            brazos, dana, account_no="S-3", label="U3"
        )
        shapes["no_mailing_holed_premises"] = an_account(brazos, dana, account_no="S-4", label="U4")
        unit = metering_models.Unit.objects.get(pk=shapes["no_mailing_holed_premises"].unit_id)
        metering_models.Premises.objects.filter(pk=unit.premises_id).update(state="")
        shapes["mailing_removed"] = an_account(brazos, dana, account_no="S-5", label="U5")
        a_mailing_row(brazos, shapes["mailing_removed"], deleted_at=dj_timezone.now())
        shapes["mailing_no_street"] = an_account(brazos, dana, account_no="S-6", label="U6")
        a_mailing_row(brazos, shapes["mailing_no_street"], line1="")

        single = {
            name: bool(customers_seam.print_address_for_account(account.id).missing)
            for name, account in shapes.items()
        }
        bulk_all = set(customer_selectors.account_ids_without_print_address())
        bulk_page = set(
            customer_selectors.account_ids_without_print_address(
                account_ids=[account.id for account in shapes.values()]
            )
        )

    assert single == {
        "mailing_complete": False,
        "mailing_holed": True,
        "no_mailing_complete_premises": False,
        "no_mailing_holed_premises": True,
        "mailing_removed": False,
        "mailing_no_street": False,
    }
    for name, account in shapes.items():
        assert (account.id in bulk_all) is single[name], name
        assert (account.id in bulk_page) is single[name], name


def test_the_print_read_writes_nothing(brazos, dana):
    """`BR-CUS-674` — the hand-over runs one direction; the fallback reads the
    premises and writes no mailing row for the customer."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-6378")
        before = customer_models.Address.objects.filter(tenant=brazos).count()
        customers_seam.print_address_for_account(account.id)
        list(customer_selectors.account_ids_without_print_address())
        after = customer_models.Address.objects.filter(tenant=brazos).count()
    assert before == after == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-6373 (filed 2026-09-23 by lane BAD-ADDRESS; decided in the
#         decision log the same day)
# generated: 2026-09-24 by lane SMALL-PAY
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
