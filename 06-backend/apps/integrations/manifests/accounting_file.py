"""Accounting export file — the month's journal for the accountant (Accounting · LIVE · no credential for a download).

WHAT `DESTINATION × CODEC` FIXES, AND WHY IT IS TWO FIELDS RATHER THAN ONE
-------------------------------------------------------------------------
`ledger/models.py:832` carries `target` over `("qbo", "xero", "csv", "iif")` —
one column answering two questions. `qbo` and `xero` name an accounting SYSTEM
the file is going TO; `csv` and `iif` name the SHAPE of the bytes. A utility
that wants a plain CSV dropped in a folder for its Xero bookkeeper cannot say
so, and every check over that column passes because the list IS consistent as
a list. Filed as `DEF-INT-4243` (field map `I-16`) before this file was
written, per the execution plan's `J1`.

So the CONNECTION splits the axes:

    destination ∈ {download, drop}      WHERE the file goes
    file_format ∈ {qbo, xero, csv, iif} WHAT SHAPE it is in

⚠ **THE LEDGER'S COLUMN IS NOT TOUCHED AND ITS SIGNED KEY DOES NOT MOVE.**
`uq_export_batches_period_target` is a signed idempotency constraint on a money
path (`BR-LED-004`), and a wave about connections does not get to move one.
`file_format` maps onto that existing string; `destination` is a fact about the
connection that the batch has never held. Retiring the column is the ledger's
own work and `DEF-INT-4243` stays open until it does it.

⚠ **NO CREDENTIAL FOR A DOWNLOAD** — `auth.mode == "none"`. A file a clerk
downloads in the browser has no far end to authenticate to, and the cheapest
secret to keep safe is the one we declined to take (`BR-INT-003`). A `drop`
destination names a folder and carries one folder password; the adapter refuses
folder fields typed against a `download` destination for that reason.

WHERE THIS STOPS (`BR-INT-054` as amended 2026-09-06, `CR-069` §20.4 wave J)
----------------------------------------------------------------------------
This connection is a REMEMBERED DESTINATION. It knows where the month's journal
goes and what shape it goes in; **it does not know what a journal row means**.
Which accounts are ready, which figures belong in the file, and whether *3
accounts still need an export code* are business judgments about the chart of
accounts, and §20.4 puts them in Runbooks. `runners/deliver.journal_rows()` and
`export_readiness()` are the two doors they arrive through, and both answer
nothing today, deliberately.

The key that DOES stay here is **period + target** (`BR-INT-020` B) — a period
handed over twice is the same file or a refusal naming the first handover by
date. That is outbound duplicate recognition, exactly the argument wave I made
inbound, and it is a fact about the connection rather than about the money.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.accounting_file.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
    Vocabulary,
)

#: WHERE the file goes. `download` is a clerk pressing a button and getting a
#: file; `drop` is a folder we write into. Two values and no third: a mailed
#: file and an API handover are different connections, not a third destination.
DESTINATION_DOWNLOAD = "download"
DESTINATION_DROP = "drop"
DESTINATIONS = (DESTINATION_DOWNLOAD, DESTINATION_DROP)

#: WHAT SHAPE the bytes are in. These four are `ledger.models.EXPORT_TARGETS`
#: verbatim (`BR-LED-004`: *"QBO/Xero/CSV/IIF"*), so `file_format` maps onto the
#: batch's `target` string one-for-one and no translation table is needed.
FILE_FORMATS = ("qbo", "xero", "csv", "iif")

#: HOW LONG a handed-over month stays downloadable — `P4.9`, Finance blueprint
#: p076 (*"Export destination + retention · Settings → Integrations"*).
#:
#: ⚠ **THE EMPTY VALUE IS *NOT SET*, AND *NOT SET* IS TODAY'S BEHAVIOUR.** A
#: batch's file is re-derived from its stored payload (`P4.2`), which is kept
#: for as long as the row is; nothing has ever expired one. So a tenant who
#: chooses nothing here gets exactly what every tenant has had until now, and
#: the field cannot change anybody's product by existing.
#:
#: ⚠ **AND WHAT THIS SETTING GOVERNS IS THE DOWNLOAD, NOT A DELETION.** The
#: file stops being served past the window; the stored payload is NOT purged,
#: because purging a hand-over's payload is a records decision nobody has taken
#: and a sweep nobody has built. `OQ-LED-12654` carries that half and this
#: file, the endpoint and the screen all say the same thing — a setting that
#: implied a deletion it does not perform would be a privacy claim this product
#: cannot keep.
RETENTION_MONTHS = ("12", "24", "36", "84")

MANIFEST = Manifest(
    key="accounting_file",
    category="accounting",
    display_name="Accounting export file",
    summary="Hand the month's journal to your accounting system as a file.",
    disposition=Disposition(kind="live", phase=4),
    auth=Auth(mode="none", placement="none"),
    codecs=FILE_FORMATS,
    vocabularies=(
        # OPEN: an accounting partner's strings for our accounts are typed per
        # utility, never shipped. ⚠ The chart's own `qbo_ref` / `xero_ref` are
        # READ and never widened — rows here sit BESIDE them (OQ-INT-1480).
        Vocabulary(
            entity_type="ledger_account",
            label="Their account codes",
            summary="Their code for each of your accounts.",
            open=True,
        ),
    ),
    fields=(
        Field(name="label", label="What to call it", kind="text"),
        Field(
            name="destination",
            label="Where the file goes",
            kind="select",
            options=DESTINATIONS,
        ),
        Field(
            name="file_format",
            label="File format",
            kind="select",
            options=FILE_FORMATS,
        ),
        #: A `drop` destination only. Same three shapes the bank connection
        #: uses for a folder, so a utility types one kind of folder detail
        #: across the product rather than two.
        Field(name="drop_host", label="Folder host", kind="host", required=False),
        Field(name="drop_username", label="Folder username", kind="text", required=False),
        Field(name="drop_path", label="Folder path", kind="text", required=False),
        Field(name="drop_password", label="Folder password", kind="secret", required=False),
        #: `P4.9`. Optional, and an empty value means *not set*, which is what
        #: every existing connection carries and what every tenant has today.
        #: ⚠ **NO `default=`.** `Field.default` has no writer (`DEF-INT-5595`),
        #: so one here would be a value the form never pre-fills and a reader
        #: would then treat *unset* and *the default* as the same answer — which
        #: is the substitution this field exists to avoid.
        Field(
            name="retention_months",
            label="Keep files for",
            kind="select",
            options=RETENTION_MONTHS,
            required=False,
        ),
    ),
    operations=(
        Operation(
            name="export_journal",
            # ⚠ THE FOLDER THE FORM ALREADY ASKS FOR. `required=False` because
            # a `download` destination has no host at all, and a connection
            # with no value for its operation's declared field contributes NO
            # host — which is the correct, earned answer (hard-won law 3).
            host_field="drop_host",
            # Sixty a minute. One journal file per period, handed over on
            # demand; the ceiling is there to refuse a retry storm, not to
            # pace real work.
            rate_limit_per_minute=60,
            label="Journal export",
            description="We build the period's journal file for you to download.",
            direction="out",
            initiative="us",
            transport="file",
            trigger="manual",
            #: `BR-INT-020` B — the covered window and the target, together.
            #: `refuse`, never `replace`: a second handover of July is how an
            #: ERP books July's revenue twice.
            idempotency=Idempotency(mode="refuse", source="period_target"),
            completion="immediate",
            test_action="Build a zero-row file for an empty period.",
        ),
    ),
)
