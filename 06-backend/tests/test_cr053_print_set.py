# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
#           *"Im okay with this"* on the PDF-set-plus-manifest recommendation.
#           Screen: the Print bills screen
# Rules:    BR-NOT-029 (the pair, the fourteen columns, and clauses (a) discrete
#           address columns / (b) hold an incomplete address / (c) claim no mail
#           standard / (d) never write from a vendor return) · BR-CUS-674 (an
#           address changes when the ACCOUNT HOLDER says so) · BR-BIL-026 (the
#           PINNED template version renders the document, for ever) ·
#           BR-BIL-030 (the bill is frozen at issue) · BR-NOT-027 (the kept
#           bytes ARE the bill) · B14 rule 31 (no database id is the visible
#           value of a field) · CLAUDE.md rule 2 (money DISPLAYS at 2dp)
# Defects:  DEF-2703 · DEF-2847 · DEF-2734
# ───────────────────────────────────────────────────────
"""What the print hand-over must be true about, made falsifiable.

⚠ **EVERY ASSERTION HERE IS ONE THAT CAN FAIL, AND THAT IS NOT A PLATITUDE —
SEVEN CHECKS THAT COULD NOT FAIL WERE FOUND IN THIS REPOSITORY IN ONE DAY.**
Three shapes are deliberately avoided:

  * *"a manifest row exists"* — it does not say WHICH bill the row is about, so
    a set that wrote every row from the first invoice would pass it. The tests
    below match a row to its bill BY NAME and by figure.
  * *"the PDF count is the bill count"* — true and useless when both are zero.
    Every count assertion is paired with `> 0`.
  * *"the address is present"* — a re-render that composed the address from a
    blob would pass. `test_the_address_is_never_split_out_of_a_blob` asserts the
    OPPOSITE: that a free-text address produces a HELD bill and no row at all.

The RED proofs for each guard are quoted in the lane report and in
12-governance/09-human-review-ledger.md (hard-won law 7).
"""

import csv
import io
import re
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import customers_seam, documents, models as billing_models, print_set
from apps.billing.exceptions import BillingRuleError
from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db

#: The instant every set in this file is stamped with. A CONSTANT, because
#: `BR-TEN-043` makes the moment an ARGUMENT and a test that read a clock would
#: assert a different filename every run.
GENERATED_AT = datetime(2026, 8, 31, 14, 5, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════
def a_mailing_address(tenant, account, **overrides):
    """A COMPLETE mailing address — four discrete columns, `BR-NOT-029` (a)."""
    values = dict(
        tenant=tenant,
        account=account,
        kind="mailing",
        line1="1408 Elm Street",
        city="San Antonio",
        state="TX",
        postal_code="78205",
    )
    values.update(overrides)
    return customer_models.Address.objects.create(**values)


def a_printable_bill(tenant, account, **overrides):
    """An ISSUED bill with a payload the renderer can draw and a pin to draw it on."""
    values = dict(
        status=billing_models.INVOICE_ISSUED,
        template_version=1,
        payload_version=1,
        bill_payload={
            "customer_name": "Miller, Sarah",
            "account_no": account.account_no,
            "total": "247.87",
        },
    )
    values.update(overrides)
    return an_invoice(tenant, account, **values)


def read_archive(path):
    """The archive's four members, parsed. Returns (manifest, held, pdfs, readme)."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        manifest = list(
            csv.reader(io.StringIO(archive.read(print_set.MANIFEST_NAME).decode("utf-8")))
        )
        held = list(csv.reader(io.StringIO(archive.read(print_set.HELD_NAME).decode("utf-8"))))
        readme = archive.read(print_set.README_NAME).decode("utf-8")
        pdfs = {
            name: archive.read(name) for name in names if name.startswith(f"{print_set.PDF_DIR}/")
        }
    return manifest, held, pdfs, readme


def build(invoices, tmp_path, name="set.zip"):
    return print_set.build_print_set(invoices, tmp_path / name, generated_at=GENERATED_AT)


def manifest_row_for(manifest, bill_no):
    """The row whose `bill_no` column is this bill, or None.

    Looked up BY THE BILL NUMBER and never by position: a set that wrote every
    row from the first invoice would pass a positional check, and that is
    exactly the defect a manifest cannot afford.
    """
    index = list(print_set.MANIFEST_HEADER).index("bill_no")
    for row in manifest[1:]:
        if row[index] == bill_no:
            return dict(zip(print_set.MANIFEST_HEADER, row))
    return None


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE PAIR — one PDF per bill, one manifest row per bill, both > 0
# ══════════════════════════════════════════════════════════════════════════
def test_one_pdf_and_one_manifest_row_per_bill(brazos, dana, tmp_path):
    """`BR-NOT-029`'s whole promise, counted rather than asserted in the abstract.

    ⚠ **`> 0` IS HALF THE TEST.** `pdf_count == bill_count` is satisfied by
    `0 == 0`, which is what a set that silently held every bill produces — and
    that is not a hypothetical here, because `DEF-2703` makes holding-everything
    the DEFAULT on a tenant whose accounts came from service requests.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        first = a_printable_bill(brazos, account, invoice_no="BL-2608-000001")
        second = a_printable_bill(brazos, account, invoice_no="BL-2608-000002")

        result = build([first, second], tmp_path)
        manifest, held, pdfs, _ = read_archive(tmp_path / "set.zip")

    assert result.considered == 2
    assert result.pdf_count == 2 > 0
    assert result.manifest_rows == 2 > 0
    assert result.pdf_count == result.manifest_rows
    assert result.held == []
    assert len(pdfs) == 2 > 0
    assert set(pdfs) == {
        f"{print_set.PDF_DIR}/BL-2608-000001.pdf",
        f"{print_set.PDF_DIR}/BL-2608-000002.pdf",
    }
    # One header row and exactly two data rows (IS-9: one header, never two).
    assert manifest[0] == list(print_set.MANIFEST_HEADER)
    assert len(manifest) == 3
    assert len(held) == 1  # the header alone


def test_a_manifest_row_matches_the_bill_it_names(brazos, dana, tmp_path):
    """Row → bill, field by field. The check that positional assertions cannot make.

    Two bills with DIFFERENT numbers, different totals and different due dates,
    so a set that wrote both rows from one invoice fails on every column rather
    than on none.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        cheap = a_printable_bill(
            brazos,
            account,
            invoice_no="BL-2608-000010",
            total=Decimal("41.5000"),
            due_date=date(2026, 8, 25),
            service_date=date(2026, 7, 31),
        )
        dear = a_printable_bill(
            brazos,
            account,
            invoice_no="BL-2608-000011",
            total=Decimal("1204.5550"),
            due_date=date(2026, 9, 25),
            service_date=date(2026, 8, 31),
        )

        build([cheap, dear], tmp_path)
        manifest, _, _, _ = read_archive(tmp_path / "set.zip")

    small = manifest_row_for(manifest, "BL-2608-000010")
    large = manifest_row_for(manifest, "BL-2608-000011")
    assert small is not None and large is not None

    assert small["account_no"] == account.account_no
    assert small["customer_name"] == "Miller, Sarah"
    assert small["address_line_1"] == "1408 Elm Street"
    assert small["city"] == "San Antonio"
    assert small["state"] == "TX"
    assert small["postal_code"] == "78205"
    assert small["pdf_filename"] == "BL-2608-000010.pdf"

    # CLAUDE.md rule 2 — money is STORED to 4dp and DISPLAYS at 2. The vendor's
    # file is a display, and `1204.5550` half-up at 2dp is `1204.56`.
    assert small["amount_due"] == "41.50"
    assert large["amount_due"] == "1204.56"

    # BR-BIL-070: the clerk's typed bill date IS the run's service date, and
    # stage 6 stamps it per invoice. BR-BIL-024's due date is stored beside it.
    assert small["bill_date"] == "2026-07-31"
    assert small["due_date"] == "2026-08-25"
    assert large["bill_date"] == "2026-08-31"
    assert large["due_date"] == "2026-09-25"


def test_the_manifest_carries_the_ruled_fourteen_columns_and_no_fifteenth(brazos):
    """`BR-NOT-029` names fourteen, in an order a vendor's loader depends on."""
    assert print_set.MANIFEST_HEADER == (
        "account_no",
        "bill_no",
        "customer_name",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "page_count",
        "bill_date",
        "due_date",
        "amount_due",
        "pdf_filename",
    )
    assert len(print_set.MANIFEST_HEADER) == 14


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE ADDRESS — BR-NOT-029 (a) and (b), and BR-CUS-674
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("gap", ["city", "state", "postal_code"])
def test_an_incomplete_address_is_held_and_reported_never_sent(brazos, dana, tmp_path, gap):
    """`BR-NOT-029` (b): REPORTED and held out of the file — never gap-filled.

    Parameterised over all three mandatory parts because a check written for one
    of them is a check that passes while the other two leak.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account, **{gap: None})
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000020")

        result = build([bill], tmp_path)
        manifest, held, pdfs, _ = read_archive(tmp_path / "set.zip")

    assert result.considered == 1
    assert result.pdf_count == 0
    assert result.manifest_rows == 0
    assert pdfs == {}
    assert manifest_row_for(manifest, "BL-2608-000020") is None

    assert result.held_count == 1
    entry = result.held[0]
    assert entry.reason_code == print_set.HELD_ADDRESS_INCOMPLETE
    assert entry.bill_no == "BL-2608-000020"
    assert gap.replace("_", " ") in entry.reason
    # The file inside the archive says it too — the clerk holds the zip, not the
    # Python object.
    assert any(row[1] == "BL-2608-000020" for row in held[1:])


def test_no_mailing_row_posts_to_the_premises_in_its_own_columns(brazos, dana, tmp_path):
    """`DEF-BIL-6373` — the SAME fallback the delivery queue takes, never a split.

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-24.** It was
    `test_the_address_is_never_split_out_of_a_blob` and held this bill, asserting
    that the premises' *"Bluestem"* appeared nowhere in the manifest. That was
    the pre-ruling rule: an account with no mailing row had no postal address.
    B2 §2 says the absence MEANS *same as service*, the delivery queue has
    addressed such a letter to the premises since `DEF-PAY-6342` part 1, and the
    PO's ruling of 2026-09-23 (*"ensure you update correct address - mailing or
    service"*) decided the print set follows it.

    What this still guards is clause (a): the address arrives in the premises'
    OWN four columns plus the unit's label, each in its own manifest column —
    nothing composed, nothing split (`BR-NOT-029`).
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        # No `addresses` row at all.
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000030")

        result = build([bill], tmp_path)
        manifest, _held, _pdfs, _ = read_archive(tmp_path / "set.zip")

    assert result.held_count == 0, [entry.reason for entry in result.held]
    row = manifest_row_for(manifest, "BL-2608-000030")
    assert row is not None
    assert row["address_line_1"] == "1901 Bluestem Ln"  # the premises' own column
    assert row["address_line_2"] == "Unit A"  # the unit's LABEL (hard rule 8)
    assert (row["city"], row["state"], row["postal_code"]) == ("Katy", "TX", "77494")
    assert row["country"] == ""  # a premises holds none, and none is invented


def test_line2_and_country_are_empty_and_are_never_invented(brazos, dana, tmp_path):
    """`DEF-2847` — two ruled columns with no schema behind them.

    They are EMPTY, and the point of the test is the two things they are not:
    a slice of line 1, and the tenant's own country.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account, line1="1408 Elm Street, Apt 3B")
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000040")
        build([bill], tmp_path)
        manifest, _, _, _ = read_archive(tmp_path / "set.zip")

    row = manifest_row_for(manifest, "BL-2608-000040")
    assert row is not None
    assert row["address_line_1"] == "1408 Elm Street, Apt 3B"  # verbatim, uncut
    assert row["address_line_2"] == ""
    assert row["country"] == ""


def test_reading_an_address_writes_nothing(brazos, dana):
    """`BR-CUS-674` — *"we cannot make chnges until account confirm it"*.

    The hand-over runs ONE direction. Proved by taking the row's `updated_at`
    before and after, rather than by reading the code: a write added later would
    move it, and no amount of docstring would.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        row = a_mailing_address(brazos, account)
        before = (row.line1, row.city, row.state, row.postal_code, row.updated_at)

        answer = customers_seam.print_address_for_account(account.id)
        assert answer.is_complete

        row.refresh_from_db()
        assert (row.line1, row.city, row.state, row.postal_code, row.updated_at) == before
        assert customer_models.Address.objects.filter(tenant=brazos).count() == 1


def test_a_legacy_service_row_is_not_the_service_address(brazos, dana, tmp_path):
    """A `kind='service'` ADDRESS ROW is never read — the premises is.

    ⚠ **THIS CASE HELD THE BILL UNTIL 2026-09-24 (`DEF-BIL-6373`)**, when it was
    `test_a_service_address_is_not_used_as_a_mailing_address`. The print set
    now falls back to the service address as the delivery queue does — and the
    service address is the PREMISES, walked to (hard rule 8), not a legacy row.
    `BR-MET-1161` retired `kind='service'` at the write door; nothing was
    migrated (there were 0 such rows), so one written before that ruling can
    still exist, and this is the only test covering what the print set does when
    it meets one. Written through the MODEL on purpose; `create_account` would
    now refuse it (`test_br_met_1161_one_address_home.py`).
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account, kind="service", line1="99 Meter Yard")
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000050")
        result = build([bill], tmp_path)
        manifest, _, _, _ = read_archive(tmp_path / "set.zip")

    assert result.held_count == 0
    assert manifest_row_for(manifest, "BL-2608-000050")["address_line_1"] == "1901 Bluestem Ln"
    assert "99 Meter Yard" not in "\n".join(",".join(row) for row in manifest)


def test_another_tenants_account_is_absent_not_answered(brazos, lonestar, dana, marcus):
    """HR-1 / BR-TEN-003: a cross-tenant id reads as ABSENT, byte-identically."""
    with tenant_ctx(lonestar):
        stranger = an_account(lonestar, marcus, account_no="A-99999", service="water")
        a_mailing_address(lonestar, stranger)
    with tenant_ctx(brazos):
        assert customer_selectors.mailing_address_for_account(stranger.id) is None
        answer = customers_seam.print_address_for_account(stranger.id)
        assert answer.readable is False
        assert answer.problem is not None


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · THE PIN — BR-BIL-026, and a reprint is the same document
# ══════════════════════════════════════════════════════════════════════════
def test_the_pdf_renders_from_the_bills_own_pinned_version(brazos, dana, tmp_path, monkeypatch):
    """`BR-BIL-026`: *"a reprint renders the pinned version forever"*.

    ⚠ **THIS TEST'S FIRST DRAFT COULD NOT FAIL, AND THE RED PROOF IS WHAT FOUND
    IT** (hard-won law 7 earning its place). It pinned the bill to version 1 and
    asserted the renderer was asked for 1 — and `documents.LAYOUTS` holds
    exactly ONE layout, so `LATEST_REGISTERED_VERSION` **is** 1: the sabotage
    that made this module render "on latest" changed nothing and the test went
    GREEN over it. A pin and a latest that are the same number prove nothing.

    So it is written twice over, and both halves have to hold:

      1. **The bill is pinned to version 3**, which is not the latest and is not
         the built-in, and the renderer is asked for **3**. A module that read
         `LATEST_REGISTERED_VERSION` would be asked for 1 and fail here.
      2. **`render_invoice` is called with NO template argument at all**, which
         is the property the rule actually depends on: `documents._pinned` takes
         the pin off the invoice row precisely when the caller supplies nothing,
         and a caller that "helpfully" passed a version would be refused by it
         the day the two disagree.
    """
    versions_asked = []
    kwargs_passed = []
    original_layout = documents._layout_for
    original_render = documents.render_invoice

    def watched_layout(template_version, template_id=None):
        versions_asked.append(template_version)
        return original_layout(template_version, template_id)

    def watched_render(invoice, **kwargs):
        kwargs_passed.append(dict(kwargs))
        return original_render(invoice, **kwargs)

    monkeypatch.setattr(documents, "_layout_for", watched_layout)
    monkeypatch.setattr(documents, "render_invoice", watched_render)

    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000060", template_version=3)
        result = build([bill], tmp_path)

    assert result.pdf_count == 1
    assert versions_asked == [3]
    assert documents.LATEST_REGISTERED_VERSION != 3, (
        "this test is only meaningful while the pinned version is NOT the latest "
        "registered one — that is the whole point of it"
    )
    assert kwargs_passed == [{}], (
        "print_set must call render_invoice with no template argument, so the "
        "invoice's own pin decides (BR-BIL-026)"
    )


def test_a_disagreeing_version_is_refused_by_the_pin(brazos, dana):
    """The other half of `BR-BIL-026`, and the reason nothing here passes a version.

    `render_invoice` is called with NO template argument precisely so the pin
    decides. This asserts what would happen if a later lane "helpfully" passed
    today's version: a refusal, not a re-render.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000070", template_version=1)
        with pytest.raises(BillingRuleError) as refusal:
            documents.render_invoice(bill, template_version=9)
    assert "pinned" in str(refusal.value)


def test_two_runs_of_the_same_set_produce_the_same_pages(brazos, dana, tmp_path):
    """A reprint next year must be byte-identical in content (`BR-BIL-030`).

    The renderer is deterministic by design — no `/Info` dates, a content hash
    for `/ID` — and this is the check that keeps it that way through THIS
    module: two independent sets over one bill, compared byte for byte.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000080")
        build([bill], tmp_path, name="first.zip")
        build([bill], tmp_path, name="second.zip")
        _, _, first, _ = read_archive(tmp_path / "first.zip")
        _, _, second, _ = read_archive(tmp_path / "second.zip")

    assert list(first) == [f"{print_set.PDF_DIR}/BL-2608-000080.pdf"]
    assert first == second


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · THE PAGE COUNT — counted, never estimated
# ══════════════════════════════════════════════════════════════════════════
def test_the_manifest_page_count_is_the_pages_the_pdf_actually_has(brazos, dana, tmp_path):
    """Three independent answers to *"how long is this bill?"*, all equal.

    The renderer's own `pdf_page_count`, the count parsed out of the archived
    bytes, and the figure written into the manifest. If any two of those can
    disagree, a mail house is quoted for the wrong number of pages.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000090")
        rendered = documents.render_invoice(bill)
        build([bill], tmp_path)
        manifest, _, pdfs, _ = read_archive(tmp_path / "set.zip")

    archived = pdfs[f"{print_set.PDF_DIR}/BL-2608-000090.pdf"]
    row = manifest_row_for(manifest, "BL-2608-000090")
    assert rendered.pdf_page_count > 0
    assert print_set.page_count_of(archived) == rendered.pdf_page_count
    assert row["page_count"] == str(rendered.pdf_page_count)


def test_a_page_count_that_cannot_be_read_is_none_and_never_zero(brazos):
    """`page_count_of` REFUSES rather than guessing. A mail house quotes on pages."""
    assert print_set.page_count_of(b"") is None
    assert print_set.page_count_of(b"not a pdf at all") is None
    assert print_set.page_count_of(b"%PDF-1.4\n<< /Type /Pages /Count 0 >>") is None
    assert print_set.page_count_of(b"%PDF-1.4\n<< /Type /Pages /Kids [] /Count 3 >>") == 3
    # The fallback path: a page tree that declares no /Count.
    assert print_set.page_count_of(b"<< /Type /Page >> << /Type /Page >>") == 2


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · RULE 31 — no database id is the visible value of a field
# ══════════════════════════════════════════════════════════════════════════
def test_no_uuid_appears_anywhere_in_the_manifest_or_a_filename(brazos, dana, tmp_path):
    """B14 rule 31, PO 2026-08-30: *"no Databse ID on screen - that is a rule"*.

    A print manifest is read by a vendor's operator and by a clerk chasing a
    returned envelope, so it is exactly a screen. Asserted by REGEX over the
    whole file rather than per column: a uuid that appeared in a column nobody
    thought to check is the way this rule is actually broken (`DEF-2716`).
    """
    uuid_re = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000100")
        build([bill], tmp_path)
        manifest, held, pdfs, readme = read_archive(tmp_path / "set.zip")

    flat = "\n".join(",".join(row) for row in manifest + held) + readme
    assert uuid_re.search(flat) is None
    assert all(uuid_re.search(name) is None for name in pdfs)


def test_a_bill_with_no_number_is_held_rather_than_named_by_its_id(brazos, dana, tmp_path):
    """The rule-31 case with teeth: the uuid is RIGHT THERE and is not used."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no=None)
        result = build([bill], tmp_path)
        manifest, _, pdfs, _ = read_archive(tmp_path / "set.zip")

    assert result.manifest_rows == 0
    assert pdfs == {}
    assert result.held[0].reason_code == print_set.HELD_NO_BILL_NUMBER
    assert str(bill.pk) not in "\n".join(",".join(row) for row in manifest)
    assert print_set.pdf_filename_for(None) is None
    assert print_set.pdf_filename_for("../../etc/passwd") is None
    assert print_set.pdf_filename_for("BL-2608-000001") == "BL-2608-000001.pdf"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · CLAUSE (c) — no mail standard is claimed, and the absence is stated
# ══════════════════════════════════════════════════════════════════════════
def test_the_archive_claims_no_mail_standard_it_does_not_perform(brazos, dana, tmp_path):
    """`BR-NOT-029` (c), and hard-won law 1 read forwards.

    Two assertions, and the second is the one that matters: the README does not
    merely avoid the word *certified* — it says in plain words that we did not
    do it, because a vendor's default assumption is the failure mode.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        bill = a_printable_bill(brazos, account, invoice_no="BL-2608-000110")
        build([bill], tmp_path)
        manifest, _, _, readme = read_archive(tmp_path / "set.zip")

    flat = "\n".join(",".join(row) for row in manifest).lower()
    for claim in ("cass", "ncoa", "barcode", "certified", "standardis", "standardiz"):
        assert claim not in flat, f"the manifest must not use the word {claim!r}"

    assert "NOT been CASS-certified" in readme
    assert "NOT been NCOA-processed" in readme
    assert "No Intelligent Mail barcode" in readme
    assert "only when the account holder tells us" in readme


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · THE SELECTION — issued and paid, never a draft, never a void
# ══════════════════════════════════════════════════════════════════════════
def test_only_bills_that_have_a_document_are_selected(brazos, dana):
    """A draft has no pin and cannot render; a void bill must never be posted."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        issued = a_printable_bill(brazos, account, invoice_no="BL-2608-000120")
        paid = a_printable_bill(
            brazos, account, invoice_no="BL-2608-000121", status=billing_models.INVOICE_PAID
        )
        a_printable_bill(
            brazos,
            account,
            invoice_no="BL-2608-000122",
            status=billing_models.INVOICE_DRAFT,
            template_version=None,
        )
        a_printable_bill(
            brazos, account, invoice_no="BL-2608-000123", status=billing_models.INVOICE_VOID
        )

        chosen = {row.invoice_no for row in print_set.print_set_selection({})}
        # A caller asking for drafts gets the printable set anyway — the filter
        # is OVERRIDDEN, because honouring it would produce an empty archive
        # that reads like a broken renderer.
        forced = {row.invoice_no for row in print_set.print_set_selection({"status": "draft"})}

    assert chosen == {issued.invoice_no, paid.invoice_no}
    assert forced == chosen
    assert len(chosen) == 2 > 0


def test_the_selection_honours_the_bills_lists_own_filters(brazos, dana):
    """`bill_run_id` / `cycle_id` are `selectors.INVOICE_FILTERS` members already,
    which is what makes *"every bill in a cycle"* a filter and not a new idea."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        mine = a_printable_bill(brazos, account, invoice_no="BL-2608-000130", account_id=account.id)
        other = an_account(brazos, dana, account_no="A-20000", label="Unit B")
        a_printable_bill(brazos, other, invoice_no="BL-2608-000131")

        picked = {
            row.invoice_no for row in print_set.print_set_selection({"account_id": str(account.id)})
        }
    assert picked == {mine.invoice_no}
    assert len(picked) == 1 > 0


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · SCALE — the ceiling refuses at the door
# ══════════════════════════════════════════════════════════════════════════
def test_an_oversized_set_is_refused_before_a_page_is_drawn(settings):
    """A limit discovered half way through is a crash with an archive behind it.

    The refusal names the count, the ceiling and the TIME — the only form of the
    number a clerk can act on — and it names the two ways a set is made smaller.
    """
    settings.BILLING_MAX_BILLS_PER_PRINT_SET = 100
    assert print_set.max_bills_per_print_set() == 100
    assert print_set.refuse_if_oversized(100) == 100
    with pytest.raises(BillingRuleError) as refusal:
        print_set.refuse_if_oversized(41_000)
    said = str(refusal.value)
    assert "41,000" in said and "100" in said
    assert "minute" in said
    assert "bill run" in said

    # Hard-won law 3: the unsafe option is the one you type.
    settings.BILLING_MAX_BILLS_PER_PRINT_SET = 0
    assert print_set.refuse_if_oversized(41_000) == 41_000


def test_the_ceiling_matches_the_bill_runs_own(brazos):
    """A print set cannot exceed the run that produced the bills, so a tighter
    ceiling here could only refuse a set for bills we were happy to create."""
    from apps.billing import run_jobs

    assert print_set.MAX_BILLS_PER_PRINT_SET_DEFAULT == run_jobs.MAX_ACCOUNTS_PER_RUN_DEFAULT


def test_the_job_rides_billings_own_queue(brazos):
    """PO 2026-08-31: *"billing will need its own named workers"*. A print set
    over a whole cycle is the shape of work that ruling was about."""
    from core import jobs as core_jobs
    from apps.billing import run_jobs

    assert core_jobs.job_handler(print_set.PRINT_SET_JOB) is print_set.run_print_set_job
    assert core_jobs.job_queue(print_set.PRINT_SET_JOB) == run_jobs.BILLING_QUEUE


def test_the_archive_is_downloadable_through_the_platform_route(brazos):
    """Hard-won law 2 in one line: without this registration the archive is
    written and no route will serve it."""
    from apps.tenancy import exports as export_kernel

    assert print_set.PRINT_SET_JOB in export_kernel.downloadable_kinds()


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · ONE BROKEN BILL NEVER COSTS THE SET ITS POST (BR-BIL-055)
# ══════════════════════════════════════════════════════════════════════════
def test_a_bill_that_cannot_render_is_held_and_the_others_still_print(
    brazos, dana, tmp_path, monkeypatch
):
    """A break in one bill is one named break, never five hundred lost envelopes."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        good = a_printable_bill(brazos, account, invoice_no="BL-2608-000140")
        broken = a_printable_bill(brazos, account, invoice_no="BL-2608-000141")

        real = documents.render_invoice

        def sometimes(invoice, **kwargs):
            if invoice.invoice_no == "BL-2608-000141":
                raise BillingRuleError("this bill's layout refused it")
            return real(invoice, **kwargs)

        monkeypatch.setattr(documents, "render_invoice", sometimes)
        result = build([good, broken], tmp_path)
        manifest, held, pdfs, _ = read_archive(tmp_path / "set.zip")

    assert result.pdf_count == 1 > 0
    assert manifest_row_for(manifest, "BL-2608-000140") is not None
    assert manifest_row_for(manifest, "BL-2608-000141") is None
    assert result.held[0].bill_no == "BL-2608-000141"
    assert result.held[0].reason_code == print_set.HELD_DOCUMENT_REFUSED
    assert any(row[1] == "BL-2608-000141" for row in held[1:])


def test_the_readme_states_what_the_run_produced(brazos, dana, tmp_path):
    """The counts a HUMAN needs live here, and not as a fifteenth manifest column."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        a_mailing_address(brazos, account)
        first = a_printable_bill(brazos, account, invoice_no="BL-2608-000150")
        second = a_printable_bill(brazos, account, invoice_no=None)
        result = build([first, second], tmp_path)
        _, _, _, readme = read_archive(tmp_path / "set.zip")

    assert "Bills considered: 2" in readme
    assert "Bills in this set: 1" in readme
    assert "PDF files: 1" in readme
    assert "Bills held back: 1" in readme
    assert f"Total pages: {result.page_total}" in readme
    assert result.page_total > 0


def test_the_archive_filename_uses_the_callers_instant_not_a_clock(brazos):
    """`BR-TEN-043` / gate G6 — there is no `timezone.now()` under `apps/billing/`."""
    with tenant_ctx(brazos):
        name = print_set.archive_filename(brazos.id, period="2026-07", generated_at=GENERATED_AT)
    assert name.endswith(".zip")
    assert "bills-print" in name
    assert "2026-07" in name
    assert "20260831T1405" in name or "20260831T" in name
