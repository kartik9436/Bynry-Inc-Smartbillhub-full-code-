# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) — the adapter protocol: validate, test,
#           execute, describe, and nothing else. `CR-115-BRC05` §7 — the two
#           email service providers a utility's bills actually leave through.
#           Screens: S141 (connect · test) · S142 (the sentence, their words,
#           and the sending-domain panel another lane draws).
# Rules:    BR-INT-003 (the credential never reaches a sentence, a log line, an
#           audit payload or a describe line) · BR-INT-019 (`test()` is the
#           smallest REAL instance — one message, really sent) · BR-INT-038
#           (an adapter TRANSLATES; it decides nothing, retries nothing,
#           persists nothing) · BR-INT-040 (per-item results, never a batch
#           boolean) · BR-NOT-005 + BR-NOT-1032 (the six normalised outcomes) ·
#           B14 rule 33 (a sentence a clerk reads is six words or fewer) ·
#           CLAUDE.md 🔒 sensitive paths (credentials)
# Tests:    06-backend/tests/test_cr115_esp_adapters.py · the conformance kit,
#           unchanged, over BOTH classes (apps/integrations/conformance.py)
# Impacts:  apps/integrations/adapters/email_sendgrid.py ·
#           apps/integrations/adapters/email_postmark.py ·
#           apps/integrations/adapters/__init__.py (the two lines that bind
#           them) · apps/integrations/sending_domain.py (the DNS half)
# ───────────────────────────────────────────────────────
"""What SendGrid and Postmark have in common — the HTTPS half, and nothing else.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*), with a row in
`12-governance/09-human-review-ledger.md`. This file HOLDS A UTILITY'S ESP
CREDENTIAL IN MEMORY for the length of one call and puts it in a header.

WHY A SHARED FILE AND NOT TWO COPIES
-------------------------------------
`oauth_mailbox.py` is the precedent and the argument is the same one wave H
made: Microsoft 365 and Google Workspace are *"two files of about thirty lines,
each declaring a send URL and a message shape, over one shared adapter"*, and
that pair is what proves `P1` — *"every time such integration comes we dont want
to change our integration framework"* — rather than merely asserting it.

⚠ **AND THE ARGUMENT HAS A LIMIT THAT IS WORTH WRITING DOWN.** Two near-identical
providers are the shape a copy-paste drifts in; they are ALSO the shape a shared
base flattens a real difference in. So the split here is by QUESTION, not by
convenience: everything in this file is true of *any* JSON-over-HTTPS ESP, and
every sentence below that begins *SendGrid does X and Postmark does Y* lives in
the provider's own file where a reader can see both halves at once.

THE FOUR METHODS, AND WHY DOMAIN VERIFICATION IS NOT A FIFTH
-------------------------------------------------------------
`base.Adapter` is four methods and the conformance kit refuses a fifth PUBLIC
one. Checking a credential and checking a sending domain are not new METHODS,
they are new OPERATIONS — declared on the manifest like every other operation
and dispatched through `execute()` on `work[i]["operation"]`, exactly as
`meters_neptune360` dispatches its six. `execute()`'s own docstring already says
what an item of `work` is: *"one request the runner has already decided to
make"*. A credential check is one request. A domain check is one request.

⚠ **THE ONE THING THAT GENUINELY DID NOT FIT IS THE FEEDBACK NORMALISER**, and
it is a PRIVATE method for the reason `base.TOKEN_MINT_METHOD` is: the
conformance kit skips names beginning with an underscore, so an adapter that
declares one still has exactly four public methods and the kit is unchanged.
`base.feedback_normaliser()` resolves it and answers `None` when it is absent,
so a caller refuses by name rather than reaching for an attribute that is not
there (hard-won law 1 — a name in a constant is not a guarantee).

WHAT `202` AND `200` MEAN, AND IT IS NOT *DELIVERED*
------------------------------------------------------
⚠ **ACCEPTED. NOTHING MORE.** SendGrid answers `202` and Postmark `200` the
moment the message is queued at their end; the mailbox has not been reached and
may never be. The queue row therefore becomes `sent` and NEVER `delivered` —
only the feedback webhook may write that word, which is `BR-NOT-013`'s standing
rule and `delivery_counts`' *not reported* sentence being true rather than
tactful. An adapter that returned a delivered-shaped success here would make
every screen in the product assert delivery it has no evidence for.

THE TRANSPORT, AND WHAT COUNTS AS AN ANSWER
---------------------------------------------
A `4xx` IS AN ANSWER. A wrong key, a refused address, an unverified sender —
each is the provider telling us something in their own words, and each belongs
on the item as a refusal a clerk can read, never as an exception and never as a
tick against the breaker (`BR-INT-022`: *"a timeout counts towards the breaker
and a refusal does not"*). A socket that never opens is NOT an answer and
raises `ProviderTimeout`, which is the distinction `DEF-INT-5599` cost a
vanishing screen to learn one module over.

⚠ **NOTHING IN THE BUILD ENVIRONMENT CAN REACH EITHER PROVIDER.** Outbound
HTTPS is proxied and refused — the same wall `CR-115-BRC05` §7.10 records for
the City of Ann Arbor (*"`curl` returns code `000`"*). Every test over this file
runs against `esp_fixtures.py`, whose own docstring says it is HAND-SHAPED from
the documented wire formats and **is not a recording**. Nothing here is evidence
that a real SendGrid or Postmark account answers the way these fixtures do.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from apps.integrations.adapters import email_format
from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldError,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations.runtime import ProviderTimeout

# ── the operations, named once ──────────────────────────────────────────────
#
# ⚠ **THESE ARE MANIFEST OPERATION NAMES AND THIS IS THE ONE COPY.** Both
# manifests declare them and `execute()` dispatches on them; a third spelling
# anywhere is the drift `DEF-INT-5589` is about.
OP_SEND = "send_message"
OP_VALIDATE_CREDENTIALS = "validate_credentials"
OP_CHECK_DOMAIN = "check_domain_verified"

#: How long we wait on an ESP before giving up, in seconds, when the runner
#: hands us no number of its own. `runtime.Limits` owns the real one — a
#: timeout hard-coded in an adapter is the same rule in a second place, and the
#: second place is the one that goes stale (`email_smtp` says the same).
TIMEOUT_SECONDS = 30.0

#: The most of a provider's answer we ever keep. Their words go on an item and
#: a run row, are scrubbed once at the write by `services.finish_run`, and are
#: shown to the owning tenant only.
PROVIDER_TEXT_CAP = 500

# ── the sentences. ≤ 6 words each (B14 rule 33), no rule id, no status code ──
SENT = "Sent one test message to {recipient}."
REFUSED_KEY = "The service refused the key."
REFUSED_SENDER = "That sender address is not verified."
REFUSED_MESSAGE = "The service refused the message."
NO_ANSWER = "The service did not answer."
MISSING_SCOPE = "That key cannot send mail."
KEY_ACCEPTED = "The key works."
DOMAIN_VERIFIED = "The domain is verified."
DOMAIN_PENDING = "The domain is not verified yet."
#: ⚠ Six words, and it says WHAT rather than WHY — B14 rule 33 puts the
#: rationale in the code and the register, never on screen. The why is
#: `DEF-INT-5650` and the Postmark adapter's own docstring.
DOMAIN_NOT_OFFERED = "We cannot check this domain yet."

# ── the DNS half, as data ───────────────────────────────────────────────────

#: What a record is FOR. A closed vocabulary, because the panel groups by it
#: and a purpose nobody declared would render as a blank heading.
PURPOSE_DKIM = "dkim"
PURPOSE_SPF = "spf"
PURPOSE_RETURN_PATH = "return_path"
PURPOSE_DMARC = "dmarc"
DNS_PURPOSES = (PURPOSE_DKIM, PURPOSE_SPF, PURPOSE_RETURN_PATH, PURPOSE_DMARC)

#: WHO the value came from, and it is the most important field on the record.
#:
#: ⚠ **EVERY PROVIDER-ISSUED VALUE COMES OUT OF THE PROVIDER'S OWN ANSWER AND
#: IS NEVER COMPOSED HERE.** SendGrid's `em1234` prefix and its DKIM selector
#: differ per ACCOUNT; Postmark's DKIM value is minted per domain. Writing a
#: plausible-looking one would hand a utility's IT team a record that publishes
#: cleanly, verifies never, and costs the one-to-three-week cycle twice.
SOURCE_PROVIDER = "provider"
#: The one exception, and it is marked so a reader can see it is ours: DMARC is
#: not issued by an ESP at all. Gmail and Yahoo require it of bulk senders and
#: the utility publishes it themselves; see `dmarc_record()`.
SOURCE_OURS = "ours"
DNS_SOURCES = (SOURCE_PROVIDER, SOURCE_OURS)

#: The four states a sending domain can be in, as the panel draws them.
DOMAIN_VERIFIED_STATE = "verified"
DOMAIN_PARTIAL = "partial"
DOMAIN_UNVERIFIED = "unverified"
DOMAIN_NOT_FOUND = "not_found"
DOMAIN_STATES = (DOMAIN_VERIFIED_STATE, DOMAIN_PARTIAL, DOMAIN_UNVERIFIED, DOMAIN_NOT_FOUND)


@dataclass(frozen=True)
class DnsRecord:
    """One line a utility's IT team types into their own DNS.

    `verified` is the PROVIDER's opinion of that one record and is `None` when
    they do not offer one per record — *unknown* and *not published* are
    different facts and a boolean cannot hold both.
    """

    purpose: str
    type: str  # "CNAME" or "TXT" — the vendor's own word, upper case
    host: str
    value: str
    verified: bool | None = None
    source: str = SOURCE_PROVIDER

    def as_dict(self) -> dict[str, Any]:
        return {
            "purpose": self.purpose,
            "type": self.type,
            "host": self.host,
            "value": self.value,
            "verified": self.verified,
            "source": self.source,
        }


@dataclass(frozen=True)
class DomainAnswer:
    """What the provider says about one sending domain, right now."""

    domain: str
    state: str
    records: tuple[DnsRecord, ...] = ()
    provider_text: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "state": self.state,
            "records": [one.as_dict() for one in self.records],
        }


# ── the feedback half, as data ──────────────────────────────────────────────


@dataclass(frozen=True)
class FeedbackOutcome:
    """ONE provider event, in OUR vocabulary and nobody else's.

    ⚠ **THE PROVIDER'S OWN WORD IS NOT ON THIS OBJECT AND THAT IS THE POINT.**
    `spamreport`, `SpamComplaint`, `dropped`, `SubscriptionChange` and
    `HardBounce` never leave the file that understands them. `status` is one of
    `notifications.models.PROVIDER_OUTCOME_STATUSES` and nothing outside an
    adapter ever learns which provider a utility is on (`BR-INT-004`).

    `tracking_ref` is OUR reference, which we put on the message when we sent it
    and which the provider hands back — `custom_args.tracking_ref` at SendGrid,
    `Metadata` at Postmark. It is how an event finds its queue row without our
    having to store the provider's own message id anywhere.
    """

    status: str
    tracking_ref: str | None = None
    address: str | None = None
    occurred_at: int | None = None  # unix seconds, THEIRS, or None
    provider_text: str | None = None


# ── the transport ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HttpAnswer:
    """What came back. A `4xx` is one of these, not an exception."""

    status: int
    body: Any = None
    headers: Mapping[str, str] = field(default_factory=dict)
    text: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        for key, value in self.headers.items():
            if str(key).lower() == wanted:
                return str(value)
        return None


#: `(method, url, headers, body_bytes, timeout_s) -> HttpAnswer`. A test binds a
#: hand-shaped one (`esp_fixtures.py`); production uses `_urllib_transport`.
Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], HttpAnswer]


def _urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_s: float,
) -> HttpAnswer:
    """The ONE network call in this file. `timeout_s` is the caller's number.

    ⚠ **AN `HTTPError` IS AN ANSWER AND IS RETURNED, NOT RAISED.** A `401` for a
    revoked key and a `403` for an unverified sender are things the provider
    SAID, and `BR-INT-022` is explicit that a refusal must not count towards a
    breaker built for a provider that is not there. `gis_city` re-raises its
    `HTTPError` for the opposite reason — there the caller wants it — and the
    two files disagreeing on purpose is better than one of them being wrong.
    """
    request = urllib.request.Request(url, data=body, method=method.upper())  # noqa: S310
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read()
            return HttpAnswer(
                status=int(response.status),
                body=_json_or_none(raw),
                headers=dict(response.headers.items()),
                text=raw.decode("utf-8", "replace")[:PROVIDER_TEXT_CAP],
            )
    except urllib.error.HTTPError as answered:
        raw = answered.read() or b""
        return HttpAnswer(
            status=int(answered.code),
            body=_json_or_none(raw),
            headers=dict(answered.headers.items()) if answered.headers else {},
            text=raw.decode("utf-8", "replace")[:PROVIDER_TEXT_CAP],
        )
    except TimeoutError as stopped:
        raise ProviderTimeout(str(stopped) or "the service did not answer") from stopped
    except (urllib.error.URLError, OSError) as gone:
        # DNS, a refused connection, a TLS failure and this environment's egress
        # proxy answering *Tunnel connection failed: 403 Forbidden* all arrive
        # here. `DEF-INT-5599`: *we never got in* is not *they said no*.
        raise ProviderTimeout(f"the service could not be reached: {gone}") from gone


def _json_or_none(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def dmarc_record(domain: str) -> DnsRecord:
    """The one record on the list that is OURS, and it is marked as ours.

    Gmail and Yahoo have required a DMARC policy of bulk senders since 2024, and
    neither SendGrid nor Postmark issues one — it is a statement the DOMAIN's
    owner makes about their own mail, so no provider response can carry it.

    ⚠ **`p=none` IS THE WEAKEST POLICY AND IT IS CHOSEN DELIBERATELY.** It
    satisfies the requirement (a record exists and is syntactically valid) and
    instructs no receiver to reject anything. `p=quarantine` or `p=reject` on a
    domain whose other mail streams we know nothing about would send a utility's
    own payroll and helpdesk mail to spam on the day they published it, and
    NOTHING IN THIS PRODUCT CAN SEE THOSE STREAMS. **So this value is a FLOOR a
    utility's own IT team may raise, never a recommendation we made**, and the
    panel should present it that way.

    ⚠ **NO `rua=` EITHER, AND THAT IS THE SAME JUDGMENT ONE STEP ON.** Asking
    for aggregate reports means naming an address WE would then have to receive
    at, parse and act on — an operational commitment nobody has taken. Putting
    one in the string now would either point at a mailbox that does not exist or
    silently create an obligation. Recorded as ours, with the reasoning, in
    `12-governance/02-decision-log.md` on 2026-09-17 (hard-won law 13: a
    judgment written down with its reasoning is the deliverable; a question is
    the failure to make one).
    """
    return DnsRecord(
        purpose=PURPOSE_DMARC,
        type="TXT",
        host=f"_dmarc.{domain}".strip("."),
        value="v=DMARC1; p=none;",
        verified=None,
        source=SOURCE_OURS,
    )


def state_from(records: Sequence[DnsRecord]) -> str:
    """Verified when every record the PROVIDER checks is verified, and never
    otherwise.

    ⚠ **THE RECORDS WE COMPOSED DO NOT VOTE.** `verified is None` means the
    provider offered no opinion — which is true of DMARC always, because they
    do not look at it — and counting an absent opinion either way would be a
    made-up fact on the one screen a utility's IT team is judged by.
    """
    checked = [one.verified for one in records if one.verified is not None]
    if not checked:
        return DOMAIN_UNVERIFIED
    if all(checked):
        return DOMAIN_VERIFIED_STATE
    if any(checked):
        return DOMAIN_PARTIAL
    return DOMAIN_UNVERIFIED


# ── the shared adapter ──────────────────────────────────────────────────────


class EspEmailAdapter(Adapter):
    """Four public methods. Everything provider-shaped is an abstract hook below.

    A subclass answers seven questions and writes no HTTP of its own:
    how a request authenticates, what a send looks like on the wire, what
    *accepted* looks like coming back, which call checks a credential and how to
    read its answer, which call checks a domain and how to read its answer, and
    how one of their feedback events maps onto our six words.
    """

    #: Bound in `adapters/__init__.py`; `register_all` refuses a mismatch.
    key: str

    def __init__(self, transport: Transport | None = None) -> None:
        #: Injected by a test. `services` builds every adapter with no
        #: arguments, so production always gets the real one.
        self._transport = transport

    # ── validate — provider knowledge, no network ──────────────────────────

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """What the manifest's shape check cannot know (`BR-INT-043`).

        One rule, and it is the one that costs a real utility a week: **the
        address we send FROM must sit inside the domain we are verifying.**
        SendGrid and Postmark both refuse mail whose `From` is outside the
        authenticated domain, and they refuse it at SEND time — so a mismatch
        typed here is a connector that tests green, verifies green, and then
        fails on every bill in the first run.
        """
        problems: FieldErrors = []
        domain = str(config.get("sending_domain") or "").strip().lower().strip(".")
        sender = str(config.get("send_from") or "").strip().lower()
        if domain and sender and "@" in sender:
            at = sender.rsplit("@", 1)[1]
            if at != domain and not at.endswith("." + domain):
                problems.append(FieldError("send_from", message_key="integrations.field.email"))
        return problems

    # ── test — the smallest REAL instance (BR-INT-019) ─────────────────────

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """Send ONE real message to an address a person typed.

        ⚠ **NOT *does the key parse*.** `BR-INT-019` underlines this twice and
        names it the commonest mistake in this space. The credential check is a
        separate operation precisely so that `test()` does not quietly become
        one: a key with `mail.send` revoked passes `GET /v3/scopes` reasoning
        and fails the thing a utility actually bought.

        ⚠ **AND IT GOES OUT IN THE SANDBOX WHEN THE CONNECTION IS ONE.** The
        connection carries `environment`, so a sandbox connection is tested the
        way it will be used. What *sandbox* means differs per provider and is
        the subclass's to say.
        """
        address = (recipient or "").strip()
        if not address:
            return TestResult(ok=False, sentence=REFUSED_MESSAGE)
        answer = self._send_one(
            conn,
            secrets,
            {"address": address, "subject": "Test message", "body": self._test_body(conn)},
            timeout_s=TIMEOUT_SECONDS,
        )
        if self._accepted(answer):
            return TestResult(ok=True, sentence=SENT.format(recipient=address))
        return TestResult(
            ok=False,
            sentence=self._refusal_sentence(answer),
            provider_text=_their_words(answer),
        )

    # ── execute — one attempt at a batch of REQUESTS ───────────────────────

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """Per-item outcomes, never a bool. Dispatches on the item's operation.

        An item with no `operation` is a SEND, because that is what the
        dispatcher hands us (`seams/notifications.dispatch_outbound_batch`
        builds `{ref, address, subject, body}` and names no operation), and a
        default that matched nothing would make every bill in the product fail
        with *is not one this connector asks for*.

        ⚠ **`confirmed` IS `True` BECAUSE THE PROVIDER ANSWERS PER MESSAGE**,
        one accepted id at a time — `BR-INT-018`'s *the far end SAID how many it
        accepted*. It is NOT a claim that anything was delivered; see the module
        docstring.
        """
        items: list[ItemResult] = []
        for index, one in enumerate(work):
            ref = str(one.get("ref", index))
            operation = str(one.get("operation") or OP_SEND)
            timeout_s = float(one.get("timeout_s") or TIMEOUT_SECONDS)
            if operation == OP_SEND:
                items.append(self._send_item(conn, secrets, one, ref, timeout_s))
            elif operation == OP_VALIDATE_CREDENTIALS:
                items.append(self._credential_item(conn, secrets, ref, timeout_s))
            elif operation == OP_CHECK_DOMAIN:
                items.append(self._domain_item(conn, secrets, one, ref, timeout_s))
            else:
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=f"{operation} is not one this connector asks for",
                    )
                )
        return RunResult(items=tuple(items), confirmed=True)

    # ── describe — the masked line on the card ─────────────────────────────

    def describe(self, conn: ConnectionView) -> str:
        """*billing@ottumwawater.gov · SendGrid* — who the mail comes FROM.

        No key, no key fragment, no host (`BR-INT-003`'s third exit). The
        sending domain is not a secret: it is the thing a utility reads off its
        own website, and it is what makes two connections tellable apart.
        """
        who = str(conn.config.get("send_from") or "").strip()
        return f"{who} · {self._vendor_name}".strip(" ·") or self._vendor_name

    # ── the item builders — private, and none of it is the protocol ────────

    def _send_item(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        one: Mapping[str, Any],
        ref: str,
        timeout_s: float,
    ) -> ItemResult:
        address = str(one.get("address") or "").strip()
        # ⚠ **NO WORDS OF OUR OWN ON A REAL MESSAGE (`DEF-NOT-10420`).** Both
        # subclasses fell back to *Message from your utility* for a missing
        # subject and `str()`-ed whatever arrived as the body. A message with no
        # subject or no text body now fails here, in our words, and nothing is
        # dialled; `test()` passes its own test words explicitly.
        try:
            email_format.compose(subject=one.get("subject"), body=one.get("body"))
        except email_format.EmailContentMissing as missing:
            return ItemResult(
                ref=ref, outcome=ITEM_FAILED, detail=address or None, provider_text=missing.sentence
            )
        answer = self._send_one(conn, secrets, one, timeout_s=timeout_s)
        if self._accepted(answer):
            return ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, detail=address or None)
        return ItemResult(
            ref=ref,
            outcome=ITEM_FAILED,
            detail=address or None,
            provider_text=_their_words(answer),
        )

    def _credential_item(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        ref: str,
        timeout_s: float,
    ) -> ItemResult:
        answer = self._call(conn, secrets, *self._credential_request(conn), timeout_s=timeout_s)
        if not answer.ok:
            return ItemResult(
                ref=ref, outcome=ITEM_FAILED, detail=REFUSED_KEY, provider_text=_their_words(answer)
            )
        can_send = self._credential_can_send(answer)
        if not can_send:
            return ItemResult(
                ref=ref,
                outcome=ITEM_FAILED,
                detail=MISSING_SCOPE,
                provider_text=_their_words(answer),
            )
        return ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, detail=KEY_ACCEPTED)

    def _domain_item(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        one: Mapping[str, Any],
        ref: str,
        timeout_s: float,
    ) -> ItemResult:
        domain = str(one.get("domain") or conn.config.get("sending_domain") or "").strip()
        request = self._domain_request(conn, domain)
        if request is None:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=DOMAIN_NOT_OFFERED)
        answer = self._call(conn, secrets, *request, timeout_s=timeout_s)
        if not answer.ok:
            return ItemResult(
                ref=ref, outcome=ITEM_FAILED, detail=REFUSED_KEY, provider_text=_their_words(answer)
            )
        found = self._domain_answer(answer, domain)
        # ⚠ The DMARC line is appended HERE rather than in either provider file,
        # because it is the same record for both and neither of them issues it.
        records = (*found.records, dmarc_record(found.domain))
        found = DomainAnswer(
            domain=found.domain,
            # ⚠ **`not_found` SURVIVES THE RECOMPUTE, AND THE FIRST DRAFT LOST
            # IT.** Appending the DMARC line and re-deriving the state turned
            # *they have never heard of this domain* into *unverified*, which
            # are different instructions to a clerk: one says ADD THE DOMAIN AT
            # THE PROVIDER, the other says CHASE YOUR IT TEAM. Caught by
            # `test_cr115__a_domain_sendgrid_has_never_heard_of_is_not_an_error`
            # and not by anything else.
            state=found.state if found.state == DOMAIN_NOT_FOUND else state_from(records),
            records=records,
            provider_text=found.provider_text,
        )
        return ItemResult(
            ref=ref,
            # ⚠ **AN UNVERIFIED DOMAIN IS A SUCCESSFUL CHECK.** The run asked
            # *what do they say* and they said it. Failing the item would put a
            # red run row on a connector the day it is set up and every day of
            # the one-to-three-week wait, which is the normal case.
            outcome=ITEM_SUCCEEDED,
            detail=json.dumps(found.as_dict(), sort_keys=True),
            provider_text=found.provider_text,
        )

    # ── the wire ───────────────────────────────────────────────────────────

    def _send_one(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        one: Mapping[str, Any],
        *,
        timeout_s: float,
    ) -> HttpAnswer:
        method, url, body = self._send_request(conn, one)
        return self._call(conn, secrets, method, url, body, timeout_s=timeout_s)

    def _call(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        method: str,
        url: str,
        body: Mapping[str, Any] | None = None,
        *,
        timeout_s: float,
    ) -> HttpAnswer:
        """Dial once, with the credential in the header the manifest declares.

        ⚠ **THE HONEST-DEADLINE CHECK IS THE SAME ONE `gis_city` MAKES**: a
        transport that ignored the deadline is recorded as *we stopped waiting*
        rather than accepted late, which is what `runtime.guarded_call` asks for
        in its own docstring.
        """
        headers = {"Accept": "application/json", **self._auth_headers(secrets)}
        payload: bytes | None = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        send = self._transport or _urllib_transport
        started = time.monotonic()
        answer = send(method, url, headers, payload, timeout_s)
        if (time.monotonic() - started) > timeout_s:
            raise ProviderTimeout("the service answered after we stopped waiting")
        return answer

    def _url(self, conn: ConnectionView, path: str) -> str:
        base = str(conn.config.get("base_url") or self._default_base_url).strip().rstrip("/")
        if "://" not in base:
            base = f"https://{base}"
        return f"{base}{path}"

    def _refusal_sentence(self, answer: HttpAnswer) -> str:
        """OUR six words for what they said. Their words ride underneath."""
        if answer.status in (401, 403):
            return REFUSED_KEY
        if answer.status == 422:
            return REFUSED_SENDER
        if answer.status >= 500:
            return NO_ANSWER
        return REFUSED_MESSAGE

    def _test_body(self, conn: ConnectionView) -> str:
        return "This is a test message from your utility billing system."

    def _accepted(self, answer: HttpAnswer) -> bool:
        """Did they take it? The STATUS is the subclass's — 202 or 200 — and
        the accepted-id check is too, because a body with no id is a provider
        that answered happily and told us nothing (`BR-INT-018`)."""
        return answer.status == self._accepted_status and self._accepted_id(answer) is not None

    # ── what a subclass must answer ────────────────────────────────────────

    @property
    @abstractmethod
    def _vendor_name(self) -> str:
        """*SendGrid* — the word on the card, in the vendor's own spelling."""

    @property
    @abstractmethod
    def _default_base_url(self) -> str:
        """Where we dial when the connection names no address."""

    @property
    @abstractmethod
    def _accepted_status(self) -> int:
        """`202` at SendGrid, `200` at Postmark. NOT *delivered*, either way."""

    @abstractmethod
    def _auth_headers(self, secrets: Mapping[str, str]) -> dict[str, str]:
        """The credential, in the header the manifest's `Auth` declares."""

    @abstractmethod
    def _send_request(
        self, conn: ConnectionView, one: Mapping[str, Any]
    ) -> tuple[str, str, Mapping[str, Any]]:
        """`(method, url, body)` for one message, with OUR tracking reference
        in whatever the vendor calls a custom field — that is how the feedback
        webhook finds the queue row again."""

    @abstractmethod
    def _accepted_id(self, answer: HttpAnswer) -> str | None:
        """THEIR id for the message they accepted, or `None` when they gave
        none. A provider that answered happily and would not say what it
        accepted has not succeeded (`BR-INT-018`)."""

    @abstractmethod
    def _credential_request(self, conn: ConnectionView) -> tuple[str, str]:
        """`(method, url)` for *is this key any good* — no body, ever."""

    @abstractmethod
    def _credential_can_send(self, answer: HttpAnswer) -> bool:
        """Does the key they described actually permit sending mail?"""

    #: ⚠ **THE DOMAIN CHECK IS THE ONE HOOK WITH A DEFAULT, AND THE DEFAULT IS
    #: *WE CANNOT ASK* RATHER THAN *THERE IS NOTHING TO ASK*.** Postmark's
    #: Domains API is gated behind an ACCOUNT token and this connector holds a
    #: SERVER token — one connector, one credential (`DEF-INT-4118`) — so the
    #: call cannot be made at all, not merely not yet. A subclass that can ask
    #: overrides both; one that cannot overrides neither and says why in its own
    #: docstring, and `_domain_item` refuses in six words rather than dialling a
    #: URL that would answer `401` and read like a bad key.
    def _domain_request(self, conn: ConnectionView, domain: str) -> tuple[str, str] | None:
        """`(method, url)` for *what do you say about this sending domain*, or
        `None` when it cannot be asked with the credential we hold."""
        return None

    def _domain_answer(self, answer: HttpAnswer, domain: str) -> DomainAnswer:
        """Their answer, as records. **Every value read out of `answer`.**"""
        return DomainAnswer(domain=domain, state=DOMAIN_UNVERIFIED, records=())


def _their_words(answer: HttpAnswer) -> str | None:
    """THEIRS, verbatim and UNSCRUBBED — `services.finish_run` scrubs once, at
    the write, and `G84` fails a second writer. An adapter that scrubbed here
    would be that second writer."""
    text = (answer.text or "").strip()
    if not text:
        return f"HTTP {answer.status}"
    return text[:PROVIDER_TEXT_CAP]


__all__ = [
    "DNS_PURPOSES",
    "DNS_SOURCES",
    "DOMAIN_NOT_FOUND",
    "DOMAIN_NOT_OFFERED",
    "DOMAIN_PARTIAL",
    "DOMAIN_STATES",
    "DOMAIN_UNVERIFIED",
    "DOMAIN_VERIFIED_STATE",
    "OP_CHECK_DOMAIN",
    "OP_SEND",
    "OP_VALIDATE_CREDENTIALS",
    "PROVIDER_TEXT_CAP",
    "PURPOSE_DKIM",
    "PURPOSE_DMARC",
    "PURPOSE_RETURN_PATH",
    "PURPOSE_SPF",
    "SOURCE_OURS",
    "SOURCE_PROVIDER",
    "TIMEOUT_SECONDS",
    "DnsRecord",
    "DomainAnswer",
    "EspEmailAdapter",
    "FeedbackOutcome",
    "HttpAnswer",
    "Transport",
    "dmarc_record",
    "state_from",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 + the decision log of 2026-09-17 (five PO rulings on email) · US-INT-015 (the four-method protocol) · BR-NOT-1032 (PROPOSED — the six normalised outcomes)
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a(backend only; the four email screens and the DNS panel are another lane's) C✔ D=PARTIAL(no provider is reachable from this environment — every proof is against esp_fixtures.py, which is hand-shaped and says so) E=n/a F✔ G✔ H=PENDING(🔒 credentials — human sign-off owed, row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr115_esp_adapters.py · the conformance kit UNCHANGED over both classes · G108 (every dial is guarded by its caller) · G33 (six words) · G84 (this file does not scrub)
# exceptions: (1) `urllib` is the transport and an `HTTPError` is returned as an ANSWER rather than raised — the opposite of `gis_city`, on purpose, because a 401 from an ESP is a refusal a clerk reads and must not move a breaker. (2) NO LOGGER, deliberately — `email_smtp`'s exit 2, for the same reason. (3) The DMARC record is the ONE value not read out of a provider answer, marked `source="ours"` on the wire so no reader can mistake it for one.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
