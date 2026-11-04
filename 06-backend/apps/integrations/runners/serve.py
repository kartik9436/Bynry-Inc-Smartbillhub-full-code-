# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) — the partner's morning. The SERVE quadrant
#           (`out · them`), built empty in wave B and FILLED here (CR-069 wave
#           S, task S1). Wave R (US-INT-040) mints the key and shows it once;
#           this file is the other half — the door that VERIFIES one.
#           Screens: S142 *Who has been reading*
# Rules:    BR-INT-035 (every partner read is a run a manager can read — who,
#           when, how many, under which key) · BR-INT-044 (the source allowlist
#           refuses before the body is read, revealing nothing) · BR-INT-045
#           (the status numbers are the manifest's) · BR-INT-053 (a machine
#           credential is scoped to one tenant) · BR-INT-054 (a — building a
#           connection; b — holding keys; c — the lifecycle: what this file
#           does, and the boundary at `partner_fields()` below) · BR-TEN-003
#           (the tenant is read from the PATH and from nothing else) ·
#           CLAUDE.md hard rule 1 (RLS FORCE; no cross-tenant queryset) ·
#           B14 rule 33 (a refusal is five or six words) · CR-110-BRC04's
#           RULED section (every refusal carries a code; two on the wire, six
#           in the record only — PO 2026-09-16)
# Tests:    06-backend/tests/test_us_int_041_partner_surface.py (TC-1..TC-9)
#           06-backend/tests/test_us_int_016_queue.py (the quadrant resolves here)
# Impacts:  apps/integrations/partner_api.py (the three routes) ·
#           apps/integrations/subprocessors.py (the inward register row) ·
#           config/urls.py (one include line) · wave R must import
#           ISSUED_KEY_BLIND_INDEX_CONTEXT from here rather than retype it
# ───────────────────────────────────────────────────────
"""SERVE — they read from us (`out · them`): the door a partner presents a key at.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials, and the enumeration
oracle a refusal becomes when it says too much). HUMAN-REVIEW-PENDING; the row
is in 12-governance/09-human-review-ledger.md.

WHAT THIS FILE DECIDES, in one sentence: whether a machine that is not signed
in may read one utility's payments and bills — and, when the answer is no, how
to say so without teaching the caller which of three things they got wrong.

THE SIX REFUSALS ARE ONE REFUSAL (BR-INT-044)
------------------------------------------------
⚠ **THIS HEADING READ *THE THREE REFUSALS* UNTIL 2026-09-16** — the guards have
been four since the scope check landed and the causes are SIX once *unknown* and
*revoked* are counted apart, which `CR-110-BRC04` now does. The rule did not
move; the count under it did, twice, without the sentence being amended.

An address that is not on the allowlist, a key that is wrong, a key that was
revoked, a key that has expired, a connector switched off and a key that may not
call this operation must be **indistinguishable**: same words, same code, same
shape, same status, same time on the wire. Anything else is an oracle — a caller holding a stolen
key learns from a faster 404 that the key is real and only the address is
wrong, and goes looking for a proxy.

So `resolve_caller()` has **no early return**. It computes all three answers
whatever the first one says, combines them into a single boolean, and raises
one exception with one sentence. The refusal path is then padded to
`REFUSAL_FLOOR_S`, because "the same work" is not the same as "the same time":
an unknown provider key costs one query less than a revoked credential does,
and a stopwatch reads that difference. The floor is the equaliser and it is
asserted, not assumed — `test_us_int_041_partner_surface.py` puts the three
side by side and compares the bodies byte-for-byte and the elapsed times
against the floor.

⚠ **A SUCCESSFUL read is faster than a refusal and that is deliberate.** The
only caller who can observe it already holds a working key, so there is
nothing left for them to learn.

THE TENANT COMES FROM THE PATH, AND THAT IS WHY THE PATH IS NOT THE ONE THE
PLAN DECLARED
---------------------------------------------------------------------------
The execution plan (S1) writes the surface as `GET /api/v1/payments`. **It
cannot be built at that address**, and the reason is two signed rules meeting:

  * `BR-TEN-003` — *"the ONLY input consulted is the request path. tenant_id in
    a header/param/body is never read."*
  * CLAUDE.md hard rule 1 — RLS is `FORCE`; with no `app.tenant_id` set, a
    tenant table yields **zero rows**.

`integration_credential` is a tenant table. At `/api/v1/payments` there is no
tenant in the path, so no context is set, so the blind-index lookup returns
nothing **for every key, including a perfectly valid one** — the endpoint would
be incapable of passing (CLAUDE.md law 7's third shape), and the only way to
make it pass would be to read the tenant from a header or a parameter, which
`BR-TEN-003` forbids by name.

So the PHASE-1 surface is **`/api/{utility}/v1/payments`** — the utility's own
slug, the same first segment every other route in this product uses, resolved by
the middleware that already exists. The deviation is recorded in
12-governance/02-decision-log.md.

⚠⚠ **AND THE FIVE PHASE-2 ADDRESSES DO NOT CARRY IT, BECAUSE THE ARGUMENT ABOVE
HAS A HOLE IN IT AND THE BLUEPRINT NAMED THE HOLE (`DEF-INT-5546`, PO ruling
2026-09-16).** Everything above is true of a TENANT table, and the conclusion —
*therefore the utility must be in the URL* — only follows if the first lookup
has to be against one. p159, *WHY NOT PUT IT IN THE PATH*, draws it the other
way round:

    key ──► connection ──► tenant ──► app.tenant_id set ──► RLS does the isolating

`integration_key_directory` (migration `0011`) is that first arrow: not a tenant
table, no RLS policy, three opaque ids and a one-way fingerprint, declared on B2
§3's exempt list beside `sessions` — which is exempt for the identical reason,
so that `/api/jobs/{id}` can open a utility from a session row before one is
open. `apps/integrations/key_directory.py` reads it and
`apps/integrations/partner_urls.py` calls that before any of the five views run.

**Nothing in THIS file changed because of it, and that is the point.** By the
time `resolve_caller` executes, `app.tenant_id` is set exactly as it would be on
a path-resolved route, the credential lookup is scoped by RLS exactly as before,
and TC-5 and TC-7 remain properties of the database. The blueprint's reason for
preferring it is worth quoting because it is an argument about maintenance
rather than taste: *"A path segment is a claim; a key is proof. If both exist,
somebody must compare them on every endpoint — that is a line of code on every
handler, and the day it is missed a partner reads another utility's bills."*

⚠ **PO 2026-09-16, verbatim:** *"we agreed not to use utility names in partner
apis that was our rule - so these urls are not corect - we will resolve utility
name using keys"*.

⚠ **THE PAYOFF IS BIGGER THAN THE COST, AND IT IS WHY THIS IS NOT A WORKAROUND.**
TC-5 and TC-7 — a key presented against another utility's route — stop being a
check somebody has to remember to write and become a property of the database:
under Lone Star Ridge's `app.tenant_id`, Brazos Bend's credential row is not
visible, so the lookup finds nothing and falls into the same one refusal as a
key that never existed. There is no line of code here that could be deleted to
break it.

WHAT IS *NOT* HERE, AND WHOSE IT IS (BR-INT-054, CR-069 §20.4)
---------------------------------------------------------------
The 2026-09-06 amendment gives integrations exactly three things: building a
connection, holding keys and secrets, and the lifecycle of a connection. The
door, the allowlist, the rate limit and the run row are all lifecycle and all
live here. **What the payload MEANS does not.**

`partner_fields()` below is the seam and it returns nothing today. The three
fields the plan's S1 lists — `tenderType` resolved through the mapping rows,
the `projectType` constant, `accountString` from the ledger codes — are
**outbound ETL**: building a business record for somebody else. CR-069 §20.4
moves them to Runbooks in as many words. They are a **deliberate absence**, not
a stub awaiting a ruling (the `OQ-1396` distinction): nothing is blocked, the
owner is named, and a lane finding this should leave it alone rather than try
to unblock it.

A test asserts a served record carries our four fields and none of those three,
so the day Runbooks fills the seam the suite goes red and names this paragraph
— which is the only way a boundary written in prose survives contact with the
next lane.

THE DOOR NOW ASKS FOUR QUESTIONS, NOT THREE (CR-110-BRC04, 2026-09-16)
-----------------------------------------------------------------------
The fourth is **WHICH OF OUR APIS THIS KEY MAY CALL**, and it is in the same
single boolean as the other three for the same reason they are in it together.
Until this change a key issued to push meter readings could call every other
inbound API on its connector, because no field said which ones it may call —
the blueprint classes that as a security defect on its own page 17.

EVERY REFUSAL NOW CARRIES A CODE, AND THE EIGHT SPLIT TWO WAYS (CR-110-BRC04)
-----------------------------------------------------------------------------
PO ruling 2026-09-16: *"build refusal code in api responses so that we cna know
what it is"*, then *"go with your recommendation - implment all these code"*.
The recommendation was the split, so the split is the ruling.

**Two travel: `RATE_LIMIT_REACHED` and `COUNTER_UNAVAILABLE`, in the `429`
body.** Both are reachable only by a caller who has already authenticated. The
second is the one the PO needed — a partner refused because OUR counter store is
down used to get the identical sentence as one who genuinely called too fast, and
a manager reading *rate limit reached* during an outage goes to the wrong place.

**Six do not: the auth causes share `SHARED_REFUSAL_CODE` on the wire and are
distinct only in the run row.** `BR-INT-044` is NOT amended. Their distinction is
the enumeration oracle this whole file is built to keep shut, and it now lives
where a manager looks and an attacker cannot.

⚠ **THE CAUSES ARE COMPUTED, NEVER BRANCHED ON, AND MORE THAN ONE CAN BE TRUE.**
See `resolve_caller` — the temptation is to test the guards in turn so as to know
which one refused, and an early return would separate the cheap causes from the
expensive ones by the clock even with identical words. The record is written
INSIDE the padded window for the same reason, because five of the six auth causes
now write a run row and `KEY_UNKNOWN` cannot.

⚠ **AND THE RATE LIMIT IS NO LONGER COUNTED IN THIS PROCESS.** The window moved
to `apps/integrations/rate_limit_store.py`, which is shared between workers.
The sentence that used to sit in `check_rate_limit`'s docstring — *"with N
gunicorn workers the effective limit is N × 100/min"* — was true, was the PO's
stated reason for ruling this work in (*"otherwise if somone hack we will not
have a control"*), and is quoted in that file rather than deleted, because the
arithmetic is what a reviewer needs in order to see what changed.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations import models, rate_limit_store, services
from apps.integrations.adapters import base as adapters_base
from apps.integrations.adapters.base import Adapter
from apps.integrations.registry import REGISTRY, Operation, Registry
from apps.integrations.seams import tenancy as tenancy_seam
from core import crypto
from core.tenancy import current_tenant_id

#: ⚠ **`__name__` AND NOT A NAME OF OUR OWN CHOOSING — `DEF-INT-5512`, AND IT
#: WAS WRONG THE FIRST TIME.** `config/settings/base.py` configures exactly
#: three logger trees: `django`, `apps` and `core`. This module's first draft
#: said `getLogger("smartbillhub.integrations.serve")`, which is under NONE of
#: them, so every record fell through to the ROOT logger — which has no handler
#: — and `logging.lastResort` only prints at WARNING and above. **The
#: `KEY_UNKNOWN` record, the one cause with nowhere else to go, was written to a
#: logger that prints nothing.** That is `DEF-2161` exactly, one package along,
#: and the settings block above it says so in as many words. Found by curling
#: the running product and seeing no line (hard-won law 6), not by any test:
#: `caplog` attaches its OWN handler to whatever name it is given, so a logger
#: with no configured handler at all looks perfectly healthy in pytest.
#: `test_the_refusal_logger_is_inside_the_configured_tree` is the guard.
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# The constants the door is made of
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠ WAVE R MUST IMPORT THIS, NEVER RETYPE IT. The blind index is an HMAC over
#: the key with this string as context; `services.record_credential(...,
#: blind_index=…)` writes it at issue and `_credential_matching()` below reads
#: it at every call. If the two strings ever differ, EVERY valid key is refused
#: and the door still looks like it is working — the failure is silent in both
#: directions, because a refused key is exactly what a wrong key looks like.
ISSUED_KEY_BLIND_INDEX_CONTEXT = "integration_credential.issued_key"

#: The one thing we say when we will not serve. FIVE WORDS (B14 rule 33), no
#: rule id, no hint about which of the guards refused. It is a module constant
#: so that a grep proves there is only one of them.
REFUSAL_SENTENCE = "We cannot serve this request."

# ═══════════════════════════════════════════════════════════════════════════
# THE EIGHT REFUSAL CODES — and the line down the middle of them
# ═══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-09-16 (`CR-110-BRC04`, the CR's last section): *"build refusal
# code in api responses so that we cna know what it is"*, then — shown all eight
# with the security consequence written against each — *"go with your
# recommendation - implment all these code"*.
#
# ⚠ **THE RECOMMENDATION *IS* THE RULING, SO THE SPLIT IS PART OF IT.** The PO
# was offered the other answer in as many words and chose this one:
#
#   * `RATE_LIMIT_REACHED` and `COUNTER_UNAVAILABLE` travel **on the wire**, in
#     the `429` body, because both are reachable only by a caller who has
#     ALREADY authenticated. The code tells them nothing they did not know.
#     Row 2 is the one the PO actually needed: today a partner refused because
#     OUR counter store is down gets the identical sentence to one who genuinely
#     called too fast, and a manager reading *rate limit reached* during an
#     outage goes to look at the ceiling instead of at Redis.
#
#   * The six AUTH causes share ONE code on the wire — `SHARED_REFUSAL_CODE` —
#     and `BR-INT-044` is NOT amended. A guessed key answering `KEY_UNKNOWN`
#     says *keep guessing*; a stolen key answering `ADDRESS_NOT_ALLOWED` says
#     *the key is REAL, now find a proxy*; from that proxy
#     `OPERATION_NOT_IN_SCOPE` says *you are in, now map what it reaches*. Each
#     would narrow an attacker's search. Their distinction lives in the RECORD —
#     the run row S142 draws — where a manager looks and an attacker cannot.

#: Rows 1–2 · distinct on the wire, in the `429` body.
CODE_RATE_LIMIT_REACHED = "RATE_LIMIT_REACHED"
CODE_COUNTER_UNAVAILABLE = "COUNTER_UNAVAILABLE"

#: Rows 3–8 · distinct in our record, one shared code on the wire.
CODE_KEY_UNKNOWN = "KEY_UNKNOWN"
CODE_KEY_REVOKED = "KEY_REVOKED"
CODE_KEY_EXPIRED = "KEY_EXPIRED"
CODE_ADDRESS_NOT_ALLOWED = "ADDRESS_NOT_ALLOWED"
CODE_CONNECTOR_DISABLED = "CONNECTOR_DISABLED"
CODE_OPERATION_NOT_IN_SCOPE = "OPERATION_NOT_IN_SCOPE"
#: `CR-110-BRC04` phase 2 — the utility itself is not one we may serve.
#: PO 2026-09-16: *"you have to also check whether connector is activae whether
#: tenant is active"*. The connector half was already row 7; this is the other.
#:
#: ⚠ **RECORD-ONLY, LIKE THE SIX ABOVE IT, AND FOR A SHARPER REASON THAN
#: THEY HAVE.** A distinct code here would answer *does this utility exist and
#: is it switched on* to anyone holding any key — which is the enumeration
#: oracle `BR-INT-044` closes, pointed at the tenant rather than at the
#: credential. It reads exactly like every other refusal on the wire.
CODE_UTILITY_INACTIVE = "UTILITY_INACTIVE"

#: ⚠ **THE ONE CODE ALL SIX AUTH REFUSALS SHARE, AND IT CARRIES NO
#: INFORMATION.** It is a constant so that the body is the same bytes whichever
#: of the six happened — the byte-identity test compares them and would go red
#: the day a lane made this depend on the cause.
SHARED_REFUSAL_CODE = "REFUSED"

#: The eight, in the order the PO's own table lists them. `G`-style gates and
#: the tests read this rather than retyping the strings.
REFUSAL_CODES = (
    CODE_RATE_LIMIT_REACHED,
    CODE_COUNTER_UNAVAILABLE,
    CODE_KEY_UNKNOWN,
    CODE_KEY_REVOKED,
    CODE_KEY_EXPIRED,
    CODE_ADDRESS_NOT_ALLOWED,
    CODE_CONNECTOR_DISABLED,
    CODE_OPERATION_NOT_IN_SCOPE,
    # ── CR-110-BRC04 phase 2 · the NINTH, and it EXTENDS the PO's table
    # rather than superseding it. The eight above are the PO's 2026-09-16
    # ruling *"go with your recommendation - implment all these code"*, taken
    # over the causes that existed that morning; this one implements the PO's
    # OTHER ruling of the same day — *"you have to also check whether connector
    # is activae whether tenant is active"* — which adds a cause and therefore
    # adds a code. Nothing above moves, and the split it falls on (record-only)
    # is the one the recommendation already set.
    CODE_UTILITY_INACTIVE,
)

#: The two that a partner is allowed to tell apart.
WIRE_CODES = (CODE_RATE_LIMIT_REACHED, CODE_COUNTER_UNAVAILABLE)

#: The six whose distinction is ours alone.
RECORD_ONLY_CODES = tuple(one for one in REFUSAL_CODES if one not in WIRE_CODES)

#: What the RUN ROW says — read by a person on S142, so B14 rule 33 applies:
#: a FACT is six words or fewer, no rule id, no code. The code is the machine's
#: half and lives in `run.items`; this is the human's half and lives in the
#: summary the access log draws.
CAUSE_TEXT = {
    CODE_RATE_LIMIT_REACHED: "rate limit reached",
    CODE_COUNTER_UNAVAILABLE: "call limit could not be counted",
    CODE_KEY_UNKNOWN: "key not recognised",
    CODE_KEY_REVOKED: "key revoked",
    CODE_KEY_EXPIRED: "key expired",
    CODE_ADDRESS_NOT_ALLOWED: "address not on the allowlist",
    CODE_CONNECTOR_DISABLED: "connector switched off",
    CODE_OPERATION_NOT_IN_SCOPE: "key may not call this",
    CODE_UTILITY_INACTIVE: "utility not active",
}


def cause_text(codes: Sequence[str]) -> str:
    """The run row's words for one refusal — *"key expired, address not on the
    allowlist"* when two causes are true at once.

    ⚠ **JOINED WITH A COMMA AND NOT WITH ` · `, WHICH IS NOT A STYLE CHOICE.**
    `partner_api.access_log` builds the screen's *What they took* column as
    `summary.split(" · ")[0]`, so a middot here would put the first cause on
    screen and hide the rest — the exact first-match-wins behaviour this wave
    exists to remove, arriving through the punctuation.
    """
    return ", ".join(CAUSE_TEXT.get(one, one) for one in codes) or "refused"

#: The refusal path never returns faster than this. See the docstring — the
#: three refusals do different amounts of database work, and without a floor a
#: stopwatch separates them. 40ms comfortably exceeds the spread between "no
#: connection row" and "a credential row that is revoked" on both vendors.
REFUSAL_FLOOR_S = 0.040

#: Requests per minute per key, per tenant. The plan's figure (S1, TC-4).
DEFAULT_RATE_LIMIT_PER_MINUTE = 100

#: What a `429` tells them to wait. Whole seconds — `Retry-After` is a header.
RETRY_AFTER_S = 60

#: The manifest field that carries the allowlist, and the config key the
#: connect modal writes it to.
ALLOWLIST_CONFIG_KEY = "allowed_addresses"
RATE_LIMIT_CONFIG_KEY = "rate_limit_per_minute"

#: The audited grant `OQ-INT-1481` option (a) requires, stored on the
#: connection's non-secret config. Read by `subprocessors.py` to derive the
#: register row pointing inward.
GRANT_CONFIG_KEY = "authority_grant"


class PartnerRefused(Exception):
    """The one refusal — and, since `CR-110-BRC04`, the one refusal that KNOWS
    WHY, without any of that knowledge reaching the caller.

    ⚠ **`causes` IS FOR THE RECORD AND NEVER FOR THE RESPONSE.** `partner_api`
    renders `REFUSAL_SENTENCE` and `SHARED_REFUSAL_CODE` and nothing off this
    object; the six auth refusals are byte-identical on the wire and a test
    puts all six side by side and proves it. The reason the field exists at all
    is that *"WorldPay refused: key expired, 14 times since 06:00"* is what the
    PO asked to be able to read on our side.

    ⚠ **IT IS A TUPLE AND NOT A SINGLE CODE, BECAUSE MORE THAN ONE CAUSE CAN BE
    TRUE AT ONCE.** An expired key presented from a disallowed address is rows
    5 AND 6 of the PO's table. *Which of the guards failed* is the whole
    diagnostic value of this wave, so first-match-wins would throw away the
    half a manager most needs — and an ordering that decided which one to keep
    would be exactly the branch the module docstring forbids.
    """

    def __init__(self, causes: Sequence[str] = ()) -> None:
        super().__init__(REFUSAL_SENTENCE)
        self.causes: tuple[str, ...] = tuple(causes)


class PartnerRateLimited(Exception):
    """Distinct from `PartnerRefused` and that is safe: a `429` is only ever
    reachable by a caller who has ALREADY authenticated, so it tells them one
    thing they already know. An unauthenticated caller can hammer this door all
    day and never see anything but `PartnerRefused` (TC-4).

    ⚠ **`countable` SAYS WHICH OF TWO THINGS HAPPENED, AND IT NEVER REACHES THE
    CALLER (`CR-110-BRC04`).** *You have had your hundred* and *we could not
    count, so no* are the same answer on the wire, deliberately — but they are
    NOT the same answer in the access log a manager reads. A run row saying
    *rate limit reached* while the real cause is an unreachable counter sends
    somebody to look at the ceiling instead of at Redis, which is the expensive
    kind of wrong conclusion this repo keeps paying for. The body, the status
    and the `Retry-After` are identical either way; only the row differs.
    """

    def __init__(self, retry_after_s: int = RETRY_AFTER_S, *, countable: bool = True) -> None:
        super().__init__(REFUSAL_SENTENCE)
        self.retry_after_s = int(retry_after_s)
        self.countable = bool(countable)

    @property
    def code(self) -> str:
        """Row 1 or row 2 of the PO's table — **and this one DOES go on the
        wire** (`CR-110-BRC04`), in the `429` body beside the same five words.

        Safe for the stated reason and for no other: a `429` is only ever
        reachable by a caller who has already authenticated, so naming which of
        the two happened tells them nothing they did not already know. An
        unauthenticated caller can hammer this door all day and sees nothing
        but `SHARED_REFUSAL_CODE`.
        """
        return CODE_RATE_LIMIT_REACHED if self.countable else CODE_COUNTER_UNAVAILABLE

    @property
    def window_text(self) -> str:
        """What the run row says. Six words or fewer, no rule id, no code —
        B14 rule 33, because S142 shows it to a person. Derived from `code` so
        the sentence and the code cannot drift apart."""
        return CAUSE_TEXT[self.code]


@dataclass(frozen=True)
class PartnerCaller:
    """Who is reading, in the only terms a record of it may carry.

    ⚠ THERE IS NO KEY ON THIS OBJECT. `hint` is `••••7Q2F` — the masked hint
    wave E already stores — and it is what travels to the run row, the screen
    and the register. A run record naming a secret is a leaked secret, and the
    cheapest way to guarantee it cannot happen is for the plaintext never to
    survive `resolve_caller()`.
    """

    connection: models.IntegrationConnection
    credential_id: Any
    hint: str
    tenant_id: Any
    scopes: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════
# The guards — computed together, refused once
# ═══════════════════════════════════════════════════════════════════════════


def _connection_for(provider_key: str) -> models.IntegrationConnection | None:
    """The partner connection in the CURRENT tenant context, or None.

    ⚠ **THE DOOR NO LONGER READS THIS — `resolve_caller()` goes at the
    CREDENTIAL and takes the connection from it** (see `_credential_matching`
    for why). This remains for the paths where there is no key to start from:
    the System Admin's grant, and the tests that build a fixture.

    No `tenant_id` ARGUMENT, deliberately: the tenant is read from the context
    the path already set, so a caller cannot point this at another utility.

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS NOT OPTIONAL, FOR A
    REASON THAT COST THIS WAVE AN HOUR.** RLS `FORCE` scopes this query on
    PostgreSQL, so the filter is redundant in production. **The test suite runs
    on SQLite, which has no RLS at all** (`config/settings/test.py` hardcodes
    it — CLAUDE.md law 14 records the same trap for aborted transactions), and
    the first draft of this function relied on RLS alone. On SQLite it
    therefore returned the FIRST connection of ANY tenant, and the two-tenant
    isolation cases failed — which was luck. Written the other way round, a
    door that leaked across tenants would have passed the whole suite, because
    the one mechanism that would have stopped it does not exist on the vendor
    the suite runs on: law 7's *structurally incapable of failing*, on the
    guarantee this product's hard rule 1 is about.

    So the tenant is stated twice — once by the database and once here — and
    `test_tc7…` can now go red on either vendor.

    A request with NO tenant context is refused outright rather than returning
    everybody's rows, because failing closed is the whole point (hard-won law 3).
    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    return (
        models.IntegrationConnection.objects.filter(
            tenant_id=tenant_id, provider_key=provider_key
        )
        .order_by("created_at")
        .first()
    )


def _credential_matching(
    presented: str | None, provider_key: str | tuple[str, ...]
) -> models.IntegrationCredential | None:
    """The credential row this key hashes to — ACTIVE OR NOT — with its connection.

    ⚠ **THE KEY NAMES THE CONNECTION, AND THE FIRST DRAFT HAD IT THE OTHER WAY
    ROUND.** It looked up *the tenant's first `gl_partner` connection by
    `created_at`* and asked whether the presented key belonged to that one. A
    tenant may lawfully have TWO — `BR-INT-026`'s UNIQUE is (tenant,
    provider_key, environment), the sandbox/production pair the design's
    failure list ranks first — so "the first by created_at" is arbitrary, and a
    production key would have been checked against the SANDBOX connection's
    allowlist, rate limit and grant. The walkthrough's seed writes both, and
    that is what exposed it.

    Inverted it is correct by construction and simpler: the key identifies the
    credential, the credential names its own connection, and that connection
    carries the allowlist, the limit and the grant. Nothing is left to order.

    ⚠ `is_active` is deliberately NOT in this filter. A revoked key must cost
    the same query as a live one, or the two are distinguishable by time; the
    activity check happens in `resolve_caller()` beside the other two, and all
    three land in one boolean.

    The lookup is `blind_index__in candidates` because the index is keyed and
    the keyring can hold more than one key during a rotation (`core/crypto.py`
    says so): equality against the ACTIVE token alone would refuse every
    credential indexed under the previous one.
    """
    if not presented:
        return None
    candidates = crypto.blind_index_candidates(
        presented, context=ISSUED_KEY_BLIND_INDEX_CONTEXT
    )
    if not candidates:
        return None
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    return (
        models.IntegrationCredential.objects.select_related("connection")
        .filter(
            tenant_id=tenant_id,
            blind_index__in=candidates,
            # ⚠ ONE QUERY, WHATEVER THE SHAPE. `CR-110-BRC04` split the one
            # finance connector into five named ERPs, so the partner surface
            # now presents five keys where it presented one — and asking five
            # times in turn would make an unknown key cost a different amount
            # of time depending on WHICH partner it nearly was, which is the
            # enumeration oracle this whole function is built to close.
            connection__provider_key__in=(
                (provider_key,) if isinstance(provider_key, str) else tuple(provider_key)
            ),
        )
        .order_by("-version")
        .first()
    )


def allowlist_permits(connection: models.IntegrationConnection | None, address: str | None) -> bool:
    """BR-INT-044 — is this source address one the connection published?

    An EMPTY or absent list permits everything: a connection whose provider
    publishes no source addresses is not thereby unreachable. A list that is
    present is exhaustive.

    Anything unparseable — a missing address, a hostname, a malformed CIDR —
    is a NO. Failing closed is the whole point (hard-won law 3).
    """
    if connection is None:
        return False
    raw = (connection.config or {}).get(ALLOWLIST_CONFIG_KEY)
    entries = _allowlist_entries(raw)
    if not entries:
        return True
    if not address:
        return False
    try:
        caller = ipaddress.ip_address(str(address).strip())
    except ValueError:
        return False
    for entry in entries:
        try:
            if caller in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            # A malformed entry refuses that entry and never the whole list —
            # one typo in the modal must not silently open the door.
            continue
    return False


def _allowlist_entries(raw: Any) -> tuple[str, ...]:
    """`198.51.100.0/24, 203.0.113.7` — typed as one line, stored as one
    string, read here as a list. A list in the config is also accepted, because
    the modal may grow a chip control later and the door should not care."""
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        items = [str(one).strip() for one in raw]
    else:
        items = [one.strip() for one in str(raw).replace(";", ",").split(",")]
    return tuple(one for one in items if one)


def _pad_to_floor(started_at: float) -> None:
    """Hold the refusal until the floor. See the module docstring."""
    remaining = REFUSAL_FLOOR_S - (time.monotonic() - started_at)
    if remaining > 0:
        time.sleep(remaining)


def scope_permits(credential: models.IntegrationCredential | None, operation: str | None) -> bool:
    """`CR-110-BRC04` — may THIS key call THIS operation?

    ⚠ **A BLANK SCOPE GRANTS NOTHING, WHICH IS THE OPPOSITE OF THE DRAWING.**
    The blueprint puts *"Leave blank for everything the key allows"* under its
    Scope box — the widest permission as the default — and the CR's decision 5
    refuses it under hard-won law 3: **the unsafe option must be the one you
    type.** So an empty list is `False` here for every operation, including
    `None`.

    `operation=None` is *"this is not an operation call"* — the published
    specification is the only such caller. A key that may call something may
    read the description of what it may call; a key that may call nothing may
    not.
    """
    if credential is None:
        return False
    granted = _scopes(credential)
    if not granted:
        return False
    if operation is None:
        return True
    return operation in granted


def resolve_caller(
    *,
    provider_key: str | tuple[str, ...],
    presented_key: str | None,
    source_address: str | None,
    operation: str | None,
) -> PartnerCaller:
    """Authenticate one partner request, or refuse it in the one way.

    ⚠ **NO EARLY RETURNS.** Every guard below is evaluated whatever the ones
    before it said, and there is exactly one `raise`. That is not style: an
    early return on the allowlist would skip the credential query, and the
    saved query is the oracle (BR-INT-044). If a later lane "tidies" this into
    guard clauses, the three refusals stop being one refusal and no test that
    only reads BODIES will notice — which is why the timing assertion exists.

    The tenant is whatever `app.tenant_id` the path already set. This function
    never takes one, so it cannot be pointed across the boundary.

    ⚠ **`operation` IS REQUIRED AND HAS NO DEFAULT, ON PURPOSE (`CR-110-BRC04`).**
    The fourth guard is the key's SCOPE, and it is folded into the same single
    boolean rather than checked afterwards by the caller, for the reason the
    other three are: a scope refusal that costs a different amount of work, or
    arrives in different words, tells a caller holding a stolen key that the key
    is real and only the operation was wrong. Making the argument required means
    a door added later cannot inherit the check by forgetting it — it has to
    name an operation or say `None`, and `None` is the specification's answer,
    not a way past this.
    """
    started_at = time.monotonic()

    # ONE query, whatever the answer turns out to be: an unknown key, a revoked
    # key and a key whose connection forbids this address all cost exactly this
    # much, which is half of what makes the three refusals one refusal.
    credential = _credential_matching(presented_key, provider_key)
    connection = credential.connection if credential is not None else None

    key_ok = credential is not None and bool(credential.is_active)
    address_ok = allowlist_permits(connection, source_address)
    connection_ok = connection is not None and bool(connection.enabled)
    # ⚠ **THE UTILITY ITSELF (`CR-110-BRC04` phase 2), AND IT IS A STATEMENT
    # AND NOT A BRANCH.** PO 2026-09-16: *"you have to also check whether
    # connector is activae whether tenant is active"*. It is computed here
    # beside the others, unconditionally, for the reason the block below gives:
    # a guard that only RUNS sometimes costs a different amount of time
    # depending on which cause is true, and a stopwatch reads that.
    #
    # ⚠ **IT ASKS THE PATH'S TENANT AND NOT THE CONNECTION'S**, which are the
    # same utility on every request that gets this far and are not the same
    # QUESTION. The path's tenant is what `app.tenant_id` is set to, so it is
    # what every read after this point is scoped by — including the credential
    # lookup above, which is why an unknown key still answers here. Reading
    # `connection.tenant_id` instead would answer `None` for an unknown key and
    # make this guard cost a query on some paths and not others.
    utility_ok = tenancy_seam.utility_is_live(current_tenant_id())
    unexpired = credential is None or credential.expires_at is None or credential.expires_at > timezone.now()
    scope_ok = scope_permits(credential, operation)

    # ⚠ **THE CAUSES ARE A VARIABLE COMPUTED BESIDE THE OTHERS, NEVER A BRANCH
    # (`CR-110-BRC04`).** The obvious way to know which guard refused is to test
    # them in turn and return at the first `no` — and that re-opens the timing
    # oracle even though every arm would raise identical words, because the
    # cheap causes then answer sooner. So every pair below is evaluated on every
    # path, out of values already in hand: no query, no short circuit that skips
    # work, and nothing here decides what happens next. The `if` under it is the
    # same single combined boolean it has always been.
    #
    # ⚠ **AND ALL OF THEM, NOT THE FIRST.** An expired key presented from an
    # address that is not on the list is rows 5 AND 6 of the PO's table, and
    # *which of the five failed* is the whole diagnostic value being built here.
    # The two `have_…` guards are what stop an unknown key reporting four
    # causes: with no credential row there is no connection either, so the
    # allowlist, the switch and the scope all answer `False` truthfully and
    # about nothing. `KEY_UNKNOWN` alone is the honest record of that request.
    have_credential = credential is not None
    have_connection = connection is not None
    # ⚠ **ADDED 2026-09-16 (`DEF-INT-5546`) AND IT GATES A RECORDED CAUSE, NEVER
    # THE REFUSAL.** `utility_ok` stays in the combined boolean below whatever
    # this says, so a request with no utility open is still refused — failing
    # closed is the whole point. What it changes is what we WRITE DOWN. Since
    # the five partner addresses lost their `{utility}` segment, a key we do not
    # recognise resolves no utility at all, and `utility_is_live(None)` is
    # correctly `False` — but recording `UTILITY_INACTIVE` for it would tell a
    # manager their utility is switched off when the truth is that we never
    # worked out which utility the caller meant. Same `have_…` reasoning as the
    # six rows below: report only what we actually know.
    have_tenant = current_tenant_id() is not None
    causes = tuple(
        code
        for failed, code in (
            (not have_credential, CODE_KEY_UNKNOWN),
            (have_credential and not key_ok, CODE_KEY_REVOKED),
            (have_credential and not unexpired, CODE_KEY_EXPIRED),
            (have_connection and not address_ok, CODE_ADDRESS_NOT_ALLOWED),
            (have_connection and not connection_ok, CODE_CONNECTOR_DISABLED),
            (have_credential and not scope_ok, CODE_OPERATION_NOT_IN_SCOPE),
            # ⚠ **UNGATED, UNLIKE EVERY ROW ABOVE IT, AND DELIBERATELY SO.**
            # The `have_…` guards exist so that an unknown key does not report
            # four causes about a connection that does not exist. A switched-off
            # UTILITY is not a fact about the key or the connection — it is true
            # of the request whoever made it, and it is the single most useful
            # thing a manager can read when every partner call is being refused
            # at once. So it stands beside `KEY_UNKNOWN` rather than instead of
            # it, and *"key not recognised, utility not active"* is the honest
            # record of a stranger knocking at a utility that is switched off.
            (have_tenant and not utility_ok, CODE_UTILITY_INACTIVE),
        )
        if failed
    )

    if not (key_ok and address_ok and connection_ok and unexpired and scope_ok and utility_ok):
        # ⚠ **RECORDED BEFORE THE PADDING, AND THE ORDER IS THE WHOLE POINT.**
        # Five of the six auth causes have a connection to hang a run row on and
        # `KEY_UNKNOWN` does not, so the refusals no longer do the same amount of
        # database work. Writing the row INSIDE the padded window is what puts
        # that difference back under the floor: `_pad_to_floor` measures from
        # `started_at`, so whatever the row cost is time the caller was going to
        # wait anyway. Move this line below the padding and every refusal that
        # writes a row becomes the slow one — which is the oracle wearing the fix.
        record_refusal(
            credential=credential,
            connection=connection,
            operation=operation,
            causes=causes,
        )
        _pad_to_floor(started_at)
        raise PartnerRefused(causes)

    assert connection is not None and credential is not None  # narrowed by key_ok
    return PartnerCaller(
        connection=connection,
        credential_id=credential.id,
        hint=credential.masked_hint,
        tenant_id=connection.tenant_id,
        scopes=_scopes(credential),
    )


#: `CR-110-BRC04` phase 2 · the ONE code that travels on a 403, and the reason
#: it may. Check 7 is reachable only by a caller who has already passed checks
#: 1–6, so it holds a live key for a live utility; telling it *the company you
#: named is not the one this key belongs to* says nothing it could not work out
#: by reading its own configuration. The same argument the two `429` codes rest
#: on, and no wider.
CODE_COMPANY_MISMATCH = "COMPANY_MISMATCH"

#: Five words, no rule id, no id echoed back (B14 rule 33, and echoing the
#: value would make this endpoint a probe for *is this a real utility id*).
COMPANY_MISMATCH_SENTENCE = "This key is another utility's."


def company_id_matches(caller: PartnerCaller, presented: Any) -> bool:
    """Check 7 — does the `company_id` they sent name the utility their key
    belongs to? **VERIFIED, NEVER USED TO SELECT.**

    ⚠ **THIS IS THE WHOLE OF WHAT `company_id` DOES, AND THE RULING THAT
    PUT IT HERE CONFIRMS THE RULE RATHER THAN SOFTENING IT.** PO 2026-09-16:
    *"company_id = tenant id"*. `BR-TEN-003` — *"the ONLY input consulted is
    the request path; tenant_id in a header/param/body is never read"* — so
    the utility comes from the KEY (key → credential → connection → tenant)
    and from the path that let the key be found, and this parameter is
    compared against that answer and thrown away. **Whoever can send one
    utility's id can send another's**, so a `company_id` that SELECTED would
    be a door onto every utility in the product.

    ⚠ **A MISSING VALUE IS A NO.** The parameter is required, and treating
    absent as *the caller meant their own* would make the one honest use of
    this check — a partner configured against the wrong utility discovering it
    on the first call rather than after a month of empty pulls — the one case
    it does not cover (hard-won law 3: the unsafe option must be the one you
    type).

    ⚠ **COMPARED AS TEXT, CASE-FOLDED, AFTER STRIPPING.** A uuid is written
    with and without hyphens and in either case by different tools; refusing a
    partner over a capital letter would be a support call that teaches nothing.
    Anything that is not a uuid at all is a no.
    """
    import uuid as _uuid

    try:
        wanted = _uuid.UUID(str(presented).strip())
    except (TypeError, ValueError, AttributeError):
        return False
    try:
        ours = caller.tenant_id if isinstance(caller.tenant_id, _uuid.UUID) else _uuid.UUID(str(caller.tenant_id))
    except (TypeError, ValueError):  # pragma: no cover — a caller always has one
        return False
    return wanted == ours


def _scopes(credential: models.IntegrationCredential) -> tuple[str, ...]:
    """Which of our operations THIS KEY may call (`CR-110-BRC04`).

    ⚠ **IT READS THE CREDENTIAL AND NOT `connection.config["scopes"]`, AND THE
    SWAP IS THE WHOLE SECURITY FIX.** The blueprint classes the old shape as a
    security defect in as many words (p017, `CR-4`, *SECURITY SHAPE · RULED:
    SCOPE IT*): *"a partner handed a key to push meter readings can call every
    other inbound API on that connector — because there is no field that says
    which ones they may call."* A scope on the CONNECTION is a property of the
    relationship; a scope on the KEY is a property of the thing a partner
    actually holds, and replacing a key is the moment its reach is meant to be
    reconsidered.

    ⚠ **ANYTHING THAT IS NOT A LIST OF STRINGS IS NO SCOPE AT ALL.** A
    malformed value must not widen the key — a `None`, a number or a dict all
    come back as `()`, which grants nothing (hard-won law 3). `issue_key`
    refuses to mint an empty one, so a row that reaches here empty has come
    from somewhere that was not supposed to write it.

    ⚠ **`connection.config["scopes"]` STILL EXISTS AND IS NO LONGER READ BY THE
    DOOR.** `gl_partner`'s manifest declares a clerk-facing `scopes` field with
    the options *payments · bills · customers*, which are not operation names
    (`read_payments`, `read_bills`, `read_customers`). Two vocabularies for one
    idea is `DEF-INT-5504`; it is FILED rather than fixed here, because
    changing a manifest belongs to the lane that owns the set-up form.
    """
    raw = credential.scope
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(one) for one in raw if isinstance(one, str) and one.strip())


# ═══════════════════════════════════════════════════════════════════════════
# The rate limit — per KEY and per TENANT, by construction
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠ KEYED ON `(tenant_id, credential_id)` AND — SINCE `CR-110-BRC04` — ON THE
#: OPERATION. `runtime.py`'s concurrency cap carries the same warning for the
#: same reason: key a limit on the PROVIDER and one utility's busy partner
#: throttles another utility's quiet one — the exact failure this module exists
#: to prevent, wearing the fix's clothes. Two tenants on the same `gl_partner`
#: manifest have two independent windows and `test_..._tc4b` proves it with two
#: tenants rather than reasoning about one.
#:
#: The window itself now lives in `apps/integrations/rate_limit_store.py`,
#: which is shared between workers. Read that file's docstring before changing
#: anything here: the arithmetic it replaced was N × this number.


def reset_partner_limits() -> None:
    """Test seam, matching `runtime.reset_caps()`."""
    rate_limit_store.reset()


def rate_limit_for(
    connection: models.IntegrationConnection,
    operation: str | None = None,
    *,
    registry: Registry = REGISTRY,
) -> int:
    """This connection's ceiling for this operation, in calls a minute.

    ⚠ **THREE SOURCES AND THE ORDER IS THE WHOLE RULE.** The row in
    `integration_rate_limit` wins, because that is where a utility's own quota
    lives and the PO ruled it into the database precisely so it can be changed
    without a release. Below it sits the connection's `config` value, kept
    because it is what every connection written before this CR carries and
    dropping it would silently promote those connections to the default.
    Below that, the manifest's declared default for the operation. Below that,
    `DEFAULT_RATE_LIMIT_PER_MINUTE`.

    ⚠ **THERE IS NO FOURTH ANSWER, AND IN PARTICULAR NO *UNLIMITED*.** A
    connection with no row, no config and no manifest default is limited to
    100 a minute, not to everything (hard-won law 3). A lane that makes an
    absent row mean *no ceiling* has turned the guard off for every connector
    that has not been provisioned yet — which is all of them.
    """
    if operation is not None:
        row = (
            models.IntegrationRateLimit.objects.filter(
                tenant_id=connection.tenant_id, connection=connection, operation=operation
            )
            .only("calls_per_minute")
            .first()
        )
        if row is not None and row.calls_per_minute > 0:
            return int(row.calls_per_minute)

    raw = (connection.config or {}).get(RATE_LIMIT_CONFIG_KEY)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    if value > 0:
        return value

    if operation is not None:
        manifest = registry.get(connection.provider_key)
        if manifest is not None:
            for one in manifest.operations:
                if one.name == operation and one.rate_limit_per_minute:
                    return int(one.rate_limit_per_minute)
    return DEFAULT_RATE_LIMIT_PER_MINUTE


def check_rate_limit(
    caller: PartnerCaller,
    *,
    operation: str,
    now: float | None = None,
    registry: Registry = REGISTRY,
) -> None:
    """The 101st request in a minute waits (TC-4) — across every worker.

    A sliding window rather than a fixed bucket, so a partner cannot take 200
    in two seconds by straddling a minute boundary. The PO's third instruction
    was *"keep nthe check in code - thats it"*, so the shape is unchanged; what
    moved is where the window is kept.

    ⚠ **THE LIMITATION THIS DOCSTRING USED TO STATE IS THE ONE THE PO RULED
    OUT, AND THE OLD SENTENCE IS QUOTED IN `rate_limit_store.py` RATHER THAN
    DELETED**, because the arithmetic it recorded — *"with N gunicorn workers
    the effective limit is N × 100/min"* — is what a reviewer needs in order to
    see what this change bought. With three workers a ceiling of 100 was 300.
    It is 100 now, whatever the worker count, and four real processes prove it
    in `tests/test_cr110_shared_counter_pg.py`.

    ⚠ **`operation` IS REQUIRED AND HAS NO DEFAULT.** The limit is per
    connection AND per operation (blueprint p017), so a caller that does not
    say which operation it is making cannot be counted correctly — and a
    default here would count every operation into one window, which is the
    shape this CR exists to replace.

    ⚠ **AN UNREACHABLE STORE REFUSES.** `rate_limit_store.take` raises when it
    cannot count, and that becomes the same `429` an over-limit caller gets.
    There is no arm of this function that serves a request it could not count:
    a rate limiter that opens when its counter breaks is a rate limiter an
    attacker turns off.
    """
    limit = rate_limit_for(caller.connection, operation, registry=registry)
    try:
        permitted = rate_limit_store.take(
            tenant_id=caller.tenant_id,
            credential_id=caller.credential_id,
            operation=operation,
            limit=limit,
            now=now,
        )
    except rate_limit_store.CounterUnavailable as exc:
        raise PartnerRateLimited(countable=False) from exc
    if not permitted:
        raise PartnerRateLimited()


# ═══════════════════════════════════════════════════════════════════════════
# The record — every page is a run, with the hint as *who*
# ═══════════════════════════════════════════════════════════════════════════


def record_read(
    *,
    caller: PartnerCaller,
    operation: str,
    rows: int,
    window: str,
    page: int = 1,
    total_pages: int = 1,
    refused: bool = False,
    items: Sequence[Mapping[str, Any]] = (),
    registry: Registry = REGISTRY,
    direction: str = models.RUN_DIRECTION_INBOUND_READ,
) -> models.IntegrationRun:
    """One partner read → one `inbound_read` run row (BR-INT-035).

    *02:41 · Aclarian · payments · 500 records · page 1 of 3 · ••••7Q2F* — and
    the last field is the whole point. `caller.hint` is a mask; there is no
    code path from here to the plaintext, because `resolve_caller()` did not
    keep one.

    EVERY PAGE IS A RUN, not every collection. Three pages of 500, 500 and 236
    are three rows, because "1,236 in one go" and "1,236 over three requests at
    02:41" look different to a manager and the second is the one worth seeing.

    `attempted` is the rows HANDED OVER — the plan's word — and it equals
    `succeeded` on a read that completed: nothing was tried and missed. A
    refused read records `attempted = 0` and `failed = 1`, so the access log
    shows an attempt that learned nothing rather than a gap.

    ⚠ **`direction` IS AN ARGUMENT SINCE 2026-09-24 AND ITS DEFAULT IS WHAT
    THIS FUNCTION ALWAYS DID.** The partner door stopped being read-only that
    day: `POST /partner/v1/make-payment/` is the first address on it that
    creates money, and `record_write` below is the sibling that records one.
    A write filed under `inbound_read` would put *they took data from us* on a
    manager's access log for a call that put money INTO this utility — two
    opposite facts under one word, which is the sort of thing nobody notices
    until they are reconciling. **Every existing caller passes nothing and is
    byte-for-byte unchanged.**
    """
    run = services.start_run(
        connection=caller.connection,
        operation=operation,
        direction=direction,
        trigger="partner",
        registry=registry,
    )
    pages = f"page {page} of {total_pages}"
    summary = (
        f"{window} · {rows} records · {pages} · {caller.hint}"
        if not refused
        else f"{window} · refused · {caller.hint}"
    )
    # ⚠ A REFUSAL WE MADE OURSELVES IS `skipped`, NOT `unconfirmed`, AND THE
    # FIRST DRAFT HAD IT WRONG — visible only by reading the rows a real run
    # wrote. `services.outcome_for` keeps three kinds of not-knowing apart:
    # `unconfirmed` is *they would not say*, `indeterminate` is *we asked and
    # cannot tell*, `skipped` is **we did not ask**. When we turn a partner
    # away there is no "they" to have said anything — we declined, deliberately
    # and knowingly — so `unconfirmed` was a lie about what we know, and
    # `never_dialled` is the flag that says so. S142 already draws `skipped`
    # neutral for exactly this reason: nothing went wrong, we declined to act.
    return services.finish_run(
        run,
        attempted=0 if refused else rows,
        succeeded=0 if refused else rows,
        failed=0,
        skipped=0,
        confirmed=True,
        never_dialled=refused,
        summary=summary,
        # ⚠ **THE MACHINE-READABLE HALF OF THE REFUSAL (`CR-110-BRC04`).**
        # `summary` is the manager's sentence and `items` is the code — one
        # entry per cause that was true, `{"ref": "KEY_EXPIRED", "detail":
        # "key expired", "outcome": "skipped"}`. It goes in a field the row
        # already has rather than in a new column, because `items` is
        # `BR-INT-040` made storable — *per-item results, never a batch
        # boolean* — and a refused call is exactly one item this run could not
        # do. **No migration.** A support engineer greps `KEY_EXPIRED`; a
        # manager reads the sentence; neither reaches a partner.
        items=list(items),
    )


def record_write(
    *,
    caller: PartnerCaller,
    operation: str,
    rows: int,
    window: str,
    refused: bool = False,
    items: Sequence[Mapping[str, Any]] = (),
    registry: Registry = REGISTRY,
) -> models.IntegrationRun:
    """One partner WRITE → one `inbound` run row (BR-INT-035), 2026-09-24.

    *14:02 · InvoiceCloud (reads from us) · record_payment · Make payment,
    A-10650 INV-2026-00412 142.18 · recorded PMT-2609-000118 · 1 records ·
    page 1 of 1 · ••••7Q2F*.

    ⚠ **A THIN WRAPPER AND NOT A SECOND COMPOSER, DELIBERATELY.** The
    tempting shape was to copy `record_read`'s `start_run`/`finish_run` pair
    and change one argument, which is twenty-five lines that have to be kept
    in step with it for ever — the `skipped`-not-`failed` distinction, the
    `never_dialled` flag S142 reads, the `items` shape a support engineer
    greps. One of those would have drifted. **There is one composer and this
    names the direction it files under.**

    `rows` is 1 for a payment recorded or replayed and 0 for a refusal, which
    is `attempted` in the plan's own vocabulary — the payments HANDED OVER, the
    same meaning the reads give it in the other direction.
    """
    return record_read(
        caller=caller,
        operation=operation,
        rows=rows,
        window=window,
        refused=refused,
        items=items,
        registry=registry,
        direction=models.RUN_DIRECTION_INBOUND,
    )


def refusal_items(causes: Sequence[str]) -> list[dict[str, Any]]:
    """The codes, in the shape `IntegrationRun.items` already stores.

    `skipped` and not `failed`, matching `record_read`'s own note: nothing went
    wrong at the far end, **we declined**. `services.outcome_for` keeps the two
    apart deliberately and S142 draws `skipped` neutral for that reason.
    """
    return [
        {
            "ref": one,
            "detail": CAUSE_TEXT.get(one, one),
            "outcome": adapters_base.ITEM_SKIPPED,
            "provider_text": None,
        }
        for one in causes
    ]


def record_refusal(
    *,
    credential: models.IntegrationCredential | None,
    connection: models.IntegrationConnection | None,
    operation: str | None,
    causes: Sequence[str],
    registry: Registry = REGISTRY,
) -> models.IntegrationRun | None:
    """Write down WHY we turned this caller away — on our side only.

    *"WorldPay refused: key expired, 14 times since 06:00"* is the sentence the
    PO asked to be able to read, and this is where it comes from. The access
    log (S142, `partner_api.access_log`) is `IntegrationRun` filtered to
    `inbound_read`, so a refusal that leaves no run row leaves no trace a
    manager can find.

    ⚠ **FIVE OF THE SIX AUTH CAUSES GET A ROW AND `KEY_UNKNOWN` CANNOT, AND
    THAT IS A FACT ABOUT THE TABLE RATHER THAN A CHOICE MADE HERE.** A run row
    is a row ON A CONNECTION — `IntegrationRun.connection` is a non-null FK and
    the table is partitioned by tenant — and a key we have never seen names no
    connection. There is nothing truthful to attach it to: this surface answers
    for five ERP connectors at once, so picking one would file a stranger's
    knock against a named partner. It goes to the logger instead, with its code,
    and the asymmetry is stated in the ledger row rather than left to be found.
    **The second reason is worth as much as the first:** a row per unknown key
    is a row any stranger can make us write, so a durable record of row 3 is an
    amplifier pointed at our own database. Rows 4–8 all require a key WE
    ISSUED, so their volume is bounded by keys we minted.

    ⚠ **THE WRITE IS INSIDE A SAVEPOINT AND ITS FAILURE IS SWALLOWED, WHICH IS
    CLAUDE.md HARD-WON LAW 14 AND NOT TIDINESS.** On PostgreSQL one failed
    statement aborts the whole transaction, so an insert that raises here would
    take the refusal's own response down with it — a `500` where a `404` was
    owed, which is a louder oracle than any of the eight codes. A nested
    `transaction.atomic()` is a SAVEPOINT and is the only construct that lets
    this continue; `except IntegrityError: pass` alone passes the whole suite on
    SQLite and loses the response on PostgreSQL. **Recording why we refused must
    never change WHETHER we refused.**
    """
    if credential is None or connection is None or operation is None:
        # ⚠ `operation is None` is the published-specification route, which has
        # no declared operation to file a row against — `services.start_run`
        # refuses an operation the manifest does not declare, by design, and
        # inventing one would put a word on a manager's screen that names
        # nothing. The logger below still carries the codes.
        _log_refusal(connection=connection, operation=operation, causes=causes)
        return None

    _log_refusal(connection=connection, operation=operation, causes=causes)
    caller = PartnerCaller(
        connection=connection,
        credential_id=credential.id,
        hint=credential.masked_hint,
        tenant_id=connection.tenant_id,
        scopes=_scopes(credential),
    )
    try:
        with transaction.atomic():
            return record_read(
                caller=caller,
                operation=operation,
                rows=0,
                window=cause_text(causes),
                refused=True,
                items=refusal_items(causes),
                registry=registry,
            )
    except Exception:  # noqa: BLE001 — see the docstring; the refusal outranks its record
        return None


def _log_refusal(
    *,
    connection: models.IntegrationConnection | None,
    operation: str | None,
    causes: Sequence[str],
) -> None:
    """The one line that carries every cause, `KEY_UNKNOWN` included.

    ⚠ **NO KEY, NO HINT, NO SOURCE ADDRESS.** A logger is where a secret goes
    to escape (`rate_limit_store.py` says the same thing about its own), and the
    codes plus the connector are the whole of what a support engineer needs.
    This is a SUPPLEMENT to the run row and never a substitute for it — the
    product's record is the row, because *"a line in a container log nobody is
    tailing"* is the thing this module already refused once.
    """
    logger.info(
        "partner refusal: connector=%s operation=%s causes=%s",
        getattr(connection, "provider_key", None),
        operation,
        ",".join(causes) or SHARED_REFUSAL_CODE,
    )


# ═══════════════════════════════════════════════════════════════════════════
# The payload boundary — BR-INT-054, and it is a deliberate absence
# ═══════════════════════════════════════════════════════════════════════════


def partner_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    """The partner's OWN words for one of our records — Runbooks', not ours.

    Returns `{}` and that is the finished answer for this module.

    `CR-069` §20.4 splits wave S in as many words: integrations KEEPS machine
    authentication, the allowlist, the rate limit, the run row and the register
    row; it MOVES *"what is in the payload — `tenderType` through the mapping
    rows, `projectType`, `accountString` from the ledger codes"*, because
    **building a business record for someone else is outbound ETL**, and
    `BR-INT-054` puts ETL in Runbooks.

    ⚠ This is a **deliberate absence and not a stub** (`OQ-1396`'s distinction):
    it raises nothing, blocks nothing and names no open question, because
    nothing is unruled. A lane finding it should leave it alone. When Runbooks
    lands, this function is where its projection plugs in — and the test named
    below goes red the moment it does, so the boundary cannot close silently.

    The four fields we DO serve — `id`, `paymentDate`, `amount`, `currency` —
    are the record as we hold it, unTRANSFORMED. Handing over a column is
    landing data; deciding that our *Bank transfer* is their `ACHCHECK` is
    interpreting it, and the line falls between those two.
    """
    return {}


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
    """A read is theirs to start. There is no batch for us to run — and unlike
    `record_read()` above, no wave will ever change that."""
    raise NotImplementedError(
        "a partner's read is not work we start; there is no batch to execute"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11); OQ-INT-1481 CLOSED 2026-09-04 option (a), OQ-INT-1480 CLOSED-held
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D✔(partner_api.py mounts three routes) E✔(S142 access log) F✔ G✔ H=pending(HUMAN-REVIEW-PENDING; row in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_041_partner_surface.py · G7 (glob in human_owned.txt, same commit)
# exceptions: `KEY_UNKNOWN` is the one refusal cause with no run row — a run row is a row ON A CONNECTION and an unknown key names none; it is recorded on the logger and the asymmetry is in the ledger row, not inferred. `partner_fields()` returns {} by BR-INT-054 — a deliberate absence owned by Runbooks, not a stub; the rate-limit counter is process-local and says so
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
