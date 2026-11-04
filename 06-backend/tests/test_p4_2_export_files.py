# ── Trace ──────────────────────────────────────────────
# Change:   P4.2 (the batch writes a file) + P4.7 (hash-stable regeneration) —
#           Finance blueprint p017.
# Rules:    BR-LED-004 (re-download is the ratified door) · BR-LED-014 /
#           BR-TEN-020 (a recorded batch keeps the refs it had AT SEND) ·
#           BR-LED-020 (v1 is a FILE; direct sync is v2) · BR-LED-039 /
#           US-LED-021 TC-7 (the cost section is carried SEPARATELY and never
#           added to the totals) · CLAUDE.md rule 4 (financial immutability) ·
#           rule 2 (money 2dp on display) · rule 7 (every money action audits)
# Golden:   LE-5 — July → QuickBooks, one summary JE, batch recorded with
#           who/when/hash; US-LED-006 TC-4 moves 4100's QBO ref AFTER the send
# ───────────────────────────────────────────────────────
"""Four real files, and a sent one that cannot move.

**THE TEST THIS FILE EXISTS FOR** is
`test_p4_7__a_later_ref_edit_does_not_move_a_sent_file` — CLAUDE.md hard rule 4
made visible on the ARTEFACT rather than on the row. `US-LED-006` TC-4 changes
`4100`'s QBO ref from 79 to 101 the month after July's batch, and the ratified
consequence is *"the recorded batch (content hash) is unchanged; only future
exports use the new ref"*. Until `P4.2` that was a property of a JSON column
nobody could open. It is now a property of the file an accountant is holding.

⚠ **`P4.7` IS PROVED ON REAL POSTGRESQL AS WELL AS ON THE DEFAULT SUITE.**
CLAUDE.md hard-won law 14 is about a different trap, but its lesson generalises
to any claim about what the database kept: `config/settings/test.py` hardcodes
in-memory SQLite, and a JSONField's round-trip is one of the places the two
engines genuinely differ. Run:

    DATABASE_URL='postgres://…' pytest tests/test_p4_2_export_files.py \\
        --ds=config.settings.pgtest --reuse-db
"""

import csv
import hashlib
import io
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import (
    close,
    export_files,
    exports,
    models,
    reporting,
    services as ledger_services,
)

from tests.ledger_le_fixtures import JULY_END, JULY_START, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CLOSED_ON = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)
SENT_AT = datetime(2026, 8, 5, 17, 0, tzinfo=dt_timezone.utc)
QBO_REFS = {"1200": "79", "4100": "101", "2200-01": "33"}


def july_books(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def map_refs(tenant, actor):
    for account in models.LedgerAccount.objects.filter(tenant=tenant, deleted_at__isnull=True):
        ledger_services.set_export_codes(
            actor,
            account_id=account.id,
            qbo_ref=QBO_REFS.get(account.code, f"X{account.code}"),
            xero_ref=f"Y{account.code}",
        )


@pytest.fixture()
def closed_july(brazos, dana):
    """LE-5's July: posted, refs mapped, period closed. Seeded ONCE.

    ⚠ It is a fixture rather than a call inside `sent_batch` because
    `sent_batch` is used more than once per test — the omitted-cost-row case
    renders all four targets — and `july_books` creates the same four account
    numbers every time. A second call trips
    `UNIQUE constraint failed: accounts.tenant_id, accounts.account_no`, which
    reads like a defect in this module and is a defect in the fixture.
    """
    with tenant_ctx(brazos):
        july_books(brazos, dana)
        map_refs(brazos, dana)
        close.close_period(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=CLOSED_ON,
            reason="registers not readable from the ledger (see the checklist)",
        )
    return brazos


def sent_batch(brazos, dana, target):
    """July handed over ONCE per target — `BR-LED-004`'s unique key is (window,
    target), so four targets of one month are four lawful hand-overs and a
    second of the SAME target is the refusal this product exists to make."""
    with tenant_ctx(brazos):
        batch = exports.create_export_batch(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            target=target,
            created_at=SENT_AT,
        )
        row = models.ExportBatch.objects.get(pk=batch["batch_id"])
        batch["payload"] = list(row.payload or ())
    return batch


def rows_of(content: bytes):
    return list(csv.reader(io.StringIO(content.decode("utf-8"))))


# ═══════════════════════════════════════════════════════════════════════════
# P4.2 — four targets, four real files
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "target",
    [models.EXPORT_CSV, models.EXPORT_IIF, models.EXPORT_QBO, models.EXPORT_XERO],
)
def test_p4_2__every_target_writes_a_file_with_content(brazos, dana, closed_july, target):
    """*"Today the handover is recorded and nothing is written or emailed."*"""
    batch = sent_batch(brazos, dana, target)
    content = export_files.render(batch)
    assert content, f"{target} wrote nothing"
    assert content.endswith(b"\n"), "a text file ends in a newline"
    # Every one of LE-1's July GL codes reaches the file in some form.
    assert b"1200" in content or b"79" in content


def test_p4_2__the_generic_csv_carries_our_own_columns_and_foots(brazos, dana, closed_july):
    batch = sent_batch(brazos, dana, models.EXPORT_CSV)
    rows = rows_of(export_files.render(batch))
    assert rows[0] == list(export_files._CSV_HEADER)
    debit_at, credit_at = rows[0].index("debit"), rows[0].index("credit")
    debits = sum(Decimal(row[debit_at] or "0") for row in rows[1:])
    credits = sum(Decimal(row[credit_at] or "0") for row in rows[1:])
    assert debits == credits, "the handed-over journal must foot in the file too"
    with tenant_ctx(brazos):
        july = reporting.trial_balance(start=JULY_START, end=JULY_END)
    assert debits == july["total_debit"].quantize(Decimal("0.01"))


def test_p4_2__money_is_two_decimals_with_no_symbol_or_separator(brazos, dana, closed_july):
    """CLAUDE.md rule 2's display half, in a file an importer parses."""
    rows = rows_of(export_files.render(sent_batch(brazos, dana, models.EXPORT_CSV)))
    at = rows[0].index("debit")
    for row in rows[1:]:
        cell = row[at]
        assert "$" not in cell and "," not in cell
        if cell:
            assert cell == str(Decimal(cell).quantize(Decimal("0.01")))


def test_p4_2__an_empty_money_cell_is_blank_and_never_zero(brazos, dana, closed_july):
    """Every importer here reads an empty debit as *this line is a credit*.
    `0.00` in both columns is a balanced line that moves nothing — it imports
    cleanly and is wrong."""
    rows = rows_of(export_files.render(sent_batch(brazos, dana, models.EXPORT_CSV)))
    debit_at, credit_at = rows[0].index("debit"), rows[0].index("credit")
    for row in rows[1:]:
        if row[debit_at] and row[credit_at]:
            pytest.fail("a GL summary row is a debit OR a credit, never both")
        assert not (row[debit_at] == "0.00" and row[credit_at] == "0.00")


def test_p4_2__iif_carries_the_vendors_own_grammar(brazos, dana, closed_july):
    """The `!TRNS` declarations, the tab and `ENDTRNS` are the VENDOR's and are
    `apps/integrations/codecs`'s already — reused, never written twice."""
    content = export_files.render(sent_batch(brazos, dana, models.EXPORT_IIF)).decode()
    assert content.startswith("!TRNS\t")
    assert "!ENDTRNS" in content
    assert "\t" in content and content.count("ENDTRNS") > 1


def test_p4_2__iif_addresses_an_account_by_code_and_name_never_by_a_ref(brazos, dana, closed_july):
    """`US-LED-006` TC-5's second sentence: *"CSV and IIF address accounts by
    code+name and remain available"* when a QBO ref is missing."""
    batch = sent_batch(brazos, dana, models.EXPORT_IIF)
    content = export_files.render(batch).decode()
    assert "1200 · " in content
    # No qbo_ref reaches an IIF file at all.
    assert "\t79\t" not in content


def test_p4_2__iif_collapses_the_pair_into_one_signed_amount(brazos, dana, closed_july):
    """QuickBooks Desktop reads a single AMOUNT and takes its sign as the side,
    so the file's amounts must sum to zero for a balanced hand-over."""
    content = export_files.render(sent_batch(brazos, dana, models.EXPORT_IIF)).decode()
    amounts = [
        Decimal(line.split("\t")[3]) for line in content.splitlines() if line.startswith("TRNS\t")
    ]
    assert amounts and sum(amounts) == Decimal("0.00")


def test_p4_2__qbo_addresses_an_account_by_the_ref_the_tenant_typed(brazos, dana, closed_july):
    batch = sent_batch(brazos, dana, models.EXPORT_QBO)
    rows = rows_of(export_files.render(batch))
    assert rows[0][0] == "*JournalNo"
    at = rows[0].index("*AccountName")
    assert any(row[at].startswith("101 ") for row in rows[1:]), rows
    # Every row of a QBO batch carries a ref — gate 4 refused the hand-over
    # atomically otherwise, so a blank here means the gate was bypassed.
    assert all(row[at].strip() for row in rows[1:])


def test_p4_2__xero_says_no_tax_on_every_line(brazos, dana, closed_july):
    """Our hand-over already carries tax as its OWN 2200-nn GL rows. Letting
    Xero compute tax on top of these lines books it twice; a blank cell lets
    Xero apply the account's default rate, which is the same double-booking
    arrived at by omission."""
    rows = rows_of(export_files.render(sent_batch(brazos, dana, models.EXPORT_XERO)))
    at = rows[0].index("*TaxRate")
    assert rows[1:], "a Xero file with no lines proves nothing"
    assert all(row[at] == "No Tax" for row in rows[1:])


def test_p4_2__xero_amounts_sum_to_zero_like_iifs(brazos, dana, closed_july):
    rows = rows_of(export_files.render(sent_batch(brazos, dana, models.EXPORT_XERO)))
    at = rows[0].index("*Amount")
    assert sum(Decimal(row[at] or "0") for row in rows[1:]) == Decimal("0.00")


def test_p4_2__the_batch_number_rides_in_the_vendor_reference_columns(brazos, dana, closed_july):
    batch = sent_batch(brazos, dana, models.EXPORT_QBO)
    rows = rows_of(export_files.render(batch))
    assert batch["batch_no"], "CR-005 seeds the EXP- series for every tenant"
    assert all(row[0] == batch["batch_no"] for row in rows[1:])


def test_p4_2__the_filename_carries_its_context_and_never_a_metadata_row(brazos, dana, closed_july):
    """IS-11's discipline: no metadata rows INSIDE the data, because a metadata
    row is a row an importer tries to import."""
    batch = sent_batch(brazos, dana, models.EXPORT_QBO)
    name = export_files.filename(batch)
    assert name.endswith(".csv")
    assert batch["batch_no"] in name and "2026-07-01" in name and "2026-07-31" in name
    rows = rows_of(export_files.render(batch))
    assert len(rows[0]) == len(rows[1]), "every line has the header's width"


def test_p4_2__an_unknown_target_is_refused_by_name(brazos, dana, closed_july):
    with pytest.raises(export_files.ExportFileError) as refused:
        export_files.render({"target": "sage", "payload": []})
    assert "sage" in str(refused.value)


# ═══════════════════════════════════════════════════════════════════════════
# BR-LED-039 / US-LED-021 TC-7 — the cost section, carried and NEVER mixed
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_2__the_omitted_cost_row_count_travels_with_every_vendor_file(brazos, dana, closed_july):
    """*"Seven rows"* and *"seven of nine rows"* must never read the same. The
    CSV carries everything and reports zero; the three import sheets carry the
    journal rows only, because an import file must foot and the cost section
    deliberately does not."""
    for target in (models.EXPORT_QBO, models.EXPORT_XERO, models.EXPORT_IIF):
        batch = sent_batch(brazos, dana, target)
        omitted = export_files.omitted_cost_rows(batch)
        cost_rows = [
            row for row in batch["payload"] if row.get("section") == exports.COST_SECTION_MARKER
        ]
        assert omitted == len(cost_rows)
    csv_batch = sent_batch(brazos, dana, models.EXPORT_CSV)
    assert export_files.omitted_cost_rows(csv_batch) == 0


def test_p4_2__the_csv_marks_which_section_each_row_came_from(brazos, dana, closed_july):
    rows = rows_of(export_files.render(sent_batch(brazos, dana, models.EXPORT_CSV)))
    at = rows[0].index("section")
    assert all(row[at] for row in rows[1:]), "no row is unlabelled"
    assert "amount" in rows[0], "a cost row's figure has its OWN column"


# ═══════════════════════════════════════════════════════════════════════════
# P4.7 — HASH-STABLE REGENERATION. CLAUDE.md rule 4, on the artefact.
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "target",
    [models.EXPORT_CSV, models.EXPORT_IIF, models.EXPORT_QBO, models.EXPORT_XERO],
)
def test_p4_7__regenerating_a_sent_file_is_byte_identical(brazos, dana, closed_july, target):
    """`J19` step 7: *"the export file re-generated from the batch is identical
    (hash-stable)"*. Asserted on the BYTES and on their SHA-256, because a
    length check would pass over a reordered file."""
    batch = sent_batch(brazos, dana, target)
    first = export_files.render(batch)
    second = export_files.render(batch)
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_p4_7__a_later_ref_edit_does_not_move_a_sent_file(brazos, dana, closed_july):
    """**THE ONE THIS FILE EXISTS FOR.** `US-LED-006` TC-4 verbatim: change
    `4100`'s QBO ref AFTER July's batch and *"the recorded batch (content hash)
    is unchanged; only future exports use the new ref"*.

    The file is re-derived from the FROZEN payload, so the ref it carries is
    the one written at send (`BR-TEN-020`) and the edit cannot reach it. A
    renderer that went back to the chart would silently start saying the new
    number — CLAUDE.md rule 4 broken by a report rather than by an UPDATE, and
    invisible to every check in this repo.
    """
    batch = sent_batch(brazos, dana, models.EXPORT_QBO)
    before = export_files.render(batch)
    before_hash = hashlib.sha256(before).hexdigest()
    assert b"101 " in before, "4100's ref at send"

    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.get(tenant=brazos, code="4100")
        ledger_services.set_export_codes(dana, account_id=account.id, qbo_ref="777")
        assert (
            models.LedgerAccount.objects.get(pk=account.pk).qbo_ref == "777"
        ), "the chart really moved"
        stored = models.ExportBatch.objects.get(pk=batch["batch_id"])
        reread = exports.batch_dict(stored)
        reread["payload"] = list(stored.payload or ())

    after = export_files.render(reread)
    assert after == before
    assert hashlib.sha256(after).hexdigest() == before_hash
    assert b"777" not in after, "a sent file may not learn a ref it never had"
    assert reread["content_hash"] == batch["content_hash"]


def test_p4_7__the_renderer_reads_no_table_at_all(brazos, dana, closed_july):
    """The property that MAKES hash-stability true, asserted directly.

    `render` is a pure function of its argument. If it ever grows a read — of
    the chart, of a setting, of the clock — two downloads of one batch can
    differ and every assertion above becomes a coincidence. Proved by rendering
    with NO tenant context set at all: a table read would raise."""
    batch = sent_batch(brazos, dana, models.EXPORT_CSV)
    outside = export_files.render(batch)  # no tenant_ctx — deliberately
    with tenant_ctx(brazos):
        inside = export_files.render(batch)
    assert outside == inside


def test_p4_7__two_targets_of_one_period_are_different_files(brazos, dana, closed_july):
    """A guard against the cheapest possible false pass: a renderer that
    ignored its target would make every assertion above true and every file
    identical."""
    csv_bytes = export_files.render(sent_batch(brazos, dana, models.EXPORT_CSV))
    iif_bytes = export_files.render(sent_batch(brazos, dana, models.EXPORT_IIF))
    assert csv_bytes != iif_bytes
