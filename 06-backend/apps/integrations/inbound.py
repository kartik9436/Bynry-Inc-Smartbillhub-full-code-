# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-044 (EP-INT-13) — the inbound door, quadrant `in · them`:
#           they send us something. The kiosk posts a payment, replays it, and
#           sends a return carrying the same id. Screens: S142 (the run row
#           this writes); the door itself has no screen — see 2b below.
# Rules:    BR-INT-058 (THEY PUSH: the door and the work are two separate acts
#           — authenticate, dedupe, persist raw, reply fast, and STOP; the
#           apply half is the runbook's) · BR-INT-021 (authenticate before the
#           body is trusted; persist raw before processing; reply before the
#           work) · BR-INT-030 (the reply is a DECLARED position and may never
#           sit before `authenticate`) · BR-INT-020 D (the key is the provider
#           event id COMPOSITE with the reversal marker) · BR-INT-044 (the
#           source allowlist refuses before the body is read, revealing
#           nothing) · BR-INT-045 (the status numbers are the manifest's; this
#           file contains none) · BR-INT-037 / G77 (configuration is data — no
#           branch on a provider key) · BR-PAY-003 (a payment is applied
#           exactly once) · BR-PAY-036 (a payment is ALWAYS accepted) ·
#           BR-TEN-003 (the tenant is the path) · CLAUDE.md hard rule 1 · rule
#           6 · rule 7 · hard-won law 3 (fail closed) · law 14 (the SAVEPOINT)
# Tests:    06-backend/tests/test_us_int_044_inbound_door.py (TC-1..TC-10) ·
#           06-backend/tests/test_us_int_016_queue.py (the quadrant resolves
#           here)
# Impacts:  apps/integrations/inbound_api.py (the one route) · config/urls.py
#           (one include line) · apps/integrations/seams/payments.py (the
#           landing address) · apps/payments/webhooks.land_delivery (the
#           writer) · apps/integrations/runners/serve.resolve_caller (the ONE
#           machine authenticator — this file mints no second one)
# ───────────────────────────────────────────────────────
"""The inbound door: they send us something (`in · them`) — and it STOPS at the door.

WHAT THIS FILE DECIDES, in one sentence: whether a machine that is not signed
in may leave something with us, whether we have seen that something before,
and what number to answer with — and **nothing at all about what the something
means**.

⚠ **THE BOUNDARY IS RULED AND IT IS THE MOST IMPORTANT PARAGRAPH HERE
(`BR-INT-058`, PO 2026-09-06, `OQ-INT-1729` option (a)).** PO, verbatim, on
the line between the two: *"I want integration to just make the conenction nad
manage the conenction, Runbooks will handle the logic , ETL and record
udaptes, and we will abel to keep record, audit of it as part of runbooks."*

    INTEGRATIONS KEEPS          RUNBOOKS TAKES
    ------------------          --------------
    authenticate                record_payment with channel KIOSK
    dedupe (the composite key)  the reversal row a return produces
    reply (200 / 409)           DRIVEUP -> OTHER
    persist raw                 showing the risk flag to a clerk

⚠ **AMENDED 2026-10-07 (`CR-174-BRC10`) — THE LINE ABOVE MOVED FOR ONE KIND
OF OPERATION, BY RULING, AND STAYS WHERE IT WAS FOR EVERY OTHER.** PO, verbatim,
on US Payments: *"(a). A person standing at a machine needs the live balance.
Runbooks still handle the exceptions in D2."* An operation may now DECLARE
that it applies (`Operation.applies`, replying after `apply`), and for that
operation alone this door lands the message AND posts it, inside one
transaction, through payments' own `agent_door` — see `_apply_door` below.
**The kiosk (`payments_kiosk`) declares nothing and still applies nothing**;
its boundary test stands, and the paragraph that follows is still exactly true
of it.

**No payment is written here and none may be added here.** `runbooks_apply()`
at the foot of this file is the named seam the apply half plugs into; it
returns `None` today and `test_us_int_044_inbound_door.py` asserts that it
does, so the boundary goes RED the day somebody closes it rather than closing
silently. It is a **deliberate absence and not a stub** (`OQ-1396`'s
distinction): it raises nothing, blocks nothing and names no open question,
because nothing is unruled.

⚠ **THE REASON IS OPERATIONAL, AND WRITING IT DOWN IS PART OF THE RULE:** the
vendor is holding a socket open and will re-send if we are slow, so answering
the door must never wait on processing. Fold the two halves back together and
a slow runbook becomes a duplicate delivery from every vendor at once — not a
slow screen, but a correctness failure on a money path arriving as a retry
storm exactly when the system can least absorb it.

THE PIPELINE, AND WHY THE ORDER IS EVERY WORD OF IT
----------------------------------------------------
    receive -> authenticate -> dedupe -> persist -> apply
                    ^            ^         ^          ^
                    |            |         |          Runbooks'
                    |            +---------+ ONE ACT (see below)
                    the body has not been read yet

**1 · Authenticate BEFORE the body is read.** Not a style preference: an
unauthenticated caller must not be able to make us parse arbitrary input.
`receive()` takes `raw_body` as BYTES and does not touch them until
`resolve_caller` has returned. TC-4 asserts it by handing in bytes that would
raise if parsed.

**2 · The dedupe and the persist are ONE ACT.** The composite key is
`K-88231|payment` vs `K-88231|return` (`BR-INT-020` D — a return carries the
same provider id as the payment it reverses, so their id alone would refuse
every return as a duplicate of its own payment), and
`uq_payment_webhook_events_event` is what decides whether we have seen it. An
INSERT the index refuses IS the duplicate verdict. That is not a shortcut:
a SELECT-then-INSERT leaves a race open between two concurrent deliveries of
the same event, and doing it this way also puts the raw envelope on disk
before the reply goes out, which is what `BR-INT-021` asks for.

**3 · The reply sits where the OPERATION says.** The kiosk's payments and
returns answer after `dedupe`, so a replay is told `409` **before anything is
posted**; its account lookup answers after `authenticate`. The registry
refuses a manifest whose reply sits before `authenticate` at load, so this
file never checks it. **The numbers are `Operation.envelope_status` and this
file contains none** (`BR-INT-045`) — grep it: there is no `200`, no `409`
and no `401` in the code below.

**4 · The apply does not happen here at all.**

NOTHING IN THIS FILE KNOWS WHICH PROVIDER IT IS SERVING
--------------------------------------------------------
Four things a door needs are read as DATA off the manifest, because a door
that knew them any other way would be a branch on a provider key (G77,
`BR-INT-037` — *"every time such integration comes we dont want to change our
integration framework"*):

  * `auth.inbound.style` — HOW this partner proves it is them: `presented_key`
    (a credential in a header), `signature` (a digest over the body) or
    `basic` (the HTTP Basic scheme). ⚠ **THIS LIST READ *THREE THINGS* AND
    NAMED ONLY THE FIRST STYLE UNTIL 2026-09-17**, because the door had only
    one and nothing said so; `DEF-INT-5628` is what that cost.
  * `auth.placement` + `auth.header` — for `presented_key`, WHERE the
    credential is and WHICH header carries it (`X-Kiosk-Key`);
  * `idempotency.key_field` — WHICH body field carries the provider's own
    event id (`eventId`);
  * `idempotency.natural_key` — whether this operation's key carries the
    reversal marker.

**All four fail CLOSED** (hard-won law 3). A manifest that places its
credential in a header and names none, an operation that must dedupe and
declares no field to dedupe on, and a signature style whose secret is not
stored are each refused — because the alternative is a door that guesses at a
header, one that treats *"I could not find an id"* as *"this is new"* and lets
a replayed payment through, or one that treats *"there is no key to check
against"* as *"this one needs no checking"*.

ONE AUTHENTICATOR, NOT TWO
---------------------------
⚠ **THE KEY CHECK IS `runners/serve.resolve_caller()` AND THIS FILE DOES NOT
MINT A SECOND ONE.** Wave R found the same thing from the other side and its
docstring says why: two resolvers would be two answers to *may this machine
in* drifting apart in silence, which is the one shape a security control must
never take. `resolve_caller` already has no early return, folds the allowlist
into the same decision, and pads the refusal to a floor so the three ways of
being turned away cannot be told apart by timing them. The direction differs —
wave S is a partner READING from us, this is a kiosk WRITING to us — and
nothing about *is this machine who it says it is* differs with the direction.

⚠ **AND IT IS STILL ONE AUTHENTICATOR AFTER THE THREE STYLES (2026-09-17).**
`verify()` below answers ONE question — *what did this caller prove knowledge
of* — and hands that value to `resolve_caller` as `presented_key`. A header
gives it directly; the Basic scheme gives it after a base64 decode; a
symmetric signature gives it because recomputing the digest proves the sender
knew the same bytes we hold. **Every guard that decides whether a machine may
come in is still applied in exactly one place**, and a failed verification
answers `None` rather than raising, so it joins the same refusal, the same
record and the same 40-millisecond floor.

The one thing that does differ is WHERE the key sits: wave S's partner sends
`Authorization: Bearer`, the kiosk sends `X-Kiosk-Key`. That is the whole of
the difference, and it is a manifest field.

WHAT IS *NOT* HERE (2b, stated rather than left silent)
---------------------------------------------------------
**This wave builds NO SCREEN, and that is a finding rather than a deferral.**
A kiosk POSTs to a door; there is nobody at it. Everything `N3` listed for a
screen turns out to display facts that only the apply half writes — the
payment's channel and reference, the report that separates counter takings
from kiosk takings, the red `DRIVEUP` row — so all of it moved with
`record_payment` and none of it can be built while the payment is not written.
What a person DOES see is already built and needs nothing: every landing
writes an `IntegrationRun` row, and S142 (`ConnectionDetailPage`) draws those
today, grouped by the operation's own label — *Payments · Account lookup ·
Returns*.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from apps.integrations import mappings, models, services, webhook_secrets
from apps.integrations.adapters.base import Adapter
from apps.integrations.registry import (
    APPLY_ACCOUNT_LOOKUP,
    GUARD_PIPELINE,
    REGISTRY,
    VERIFY_BASIC,
    VERIFY_PRESENTED_KEY,
    VERIFY_SIGNATURE,
    Manifest,
    Operation,
    Registry,
)
from apps.integrations.runners import serve
from apps.integrations.seams import notifications as notifications_seam
from apps.integrations.seams import payments as payments_seam
from apps.integrations.seams import tenancy as tenancy_seam

logger = logging.getLogger(__name__)

#: The five positions, imported from the registry so this file and the
#: manifest validation cannot disagree about their order.
PIPELINE = GUARD_PIPELINE

#: The two halves of the composite key's second field (`BR-INT-020` D). A
#: RETURN carries the same provider id as the payment it reverses, so the key
#: has to say which of the two this is or every return is refused as a
#: duplicate of its own payment. The marker is derived from the operation's
#: DECLARED `natural_key`, never from its name.
MARKER_PAYMENT = "payment"
MARKER_REVERSAL = "return"
REVERSAL_NATURAL_KEY_SUFFIX = "+reversal"

#: The declared `natural_key` spelling that means *this operation reverses
#: something*. Matched as a suffix so `event_id+reversal` and any future
#: `<something>+reversal` both read correctly.
#:
#: ⚠ A MARKER THAT IS NOT PART OF THE STORED KEY IS NOT A KEY AT ALL. The
#: whole point is that `K-88231|payment` and `K-88231|return` are two rows
#: under `uq_payment_webhook_events_event`, so the reversal is not mistaken
#: for a duplicate — `US-INT-044` TC-3, and the phase-5 exit test.
KEY_SEPARATOR = "|"

#: The batch shapes the door accepts. A kiosk usually posts ONE notification;
#: `US-INT-044` TC-9 posts two in one call, which is where the savepoint
#: earns its place. Both are landed the same way — one item at a time, each in
#: its own savepoint — so there is no "batch path" to diverge from the single
#: one.
BATCH_KEYS = ("payments", "returns", "items", "notifications")

#: Per-item outcomes, as CODES a caller groups on rather than prose it parses.
ITEM_LANDED = "landed"
ITEM_DUPLICATE = "duplicate"
ITEM_NO_KEY = "no_event_id"


class DoorRefused(Exception):
    """The one refusal, and it carries no reason ON PURPOSE.

    It is `serve.PartnerRefused`'s sibling and it says the same five words. An
    address off the allowlist, a wrong key, a revoked key, an unknown provider
    and an operation this provider does not declare must all be the same bytes
    with the same status: anything else is an oracle a caller holding a stolen
    key can read.
    """

    def __init__(self) -> None:
        super().__init__(serve.REFUSAL_SENTENCE)


class DoorRateLimited(Exception):
    """Too many calls this minute (`CR-110-BRC04`).

    ⚠ **DISTINCT FROM `DoorRefused`, AND THAT IS SAFE RATHER THAN A LEAK** —
    the same argument `serve.PartnerRateLimited` makes at length. A `429` is
    only reachable by a caller who has ALREADY authenticated, so it tells them
    one thing they already know. An unauthenticated caller can hammer this door
    all day and see nothing but `DoorRefused`.

    ⚠ **IT MUST NOT BE FOLDED INTO `DoorRefused` "FOR CONSISTENCY".** The kiosk
    network reads the OUTCOME off the status: a `401` means *my key is wrong,
    stop and page somebody*, and a `429` means *slow down and come back*. A
    machine told the first when the second is true stops sending payments
    until a person intervenes.
    """

    def __init__(self, retry_after_s: int = serve.RETRY_AFTER_S) -> None:
        super().__init__(serve.REFUSAL_SENTENCE)
        self.retry_after_s = int(retry_after_s)


class DoorMisconfigured(Exception):
    """A manifest that cannot be served, refused CLOSED and BY NAME.

    ⚠ **DISTINCT FROM `DoorRefused`, AND THE DIFFERENCE IS WHO IS AT FAULT.**
    A caller can never provoke this: it fires only when OUR OWN manifest does
    not say where the credential is or where the event id is. It is a
    deployment error, it names the provider, the operation and the missing
    field, and the door serves nobody until it is fixed — which is the safe
    direction (hard-won law 3). The alternative is a door that guesses a
    header name, or one that reads *"no id found"* as *"this is new"* and
    applies a replayed payment.

    ⚠ It is deliberately NOT a load-time refusal; `registry.Idempotency
    .key_field` records why in full, and the short version is that demanding
    the field of every manifest would put dead data on `payments_sandbox`,
    whose event id never travels in a body at all.
    """


@dataclass(frozen=True)
class LandedItem:
    """One notification inside one delivery."""

    event_id: str | None
    key: str | None
    state: str

    def envelope(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "key": self.key, "state": self.state}


@dataclass(frozen=True)
class InboundReply:
    """What the door will answer, and what it did.

    `status` is the manifest's number for `outcome` and is looked up rather
    than typed (`BR-INT-045`).
    """

    provider_key: str
    operation: str
    outcome: str
    status: int
    items: tuple[LandedItem, ...] = ()
    run_id: str | None = None
    #: What this door did NOT do, on every result. The same discipline
    #: `payments/webhooks.py` keeps with `WEBHOOK_UNAVAILABLE`: a reader of
    #: this envelope should never have to infer an absence.
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    #: `CR-174-BRC10` — an operation that APPLIES answers in the partner's own
    #: words (`{"accountValid": false}`, `{"received": true}`), already
    #: composed; the view sends it instead of the door's envelope.
    answer: Mapping[str, Any] | None = None

    def envelope(self) -> dict[str, Any]:
        if self.answer is not None:
            return dict(self.answer)
        return {
            "provider": self.provider_key,
            "operation": self.operation,
            "status": self.outcome,
            "items": [one.envelope() for one in self.items],
            "problems": list(self.problems),
        }


#: On every reply, because a partner integrating against this door has to know
#: where the work stops (`BR-INT-058`).
DOOR_STOPS_HERE: tuple[dict[str, Any], ...] = (
    {
        "code": "landed_not_applied",
        "br_ref": "BR-INT-058",
        "detail": "this door authenticates the caller, refuses a repeat, saves exactly what "
        "arrived and replies. Applying it — recording the payment, writing the reversal row, "
        "resolving the tender word — happens afterwards and is not part of this answer. A "
        "success here means WE HAVE IT, not that it has been posted.",
    },
)


# ═══════════════════════════════════════════════════════════════════════════
# What the manifest declares, read as data
# ═══════════════════════════════════════════════════════════════════════════


def operation_named(manifest: Manifest, name: str) -> Operation | None:
    for one in manifest.operations:
        if one.name == name:
            return one
    return None


def credential_header(manifest: Manifest) -> str:
    """The header this provider's key arrives in (`BR-INT-037`).

    Refuses CLOSED when the manifest places a credential in a header and does
    not name it: a door that fell back to a guess would authenticate against
    the wrong header on the day a provider changed it, and the symptom —
    every valid key refused — is indistinguishable from a wrong key.
    """
    auth = manifest.auth
    if auth.placement == "bearer":
        return "Authorization"
    if auth.placement == "header":
        if not auth.header:
            raise DoorMisconfigured(
                f"{manifest.key} places its credential in a header and names none. "
                "Declare `Auth(..., header=\"X-...\")` on the manifest; the door will not "
                "guess which header carries a key."
            )
        return auth.header
    raise DoorMisconfigured(
        f"{manifest.key} authenticates by {auth.placement!r}, which this door cannot read. "
        "An inbound door reads a credential from a header or a bearer token."
    )


def presented_key(manifest: Manifest, headers: Mapping[str, Any]) -> str | None:
    """The key the caller presented, read from the header the manifest names.

    `headers` is `request.META` — Django's WSGI spelling (`HTTP_X_KIOSK_KEY`).
    A `bearer` placement strips the scheme; a plain header does not, because
    the value IS the key.
    """
    name = credential_header(manifest)
    raw = headers.get("HTTP_" + name.upper().replace("-", "_"))
    if not raw:
        return None
    value = str(raw).strip()
    if name.lower() == "authorization":
        prefix = "bearer "
        if not value.lower().startswith(prefix):
            return None
        value = value[len(prefix) :].strip()
    return value or None


# ═══════════════════════════════════════════════════════════════════════════
# THREE WAYS A PARTNER PROVES IT IS THEM — declared, never branched on
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS DOOR HAD EXACTLY ONE WAY UNTIL 2026-09-17, AND IT IS THE ONE A
# WHOLE CLASS OF WEBHOOK CANNOT USE** (`DEF-INT-5628`). `presented_key` reads
# a credential out of a header. **SendGrid presents no credential at all: it
# SIGNS THE BODY**, and Postmark puts HTTP Basic credentials in the URL. So the
# only way to accept either call was to turn authentication off — on a route
# that writes delivery state.
#
# The style is `registry.INBOUND_VERIFICATIONS`, declared on the manifest,
# refused at LOAD by name when it is outside the list. There is no
# `if key == "sendgrid"` here and `G77` would fail one (`BR-INT-037`).


def basic_password(headers: Mapping[str, Any]) -> str | None:
    """The PASSWORD half of `Authorization: Basic base64(user:password)`.

    ⚠ **THE PASSWORD IS A KEY WE MINTED, WHICH IS WHY `basic` NEEDS NO NEW
    AUTHENTICATOR.** Postmark's basic credentials go in the URL WE give it, so
    both halves are ours to choose; the password is issued through
    `machine_auth` like any other partner key and carries the same blind index.
    `basic` is therefore a TRANSPORT — the credential arrives under the Basic
    scheme instead of in a header we name — and the value goes to
    `serve.resolve_caller` exactly as a header-borne key does.
    ⚠ **THE USERNAME IS NOT CHECKED AND MUST NOT BECOME A SECOND SECRET.** It
    is a label; the entropy is all in the password. Comparing it too would add
    a second comparison whose failure is indistinguishable from the first and
    which nothing could tell a clerk about.

    `None` for a missing header, a different scheme, base64 that will not
    decode, bytes that are not UTF-8, or no `:` at all — every one of which is
    the same refusal, because they are all *this caller did not present a key*.
    """
    import base64

    raw = headers.get("HTTP_AUTHORIZATION")
    if not raw:
        return None
    value = str(raw).strip()
    prefix = "basic "
    if not value.lower().startswith(prefix):
        return None
    try:
        decoded = base64.b64decode(value[len(prefix) :].strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    # `split(":", 1)` and not `rsplit`: a password may contain a colon, a
    # username may not (RFC 7617 says so in as many words).
    _username, password = decoded.split(":", 1)
    return password or None


def signature_verified_secret(
    manifest: Manifest,
    headers: Mapping[str, Any],
    raw_body: bytes,
    *,
    received_at: datetime,
    secret: str | None,
) -> str | None:
    """Does this body carry a signature only the holder of `secret` could make?

    Answers the SECRET ITSELF when it verifies and `None` when it does not, so
    the caller can hand what was proved to the one authenticator. With a
    symmetric HMAC that answer is literally true: recomputing the digest proves
    the sender knew the same bytes we hold, which is the same statement
    `presented_key` makes about a key that arrived in a header.
    **`registry.SIGNATURE_ALGORITHMS` is symmetric-only for exactly this
    reason**, and it refuses anything else BY NAME at load.

    ⚠ **THE BODY IS HASHED, NEVER PARSED, AND THAT IS WHAT KEEPS `BR-INT-021`
    TRUE.** The rule is that an unauthenticated caller must not be able to make
    us parse arbitrary input. `hmac.new(...).digest()` over bytes is fixed work
    on any input — there is no grammar, no recursion and nothing to exhaust —
    so hashing before authenticating is not *trusting* the body. `receive()`
    still does not call `_parsed` until this has returned, and the test asserts
    it by replacing the parser with a recorder and requiring the recording to
    be empty.

    WHAT WOULD MAKE THIS CHECK PASS WRONGLY — asked, because law 7 says a check
    you cannot describe a false pass for is a check you do not understand:

      1. **A MISSING SIGNATURE HEADER READ AS A MATCH.** The classic. `None ==
         None` is true, and an empty header compared against an empty computed
         digest is true in any implementation that forgets to demand one. Both
         are refused here BEFORE anything is computed, and
         `test_a_missing_signature_is_refused` proves it red.
      2. **A MISSING SECRET READ AS *NO VERIFICATION NEEDED*.** `secret` is
         `None` when nothing is stored — a connector half set up — and that is
         a REFUSAL, never a pass (hard-won law 3).
         ⚠ **THIS ONE IS DEFENDED TWICE AND THE SECOND DEFENCE IS THE DESIGN
         RATHER THAN A CHECK.** Putting the mistake back in — an early
         `return "anything"` on a missing secret — does NOT let a caller in,
         and the two tests for it stay green. This function does not answer
         *yes*; it answers WHAT THE CALLER PROVED KNOWLEDGE OF, and that value
         then has to identify a real credential row through `resolve_caller`'s
         blind index. Invented bytes hash to no credential, so the one
         authenticator refuses them exactly as it would a wrong key. **Do not
         "simplify" that away**: a verifier that returned a boolean would make
         this false pass reachable in one edit. Transcript in the decision log,
         2026-09-17.
      3. **A TIMESTAMP NOBODY AGES.** A signature over `timestamp + body` is
         valid for ever if the timestamp is only concatenated and never
         compared, so one captured call replays at any time and verifies
         perfectly. The window is `max_skew_seconds`, the manifest has to
         declare it, and the comparison is `abs()` — a future timestamp is as
         refused as a stale one, or a caller buys itself an unlimited window by
         dating its replay next year.
      4. **A `==` INSTEAD OF `compare_digest`.** A plain comparison returns as
         soon as two bytes differ, so a caller can recover a valid digest one
         byte at a time by timing it. `hmac.compare_digest` is constant-time
         and is the only comparison in this function.
      5. **A DECODE THAT RAISES BEING TREATED AS A CRASH RATHER THAN A
         REFUSAL.** Rubbish in the signature header is a refusal, not a 500.

    ⚠ **A SIGNATURE REFUSAL IS NOT PADDED HERE AND DOES NOT NEED TO BE.** It
    answers `None`, and `receive()` then hands `None` to `serve.resolve_caller`,
    which does all of its work anyway, records the refusal and pads it to
    `REFUSAL_FLOOR_S`. So there is ONE refusal path with ONE floor, rather than
    a second one in this file that would drift from it.
    """
    import base64
    import binascii
    import hashlib
    import hmac

    declared = manifest.auth.inbound
    if declared is None or declared.style != VERIFY_SIGNATURE:
        return None
    if not secret:
        return None
    presented = headers.get("HTTP_" + str(declared.signature_header).upper().replace("-", "_"))
    if not presented:
        return None
    presented = str(presented).strip()
    if not presented:
        return None

    signed = raw_body
    if declared.signs_a_timestamp:
        stamp = headers.get("HTTP_" + str(declared.timestamp_header).upper().replace("-", "_"))
        if not stamp:
            return None
        try:
            sent_at = int(str(stamp).strip())
        except ValueError:
            return None
        skew = abs(int(received_at.timestamp()) - sent_at)
        if skew > int(declared.max_skew_seconds or 0):
            return None
        signed = str(sent_at).encode("utf-8") + raw_body

    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
    try:
        if declared.encoding == "base64":
            offered = base64.b64decode(presented, validate=True)
        else:
            offered = binascii.unhexlify(presented)
    except (ValueError, binascii.Error):
        return None
    if not hmac.compare_digest(expected, offered):
        return None
    return secret


def verify(
    manifest: Manifest,
    headers: Mapping[str, Any],
    raw_body: bytes,
    *,
    received_at: datetime,
) -> str | None:
    """WHAT THE CALLER PROVED KNOWLEDGE OF — or `None`, which is a refusal.

    One function, three declared styles, no provider key anywhere in it. The
    answer goes straight to `serve.resolve_caller` as `presented_key`, so the
    six guards that decide whether a machine may come in — unknown, revoked,
    expired, address, connector off, scope, utility live — go on being applied
    by the one function that has always applied them. **This file still mints
    no second authenticator**; what it now does is read three kinds of proof
    instead of one.

    ⚠ **`None` IS HANDED ON RATHER THAN RAISED HERE, ON PURPOSE.**
    `resolve_caller` has no early return, computes every guard whatever the
    first says, writes the refusal record and holds the answer to the
    40-millisecond floor. Raising from here would be a refusal that skipped all
    of that and came back faster — the timing oracle `BR-INT-044` exists to
    close, arriving through the fix for something else.
    """
    declared = manifest.auth.inbound
    if declared is None or declared.style == VERIFY_PRESENTED_KEY:
        return presented_key(manifest, headers)
    if declared.style == VERIFY_BASIC:
        return basic_password(headers)
    if declared.style == VERIFY_SIGNATURE:
        found = webhook_secrets.secret_for(manifest)
        return signature_verified_secret(
            manifest,
            headers,
            raw_body,
            received_at=received_at,
            secret=None if found is None else found.secret,
        )
    # Unreachable: `registry.validate` refuses an unknown style at LOAD. It is
    # a refusal rather than a fall-through because the safe answer to *a style
    # nobody implemented* is nobody gets in (hard-won law 3), and because a
    # silent `return None` here would look exactly like a wrong key for ever.
    raise DoorMisconfigured(  # pragma: no cover — the registry refuses it first
        f"{manifest.key} declares inbound verification style "
        f"{declared.style!r}, which this door does not implement."
    )


def reversal_marker(operation: Operation) -> str:
    """`payment` or `return`, from the operation's DECLARED natural key.

    Never from `operation.name`: a provider free to call its operation
    anything would break a door that read the name, and G77 refuses that shape
    for exactly this reason.
    """
    natural = (operation.idempotency.natural_key or "") if operation.idempotency else ""
    return MARKER_REVERSAL if natural.endswith(REVERSAL_NATURAL_KEY_SUFFIX) else MARKER_PAYMENT


def dedupe_key(operation: Operation, event_id: str) -> str:
    """`BR-INT-020` D — the provider's event id, COMPOSITE with the marker.

    `K-88231|payment` and `K-88231|return` are two different keys, which is
    the whole of why a return is not mistaken for a duplicate of the payment
    it reverses. This is the phase-5 exit test in one line.
    """
    return f"{event_id}{KEY_SEPARATOR}{reversal_marker(operation)}"


def event_id_of(operation: Operation, item: Mapping[str, Any]) -> str | None:
    """The provider's own id, out of the field the manifest names.

    Answers `None` when the field is absent from THIS item — that is a bad
    notification, not a bad manifest, and the caller records it refused
    (`ITEM_NO_KEY`) and carries on with the rest of the batch. A manifest that
    names no field at all is a different fault and raises.
    """
    key_field = (operation.idempotency.key_field or "") if operation.idempotency else ""
    if not key_field:
        raise DoorMisconfigured(
            f"operation {operation.name!r} replies at {operation.respond_after!r} and its "
            "manifest declares no `idempotency.key_field`, so there is nothing to dedupe "
            "on. Declare which body field carries the provider's event id; the door will "
            "not treat a missing id as a new notification."
        )
    raw = item.get(key_field)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def status_for(operation: Operation, outcome: str) -> int:
    """`BR-INT-045` — the number is the manifest's and this file holds none."""
    declared = (operation.envelope_status or {}).get(outcome)
    if declared is None:
        raise DoorMisconfigured(
            f"operation {operation.name!r} declares no {outcome!r} status. The envelope's "
            "numbers are the manifest's (BR-INT-045) and this door contains none."
        )
    return int(declared)


def items_in(operation: Operation, body: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """One notification, or a batch of them, as a tuple either way.

    ⚠ THERE IS NO SEPARATE BATCH PATH, DELIBERATELY. A single notification is
    a batch of one and is landed by the same loop with the same savepoint, so
    the case that only shows up on PostgreSQL under load (TC-9) is exercised
    by every single-item test that has ever run. A second code path for one
    item would be the path everybody tests and the batch path the one that
    breaks.
    """
    for name in BATCH_KEYS:
        found = body.get(name)
        if isinstance(found, (list, tuple)):
            return tuple(one for one in found if isinstance(one, Mapping))
    return (body,)


# ═══════════════════════════════════════════════════════════════════════════
# The door
# ═══════════════════════════════════════════════════════════════════════════


def receive(
    *,
    provider_key: str,
    operation_name: str,
    presented: str | None,
    source_address: str | None,
    raw_body: bytes,
    received_at: datetime,
    registry: Registry = REGISTRY,
    method: str = "POST",
    headers: Mapping[str, Any] | None = None,
    query: Mapping[str, Any] | None = None,
) -> InboundReply:
    """Land one delivery. Authenticate, dedupe, persist raw, reply — and stop.

    `method`, `headers` and `query` (`CR-174-BRC10`) are read only AFTER the
    caller is authenticated: the verb must be the operation's declared one,
    an identity header the partner sends must match the utility's own copy,
    and a `GET` lookup carries its account in the query string.

    ⚠ **`raw_body` IS NOT TOUCHED UNTIL `resolve_caller` HAS RETURNED**, and
    that is the ordering `BR-INT-021` is about: an unauthenticated caller must
    not be able to make us parse arbitrary input. The bytes are carried, not
    read, through the first half of this function. `US-INT-044` TC-4 proves it
    by handing in bytes that are not JSON at all and asserting the refusal is
    byte-identical to the one a valid body gets.

    ⚠ **NO EARLY RETURN BEFORE THE REFUSAL.** `resolve_caller` does all three
    of its checks whatever the first says and raises once; the unknown-manifest
    and unknown-operation cases below join the SAME refusal rather than
    answering *"no such provider"*, which would tell a caller which utilities
    have which connectors.

    Raises `DoorRefused` for anything a caller did wrong and
    `DoorMisconfigured` for anything WE did wrong. Everything else is a
    RESULT with its reason — a kiosk retrying a 500 forever over one bad
    notification helps nobody (`BR-PAY-036`: a payment is always accepted).
    """
    manifest = registry.get(provider_key)
    operation = operation_named(manifest, operation_name) if manifest is not None else None
    if manifest is None or operation is None or not operation.they_call_us:
        # The same five words a wrong key gets. A caller learns nothing about
        # which providers exist or which operations they declare.
        raise DoorRefused()

    # ── 1 · authenticate — before the body is read ─────────────────────────
    #
    # ⚠ `operation=operation.name` IS THE SCOPE GUARD (`CR-110-BRC04`), AND
    # THIS DOOR IS THE ONE IT WAS WRITTEN FOR. The blueprint's own words
    # (p017, `CR-4`): *"a partner handed a key to push meter readings can call
    # every other inbound API on that connector — because there is no field
    # that says which ones they may call."* The kiosk network is one of the six
    # connectors that hold a key of ours; before this, its key opened all three
    # of its operations and would have opened a fourth the day one was added.
    try:
        caller = serve.resolve_caller(
            provider_key=provider_key,
            presented_key=presented,
            source_address=source_address,
            operation=operation.name,
        )
    except serve.PartnerRefused as refused:
        raise DoorRefused() from refused

    # ── 1b · the call limit ────────────────────────────────────────────────
    #
    # ⚠ **THIS DOOR HAD NO LIMIT AT ALL UNTIL `CR-110-BRC04`, AND THAT IS THE
    # HALF OF THE PO'S HACKING CASE NOBODY HAD COUNTED** (`DEF-INT-5503`).
    # `partner_api._serve` metered the two READ routes; this one — the door a
    # payment machine posts money events at, with no session and no person —
    # metered nothing, so the ceiling on it was the web server's. It is
    # refused BEFORE the body is parsed, for the same reason authentication is:
    # an unauthenticated flood must never cost us a JSON parse.
    #
    # A `429` rather than the five-word refusal, and that is safe: it is only
    # reachable by a caller who has ALREADY authenticated, so it tells them one
    # thing they already know (`serve.PartnerRateLimited` says so at length).
    try:
        serve.check_rate_limit(caller, operation=operation.name, registry=registry)
    except serve.PartnerRateLimited as limited:
        raise DoorRateLimited(limited.retry_after_s) from limited

    # ── 1c · the verb and the partner's own name for the utility ───────────
    #
    # `CR-174-BRC10`. Both after authentication, so neither can be used to
    # learn anything about a key: a caller reaching them already holds one.
    # Both join the ONE refusal — a wrong verb and a wrong enterprise id are a
    # caller doing something we do not serve, and saying which would be an
    # oracle for no benefit.
    if str(method or "POST").upper() != operation.http_method:
        raise DoorRefused()
    if not _identity_matches(manifest, caller, headers or {}):
        raise DoorRefused()

    # ── an operation that APPLIES (`CR-174-BRC10`, PO D1) ───────────────────
    if operation.applies is not None:
        return _apply_door(
            caller,
            manifest,
            operation,
            raw_body=raw_body,
            query=query or {},
            received_at=received_at,
            registry=registry,
        )

    # ── the reply may sit here (`respond_after = authenticate`) ────────────
    if operation.respond_after == "authenticate":
        return _answered_at_authenticate(caller, operation, manifest, registry)

    # ── 2 · the body, now that we know who is calling ──────────────────────
    body = _parsed(raw_body)

    # ── 3 · dedupe AND persist raw, one item at a time, each in a savepoint ─
    landed: list[LandedItem] = []
    for item in items_in(operation, body):
        landed.append(
            _land_one(manifest.key, operation, item, received_at=received_at)
        )

    # ── 4 · the run row a manager reads on S142 ────────────────────────────
    run = _record_landing(caller, operation, landed, registry=registry)

    # ── 5 · reply, with the manifest's own number ──────────────────────────
    outcome = _outcome_of(landed)
    return InboundReply(
        provider_key=provider_key,
        operation=operation.name,
        outcome=outcome,
        status=status_for(operation, outcome),
        items=tuple(landed),
        run_id=None if run is None else str(run.id),
        problems=DOOR_STOPS_HERE,
    )
    # ── 6 · apply — NOT HERE. `runbooks_apply()` is the seam; see the
    #        module docstring and BR-INT-058. Nothing calls it yet and
    #        nothing in this module may.


def _answered_at_authenticate(
    caller: serve.PartnerCaller,
    operation: Operation,
    manifest: Manifest,
    registry: Registry,
) -> InboundReply:
    """An operation whose reply sits at `authenticate` — the kiosk's account
    lookup. The caller is admitted and **the answer's CONTENT is Runbooks'.**

    ⚠ THIS IS WHY THE BODY IS NOT PARSED ON THIS BRANCH. Composing *what is
    owed on ACC-1048* is building a business record for somebody else, which
    `CR-069` §20.4 and §20.9.4 both put on the Runbooks side — the same
    argument that makes `serve.partner_fields()` return `{}`. So the door
    admits the caller, writes the access row a manager reads, and hands back
    an envelope with no account in it. When Runbooks lands, `runbooks_apply()`
    fills this in and the test that asserts the absence goes red.

    ⚠ AND THE `not_found` NUMBER IS **200**, NOT 404 (`DEF-INT-4257`). It is
    read off the manifest here so that a future edit of either the manifest or
    `US-INT-044` TC-7 cannot drift from the other unnoticed.
    """
    run = services.finish_run(
        services.start_run(
            connection=caller.connection,
            operation=operation.name,
            direction=models.RUN_DIRECTION_INBOUND_READ,
            trigger="partner",
            registry=registry,
        ),
        attempted=0,
        succeeded=0,
        failed=0,
        skipped=0,
        confirmed=True,
        never_dialled=True,
        summary=f"{operation.label} · asked · {caller.hint}",
    )
    return InboundReply(
        provider_key=manifest.key,
        operation=operation.name,
        outcome="ok",
        status=status_for(operation, "ok"),
        run_id=str(run.id),
        problems=DOOR_STOPS_HERE
        + (
            {
                "code": "answer_is_runbooks",
                "br_ref": "BR-INT-054",
                "detail": "what is owed on an account is a business record composed from our "
                "data, which BR-INT-054 puts in Runbooks. The caller is authenticated and the "
                "read is recorded; the balance is not built here and is not built yet.",
            },
        ),
    )


def _parsed(raw_body: bytes) -> dict[str, Any]:
    """The body as a dict, or `{}`.

    A body that will not parse is still a delivery from an AUTHENTICATED
    caller, so it answers `{}` rather than raising and every item in it is
    then recorded `no_event_id` by name. The alternative — a 500 — makes the
    kiosk retry a malformed notification for ever.
    """
    import json

    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _land_one(
    provider_key: str,
    operation: Operation,
    item: Mapping[str, Any],
    *,
    received_at: datetime,
) -> LandedItem:
    """Dedupe and persist ONE notification.

    ⚠ THE SAVEPOINT IS ONE LAYER DOWN, IN `payments.webhooks.land_delivery`,
    BESIDE THE INSERT IT PROTECTS (CLAUDE.md law 14). This loop therefore
    survives an item the unique index refuses, and the items before it stay
    committed. **On SQLite that is true without the savepoint, which is why
    the proof for it is a `requires_postgres` test and not a green suite.**
    """
    event_id = event_id_of(operation, item)
    if event_id is None:
        # A notification with no id cannot be deduped, so it is refused BY
        # NAME rather than landed. Treating it as new is the one outcome that
        # would let a replayed payment through (hard rule 6).
        return LandedItem(event_id=None, key=None, state=ITEM_NO_KEY)
    key = dedupe_key(operation, event_id)
    landing = payments_seam.land_inbound_delivery(
        # The provider half of the dedupe key is the MANIFEST key, threaded in
        # from `receive` rather than looked up: `uq_payment_webhook_events_event`
        # is `(tenant, provider, event_id)`, so two providers may both number an
        # event `1` and neither collides with the other.
        provider=provider_key,
        event_id=key,
        body=dict(item),
        received_at=received_at,
        audit_after={"job": "integrations.inbound_door", "operation": operation.name},
    )
    return LandedItem(
        event_id=event_id,
        key=key,
        state=ITEM_LANDED if landing.landed else ITEM_DUPLICATE,
    )


def _outcome_of(landed: Sequence[LandedItem]) -> str:
    """`ok` or `duplicate` — and the second only when NOTHING was new.

    ⚠ **A MIXED BATCH ANSWERS `ok`, AND THE ASYMMETRY IS DELIBERATE.** `409`
    tells a kiosk *we already have this, stop re-sending*; answering it while
    one item WAS new would tell the kiosk to stop re-sending a notification we
    have never seen. `ok` with the per-item states in the body is the honest
    answer, and the states say which was which.
    """
    if landed and all(one.state == ITEM_DUPLICATE for one in landed):
        return "duplicate"
    return "ok"


def _record_landing(
    caller: serve.PartnerCaller,
    operation: Operation,
    landed: Sequence[LandedItem],
    *,
    registry: Registry,
) -> models.IntegrationRun | None:
    """One delivery -> one `inbound` run row, so S142 shows it (`BR-INT-035`).

    *14:02 · Payment kiosk network · payments · 1 landed · ••••K1OS* — and the
    last field is a MASK. `resolve_caller` kept no plaintext, so there is no
    code path from here to the key.

    A duplicate is `skipped`, not `failed`: nothing went wrong: we recognised a
    repeat and declined to store it twice. `services.outcome_for` keeps the
    three kinds of not-knowing apart and `record_read`'s own comment records
    the same distinction being got wrong once already.
    """
    duplicates = sum(1 for one in landed if one.state == ITEM_DUPLICATE)
    unkeyed = sum(1 for one in landed if one.state == ITEM_NO_KEY)
    new = sum(1 for one in landed if one.state == ITEM_LANDED)
    run = services.start_run(
        connection=caller.connection,
        operation=operation.name,
        direction=models.RUN_DIRECTION_INBOUND,
        trigger="partner",
        registry=registry,
    )
    parts = [f"{new} landed"]
    if duplicates:
        parts.append(f"{duplicates} already had")
    if unkeyed:
        parts.append(f"{unkeyed} with no id")
    return services.finish_run(
        run,
        attempted=len(landed),
        succeeded=new,
        failed=unkeyed,
        skipped=duplicates,
        confirmed=True,
        summary=f"{operation.label} · {' · '.join(parts)} · {caller.hint}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE APPLY DOOR — `CR-174-BRC10`, for an operation that DECLARES it
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-07 (D1), verbatim: *"(a). A person standing at a machine needs the
# live balance. Runbooks still handle the exceptions in D2."* Everything below
# runs only for an operation whose manifest says `applies=…`; it reads every
# field name off `Operation.wire`, every status number off
# `Operation.envelope_status`, and contains no provider key (G77).

#: The account id the agent sends: letters, digits and a hyphen, up to fifty,
#: matched EXACTLY — leading zeros are part of it (the specification's words).
ACCOUNT_REF = re.compile(r"^[A-Za-z0-9-]{1,50}$")
#: A 64-bit payment id — the provider's own, and the half of both duplicate
#: keys that makes a resend a resend.
INT64_MAX = 2**63 - 1
#: How many times a return may arrive before its payment before a System Admin
#: is told. A return overtaking its payment is a race the first resend
#: normally wins; the THIRD refusal means it is not a race. Judgment J6,
#: decision log 2026-10-07. The alert fires exactly once, on that attempt.
NOT_YET_ALERT_AT = 3
#: The landing row's marker for the payment a return reverses.
_CENT = Decimal("0.01")


class _Undo(Exception):
    """Leave the transaction with nothing kept: the landing row, the run's
    work and any partial money all go. Raised for an answer that is not
    `200`/`409`, so the agent's resend of the identical body is a FIRST
    delivery and never a `409` over money we did not post."""

    def __init__(self, outcome: str, detail: str) -> None:
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


def _identity_matches(manifest: Manifest, caller: serve.PartnerCaller, headers: Mapping[str, Any]) -> bool:
    """Every identity header the partner SENT names this utility (`CR-174-BRC10`).

    A header not sent is not checked (the specification makes both optional).
    A header sent is compared, exactly, with the connection's own copy — and
    when the utility typed no copy, it is compared with the utility's own id
    the way `serve.company_id_matches` does (*"company_id = tenant id"*, PO
    2026-09-16). A header that matches neither is a NO: the agent is
    configured against another utility, and telling it so on the first call
    beats a month of payments posted somewhere they do not belong.
    """
    config = dict(caller.connection.config or {})
    for header_name, field_name in manifest.auth.identity_headers.items():
        sent = headers.get("HTTP_" + header_name.upper().replace("-", "_"))
        if sent is None or str(sent).strip() == "":
            continue
        ours = str(config.get(field_name) or "").strip()
        if ours:
            if str(sent).strip() != ours:
                return False
        elif not serve.company_id_matches(caller, sent):
            return False
    return True


def _exact_json(raw_body: bytes) -> dict[str, Any] | None:
    """The body, with every JSON number with a fraction read as a `Decimal`.

    ⚠ **NEVER A FLOAT** (hard rule 2). `json.loads` reads `42.10` as a binary
    float by default, and `Decimal(42.1)` is `42.100000000000001…`. `None`
    when the body is not a JSON object at all.
    """
    try:
        parsed = json.loads(raw_body.decode("utf-8"), parse_float=Decimal)
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _wire_number(value: Decimal) -> str:
    return str(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def render_answer(answer: Mapping[str, Any]) -> bytes:
    """`{"amountDue": 147.85}` — a JSON number, exactly, with no float in between.

    `json` has no way to write a Decimal as a number, and `DjangoJSONEncoder`
    writes it as a STRING, which the agent's contract does not accept
    (*"amount — JSON number, two decimals"*). So each Decimal is written as a
    marked string and the marks are taken off afterwards; the digits are
    `Decimal.quantize`'s own and never a float's.
    """
    marked = {
        key: (f"\u0000{_wire_number(value)}\u0000" if isinstance(value, Decimal) else value)
        for key, value in answer.items()
    }
    text = json.dumps(marked)
    return re.sub(r'"\\u0000(-?[0-9]+\.[0-9]{2})\\u0000"', r"\1", text).encode("utf-8")


def _rfc3339(raw: Any) -> datetime | None:
    """An RFC 3339 instant with its zone (`2026-10-07T14:32:05Z`), or None."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _money(raw: Any) -> Decimal | None:
    """A positive amount with no more than two decimals, or None."""
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value <= 0 or value != value.quantize(_CENT):
        return None
    return value


def _payment_id(raw: Any) -> str | None:
    """The agent's 64-bit payment id, as its decimal digits, or None."""
    if isinstance(raw, bool):
        return None
    text = str(raw if raw is not None else "").strip()
    if not text.isdigit() or int(text) > INT64_MAX:
        return None
    # The text AS SENT, never re-spelled: `_land_one` keys the landing row on
    # exactly this string, and a payment and its return must agree on it.
    return text


def _apply_door(
    caller: serve.PartnerCaller,
    manifest: Manifest,
    operation: Operation,
    *,
    raw_body: bytes,
    query: Mapping[str, Any],
    received_at: datetime,
    registry: Registry,
) -> InboundReply:
    """Authenticated already. Read, land, post, record the run, reply."""
    if operation.applies == APPLY_ACCOUNT_LOOKUP:
        return _lookup(caller, manifest, operation, raw_body=raw_body, query=query, received_at=received_at, registry=registry)
    return _post(caller, manifest, operation, raw_body=raw_body, received_at=received_at, registry=registry)


def _lookup(
    caller: serve.PartnerCaller,
    manifest: Manifest,
    operation: Operation,
    *,
    raw_body: bytes,
    query: Mapping[str, Any],
    received_at: datetime,
    registry: Registry,
) -> InboundReply:
    """`200`, always — `{found: false}` for an account we cannot show.

    ⚠ **THE BALANCE IS THE PORTAL'S OWN READ** (`payments.account_balance`),
    never a sum made here. ⚠ **THE ACCOUNT NUMBER IS NOT WRITTEN TO THE RUN
    ROW** — the access log is read by a manager and says *asked · found*; a
    list of every account number a machine tried is a list nobody needs.
    """
    wire = operation.wire
    source: Mapping[str, Any] = query if operation.http_method == "GET" else (_exact_json(raw_body) or {})
    raw_ref = source.get(wire["account"])
    if isinstance(raw_ref, (list, tuple)):
        raw_ref = raw_ref[0] if raw_ref else None
    ref = str(raw_ref) if raw_ref is not None else ""
    as_of = tenancy_seam.today() or received_at.date()
    position = (
        payments_seam.agent_account_position(ref, as_of=as_of) if ACCOUNT_REF.match(ref) else None
    )
    if position is None:
        answer: dict[str, Any] = {wire["found"]: False}
    else:
        answer = {
            wire["found"]: True,
            wire["balance"]: Decimal(position["balance"]),
            wire["past_due"]: Decimal(position["past_due"]),
            wire["allow_payments"]: bool(position["allow_payments"]),
            wire["allow_check"]: bool(position["allow_check"]),
            wire["allow_credit"]: bool(position["allow_credit"]),
            wire["allow_debit"]: bool(position["allow_debit"]),
            wire["display_credit"]: bool(position["display_credit"]),
            wire["residential"]: bool(position["residential"]),
        }
    run = services.finish_run(
        services.start_run(
            connection=caller.connection,
            operation=operation.name,
            direction=models.RUN_DIRECTION_INBOUND_READ,
            trigger="partner",
            registry=registry,
        ),
        attempted=1,
        succeeded=1,
        failed=0,
        skipped=0,
        confirmed=True,
        summary=f"{operation.label} · {'found' if position is not None else 'not found'} · {caller.hint}",
    )
    return InboundReply(
        provider_key=manifest.key,
        operation=operation.name,
        outcome="ok",
        status=status_for(operation, "ok"),
        run_id=str(run.id),
        answer=answer,
    )


def _tender(caller: serve.PartnerCaller, manifest: Manifest, word: Any, *, received_at: datetime) -> str | None:
    """THEIR tender word → OUR method code, through the mapping screen's rows.

    *"unknown → OTHER, never refuse"*: a word with no mapping — one nobody
    listed, or a listed one the utility left red — resolves to the
    vocabulary's FALLBACK word's mapping, and the word is recorded as an
    unmapped row with its *last seen* so a clerk sees it (BR-INT-031). `None`
    only when even the fallback is unmapped, which switching on refuses.
    """
    vocabulary = next((one for one in manifest.vocabularies if one.entity_type == "tender"), None)
    if vocabulary is None:
        return None
    spoken = str(word or "").strip().upper()
    tenant_id = caller.connection.tenant_id
    if spoken:
        found = mappings.local_for(tenant_id, manifest.key, "tender", spoken)
        if found is not None:
            return str(found["value"])
        mappings.record_unknown(
            connection=caller.connection,
            entity_type="tender",
            external_value=spoken,
            seen_at=received_at,
        )
    if vocabulary.fallback is None:
        return None
    fallback = mappings.local_for(tenant_id, manifest.key, "tender", vocabulary.fallback)
    return None if fallback is None else str(fallback["value"])


def _post(
    caller: serve.PartnerCaller,
    manifest: Manifest,
    operation: Operation,
    *,
    raw_body: bytes,
    received_at: datetime,
    registry: Registry,
) -> InboundReply:
    """A payment or a return: validate, then land + post as ONE transaction.

    The answers, every number off the manifest:

      * `ok` — posted, or landed and parked for a clerk (D2's residue);
      * `duplicate` — this paymentId has been landed before; NOTHING processed;
      * `invalid` — a body we cannot act on; nothing kept;
      * `not_yet` — a return whose payment has not arrived; nothing kept;
      * `failed` — our fault; nothing kept, so their resend is a first delivery.

    ⚠ **THE LANDING ROW AND THE MONEY ARE ONE TRANSACTION, AND THAT IS WHAT
    MAKES `409` TRUE.** If the post fails after the row is written and the row
    survived, the agent's retry would be told *duplicate* over money that was
    never posted. So the row is written inside the same `atomic()` as the
    payment and leaves with it.

    ⚠ **TWO IDENTICAL MESSAGES AT ONCE: THE UNIQUE INDEX DECIDES, AND THE
    LOSER GETS `409`, NOT `500`.** On PostgreSQL the second INSERT into
    `payment_webhook_events` waits on the first transaction's uncommitted row;
    when that commits, the index refuses the second, `land_delivery`'s own
    SAVEPOINT absorbs the refusal (law 14) and it answers *duplicate*. Proved
    on PostgreSQL 16 by `test_cr174_us_payments.py`'s two-thread case.
    """
    wire = operation.wire
    body = _exact_json(raw_body)
    reversal = reversal_marker(operation) == MARKER_REVERSAL
    item = body or {}
    payment_id = _payment_id(item.get(operation.idempotency.key_field))
    account_ref = item.get(wire["account"])
    account_text = account_ref if isinstance(account_ref, str) else None
    amount = _money(item.get(wire["amount"]))
    occurred = _rfc3339(item.get(wire["occurred_at"]))
    problem = None
    if body is None:
        problem = "the body is not a JSON object"
    elif payment_id is None:
        problem = "the payment id is not a whole number"
    elif account_text is None or not ACCOUNT_REF.match(account_text):
        problem = "the account id is not one we can read"
    elif amount is None:
        problem = "the amount is not a positive two-decimal number"
    elif occurred is None:
        problem = "the date and time is not RFC 3339 with a zone"
    if problem is not None:
        return _answered(caller, manifest, operation, outcome="invalid", detail=problem, key=None, registry=registry)

    key = dedupe_key(operation, payment_id)
    outcome = "ok"
    detail = "posted"
    parked = False
    try:
        with transaction.atomic():
            # ⚠ THE LANDED ROW IS THE BODY AS JSON PARSES IT, NOT `item`: the
            # Decimal reading above exists so no float touches the MONEY we
            # post, and `payment_webhook_events.body` is a JSON column that
            # stores what arrived. Same bytes, two readings, each for its job.
            landed = _land_one(manifest.key, operation, _parsed(raw_body), received_at=received_at)
            if landed.state == ITEM_DUPLICATE:
                outcome, detail = "duplicate", "already had"
            else:
                event_row = payments_seam.agent_outcomes().landed_event(manifest.key, key)
                codes = payments_seam.agent_outcomes()
                if reversal:
                    result = payments_seam.post_agent_return(
                        provider=manifest.key,
                        payment_door_key=f"{payment_id}{KEY_SEPARATOR}{MARKER_PAYMENT}",
                        door_key=key,
                        event_row_id=event_row.pk,
                        account_ref=account_text,
                        amount=amount,
                        returned_at=occurred,
                        return_code=(str(item.get(wire["return_code"]) or "").strip() or None)
                        if wire.get("return_code")
                        else None,
                    )
                else:
                    result = payments_seam.post_agent_payment(
                        provider=manifest.key,
                        door_key=key,
                        event_row_id=event_row.pk,
                        account_ref=account_text,
                        amount=amount,
                        paid_at=occurred,
                        method_code=_tender(caller, manifest, item.get(wire["method"]), received_at=received_at),
                        confirmation=payment_id,
                        channel=item.get(wire["channel"]) if wire.get("channel") else None,
                        terminal=item.get(wire["terminal"]) if wire.get("terminal") else None,
                    )
                if result.code == codes.NOT_YET:
                    raise _Undo("not_yet", result.detail or "not yet")
                if result.code == codes.INVALID:
                    raise _Undo("invalid", result.detail or "invalid")
                parked = result.code == codes.PARKED
                detail = (
                    f"parked · {result.detail}" if parked else f"posted as {result.payment_no or result.payment_id}"
                )
    except _Undo as undo:
        outcome, detail = undo.outcome, undo.detail
    except Exception:  # noqa: BLE001 — the one boundary where broad is right
        # Our fault. The transaction rolled back, so nothing is kept and the
        # agent's resend is a first delivery. ⚠ THE LOG LINE NAMES THE
        # OPERATION AND THE TRACE AND NEVER A HEADER — the credential arrives
        # in one (`password`), and a log that printed the request would print it.
        logger.exception("inbound apply failed: %s · %s", manifest.key, operation.name)
        outcome, detail = "failed", "could not be posted; nothing was kept"
    return _answered(
        caller,
        manifest,
        operation,
        outcome=outcome,
        detail=detail,
        key=key,
        registry=registry,
        alert=parked,
        received_at=received_at,
    )


# `DEF-INT-10018` — every run closed below goes through `services.finish_run`,
# which moves an UNTESTED connector to `working` on the partner's first
# successful call (`_first_partner_call_is_the_test`); nothing here does.
def _answered(
    caller: serve.PartnerCaller,
    manifest: Manifest,
    operation: Operation,
    *,
    outcome: str,
    detail: str,
    key: str | None,
    registry: Registry,
    alert: bool = False,
    received_at: datetime | None = None,
) -> InboundReply:
    """One run row a manager reads on S142, any alert owed, and the reply.

    ⚠ `request_key` IS THE DOOR KEY (`900000000123|return`), so a return that
    keeps arriving before its payment can be COUNTED across attempts that each
    kept nothing else (`NOT_YET_ALERT_AT`). No account number, no amount and
    no header is on the row — the summary says what happened in a clerk's
    words and the masked key hint says who.
    """
    ok = outcome == "ok"
    duplicate = outcome == "duplicate"
    run = services.finish_run(
        services.start_run(
            connection=caller.connection,
            operation=operation.name,
            direction=models.RUN_DIRECTION_INBOUND,
            trigger="partner",
            request_key=key,
            registry=registry,
        ),
        attempted=1,
        succeeded=1 if ok else 0,
        failed=0 if (ok or duplicate) else 1,
        skipped=1 if duplicate else 0,
        confirmed=True,
        summary=f"{operation.label} · {detail} · {caller.hint}",
    )
    if alert:
        _alert(operation, run, received_at=received_at or run.started_at)
    if outcome == "not_yet" and key is not None:
        tries = models.IntegrationRun.objects.filter(
            tenant_id=caller.connection.tenant_id,
            connection=caller.connection,
            operation=operation.name,
            request_key=key,
            failed__gt=0,
        ).count()
        if tries == NOT_YET_ALERT_AT:
            _alert(operation, run, received_at=received_at or run.started_at)
    answer = {"received": True} if ok else {"received": False, "status": outcome}
    return InboundReply(
        provider_key=manifest.key,
        operation=operation.name,
        outcome=outcome,
        status=status_for(operation, outcome),
        run_id=str(run.id),
        answer=answer,
    )


def _alert(operation: Operation, run: models.IntegrationRun, *, received_at: datetime) -> None:
    """ONE bell message to the utility's System Admins. Never raises."""
    try:
        notifications_seam.queue_staff_alert(
            actor=None,
            operation=f"{operation.label} from a payment partner",
            operation_id=run.id,
            total_count=1,
            failed_count=1,
            finished_at=received_at,
            job="integrations.agent_door",
        )
    except Exception:  # noqa: BLE001 — a failed alert must never fail the message
        logger.exception("agent door alert could not be raised: %s", operation.name)


# ═══════════════════════════════════════════════════════════════════════════
# The boundary — BR-INT-058, and it is a deliberate absence
# ═══════════════════════════════════════════════════════════════════════════


def runbooks_apply(reply: InboundReply) -> None:
    """What a landed notification MEANS — Runbooks', not ours.

    Returns `None` and that is the finished answer for this module.

    `CR-069` §20.4 splits wave N in as many words: integrations KEEPS
    authenticate, dedupe on the composite key, the `200`/`409` reply and
    persist raw; it MOVES *"`record_payment` with channel `KIOSK`, the
    reversal row for a return, `DRIVEUP → OTHER`, and showing the risk flag to
    a clerk"*. `BR-INT-058` states the same line across the guard pipeline:
    the first three positions are integrations' and `apply` is the runbook's.

    ⚠ This is a **deliberate absence and not a stub** (`OQ-1396`'s
    distinction): it raises nothing, blocks nothing and names no open
    question, because nothing is unruled. `OQ-INT-1729` was RULED option (a)
    on 2026-09-06 — the lane stops at the door — and `OQ-INT-1486` was ruled
    on 2026-09-04: a risky-flagged payment is accepted and its flag is shown
    on the payment for a clerk. **Both of those are things the APPLY half
    does**, so neither blocks this file, and a lane finding this function
    should leave it alone rather than try to unblock it.

    ⚠ **THE RISK FLAG IS ALREADY KEPT AND THAT IS THE HALF THAT IS OURS.**
    Whatever the kiosk sends is in the raw envelope on
    `payment_webhook_events.body`, unread and unaltered, because the door
    persists what arrived rather than what it understood. The clerk-visible
    half — the flag ON THE PAYMENT — needs a payment, and there is none yet.

    When Runbooks lands, this is where its apply plugs in, and
    `test_us_int_044_inbound_door.py::test_tc_boundary_the_door_applies_nothing`
    goes red the moment it does — which is the only way a boundary written in
    prose survives contact with the next lane.
    """
    return None


# ═══════════════════════════════════════════════════════════════════════════
# The quadrant's other half
# ═══════════════════════════════════════════════════════════════════════════


def execute_run(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    work: Sequence[Mapping[str, Any]],
    trigger: str,
    job_id: Any = None,
) -> models.IntegrationRun:
    """A partner's message is theirs to start. There is no batch for us to run.

    ⚠ THIS RAISES FOR GOOD AND NO WAVE WILL CHANGE IT — the same sentence
    `serve.execute_run` carries, for the same reason. Wave B left this raising
    `NotImplementedError("US-INT-044")`, which read as *not built yet*; wave N
    is that story and the answer turns out to be that there is nothing here to
    build. `receive()` above is the door, and a kiosk calling it is the only
    way work arrives in this quadrant.
    """
    raise NotImplementedError(
        "a partner's message is not work we start; there is no batch to execute"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-044@wave-N (EP-INT-13); BR-INT-058 CONFIRMED 2026-09-06; OQ-INT-1729 CLOSED option (a) 2026-09-06; OQ-INT-1486 CLOSED option (a) 2026-09-04 (the apply half's, not this file's)
# generated: 2026-09-06 by the CR-069 wave N build lane (the door half)
# checklist: A✔ B✔ C✔ D✔(inbound_api.py mounts one route) E=n/a(NO SCREEN — a kiosk POSTs here; the reason is in the docstring, and the run row this writes is drawn by S142 which already exists) F✔ G✔ H=pending(the guard glob for this file is ASKED of the PO in 09-human-review-ledger.md; a lane may not add itself — G53)
# gates: pytest tests/test_us_int_044_inbound_door.py tests/test_us_int_016_queue.py · G6 (no cross-module model import) · G77 (no provider-key branch) · G7 once the glob lands
# exceptions: `runbooks_apply()` returns None by BR-INT-058 — a deliberate absence owned by Runbooks, not a stub · no HUMAN-OWNED marker is written here because no glob matches this path yet and G53 refuses a file that declares itself owned while none does (the marker and the glob land in the same commit, the PO's)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
