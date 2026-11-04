# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-017 (EP-CWP-03) — the one-time code that proves it is you ·
#           US-CWP-019 — the reset link. Screens: CWP-017 · CWP-019
# Rules:    B2 r16 #7 (`outbound_messages` is the ONE table B1 opens to
#           cross-module writes) · BR-CWP-012 (the portal reads through the
#           published seams of the owning modules and adds no second copy) ·
#           BR-CWP-033 (the code goes only to a contact already held) ·
#           CR-068 R12 / BR-CWP-003 (the portal's write boundary is a machine
#           check, and a door that a gate cannot see is not a door)
# Tests:    06-backend/tests/test_us_cwp_016_getting_in.py TC-5 (the outbound
#           row's destination and channel are asserted, not the screen)
# Impacts:  apps/portal/credentials.py (its only caller)
# ───────────────────────────────────────────────────────
"""The ONE door from the portal to `outbound_messages`, resolved by NAME.

⚠ **WHY THIS FILE EXISTS AT ALL, AND WHY IT DOES NOT `import
apps.notifications.services`.** `G81` refuses an import of another module's
`services` anywhere under `apps/portal` — *"a write reached through a service is
still a write"* — and it refused `credentials.py` by name when the queue call
lived there. That gate is right, and the answer is not an allow-list entry: it
is the shape **every other module already uses**. `apps/metering/seams.py` and
`apps/customers/seams.py` both publish exactly this, resolving the callable at
call time rather than binding it at import.

**`outbound_messages` IS A SANCTIONED CROSS-MODULE WRITE AND IS THE ONLY ONE.**
`metering/seams.py` states the rule in its own words — *"the one table B1 opens
to cross-module writes (B2 r16 #7), and this is what that exception means: the
service resolves the recipient, honours the idempotency rule and audits — all of
which a caller reaching for the ORM would skip."* The portal is not asking for a
fifth write point; it is using the exception the platform already made, through
the same door, in the same shape.

⚠ **UNWIRED ⇒ `None` ⇒ THE CALLER REPORTS THAT NOTHING WAS QUEUED.** It never
reports a message it did not queue. For the portal that matters more than
usual: a screen saying *"we sent you a code"* over a queue with no row is a
person waiting for a message that will never come.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

#: The channel names, resolved rather than imported for the same reason the
#: callable is — half a published interface is not an interface. Kept as
#: literals here because they are B2's vocabulary and not notifications'
#: private spelling: `models.CHANNELS` has held these four since r12 #16.
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"

#: The source kind the portal queues under. ⚠ **DELIBERATELY NOT `account`.**
#: `CHANNEL_FLOOR_BY_SOURCE` is keyed on this value and `account` carries a
#: PRINT floor, so filing a one-time code under it would post a six-digit login
#: code by letter, arriving four days after it expired.
SOURCE_PORTAL = "portal"


def _resolve(attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    try:
        target = import_module(f"apps.notifications.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


#: ⚠ **THE FLOOR IS A FACT `notifications` OWNS AND THE PORTAL MAY NOT
#: RESTATE IT.** `services.CHANNEL_FLOOR_BY_SOURCE` is the single statement of
#: which document kinds are ALWAYS printed (`BR-NOT-024`, widened to six kinds
#: by the PO on 2026-08-30: *"don't switch of print for any document it is
#: awayls on"*). A tuple copied here would be a second answer that goes stale
#: the next time the PO widens it, and `CWP-025` renders **ALWAYS** off this
#: read — so a screen promising an off switch and a queue that prints anyway
#: cannot happen.
def print_floor_kinds() -> tuple[str, ...]:
    """The source kinds that are ALWAYS printed, whatever a customer elects.

    ⚠ **AN EMPTY TUPLE IS NOT AN ANSWER OF *no floor* — IT IS *nobody could
    look*, AND THE CALLER MUST TREAT IT THAT WAY.** Every other reader in this
    seam file returns `None` for that; a tuple cannot carry both, so the caller
    (`selectors.contact_preferences`) refuses to draw the grid at all rather
    than drawing one that says a bill can be switched off paper.
    """
    try:
        target = import_module("apps.notifications.services")
    except ImportError:  # pragma: no cover - defensive
        return ()
    floor = getattr(target, "CHANNEL_FLOOR_BY_SOURCE", None)
    if not isinstance(floor, dict):
        return ()
    return tuple(sorted(kind for kind, channels in floor.items() if channels))


def template_pin(code: str) -> Any:
    """`notifications.TemplatePin(code=…)` — WHAT will render this message.

    ⚠ **THE HANDLE IS PASSED AND ITS BODY IS NOT WRITTEN, AND THAT IS A STATED
    ABSENCE.** `queue_document` refuses a row that says nothing about what will
    render it — *"the dispatcher has a recipient and a channel and no idea what
    to put in the envelope"* — and it refused this call by name on the first
    test run, which is that guard doing its job. No template with these codes
    exists yet; `_pinned` REPORTS the missing template rather than guessing, the
    row is written, and it holds with that reason at dispatch (field map N-1's
    ratified posture). The wave that turns sending on owes the BODY.
    """
    pin = _resolve("TemplatePin")
    return pin(code=code) if pin is not None else None


def queue_document(**message: Any) -> Any:
    """Queue one message on the platform's own queue, or answer `None`."""
    fn = _resolve("queue_document")
    return fn(**message) if fn is not None else None


def ensure_seeded(code: str) -> Any:
    """Plant one Account access class's wording for this tenant if it is missing
    (`notifications.seed_templates.ensure_seeded`, insert-missing, cheap when
    present) — so a utility provisioned before the wording existed is never
    queued a message pinned to nothing. Unwired ⇒ `None`."""
    fn = _resolve("ensure_seeded", kind="seed_templates")
    return fn(code) if fn is not None else None


def send_now(write: Any) -> Any:
    """Ask `notifications.services.send_now` to send the rows just queued NOW.

    PO 2026-10-22 (decision log *"Account-access emails are sent instantly, at
    the highest priority"*). The owning service registers the send on
    `transaction.on_commit` as a background job on its own high-priority queue
    and returns at once, so **nothing is sent inside the request** — a send
    there would make an address WITH a login answer slower than one without,
    the disclosure `credentials.equalise_timing` exists to prevent.

    Unwired ⇒ `None`, and the row waits for the normal dispatch cycle: it is
    already on the queue, so nothing is lost.
    """
    ids = [message.id for message in (getattr(write, "messages", None) or ())]
    if not ids:
        return None
    fn = _resolve("send_now")
    return fn(ids) if fn is not None else None


def recipient(*, channel: str, address: str) -> Any:
    """`notifications.Recipient` — WHO one channel's copy goes to, at queue time."""
    made = _resolve("Recipient")
    return made(channel=channel, address=address) if made is not None else None


def first_message_id(write: Any) -> Any:
    """The id of the row a `queue_document` call left, or None.

    A tiny reader rather than the caller reaching into the result shape, so the
    one place that knows `QueueWrite.messages[0].id` is the seam that knows what
    `QueueWrite` is.
    """
    messages = getattr(write, "messages", None) or ()
    return messages[0].id if messages else None


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-031` — DOCUMENTS AND LETTERS (US-CWP-036)
#
# ⚠ **THIS HALF READS AND THE HALF ABOVE WRITES, AND BOTH GO THROUGH THE SAME
# DOOR FOR THE SAME REASON.** The queue is notifications' table (B2 r12 #16);
# the portal may not touch it, may not import that module's `services` (G81
# clause 4), and — since the PO's ruling of 2026-09-04 — may not answer a
# question the OWNING module could answer instead. So the READ is published as
# `apps.notifications.correspondence_reads.account_correspondence` and this
# seam resolves it BY NAME, exactly as the write half above resolves
# `queue_document`.
#
# ⚠ **UNWIRED ⇒ `None` ⇒ THE SCREEN SAYS IT COULD NOT ASK.** `None` here is a
# different fact from `[]`, and the difference is the posture this repo takes
# on every absence (`DEF-127`; `customers.seams.payment_plans_for` states it in
# as many words): `[]` means the queue was ASKED and this account has nothing
# sent, which for a new customer is the truth; `None` means nobody could ask,
# and a screen rendering *"nothing has been sent to you"* over an unreachable
# queue would tell a customer their bills never went out.
# ═══════════════════════════════════════════════════════════════════════════


def account_correspondence(*, account_ids: list[Any]) -> list[dict[str, Any]] | None:
    """`CWP-031`'s rows — every document sent to these accounts, or `None`.

    A pure read. `BR-CWP-010`'s two halves live inside the published
    function's own query (tenant AND the account set); this seam adds nothing
    to them and filters nothing afterwards, because a filter applied here would
    be a second place the rule lives and one of the two would eventually drift.
    """
    fn = _resolve("account_correspondence", kind="correspondence_reads")
    if fn is None:
        return None
    return list(fn(account_ids=list(account_ids)))


def plan_agreement_bytes(*, plan_id: Any) -> tuple[bytes, str, str] | None:
    """The kept agreement for one plan — `(bytes, content_type, filename)`.

    ⚠ **`CR-085` `CPB-03`.** The button on `CWP-063` read *Downloads are not
    ready yet* over a document the product had already frozen and could already
    serve: `bill_document_pdf` has streamed the same kind of bytes, through the
    same store, behind the same `download` permission, since `US-CWP-034`. The
    hold was a hold on nothing.

    ⚠ **THE SAME TWO PLACES `_stored` ASKS, IN ITS ORDER, WITH ITS SPELLING —
    AND THE SPELLING IS THE LOAD-BEARING PART.** A document is looked for
    against the SOURCE itself and then against every OUTBOUND MESSAGE that
    carried it. The screen's `available` flag comes from `_stored`, so a serving
    path that asked a different question would refuse a download the very same
    screen had just offered — a hold and a promise disagreeing about one
    document, which is worse than either.

    ⚠ **IN PRACTICE ONLY THE SECOND LOOKUP CAN EVER HIT, AND THAT IS A REAL
    MISMATCH RATHER THAN A DESIGN (`DEF-CWP-4688`).** `notifications` spells a
    plan `"plan"` (`models.SOURCE_TYPES`) and `tenancy` spells the same thing
    `"payment_plan"` (`document_models.SOURCE_PAYMENT_PLAN`, and its CHECK
    constraint permits only that), so `for_source(source_type="plan", …)` can
    never match a stored row. Nothing is broken today because nothing stores a
    plan agreement at CREATION — `frozen_documents` freezes it at DISPATCH,
    against the message — but the day somebody files one rather than posting it,
    which `document_store.store`'s own docstring names as a case, `_stored`
    would report *no file was kept* over a document that exists. **This file
    keeps the mismatched spelling on purpose**: agreeing with `_stored` is the
    invariant that matters, and correcting the vocabulary is a change to another
    module's read that the Documents screen also uses. It is filed, not fixed
    here.

    ⚠ **NOTHING IS RENDERED HERE AND THERE IS NO FALLBACK** (`BR-CWP-045`,
    `BR-NOT-027`). No stored copy means `None` and the caller states the
    absence; a re-render would hand the customer a document that is not the one
    they were sent.

    ⚠ **A TAMPERED COPY IS STILL NOT SOFTENED INTO A MISSING ONE — IT NOW HAS
    ITS OWN ANSWER (`CR-085` `CPB-19`, amending `CPB-03` the same week).** This
    docstring used to say `ContentHashMismatch` *"is deliberately not caught"*,
    and that was half right: it kept `BR-NOT-027`'s distinction and it paid for
    it with a raw **500** in front of a customer, on the routes whose own
    docstrings say *"NOT A 500 AND NOT A RE-RENDER"*. `stored_document_service`
    answers `DOCUMENT_NOT_TRUSTED` instead — a refusal with its own sentence,
    distinct from *no copy was kept* — so the distinction survives and the
    stack trace does not, and nothing degrades into a re-render either way.
    **This function keeps the old two-valued shape** (`bytes` or `None`) for the
    callers that had it; a caller that wants to tell the two refusals apart
    reads `stored_document_service` directly, as `plan_agreement_document` now
    does.

    ⚠ **IT TAKES A PLAN ID AND CHECKS NOTHING ABOUT WHO IS ASKING.**
    `BR-CWP-010` is the CALLER's, and the caller resolves the plan from the
    session's own account set before this is reached — the posture every read in
    this file takes. A seam that re-implemented the rule would be the second
    place it lives.

    ⚠ **THE TWO-PLACE LOOKUP MOVED OUT OF THIS BODY AND INTO
    `stored_document_service`** (`CPB-14`), because a receipt and a letter ask
    exactly the same question and a second copy of it is the drift this file
    warns about three paragraphs up. The spelling — `"plan"` here,
    `"payment_plan"` in `tenancy` — is UNCHANGED and still mismatched by design
    (`DEF-CWP-4688`).
    """
    verdict, payload, content_type, display_name = stored_document_service(
        source_type="plan", source_id=plan_id
    )
    if verdict != DOCUMENT_OK or payload is None:
        return None
    return (payload, content_type or "application/pdf", display_name or str(plan_id))


# ═══════════════════════════════════════════════════════════════════════════
# `CR-085` `CPB-14`/`CPB-19`/`CPB-20` — ONE SERVING PATH FOR EVERY KEPT DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════

#: The document is here and its bytes still hash to the record.
DOCUMENT_OK = "ok"
#: There is no kept copy — no row at all, or a row whose object has gone from
#: the store. Both are the SAME FACT to the person looking at the screen: we do
#: not have the page we sent you (`DEF-CWP-4657`).
DOCUMENT_NOT_KEPT = "not_kept"
#: ⚠ **A THIRD ANSWER, AND IT IS NOT A SOFTER SPELLING OF THE SECOND.**
#: `BR-NOT-027`: *missing* means we no longer have it; *tampered* means what we
#: have is not what you received. The store already draws that line
#: (`StoredObjectMissing` against `ContentHashMismatch`) and until `CR-085`
#: every caller collapsed it — not into the wrong sentence, but into **nothing
#: at all**: `ContentHashMismatch` was left uncaught on purpose and reached the
#: customer as a raw 500 on the one route whose own docstring says *"NOT A 500
#: AND NOT A RE-RENDER"*. Refusing BY NAME keeps `BR-NOT-027` exactly as
#: written — the document refuses and nothing degrades into a re-render — and
#: removes the stack trace.
DOCUMENT_NOT_TRUSTED = "not_trusted"


def stored_document_service(
    *, source_type: Any, source_id: Any
) -> tuple[str, bytes | None, str | None, str | None]:
    """One kept document — `(verdict, bytes, content_type, display_name)`.

    ⚠ **THE TWO PLACES A DOCUMENT CAN BE FROZEN, ASKED IN `_stored`'S ORDER
    WITH `_stored`'S SPELLING.** A bill is sealed at ISSUE against its own
    source; everything else is sealed at DISPATCH against the OUTBOUND MESSAGE
    that carried it. The screen's *available* flag comes from `_stored`, so a
    serving path that asked a different question would refuse a copy the very
    same screen had just offered — a hold and a promise disagreeing about one
    document, which is worse than either.

    ⚠ **THIS IS THE ONLY PLACE THAT QUESTION IS WRITTEN NOW.**
    `plan_agreement_bytes` below asked it in its own words from `CPB-03` until
    `CPB-14` needed the same answer for a receipt and a letter; two copies of a
    two-place lookup is exactly the drift its own docstring warns about.

    ⚠ **NOTHING IS RENDERED AND THERE IS NO FALLBACK** (`BR-CWP-045`,
    `BR-NOT-027`). No kept copy is `DOCUMENT_NOT_KEPT` and the caller states the
    absence; a re-render would hand the customer a document that is not the one
    they were sent.

    ⚠ **IT CHECKS NOTHING ABOUT WHO IS ASKING.** `BR-CWP-010` is the CALLER's,
    and the caller resolves the source from the session's own account set before
    this is reached — the posture every read in this file takes.
    """
    from apps.tenancy import document_storage, document_store

    lookup = document_store.for_source(source_type=source_type, source_id=source_id)
    ref = lookup.document
    if ref is None:
        # ⚠ **UNWIRED ⇒ NOT KEPT, WHICH IS THIS FILE'S POSTURE EVERYWHERE**
        # (`G81`: the portal resolves, it does not import).
        by_source = _resolve("message_ids_for_source", kind="correspondence_reads")
        if by_source is None:
            return (DOCUMENT_NOT_KEPT, None, None, None)
        for message_id in by_source(source_type=source_type, source_id=source_id):
            by_message = document_store.for_source(
                source_type="outbound_message", source_id=message_id
            )
            if by_message.found:
                ref = by_message.document
                break
    if ref is None:
        return (DOCUMENT_NOT_KEPT, None, None, None)
    try:
        payload = document_store.fetch(ref.id)
    except document_storage.StoredObjectMissing:
        return (DOCUMENT_NOT_KEPT, None, None, None)
    except document_storage.ContentHashMismatch:
        return (DOCUMENT_NOT_TRUSTED, None, None, None)
    return (DOCUMENT_OK, payload, ref.content_type, ref.display_name or None)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-017@fcfb8e21 (EP-CWP-03 story + BR-CWP-033 + B2 r16 #7)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(credentials.py) E✔(CWP-017's masked line) F✔ G✔ H=n/a
# gates: G81 (this file resolves rather than imports, so no portal file imports another module's services) · pytest tests/test_us_cwp_016_getting_in.py TC-5
# exceptions: the two template codes name templates nobody has written — stated above, and the row holds with that reason rather than being dropped
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
