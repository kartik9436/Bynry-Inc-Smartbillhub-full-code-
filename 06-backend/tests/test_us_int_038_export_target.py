# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-038 (EP-INT-10) TC-2 · TC-3 · TC-5 · TC-6 — outbound
#           refuses by name; camt.053 as a codec; the R02 boundary.
#           US-INT-033 (EP-INT-09) TC-2 · TC-5 — a period regenerated is the
#           same file or a refusal naming the first; `test()` writes a zero-row
#           export. US-INT-009 (the saved export target). Screens: S43 · S142
# Rules:    BR-INT-020 B · BR-INT-031 · BR-INT-033 · BR-INT-010 · BR-INT-019 ·
#           BR-INT-054 as amended 2026-09-06 · BR-LED-004 ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6 (idempotency)
# Tests:    this file. The PostgreSQL half — the append-only trigger and RLS —
#           is tests/test_us_int_038_export_target_pg.py
# Impacts:  apps/integrations/departures.py · adapters/accounting_file.py ·
#           manifests/accounting_file.py · codecs.py (iif encoder, camt053
#           decoder)
# ───────────────────────────────────────────────────────
"""US-INT-038 and US-INT-033's file-out half — a period goes out, goes out again, and is refused by name.

⚠ WHAT THIS FILE CAN AND CANNOT PROVE, SAID FIRST SO NOBODY TRUSTS IT FOR MORE
THAN IT IS WORTH (hard-won law 14). The refusal here is the SERVICE's, and the
service refuses on every vendor, so these cases are real. What SQLite cannot
express is the append-only trigger and RLS `FORCE`; the run row's immutability
and the tenant-isolation half live in the `_pg.py` companion and SKIP rather
than pass vacuously on this suite.

⚠ AND THE CONTROL CASE IS THE POINT, exactly as it was in wave I. *"Nothing
went out"* also describes a broken endpoint, so proving the duplicate refusal
means proving that a genuinely different window, and the same window to a
DIFFERENT target, are both still accepted in the same breath. A test that only
ever refuses cannot tell the two apart.
"""

from __future__ import annotations

from datetime import date

import pytest

from types import SimpleNamespace

from apps.integrations import codecs, departures, models, registry, services
from apps.integrations.adapters import ADAPTERS, accounting_file
from apps.integrations.adapters.base import ConnectionView
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

ACCOUNTING = "accounting_file"
EXPORT = "export_journal"

JULY = (date(2026, 7, 1), date(2026, 7, 31))
AUGUST = (date(2026, 8, 1), date(2026, 8, 31))


def _target(tenant, *, label="Month-end journal", destination="download", file_format="iif"):
    config = {"label": label, "destination": destination, "file_format": file_format}
    if destination == "drop":
        config.update(
            {"drop_host": "sftp.aclarian.example", "drop_username": "brazos", "drop_path": "/in"}
        )
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=ACCOUNTING,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config=config,
    )


def _view(connection):
    return ConnectionView(
        provider_key=connection.provider_key,
        environment=connection.environment,
        config=dict(connection.config or {}),
        label=connection.label,
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-033 TC-2 — July regenerated is the same handover or a refusal naming
#                   the first, and NEVER a second, different file.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_july_asked_for_twice_is_refused_naming_the_first_handover(brazos):
    """The second request is refused, and the sentence names the DATE.

    ⚠ IT ALSO ASSERTS THE ROW EXISTS FOR THE SECOND REQUEST, which is the half
    a reader skips. A refusal that left no row would make the second export
    invisible, and a utility asking *did my second July export do anything* is
    owed an answer. Two rows, one accepted and one `skipped`.
    """
    with tenant_ctx(brazos):
        connection = _target(brazos)
        first = departures.record_departure(
            connection=connection,
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="iif",
        )
        second = departures.record_departure(
            connection=connection,
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="iif",
        )

    assert first.accepted is True
    assert second.accepted is False
    assert second.duplicate_of is not None
    assert second.duplicate_of.id == first.run.id, "it names the FIRST, not the previous"
    assert second.export_key == first.export_key
    #: the row exists and says *we did not ask* — nothing was built, nothing left
    assert second.run.outcome == models.OUTCOME_SKIPPED
    assert "July was already exported on" in (second.run.summary or "")
    #: and both rows are there, so neither request is invisible
    with tenant_ctx(brazos):
        assert models.IntegrationRun.objects.filter(connection=connection).count() == 2


@pytest.mark.django_db
def test_tc2_control_a_different_window_and_a_different_target_are_both_accepted(brazos):
    """The control case. Refusing everything is not the behaviour under test."""
    with tenant_ctx(brazos):
        connection = _target(brazos)
        july = departures.record_departure(
            connection=connection,
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="iif",
        )
        august = departures.record_departure(
            connection=connection,
            operation=EXPORT,
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            target="iif",
        )
        #: the SAME July, to a DIFFERENT format — US-LED-016 TC-2's own reading:
        #: *QuickBooks and a generic CSV are two accountants, not one
        #: double-handover*.
        july_as_csv = departures.record_departure(
            connection=connection,
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="csv",
        )

    assert july.accepted is True
    assert august.accepted is True, "a different window is a different handover"
    assert july_as_csv.accepted is True, "a different target is a different handover"
    assert july.export_key != august.export_key != july_as_csv.export_key


@pytest.mark.django_db
def test_tc6_tenant_isolation_one_utility_s_july_never_refuses_another_s(brazos, lonestar):
    """The key is per TENANT and per CONNECTION, in that order (hard rule 1).

    Two utilities exporting their own July produce the SAME key — the key is a
    digest of a window and a format and knows nothing about who asked — and
    neither refuses the other. `tenant_id` is filtered explicitly as well as by
    RLS, which is the second guard for SQLite, where there is no RLS at all and
    a missing filter would pass every case in this suite.
    """
    with tenant_ctx(brazos):
        theirs = departures.record_departure(
            connection=_target(brazos),
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="iif",
        )
    with tenant_ctx(lonestar):
        ours = departures.record_departure(
            connection=_target(lonestar),
            operation=EXPORT,
            period_start=JULY[0],
            period_end=JULY[1],
            target="iif",
        )
    assert theirs.accepted is True
    assert ours.accepted is True, "another utility's July is not ours"
    assert theirs.export_key == ours.export_key, "the same key, scoped apart"


@pytest.mark.django_db
def test_a_utility_can_hold_only_one_saved_accounting_target_today(brazos):
    """⚠ A LIMITATION FOUND BY BUILDING THIS, ASSERTED SO NOBODY PLANS AROUND
    A CAPABILITY THAT IS NOT THERE — `DEF-INT-4245`.

    `uq_integration_connection_key_env` allows ONE connection per provider per
    environment, so *the QuickBooks target and the CSV copy for the auditor*
    that `US-LED-016` TC-2 describes cannot both be SAVED. The handover itself
    is unaffected — the control case above proves July still goes out as IIF
    and as CSV through one connection — so what is missing is the REMEMBERING,
    which is the thing this wave is named for. Widening that constraint touches
    every provider on a shared table and is not wave J's to do.
    """
    from django.db import IntegrityError

    with tenant_ctx(brazos):
        _target(brazos, label="Month-end journal")
        with pytest.raises(IntegrityError):
            _target(brazos, label="Auditor copy", file_format="csv")


def test_the_key_is_the_window_and_the_target_and_refuses_a_typed_date():
    """A string means a caller already chose a spelling, and two spellings of
    one July are two keys — the failure the type refuses."""
    key = departures.export_key(period_start=JULY[0], period_end=JULY[1], target="iif")
    assert key == departures.export_key(
        period_start=date(2026, 7, 1), period_end=date(2026, 7, 31), target="iif"
    )
    with pytest.raises(TypeError, match="already chose a spelling"):
        departures.export_key(period_start="2026-07-01", period_end=JULY[1], target="iif")
    with pytest.raises(ValueError, match="runs backwards"):
        departures.export_key(period_start=JULY[1], period_end=JULY[0], target="iif")


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-038 TC-2 — an outbound unregistered format is REFUSED BY NAME, with
#                   the list of what this connection offers.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_negative_xlsx_is_refused_by_name_with_the_four_that_exist(brazos):
    """*xlsx is not a registered format — QuickBooks, Xero, CSV, IIF*.

    Two halves and both are asserted, because a refusal missing either is the
    one people ship: the NAME asked for, so a clerk knows what was rejected,
    and the LIST, so they know what to type instead.
    """
    with tenant_ctx(brazos):
        connection = _target(brazos)
        with pytest.raises(departures.UnregisteredFormat) as raised:
            departures.record_departure(
                connection=connection,
                operation=EXPORT,
                period_start=JULY[0],
                period_end=JULY[1],
                target="xlsx",
            )

    message = str(raised.value)
    assert "xlsx is not a registered format" in message
    assert "QuickBooks, Xero, CSV, IIF" in message
    assert raised.value.message_key == departures.REFUSAL_UNREGISTERED_FORMAT


@pytest.mark.django_db
def test_tc2_the_refused_format_leaves_no_run_row_at_all(brazos):
    """⚠ THE ASYMMETRY WITH WAVE I, ASSERTED RATHER THAN COMMENTED.

    An arrival in a shape we cannot read is still an ARRIVAL and gets a row. A
    file we were asked to WRITE in a shape nobody registered was never a
    handover — there is nothing to record having happened. `BR-INT-031` in one
    line: inbound degrades, outbound refuses.
    """
    with tenant_ctx(brazos):
        connection = _target(brazos)
        with pytest.raises(departures.UnregisteredFormat):
            departures.record_departure(
                connection=connection,
                operation=EXPORT,
                period_start=JULY[0],
                period_end=JULY[1],
                target="xlsx",
            )
        assert models.IntegrationRun.objects.filter(connection=connection).count() == 0


@pytest.mark.django_db
def test_the_list_is_this_connection_s_four_and_not_every_codec_in_the_product(brazos):
    """Offering `bai2` to somebody exporting a journal is a worse answer than
    none, so the list comes off the manifest and not off `CODECS`."""
    with tenant_ctx(brazos):
        connection = _target(brazos)
        with pytest.raises(departures.UnregisteredFormat) as raised:
            departures.require_registered_format(connection=connection, asked="bai2")
    assert raised.value.offered == ("qbo", "xero", "csv", "iif")
    assert "bai2" not in str(raised.value).replace("bai2 is not a registered format", "")


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-033 TC-5 — `test()` writes a ZERO-ROW export and says what it wrote.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc5_test_on_a_download_target_writes_an_empty_quickbooks_file(brazos):
    """*Wrote an empty QuickBooks file.* — and the file is a real IIF file.

    ⚠ A ZERO-ROW FILE IS NOT A ZERO-BYTE FILE, which is what makes the sentence
    honest. The declarations are there and the entries are not, so QuickBooks
    would open it and find nothing — which is exactly the claim being made.
    """
    with tenant_ctx(brazos):
        connection = _target(brazos, file_format="iif")
        result = accounting_file.AccountingFileAdapter().test(_view(connection), {})

    assert result.ok is True
    assert result.sentence == "Wrote an empty QuickBooks file."
    payload = accounting_file.zero_row_export("iif").decode("utf-8")
    assert payload.startswith("!TRNS\t"), "the vendor's declaration line"
    assert "!ENDTRNS" in payload
    assert "\nTRNS\t" not in payload, "a ZERO-row file has no entries"
    assert len(payload) > 0, "and it is not an empty file either"


def test_tc5_a_format_with_no_writer_answers_honestly_rather_than_passing():
    """⚠ HARD-WON LAW 7's *incapable of failing* shape, in a `test()`.

    `xero`'s column layout is a projection and is Runbooks' by ruling; `qbo` is
    wave I's. Both are REGISTERED, so the picker offers them and `departures`
    accepts them — and a `test()` that reported success because it never wrote
    anything would be the credential-parse mistake wearing better manners.

    No database: `test()` reads a `ConnectionView`, and building two views is
    the honest way to exercise two formats when a utility may hold only one
    saved accounting connection (`DEF-INT-4245`).
    """
    for unwritable in ("xero", "qbo"):
        view = ConnectionView(
            provider_key=ACCOUNTING,
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"label": f"To {unwritable}", "destination": "download",
                    "file_format": unwritable},
            label=f"To {unwritable}",
        )
        result = accounting_file.AccountingFileAdapter().test(view, {})
        assert result.ok is False, f"{unwritable} has no encoder and must not pass"
        assert result.sentence == accounting_file.NO_WRITER_SENTENCE


@pytest.mark.django_db
def test_a_drop_destination_with_no_folder_client_says_so_rather_than_passing(brazos):
    """The declared gap on this deployment, asserted so it cannot rot silently."""
    with tenant_ctx(brazos):
        connection = _target(brazos, destination="drop", file_format="csv")
        result = accounting_file.AccountingFileAdapter().test(_view(connection), {})
    assert accounting_file.folder_writer() is None, "no folder client is installed here"
    assert result.ok is False
    assert result.sentence == accounting_file.NO_CLIENT_SENTENCE


@pytest.mark.django_db
def test_a_drop_destination_with_a_writer_bound_places_the_zero_row_file(brazos, monkeypatch):
    """The OTHER direction of the gap above — with a writer bound, it writes.

    ⚠ THIS IS WHAT MAKES THE GAP A GAP RATHER THAN A MISSING FEATURE. The path
    is complete and proved; what is absent is an SFTP library on this
    deployment. Bind a recorded writer and the whole thing runs.
    """
    written: list[dict] = []

    class Recorded(accounting_file.FolderWriter):
        def write(self, **kwargs):
            written.append(kwargs)

    monkeypatch.setattr(accounting_file, "FOLDER_WRITER", Recorded())
    with tenant_ctx(brazos):
        connection = _target(brazos, destination="drop", file_format="csv")
        result = accounting_file.AccountingFileAdapter().test(
            _view(connection), {"drop_password": "hunter2"}
        )

    assert result.ok is True
    assert result.sentence == "Wrote an empty CSV file."
    assert len(written) == 1
    assert written[0]["host"] == "sftp.aclarian.example"
    assert written[0]["filename"] == "smartbillhub-test-export.csv"
    assert written[0]["payload"], "a zero-ROW file still has bytes"


@pytest.mark.django_db
def test_the_folder_password_never_reaches_the_describe_sentence(brazos):
    """`BR-INT-003`. The conformance kit asserts this for every adapter; it is
    asserted here too because this is the first adapter that holds a folder
    password for an OUTBOUND connection."""
    with tenant_ctx(brazos):
        connection = _target(brazos, destination="drop", file_format="csv")
        sentence = accounting_file.AccountingFileAdapter().describe(_view(connection))
    assert "hunter2" not in sentence
    assert "password" not in sentence.lower()
    assert sentence == "Month-end journal · CSV · dropped at sftp.aclarian.example"


# ═══════════════════════════════════════════════════════════════════════════
# The connection's own shape — `destination × codec`, and the defect it fixes.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_connection_carries_two_axes_and_the_ledger_column_is_untouched():
    """`DEF-INT-4243` (field map `I-16`) in one assertion.

    The manifest answers WHERE and WHAT SHAPE separately, and the four shapes
    are the ledger's four `EXPORT_TARGETS` verbatim, so `file_format` maps onto
    the batch's existing `target` string one-for-one and no signed idempotency
    key moves.
    """
    from apps.ledger import models as ledger_models

    manifest = registry.REGISTRY.require(ACCOUNTING)
    by_name = {one.name: one for one in manifest.fields}
    assert by_name["destination"].options == ("download", "drop")
    assert by_name["file_format"].options == ledger_models.EXPORT_TARGETS
    assert manifest.auth.mode == "none", "a download has no far end to authenticate to"


@pytest.mark.django_db
def test_folder_fields_are_refused_against_a_download_never_merely_ignored(brazos):
    """`BR-INT-003` — the cheapest secret to keep safe is the one we declined
    to take. A folder password stored against a connection that will never dial
    a folder is a secret held for no purpose."""
    adapter = accounting_file.AccountingFileAdapter()
    errors = adapter.validate(
        {
            "label": "Month-end journal",
            "destination": "download",
            "file_format": "iif",
            "drop_password": "hunter2",
            "drop_host": "sftp.example",
        }
    )
    fields = {one.field for one in errors}
    assert "drop_password" in fields and "drop_host" in fields
    #: and the mirror: a drop with no host is not a destination
    missing = adapter.validate(
        {"label": "To the folder", "destination": "drop", "file_format": "csv"}
    )
    assert {one.field for one in missing} == {"drop_host", "drop_username"}


def test_the_adapter_is_actually_bound_which_is_what_makes_the_card_connectable():
    """Hard-won law 2: built is not wired. Until this line existed the card was
    live, the manifest was registered, and every connect was refused."""
    assert ADAPTERS[ACCOUNTING] is accounting_file.AccountingFileAdapter


def test_the_docstring_that_counts_the_adapters_agrees_with_the_dictionary():
    """⚠ **THE COUNT IS READ FROM THE SENTENCE, NOT PINNED AS A LITERAL — AND
    THAT REWRITE IS ITSELF A LESSON, LEARNED TWICE IN ONE DAY.**

    `adapters/__init__.py` opens with *"N ADAPTERS ARE LISTED"*, and that
    sentence had been wrong twice before wave J — the same shape as B14's
    rule-count line, which `CLAUDE.md` records as wrong five times: adding the
    thing and updating the sentence that counts them are two acts and only the
    first feels like the work.

    Wave J pinned `len(ADAPTERS) == 6` to stop it. **It was right for about an
    hour.** Wave K bound the water meter cloud and moved it to 7; wave M bound
    the city's address service and moved the DOCSTRING to 8 and left the
    assertion at 7. So a literal made the guard a chore that two siblings had to
    remember, and the second one did not — which is the failure the guard
    existed to prevent, wearing a different hat.

    **Reading the number out of the sentence removes the chore entirely.** A
    lane that adds a ninth adapter and forgets the docstring goes red, naming
    both numbers; a lane that updates both goes green with no edit here. The
    guard now polices the AGREEMENT rather than the value, which is the thing
    anybody actually cared about.
    """
    import re

    from apps.integrations import adapters as adapters_module

    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15,
    }
    found = re.search(r"([A-Z]+) ADAPTERS ARE LISTED", adapters_module.__doc__ or "")
    assert found is not None, (
        "adapters/__init__.py must open with '<N> ADAPTERS ARE LISTED' — that "
        "sentence is what this guard reads, and a rewrite that drops it removes "
        "the only thing keeping the count honest"
    )
    claimed = words.get(found.group(1).lower())
    assert claimed is not None, f"unknown number word {found.group(1)!r}"
    assert claimed == len(ADAPTERS), (
        f"the docstring says {found.group(1)} adapters and the dictionary holds "
        f"{len(ADAPTERS)}. Adding an adapter and updating the sentence that counts "
        "them are two acts; this is the one that fails when only the first is done."
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-038 TC-3 · TC-6 — camt.053 decodes, and is STILL not a supported
#                          format, because supported means a recorded file.
# ═══════════════════════════════════════════════════════════════════════════

#: A structural camt.053 statement, held under `tests/` and DELIBERATELY NOT
#: under `apps/integrations/fixtures/camt053/`. A file written to exercise a
#: parser must never be able to make the conformance kit say *supported* about
#: a format no real bank has been read with — which is the failure `BR-INT-033`
#: exists to prevent, and the one thing a test file could cause.
CAMT053 = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr><MsgId>BRAZOS-2026-09-01</MsgId></GrpHdr>
    <Stmt>
      <Id>STMT-0091</Id>
      <Acct><Id><Othr><Id>0000123456</Id></Othr></Id><Ccy>USD</Ccy></Acct>
      <Ntry>
        <Amt Ccy="USD">142.18</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <BookgDt><Dt>2026-09-01</Dt></BookgDt>
        <ValDt><Dt>2026-09-01</Dt></ValDt>
        <AcctSvcrRef>20260901-000318</AcctSvcrRef>
        <NtryDtls><TxDtls>
          <Refs><EndToEndId>PAY-2609-0311</EndToEndId></Refs>
          <RmtInf><Ustrd>ACC-1048 SEPTEMBER</Ustrd></RmtInf>
        </TxDtls></NtryDtls>
      </Ntry>
      <Ntry>
        <Amt Ccy="USD">42.50</Amt>
        <CdtDbtInd>DBIT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <BookgDt><Dt>2026-09-01</Dt></BookgDt>
        <ValDt><Dt>2026-09-02</Dt></ValDt>
        <AcctSvcrRef>20260901-000319</AcctSvcrRef>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>
"""


def test_tc3_a_camt053_statement_decodes_to_one_row_per_entry():
    rows = codecs.parse("camt053", CAMT053)
    assert len(rows) == 2, "one row per <Ntry>, and nothing else in the file"
    assert rows[0]["amount"] == "142.18"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["booking_date"] == "2026-09-01"
    assert rows[0]["bank_reference"] == "20260901-000318"
    assert rows[0]["remittance"] == "ACC-1048 SEPTEMBER"
    #: an entry with no remittance block is a row with an empty field, never a
    #: missing key — a caller reading `row["remittance"]` must not raise on the
    #: ordinary case of a bank that sent none.
    assert rows[1]["remittance"] == ""
    assert rows[1]["end_to_end_id"] == ""


def test_tc3_the_direction_is_carried_and_never_folded_into_a_sign():
    """⚠ THE JUDGMENT THIS CODEC IS NOT ALLOWED TO MAKE, ASSERTED.

    A camt.053 states the amount unsigned and the direction beside it. Folding
    them into a negative number here would decide, in a codec, that a debit
    means money leaving us — true of a bank account, false of a lockbox, and
    exactly the kind of meaning `BR-INT-054` puts on the other side of the line.
    """
    rows = codecs.parse("camt053", CAMT053)
    assert rows[0]["direction"] == "CRDT" and not rows[0]["amount"].startswith("-")
    assert rows[1]["direction"] == "DBIT" and not rows[1]["amount"].startswith("-")


def test_tc3_a_bank_that_upgraded_its_iso_version_still_reads():
    """⚠ THE SILENT FAILURE THIS AVOIDS IS THE WORSE ONE. Pinning a namespace
    would make a perfectly good statement from a bank on `camt.053.001.08` read
    as an EMPTY FILE — no error, no rows, nothing red."""
    upgraded = CAMT053.replace(b"camt.053.001.02", b"camt.053.001.08")
    assert codecs.parse("camt053", upgraded) == codecs.parse("camt053", CAMT053)


def test_tc6_camt053_has_code_and_is_still_not_a_supported_format():
    """⚠ THE THIRD STATE, AND IT IS THE POINT OF `BR-INT-033`.

    *Registered* is a name. *Supported* is a name plus code plus **a recorded
    file from the real provider**. camt.053 now has code and no recorded bank
    statement, so the kit says *not a supported format* — truthfully, about the
    half that is missing. This is `US-INT-038` TC-6 exactly: a codec with no
    fixture fails the kit.
    """
    assert codecs.CODECS.require("camt053").decode is not None, "it has a decoder"
    assert codecs.is_supported("camt053") is False, "and no recorded bank file"
    finding = next(f for f in codecs.check_fixtures() if f.codec == "camt053")
    assert finding.status == "not_supported"
    assert "no recorded fixture" in finding.reason
    #: and the folder says WHY in words, not merely by being empty
    note = codecs.provenance("camt053") or ""
    assert "real bank" in note


def test_the_camt053_fixture_used_here_is_not_in_the_fixtures_folder():
    """The guard on the guard. If this file's sample ever moved into
    `fixtures/camt053/`, the kit above would flip to *supported* and this repo
    would claim to read a format no bank has ever sent it."""
    assert codecs.fixture_paths("camt053") == [], (
        "a typed sample must never live in fixtures/ — BR-INT-033's whole point"
    )


# ═══════════════════════════════════════════════════════════════════════════
# The IIF codec — the vendor's grammar over the projection's columns.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_recorded_iif_fixture_is_this_emitter_on_the_worked_payment():
    """The fixture is what makes a codec SUPPORTED, and it is honest only if it
    is what the code produces. Re-record it on purpose, never by hand."""
    from datetime import date as _date
    from decimal import Decimal
    from types import SimpleNamespace

    payment = SimpleNamespace(
        payment_no="PAY-2609-0311",
        posted_at=_date(2026, 9, 1),
        amount=Decimal("142.1800"),
        currency="USD",
        method=SimpleNamespace(name="Bank transfer"),
        account_code="4100",
        partner_account="001.100.44100",
        account_no="ACC-1048",
    )
    emitted = codecs.emit("gl_payment_v1", "iif", [payment])
    recorded = (codecs.FIXTURES_ROOT / "iif" / "gl_payment_v1.iif").read_bytes()
    assert emitted.payload == recorded
    assert emitted.filename == "gl_payment_v1.iif"
    assert codecs.is_supported("iif") is True


def test_a_tab_inside_a_value_is_refused_rather_than_escaped():
    """⚠ IIF HAS NO QUOTING, so a tab in a memo shifts every later column one
    place left — an amount lands in a date field with nothing going red. There
    is no substitution that keeps the value a person typed, so it is refused
    and NAMED."""
    with pytest.raises(ValueError, match="no quoting"):
        codecs.CODECS.require("iif").encode(
            ({"memo": "paid\tin\tfull", "amount": "10.00"},), ("memo", "amount")
        )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-INT-4254 — a refusal that crashed instead of refusing, found by clicking
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_bad_environment_and_a_bad_cadence_are_REFUSED_rather_than_crashing(brazos):
    """⚠ THESE THREE BRANCHES ANSWERED HTTP 500 FROM WAVE B UNTIL 2026-09-06.

    They raised `errors.VAL_INVALID`, an attribute that **has never existed** on
    `core.errors`, so each one answered `AttributeError` instead of the refusal
    it was written to give. Nothing in this repository could see it: Python
    resolves a module attribute at CALL time rather than at import, the connect
    modal offers `production | sandbox` as a two-value control and `manual` as a
    default so no screen can reach the branch, and no test had ever sent a value
    outside the vocabulary.

    **A browser walkthrough that omitted `environment` by accident is what found
    it** — hard-won law 6 in one line: no gate here looks at rendered output.

    This case is that branch's first reader. It sends a value outside each
    closed vocabulary and asserts a REFUSAL a clerk could act on.
    """
    from core import errors

    assert not hasattr(errors, "VAL_INVALID"), (
        "if this ever exists, the three sites this case guards should still not "
        "use it — a value outside a closed vocabulary is an UNKNOWN LOOKUP"
    )

    with tenant_ctx(brazos):
        for bad, message_key in (
            ({"environment": "staging"}, "integrations.refusal.environment"),
            ({"cadence": "fortnightly"}, "integrations.refusal.cadence"),
        ):
            with pytest.raises(errors.ValidationError) as refused:
                services.connect_with_fields(
                    actor=SimpleNamespace(id=None, role="system_admin"),
                    tenant_id=brazos.id,
                    provider_key=ACCOUNTING,
                    environment=bad.get("environment", models.ENVIRONMENT_PRODUCTION),
                    cadence=bad.get("cadence", "manual"),
                    label="Month-end journal",
                    fields={
                        "label": "Month-end journal",
                        "destination": "download",
                        "file_format": "iif",
                    },
                )
            #: a REFUSAL, with a code and a catalogue key a clerk reads —
            #: never an AttributeError
            assert refused.value.code == errors.VAL_UNKNOWN_LOOKUP
            assert refused.value.message_key == message_key


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-038 TC-5 — the R02 boundary. ⚠ RULED, so nothing here is a stub.
# ═══════════════════════════════════════════════════════════════════════════


def test_tc5_the_four_signed_reversal_reasons_are_still_four():
    """`OQ-INT-1487` closed 2026-09-04 to option (b): `R02` records as `other`
    with the raw code kept, and the four signed reasons are NOT widened to
    five. This asserts the ratified figure so drift goes red."""
    from apps.payments import models as payment_models

    assert len(payment_models.REVERSAL_REASONS) == 4, (
        "OQ-INT-1487 (b) — widening a signed list for one bank code needs a "
        "finance re-sign, and the PO declined it"
    )
    assert "account_closed" not in payment_models.REVERSAL_REASONS


# ═══════════════════════════════════════════════════════════════════════════
# The boundary — two deliberate absences, asserted so they cannot close
#                silently when Runbooks lands.
# ═══════════════════════════════════════════════════════════════════════════


def test_what_goes_in_the_file_is_runbooks_and_this_module_answers_nothing():
    """⚠ THIS TEST GOES RED THE DAY RUNBOOKS PLUGS IN, AND THAT IS ITS JOB.

    `CR-069` §20.4 moves *readiness* and the journal's contents to Runbooks.
    Both doors answer empty today. A lane that fills one without moving this
    assertion has closed a ruled boundary in silence, which is the failure
    hard-won law 2's mirror describes.
    """
    assert departures.journal_rows(period_start=JULY[0], period_end=JULY[1], target="iif") == []
    assert departures.export_readiness(target="iif") == {}


def test_the_zero_row_export_asks_nobody_what_belongs_in_a_file():
    """The structural proof of the boundary, rather than a claim about it: the
    one function `test()` calls to build bytes is handed no period, no tenant
    and no ledger — only a format name."""
    import inspect

    signature = inspect.signature(accounting_file.zero_row_export)
    assert list(signature.parameters) == ["file_format"], (
        "a zero-row export that took a period would be asking the books a "
        "question BR-INT-054 puts in Runbooks"
    )
