"""Bank & lockbox file — import a statement or a lockbox file (Banking · LIVE · upload or SFTP).

BR-INT-009: the bank side of v1 is a FILE. ONE codec is registered — CSV — so
the modal draws NO format picker (BR-INT-033 — where one is registered there is
no picker at all). ⚠ **IT OFFERED SIX UNTIL 2026-10-30 (`DEF-INT-10702`,
lockbox audit LBX-07):** `bai2 · camt053 · csv · ofx · qbo · qfx`, while
`apps/payments/lockbox.py` reads CSV and nothing else, so a utility choosing
BAI2 got a connection that could import nothing. PO Q2 = A, verbatim: *"Will
any utility you're onboarding send lockbox files only in a bank format (BAI or
EDI 823) rather than CSV?-A"* — **CSV only, the other five removed until a
reader exists**; a named customer's need re-opens it. A non-CSV file still
meets the reader's own named refusal. The content hash is computed BEFORE parse (BR-INT-020 C) and a
second upload of the same file is a refused duplicate naming the first — proved
on PostgreSQL in wave I. The column mapping appears only once a file has been
seen (field kind `mapping_editor`, BR-INT-043).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.bank_lockbox_file.*` wins on screen when present, so a
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

#: US-INT-038 — Nacha return codes as MAPPING ROWS onto our four signed
#: reversal reasons (BR-INT-032), never a fifth reason. `R01` maps cleanly to
#: *not enough money*; ⚠ `R02` (*account closed*) maps to none of ours and is
#: `OQ-INT-1487` — the writer refuses to choose for it until the PO does.
NACHA_RETURN_CODES = ("R01", "R02", "R03", "R04", "R10", "R29")

MANIFEST = Manifest(
    key="bank_lockbox_file",
    category="banking",
    display_name="Bank & lockbox file",
    summary="Import a statement or lockbox file.",
    disposition=Disposition(kind="live", phase=4),
    auth=Auth(mode="we_hold_theirs", placement="native"),
    codecs=("csv",),
    vocabularies=(
        Vocabulary(
            entity_type="reversal_reason",
            label="Bounced payments",
            summary="Which of your reversal reasons each bank return code means.",
            values=NACHA_RETURN_CODES,
        ),
    ),
    fields=(
        Field(name="label", label="What to call it", kind="text"),
        # No `file_format` field: one codec, so no picker (BR-INT-033) —
        # `DEF-INT-10702`. The adapter still refuses a stored non-CSV value.
        Field(
            name="source",
            label="Where it comes from",
            kind="select",
            options=("upload", "sftp"),
        ),
        Field(name="sftp_host", label="Folder host", kind="host", required=False),
        Field(name="sftp_username", label="Folder username", kind="text", required=False),
        #: CR-069 wave I. A bank almost never drops files in the account root —
        #: `/outgoing/lockbox` is the shape of it — and `test()` has to list the
        #: folder the files actually land in or it is testing the wrong thing
        #: (BR-INT-019). Optional: left empty, the adapter lists the root.
        Field(name="sftp_path", label="Folder path", kind="text", required=False),
        Field(name="sftp_password", label="Folder password", kind="secret", required=False),
        Field(name="column_mapping", label="Which column is which", kind="mapping_editor"),
    ),
    operations=(
        Operation(
            name="import_statement",
            # ⚠ THE FOLDER THE FORM ALREADY ASKS FOR; absent on an `upload`
            # source, which contributes no host and is right.
            host_field="sftp_host",
            # Sixty a minute: a statement arrives once a day and the ceiling
            # refuses a retry storm rather than pacing anything real.
            rate_limit_per_minute=60,
            label="Bank statement",
            description="We read the bank's statement file and match it to payments.",
            direction="in",
            initiative="us",
            transport="file",
            trigger="manual",
            idempotency=Idempotency(mode="refuse", source="content_hash"),
            completion="immediate",
            test_action="List one folder. Nothing is imported.",
        ),
        Operation(
            name="import_lockbox",
            host_field="sftp_host",
            # Sixty a minute, for the same reason as the statement above.
            rate_limit_per_minute=60,
            label="Lockbox file",
            description="We read the lockbox file and record the cheques it carries.",
            direction="in",
            initiative="us",
            transport="file",
            trigger="manual",
            idempotency=Idempotency(mode="refuse", source="content_hash"),
            completion="immediate",
            test_action="List one folder. Nothing is imported.",
        ),
    ),
)
