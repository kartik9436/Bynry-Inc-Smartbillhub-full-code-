# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-013 (EP-INT-05) — the manifest registry: a provider is one
#           declarative object, and seven readers read it. US-INT-018 — operations,
#           not providers, are the unit. Screens: S8 (the card grid draws this)
# Rules:    BR-INT-037 (P1 — configuration is data, not code; adding a provider
#           touches no screen, no endpoint and no migration) · BR-INT-028 (a
#           provider is a set of operations; one partner is one card, one
#           credential) · BR-INT-001 (the v1 connector matrix decides
#           `disposition`; nothing else may) · BR-INT-030 (the reply may never
#           sit before `authenticate` — refused at load) · BR-INT-033 (an
#           unregistered codec name is refused by name with the list of what
#           exists) · BR-INT-043 (the field slot is a CLOSED vocabulary of kinds) ·
#           BR-INT-053 (`certified` with no certificate id is refused) ·
#           CR-069 §13 gate 3 (every operation names its idempotency mode AND its
#           completion mode — refused at registration, never at run time)
# Tests:    06-backend/tests/test_us_int_013_registry.py (TC-2 · TC-3 · TC-4 ·
#           TC-6 · US-INT-018 TC-3) · 10-scripts/gates/g76_operation_modes.py
# Impacts:  apps/integrations/manifests/ (the seventeen) · apps/integrations/apps.py
#           (registers them at ready()) · selectors.py (the card read model) ·
#           07-frontend/src/features/integrations/IntegrationsTab.tsx (draws it)
# ───────────────────────────────────────────────────────
"""THE registry — manifests in, refusals at load, and nothing else.

WHAT THIS IS
------------
A provider is ONE declarative object: its key, category, display name,
disposition, auth mode and placement, fields with their kinds, conformance
claim, and its operations — each with its own direction, initiative,
transport, trigger, codec, envelope status map, idempotency mode, reply
position, completion mode and test action. **Seven readers, one source:** the
card grid (category · name · disposition), the modal field slot (fields ·
kinds), runner selection (direction × initiative), the projection, the
scheduler, the response envelope and the auth mode all read the objects
registered here. **Every arrow points inward: the registry reads nothing and
calls nothing** — no database, no network, no settings.

Manifests are data in `apps/integrations/manifests/`, one file per provider,
registered by `apps/integrations/apps.py` at `AppConfig.ready()`. A coming-soon
card is the same object with `disposition.kind == "coming_soon"` and no adapter
registered; `adapter_for()` answers `None` as a VALUE, and nothing raises
(US-INT-013 TC-6).

WHAT IS REFUSED, AT LOAD AND NEVER AT RUN TIME
----------------------------------------------
`register()` raises `ManifestError` — naming the provider key and, where one
is involved, the operation — for:

  * an operation missing its idempotency mode or its completion mode
    (`CR-069` §13 gate 3; US-INT-013 TC-2)
  * a reply position before `authenticate` (`BR-INT-030`; TC-3)
  * a codec name not in the codec vocabulary (`BR-INT-033`) — refused BY NAME
    with the list of what exists
  * a `certified` conformance claim with no certificate id (`BR-INT-053`; TC-4)
  * a field of an unknown kind (`BR-INT-043`)
  * a vocabulary for a kind of thing we do not have, or one that ships no
    words and is not open (`BR-INT-032`; wave D)
  * a provider with zero operations (`BR-INT-028`; US-INT-018 TC-3)
  * a value outside any closed vocabulary below, a duplicate key, a coming-soon
    disposition with no wave label (`BR-INT-001` says the label is on the card),
    an operation that is called by the partner (`initiative == "them"`) with no
    reply position, or one that is not and yet declares one

So a mistake in a manifest fails `manage.py check`, `manage.py runserver`,
`manage.py migrate` and the test session on the developer's own machine —
which is where a configuration error is cheap. A run-time refusal would fail
the first real batch at 06:02 on the first of the month instead.

⚠ THE CODEC VOCABULARY IS READ FROM `codecs.py` (wave D, 2026-09-03). Until
then `CODECS` was a constant here; `BR-INT-033` says a format is a registered
codec, separate from the projection, and the registry of codecs now exists at
`apps/integrations/codecs.py`. `codec_names()` below reads it at validate
time, so a codec registered after import counts, and a manifest naming a name
nobody registered is refused exactly as before — by name, with the list.

⚠ ONE VALUE THE STORY'S TABLE DID NOT LIST, AND WHY (lane judgment, decision
log 2026-09-03): `auth.placement` gains **`native`**. The story lists `header ·
bearer · query · redirect`, which are positions in an HTTP request. SMTP AUTH
and SFTP carry the credential inside the protocol's own handshake — there is
no HTTP position to name — and writing `header` for a mail server would be a
lie the modal would then draw. `none` is also allowed, for a provider with no
credential at all (the public tile server, the Census geocoder).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

# ── closed vocabularies ─────────────────────────────────────────────────────

DIRECTIONS = ("in", "out")  # which way the data moves
INITIATIVES = ("us", "them")  # who starts it
#: ⚠ **`platform_holds_ours` ADDED 2026-10-29 (`CR-198-BRC10`) — THE FIFTH MODE
#: `DEF-INT-5636` SAID WAS MISSING.** *We hold OUR OWN credential and send on
#: every utility's behalf* (PO 2026-10-29, ruling 4B: one shared platform Twilio
#: account). The credential is a SERVER SECRET read by `platform_sms.py`; it is
#: never in `integration_credential` (RLS FORCED, tenant-owned) and never typed
#: by a utility, so a provider in this mode is never CONNECTED — its card is
#: *provided by the platform* and `services.connect_with_fields` refuses it by
#: name. Only SMS uses it; email still ships `we_hold_theirs` (`DEF-INT-5636`
#: stays open for email).
MODE_PLATFORM_HOLDS_OURS = "platform_holds_ours"
AUTH_MODES = (
    "we_hold_theirs",
    "they_hold_ours",
    "token_exchange",
    "none",
    MODE_PLATFORM_HOLDS_OURS,
)
AUTH_PLACEMENTS = ("header", "bearer", "query", "redirect", "native", "none")

# ── how a partner PROVES it is them at the inbound door ─────────────────────
#
# ⚠ **`AUTH_PLACEMENTS` ABOVE IS THE OUTBOUND HALF AND CANNOT ANSWER THIS
# QUESTION.** It says where OUR credential sits in a request WE build. The
# inbound door (`inbound.py`) is the other direction — a partner posting to
# us — and until 2026-09-17 it had exactly one answer: read a credential out
# of the header the manifest names (`inbound.presented_key`). Two connectors
# that are about to be built cannot be served that way at all:
#
#   * **SendGrid signs the body.** It presents no credential. It sends
#     `X-Twilio-Email-Event-Webhook-Signature` and
#     `X-Twilio-Email-Event-Webhook-Timestamp` and expects us to recompute the
#     signature over `timestamp + body` with a verification key issued when the
#     webhook was created. `presented_key` has nothing to read, so the only way
#     to accept the call today is to turn authentication off — on a route that
#     writes delivery state.
#   * **Postmark puts HTTP Basic credentials in the URL**, so the credential
#     arrives as `Authorization: Basic <base64>` rather than in a header we
#     name.
#
# ⚠ **A CLOSED VOCABULARY AND NOT AN `if key == "sendgrid"`.** `BR-INT-037`:
# configuration is data. `G77` fails a provider-key branch. So the STYLE is
# declared on the manifest, refused at load by name when it is outside this
# list, and `inbound.verify()` dispatches on the declared word.
VERIFY_PRESENTED_KEY = "presented_key"
VERIFY_SIGNATURE = "signature"
VERIFY_BASIC = "basic"
INBOUND_VERIFICATIONS = (VERIFY_PRESENTED_KEY, VERIFY_SIGNATURE, VERIFY_BASIC)

#: How a signature is computed. **SYMMETRIC ONLY, AND THE NARROWNESS IS THE
#: DESIGN RATHER THAN A SHORTCUT.**
#:
#: The door's one authenticator is `runners/serve.resolve_caller`, which
#: identifies a caller by the blind index of the secret it presented and then
#: applies six guards to it. A SHARED-SECRET signature keeps that statement
#: exactly true: recomputing an HMAC proves the caller knew the same bytes we
#: hold, so the door may honestly hand those bytes to `resolve_caller` as
#: *what the caller proved knowledge of*, and every other guard — revoked,
#: expired, allowlist, connector off, scope, utility live — goes on being
#: applied by the one function that has always applied them.
#:
#: ⚠ **AN ASYMMETRIC ALGORITHM BREAKS THAT AND IS THEREFORE NOT IN THE LIST.**
#: With ECDSA the stored value is a PUBLIC key: verifying proves the sender
#: holds a private key we have never seen, and the public half identifies a
#: connection without proving anything about possession. That is a different
#: security statement and it needs a different answer to *which credential row
#: is this caller* — so it is refused BY NAME at load rather than accepted and
#: quietly mis-modelled. ⚠ **SendGrid's real Event Webhook may well be that
#: case**; which algorithm the going-live manifest declares is the manifest
#: lane's to establish, and `test_signature_algorithms_are_symmetric_only`
#: goes RED the day a value is added here, which is how the question gets
#: asked instead of assumed (hard-won law 2 — a hold with a test on it).
SIGNATURE_ALGORITHMS = ("hmac_sha256",)
#: WHICH BYTES ARE SIGNED. Vendors differ and the difference is silent: sign
#: the wrong string and every valid call is refused, which looks exactly like
#: a wrong key. SendGrid and Stripe sign `timestamp + body`; GitHub and
#: Postmark-style hooks sign the body alone.
SIGNED_PAYLOADS = ("timestamp_body", "body")
#: How the signature is spelled on the wire. SendGrid is base64; a hex digest
#: is the other common spelling.
SIGNATURE_ENCODINGS = ("base64", "hex")
#: BR-INT-043 — the closed vocabulary of field kinds, including the three a
#: plain field cannot express: a redirect, a mapping editor, an issued secret.
FIELD_KINDS = (
    "text",
    "email",
    "host",
    # ⚠ **A WHOLE SERVICE ADDRESS, AND IT IS NOT `host` WIDENED** (`DEF-INT-5589`,
    # PO 2026-09-17: *"a) build it now with the Edit fix"*). The City of Ann
    # Arbor's ArcGIS service is named by its PATH —
    # `/SEU/SEUQualifiedAddress/FeatureServer/0/` — so a *Service address*
    # declared `host` could not hold the one value the customer has. `host`
    # stays host-only because SMTP and the two file drops dial a host and a
    # port and concatenate it into a connection string.
    "url",
    "port",
    "secret",
    "select",
    "redirect",
    "mapping_editor",
    "issued_secret",
)
#: A value of one of these kinds lands in `integration_credential.payload_enc`
#: and never in `integration_connection.config`.
SECRET_FIELD_KINDS = frozenset({"secret", "issued_secret"})
#: The kinds that mean *this field holds an address*. Named ONCE because three
#: readers ask the question — `selectors.host_fallback_field` (which column to
#: draw), `page_policy` (which origin a browser may fetch) and the setup screen
#: — and three copies of it is `DEF-INT-4252` again. ⚠ `host` is a bare name;
#: `url` is a whole service address. Both are addresses, which is what these
#: callers are asking.
ADDRESS_FIELD_KINDS = frozenset({"host", "url"})

#: ⚠ **ONE NAMED, DATED EXEMPTION FROM THE SEEDED-DEFAULT CHECK BELOW, AND IT
#: IS A HOLD WITH A TEST ON IT.** `DEF-INT-5590` moved nineteen *Service
#: address* fields to `url` so their seeded defaults became values their own
#: form accepts. `pay_invoicecloud.base_url` is the twentieth and is NOT fixed
#: here: on 2026-09-17 another lane held that file open for `CR-111-BRC04`,
#: and editing a file a sibling is mid-edit in is how law 11's revert-by-
#: subtraction happens. Without this entry the check refuses that manifest at
#: `AppConfig.ready()` and the whole product fails to start.
#:
#: **THE FIX IS ONE WORD** — `kind="host"` → `kind="url"` in
#: `manifests/pay_invoicecloud.py` — and it belongs to whoever next touches
#: that file (`DEF-INT-5592`). ⚠ **DELETE THIS ENTRY IN THE SAME COMMIT.**
#: `tests/test_def_int_5589_service_address_url.py` asserts this set is
#: EXACTLY this one pair, so the day the manifest is fixed the suite goes RED
#: and names it — hard-won law 2: a hold with no test that fires when it
#: expires is a promise nobody is keeping.
SEEDED_DEFAULT_EXEMPTIONS = frozenset({("pay_invoicecloud", "base_url")})
#: BR-INT-032 — the kinds of OUR things a partner may have a word for. ONE
#: list: `models.TARGET_ENTITY_TYPES` imports it, so the column's choices and
#: a manifest's vocabulary cannot drift (03-field-map.md §5).
MAPPING_ENTITY_TYPES = (
    "ledger_account",
    "tender",
    "route",
    "reversal_reason",
    "meter_type",
    "service",
)
IDEMPOTENCY_MODES = ("refuse", "reconcile")  # BR-INT-029
IDEMPOTENCY_SOURCES = (  # BR-INT-020 — the key is declared by the operation's shape
    "queue_row_id",  # message out: per-item queue row id
    "period_target",  # file out: period + target
    "content_hash",  # file in: computed BEFORE parse
    "provider_event_id",  # call in: the provider's event id (composite with a reversal marker)
    "request_key",  # a key WE mint and store before the request leaves (BR-INT-052)
    "natural_key",  # reconcile by the thing's own identity (meter + read_at, parcel)
    "none",  # a read with nothing to deduplicate
)
COMPLETIONS = ("immediate", "submit_poll_collect")  # BR-INT-046
#: BR-INT-046 `C20` — what a submit-poll-collect operation gets back when the
#: vendor has finished. `link` is a URL we store as the run's artifact; `handle`
#: is an identifier we collect BY into our own artifact store. ⚠ ONE RUNNER
#: SERVES BOTH — the value is read, never branched on per provider, which is
#: what makes Neptune's two API versions one code path (US-INT-031 TC-2).
RESULT_DELIVERIES = ("link", "handle")
#: BR-INT-030 — the guard pipeline, in order. `respond_after` names a position
#: in it and may never be `receive`, which is the position before `authenticate`.
GUARD_PIPELINE = ("receive", "authenticate", "dedupe", "persist", "apply")
#: ── `CR-174-BRC10` · WHAT AN OPERATION THAT REPLIES AFTER `apply` DOES ──────
#: PO 2026-10-07 (D1), verbatim: *"(a). A person standing at a machine needs
#: the live balance. Runbooks still handle the exceptions in D2."* That ruling
#: moved `BR-INT-058`'s line FOR US PAYMENTS: the door no longer stops after
#: `dedupe` there. It is declared per OPERATION, as one of these three words,
#: and `inbound.py` reads the word — so the kiosk, which declares none, still
#: applies nothing, and no line anywhere branches on a provider key (G77).
APPLY_ACCOUNT_LOOKUP = "account_lookup"
APPLY_RECORD_PAYMENT = "record_payment"
APPLY_REVERSE_PAYMENT = "reverse_payment"
APPLY_KINDS = (APPLY_ACCOUNT_LOOKUP, APPLY_RECORD_PAYMENT, APPLY_REVERSE_PAYMENT)
#: The HTTP verb a partner uses for an operation. `GET` only for a read — an
#: operation that dedupes a message has a body to dedupe.
HTTP_METHODS = ("GET", "POST")
#: Our CONCEPTS, each mapped by a manifest to THEIR field name (`Operation.
#: wire`). The first seven are read from what they send; the last nine are the
#: names an account lookup answers in. A partner's spelling is data, never code.
WIRE_REQUEST_CONCEPTS = (
    "account",  # the account number, an exact string
    "amount",  # money, two decimals, positive
    "occurred_at",  # RFC 3339 UTC — when the payment (or the return) happened
    "method",  # their tender word, resolved through the `tender` vocabulary
    "channel",  # where the customer was — kept, shown, never refused
    "terminal",  # which machine — kept, shown
    "return_code",  # the bank's own Nacha code on a return
)
WIRE_REPLY_CONCEPTS = (
    "found",
    "balance",
    "past_due",
    "allow_payments",
    "allow_check",
    "allow_credit",
    "allow_debit",
    "display_credit",
    "residential",
)
WIRE_CONCEPTS = WIRE_REQUEST_CONCEPTS + WIRE_REPLY_CONCEPTS
#: What each apply kind cannot work without, refused at LOAD by name.
WIRE_REQUIRED: Mapping[str, tuple[str, ...]] = {
    APPLY_ACCOUNT_LOOKUP: ("account",) + WIRE_REPLY_CONCEPTS,
    APPLY_RECORD_PAYMENT: ("account", "amount", "occurred_at", "method"),
    APPLY_REVERSE_PAYMENT: ("account", "amount", "occurred_at"),
}
#: The outcomes each apply kind can answer, so a status number is never typed
#: in the door (`BR-INT-045`). `invalid` is a body we cannot act on (400);
#: `failed` is our own fault and the partner retries the identical body (500);
#: `not_yet` is a return whose payment has not arrived (they retry).
APPLY_OUTCOMES: Mapping[str, tuple[str, ...]] = {
    APPLY_ACCOUNT_LOOKUP: ("ok", "refused"),
    APPLY_RECORD_PAYMENT: ("ok", "duplicate", "refused", "invalid", "failed"),
    APPLY_REVERSE_PAYMENT: ("ok", "duplicate", "refused", "invalid", "failed", "not_yet"),
}
TRANSPORTS = ("smtp", "https", "sftp", "file", "browser")
TRIGGERS = ("manual", "scheduled", "dispatcher", "webhook", "partner", "inline")
EXECUTORS = ("server", "browser", "browser_credentialed")  # BR-INT-048
#: The two executors that run in the VIEWER's browser rather than on our
#: server. One list, because three readers ask the same question — the
#: page-security policy (`page_policy.py`), the card's *the call is made by the
#: browser* line, and the load-time refusal of a required secret on a browser
#: operation — and a second copy is the one that goes stale.
BROWSER_EXECUTORS = frozenset({"browser", "browser_credentialed"})
#: `BR-INT-048` / `C16` — what happens to what came back. `load` writes it;
#: `offer` shows it and writes NOTHING until a person picks a row. The address
#: search is `offer`, and that is the whole of `C16`: a clerk typing an address
#: has not asked for a premises to exist.
RESULT_DISPOSITIONS = ("load", "offer")
#: `BR-INT-048` / `C15` — the default latency budget for an INLINE operation
#: our server executes, in milliseconds. *"Candidates in under a second"* is
#: `US-INT-042` §1's own number and `M3`'s TC-1 asserts it.
DEFAULT_LATENCY_BUDGET_MS = 1000
CONFORMANCE_CLAIMS = ("self_declared", "compatible", "certified")  # BR-INT-053
DISPOSITION_LIVE = "live"
DISPOSITION_COMING_SOON = "coming_soon"
DISPOSITIONS = (DISPOSITION_LIVE, DISPOSITION_COMING_SOON)


def codec_names() -> tuple[str, ...]:
    """Every registered codec name — `codecs.py`'s list, read when a manifest
    is validated rather than when this module was imported (BR-INT-033)."""
    from apps.integrations import codecs  # pure; imports no Django and no registry

    return codecs.names()


def notification_classes() -> tuple[str, ...]:
    """The KINDS OF MESSAGE this product sends — notifications' own list.

    Read through `seams/notifications.py` at validate time, exactly as
    `codec_names()` reads `codecs.py`, so this file holds no second copy of a
    vocabulary another module owns (hard-won law 1 — two lists are two answers
    drifting apart in silence, and `G6` rule 4 forbids the shortcut of
    importing the owner's models).

    ⚠ **IT IS `apps.notifications.catalogs.CR_CATEGORIES` AND NOT ONE OF THE
    OTHER TWO CANDIDATES**, and the choice is written down because it is not
    obvious. Notifications carries two category axes: `rule_catalog.CATEGORIES`
    (six values — what part of the business SCHEDULES a message) and
    `catalogs.CR_CATEGORIES` (five values — what part of the business SENDS
    one, `CR-007`, the PO's own SET-09 chips). A per-class connector setting is
    resolved at SEND time, and what a sender holds is an `OutboundMessage` with
    a `template_code`; `catalogs.listing_for(code).category` turns that into one
    of these five. The rule axis is not reachable from a message at all.

    ⚠ **AN EMPTY ANSWER IS A REFUSAL AND NOT AN OPEN DOOR** (hard-won law 3).
    If notifications cannot be read, `validate()` refuses the manifest by name
    rather than accepting whatever class names it happened to carry.
    """
    from apps.integrations.seams import notifications as notifications_seam

    return notifications_seam.notification_classes()


class ManifestError(ValueError):
    """A manifest declared something the registry refuses. Raised at LOAD.

    The message always names the provider key, and the operation where one is
    involved, so the process that refuses to start says which file to open.
    """


# ── the declarative objects ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Field:
    """One entry of the modal's field slot (BR-INT-043)."""

    name: str
    label: str
    kind: str
    required: bool = True
    #: For `select`: the closed list of values. For everything else: empty.
    options: tuple[str, ...] = ()
    #: `CR-110-BRC04` wave C — the phase-1 placeholder address a connector
    #: that dials out ships with.
    #:
    #: ⚠ **NOTHING READS IT YET, AND THIS LINE CLAIMED OTHERWISE UNTIL
    #: 2026-09-17 (`DEF-INT-5595`).** It read *"the value provisioning writes
    #: into the connection's config when nobody has typed one"*, and no such
    #: writer exists: `live_calls.LIVE_CALL_DEFAULTS` is a separate hardcoded
    #: dict of two entries and is not derived from this, and the set-up form
    #: does not pre-fill from it — pressing Connect shows an EMPTY box. That is
    #: hard-won law 1, a comment claiming a guarantee that is not the
    #: guarantee, and it is what let **nineteen** values that no form would
    #: accept sit here unnoticed (`DEF-INT-5590`): they looked load-bearing, so
    #: nobody checked them, and they were load-bearing for nothing, so nothing
    #: went red. The values are now VALIDATED below whether or not anyone reads
    #: them, which is the half that can be fixed from here; wiring the reader
    #: — or deleting the promise — is `DEF-INT-5595`. **This is the whole of
    #: the PO's phase-1 dummy API** (2026-09-16, *"i want you to put dummary
    #: apis in all these 28 conenctor - in phase 2 we will replace them and
    #: build a actual logic around them"*): a connector that dials out names a
    #: host field and seeds it with a placeholder address, so `DEF-INT-5488`'s
    #: *"no connection ever holds a host"* stops being true the day the file
    #: is written rather than the day a vendor contract is signed.
    #:
    #: ⚠ **REFUSED ON EVERY SECRET KIND, BY NAME.** A seeded secret is a
    #: credential in the repository — hard-won law 3 says the unsafe option is
    #: the one you type, and here the unsafe option must not be typeable at
    #: all. `redirect` and `mapping_editor` take none either: neither holds a
    #: value a clerk could have typed.
    default: str = ""
    #: **ONE VALUE PER KIND OF MESSAGE** — a setting that is not one value but
    #: a value per notification class, with `default` as the fallback for every
    #: class not named here.
    #:
    #: ⚠ **IT IS NOT A POSTMARK FEATURE, IT IS *THIS SETTING VARIES BY THE KIND
    #: OF MESSAGE*.** The case that forced it: Postmark's Message Streams put
    #: transactional mail on `outbound` and bulk mail on `broadcast`, and the
    #: choice is made per message rather than per connection — a login code and
    #: an outage broadcast leave the same connector on different streams.
    #: `FIELD_KINDS` already had `select`, so ONE stream was expressible; one
    #: stream PER CLASS was not expressible at all.
    #:
    #: ⚠ **THE KEYS ARE `notification_classes()` AND NOTHING ELSE** — refused
    #: at load, by name, with the list of what exists. A class name this
    #: product does not have is a setting that can never be selected, which is
    #: `DEF-INT-5488`'s shape (a declared name that resolves to nothing) in a
    #: different column.
    #:
    #: ⚠ **`default` IS REQUIRED WHEN THIS IS NON-EMPTY, AND THAT IS THE WHOLE
    #: RULE RATHER THAN A TIDINESS CHECK.** A map that names three of five
    #: classes has to answer for the other two, and *no value* is not an answer
    #: a sender can act on — it would leave the day a new class is minted as
    #: the day a connector silently sends with no stream.
    #:
    #: ⚠ **NOTHING DECLARES ONE YET AND NOTHING READS ONE YET, AND THIS LINE
    #: SAYS SO ON PURPOSE.** `Field.default` sat here for a day claiming a
    #: reader it did not have (`DEF-INT-5595`), and that is exactly what let
    #: nineteen unusable values go unnoticed (`DEF-INT-5590`). So: the values
    #: are VALIDATED whether or not anyone reads them — which is the half that
    #: can be made true from here — and `declared_value_for()` below is the
    #: resolver. **WHERE A TENANT'S OWN PER-CLASS OVERRIDE IS STORED IS NOT
    #: DECIDED HERE**: `integration_connection.config` is `{field: value}`
    #: today, and turning it into `{field: {class: value}}` is a screen, a
    #: migration and a read model that belong to the connector lane.
    per_class: Mapping[str, str] = field(default_factory=dict)
    #: CR-173-BRC10 — **A NAMED SECTION OF THE CONNECTION, WITH ITS OWN SAVE.**
    #: Empty for every field that belongs to the connection itself, which is
    #: every field until this change. A field with a group is drawn in that
    #: group's own panel (the catalogue key `integrations.group.<group>.*`
    #: names it), is saved through `file_drop`, never through connect or PATCH,
    #: and — when it is a secret — is stored in the credential SLOT of the same
    #: name, so it can never displace the connection's own key or password
    #: (`models.IntegrationCredential.slot`). Data, never a provider branch
    #: (`BR-INT-037`): New World's *Send to City folder* is the first group and
    #: a second connector with a folder to send to declares the same word.
    group: str = ""

    @property
    def is_secret(self) -> bool:
        return self.kind in SECRET_FIELD_KINDS

    def declared_value_for(self, notification_class: str | None) -> str:
        """What THIS MANIFEST declares for one kind of message.

        The per-class value when there is one, and `default` otherwise —
        including for `notification_class=None`, which means *this send is not
        classified*, and for a class the map does not name.

        ⚠ **IT IS THE MANIFEST'S ANSWER AND NOT THE CONNECTION'S.** A tenant
        that has typed its own value into the set-up form overrides this, and
        that resolution lives with whoever owns `connection.config` — see
        `per_class` above. Naming this `declared_` rather than `value_for` is
        the point: a reader who wants the EFFECTIVE value must not be able to
        reach for this by mistake.
        """
        if notification_class and self.per_class:
            found = self.per_class.get(notification_class)
            if found:
                return str(found)
        return self.default


@dataclass(frozen=True)
class Vocabulary:
    """The words a partner uses for one kind of our things (BR-INT-032).

    A manifest SHIPS the list it knows — the kiosk's fourteen tender words,
    Nacha's return codes — so S143 has rows to show before a single value has
    arrived; an inbound value nobody listed adds an unmapped row of its own
    (BR-INT-031). `values` may be EMPTY only when `open` is True: their words
    are typed rather than shipped (an accounting partner's account strings),
    and the tab draws what has been recorded so far. `label` is the tab's
    English fallback (*How they pay*); a catalogue line wins on screen.
    """

    entity_type: str
    label: str
    values: tuple[str, ...] = ()
    summary: str = ""
    open: bool = False
    #: `CR-174-BRC10` — the word an UNKNOWN arrival resolves to (*"unknown →
    #: OTHER, never refuse"*), and therefore the word that must be mapped
    #: BEFORE the connector may be switched on: with it unmapped, a payment in
    #: a tender nobody listed would have no method of ours to land under.
    #: `None` — the kiosk's — keeps the older behaviour exactly.
    fallback: str | None = None
    #: `CR-174-BRC10` — their word → OUR CODE, applied once when the connector
    #: is switched on, for every word not already mapped and only where the
    #: utility actually HAS an active value with that code. A SUGGESTION, never
    #: a creation: *"Methods come from the tenant's own payment_methods;
    #: nothing is created."*
    suggested: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Conformance:
    """A standard claimed with its evidence (BR-INT-053). ⚠ The WORDS a screen
    may use about a claim are `OQ-INT-1483` and are not decided here."""

    standard: str
    claim: str
    evidence: str
    certificate_id: str | None = None


@dataclass(frozen=True)
class Idempotency:
    """BR-INT-020 / BR-INT-029 — the key's shape and the mode.

    `mode` is Optional ONLY so that a manifest which forgets it can exist long
    enough to be refused by name; a registered operation always has one.
    """

    mode: str | None = None
    source: str = "none"
    natural_key: str | None = None
    #: WHICH field of the arriving body carries the provider's own event id
    #: (wave N, `US-INT-044`, `BR-INT-020` D). `source` says WHAT the key is;
    #: this says WHERE to find it, so `inbound.py` reads one declared name
    #: instead of guessing at three (`BR-INT-037` — configuration is data).
    #:
    #: ⚠ **IT IS NOT REQUIRED AT LOAD, AND THAT IS A DELIBERATE EXCEPTION TO
    #: THIS FILE'S OWN "REFUSE AT LOAD" POSTURE.** The obvious rule — *every
    #: operation replying at or after `dedupe` declares one* — would also
    #: catch `payments_sandbox.settlement`, whose event id is an ARGUMENT
    #: `gateway.py` composes and hands to `webhooks.settle_charge`; it never
    #: reaches `inbound.py` and has no body field to name. Demanding one there
    #: would put dead data on a manifest, which is the exact thing this file
    #: refuses for `auth.oauth` and `auth.token`. So the ONE reader enforces
    #: it: `inbound.py` fails CLOSED and names the operation and this field
    #: when a door needs a key and the manifest declares no place to find one
    #: (hard-won law 3), and `test_us_int_044_inbound_door.py` proves that
    #: refusal RED. Decision log 2026-09-06.
    key_field: str | None = None


@dataclass(frozen=True)
class OAuthEndpoints:
    """Where a `redirect` field kind actually sends a person (BR-INT-043).

    ⚠ **THIS IS DATA BECAUSE THE ADAPTER PROTOCOL HAS EXACTLY FOUR METHODS AND
    THE CONFORMANCE KIT REFUSES A FIFTH.** There is nowhere on an `Adapter` to
    hang *"where does Microsoft's sign-in live"*, and that turns out to be the
    right answer rather than a constraint worked around: `BR-INT-043` asks for
    a connect modal *"generated from the manifest's field list … no code
    branched to make that true"*, and a round trip built from three declared
    strings has no per-provider branch anywhere in it. `apps/integrations/
    oauth.py` reads these and serves every provider that declares them —
    Microsoft and Google differ by this object and by nothing else.

    `scopes` is what we ask the provider's consent screen for, and it is here
    rather than in code for the same reason: widening a permission is then a
    reviewable one-line data change on a file that has a lifecycle trailer.

    ⚠ `client_id` and `client_secret` are NOT here. They are OUR registration
    with the provider, they differ per deployment, and one of them is a secret
    — so they come from settings at call time, never from a file in the repo.
    """

    authorize_url: str
    token_url: str
    scopes: tuple[str, ...] = ()
    #: How long the provider's consent lasts, in days, when its token response
    #: does not say. Microsoft re-consents every ninety days.
    default_lifetime_days: int = 90


@dataclass(frozen=True)
class TokenExchange:
    """Where a long-lived pair is exchanged for a SHORT-LIVED bearer token.

    ⚠ **THIS IS DATA FOR THE SAME REASON `OAuthEndpoints` IS** — the adapter
    protocol has exactly four public methods and the conformance kit refuses a
    fifth, so there is nowhere on an `Adapter` to hang *"where does this
    head-end mint tokens"*. `runtime.TokenCache` reads these three numbers and
    serves every provider that declares them.

    `ttl_seconds` is **THEIRS, not ours** (`US-INT-028` decision 6): Neptune's
    bearer token is good for ten minutes and no manifest may pretend otherwise.
    `refresh_before_s` is the skew — how long before the stated expiry we stop
    trusting a token, so a call that starts at 09:59:59 does not arrive at
    10:00:01 with a dead one.

    ⚠ **NOTHING MINTED THROUGH THIS IS EVER WRITTEN DOWN.** `BR-INT-047`: token
    exchange never writes the credential table. A ten-minute token across a
    two-hour walk is about **twelve** mints; a version row per mint would be
    **144 a day** on one connection, and the rotation history a clerk reads on
    S142 would be unusable within a week.
    """

    token_url: str
    #: The provider's stated lifetime, in seconds. Neptune: 600.
    ttl_seconds: int = 600
    #: How early we re-mint. Never zero — a token that expires between the
    #: check and the call is the failure this exists to prevent.
    refresh_before_s: int = 30


@dataclass(frozen=True)
class FetchPlan:
    """How we walk THIS provider: their window, their page size (`C12`).

    `US-INT-028`: *"a fetch plan is declared per operation — `window = 7 days`,
    `page_size = {readings: 5000, meters: 150, routes: 100}`"*. ⚠ **THE STORY
    WRITES THE PAGE SIZES AS ONE DICT ACROSS THREE SERVICES AND THIS MODELS
    THEM AS ONE INTEGER ON EACH OF THE THREE OPERATIONS** — the same three
    numbers, keyed by the operation they belong to rather than by a second name
    for it. A dict on the manifest would need its keys kept in step with the
    operation names by hand, and a typo in one would be a page size nobody
    applied (lane judgment, decision log 2026-09-06).

    **None of these numbers is in code** — that is the whole of `C12`. Changing
    `page_size` here changes the request and touches no runner.
    """

    #: The provider's own chunk of time. Seven days at Neptune; a manifest that
    #: asks for thirty gets a refusal FROM THE PROVIDER naming the parameter,
    #: never a silent narrowing on our side (`US-INT-028` TC-4).
    window_days: int
    page_size: int


@dataclass(frozen=True)
class Poll:
    """`completion = submit_poll_collect`'s schedule (`C10`): every 30 s, up to 40.

    Declared TOGETHER with the completion mode or the registry refuses the
    manifest — `US-INT-031` TC-5. A submit-poll-collect operation with no poll
    schedule is a run that submits and then waits forever, which no screen can
    describe and no clerk can act on.
    """

    every_seconds: int
    max_attempts: int

    @property
    def budget_seconds(self) -> int:
        """How long the vendor has, in total — 30 × 40 = **twenty minutes**."""
        return self.every_seconds * self.max_attempts


@dataclass(frozen=True)
class InboundVerification:
    """HOW THE INBOUND DOOR SATISFIES ITSELF THAT A CALLER IS THE PARTNER.

    ⚠ **THE FIELDS ABOVE IT ARE THE OUTBOUND HALF.** `Auth.mode`,
    `Auth.placement` and `Auth.header` describe a request WE build. This
    describes a request THEY build, and the two are independent: Postmark
    takes a server token in a header when we send, and presents HTTP Basic
    when it calls back.

    ⚠ **ABSENT MEANS `presented_key`, AND AN EXPLICIT `presented_key` IS
    REFUSED.** There is exactly one spelling of each style. Declaring the
    default says nothing the absence does not, and this file already refuses
    dead data in both directions for `auth.oauth` and `auth.token` — a second
    way to say one thing is a second thing for the next lane to keep in step.

    WHAT EACH STYLE NEEDS, and every other field is refused BY NAME
    ---------------------------------------------------------------
    * **`presented_key`** — nothing here at all. `auth.placement` /
      `auth.header` already say where the credential sits and
      `inbound.credential_header()` already refuses a placement it cannot read.
    * **`basic`** — nothing here either, and that is not an oversight. The
      scheme fixes the header (`Authorization`) and the shape
      (`Basic base64(user:password)`), and the PASSWORD is a key we minted, so
      it goes to the one authenticator through the blind index exactly as a
      header-borne key does. **The style is what tells the door to read the
      Basic scheme instead of `auth.placement`.**
    * **`signature`** — all five of `signature_header`, `secret_field`,
      `algorithm`, `signed_payload`, `encoding`, plus `timestamp_header` and
      `max_skew_seconds` when the signed payload carries a timestamp.

    ⚠ **`max_skew_seconds` IS THE REPLAY WINDOW AND IT IS NOT OPTIONAL.** A
    signature over `timestamp + body` is valid for ever if nobody checks the
    timestamp: a call captured once can be replayed at any time and verifies
    perfectly. There is no safe default to fall back to, so a manifest that
    signs a timestamp and names no window is refused at load.
    """

    style: str
    #: `signature` — WHICH header carries the signature.
    signature_header: str | None = None
    #: `signature` + `signed_payload = "timestamp_body"` — which header carries
    #: the timestamp that is prefixed to the body before hashing.
    timestamp_header: str | None = None
    #: `signature` — WHICH declared field of this manifest holds the shared
    #: secret. Must name a field of a SECRET kind: the value lands in
    #: `integration_credential.payload_enc` and never in
    #: `integration_connection.config` (`SECRET_FIELD_KINDS` is the rule).
    secret_field: str | None = None
    #: `signature` — one of `SIGNATURE_ALGORITHMS`.
    algorithm: str | None = None
    #: `signature` — one of `SIGNED_PAYLOADS`.
    signed_payload: str | None = None
    #: `signature` — one of `SIGNATURE_ENCODINGS`.
    encoding: str | None = None
    #: `signature` — how far out of date a timestamp may be, in seconds.
    max_skew_seconds: int | None = None

    @property
    def signs_a_timestamp(self) -> bool:
        return self.signed_payload == "timestamp_body"


@dataclass(frozen=True)
class Auth:
    mode: str
    placement: str
    #: Wave `CR-115-BRC05` lane 4 — how the INBOUND door verifies a caller.
    #: Absent means `presented_key`, which is what every manifest written
    #: before 2026-09-17 means and what all of them go on meaning.
    inbound: InboundVerification | None = None
    #: Required when `placement == "redirect"`, refused otherwise (see
    #: `validate`). A redirect with nowhere to redirect to is a button wired to
    #: nothing — hard-won law 2, caught at load rather than by a clerk.
    oauth: OAuthEndpoints | None = None
    #: Required when `mode == "token_exchange"` and the placement is NOT a
    #: redirect — the machine-to-machine half of the same mode (wave K). A
    #: redirect exchanges a person's consent through `oauth`; a `bearer`
    #: placement exchanges a stored pair through this. Refused on any other
    #: mode, because a token endpoint nothing mints from is dead data a later
    #: lane would build on (the same argument as `oauth` above).
    token: TokenExchange | None = None
    #: WHICH header carries the credential when `placement == "header"` —
    #: `X-Kiosk-Key` for the payment kiosk (wave N, `US-INT-044`). Declared
    #: here because the inbound door has to read it, and a door that knew the
    #: name any other way would be branching on a provider key (G77,
    #: `BR-INT-037`). `bearer` needs none: the header is `Authorization` by
    #: definition, which is why `gl_partner` declares nothing.
    #:
    #: ⚠ ABSENT IS LAWFUL AND MEANS THE DOOR REFUSES. The `we_hold_theirs`
    #: connectors that place a credential in a header (`print_vendor`,
    #: `sms_twilio`, and the retired `meters_mdm` / `payments_card`) put it in
    #: a request WE build, so the name is the adapter's business and none of
    #: them names one here. `sms_twilio` also carries a feedback operation the
    #: partner calls — wave `F`'s door — and when that door is built it will
    #: need this field or `inbound.py` will turn the provider away rather than
    #: read a header it cannot name (hard-won law 3).
    #:
    #: ⚠ **`postmark` IS THE FIRST TO NAME ONE (`CR-115-BRC05`).** It declares
    #: `X-Postmark-Server-Token` because it also declares an `auth.inbound`
    #: style, and a door that knew the header any other way would be branching
    #: on a provider key. Its ESP sibling `sendgrid` names none and needs none:
    #: it is `placement="bearer"`, where the header is `Authorization` by
    #: definition.
    header: str | None = None
    #: `CR-174-BRC10` — OPTIONAL headers a partner sends to name the utility in
    #: THEIR terms (US Payments' `enterpriseId` / `companyId`), each mapped to
    #: the connection field that holds our copy. **Verified, never used to
    #: select** — the utility comes from the key (`serve.company_id_matches`
    #: makes the same argument): a header that is sent and does not match is
    #: refused in the door's one refusal; a header not sent is not checked.
    identity_headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Disposition:
    """BR-INT-001 made into data. `wave` is the label the card shows next to
    *Coming soon* (`W7`, `v1.1`, `v2`); `phase` is which `CR-069` phase makes a
    LIVE provider connectable (informational — a live card with a later phase
    still refuses to connect until its adapter is registered)."""

    kind: str = DISPOSITION_LIVE
    wave: str | None = None
    phase: int | None = None

    @property
    def coming_soon(self) -> bool:
        return self.kind == DISPOSITION_COMING_SOON


@dataclass(frozen=True)
class Operation:
    """One thing a provider does (BR-INT-028). Direction × initiative picks the
    runner; the rest declares how it runs, how it is keyed and how it replies.

    `idempotency` and `completion` are Optional ONLY so a manifest that omits
    them can be refused by name (US-INT-013 TC-2). No registered operation
    lacks either.
    """

    name: str
    label: str
    direction: str
    initiative: str
    transport: str
    trigger: str
    idempotency: Idempotency | None = None
    completion: str | None = None
    codec: str | None = None
    #: Inbound only (initiative == "them"): where the reply sits (BR-INT-030).
    respond_after: str | None = None
    #: BR-INT-045 — declared status numbers; the adapter contains none.
    envelope_status: Mapping[str, int] = field(default_factory=dict)
    executor: str = "server"
    #: `BR-INT-048` / `C15` — **a latency budget, not a job.** An operation our
    #: SERVER runs `inline` has to answer while a person is looking at the
    #: screen, so it declares how long that is; when the wait passes the budget
    #: the breaker's arithmetic is fed a timeout and the field says so rather
    #: than spinning. Required for a server-executed `inline` operation WE
    #: initiate, and refused on every other kind, because a budget on a nightly
    #: job is a number nobody reads.
    #:
    #: ⚠ **A BROWSER-EXECUTED INLINE OPERATION DECLARES NONE, AND THAT IS NOT
    #: AN OVERSIGHT.** Map tiles are `inline` and `browser`: we are not the one
    #: waiting, we do not hold the socket, and we could not enforce a deadline
    #: on it if we declared one. A budget we cannot enforce is hard-won law 1 —
    #: a comment claiming a guarantee — so the validator refuses it by name.
    latency_budget_ms: int | None = None
    #: `BR-INT-048` / `C16` — `load` or `offer`. See `RESULT_DISPOSITIONS`.
    result_disposition: str | None = None
    #: WHICH non-secret config field holds THIS operation's host.
    #:
    #: ⚠ **ONE CONNECTION CAN HOLD TWO HOSTS, AND ASSUMING IT HOLDS ONE PUT THE
    #: WRONG ONE IN A SECURITY HEADER (`DEF-INT-4259`).** `gis_city` is one
    #: relationship with one city and TWO addresses: an address service our
    #: server calls, and a tile server the BROWSER draws from (`US-INT-042` §4
    #: names them separately). The policy generator read `base_url` for every
    #: browser operation, so the header permitted the ADDRESS service as an
    #: image source and did not permit the tile server at all — the city's own
    #: map would have been blocked, and nothing but a browser could see it.
    #:
    #: A connection with no value for its operation's declared field
    #: contributes NO host (hard-won law 3 — the permissive answer is earned).
    #:
    #: ⚠ **AND FROM `CR-110-BRC04` THE NAME HAS TO RESOLVE.** `DEF-INT-5488`:
    #: fifteen of eighteen manifests named `base_url` and declared no such
    #: field, so the value was permanently absent and the endpoint the
    #: blueprint draws on every API row could be served for three connectors
    #: out of eighteen. `validate()` now refuses a manifest whose operation
    #: names a host field the manifest does not declare — for operations WE
    #: initiate only; see `_validate_hosts` for the exemption and why it is
    #: narrow.
    host_field: str = "base_url"
    #: `CR-110-BRC04` (PO 2026-09-16) — **the DEFAULT ceiling for this
    #: operation, in calls a minute, that provisioning copies into the
    #: connection's own row.** Required, and refused below when absent: the
    #: blueprint draws a limit on all 78 operation rows, and an operation with
    #: no ceiling is a door with no guard (hard-won law 3).
    #:
    #: ⚠ **IT IS A GUARD, NOT A SETTING.** PO, verbatim: *"so wecant allow
    #: clark to reset it; you can have shared counter - and keep nthe check in
    #: code - thats it - it will solve - keep the limit in database so if we
    #: want to change it later it is easy to do."* So the number is display
    #: only on screen, nobody may edit it from the product, and the row it is
    #: copied into plus the shared counter behind `serve.check_rate_limit` are
    #: another lane's work. **Because no clerk can correct it, a wrong default
    #: here is a support call rather than a five-second fix** — every value in
    #: this repo's manifests was chosen deliberately and its reasoning is in
    #: the file that declares it.
    #:
    #: ⚠ **THE FIGURES DRAWN IN THE BLUEPRINT ARE ILLUSTRATIONS** (B14 rule 37,
    #: and the blueprint says so of itself on p017: *"No value here was read
    #: from anything"*). None of them was copied.
    #:
    #: ⚠ **THE MANIFEST CARRIES THE DEFAULT AND THE DATABASE CARRIES THE
    #: LIMIT**, which is the blueprint's p017 split: a manifest is code data
    #: shared by every tenant, so it cannot hold a number that differs between
    #: two utilities, and a quota a bigger utility bought is exactly such a
    #: number. This is a starting value, copied once at connect; changing it
    #: here moves no existing row. Absent means
    #: `runners/serve.DEFAULT_RATE_LIMIT_PER_MINUTE`.
    #:
    #: ⚠ **THIS FIELD WAS DECLARED TWICE IN THIS CLASS UNTIL 2026-09-16
    #: (`DEF-INT-5523`).** Waves C and D each added it, with the same type and
    #: the same default, so the second silently won and nothing anywhere could
    #: go red — while the two comment blocks above them said two different
    #: things, which is hard-won law 1 with a duplicate: the field was fine and
    #: the RECORD of it was two records. The paragraphs are merged here.
    #:
    #: ⚠ **INWARD AND OUTWARD ARE TWO DIFFERENT FACTS IN ONE NUMBER** and the
    #: drawing says so: *"Outward the limit is what they allow us; inward it is
    #: what we allow them."* Only the inward half is enforced today — by
    #: `serve.check_rate_limit`, which is the PO's hacking case. The outward
    #: half is declared and not enforced; the outward throttle is recorded in
    #: `CR-110-BRC04` as struck from scope by the PO's *"thats it"*.
    rate_limit_per_minute: int | None = None
    #: BR-INT-019 — the smallest real instance of the operation, in words, or
    #: None when the provider offers no safe instance (the card then reads
    #: *cannot be tested until first use*).
    test_action: str | None = None
    #: Wave K (`C12`, `BR-INT-047`) — how we walk this operation: their window,
    #: their page size. Absent means one request, no walk.
    fetch_plan: FetchPlan | None = None
    #: Wave K (`C10`, `BR-INT-046`) — required with `completion =
    #: submit_poll_collect`, refused with `immediate`.
    poll: Poll | None = None
    #: Wave K (`C20`) — `link` or `handle`. Required and refused on the same
    #: terms as `poll`.
    result_delivery: str | None = None
    #: Wave K (`C18`, `BR-INT-050`) — request parameters whose DEFAULT IS
    #: UNSAFE. The runner refuses to start a request that leaves one unset and
    #: names it. ⚠ Four of Neptune's are unsafe and two of those are on the
    #: money path: a collection that omits `actual_consumption` comes back with
    #: ESTIMATED figures that look exactly like reads, and a utility bills them.
    safety_parameters: tuple[str, ...] = ()
    #: Wave K (`C19`, `BR-INT-050`) — this operation CHANGES THE PARTNER'S
    #: WORLD. Neptune's `CloseOnExport` closes billing routes on their side, so
    #: a retry that ran it twice would close them twice. An operation that
    #: declares this must also declare an idempotency source WE mint before the
    #: request leaves (`request_key`) — refused at load otherwise.
    mutates_partner_state: bool = False
    #: Wave B (US-INT-019 · BR-INT-026): the test needs a TYPED address — one
    #: real message to a recipient a person types, never a customer list. The
    #: API refuses a test request with no recipient when this is set, before a
    #: job exists. Declared here, as data, so no code branches on a provider.
    test_needs_recipient: bool = False
    #: `CR-110-BRC04` phase 2 (PO 2026-09-16) — **OUR OWN ADDRESS, for the one
    #: relationship where the endpoint on the row is ours rather than theirs.**
    #:
    #: A `they_hold_ours · out · them` operation is a door WE publish and a
    #: partner dials. There is no host in the connection's settings for it,
    #: because there is no vendor host: the address is a route in this product.
    #: So `_operation_row`'s endpoint column drew a dash on every such row —
    #: not because a value was missing, but because the column asks a question
    #: that has no answer for this quadrant (hard-won law 7, *structurally
    #: incapable of showing anything*, which `DEF-INT-5502` already recorded
    #: one shape along).
    #:
    #: ⚠ **IT IS DATA AND NEVER A BRANCH** (`BR-INT-037`). The alternative was
    #: for `selectors.py` to know that Aclarian's `serve_bill` is served at
    #: `/partner/v1/bills`, which is a provider name inside a screen's code —
    #: exactly what `G77` fails a gate for.
    #:
    #: ⚠ **THE TENANT SEGMENT IS NOT IN IT AND THAT IS DELIBERATE.** What a
    #: partner dials is `/api/partner/v1/bills` — no utility since 2026-09-16
    #: (`DEF-INT-5546`); what is declared here is that path without the `/api`
    #: mount, which `addressing.OUR_API_ROOT` puts back for the card
    #: (`DEF-INT-10020`).
    #:
    #: ⚠ **ON AN INBOUND OPERATION THAT APPLIES (`applies`), THIS IS ALSO WHERE
    #: IT IS SERVED (`DEF-INT-10020`).** `partner_urls` builds the route from
    #: it and `inbound_api` refuses that operation at the per-utility inbound
    #: address — so US Payments has one address, and the card shows it.
    served_path: str | None = None
    description: str = ""
    #: `CR-174-BRC10` — what this door DOES after it lands a message, for an
    #: operation that replies after `apply`. One of `APPLY_KINDS`; `None` on
    #: every other operation, which is every operation before this change.
    applies: str | None = None
    #: `CR-174-BRC10` — `GET` or `POST`. A read may be a `GET`; anything that
    #: dedupes a message is a `POST`.
    http_method: str = "POST"
    #: `CR-174-BRC10` — OUR concept → THEIR field name. See `WIRE_CONCEPTS`.
    wire: Mapping[str, str] = field(default_factory=dict)

    @property
    def they_call_us(self) -> bool:
        return self.initiative == "them"


@dataclass(frozen=True)
class Manifest:
    key: str
    category: str
    display_name: str
    #: One sentence a clerk reads under the name (B14 rule 32).
    summary: str
    auth: Auth
    operations: tuple[Operation, ...]
    disposition: Disposition = field(default_factory=Disposition)
    fields: tuple[Field, ...] = ()
    conformance: Conformance | None = None
    #: The codecs a file channel may be configured with (BR-INT-033). A picker
    #: appears only where more than one is registered.
    codecs: tuple[str, ...] = ()
    #: BR-INT-044 — whether the connection carries a source allowlist.
    network_allowlist: bool = False
    #: BR-INT-032 — their words for our things, one entry per kind. Read by
    #: `mappings.view()` for S143; a manifest with none has no Mappings link.
    vocabularies: tuple[Vocabulary, ...] = ()
    #: BR-INT-042 (wave H) — how many days before `expires_at` the warning
    #: starts. **A fact about THIS provider, so it is DATA and never a branch
    #: in the sweep** (BR-INT-037): Microsoft asks for consent again every
    #: ninety days and eleven days of notice is generous; a partner that
    #: re-keys once a year would want thirty. The default is the fourteen the
    #: execution plan names, so a manifest that says nothing is still warned
    #: about — an absent window must never mean *no warning*.
    expiry_warning_days: int = 14

    @property
    def kicker(self) -> tuple[str, str]:
        """(direction, initiative) of the DEFINING operation — the first one.

        A manifest orders its operations with the one that names the
        relationship first (the kiosk SENDS payments; it also answers
        lookups). The card's three-word kicker — *EMAIL · WE SEND*, *PAYMENTS ·
        THEY SEND* — is read from here, so no screen holds a per-provider
        branch (BR-INT-037).
        """
        first = self.operations[0]
        return first.direction, first.initiative

    @property
    def we_never_dial(self) -> bool:
        """True when EVERY operation is theirs to start — so no adapter exists,
        none is missing, and none ever will (`DEF-INT-4215`, 2026-09-06).

        An adapter is the object that TALKS TO a provider. `they_hold_ours` is
        the one relationship in this product where we never talk: the partner
        presents a key we issued and reads from us (`gl_partner`), or posts to
        us (`payments_kiosk`). Both manifests are `initiative = "them"` on every
        operation, so there is no call for an adapter to make.

        ⚠ IT IS COMPUTED FROM `initiative` AND NOT FROM `auth.mode`, WHICH IS
        THE NARROWER AND THEREFORE SAFER TEST. Today the two coincide across
        all eighteen manifests. They are not the same claim: a connector could
        hold our key and still have an operation WE start (`DEF-INT-4118`'s
        InvoiceCloud is exactly that partner), and such a connector DOES need
        an adapter for that half. `initiative` asks the question that actually
        decides it — *is there anything here for us to dial* — so this property
        stays correct through the fix for 4118 rather than becoming a second
        thing to remember to change.
        """
        return all(one.they_call_us for one in self.operations)


# ── validation — every refusal names the provider, and the operation ────────


def _refuse(key: str, why: str, operation: str | None = None) -> ManifestError:
    where = f"{key} · {operation}" if operation else key
    return ManifestError(f"manifest refused — {where}: {why}")


def _in(value: object, vocabulary: Iterable[str], what: str) -> str | None:
    allowed = tuple(vocabulary)
    if value not in allowed:
        return f"{what} {value!r} is not one of {list(allowed)}"
    return None


def validate(manifest: Manifest) -> None:
    """Raise `ManifestError` for the first thing wrong, naming where it is."""
    key = manifest.key
    if not key or not key.replace("_", "").isalnum() or key != key.lower():
        raise _refuse(repr(key), "the key must be lower-case letters, digits and underscores")
    if not manifest.category:
        raise _refuse(key, "a category is required — the filter chips are generated from it")
    if not manifest.display_name or not manifest.summary:
        raise _refuse(key, "a display name and a one-sentence summary are required")
    if (why := _in(manifest.disposition.kind, DISPOSITIONS, "disposition")) is not None:
        raise _refuse(key, why)
    if manifest.disposition.coming_soon and not manifest.disposition.wave:
        raise _refuse(key, "a coming-soon disposition needs its wave label (BR-INT-001)")
    if (why := _in(manifest.auth.mode, AUTH_MODES, "auth.mode")) is not None:
        raise _refuse(key, why)
    if (why := _in(manifest.auth.placement, AUTH_PLACEMENTS, "auth.placement")) is not None:
        raise _refuse(key, why)
    # Wave N (`US-INT-044`) — a credential header name belongs to the `header`
    # placement and to nothing else. Refused in the ONE direction the registry
    # can be sure about: a name on `bearer`, `query`, `native` or `none` is
    # dead data a later lane would trust (the same argument the `auth.oauth`
    # and `auth.token` rules below make). The other direction — a `header`
    # placement with no name — is NOT refused here; see `Auth.header` for why,
    # and for which file refuses it instead.
    if manifest.auth.header is not None and manifest.auth.placement != "header":
        raise _refuse(
            key,
            f"names a credential header {manifest.auth.header!r} and its placement is "
            f"{manifest.auth.placement!r} — only a `header` placement has a header to name",
        )
    # BR-INT-043 (wave H) — a redirect is a button and a return trip, so it has
    # to say where it goes. Both directions are refused: a redirect with no
    # endpoints is a button wired to nothing (hard-won law 2), and endpoints on
    # a placement that never redirects are dead data a later lane would trust.
    has_redirect_field = any(one.kind == "redirect" for one in manifest.fields)
    wants_redirect = manifest.auth.placement == "redirect" or has_redirect_field
    # ⚠ A COMING-SOON PROVIDER IS EXEMPT, AND THE EXEMPTION IS THE HONEST HALF
    # OF THIS RULE. `sso` declares a redirect for a v2 identity provider nobody
    # has chosen yet; demanding endpoints would mean INVENTING a URL, and a
    # plausible-looking endpoint for an unpicked provider is a worse artefact
    # than an absent one (hard-won law 1 — a comment claiming a guarantee).
    # BR-INT-001 already refuses a coming-soon connect at the service boundary,
    # so its button cannot fire.
    #
    # ⚠ AND THIS IS A HOLD THAT FIRES WHEN IT EXPIRES, which is what law 2 asks
    # of every hold: the day somebody flips `sso` to `live`, THIS check refuses
    # the registry at load and names the file. Nothing has to remember.
    if wants_redirect and manifest.auth.oauth is None and not manifest.disposition.coming_soon:
        raise _refuse(
            key,
            "declares a redirect (auth.placement or a field of kind 'redirect') and no "
            "auth.oauth endpoints — a sign-in button has to say where it sends a person "
            "(BR-INT-043)",
        )
    if manifest.auth.oauth is not None:
        if not wants_redirect:
            raise _refuse(
                key,
                "carries auth.oauth endpoints but nothing redirects — dead data a later "
                "lane would build on (BR-INT-043)",
            )
        for label, url in (
            ("authorize_url", manifest.auth.oauth.authorize_url),
            ("token_url", manifest.auth.oauth.token_url),
        ):
            if not str(url).startswith("https://"):
                raise _refuse(
                    key,
                    f"auth.oauth.{label} is {url!r} — a sign-in round trip carries a "
                    "credential and is https, always",
                )
        if manifest.auth.oauth.default_lifetime_days < 1:
            raise _refuse(
                key,
                "auth.oauth.default_lifetime_days is "
                f"{manifest.auth.oauth.default_lifetime_days} — a consent that lasts no "
                "days would be warned about and lapsed on the day it was granted "
                "(BR-INT-042)",
            )
    # ── wave K (BR-INT-047) — the machine-to-machine half of `token_exchange` ──
    # A `redirect` placement exchanges a PERSON's consent and reads `auth.oauth`
    # (wave H). A `bearer` placement exchanges a STORED PAIR and reads this.
    # Both directions are refused, for the reason `auth.oauth` already gives:
    # a mode with nowhere to mint from cannot mint, and a token endpoint on a
    # mode that never mints is dead data the next lane would trust.
    wants_token = manifest.auth.mode == "token_exchange" and manifest.auth.placement != "redirect"
    if wants_token and manifest.auth.token is None and not manifest.disposition.coming_soon:
        raise _refuse(
            key,
            "declares auth.mode 'token_exchange' with a non-redirect placement and no "
            "auth.token — there is nowhere to mint the short-lived token from "
            "(BR-INT-047)",
        )
    if manifest.auth.token is not None:
        if not wants_token:
            raise _refuse(
                key,
                "carries auth.token and never exchanges one — dead data a later lane "
                "would build on (BR-INT-047)",
            )
        token = manifest.auth.token
        if not str(token.token_url).startswith("https://"):
            raise _refuse(
                key,
                f"auth.token.token_url is {token.token_url!r} — a token exchange carries "
                "the long-lived pair and is https, always",
            )
        if token.ttl_seconds < 1:
            raise _refuse(
                key,
                f"auth.token.ttl_seconds is {token.ttl_seconds} — a token that lives no "
                "seconds is expired when it is minted",
            )
        # ⚠ A SKEW AT OR ABOVE THE LIFETIME MEANS EVERY TOKEN IS STALE ON
        # ARRIVAL, so the cache re-mints on every single call — a walk of 105
        # windows would mint 105 times and look, from the outside, exactly like
        # a working cache. Refused here because nothing downstream can see it.
        if not 1 <= token.refresh_before_s < token.ttl_seconds:
            raise _refuse(
                key,
                f"auth.token.refresh_before_s is {token.refresh_before_s} against a "
                f"lifetime of {token.ttl_seconds}s — the skew has to leave some of the "
                "token's life usable (BR-INT-047)",
            )
    _validate_inbound_verification(manifest)
    for one in manifest.fields:
        if (why := _in(one.kind, FIELD_KINDS, f"field {one.name!r} kind")) is not None:
            raise _refuse(key, f"{why} (BR-INT-043)")
        # CR-173-BRC10 — a group is a credential SLOT name and a catalogue key
        # segment, so it is a bare lower-case word, and it is never `primary`
        # (that slot is the connection's own secret).
        if one.group and (
            not one.group.replace("_", "").isalnum()
            or one.group != one.group.lower()
            or one.group == "primary"
        ):
            raise _refuse(
                key,
                f"field {one.name!r} declares group {one.group!r} — a group is a lower-case "
                "word and never 'primary', the connection's own credential slot (CR-173-BRC10)",
            )
        if one.group and one.kind == "issued_secret":
            raise _refuse(
                key,
                f"field {one.name!r} is an issued key in group {one.group!r} — a key we issue "
                "is the connection's own and is never part of a group (CR-173-BRC10)",
            )
        if one.kind == "select" and not one.options:
            raise _refuse(key, f"field {one.name!r} is a select with no options")
        # `CR-110-BRC04` — a seeded value is the phase-1 placeholder address
        # and NOTHING else. A default on a secret would be a credential in the
        # repository; a default on a redirect or a mapping editor would be a
        # value neither control can hold. Refused by name in both cases.
        if one.default:
            if one.kind in SECRET_FIELD_KINDS:
                raise _refuse(
                    key,
                    f"field {one.name!r} is a {one.kind} and carries a default — a seeded "
                    "secret is a credential in the repository, and the unsafe option has "
                    "to be the one you type",
                )
            if one.kind in ("redirect", "mapping_editor"):
                raise _refuse(
                    key,
                    f"field {one.name!r} is a {one.kind} and carries a default — neither "
                    "control holds a value a clerk could have typed",
                )
        if one.kind == "select" and one.default and one.default not in one.options:
            raise _refuse(
                key,
                f"field {one.name!r} defaults to {one.default!r}, which is not one of "
                f"{list(one.options)}",
            )
        # ⚠ **A SEEDED DEFAULT MUST BE A VALUE THE FORM WOULD ACCEPT, AND
        # NINETEEN WERE NOT (`DEF-INT-5590`).** `CR-110-BRC04` wave C seeded a
        # placeholder address into every connector that dials out, each one
        # carrying `https://`, into fields declared `host` — whose own check
        # refuses a scheme. So nineteen connectors shipped a box pre-filled
        # with the single value it would refuse to save: hard-won law 7's
        # *incapable of passing*, and nothing could see it, because the only
        # code that judges a default lived in the validator and the only code
        # that wrote one lived in the manifests.
        #
        # ⚠ **THE CHECK ABOVE IS WHY THIS ONE IS HERE.** `select` already had
        # exactly this guard — *does the default appear in the options* — for
        # exactly one kind. This is that guard for all of them, asked the only
        # way that cannot drift: by running the field's OWN validator over it.
        # The import is deferred because `adapters.base` imports this module.
        # ⚠ **FILTERED TO THE FIELD UNDER JUDGMENT, AND THE FIRST DRAFT WAS
        # NOT.** `validate_fields` judges a WHOLE form, so an unfiltered call
        # here reports every OTHER required field as missing and refuses every
        # manifest that has more than one — which is a guard that fires on
        # everything, i.e. one that says nothing. It was caught by running it,
        # which is the only way this kind of fault is ever caught.
        if one.default and one.kind not in SECRET_FIELD_KINDS:
            from apps.integrations.adapters.base import validate_fields

            spoiled = [
                problem
                for problem in validate_fields(
                    manifest, {one.name: one.default}, require_secrets=False
                )
                if problem.field == one.name
            ]
            if spoiled and (key, one.name) not in SEEDED_DEFAULT_EXEMPTIONS:
                raise _refuse(
                    key,
                    f"field {one.name!r} is a {one.kind} and defaults to "
                    f"{one.default!r}, which this connector's own form would "
                    "refuse — a box pre-filled with the one value it cannot "
                    "save is worse than an empty box (DEF-INT-5590)",
                )
        _validate_per_class(key, one)
    names = [one.name for one in manifest.fields]
    if len(set(names)) != len(names):
        raise _refuse(
            key, f"duplicate field names {sorted(set(n for n in names if names.count(n) > 1))}"
        )
    # BR-INT-042 (wave H) — a window of zero or fewer days is not "no warning",
    # it is a warning that arrives on or after the day sending stops. Refused
    # here, by name, rather than silently normalised: the whole rule is *days
    # ahead*, so a manifest that asks for none is a manifest with a typo.
    if manifest.expiry_warning_days < 1:
        raise _refuse(
            key,
            f"expiry_warning_days is {manifest.expiry_warning_days} — the warning has to "
            "arrive BEFORE the credential lapses, so the window is at least one day "
            "(BR-INT-042)",
        )
    registered_codecs = codec_names()
    for codec in manifest.codecs:
        if codec not in registered_codecs:
            raise _refuse(
                key,
                f"codec {codec!r} is not registered; what exists: {list(registered_codecs)} "
                "(BR-INT-033)",
            )
    # BR-INT-033 — the format picker appears ONLY where more than one codec is
    # registered, and it is a `select` field on the manifest, drawn by S141's
    # field slot; so the rule is held here, as data, and no screen decides it.
    codec_selects = [
        one
        for one in manifest.fields
        if one.kind == "select" and one.options and set(one.options) <= set(codec_names())
    ]
    if len(manifest.codecs) > 1:
        if not any(tuple(one.options) == tuple(manifest.codecs) for one in codec_selects):
            raise _refuse(
                key,
                f"registers {len(manifest.codecs)} codecs and carries no select field offering "
                "exactly those — the format picker is that field (BR-INT-033)",
            )
    elif codec_selects:
        raise _refuse(
            key,
            f"registers {len(manifest.codecs)} codec(s) and field "
            f"{codec_selects[0].name!r} offers only codec names — a picker appears only where "
            "more than one is registered (BR-INT-033)",
        )
    kinds_seen: set[str] = set()
    for vocabulary in manifest.vocabularies:
        if (why := _in(vocabulary.entity_type, MAPPING_ENTITY_TYPES, "vocabulary")) is not None:
            raise _refuse(key, f"{why} (BR-INT-032)")
        if vocabulary.entity_type in kinds_seen:
            raise _refuse(key, f"vocabulary {vocabulary.entity_type!r} declared twice")
        kinds_seen.add(vocabulary.entity_type)
        if not vocabulary.label:
            raise _refuse(key, f"vocabulary {vocabulary.entity_type!r} needs a label — it is a tab")
        if not vocabulary.values and not vocabulary.open:
            raise _refuse(
                key,
                f"vocabulary {vocabulary.entity_type!r} ships no words and is not open — "
                "a closed empty list maps nothing",
            )
        if any(not str(word).strip() for word in vocabulary.values):
            raise _refuse(key, f"vocabulary {vocabulary.entity_type!r} carries a blank word")
        if len(set(vocabulary.values)) != len(vocabulary.values):
            raise _refuse(key, f"vocabulary {vocabulary.entity_type!r} lists a word twice")
        # `CR-174-BRC10` — a fallback or a suggestion for a word the list does
        # not ship is a mapping row nobody can see on S143.
        if vocabulary.fallback is not None and vocabulary.fallback not in vocabulary.values:
            raise _refuse(
                key,
                f"vocabulary {vocabulary.entity_type!r} falls back to "
                f"{vocabulary.fallback!r}, which it does not list",
            )
        stray = sorted(set(vocabulary.suggested) - set(vocabulary.values))
        if stray:
            raise _refuse(
                key, f"vocabulary {vocabulary.entity_type!r} suggests for unlisted words {stray}"
            )
    # `CR-174-BRC10` — an identity header is compared against a NON-SECRET
    # field the connection holds; naming one that does not exist would make the
    # comparison fail closed for ever, and naming a secret would compare a key.
    declared_fields = {one.name: one for one in manifest.fields}
    for header_name, field_name in manifest.auth.identity_headers.items():
        target = declared_fields.get(field_name)
        if target is None or target.is_secret:
            raise _refuse(
                key,
                f"identity header {header_name!r} names {field_name!r}, which is not a "
                "non-secret field of this manifest",
            )
    if manifest.conformance is not None:
        claim = manifest.conformance.claim
        if (why := _in(claim, CONFORMANCE_CLAIMS, "conformance.claim")) is not None:
            raise _refuse(key, why)
        if claim == "certified" and not manifest.conformance.certificate_id:
            raise _refuse(
                key, "a `certified` conformance claim needs a certificate id (BR-INT-053)"
            )
    if not manifest.operations:
        raise _refuse(
            key, "a provider is a set of operations and this one declares none (BR-INT-028)"
        )
    # ── BR-INT-048 / BR-INT-003 (CR-069 wave M) — no tenant secret reaches the
    # browser, held at LOAD rather than at call time. `executor = "browser"`
    # means the viewer's browser places the call, so anything the request needs
    # is in the page and therefore in the reader's developer tools. A manifest
    # that both requires a secret and asks the browser to call is a leak that
    # would be discovered by a customer.
    #
    # ⚠ `browser_credentialed` is EXEMPT and that is the whole reason the third
    # word exists: the processor hosts the page (PO 2026-09-03, *"they are on
    # Spruce page"*), so the credential is THEIRS and ours never travels.
    # ⚠ **THE NAME OF THE FIELD, NEVER ITS VALUE** — `one.name` is `"api_key"`,
    # not the key. It used to be called `required_secret`, which was wrong twice
    # over: a reader could take it for a credential, and G94 DID, refusing the
    # f-string below on the fourth exit ("interpolates a credential into a
    # string"). G94 reasons about the NAME of the interpolated expression,
    # because there is no other way to reason about it statically — so a local
    # whose name lies to the gate is a local that lies to the next lane.
    required_field_name = next(
        (one.name for one in manifest.fields if one.kind in SECRET_FIELD_KINDS and one.required),
        None,
    )
    if required_field_name is not None:
        offender = next((one for one in manifest.operations if one.executor == "browser"), None)
        if offender is not None:
            raise _refuse(
                key,
                f"operation {offender.name!r} is executed by the BROWSER and this provider "
                f"requires the secret field {required_field_name!r} — a browser-executed "
                "operation carries no tenant secret (BR-INT-048, BR-INT-003)",
            )
    seen: set[str] = set()
    for op in manifest.operations:
        _validate_operation(key, op)
        if op.name in seen:
            raise _refuse(key, "declared twice", op.name)
        seen.add(op.name)
    _validate_hosts(manifest)


def _validate_per_class(key: str, one: Field) -> None:
    """A field that varies by the KIND OF MESSAGE — refused at load if malformed.

    Every refusal here names the field and, where one is involved, the class.

    ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (hard-won law 7, habit 2):
    the class list arriving EMPTY. `notification_classes()` reads another
    module through a seam, and a seam that cannot resolve its target answers
    `()` rather than raising — so an unguarded `key in classes` loop would
    accept nothing, and an unguarded `if classes and key not in classes` would
    accept EVERYTHING. So an empty list is its own refusal, by name, and the
    manifest does not load.
    """
    if not one.per_class:
        return
    if one.kind in SECRET_FIELD_KINDS:
        raise _refuse(
            key,
            f"field {one.name!r} is a {one.kind} and declares per-class values — a "
            "credential in the repository is a credential in the repository however "
            "many of them there are",
        )
    if one.kind in ("redirect", "mapping_editor"):
        raise _refuse(
            key,
            f"field {one.name!r} is a {one.kind} and declares per-class values — "
            "neither control holds a value a clerk could have typed",
        )
    if not one.default:
        raise _refuse(
            key,
            f"field {one.name!r} declares per-class values and no default — the "
            f"classes it does NOT name ({sorted(set(notification_classes()) - set(one.per_class))}) "
            "would have no value at all, and the day a new class is minted is the day "
            "this connector sends with nothing",
        )
    classes = notification_classes()
    if not classes:
        raise _refuse(
            key,
            f"field {one.name!r} declares per-class values and the notification classes "
            "could not be read — a per-class setting whose classes are unknown is "
            "refused rather than accepted (hard-won law 3)",
        )
    for notification_class, value in one.per_class.items():
        if notification_class not in classes:
            raise _refuse(
                key,
                f"field {one.name!r} names notification class {notification_class!r}, "
                f"which this product does not have; what exists: {list(classes)}",
            )
        if not str(value).strip():
            raise _refuse(
                key,
                f"field {one.name!r} declares a blank value for {notification_class!r} — "
                "a class named with nothing behind it is worse than a class left to the "
                "default, because it looks decided",
            )
        if one.kind == "select" and value not in one.options:
            raise _refuse(
                key,
                f"field {one.name!r} sends {notification_class!r} to {value!r}, which is "
                f"not one of {list(one.options)}",
            )
    # The same guard `default` earns above, for the same reason and asked the
    # same way: by running the field's OWN validator over each value. A value
    # this connector's own form would refuse is a value no clerk could ever
    # save, whichever class it belongs to (`DEF-INT-5590`).
    #
    # ⚠ **JUDGED THROUGH A ONE-FIELD MANIFEST AND NOT THE REAL ONE.**
    # `validate_fields` judges a WHOLE form, so handing it the real manifest
    # reports every OTHER required field as missing — the first-draft mistake
    # the `default` check above records. Filtering to `problem.field` cures
    # that either way; a manifest holding only this field makes the intent
    # plain and cannot be un-filtered by a later tidy-up. The import is
    # deferred because `adapters.base` imports this module.
    from apps.integrations.adapters.base import validate_fields

    alone = Manifest(
        key=key,
        category="_",
        display_name="_",
        summary="_",
        auth=Auth(mode="none", placement="none"),
        operations=(),
        fields=(one,),
    )
    for notification_class, value in one.per_class.items():
        spoiled = [
            problem
            for problem in validate_fields(alone, {one.name: str(value)}, require_secrets=False)
            if problem.field == one.name
        ]
        if spoiled:
            raise _refuse(
                key,
                f"field {one.name!r} sends {notification_class!r} to {value!r}, which "
                "this connector's own form would refuse",
            )


def _validate_inbound_verification(manifest: Manifest) -> None:
    """The inbound door's declared verification style — every refusal by name.

    ⚠ **BOTH DIRECTIONS, AS EVERYWHERE ELSE IN THIS FILE.** A style that needs
    a field and does not name it is refused; a field named by a style that
    never reads it is refused as dead data a later lane would build on.
    """
    key = manifest.key
    declared = manifest.auth.inbound
    if declared is None:
        return
    if (why := _in(declared.style, INBOUND_VERIFICATIONS, "auth.inbound.style")) is not None:
        raise _refuse(key, why)
    if declared.style == VERIFY_PRESENTED_KEY:
        raise _refuse(
            key,
            "declares auth.inbound.style 'presented_key', which is what an ABSENT "
            "auth.inbound already means — two spellings of one thing is one more thing "
            "for the next lane to keep in step",
        )
    if not any(one.they_call_us for one in manifest.operations):
        raise _refuse(
            key,
            f"declares an inbound verification ({declared.style!r}) and no operation the "
            "partner calls — there is no door for it to guard",
        )
    signature = declared.style == VERIFY_SIGNATURE
    # Every knob, in one table: which style may carry it. A style that is not
    # this row's owner is refused BY NAME, which is how `basic` stays the one
    # thing it is — a transport for a key we minted — rather than drifting into
    # a second signature scheme.
    for value, name, owner in (
        (declared.signature_header, "signature_header", VERIFY_SIGNATURE),
        (declared.timestamp_header, "timestamp_header", VERIFY_SIGNATURE),
        (declared.secret_field, "secret_field", VERIFY_SIGNATURE),
        (declared.algorithm, "algorithm", VERIFY_SIGNATURE),
        (declared.signed_payload, "signed_payload", VERIFY_SIGNATURE),
        (declared.encoding, "encoding", VERIFY_SIGNATURE),
        (declared.max_skew_seconds, "max_skew_seconds", VERIFY_SIGNATURE),
    ):
        if value is not None and declared.style != owner:
            raise _refuse(
                key,
                f"auth.inbound declares {name}={value!r} and its style is "
                f"{declared.style!r} — only {owner!r} reads it",
            )
    if not signature:
        return
    for value, name in (
        (declared.signature_header, "signature_header"),
        (declared.algorithm, "algorithm"),
        (declared.signed_payload, "signed_payload"),
        (declared.encoding, "encoding"),
        (declared.secret_field, "secret_field"),
    ):
        if not value:
            raise _refuse(
                key,
                f"auth.inbound.style is 'signature' and names no {name} — the door will "
                "not guess how a partner signs (hard-won law 3)",
            )
    for value, vocabulary, what in (
        (declared.algorithm, SIGNATURE_ALGORITHMS, "auth.inbound.algorithm"),
        (declared.signed_payload, SIGNED_PAYLOADS, "auth.inbound.signed_payload"),
        (declared.encoding, SIGNATURE_ENCODINGS, "auth.inbound.encoding"),
    ):
        if (why := _in(value, vocabulary, what)) is not None:
            raise _refuse(key, why)
    declared_fields = {one.name: one for one in manifest.fields}
    secret = declared_fields.get(str(declared.secret_field))
    if secret is None:
        raise _refuse(
            key,
            f"auth.inbound names secret_field {declared.secret_field!r} and this manifest "
            f"declares no such field; what it declares: {sorted(declared_fields)}",
        )
    if secret.kind not in SECRET_FIELD_KINDS:
        raise _refuse(
            key,
            # ⚠ THE ENCRYPTED COLUMN IS NAMED IN THE COMMENT AND NOT IN THE
            # STRING, AND THAT IS NOT PEDANTRY. `G94` reasons about the
            # credential path STATICALLY, by the names that appear in code —
            # there is no other way to reason about it — so a refusal sentence
            # quoting the column reads to the gate exactly like a file that
            # READS it, and the gate was right to say so. Naming it here costs
            # a reader nothing and keeps the one that watches the credential
            # path able to mean what it says.
            f"auth.inbound names secret_field {declared.secret_field!r}, which is declared "
            f"as kind {secret.kind!r} — a verification key lands in the encrypted credential "
            f"store, so it is one of {sorted(SECRET_FIELD_KINDS)} and never a value in the "
            "connection's own settings (BR-INT-003)",
        )
    if declared.signs_a_timestamp:
        if not declared.timestamp_header:
            raise _refuse(
                key,
                "auth.inbound signs 'timestamp_body' and names no timestamp_header — "
                "there would be nothing to prefix and nothing to age",
            )
        if declared.max_skew_seconds is None:
            raise _refuse(
                key,
                "auth.inbound signs a timestamp and declares no max_skew_seconds — a "
                "signature nobody ages is valid for ever, so one captured call replays "
                "for ever and verifies perfectly every time",
            )
        if int(declared.max_skew_seconds) < 1:
            raise _refuse(
                key,
                f"auth.inbound.max_skew_seconds is {declared.max_skew_seconds} — a window "
                "of no seconds refuses a healthy partner on its first call",
            )
    else:
        for value, name in (
            (declared.timestamp_header, "timestamp_header"),
            (declared.max_skew_seconds, "max_skew_seconds"),
        ):
            if value is not None:
                raise _refuse(
                    key,
                    f"auth.inbound signs {declared.signed_payload!r} and declares "
                    f"{name}={value!r} — nothing reads it, and a replay window nothing "
                    "enforces is hard-won law 1 written in data",
                )


def _validate_hosts(manifest: Manifest) -> None:
    """`DEF-INT-5488` — an operation's `host_field` has to name a real field.

    THE DEFECT, in its own numbers: fifteen of eighteen manifests named
    `base_url` and declared no field of that name, so `Operation.host_field`'s
    own promise — *"WHICH non-secret config field holds THIS operation's
    host"* — was false for forty-five operations out of forty-five on those
    fifteen, and the endpoint the blueprint draws on every one of 78 API rows
    could be filled for three connectors. Nothing could see it: the default
    was read only by the page-security policy generator, and only for
    browser-executed operations, which the three honest manifests happened to
    be the only ones to have. **A field that claims to name a host and names
    nothing is hard-won law 1 written in data instead of in a comment.**

    ⚠ **THE CHECK APPLIES TO OPERATIONS WE INITIATE, AND ONLY TO THOSE. THE
    EXEMPTION IS NARROW AND IT IS STATED HERE RATHER THAN LEFT TO BE
    INFERRED**, because a check that silently excludes part of its subject is
    indistinguishable from an empty one (hard-won law 7, `G32`'s shape).
    When `initiative == "them"` the partner dials US: the address is the one
    WE publish — `/partner/v1/…` and `/auth/saml/acs` — it is the same for
    every tenant, and no clerk configures it. Asking such a manifest to
    declare a host field would put a box on a set-up form inviting a utility
    to type our own address. `Registry.host_coverage()` prints both halves so
    the skipped set always carries a number beside the checked one.

    The kind matters too. A host that is a `secret` would be a credential
    rendered as an address, and a host that is `text` loses the one validation
    the field slot performs on an address.

    ⚠ **BOTH ADDRESS KINDS SATISFY IT (`DEF-INT-5589`).** `host` is a bare
    name and `url` is a whole service address; the thing this check cares
    about is that the named field is VALIDATED as an address, which both are
    and `text` is not. It read `!= "host"` until 2026-09-17, so the day the
    nineteen *Service address* fields moved to `url` it refused eighteen of
    the twenty-eight connectors at `AppConfig.ready()` — loudly, which is the
    good case, and is how it was found.
    """
    declared = {one.name: one for one in manifest.fields}
    for op in manifest.operations:
        if op.they_call_us:
            continue
        field_declared = declared.get(op.host_field)
        if field_declared is None:
            raise _refuse(
                manifest.key,
                f"names host_field {op.host_field!r} and this manifest declares no such "
                f"field; what it declares: {sorted(declared)} — an operation we dial has "
                "to say which configured value holds the address (DEF-INT-5488)",
                op.name,
            )
        if field_declared.kind not in ADDRESS_FIELD_KINDS:
            raise _refuse(
                manifest.key,
                f"names host_field {op.host_field!r}, which is declared as kind "
                f"{field_declared.kind!r} — an address is a `host` or a `url` "
                f"({sorted(ADDRESS_FIELD_KINDS)}) (DEF-INT-5488)",
                op.name,
            )


def _validate_operation(key: str, op: Operation) -> None:
    if not op.name or not op.label:
        raise _refuse(key, "an operation needs a name and a label", op.name or "?")
    for value, vocabulary, what in (
        (op.direction, DIRECTIONS, "direction"),
        (op.initiative, INITIATIVES, "initiative"),
        (op.transport, TRANSPORTS, "transport"),
        (op.trigger, TRIGGERS, "trigger"),
        (op.executor, EXECUTORS, "executor"),
    ):
        if (why := _in(value, vocabulary, what)) is not None:
            raise _refuse(key, why, op.name)
    # CR-069 §13 gate 3 — the two declared values no operation may omit.
    if op.idempotency is None or op.idempotency.mode is None:
        raise _refuse(key, "no idempotency mode declared (CR-069 §13 gate 3)", op.name)
    if (why := _in(op.idempotency.mode, IDEMPOTENCY_MODES, "idempotency.mode")) is not None:
        raise _refuse(key, why, op.name)
    if (why := _in(op.idempotency.source, IDEMPOTENCY_SOURCES, "idempotency.source")) is not None:
        raise _refuse(key, why, op.name)
    # ⚠ **THIS CHECK WAS HERE TWICE AND THE EARLIER COPY SHADOWED THE LATER
    # ONE (`DEF-INT-5523`, 2026-09-16).** Wave C added the `< 1` refusal below,
    # with the sentence its own test asserts — *"refuses a healthy partner on
    # its first request"* — and wave D added a second copy HERE, four
    # statements earlier, raising different words. Its test
    # (`test_cr110__a_ceiling_of_nothing_is_refused_by_name`) had been RED and
    # unread ever since, on a message mismatch and never on the rule: a
    # zero-ceiling manifest was refused correctly the whole time. The earlier
    # copy is removed; the rule below is unchanged and is now the only one.
    # ── CR-110-BRC04 phase 2 — a declared address has to look like one ──
    # Two ways this goes wrong and both are silent on a screen: a value with no
    # leading slash renders as a relative fragment beside a utility slug, and a
    # value declared on an OUTBOUND operation prints one of our routes beside a
    # call we place at a vendor — a hard-won-law-1 comment claiming a guarantee,
    # drawn in a table a clerk reads.
    if op.served_path is not None:
        if not str(op.served_path).startswith("/"):
            raise _refuse(
                key,
                f"served_path is {op.served_path!r} — our own address is an absolute "
                "path, because a screen composes it after the utility's slug "
                "(CR-110-BRC04 phase 2)",
                op.name,
            )
        # ⚠ **THIS READ `op.direction == "out" and op.initiative == "them"`
        # UNTIL 2026-09-24 AND IT WAS THE WRONG PREDICATE (`DEF-INT-6485`).**
        # The question a `served_path` answers is *is this a door WE PUBLISH*,
        # and the property that decides it is `initiative` alone: **they call
        # us**. `direction` says which way the DATA then moves through that
        # door, which is a different fact — Invoice Cloud's `make-payment` is
        # `in · them`, an address of ours that a partner POSTs to, and the old
        # predicate refused it by name.
        #
        # ⚠ **`Manifest.we_never_dial` HAD ALREADY WRITTEN THIS DOWN** and its
        # own docstring says why it uses `initiative` rather than the fact that
        # happens to travel with it: *"`initiative` asks the question that
        # actually decides it — is there anything here for us to dial"*. Two
        # predicates for one question is how they drift.
        #
        # **Nothing existing moves.** Every `out · them` operation in the repo
        # still passes, and the case the original comment names — *"a value
        # declared on an OUTBOUND operation prints one of our routes beside a
        # call we place at a vendor"* — is `initiative == "us"`, which this
        # still catches. What it stops refusing is the kiosk's own quadrant,
        # where three live inbound operations carry no address and therefore
        # draw no row: `DEF-INT-5622` sitting unreported one quadrant over.
        if not op.they_call_us:
            raise _refuse(
                key,
                "declares a served_path and is not an operation THEY call — only a "
                "door WE publish has an address of ours to show (CR-110-BRC04 phase 2, "
                "predicate corrected by DEF-INT-6485)",
                op.name,
            )
    if op.completion is None:
        raise _refuse(key, "no completion mode declared (CR-069 §13 gate 3)", op.name)
    # ── CR-110-BRC04 (PO 2026-09-16) — every operation names its ceiling ──
    # Required rather than defaulted, and the reason is `DEF-INT-5488` one
    # file up: a silent default on a per-connector FACT is how forty-five
    # operations came to carry a value nobody chose. The limit is a guard the
    # product will not let anybody edit, so the only place it can be got right
    # is here, once, by the person writing the manifest.
    if op.rate_limit_per_minute is None:
        raise _refuse(
            key,
            "declares no rate_limit_per_minute — the limit is a guard nobody may edit "
            "from a screen, so every operation names the ceiling it ships with "
            "(CR-110-BRC04)",
            op.name,
        )
    if int(op.rate_limit_per_minute) < 1:
        raise _refuse(
            key,
            f"rate_limit_per_minute is {op.rate_limit_per_minute} — a ceiling of no calls "
            "a minute refuses a healthy partner on its first request (CR-110-BRC04)",
            op.name,
        )
    if (why := _in(op.completion, COMPLETIONS, "completion")) is not None:
        raise _refuse(key, why, op.name)
    # ── wave K · BR-INT-046 (`C10`, `C20`) — completion and its two companions ──
    # US-INT-031 TC-5: *an operation declares `completion = submit_poll_collect`
    # and no poll schedule → refused at load*. Both directions again: a poll
    # schedule on an `immediate` operation is a number nothing reads.
    submits = op.completion == "submit_poll_collect"
    if submits:
        if op.poll is None:
            raise _refuse(
                key,
                "declares completion 'submit_poll_collect' and no poll schedule — a run "
                "that submits and never asks again waits forever (BR-INT-046)",
                op.name,
            )
        if op.result_delivery is None:
            raise _refuse(
                key,
                "declares completion 'submit_poll_collect' and no result_delivery — we "
                "would not know whether the answer is a link or a handle (BR-INT-046)",
                op.name,
            )
        if (why := _in(op.result_delivery, RESULT_DELIVERIES, "result_delivery")) is not None:
            raise _refuse(key, why, op.name)
        if op.poll.every_seconds < 1 or op.poll.max_attempts < 1:
            raise _refuse(
                key,
                f"poll every {op.poll.every_seconds}s up to {op.poll.max_attempts} times — "
                "both have to be at least one, or nothing is ever asked",
                op.name,
            )
    else:
        if op.poll is not None:
            raise _refuse(
                key,
                f"completion is {op.completion!r} and a poll schedule is declared — "
                "nothing polls an immediate operation (BR-INT-046)",
                op.name,
            )
        if op.result_delivery is not None:
            raise _refuse(
                key,
                f"completion is {op.completion!r} and result_delivery is declared — an "
                "immediate operation's result is its answer (BR-INT-046)",
                op.name,
            )
    # ── wave K · BR-INT-050 (`C19`) — a fetch that changes THEIR world ──
    # US-INT-035 TC-4: *a manifest marks an operation `mutates_partner_state =
    # true` and declares no idempotency source → refused at load*. The source
    # has to be one WE mint BEFORE the request leaves, which is `request_key`
    # and nothing else: a key computed from what came BACK cannot be written
    # before the call, so it cannot refuse the retry of a call that already
    # closed their routes (BR-INT-020, BR-INT-052).
    if op.mutates_partner_state and op.idempotency.source != "request_key":
        raise _refuse(
            key,
            f"changes the partner's state and keys on {op.idempotency.source!r} — a key "
            "we mint before the request leaves ('request_key') is the only one that can "
            "refuse the retry (BR-INT-050)",
            op.name,
        )
    # ── wave K · BR-INT-050 (`C18`) — safety parameters ──
    if op.safety_parameters:
        if op.they_call_us:
            raise _refuse(
                key,
                "declares safety parameters and we do not make the request — a parameter "
                "we never send cannot be left unset (BR-INT-050)",
                op.name,
            )
        if any(not str(one).strip() for one in op.safety_parameters):
            raise _refuse(key, "declares a blank safety parameter", op.name)
        if len(set(op.safety_parameters)) != len(op.safety_parameters):
            raise _refuse(key, "lists a safety parameter twice", op.name)
    # ── wave K · C12 — the fetch plan ──
    if op.fetch_plan is not None:
        if op.they_call_us:
            raise _refuse(
                key,
                "declares a fetch plan and we do not start it — a walk is something we "
                "do, never something they do to us",
                op.name,
            )
        if op.fetch_plan.window_days < 1 or op.fetch_plan.page_size < 1:
            raise _refuse(
                key,
                f"fetch plan window {op.fetch_plan.window_days}d, page size "
                f"{op.fetch_plan.page_size} — a walk of zero-day windows or zero-row "
                "pages never reaches the end (C12)",
                op.name,
            )
    # ── BR-INT-048 · C15 / C16 (CR-069 wave M) ───────────────────────────────
    # `result_disposition` is optional so a manifest written before wave M
    # still loads; what it may NEVER be is a word outside the vocabulary.
    if op.result_disposition is not None and (
        why := _in(op.result_disposition, RESULT_DISPOSITIONS, "result_disposition")
    ) is not None:
        raise _refuse(key, f"{why} (BR-INT-048)", op.name)
    # ⚠ **`initiative == "us"` IS LOAD-BEARING AND WAS MISSING FOR ONE RUN.**
    # The first draft of this check asked only *inline and not the browser* and
    # refused `sso · sign_in` at import — correctly, by its own words, and
    # wrongly. `sign_in` is `inline` because THEY call US and the reply happens
    # in the request; there is no call of ours to put a deadline on, so a
    # budget there would be a number measuring nothing. `C15`'s budget is about
    # a call WE place while a person waits.
    server_inline = (
        op.trigger == "inline"
        and op.initiative == "us"
        and op.executor not in BROWSER_EXECUTORS
    )
    if server_inline:
        if op.latency_budget_ms is None:
            raise _refuse(
                key,
                "runs inline on our server and declares no latency_budget_ms — an inline "
                "operation is a latency budget, not a job, and a budget nobody declared "
                "is a screen that spins (BR-INT-048, C15)",
                op.name,
            )
        if int(op.latency_budget_ms) < 1:
            raise _refuse(
                key,
                f"latency_budget_ms is {op.latency_budget_ms} — a budget of no time refuses "
                "a healthy provider on its first call (BR-INT-048, C15)",
                op.name,
            )
        if op.result_disposition is None:
            raise _refuse(
                key,
                "runs inline and declares no result_disposition — `offer` and `load` are the "
                "difference between showing a list and writing a row (BR-INT-048, C16)",
                op.name,
            )
        if op.completion == "submit_poll_collect":
            raise _refuse(
                key,
                "runs inline and completes by submit-poll-collect — a person cannot wait "
                "for a poll, so one of the two is wrong (BR-INT-048, C15)",
                op.name,
            )
    elif op.latency_budget_ms is not None:
        # ⚠ A budget on a job, or on a call the BROWSER places, is a number we
        # cannot enforce. Refused by name rather than ignored: an unenforced
        # guarantee written down is hard-won law 1.
        raise _refuse(
            key,
            f"declares latency_budget_ms={op.latency_budget_ms} and is not a server-executed "
            "inline operation — we are not the one waiting, so the budget could not be "
            "enforced (BR-INT-048, C15)",
            op.name,
        )
    if op.codec is not None and op.codec not in codec_names():
        raise _refuse(
            key,
            f"codec {op.codec!r} is not registered; what exists: {list(codec_names())} "
            "(BR-INT-033)",
            op.name,
        )
    # BR-INT-030 — the reply position exists only when THEY call US, and it
    # may never sit before `authenticate`.
    if op.they_call_us:
        if op.respond_after is None:
            raise _refuse(key, "the partner calls us and no reply position is declared", op.name)
        if op.respond_after not in GUARD_PIPELINE:
            raise _refuse(
                key,
                f"respond_after {op.respond_after!r} is not one of {list(GUARD_PIPELINE)}",
                op.name,
            )
        if GUARD_PIPELINE.index(op.respond_after) < GUARD_PIPELINE.index("authenticate"):
            raise _refuse(
                key,
                f"respond_after {op.respond_after!r} sits before `authenticate` (BR-INT-030)",
                op.name,
            )
        if "ok" not in op.envelope_status:
            raise _refuse(
                key, "an inbound envelope must declare its `ok` status (BR-INT-045)", op.name
            )
    elif op.respond_after is not None:
        raise _refuse(key, "we start this operation, so it has no reply position", op.name)
    _validate_apply(key, op)
    for status in op.envelope_status.values():
        if not isinstance(status, int) or not 100 <= status <= 599:
            raise _refuse(key, f"envelope status {status!r} is not an HTTP status", op.name)
    if op.test_needs_recipient and op.test_action is None:
        raise _refuse(key, "asks for a test recipient and declares no test action", op.name)


def _validate_apply(key: str, op: Operation) -> None:
    """`CR-174-BRC10` — an operation that APPLIES says exactly what, and has
    every field it needs to, or the registry refuses to load (hard-won law 3).
    """
    if (why := _in(op.http_method, HTTP_METHODS, "http_method")) is not None:
        raise _refuse(key, why, op.name)
    if op.http_method == "GET" and (op.idempotency is None or op.idempotency.source != "none"):
        raise _refuse(key, "a GET is a read and dedupes nothing; declare source 'none'", op.name)
    if op.applies is None:
        if op.respond_after == "apply":
            raise _refuse(key, "replies after `apply` and declares no apply kind", op.name)
        if op.wire:
            raise _refuse(key, "names wire fields and applies nothing — dead data", op.name)
        return
    if (why := _in(op.applies, APPLY_KINDS, "applies")) is not None:
        raise _refuse(key, why, op.name)
    if not op.they_call_us or op.respond_after != "apply":
        raise _refuse(
            key, "an operation that applies is THEIR call and replies after `apply`", op.name
        )
    unknown = sorted(set(op.wire) - set(WIRE_CONCEPTS))
    if unknown:
        raise _refuse(key, f"wire names concepts nobody defined: {unknown}", op.name)
    missing = [one for one in WIRE_REQUIRED[op.applies] if not op.wire.get(one)]
    if missing:
        raise _refuse(key, f"{op.applies} needs wire names for {missing}", op.name)
    absent = [one for one in APPLY_OUTCOMES[op.applies] if one not in op.envelope_status]
    if absent:
        raise _refuse(key, f"{op.applies} declares no status for {absent} (BR-INT-045)", op.name)
    natural = (op.idempotency.natural_key or "") if op.idempotency else ""
    if op.applies == APPLY_ACCOUNT_LOOKUP:
        if op.idempotency is None or op.idempotency.source != "none":
            raise _refuse(key, "an account lookup is a read and dedupes nothing", op.name)
        return
    if (
        op.idempotency is None
        or op.idempotency.mode != "refuse"
        or op.idempotency.source != "provider_event_id"
        or not op.idempotency.key_field
    ):
        raise _refuse(
            key,
            f"{op.applies} moves money and must refuse a repeat on the provider's own id "
            "(mode 'refuse', source 'provider_event_id', a key_field) — hard rule 6",
            op.name,
        )
    if (op.applies == APPLY_REVERSE_PAYMENT) != natural.endswith("+reversal"):
        raise _refuse(
            key,
            "a reversal's key carries the reversal marker and a payment's does not "
            "(BR-INT-020 D)",
            op.name,
        )


# ── the registry ────────────────────────────────────────────────────────────


class Registry:
    """Ordered, refuse-on-register, read-only afterwards. One instance per
    process (`REGISTRY`); tests may build their own."""

    def __init__(self) -> None:
        self._manifests: dict[str, Manifest] = {}
        self._adapters: dict[str, type] = {}

    def register(self, manifest: Manifest) -> Manifest:
        validate(manifest)
        existing = self._manifests.get(manifest.key)
        if existing is not None:
            if existing == manifest:
                return existing  # the same declaration twice is not two providers
            raise _refuse(manifest.key, "already registered with a different declaration")
        self._manifests[manifest.key] = manifest
        return manifest

    def register_adapter(self, key: str, adapter: type) -> None:
        """Wave B: an adapter class for a LIVE provider. A coming-soon provider
        never gets one — that is what makes its card honest (US-INT-017)."""
        manifest = self.require(key)
        if manifest.disposition.coming_soon:
            raise _refuse(key, "a coming-soon provider registers no adapter (BR-INT-001)")
        self._adapters[key] = adapter

    def adapter_for(self, key: str) -> type | None:
        """None as a VALUE — *no adapter registered* — never a raise (TC-6)."""
        self.require(key)
        return self._adapters.get(key)

    def unregister(self, key: str) -> None:
        """Tests only — drop ONE manifest and its adapter.

        ⚠ **IT EXISTS SO A TEST NEED NOT REACH INTO `_manifests`.** A case that
        exercises a door has to put a fixture manifest in the registry the
        PRODUCT reads (`REGISTRY`), because the view holds that one by name;
        `clear()` would take the other twenty-nine with it and every sibling
        case in the session would then run against an empty registry. The
        product registers at `ready()` and never unregisters.
        """
        self._manifests.pop(key, None)
        self._adapters.pop(key, None)

    def unregister_adapter(self, key: str) -> None:
        """Tests only — a fixture adapter bound for one case is unbound after
        it (wave B). The product binds at `ready()` and never unbinds."""
        self._adapters.pop(key, None)

    def get(self, key: str) -> Manifest | None:
        return self._manifests.get(key)

    def require(self, key: str) -> Manifest:
        manifest = self._manifests.get(key)
        if manifest is None:
            raise ManifestError(f"no manifest registered for {key!r}; registered: {self.keys()}")
        return manifest

    def all(self) -> tuple[Manifest, ...]:
        """In registration order — the order the grid draws them."""
        return tuple(self._manifests.values())

    def keys(self) -> list[str]:
        return list(self._manifests)

    def categories(self) -> list[str]:
        """Every category with at least one card, in first-appearance order.
        The filter chips are GENERATED from this — never a typed list
        (08-screen-layouts.md, the pack's own callout)."""
        seen: dict[str, None] = {}
        for manifest in self._manifests.values():
            seen.setdefault(manifest.category, None)
        return list(seen)

    def host_coverage(self) -> dict[str, int]:
        """What `_validate_hosts` checked, and what it could not — with numbers.

        `DEF-INT-5488` hid behind a check that did not exist; the shape that
        replaces it must not hide behind a check whose blind spot has no
        figure attached. A partner-called operation has no configured host
        because the address is ours, so it is skipped — and this says how many
        were skipped, every time anybody asks.
        """
        checked = skipped = 0
        for manifest in self._manifests.values():
            for op in manifest.operations:
                if op.they_call_us:
                    skipped += 1
                else:
                    checked += 1
        return {"connectors": len(self._manifests), "checked": checked, "skipped": skipped}

    def clear(self) -> None:
        """Tests only — a fresh process registers once at `ready()`."""
        self._manifests.clear()
        self._adapters.clear()

    def __len__(self) -> int:
        return len(self._manifests)


#: The one registry the running product reads. Filled by `apps.py`.
REGISTRY = Registry()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-013@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packet US-INT-018@62d3643)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D✔(GET /integrations serves REGISTRY.all() joined to this tenant's state) E✔(IntegrationsTab.tsx draws it) F✔ G✔ H=n/a(not a 🔒 path — no RLS, no money, no key)
# gates: pytest tests/test_us_int_013_registry.py · G76 (every declared operation names idempotency mode AND completion — the same rule as `_validate_operation`, read from source without Django) · G77 (`provider_key ==` appears nowhere outside adapters/ and manifests/)
# exceptions: the codec vocabulary is read from codecs.py (wave D, 2026-09-03; it was a constant here until then) · `native` added to AUTH_PLACEMENTS as a lane judgment (decision log 2026-09-03) · no adapter is registered by this wave; `adapter_for()` answers None for all seventeen
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
