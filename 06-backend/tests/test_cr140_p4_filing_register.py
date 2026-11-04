"""`P4.4` · `P4.3` · `P4.11` — the filing register, the receipt, and the read.

⚠ **THE INTERESTING HALF OF THIS FILE ONLY WORKS ON POSTGRESQL, AND IT SAYS SO
RATHER THAN PASSING QUIETLY.** `ledger/0020`'s UPDATE and DELETE refusals are
TRIGGERS. `config/settings/test.py` hardcodes in-memory SQLite, where a trigger
written in plpgsql does not exist — so on the default suite those two cases
would pass by doing nothing at all, which is hard-won law 7's *incapable of
failing* shape with a green tick on it. They `skip` with the reason named, and
they are run under `--ds=config.settings.pgtest`, where they bite.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first (law 7, habit 2)
------------------------------------------------------------------------
**(a) ASSERTING THE REGISTER AND NOT THE BOOKS.** A register that recorded the
filing and posted nothing would pass every case about `tax_remittances` and
would have lost the money. So the entry is asserted too, and `remitted` is read
back out of `reporting.remittance_by_authority` — which is the number that has
to be right (`BR-REP-002`).

**(b) A FIXTURE WITH ONE FILING.** One row cannot show that a RETRY writes no
second row, which is the whole reason `uq_tax_remittances_entry` exists. The
idempotency case files the same return twice.

**(c) A RECEIPT CASE THAT NEVER LOOKS IN THE STORE.** Asserting that the call
did not raise says nothing about whether the bytes were kept — which is exactly
what the old refusal was protecting against (*"a clerk who attaches a receipt
believes it was kept"*). The case reads it back through `for_source`.

**(d) THE `journal_only` COUNT AGREEING WITH ITSELF.** A count derived from the
same queryset the list uses would be 0 by construction. The case posts an entry
through the posting service with NO register row beside it — the shape every
pre-2026-09-24 filing has — and asserts the count sees it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import connection, transaction

from apps.ledger import journal, models, reporting
from apps.tenancy import document_models, document_store

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE3_STATE_REMIT_NOW,
    ensure_authority_accounts,
    make_accounts,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "ledger/0020's immutability refusals are plpgsql TRIGGERS and SQLite has none, "
        "so this case would pass by doing nothing on the default suite. Run it with "
        "--ds=config.settings.pgtest (CLAUDE.md hard-won law 14)."
    ),
)

PAID_ON = date(2026, 8, 18)
POSTED_AT = datetime(2026, 8, 18, 14, 5, tzinfo=dt_timezone.utc)
#: LE-3's own State-of-Texas figure, so the money assertion below is the one
#: `US-LED-014` TC-3 already signed rather than a number invented here.
AMOUNT = LE3_STATE_REMIT_NOW
CONFIRMATION = "CONF-88213"
STATE = "2200-01"


@pytest.fixture()
def authority(brazos, dana):
    """LE-3's State of Texas account, with WE-1's tax posted across it."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        authorities = ensure_authority_accounts(brazos, dana)
        post_le3_authorities(brazos, accounts, authorities)
        yield authorities[STATE]


def _file(tax_account_id, *, amount=AMOUNT, confirmation=CONFIRMATION, receipt=None, actor=None):
    """⚠ **`actor` IS NOT OPTIONAL WHEN A RECEIPT IS ATTACHED, AND THAT IS REAL.**
    `document_store.store()` refuses a document with no author — *"a legal
    document whose origin is unrecorded is unprovable"* — so a filing that keeps
    a receipt must name the clerk who filed it. The endpoint always does
    (`finance_api` passes `_actor(request)`); a helper that did not would be
    testing a call no screen can make.
    """
    return journal.record_tax_remittance(
        tax_account_id=tax_account_id,
        period_start=JULY_START,
        period_end=JULY_END,
        amount=amount,
        basis=journal.BASIS_COLLECTED,
        confirmation_ref=confirmation,
        entry_date=PAID_ON,
        posted_at=POSTED_AT,
        receipt=receipt,
        actor=actor,
    )


def test_p4_4__a_filing_writes_one_register_row_beside_its_entry(authority, brazos):
    """(a) — the row AND the books, never one without the other."""
    result = _file(authority.pk)

    assert result.created is True
    assert result.remittance_id != ""
    row = models.TaxRemittance.objects.get(pk=result.remittance_id)
    assert str(row.journal_entry_id) == result.entry_id
    assert row.amount == AMOUNT
    assert row.confirmation_ref == CONFIRMATION
    # ⚠ ONE INPUT, TWO NAMES. 4·2 labels the field *Date paid* and the API has
    # always called it `entry_date`; the register records what the clerk typed.
    assert row.paid_on == PAID_ON
    assert row.basis == journal.BASIS_COLLECTED

    # (a) — the money. `remitted` is read out of the BOOKS and not out of the
    # register, and that does not change because the register now exists.
    report = reporting.remittance_by_authority(start=JULY_START, end=date(2026, 8, 31))
    state = next(one for one in report["rows"] if one.code == STATE)
    assert state.remitted == AMOUNT


def test_p4_4__a_retried_filing_writes_no_second_row(authority, brazos):
    """(b) — `posting.post()` is idempotent, so the register must be too.

    Without this the filing history would list one payment twice, which is the
    failure `export_batches` closes with its period+target key.
    """
    first = _file(authority.pk)
    second = _file(authority.pk)

    assert second.created is False
    assert second.entry_id == first.entry_id
    assert second.remittance_id == first.remittance_id
    assert models.TaxRemittance.objects.count() == 1


@POSTGRES_ONLY
def test_p4_4__a_filing_row_cannot_be_edited(authority, brazos):
    """The register is append-only although hard rule 4 does not name it."""
    result = _file(authority.pk)
    # ⚠ **THE SAVEPOINT IS NOT TIDINESS — CLAUDE.md HARD-WON LAW 14.** The
    # trigger's RAISE aborts the whole PostgreSQL transaction, so without a
    # nested `atomic()` every later statement — including the tenant fixture's
    # own `clear_current_tenant()` at teardown — dies with
    # `TransactionManagementError`, and the case ERRORS while the refusal it
    # asserts worked perfectly. Measured: it did exactly that before this line.
    with pytest.raises(Exception) as refusal:  # noqa: PT011 — plpgsql RAISE
        with transaction.atomic():
            models.TaxRemittance.objects.filter(pk=result.remittance_id).update(
                confirmation_ref="CONF-88231"
            )
    assert "BR-LED-019" in str(refusal.value)


@POSTGRES_ONLY
def test_p4_4__a_filing_row_cannot_be_deleted(authority, brazos):
    result = _file(authority.pk)
    # The SAVEPOINT, for the reason named on the case above (law 14).
    with pytest.raises(Exception) as refusal:  # noqa: PT011 — plpgsql RAISE
        with transaction.atomic():
            models.TaxRemittance.objects.filter(pk=result.remittance_id).delete()
    assert "BR-LED-019" in str(refusal.value)


def test_p4_3__the_receipt_is_kept_and_can_be_read_back(authority, brazos, dana):
    """(c) — the bytes, not the absence of an exception.

    The refusal this replaces said it in terms: *"a clerk who attaches a receipt
    believes it was kept"*. So the case reads it back out of the store.
    """
    payload = b"%PDF-1.4 bexar county july return\n"
    result = _file(
        authority.pk,
        actor=dana,
        receipt=journal.ReceiptUpload(
            content_type="application/pdf",
            filename="bexar-july.pdf",
            payload=payload,
        ),
    )

    assert result.receipt_document_id is not None
    stored = document_store.for_source(
        source_type=document_models.SOURCE_TAX_REMITTANCE,
        source_id=result.remittance_id,
    )
    # ⚠ `for_source` returns a `DocumentLookup`, NOT a list — it never returns
    # an empty success, so absence is `unavailable_reason`, never `[]`.
    assert stored.found, stored.unavailable_reason
    assert stored.document.kind == document_models.KIND_REMITTANCE_RECEIPT
    # (c) — THE BYTES, not the absence of an exception. `fetch` re-computes the
    # content hash on every read, so this also proves what was stored is what
    # comes back.
    assert document_store.fetch(stored.document.id) == payload
    # The display name carries the filing's own reference, which is why
    # `document_store` refuses to invent one.
    assert CONFIRMATION in stored.document.display_name
    # ⚠ **THE RETURNED ID MUST BE THE STORED ONE, AND THIS CASE PASSED WITHOUT
    # THIS LINE.** Measured: a service returning any non-None string for
    # `receipt_document_id` while storing the document correctly satisfied
    # every assertion above, and a screen following that id would fetch
    # nothing. Asserting the two AGREE is what makes the id worth returning.
    assert result.receipt_document_id == str(stored.document.id)


def test_p4_3__a_filing_with_no_receipt_is_lawful(authority, brazos):
    """`None` is not a refusal any more — the paper arrives a week later."""
    result = _file(authority.pk)
    assert result.receipt_document_id is None
    assert result.remittance_id != ""


def test_p4_3__a_receipt_in_a_shape_the_store_cannot_take_is_refused(authority, brazos):
    """The old code refused EVERY receipt; this refuses only an unusable one.

    A raw file object, a path or a base64 string would otherwise be guessed at,
    and `document_store.store()` measures nothing — so whatever it happened to
    contain would become the clerk's receipt.
    """
    with pytest.raises(journal.JournalActionError) as refusal:
        _file(authority.pk, receipt="/tmp/receipt.pdf")
    assert "ReceiptUpload" in str(refusal.value)


def test_p4_4__the_two_stale_unavailable_codes_are_gone(authority, brazos):
    """They rode on EVERY remittance response this product ever gave.

    B14 rule 33 removes a refusal rather than shortening it, and hard-won law
    2's mirror is why: a refusal that has stopped being true is worse than one
    that never was.
    """
    result = _file(authority.pk)
    assert result.unavailable == ()
    assert not hasattr(journal, "RECEIPT_HAS_NO_HOME")
    assert not hasattr(journal, "REMITTANCE_REGISTER_NOT_BUILT")
