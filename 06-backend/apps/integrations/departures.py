# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-033 (EP-INT-09) TC-2 · TC-5 — a period regenerated is the
#           same file or a refusal naming the first handover. US-INT-038 TC-2 —
#           an outbound unregistered format refused BY NAME with the list.
#           US-INT-009 (the saved export target). Screens: S43 · S142
# Rules:    BR-INT-020 B (**the key is period + target**) · BR-INT-031
#           (inbound degrades, outbound REFUSES by name with the list) ·
#           BR-INT-033 (a format is a registered codec) · BR-INT-039 (a run
#           row is append-only) · BR-INT-054 as amended 2026-09-06
#           (integrations records that a file went out — AND STOPS) ·
#           BR-LED-004 (the four targets, and the ledger's own signed key) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6 (idempotency)
# Tests:    06-backend/tests/test_us_int_038_export_target.py
# Impacts:  apps/integrations/adapters/accounting_file.py (the connection this
#           keys) · apps/integrations/arrivals.py (the INBOUND mirror — read
#           the two together) · apps/ledger/exports.py (`overlapping_batch`,
#           `content_hash` — the ledger's own key, which this does not move)
# ───────────────────────────────────────────────────────
"""A period went out on a connection — keyed, recorded, and refused if we have sent it already.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 IDEMPOTENCY KEYS (CLAUDE.md sensitive paths).
    The key this module computes is a hard-rule-6 idempotency key on the
    carrier of outbound money. Get it wrong in one direction and a utility's
    ERP books July's revenue twice; get it wrong in the other and a genuine
    correction is silently refused. Authored by AI under the standing protocol
    (PO 2026-08-09, *"AI will do it; we will review it later as human"*); the
    row stating what a reviewer is owed, in plain English with a figure, is in
    `12-governance/09-human-review-ledger.md`.

THE MIRROR OF `arrivals.py`, AND THE ONE PLACE THE MIRROR IS NOT SYMMETRIC
══════════════════════════════════════════════════════════════════════════
Wave I asked *have we taken these bytes before* and answered it on the BYTES,
before anything parsed them. This asks *have we handed this window over
before* — and it cannot answer on the bytes, because the bytes do not exist
yet. Nothing has been built when the question has to be asked, and that is the
whole difference:

    inbound   the file exists  → hash it, then decide       (BR-INT-020 C)
    outbound  the file does not → key the REQUEST, then decide (BR-INT-020 B)

So the outbound key is **period + target**, and it is computed from what was
ASKED FOR rather than from what was produced. A period asked for twice is the
same handover whatever we would build the second time, and that is the
guarantee `BR-LED-004` needs: *"export batches recorded + IDEMPOTENT (no
double-handover)"*.

⚠ **WHY *THE SAME FILE OR A REFUSAL* AND NEVER *A DIFFERENT FILE***. The
dangerous outcome is not the refusal, it is the third one nobody asks for: a
second export of July that QUIETLY DIFFERS from the first — a ref edited in
between, a rounding rule moved, an entry auto-forwarded after the close. The
accountant then holds two files that both claim to be July and cannot be told
apart by looking. The ledger already prevents that by STORING the payload it
sent (`apps/ledger/exports.py` — *"the rows that were handed over are kept
exactly as they were handed over"*), so regenerating July reads the recorded
batch rather than re-deriving from the books. This module is the second guard,
on the CONNECTION, and it is stricter than the ledger's in one way that
matters: the ledger's key is per tenant and window, and this one is per
tenant, CONNECTION and window — so two saved export targets at one utility, a
QuickBooks one and a CSV one for the auditor, do not refuse each other.

WHERE THIS STOPS, AND WHY IT STOPS THERE (BR-INT-054 as amended 2026-09-06)
══════════════════════════════════════════════════════════════════════════
`CR-069` §20.4 splits wave J in as many words. **Kept here:** the connection,
`test()`, the codec, and *"period + target giving the same file or a refusal
naming 5 August — outbound duplicate-recognition, the same argument as wave
I"*. **Moved to Runbooks:** *"readiness (3 accounts still need an export code
is a business judgment about the chart of accounts)"*.

So this module knows that July went to the QuickBooks target on 5 August. It
does not know what a journal row is, which accounts are ready, or whether a
figure is right. `journal_rows()` and `export_readiness()` below are the two
doors those answers arrive through, and both are **deliberate absences rather
than stubs** — nothing is unruled and no question is open, so a lane finding
them should leave them alone.

THE OTHER HALF: AN UNREGISTERED FORMAT IS REFUSED BY NAME (BR-INT-031)
══════════════════════════════════════════════════════════════════════════
Inbound and outbound are the same rule pointing opposite ways. Inbound
DEGRADES — *"refusing a real payment over a vocabulary is worse than misfiling
it"* — and an unmapped tender word records as `other` and goes red for a clerk.
Outbound REFUSES, because the failures are not comparable: a file that reaches
a partner's loader in a shape they did not expect either stops, or reads the
wrong field into the wrong place and posts money to the wrong account with
nothing going red. **A refusal costs one attempt; a substitution costs a
close.**

⚠ AND THE REFUSAL NAMES WHAT EXISTS, WHICH IS THE HALF PEOPLE DROP. *"xlsx is
not a registered format"* leaves a clerk guessing. *"xlsx is not a registered
format — QuickBooks, Xero, CSV, IIF"* is one sentence they can act on, and the
list comes off THIS CONNECTION's manifest rather than off every codec in the
product: offering `bai2` to somebody exporting a journal would be a worse
answer than none.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from apps.integrations import models, services
from apps.integrations.registry import REGISTRY, Manifest, Operation, Registry

#: The key's algorithm, named so a reader of a run row knows what was keyed
#: without coming and finding this file.
KEY_ALGORITHM = "sha-256"

#: The refusal a second handover gets. A catalogue key in all eleven
#: languages; the SENTENCE is capped at six words (B14 rule 33) and the period
#: and the first handover's date travel as PARAMETERS, never baked into the
#: string, so a catalogue puts them where its own language wants them.
REFUSAL_ALREADY_EXPORTED = "integrations.refusal.already_exported"

#: The refusal an unregistered format gets (BR-INT-031, US-INT-038 TC-2).
REFUSAL_UNREGISTERED_FORMAT = "integrations.refusal.unregistered_format"

#: What a clerk calls each of the four (B14 rule 32 — no enum word on screen).
#: The ENGLISH fallback; the catalogue key wins where it is present.
FORMAT_NAMES = {
    "qbo": "QuickBooks",
    "xero": "Xero",
    "csv": "CSV",
    "iif": "IIF",
}


class UnregisteredFormat(ValueError):
    """An outbound format this connection does not offer — refused BY NAME.

    Carries what was asked and what the connection offers, so a caller can
    phrase it for its own audience without losing either half.
    """

    def __init__(self, asked: str, offered: Sequence[str]) -> None:
        self.asked = asked
        self.offered = tuple(offered)
        self.message_key = REFUSAL_UNREGISTERED_FORMAT
        listed = ", ".join(FORMAT_NAMES.get(one, one) for one in self.offered)
        super().__init__(
            f"{asked} is not a registered format — {listed}"
            if self.offered
            else f"{asked} is not a registered format, and this connection offers none"
        )


@dataclass(frozen=True)
class Departure:
    """One period, handed over on one connection, with the run row recording it.

    `duplicate_of` is the FIRST run that carried this key — not the previous
    one — because *already exported on 5 Aug* has to name the handover a clerk
    can go and look at, and on a third request 5 August is still the answer.
    """

    run: models.IntegrationRun
    export_key: str
    accepted: bool
    duplicate_of: models.IntegrationRun | None = None

    @property
    def first_sent_at(self) -> Any:
        """When this window first went out — the instant the refusal names."""
        return self.duplicate_of.started_at if self.duplicate_of else self.run.started_at


def export_key(*, period_start: date, period_end: date, target: str) -> str:
    """The digest of the WINDOW and the TARGET, and of nothing else.

    ⚠ **GRANULARITY IS DELIBERATELY NOT IN THE KEY**, and that is the ledger's
    signed reading rather than a choice made here: `T5-07` step 3 refuses *"the
    OTHER granularity over the same already-covered window"*, because
    *"idempotency is per covered window, whichever granularity was chosen; the
    window is handed over once"*. Weekly journals over July and one summary
    journal over July are two shapes of the SAME handover, and an ERP that took
    both would book July twice.

    ⚠ **`date` AND NOT `str`, ON PURPOSE.** `"2026-07-01"` and `"2026-7-1"` are
    one window and two digests, so a caller that had already chosen a spelling
    would be able to hand the same July over twice through a formatting
    difference. The type refuses it here, and `isoformat()` is the one spelling.
    """
    if not isinstance(period_start, date) or not isinstance(period_end, date):
        raise TypeError(
            "export_key takes dates; a string means a caller already chose a spelling, "
            "and two spellings of one July are two keys (BR-INT-020 B)"
        )
    if period_end < period_start:
        raise ValueError(f"the window {period_start} … {period_end} runs backwards")
    blob = f"{period_start.isoformat()}|{period_end.isoformat()}|{target}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def previous_departure(
    *,
    connection: models.IntegrationConnection,
    key: str,
) -> models.IntegrationRun | None:
    """The FIRST run on this connection that carried this key, or None.

    ⚠ SCOPED TO THE TENANT AND THE CONNECTION, IN THAT ORDER (hard rule 1).
    `tenant_id` is filtered explicitly as well as by RLS: the guarantee is the
    database's, and this is the second guard for SQLite, where there is no RLS
    at all and a missing filter would pass every test in the default suite.

    ⚠ AND SCOPED TO THE CONNECTION, WHICH IS A JUDGMENT AND IS LOOSER THAN THE
    LEDGER'S OWN KEY. `uq_export_batches_period_target` is per tenant and
    window; this is per tenant, CONNECTION and window. A utility with a
    QuickBooks target and a separate CSV target for its auditor is handing July
    to two different readers, and neither should refuse the other — which is
    `US-LED-016` TC-2's own reading, *"QuickBooks and a generic CSV are two
    accountants, not one double-handover"*. The narrower ledger key still
    stands underneath and is not moved by anything here.
    """
    return (
        models.IntegrationRun.objects.filter(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            input_hash=key,
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


def require_registered_format(
    *,
    connection: models.IntegrationConnection,
    asked: str,
    registry: Registry = REGISTRY,
) -> str:
    """`asked`, or `UnregisteredFormat` — never a substitution (BR-INT-031).

    The list in the refusal is **this connection's manifest's**, not every
    codec in the product. A clerk exporting a journal who is told the system
    also knows `bai2` has been given a worse answer than none.
    """
    manifest = registry.require(connection.provider_key)
    if asked not in manifest.codecs:
        raise UnregisteredFormat(asked, manifest.codecs)
    return asked


def record_departure(
    *,
    connection: models.IntegrationConnection,
    operation: str,
    period_start: date,
    period_end: date,
    target: str,
    trigger: str = "manual",
    job_id: Any = None,
    registry: Registry = REGISTRY,
) -> Departure:
    """Record that a period was asked for. Key FIRST, then the row, then the verdict.

    Returns a `Departure`. `accepted` is False when this window has already
    gone out on this connection; the run row is then closed `skipped` — *we did
    not ask* — because nothing was built and nothing left, and its summary
    names the first handover by date.

    ⚠ THE ORDER OF THE FIRST THREE STEPS IS THE GUARANTEE, exactly as it is in
    `arrivals.record_arrival`, and for the mirror-image reason. Read them as a
    sequence, because a later edit that reorders them breaks a rule no type
    checker can see:

        1. refuse an unregistered format   — before a run row exists at all
        2. key the request, open the row carrying it
                                           — so the request is recorded even
                                             if step 3 raises
        3. ask whether we have sent it     — and refuse if we have

    Step 1 before step 2 is deliberate and is the one asymmetry with the
    inbound path: a file that ARRIVES in a shape we cannot read is still an
    arrival and is owed a row, but a file we were asked to WRITE in a shape
    nobody registered was never a handover at all — there is nothing to record
    having happened. `BR-INT-031` is that difference in one line: inbound
    degrades, outbound refuses.

    Step 2 before step 3 is the same call wave I made: a second request is
    still a REQUEST, and a utility asking *did my second July export do
    anything* is owed a row that says what it did.
    """
    #: 1 · a format nobody registered, refused by name with the list.
    require_registered_format(connection=connection, asked=target, registry=registry)

    manifest = registry.require(connection.provider_key)
    file_operation = _file_operation(manifest, operation)
    if file_operation.transport != "file":
        raise ValueError(
            f"{manifest.key}.{operation} is transport {file_operation.transport!r}, "
            "not a file — a departure is a file leaving (BR-INT-010)"
        )
    if file_operation.direction != "out":
        raise ValueError(
            f"{manifest.key}.{operation} is direction {file_operation.direction!r}; "
            "a departure is outbound. An arrival is `arrivals.record_arrival`."
        )

    #: 2 · the key, then the run row with the key ALREADY on it.
    key = export_key(period_start=period_start, period_end=period_end, target=target)
    run = services.start_run(
        connection=connection,
        operation=operation,
        direction=models.RUN_DIRECTION_OUTBOUND,
        trigger=trigger,
        job_id=job_id,
        #: ⚠ `input_hash` HOLDS THE OUTBOUND KEY TOO, AND THE COLUMN NAME IS
        #: RIGHT RATHER THAN REUSED. It is *the identity of what this run was
        #: given*: for a file arriving that is the bytes; for a file leaving it
        #: is the window and the target we were asked to produce. A connection
        #: is inbound or outbound by its manifest and never both, so the two
        #: readings cannot meet on one connection — and the index
        #: `ix_intg_run_input_hash` serves both lookups unchanged.
        input_hash=key,
        registry=registry,
    )

    #: 3 · have we handed this window over on this connection before?
    first = previous_departure(connection=connection, key=key)
    if first is not None and first.id != run.id:
        services.finish_run(
            run,
            attempted=0,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=True,
            never_dialled=True,
            summary=duplicate_summary(first, period_start=period_start),
        )
        run.refresh_from_db()
        return Departure(run=run, export_key=key, accepted=False, duplicate_of=first)

    return Departure(run=run, export_key=key, accepted=True)


def duplicate_summary(first: models.IntegrationRun, *, period_start: date) -> str:
    """*July was already exported on 5 Aug*.

    The ENGLISH fallback. The catalogue key `REFUSAL_ALREADY_EXPORTED` wins on
    screen where it is present, with the period name and the date as
    parameters, so a translation is a catalogue line and never an edit here
    (B14 rule 35 — a catalogue is written in its own language, not translated
    from English).

    ⚠ THE DATE COMES OFF THE FIRST RUN'S OWN TIMESTAMP AND IS NOT A GUESS. A
    clerk who exported on 5 August reads *5 Aug*; the row itself carries the
    instant, so the sentence and the row cannot disagree.
    """
    return f"{period_start:%B} was already exported on {first.started_at:%-d %b}"


def close_departure(
    departure: Departure,
    *,
    attempted: int,
    succeeded: int,
    failed: int,
    skipped: int,
    confirmed: bool = True,
    summary: str | None = None,
    artifact_link: str | None = None,
) -> models.IntegrationRun:
    """Close an ACCEPTED departure's run row once its owner has finished with it.

    ⚠ INTEGRATIONS DOES NOT CALL THIS AND CANNOT SUPPLY ITS ARGUMENTS, which is
    the same shape `arrivals.close_arrival` has and for the same reason. The
    counts it takes are a statement about what the ROWS IN THE FILE were, and
    `BR-INT-054` puts that in Runbooks: a run row recording *this connection
    was asked for July and it had not been asked before* is lifecycle and lives
    here; a run row recording *what the 412 journal lines inside it said* does
    not. The function exists so the processing half has a door on this side to
    close the row through, rather than reaching into `services.finish_run` and
    typing an outcome word itself (BR-INT-018 — the outcome is COMPUTED).

    Until Runbooks is built, an accepted departure's run row stays open, and
    that is honest: the period was asked for, and nothing has yet said what was
    built for it.
    """
    if not departure.accepted:
        raise ValueError("a refused duplicate is already closed; it has no counts")
    return services.finish_run(
        departure.run,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        confirmed=confirmed,
        summary=summary,
        artifact_link=artifact_link,
    )


# ═══════════════════════════════════════════════════════════════════════════
# The two doors Runbooks arrives through — deliberate absences, not stubs
# ═══════════════════════════════════════════════════════════════════════════


def journal_rows(
    *, period_start: date, period_end: date, target: str
) -> list[Mapping[str, Any]]:
    """What goes IN the file — Runbooks', not ours. Returns `[]`, finished.

    `CR-069` §20.4 keeps *"the `accounting_file` connection (destination ×
    codec), `test()`, the `camt053` codec, and period + target giving the same
    file or a refusal naming 5 August"* with integrations, and `BR-INT-054`
    puts *"the logic, the ETL and the record updates"* in Runbooks. Choosing
    which of a period's figures becomes a journal line, and under which of the
    partner's account codes, is a business record built out of our data. It is
    a projection, and §20.4 names projections on the Runbooks side explicitly.

    ⚠ This is a **deliberate absence and not a stub** (`OQ-1396`'s
    distinction): it raises nothing, blocks nothing and names no open question,
    because nothing here is unruled. A lane finding it should leave it alone.
    When Runbooks lands, this is where its projection plugs in — and the test
    named in the header goes red the moment it does, so the boundary cannot
    close silently.

    ⚠ AND AN EMPTY LIST IS NOT A BUG THE CALLER SHOULD ROUND OFF. `test()`
    writes a zero-row file from exactly this answer, and a zero-row file is the
    point: it proves this system can shape and place a file without asking
    anybody what belongs in one.
    """
    return []


def export_readiness(*, target: str) -> dict[str, Any]:
    """*3 accounts still need an export code* — Runbooks'. Returns `{}`, finished.

    §20.4 moves this out of wave J by name: *"readiness (3 accounts still need
    an export code is a business judgment about the chart of accounts)"*.
    Counting which of a utility's GL accounts carry the target system's
    reference is a reading of the chart of accounts, and `BR-LED-014` is the
    ledger's rule for it — `apps/ledger/exports.export_preview` already
    computes `missing_refs` for S43 and is unaffected by anything here.

    ⚠ **WHAT INTEGRATIONS MUST NOT DO IS BUILD A SECOND OPINION.** Two counts
    of *how many accounts are unmapped*, computed in two modules against the
    same rows, part company the first time either moves — and the one on the
    connection card would be the one nobody checks. So this answers nothing at
    all rather than answering nearly the same thing.

    ⚠ A **deliberate absence and not a stub**, on the same reading as
    `journal_rows` above.
    """
    return {}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-033 TC-2 · TC-5 · US-INT-038 TC-2 · US-INT-009 (EP-INT-09,
#         EP-INT-10) + BR-INT-020 B · BR-INT-031 · BR-INT-033 +
#         BR-INT-054 as amended 2026-09-06 (CR-069 §20.4 wave J)
# generated: 2026-09-06 by the CR-069 wave J build lane
# checklist: A✔ B✔ C✔ D✔ E✔(S142's run row and its refusal sentence) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_038_export_target.py
# exceptions: `close_departure`, `journal_rows` and `export_readiness` have no
#             caller in this module BY RULING — the processing half is
#             Runbooks' (BR-INT-054, CR-069 §20.4). Deliberate absences, not
#             unfinished stubs; each says so in its own docstring.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
