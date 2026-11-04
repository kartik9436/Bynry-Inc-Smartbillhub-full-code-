# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-040 (EP-INT-11) — a key we issue, scoped to one tenant,
#           shown once and never again. Screens: S144 · S141 (frame 50.1)
# Rules:    BR-INT-053 (a machine credential is scoped to one tenant, shown
#           once, only replaced; revocation refuses the VERY NEXT call) ·
#           BR-INT-003 (never rendered back — the hint only, after the one
#           display) · BR-INT-043 (`issued_secret` is a declared field kind) ·
#           BR-INT-025 (a credential is versioned, never updated) ·
#           CLAUDE.md hard rule 1 (a key belongs to ONE tenant; RLS FORCE and
#           the tenant_id filter are two guards, not one) · hard rule 7 (mint
#           and revoke each write audit_log, masked)
# Tests:    06-backend/tests/test_us_int_040_issued_key.py (TC-1..7 — the
#           revoke and the two-tenant cases go through wave S's REAL partner
#           route, so the two halves are proved joined rather than separately)
# Impacts:  apps/integrations/services.py (re-exports these — B1: one address
#           for this module's write path) · apps/integrations/api.py (routes
#           19 and 20 of 07-endpoints.md) · apps/integrations/selectors.py
#           (S144's rows) · apps/integrations/runners/serve.py (wave S — this
#           file WRITES the blind index its `resolve_caller()` reads, under the
#           context string declared THERE and imported here)
# ───────────────────────────────────────────────────────
"""The key we ISSUE — minted once, recognised by a blind index, revoked on the spot.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials). HUMAN-REVIEW-PENDING;
the row is in 12-governance/09-human-review-ledger.md and states, in plain
English, the one decision most worth a second opinion: **we do not keep the
key, so nobody here can ever recover it for a partner who loses theirs.**

Every other connector in this product is the utility reaching outward and we
hold somebody else's secret. This is the other direction: `they_hold_ours`,
two connectors of eighteen (`gl_partner`, `payments_kiosk`), where WE mint the
secret and a partner presents it back.

⚠ **THIS FILE MINTS AND REVOKES. IT DOES NOT AUTHENTICATE, AND THE FIRST DRAFT
OF IT DID.** `runners/serve.py` — wave S, 🔒 human-owned — already holds
`resolve_caller()`, live behind three real partner routes, and it is better
than what this file had: no early returns, one `raise`, a timing floor that
equalises the three refusals, and the allowlist folded into the same decision.
Two resolvers would have been two answers to *may this machine read* drifting
apart in silence, which is the one shape a security control must never take.
So the second one was deleted before it was pushed and this file keeps the half
wave S deliberately left to it: **minting, replacing, revoking, and listing**.

THREE SECURITY PROPERTIES, AND WHO KEEPS EACH
----------------------------------------------

**1 · SHOWN ONCE — this file's, and the only copy that ever exists is the
return value of `issue_key()`.**  The row written here carries NO key material
at all: `blind_index` holds an HMAC-SHA256 token (`core.crypto`, keyed by
`key.idx`, which the database does not hold) and `masked_hint` holds four
characters. `payload_enc` carries a marker and no secret, so there is nothing
for a future reader to decrypt and nothing for a log, an audit payload, an
error message or a run record to leak.

⚠ **THAT IS DELIBERATELY STRONGER THAN `US-INT-040` §5, WHICH MAPS THE ISSUED
KEY TO `payload_enc` "encrypted + blind index".**  Encryption is reversible by
design and is the right shape for `we_hold_theirs`, where an adapter must
PRESENT the secret to somebody.  Nothing in this product ever presents this
key — `resolve_caller()` only ever RECOGNISES one, by its blind index — so a
one-way token is the whole requirement and a reversible copy is a liability we
would be choosing to keep.  Recorded in `12-governance/02-decision-log.md`
(2026-09-06); §5 is amended to match rather than silently diverged from.

**2 · REVOCATION REFUSES THE VERY NEXT CALL — shared, and neither half is
enough alone.**  `revoke_key()` below commits one UPDATE; `resolve_caller()`
reads the database on every single call and caches nothing.  Remove either and
the rule breaks while the other still looks correct, which is why the proof is
an end-to-end one: `test_us_int_040_issued_key.py` calls the partner's real
route, revokes, and calls the same route again in the same process.

**3 · THE REFUSAL REVEALS NOTHING — wave S's, entirely.**  See
`runners/serve.py`'s docstring for why `resolve_caller()` has no early return
and why the refusal path is padded to a floor.  Nothing in this file may grow
a second refusal for a partner: everything here is reached by a signed-in
System Admin, whose refusals are ordinary business refusals.

⚠ **ONE STRING TIES THE TWO FILES TOGETHER AND IT IS IMPORTED, NEVER RETYPED.**
`serve.ISSUED_KEY_BLIND_INDEX_CONTEXT` is baked into the HMAC. If the writer
here and the reader there ever spelled it differently, **every valid key would
be refused** — and it would look exactly like a wrong key, in both directions,
because that is what a wrong key looks like. `serve.py`'s own Impacts line asks
this wave to import it, and `test_the_mint_and_the_door_share_one_context`
asserts the two are the same object.

WHAT IS SOMEBODY ELSE'S
------------------------
  * the DRF authentication class `MachineCredentialAuthentication` is
    **identity's** (seam I-9, `03-field-map.md`). It is still unbuilt, and
    wave S did not need it: the three partner routes opt out of the default
    authenticator entirely and call `resolve_caller()` themselves.
  * the door, the allowlist, the rate limit, the `inbound_read` run row, the
    audited grant and the subprocessor register are all **wave S**
    (`US-INT-041`) and all landed on 2026-09-06.
"""

from __future__ import annotations

import json
import secrets as pysecrets
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations import models
from apps.integrations.registry import REGISTRY, Manifest, Registry
from core import audit as core_audit
from core import crypto
from core import errors
from core.permissions import SYSTEM_ADMIN, require_role

#: The auth mode this file serves. `registry.AUTH_MODES` owns the vocabulary;
#: this is DATA read off the manifest, never a branch on `provider_key` (G77).
MODE_THEY_HOLD_OURS = "they_hold_ours"

def crypto_context() -> str:
    """The blind-index context — **wave S's constant, imported, never retyped.**

    ⚠ THE IMPORT IS DEFERRED AND THAT IS A REAL CONSTRAINT, NOT A STYLE CHOICE.
    `runners/serve.py` imports `services`, and `services` imports this module,
    so a module-level `from apps.integrations.runners import serve` here closes
    a cycle Django cannot load. Deferring it costs one function call per mint
    and keeps ONE spelling of the string in the repository — which is the point,
    because if the writer and the reader ever disagreed, every valid key would
    be refused and would look exactly like a wrong key.
    """
    from apps.integrations.runners import serve

    return serve.ISSUED_KEY_BLIND_INDEX_CONTEXT

#: `sbh_live_…` on production, `sbh_test_…` on sandbox (frame 50.1 draws the
#: first). The prefix is not decoration: `BR-INT-026` puts the sandbox /
#: production mix-up at the top of the design's failure list, and a key a
#: partner can read the environment off is one they cannot paste into the
#: wrong config without seeing it.
KEY_PREFIXES = {
    models.ENVIRONMENT_PRODUCTION: "sbh_live_",
    models.ENVIRONMENT_SANDBOX: "sbh_test_",
}

#: 16 bytes → 32 lowercase hex characters → **128 bits**.
#:
#: ⚠ HEX IS NOT AN AESTHETIC CHOICE AND A LATER LANE MUST NOT "IMPROVE" IT TO
#: BASE62. `core.crypto._index_token` normalises through
#: `normalise_identifier()`, which strips non-alphanumerics and UPPER-CASES —
#: so the blind index is case-insensitive. Over a lowercase-hex alphabet that
#: costs exactly nothing (`9f2c` and `9F2C` are the same sixteen values). Over
#: a mixed-case alphabet it would silently fold the alphabet in half and throw
#: away about a fifth of the entropy, with every test still passing.
KEY_BYTES = 16

#: `••••7Q2F` — four characters, and `services._masked` refuses more.
HINT_KEEP = 4

AUDIT_KEY_ISSUED = "integration.key_issued"
AUDIT_KEY_REPLACED = "integration.key_replaced"
AUDIT_KEY_REVOKED = "integration.key_revoked"

#: The two refusals a SYSTEM ADMIN can meet here. A partner never reaches this
#: file, so neither of these is ever seen by a machine — wave S owns that one
#: refusal, and it stays one.
REFUSAL_NOT_A_PARTNER_CONNECTION = "integrations.refusal.not_a_partner_connection"
REFUSAL_NO_KEY_ISSUED = "integrations.refusal.no_key_issued"
#: `CR-110-BRC04` — a key with nothing ticked cannot be issued, and a key that
#: names something this connector does not do cannot be issued either.
#:
#: ⚠ **BOTH REUSE A SENTENCE THE CATALOGUES ALREADY CARRY, AND THAT IS A
#: DECISION RATHER THAN A SHORTCUT.** The obvious move is to mint
#: `integrations.refusal.no_scope` and `…unknown_scope` and write eleven new
#: translations. But *"Check the highlighted fields."* is what this product
#: already says when a form is missing something required, and the Scope box
#: with nothing ticked IS a required field on a form; *"That operation does not
#: exist."* is what it already says about a name that is not one of a
#: connector's operations. Two spellings of one idea is exactly what B14 rule
#: 34 exists to stop, and a new key would also have meant editing all eleven
#: locale catalogues while four front-end lanes are live in them — a shared
#: file, and hard-won law 11's own subject.
#:
#: A later lane that wants a more specific sentence should CHANGE these two
#: constants and write the catalogue lines in the same commit; it must not
#: raise a key no catalogue defines, because the PO suppressed the server's
#: `detail` text on 2026-08-19 and such a refusal reaches a clerk as SILENCE.
REFUSAL_NO_SCOPE = "integrations.refusal.fields"
REFUSAL_UNKNOWN_SCOPE = "integrations.refusal.unknown_operation"


# ── minting ─────────────────────────────────────────────────────────────────


def _mint(environment: str) -> str:
    """A new key. The ONLY place a plaintext key is ever created."""
    prefix = KEY_PREFIXES.get(environment, KEY_PREFIXES[models.ENVIRONMENT_PRODUCTION])
    return prefix + pysecrets.token_hex(KEY_BYTES)


def _hint_for(key: str) -> str:
    return "•" * HINT_KEEP + key[-HINT_KEEP:]


def _marker_payload(field_name: str) -> str:
    """What goes in `payload_enc` for an issued key: a marker, and no secret.

    It is still encrypted at rest — the column's field does that — but there is
    nothing in it worth decrypting, which is the point. `credential_secrets()`
    (the one reader of that column) therefore returns a marker for these rows
    and hands no adapter a key, because no adapter of ours ever presents one.
    """
    return json.dumps({"kind": "issued_secret", "field": field_name})


def _partner_manifest(manifest: Manifest) -> Manifest:
    """A key is issued only where the MANIFEST says we issue one.

    Read off `auth.mode`, which is data (G77 fails a gate that branches on
    `provider_key`); so adding a nineteenth `they_hold_ours` connector adds a
    manifest and touches no line of this file.
    """
    if manifest.auth.mode != MODE_THEY_HOLD_OURS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-053",
            message_key=REFUSAL_NOT_A_PARTNER_CONNECTION,
        )
    return manifest


def issued_key_field(manifest: Manifest) -> Any:
    """The manifest's `issued_secret` field, or None. `BR-INT-043`'s vocabulary
    decides which connectors have a key, not a list kept here."""
    for one in manifest.fields:
        if one.kind == "issued_secret":
            return one
    return None


def callable_operations(manifest: Manifest) -> tuple[str, ...]:
    """The operations a partner holding OUR key may call, in manifest order.

    ⚠ **`they_call_us` AND NOTHING ELSE.** A key we issue is presented AT our
    door; an operation we start against somebody else's API is not something a
    partner's key can name, so offering it in a scope would be a permission
    that cannot be exercised and, worse, one a reviewer would read as though it
    could. `gl_partner` gives three, `payments_kiosk` gives three.
    """
    return tuple(one.name for one in manifest.operations if one.they_call_us)


def _validated_scope(manifest: Manifest, scope: Any) -> list[str]:
    """What this key may call — refused when it is empty or names a stranger.

    ⚠ **BLANK GRANTS NOTHING AND IS REFUSED AT THE MINT (`CR-110-BRC04`
    decision 5).** The blueprint draws *"Leave blank for everything the key
    allows"* under its Scope box — the widest permission as the DEFAULT — and
    that is refused under hard-won law 3: the unsafe option must be the one you
    type. So there are two guards pointing the same way and both are needed:
    this one stops an empty scope being WRITTEN, and `serve.scope_permits`
    stops an empty scope being HONOURED if one ever arrives by another road.

    ⚠ **AN UNKNOWN NAME IS REFUSED RATHER THAN DROPPED**, which is the
    difference between a clerk being told and a clerk being surprised. Silently
    discarding `read_paymets` would issue a key that authorises less than the
    screen said, and the partner would discover it at go-live.

    The result is SORTED and de-duplicated so that two keys granting the same
    three operations store the same list, and a reviewer comparing two rows is
    reading a difference rather than an ordering.
    """
    if isinstance(scope, str) or not isinstance(scope, (list, tuple, set, frozenset)):
        names: list[str] = [] if scope is None else [str(scope)]
    else:
        names = [str(one).strip() for one in scope]
    names = [one for one in names if one]
    if not names:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=REFUSAL_NO_SCOPE,
        )
    allowed = set(callable_operations(manifest))
    unknown = sorted(set(names) - allowed)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_UNKNOWN_SCOPE,
            params={"operation": unknown[0]},
        )
    return sorted(set(names))


def _active_credential(
    connection: models.IntegrationConnection,
) -> models.IntegrationCredential | None:
    return (
        models.IntegrationCredential.objects.filter(
            connection=connection, is_active=True, slot=models.CREDENTIAL_SLOT_PRIMARY
        )
        .order_by("-version")
        .first()
    )


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def issue_key(
    *,
    actor: Any,
    connection: models.IntegrationConnection,
    scope: Any,
    registry: Registry = REGISTRY,
) -> tuple[models.IntegrationCredential, str]:
    """`POST /integrations/{key}/key` — issue or REPLACE. Returns `(row, key)`.

    ⚠ **`scope` IS REQUIRED AND HAS NO DEFAULT (`CR-110-BRC04`).** It names
    which of this connector's operations the key may call, and a key with
    nothing ticked is REFUSED rather than minted as a key that can do nothing
    — the two read the same on a screen and only one of them tells the clerk
    they missed a step. Giving it a default of `()` would have been the same
    mistake as the drawing's *"leave blank for everything"*, arriving from the
    other direction: a caller that forgets it would mint a dead key instead of
    an omnipotent one, and either way nobody is told.

    ⚠ **A REPLACEMENT KEY DOES NOT INHERIT THE OLD ONE'S SCOPE.** Replacing is
    the moment a partner's reach is meant to be reconsidered — that is why the
    scope lives on the credential and not on the connection — so the caller
    says again what the new key may do. v(n) and v(n+1) may legitimately differ,
    and the audit row below records both.

    ⚠ **THE SECOND ELEMENT OF THAT TUPLE IS THE ONLY COPY OF THE KEY THAT WILL
    EVER EXIST.** It is handed to the API layer, which puts it in one response
    body, and it is not written anywhere: not to `payload_enc`, not to the
    audit row, not to a log, not to the run record. If a caller drops it, the
    key is gone and the answer is to issue another one — which is what
    *replace* is.

    REPLACING is `BR-INT-025`'s ordinary versioning and nothing new: v(n) is
    deactivated and v(n+1) written in one transaction, the database's
    one-active guard standing behind it. **The old key stops working at the
    moment this commits**, which is `US-INT-040` TC-4 — a replace is a revoke
    and an issue, not a grace period.
    """
    manifest = _partner_manifest(registry.require(connection.provider_key))
    field = issued_key_field(manifest)
    if field is None:  # a `they_hold_ours` manifest with no `issued_secret` field
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-043",
            message_key=REFUSAL_NOT_A_PARTNER_CONNECTION,
        )
    # ⚠ BEFORE the key is minted. A refusal after `_mint` would have created a
    # secret that exists in this process's memory and in no row — harmless
    # today because nothing logs it, and exactly the kind of window that grows
    # a logger later.
    granted = _validated_scope(manifest, scope)

    key = _mint(connection.environment)
    hint = _hint_for(key)
    previous = _active_credential(connection)

    from apps.integrations import services  # one-way at call time, not import time

    row = services.record_credential(
        actor=actor,
        connection=connection,
        # No key material. `blind_index` is how the key is recognised; this
        # column exists because the model requires a payload and there is
        # nothing secret to put in it (see property 1 in the module docstring).
        payload=_marker_payload(field.name),
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=crypto_context()),
        scope=granted,
        audit_action=None,  # this function writes the one audit row itself
    )
    core_audit.money_action(
        actor,
        AUDIT_KEY_REPLACED if previous is not None else AUDIT_KEY_ISSUED,
        "integration_connection",
        connection.id,
        before=(
            {
                "version": previous.version,
                "masked_hint": previous.masked_hint,
                "scope": previous.scope,
            }
            if previous is not None
            else None
        ),
        after={
            "version": row.version,
            "masked_hint": hint,
            "provider_key": connection.provider_key,
            "environment": connection.environment,
            # ⚠ WHAT THIS KEY MAY CALL IS THE PART AN AUDITOR IS ACTUALLY
            # ASKING ABOUT, and it is not a secret — it is the opposite of one.
            # `BR-INT-003` forbids the KEY in an audit payload; the permissions
            # granted with it are the reason the row exists.
            "scope": granted,
            # The sentence an auditor reads, in a clerk's words, with no rule
            # id and no table name in it (B14 rule 32).
            "summary": (
                f"{previous.masked_hint} → {hint}, for {len(granted)} of "
                f"{len(callable_operations(manifest))}"
                if previous is not None
                else f"{hint} issued, for {len(granted)} of "
                f"{len(callable_operations(manifest))}"
            ),
        },
    )
    return row, key


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def revoke_key(
    *,
    actor: Any,
    connection: models.IntegrationConnection,
    registry: Registry = REGISTRY,
) -> models.IntegrationCredential:
    """`DELETE /integrations/{key}/key` — the partner's VERY NEXT call is refused.

    The row is deactivated, never deleted: S144 lists it *revoked*, with when
    it was issued and when it was last used, which is the question an auditor
    actually asks. `disconnect()` is the other act and it DOES destroy every
    version — that is a connection ending, this is a key ending.

    ⚠ WHAT MAKES THE REFUSAL IMMEDIATE IS NOT THIS FUNCTION, IT IS
    `authenticate()` HOLDING NO CACHE. This one commits a single UPDATE; the
    next call reads the database and finds no active row. Anything that put an
    authorisation decision in memory between the two would break the rule here
    while leaving this code looking correct.
    """
    _partner_manifest(registry.require(connection.provider_key))
    row = _active_credential(connection)
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-053", message_key=REFUSAL_NO_KEY_ISSUED
        )
    now = timezone.now()
    models.IntegrationCredential.objects.filter(pk=row.pk).update(is_active=False, rotated_at=now)
    core_audit.money_action(
        actor,
        AUDIT_KEY_REVOKED,
        "integration_connection",
        connection.id,
        before={"version": row.version, "masked_hint": row.masked_hint, "is_active": True},
        after={
            "version": row.version,
            "masked_hint": row.masked_hint,
            "is_active": False,
            "provider_key": connection.provider_key,
            "summary": f"{row.masked_hint} revoked",
        },
    )
    row.is_active = False
    row.rotated_at = now
    return row


# ── reads ───────────────────────────────────────────────────────────────────


def issued_keys(connection: models.IntegrationConnection) -> list[dict[str, Any]]:
    """S144's rows for one connection — newest first, active and revoked both.

    Hints and dates. `payload_enc` and `blind_index` are not in the `.only()`
    list and are not read: the hint is the display value and a row's id is
    never one (B14 rule 31).

    ⚠ **`last_used_at` IS DERIVED FROM THE ACCESS LOG, NOT STORED — AND THAT IS
    AN AMENDMENT TO `US-INT-040` §5, WHICH MAPS IT TO `config.last_used_at`.**
    Two reasons, and the second is the one that decided it:

      1. Wave S writes an `inbound_read` run for **every page a partner takes**
         (`serve.record_read`), so the fact is already recorded, durably and
         append-only. A second copy on the connection's `config` would be one
         more write on the hot path and one more thing to disagree with.
      2. A stored `config.last_used_at` holds ONE timestamp for the whole
         connection, so a REPLACED key could never say when it was last used —
         its number would have been overwritten by its successor's. Reading the
         runs gives every version an honest answer, because a run is stamped in
         time and each version's window is `created_at → rotated_at`.

    The windows cannot overlap: `record_credential` deactivates v(n) and writes
    v(n+1) in one transaction, so at any instant exactly one key could have been
    presented. `rotated_at` is NULL for the active row, which is the open end of
    the window.
    """
    rows = list(
        models.IntegrationCredential.objects.filter(
            connection=connection, slot=models.CREDENTIAL_SLOT_PRIMARY
        )
        .only("version", "is_active", "masked_hint", "rotated_at", "created_at", "scope")
        .order_by("-version")
    )
    reads = list(
        models.IntegrationRun.objects.filter(
            connection=connection, direction=models.RUN_DIRECTION_INBOUND_READ
        )
        .only("started_at")
        .order_by("-started_at")
    )
    out = []
    for one in rows:
        closed_at = one.rotated_at
        last_used = next(
            (
                run.started_at
                for run in reads  # newest first
                if run.started_at >= one.created_at
                and (closed_at is None or run.started_at <= closed_at)
            ),
            None,
        )
        out.append(
            {
                "version": one.version,
                "hint": one.masked_hint,
                "state": "active" if one.is_active else "revoked",
                "issued_at": one.created_at,
                "revoked_at": None if one.is_active else closed_at,
                "last_used_at": last_used,
                # `CR-110-BRC04` — WHICH OF OUR APIS THIS KEY MAY CALL. Served
                # so S144 can show it; **this is not a secret and it is the
                # question an auditor actually asks of a key.** Operation NAMES
                # rather than ids, because B14 rule 31 forbids a database id
                # being the visible value of a field and because the manifest's
                # own label is what a clerk reads beside it.
                "scope": list(one.scope or []),
            }
        )
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-040@93a5e80 (EP-INT-11) + BR-INT-053 + 07-endpoints.md rows 19–20 + frame 50.1
# generated: 2026-09-06 by the CR-069 wave R build lane
# checklist: A✔ B✔ C✔ D✔(api.py routes 19/20) E✔(MachineKeysPage.tsx S144 + ConnectModal's issued-key panel) F✔ G✔ H=n/a(no 🔒 path — the crypto is core/crypto.py's, already reviewed)
# gates: pytest tests/test_us_int_040_issued_key.py · G77 (no provider_key branch — the mode is read off the manifest) · G15 (the refusal keys in all eleven catalogues) · G33 (the refusal is five words)
# exceptions: `payload_enc` holds a marker rather than the key, and `last_used_at` is derived from the access log rather than stored on `config` — both stronger than US-INT-040 §5 and both recorded in the decision log 2026-09-06 · this file does NOT authenticate: `runners/serve.py::resolve_caller` is the one resolver and this file writes the index it reads
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
