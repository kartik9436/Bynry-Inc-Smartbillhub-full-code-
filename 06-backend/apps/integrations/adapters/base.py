# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) — the adapter protocol: validate, test,
#           execute, describe — and nothing else. Screens: S141 · S142 (the
#           sentences `test()` and `describe()` return are what those draw)
# Rules:    BR-INT-004 (a provider-agnostic seam; no provider hardcoded into
#           business logic) · BR-INT-038 (P2 — the adapter is the
#           anti-corruption layer: translation only; no retry, no scheduling,
#           no persistence) · BR-INT-019 (`test()` performs the smallest REAL
#           instance of the operation, never a credential parse; a provider
#           with no safe instance declares it in its manifest) · BR-INT-003
#           (`describe()` never contains a secret; the plaintext exists at
#           exactly one point — in memory, inside `test()` or `execute()`,
#           for the length of one call) · BR-INT-043 (the field kinds are a
#           CLOSED vocabulary — the shape check below knows each one and has
#           no fallback branch)
# Tests:    06-backend/tests/test_us_int_015_adapters.py (TC-1..7) ·
#           apps/integrations/conformance.py (the kit every adapter runs)
# Impacts:  apps/integrations/adapters/__init__.py (the key → class registry) ·
#           apps/integrations/jobs.py (the runtime that calls these four) ·
#           apps/integrations/services.py (`validate_fields` runs BEFORE any
#           write on `connect`) · wave E's adapters/email_smtp.py (the first
#           real one, which must pass conformance.py unchanged)
# ───────────────────────────────────────────────────────
"""The adapter protocol — four methods, and the only code that knows a provider exists.

WHAT AN ADAPTER IS, AND IS NOT (US-INT-015, BR-INT-038)
-------------------------------------------------------
    validate(config)                 -> FieldErrors   shape only, cheap, NO network;
                                                       runs before anything is stored
    test(conn, secrets, recipient)   -> TestResult    the smallest REAL instance —
                                                       one message, one directory
                                                       listing, one zero-row file —
                                                       answered in one sentence a
                                                       clerk can read
    execute(conn, secrets, work)     -> RunResult     do the thing once, for a batch;
                                                       PER-ITEM outcomes, never a bool
    describe(conn)                   -> str           the masked line on the card;
                                                       never a secret

The adapter owns TRANSLATION and nothing else. No retry (the framework's, with
jitter — `core/jobs.py`), no scheduling (wave G's sweeps), no persistence (the
run row is `services.finish_run`'s, and the OUTCOME word is chosen there from
the counts — an adapter never types `succeeded`). *"Break this and a
provider's API change becomes a schema migration."*

⚠ THE PLAINTEXT CREDENTIAL EXISTS AT EXACTLY ONE POINT. The runtime decrypts
it (`services.credential_secrets`), hands it to `test()` or `execute()` as the
`secrets` mapping, and drops it when the call returns. It is never on the
`ConnectionView`, never returned, never logged, never in a sentence — the
conformance kit asserts the last three on every adapter, and the ONE place
that reads `payload_enc` is named in `services.py` so a grep finds it.

⚠ `test()` IS THE RED PEN THE DESIGN UNDERLINES TWICE (BR-INT-019). *"I have
seen this method built as 'does the API key parse' more times than any other
mistake in this space… A test that cannot fail the way production fails is
worse than no test, because someone trusted it."* Send one message. List one
directory. Write one empty file. A provider with no safe instance says so in
its manifest (`Operation.test_action = None`) and the card reads *cannot be
tested until first use*; the runtime refuses the request before this method
is ever reached.

THE MANIFEST-DRIVEN SHAPE CHECK, AND WHY IT LIVES HERE
------------------------------------------------------
`validate_fields()` below is the check every LIVE provider gets for free from
its manifest — a required field missing, a port that is not a number, an email
with no `@`, a host with a scheme in it, a select outside its options — keyed
by the CLOSED vocabulary of field kinds (BR-INT-043) with no fallback branch:
a kind this function does not know is refused by the registry at load, so it
never reaches here. An adapter's own `validate()` ADDS provider knowledge on
top (a port that must be 587 or 465, say); it does not repeat this. Both run
before a single row is written (US-INT-017 TC-4).

Message keys raised here resolve in all eleven catalogues (G32): a field error
reaches the modal as a sentence under the field, never as a code.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar
from urllib.parse import urlsplit

from apps.integrations.registry import FIELD_KINDS, Manifest

# ── results — the four return shapes ────────────────────────────────────────


@dataclass(frozen=True)
class FieldError:
    """One thing wrong with one field, in catalogue form (B12 §3 field_errors)."""

    field: str
    message_key: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def envelope(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "code": "VAL-002",
            "message_key": self.message_key,
            "params": dict(self.params),
        }


FieldErrors = list[FieldError]


@dataclass(frozen=True)
class TestResult:
    """The smallest real instance, answered in one sentence.

    `sentence` is OURS — one clause, no rule id, no status code (*the mail
    server rejected the password*). `provider_text` is THEIRS, verbatim but
    scrubbed by the adapter, shown underneath on S142 to the owning tenant
    only (*535 5.7.8 AUTHENTICATION FAILED*) — because one is actionable and
    the other is what support needs (frame 52.2).
    """

    ok: bool
    sentence: str
    provider_text: str | None = None


ITEM_SUCCEEDED = "succeeded"
ITEM_FAILED = "failed"
ITEM_SKIPPED = "skipped"
ITEM_OUTCOMES = (ITEM_SUCCEEDED, ITEM_FAILED, ITEM_SKIPPED)


@dataclass(frozen=True)
class ItemResult:
    """One item of a batch: what it was, what happened, what they said.

    ⚠ `ref` IS THE NUMBER A CLERK WOULD SEARCH FOR, NEVER A DATABASE ID (B14
    rule 31) — the account number `A-10432`, the meter number, the file name.
    `detail` is the thing itself in the clerk's words (the address the message
    was going to); the two are separate because frame 51.1 shows both and one
    of them is how you find the customer while the other is what you fix.
    `provider_text` is THEIRS, scrubbed by the adapter (`scrubbing.scrub`).

    Wave C stores the items a run could NOT do on the run row itself
    (`IntegrationRun.items`); the ones it could are counted, and their per-item
    rows are the notification queue's (`US-INT-023`, wave F).
    """

    ref: str
    outcome: str
    provider_text: str | None = None
    detail: str | None = None
    #: `CR-198-BRC10` — THE PROVIDER'S OWN ID for what it accepted (Twilio's
    #: `SM…` sid), the value a later status callback names. `None` for every
    #: adapter that has no such id or does not need one; additive, so no
    #: existing adapter or kit case changes.
    provider_reference: str | None = None
    #: `CR-198-BRC10` — the provider's machine code on a refusal (Twilio's
    #: `21610`), kept beside `provider_text` so the caller can decide
    #: retryable vs not and suppression without parsing their prose.
    provider_code: str | None = None
    #: `CR-198-BRC10` — False when sending again cannot succeed (a bad number,
    #: an opted-out person). `None` = the adapter does not say, and the caller
    #: keeps its own default (retry).
    retryable: bool | None = None


@dataclass(frozen=True)
class RunResult:
    """Per-item outcomes, never a boolean (US-INT-015 TC-3).

    `confirmed` is whether the far end SAID how many it accepted. A provider
    that answered 200 and would not say has not succeeded — the runtime turns
    `confirmed=False` into `unconfirmed` (BR-INT-018), never into a green word.
    """

    items: tuple[ItemResult, ...]
    confirmed: bool
    provider_text: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "attempted": len(self.items),
            "succeeded": sum(1 for one in self.items if one.outcome == ITEM_SUCCEEDED),
            "failed": sum(1 for one in self.items if one.outcome == ITEM_FAILED),
            "skipped": sum(1 for one in self.items if one.outcome == ITEM_SKIPPED),
        }


@dataclass(frozen=True)
class ConnectionView:
    """What an adapter may see of a connection — and it holds NO secret.

    Built by the runtime from `integration_connection`, which itself holds no
    secret material (US-INT-014); the secrets travel as a separate argument
    for the length of one call and are not attached here on purpose.
    """

    provider_key: str
    environment: str
    config: Mapping[str, Any]
    label: str | None = None


# ── the protocol ────────────────────────────────────────────────────────────


class Adapter(ABC):
    """Four methods and only four. The conformance kit refuses a fifth public one."""

    #: The manifest key this adapter serves. Bound once in `adapters/__init__.py`.
    key: ClassVar[str]

    @abstractmethod
    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Provider knowledge about the NON-SECRET fields. Cheap, no network.
        The manifest's own shape check (`validate_fields`) has already run."""

    @abstractmethod
    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """The smallest real instance. Never raises for a provider's refusal —
        that is a `TestResult(ok=False, …)` with their words underneath."""

    @abstractmethod
    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch. Per-item outcomes. Retry is not yours."""

    @abstractmethod
    def describe(self, conn: ConnectionView) -> str:
        """The masked line on the card — *billing@brazosbend.example · Custom SMTP*."""


#: The four names, and the test that an adapter has exactly these as its
#: public surface (US-INT-015: "and nothing else").
PROTOCOL_METHODS = frozenset({"validate", "test", "execute", "describe"})

#: ⚠ **HOW A `token_exchange` PROVIDER MINTS, WITHOUT A FIFTH PUBLIC METHOD
#: (wave K, `US-INT-028`).** The protocol above is four methods and the
#: conformance kit refuses a fifth PUBLIC one — the design's own sentence is
#: *"if a new connector requires the suite to change, that is the signal"*. But
#: a head-end that exchanges a stored pair for a ten-minute bearer token needs
#: somewhere to put the exchange, and the exchange is provider knowledge: the
#: URL is data on the manifest (`Auth.token`), the RESPONSE SHAPE is not.
#:
#: So it is a **private** method, named here once so a runner can find it
#: without knowing which provider it is talking to. `dir()` in the conformance
#: kit skips names beginning with an underscore, so an adapter that declares it
#: still has exactly four public methods and the kit is unchanged.
#:
#: ⚠ A NAME IN A CONSTANT IS NOT A GUARANTEE (hard-won law 1). `token_minter()`
#: below RESOLVES it and answers `None` when it is absent, and the runner then
#: refuses by name rather than dialling with no token — so a manifest that
#: declares `auth.token` against an adapter that cannot mint is caught at the
#: call, in words, instead of as an authentication failure nobody can read.
TOKEN_MINT_METHOD = "_mint_token"


def token_minter(adapter: "Adapter") -> Callable[..., str] | None:
    """The adapter's private minter, or `None` when it declares none."""
    minter = getattr(adapter, TOKEN_MINT_METHOD, None)
    return minter if callable(minter) else None


#: ⚠ **WHERE THE RUNNER PUTS A TOKEN IT HAS ALREADY MINTED, AND WHY IT MUST**
#: (wave K, `US-INT-028` TC-1). `execute()` takes the secrets for one call, and
#: an adapter left to mint its own token would mint on **every page** — a walk
#: of 105 windows would exchange 105 times instead of the twelve a ten-minute
#: token actually needs, and `runtime.TokenCache` would be a cache nothing read.
#: So the runner mints through the cache and passes the result down under this
#: reserved key; the adapter uses it when it is there and mints only when it is
#: not (a `test()` press, which is one call and needs no cache).
#:
#: ⚠ **IT IS A SECRET AND IT TRAVELS WITH THE SECRETS FOR EXACTLY THAT REASON.**
#: `BR-INT-003`'s three exits — a sentence, a log line, a `describe()` — apply to
#: it precisely as they apply to the long-lived pair, and the conformance kit's
#: log-capture cases run over the same mapping.
MINTED_TOKEN_KEY = "_minted_token"

#: ⚠ **HOW A PROVIDER THAT TELEPHONES US BACK NORMALISES ITS OWN VOCABULARY,
#: WITHOUT A FIFTH PUBLIC METHOD (`CR-115-BRC05`, the two email connectors).**
#: Exactly the shape `TOKEN_MINT_METHOD` above established, for exactly the same
#: reason: the protocol is four methods, the conformance kit refuses a fifth
#: PUBLIC one, and `dir()` in the kit skips names beginning with an underscore.
#:
#: The problem it solves is `BR-INT-004`'s — *no provider hardcoded into
#: business logic*. SendGrid reports `delivered · bounce · deferred · dropped ·
#: spamreport · unsubscribe`; Postmark reports `Delivery · Bounce(+Type) ·
#: SpamComplaint · SubscriptionChange`. **Neither vocabulary may escape its
#: adapter**, and the product holds six words and nothing else
#: (`notifications.models.PROVIDER_OUTCOME_STATUSES`). The translation is
#: provider knowledge, so it belongs in the adapter; it is not one of the four
#: acts, so it is not a public method.
#:
#: ⚠ A NAME IN A CONSTANT IS NOT A GUARANTEE (hard-won law 1).
#: `feedback_normaliser()` below RESOLVES it and answers `None` when it is
#: absent, so a caller handed a provider that declares a feedback operation and
#: an adapter that cannot translate one refuses BY NAME rather than reading an
#: attribute that is not there.
FEEDBACK_NORMALISER_METHOD = "_normalise_feedback"


def feedback_normaliser(adapter: "Adapter") -> Callable[..., Any] | None:
    """The adapter's private feedback translator, or `None` when it declares none."""
    found = getattr(adapter, FEEDBACK_NORMALISER_METHOD, None)
    return found if callable(found) else None



# ── the manifest-driven shape check (BR-INT-043's vocabulary, no fallback) ──

#: A host is a name or an address — never a URL, never a space. `sftp_host`,
#: `drop_host` and SMTP's own `host` are declared `host`; a scheme typed into
#: one is the mistake this catches before the adapter tries to dial it.
#:
#: ⚠ **THIS IS DELIBERATELY NOT WIDENED, AND `url` BELOW IS WHY** (`DEF-INT-5589`).
#: A *Service address* genuinely carries a scheme and a path — Ann Arbor's
#: ArcGIS layer is named by `/SEU/SEUQualifiedAddress/FeatureServer/0/` and
#: nothing else — but SMTP and the two file drops dial a host and a port, and
#: their values are concatenated into a connection string. Letting a path into
#: `host` to serve the URL case would have widened every one of those too, so
#: the address fields moved to a kind of their own instead.
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?)*$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

#: The schemes we will dial. A closed list, for the same reason every other
#: vocabulary in this module is closed: `javascript:` and `file:` parse
#: perfectly well as URLs.
_URL_SCHEMES = ("https", "http")


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def _check_text(name: str, value: Any) -> FieldError | None:
    if not isinstance(value, str):
        return FieldError(name, message_key="integrations.field.text")
    return None


def _check_email(name: str, value: Any) -> FieldError | None:
    if not isinstance(value, str) or not _EMAIL.match(value.strip()):
        return FieldError(name, message_key="integrations.field.email")
    return None


def _check_host(name: str, value: Any) -> FieldError | None:
    if not isinstance(value, str) or not _HOST.match(value.strip()):
        return FieldError(name, message_key="integrations.field.host")
    return None


def _check_url(name: str, value: Any) -> FieldError | None:
    """An ABSOLUTE service address: scheme, host, optional port, optional path.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ASKED BEFORE IT WAS WRITTEN.** The
    obvious version of this check is `^https?://.+`, and it accepts
    `https://` followed by a space, `http://a b/c`, and a URL with a password
    in it. So the host is validated by `_HOST` — the SAME regex the `host`
    kind uses, so the two kinds cannot drift apart about what a host is — and
    everything else is refused by name below.

    ⚠ **A QUERY AND A FRAGMENT ARE REFUSED, AND THAT IS THIS FILE'S EXISTING
    POSTURE RATHER THAN caution.** `adapters/gis_city.py:_url` builds its call
    as `f"{base}?{urlencode(params)}"` — a base that already carries a `?`
    produces a URL with two of them and a parameter the service never reads.
    A fragment never leaves the browser at all, so a clerk who pasted one
    would be configuring something that cannot have an effect.

    ⚠ **A CREDENTIAL IS REFUSED BY NAME (`BR-INT-003`).** `https://user:pass@…`
    puts a password into `integration_connection.config`, which is the
    NON-SECRET half and is stored in clear. The secret half of this form
    exists precisely so that cannot happen.
    """
    if not isinstance(value, str):
        return FieldError(name, message_key="integrations.field.url")
    text = value.strip()
    refused = FieldError(name, message_key="integrations.field.url")
    if not text or any(one.isspace() for one in text):
        return refused
    try:
        parts = urlsplit(text)
    except ValueError:
        return refused
    if parts.scheme.lower() not in _URL_SCHEMES:
        return refused
    if parts.query or parts.fragment:
        return refused
    if parts.username is not None or parts.password is not None:
        return refused
    try:
        host, port = parts.hostname, parts.port
    except ValueError:  # a port that is not a number
        return refused
    if not host or not _HOST.match(host):
        return refused
    if port is not None and not 1 <= port <= 65535:
        return refused
    return None


def _check_port(name: str, value: Any) -> FieldError | None:
    if isinstance(value, bool):
        return FieldError(name, message_key="integrations.field.port")
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return FieldError(name, message_key="integrations.field.port")
    if not 1 <= number <= 65535:
        return FieldError(name, message_key="integrations.field.port")
    return None


def _check_select(name: str, value: Any, options: tuple[str, ...]) -> FieldError | None:
    if value not in options:
        return FieldError(name, message_key="integrations.field.select", params={"options": ", ".join(options)})
    return None


#: The closed vocabulary, each kind with its check. A `secret` is checked for
#: PRESENCE only (its bytes are never inspected here — they are about to be
#: encrypted). `redirect`, `mapping_editor` and `issued_secret` are not typed
#: by a person on the modal at all: the round trip, the second step and the
#: issuance supply them, so a value ARRIVING for one is refused as unknown.
_TYPED_KINDS = frozenset({"text", "email", "host", "url", "port", "secret", "select"})
assert _TYPED_KINDS <= set(FIELD_KINDS)


def validate_fields(
    manifest: Manifest,
    config: Mapping[str, Any],
    secrets: Mapping[str, Any] | None = None,
    *,
    require_secrets: bool = True,
) -> FieldErrors:
    """The shape check the manifest gives every provider for free.

    `config` carries the NON-SECRET fields, `secrets` the secret ones — split
    by the caller so a password never sits in the mapping that is about to be
    written to `integration_connection.config` (BR-INT-003). Every problem is
    returned, not just the first: a clerk fixes a form in one pass.
    `require_secrets=False` is the PATCH path: the non-secret half is checked
    against a credential that already exists and is not in hand.
    """
    problems: FieldErrors = []
    declared = {one.name: one for one in manifest.fields}
    supplied = dict(config)
    for name, value in (secrets or {}).items():
        supplied[name] = value
    for name in supplied:
        if name not in declared:
            problems.append(FieldError(name, message_key="integrations.field.unknown"))
    for one in manifest.fields:
        if one.kind not in _TYPED_KINDS:
            # Not typed by a person: a value arriving for it did not come from
            # the modal, and the runtime supplies it by another path.
            if one.name in supplied:
                problems.append(FieldError(one.name, message_key="integrations.field.unknown"))
            continue
        value = supplied.get(one.name)
        if not _present(value):
            if one.required and (require_secrets or one.kind != "secret"):
                problems.append(FieldError(one.name, message_key="integrations.field.required"))
            continue
        if one.kind == "secret":
            continue  # presence is all that is checked; the bytes are not read
        if one.kind == "text":
            found = _check_text(one.name, value)
        elif one.kind == "email":
            found = _check_email(one.name, value)
        elif one.kind == "host":
            found = _check_host(one.name, value)
        elif one.kind == "url":
            found = _check_url(one.name, value)
        elif one.kind == "port":
            found = _check_port(one.name, value)
        else:  # select — the last member of _TYPED_KINDS; no fallback branch
            found = _check_select(one.name, value, one.options)
        if found is not None:
            problems.append(found)
    return problems


def split_fields(manifest: Manifest, values: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """`(config, secrets)` — the modal's one mapping, split by the manifest's
    field kinds so the caller cannot write a secret into the wrong table."""
    secret_names = {one.name for one in manifest.fields if one.is_secret}
    config: dict[str, Any] = {}
    secrets: dict[str, str] = {}
    for name, value in values.items():
        if name in secret_names:
            if _present(value):
                secrets[name] = str(value)
        else:
            config[name] = value
    return config, secrets


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-015@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packets US-INT-017@62d3643 · US-INT-019@62d3643)
# generated: 2026-09-03 by the CR-069 wave B build lane
# checklist: A✔ B✔ C✔ D✔(POST /integrations/{key}/connect runs validate_fields + adapter.validate before any write) E✔(ConnectModal.tsx renders field errors under the field) F✔ G✔ H=n/a(no RLS, no money — the secret's handling is asserted by the kit)
# gates: pytest tests/test_us_int_015_adapters.py · conformance.py (every registered adapter, unchanged) · G77 (no provider_key branch here — a provider is data)
# exceptions: no REAL adapter is registered by this wave (wave E's email_smtp.py is the first); the kit's fixture adapters live in conformance.py and are never registered at ready()
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
