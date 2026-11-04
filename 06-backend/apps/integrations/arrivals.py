# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-033 (EP-INT-09) — the same bank file twice. US-INT-008 (the
#           bank connection), US-INT-010 (the batch names its connection).
#           Screens: S142 (the run row and its refusal sentence), S38, S141
# Rules:    BR-INT-020 C (**the content hash is computed BEFORE parse**) ·
#           BR-INT-009 (bank side v1 is a FILE) · BR-INT-039 (a run row is
#           append-only) · BR-INT-054 as amended 2026-09-06 (integrations
#           records that a batch arrived — AND STOPS) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 6 (idempotency by unique key)
# Tests:    06-backend/tests/test_us_int_033_duplicate_file.py (SQLite) ·
#           06-backend/tests/test_us_int_033_duplicate_file_pg.py (PostgreSQL —
#           the phase-4 exit test)
# Impacts:  apps/integrations/services.py (`start_run(input_hash=…)` and the
#           `KEEP` sentinel on `finish_run` exist for this file) ·
#           apps/integrations/adapters/bank_lockbox_file.py
# ───────────────────────────────────────────────────────
"""A file arrived on a connection — hashed, recorded, and refused if we have it already.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 IDEMPOTENCY KEYS (CLAUDE.md sensitive paths).
    The content hash this module computes IS a hard-rule-6 idempotency key, on
    the carrier of inbound money: get it wrong in one direction and a utility's
    bank file is applied twice; get it wrong in the other and a real second
    file is silently dropped. That puts this file in the same class as
    `apps/payments/lockbox.py`. Authored by AI under the standing protocol (PO
    2026-08-09, *"AI will do it; we will review it later as human"*); the row
    stating what a reviewer is owed, in plain English with a figure, is in
    `12-governance/09-human-review-ledger.md`.

WHY THE HASH COMES BEFORE THE PARSE, WHICH IS THE WHOLE POINT OF THIS FILE
--------------------------------------------------------------------------
The same bank file arriving twice must be refused on the second arrival, and
refused **on what arrived rather than on what we made of it**. Those are two
different guarantees and only one of them survives contact with time:

  * Hashing the BYTES means a byte-identical file is a duplicate **even if the
    parser has since changed** — a new codec, a fixed column mapping, a bug
    repaired between Tuesday and Wednesday. The answer to *have we had this
    file before* cannot be altered by editing the code that reads it.
  * It also means a file differing by ONE BYTE is a NEW file **even if it
    parses to the same rows**. That is the direction people find surprising,
    and it is the safe one: we refuse only what we can prove we have already
    taken, and a bank that re-cuts a file with a new sequence number in its
    header gets a fair hearing rather than a silent drop.

Hash after parsing and both guarantees invert. The key becomes a fact about
our own interpretation, so it moves when our code moves, and the day a parser
changes, every file in history stops matching itself.

⚠ AND THE ORDERING IS THE ONLY THING THAT MAKES IT TRUE, so it is a fact about
the ROW rather than a claim in a comment (hard-won law 1). `record_arrival`
below hashes at its first statement and opens the run row with the digest
already on it, through `services.start_run(input_hash=…)`. Nothing in this
module can read a field out of the file, and it imports no codec and no parser
to do it with. A test asserts the ordering by handing in bytes that would
raise if anything tried to decode them (`US-INT-033` TC-1).

WHERE THIS STOPS, AND WHY IT STOPS THERE (BR-INT-054 as amended 2026-09-06)
---------------------------------------------------------------------------
The Product Owner drew the line through this exact case on 2026-09-05:

    *"A bank file lands. Integrations connects to the bank, authenticates,
    pulls the file, and records that a batch arrived on that connection — and
    stops. Runbooks reads the batch, decides which payment matches which
    account, writes the payments, and keeps the run record and the audit of
    what it decided."*

So this module records an ARRIVAL and nothing else. It does not know what a
row of a lockbox file means, which account a cheque belongs to, or that money
is involved at all — and it writes no payment, no invoice and no journal line.
`arrival` carries the bytes on to whoever owns the processing half; today
nobody does, and that absence is deliberate rather than unfinished. **It is
not a stub awaiting an answer**: the question of who wraps `stage_import` is
ruled, not open (`CR-069` §20.4 wave `I`), and the answer is Runbooks.

⚠ THE DUPLICATE REFUSAL IS THEREFORE STRICTLY STRONGER THAN THE ONE PAYMENTS
ALREADY HAS. `apps/payments/payment_import.py` refuses a duplicate at the
point of staging a batch (`BR-PAY-028`). This one refuses at the point of
ARRIVAL — before a parser is chosen, before a mapping is read — and it is on
the CONNECTION rather than on the import profile, so a file that arrives twice
through the same bank connection is refused whichever processing sits behind
it, and refused when there is none at all.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from apps.integrations import models, services
from apps.integrations.registry import REGISTRY, Manifest, Operation, Registry

#: sha-256 of the bytes exactly as they arrived. Named so a reader of a run row
#: knows what was hashed without coming and finding this file.
HASH_ALGORITHM = "sha-256"

#: The refusal a second arrival gets. A catalogue key in all eleven languages,
#: and the SENTENCE is capped at six words (B14 rule 33) — the date of the
#: first arrival travels as a parameter, never baked into the string, so a
#: catalogue can put it where its own language wants it.
REFUSAL_DUPLICATE_FILE = "integrations.refusal.duplicate_file"


@dataclass(frozen=True)
class Arrival:
    """One file, landed on one connection, with the run row that records it.

    `duplicate_of` is the FIRST run that carried these bytes — not the previous
    one — because *the same file as Tuesday 06:10* has to name the arrival a
    clerk can go and look at, and on a third arrival Tuesday is still the
    answer.
    """

    run: models.IntegrationRun
    input_hash: str
    accepted: bool
    duplicate_of: models.IntegrationRun | None = None

    @property
    def first_seen_at(self) -> Any:
        """When these bytes first arrived — the instant the refusal names."""
        return self.duplicate_of.started_at if self.duplicate_of else self.run.started_at


def content_hash(body: bytes) -> str:
    """The digest of the bytes AS THEY ARRIVED. No decode, no strip, no parse.

    ⚠ `bytes` AND NOT `str`, ON PURPOSE. Accepting text would mean somebody had
    already chosen an encoding, and a file that fails to decode as UTF-8 is
    exactly the file whose arrival most needs recording. A caller holding a
    `str` has already parsed, one layer up, and the type refuses it here.
    """
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise TypeError(
            "content_hash takes the bytes as they arrived; a str means something "
            "already chose an encoding, which is a parse (BR-INT-020 C)"
        )
    return hashlib.sha256(bytes(body)).hexdigest()


def previous_arrival(
    *,
    connection: models.IntegrationConnection,
    input_hash: str,
) -> models.IntegrationRun | None:
    """The FIRST run on this connection that carried these bytes, or None.

    ⚠ SCOPED TO THE TENANT AND THE CONNECTION, IN THAT ORDER (hard rule 1).
    `tenant_id` is filtered explicitly as well as by RLS: the guarantee is the
    database's, and this is the second guard for SQLite, where there is no RLS
    at all and a missing filter would pass every test in the default suite.

    ⚠ AND IT IS SCOPED TO THE CONNECTION, WHICH IS A JUDGMENT. Two bank
    connections at one utility — Chase lockbox and BofA lockbox — can each
    receive a file with identical bytes, and neither should refuse the other's:
    they are different relationships with different banks. The idempotency key
    is therefore (tenant, connection, input_hash), which is what the index on
    `integration_run` supports (`ix_intg_run_input_hash` on tenant + hash,
    narrowed by connection here).
    """
    return (
        models.IntegrationRun.objects.filter(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            input_hash=input_hash,
        )
        .order_by("started_at", "id")
        .first()
    )


def _file_operation(manifest: Manifest, operation: str) -> Operation:
    for one in manifest.operations:
        if one.name == operation:
            return one
    raise ValueError(
        f"{manifest.key} declares no operation {operation!r}; "
        f"declared: {[one.name for one in manifest.operations]}"
    )


def record_arrival(
    *,
    connection: models.IntegrationConnection,
    operation: str,
    body: bytes,
    trigger: str = "manual",
    job_id: Any = None,
    registry: Registry = REGISTRY,
) -> Arrival:
    """Record that a file arrived. Hash FIRST, then the row, then the verdict.

    Returns an `Arrival`. `accepted` is False when these bytes have arrived on
    this connection before; the run row is then closed `skipped` — *we did not
    ask* — because nothing was parsed and nothing was handed on, and its
    summary names the first arrival by day and time.

    ⚠ THE ORDER OF THE FIRST THREE STEPS IS THE GUARANTEE. Read them as a
    sequence, because a later edit that reorders them breaks a rule no type
    checker can see:

        1. hash the bytes                    — before anything looks inside
        2. open the run row carrying it      — so the arrival is recorded even
                                               if step 3 raises
        3. ask whether we have seen it       — and refuse if we have

    Step 2 before step 3 is deliberate: a duplicate that arrives is still an
    ARRIVAL, and a utility asking *did Wednesday's upload reach you at all* is
    owed a row that says yes. Refusing before recording would make the second
    arrival invisible, which is the failure `US-INT-033` names.
    """
    #: 1 · the bytes, as they arrived, before anything reads a field out of them.
    digest = content_hash(body)

    manifest = registry.require(connection.provider_key)
    file_operation = _file_operation(manifest, operation)
    if file_operation.transport != "file":
        raise ValueError(
            f"{manifest.key}.{operation} is transport {file_operation.transport!r}, "
            "not a file — an arrival is a file landing (BR-INT-009)"
        )

    #: 2 · the run row, opened with the digest ALREADY on it.
    run = services.start_run(
        connection=connection,
        operation=operation,
        direction=models.RUN_DIRECTION_INBOUND,
        trigger=trigger,
        job_id=job_id,
        input_hash=digest,
        registry=registry,
    )

    #: 3 · have we taken these exact bytes on this connection before?
    first = previous_arrival(connection=connection, input_hash=digest)
    if first is not None and first.id != run.id:
        services.finish_run(
            run,
            attempted=0,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=True,
            never_dialled=True,
            summary=duplicate_summary(first),
        )
        run.refresh_from_db()
        return Arrival(run=run, input_hash=digest, accepted=False, duplicate_of=first)

    return Arrival(run=run, input_hash=digest, accepted=True)


def duplicate_summary(first: models.IntegrationRun) -> str:
    """*refused duplicate — the same file as Tuesday 06:10*.

    The ENGLISH fallback. The catalogue key `REFUSAL_DUPLICATE_FILE` wins on
    screen where it is present, with the day and the time as parameters, so a
    translation is a catalogue line and never an edit here (B14 rule 35 — a
    catalogue is written in its own language, not translated from English).

    ⚠ THE DAY NAME COMES OFF THE FIRST RUN'S OWN TIMESTAMP AND IS NOT A GUESS.
    A clerk who uploaded on Tuesday reads *Tuesday*; the row itself carries the
    instant, so the sentence and the row cannot disagree.
    """
    when = first.started_at
    return f"refused duplicate — the same file as {when:%A %H:%M}"


def close_arrival(
    arrival: Arrival,
    *,
    attempted: int,
    succeeded: int,
    failed: int,
    skipped: int,
    confirmed: bool = True,
    summary: str | None = None,
    artifact_link: str | None = None,
) -> models.IntegrationRun:
    """Close an ACCEPTED arrival's run row once its owner has finished with it.

    ⚠ INTEGRATIONS DOES NOT CALL THIS AND CANNOT SUPPLY ITS ARGUMENTS. The
    counts it takes — *899 accepted, 1 refused* — are a statement about what
    the rows in the file MEANT, and `BR-INT-054`(3) puts that on the Runbooks
    side: a run row recording *a connection authenticated and pulled a file* is
    lifecycle and lives here; a run row recording *what was decided about the
    899 rows inside it* does not. The function exists so that the processing
    half has a door on this side of the boundary to close the row through,
    rather than reaching into `services.finish_run` and typing an outcome word
    itself (BR-INT-018 — the outcome is COMPUTED, never typed).

    Until Runbooks is built, an accepted arrival's run row stays open, and that
    is honest: the file arrived, and nothing has yet said what became of it.
    """
    if not arrival.accepted:
        raise ValueError("a refused duplicate is already closed; it has no counts")
    return services.finish_run(
        arrival.run,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        confirmed=confirmed,
        summary=summary,
        artifact_link=artifact_link,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-033 · US-INT-008 · US-INT-010 (EP-INT-09) + BR-INT-020 C +
#         BR-INT-054 as amended 2026-09-06 (CR-069 §20.4 wave I)
# generated: 2026-09-06 by the CR-069 wave I build lane
# checklist: A✔ B✔ C✔ D✔ E✔(S142's run row) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_033_duplicate_file.py ;
#        DJANGO_SETTINGS_MODULE=config.settings.local pytest
#        tests/test_us_int_033_duplicate_file_pg.py
# exceptions: `close_arrival` has no caller in this module BY RULING — the
#             processing half is Runbooks' (BR-INT-054). Deliberate absence,
#             not an unfinished stub; see the docstring.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
