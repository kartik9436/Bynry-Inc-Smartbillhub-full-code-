# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — the five tables; `services.py` is the only
#           write path (B1). US-INT-018 — run rows per operation. US-INT-001 —
#           the grid's connection state. Screens: S8 · S141 · S142
# Rules:    BR-INT-001 (a coming-soon provider is refused at the API, not just
#           by a greyed button) · BR-INT-003 (the secret is never logged, never
#           in an audit payload — masked hint only) · BR-INT-014 (every
#           connection lifecycle event writes audit_log with masked refs) ·
#           BR-INT-018 (`succeeded` only when the arithmetic holds AND the far
#           end confirmed a count; otherwise `unconfirmed`) · BR-INT-025 (a
#           credential is versioned, never updated; one active) · BR-INT-026
#           (production and sandbox are two rows) · BR-INT-037 (an unknown
#           provider key is refused by the registry, not by a branch here) ·
#           BR-INT-039 (a run is append-only once finished) · CLAUDE.md hard
#           rule 7 (every money-adjacent action writes audit_log)
# Tests:    06-backend/tests/test_us_int_014_tables.py ·
#           06-backend/tests/test_us_int_018_operations.py ·
#           06-backend/tests/test_us_int_014_pg.py
# Impacts:  apps/integrations/models.py · selectors.py (reads what this writes)
#           · wave B's api.py writes call these and nothing else
# ───────────────────────────────────────────────────────
"""integrations service layer — the ONLY write path into this module's tables (B1).

WHAT IS HERE IN WAVE A, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------------
Wave A ships the grid that tells the truth: seventeen cards, every one *Not set
up*, because no connection row exists. So this file is a SKELETON with real
guards — enough for the tests to seed a connection, a credential and run rows
the way the product will, and for every rule those rows must obey to be
enforced here rather than remembered:

  * `connect()` — one connection per tenant × provider × environment
    (BR-INT-026; the database's UNIQUE is the second guard). A COMING-SOON
    provider is refused HERE, with `BIZ-STATE` and `BR-INT-001`, so wave B's
    `POST /integrations/{key}/connect` cannot forget to (US-INT-017: the
    refusal is the server's, not the disabled button's). An unknown key is
    refused by the registry, by name, with the list of what exists.
  * `record_credential()` — version n+1, n deactivated, in one transaction;
    the database's EXCLUDE (PostgreSQL) or partial unique index (SQLite) is
    the guard that holds if this code is ever wrong (BR-INT-025). The audit row
    carries the MASKED HINT and never the payload (BR-INT-003).
  * `start_run()` / `finish_run()` — the run record (BR-INT-039). `finish_run`
    applies BR-INT-018's arithmetic ITSELF: a caller states the five counts and
    whether the far end confirmed; it never types the word `succeeded`.
    A finished run refuses a second finish (the trigger is the second guard).

NOT here, on purpose: `test()`, `disconnect()`, `enable()` / `disable()`, the
credential roll-back, the target-reference writer and anything that talks to a
provider — waves B, C, D and E each own one of those and each arrives with its
own story's tests. There is NO writer for `integration_consent` at all
(`OQ-INT-1482` is OPEN; a lane may not decide it by writing a row).

Every write here runs inside the caller's tenant context (BE-01); RLS FORCE
refuses a row stamped for another tenant below this code.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.integrations import key_directory, machine_auth, mappings, models, runtime, scrubbing
from apps.integrations.adapters import base as adapters_base
from apps.integrations.adapters.base import FieldError, TestResult, split_fields, validate_fields
from apps.integrations.registry import (
    MODE_PLATFORM_HOLDS_OURS,
    REGISTRY,
    Manifest,
    Operation,
    Registry,
)
from apps.integrations.seams import notifications as notifications_seam
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: The eight hex characters a clerk reads down the phone (BR-INT-039).
TRACE_ID_HEX = 8

#: How many UNSUCCESSFUL items a run stores (wave C, US-INT-020). A run keeps
#: the items it could not do, never the ones it could — see migration 0003 for
#: the arithmetic that decided a column instead of a table. Two hundred is the
#: point past which a clerk stops reading a list and starts wanting a file, and
#: the artifact is where that belongs; what the cap left out is stated on the
#: screen in words rather than silently dropped.
ITEM_CAP = 200

# Wave D (US-INT-037): the target-reference writers live in `mappings.py` and
# are reachable from here so this file stays the module's one write path (B1).
set_mappings = mappings.set_rows
record_unknown_value = mappings.record_unknown

# Wave E (US-INT-026): the two callables `apps/notifications/provider_seam.py`
# resolves BY NAME on this module — the dispatcher's hand-off and the
# connection-status read it has been asking for since 2026-08-15 and getting
# `None` from. They are DEFINED in `seams/notifications.py`, beside the read
# that goes the other way, and re-exported here because the neighbour's
# address is `apps.integrations.services.<name>` and moving that address is a
# change to somebody else's file for no reason (DEF-075's rule).
dispatch_outbound_batch = notifications_seam.dispatch_outbound_batch
provider_connection_status = notifications_seam.provider_connection_status
sending_ceiling = notifications_seam.sending_ceiling  # CR-198-BRC10 — one hand-off ≤ the provider's minute
# Lane SETTINGS-MOVE (2026-10-22): the mail server notifications SHOWS, read-only.
email_sender_status = notifications_seam.email_sender_status


def _manifest(provider_key: str, registry: Registry) -> Manifest:
    """The registry refuses an unknown key by name, with the list of what exists."""
    return registry.require(provider_key)


def _masked(hint: str | None) -> str:
    """A hint is display material; it must never be the secret. Refuse a hint
    longer than the last four characters plus the mask, so a caller cannot
    smuggle the payload through the one column a screen reads."""
    if not hint or len(hint.replace("•", "")) > 4:
        raise ValueError("masked_hint must be the mask plus at most four characters (BR-INT-003)")
    return hint


# ── connections ─────────────────────────────────────────────────────────────


@require_role(SYSTEM_ADMIN)
def connect(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    environment: str,
    label: str | None = None,
    config: dict[str, Any] | None = None,
    cadence: str = models.CADENCE_MANUAL,
    registry: Registry = REGISTRY,
) -> models.IntegrationConnection:
    """Create the connection row — status `untested` until `test()` (wave B) runs.

    Refuses a coming-soon provider (BR-INT-001), an unknown environment or
    cadence, and any SECRET-kind field arriving in `config` — a password in the
    non-secret column would be the leak the two-table split exists to prevent.
    """
    manifest = _manifest(provider_key, registry)
    if manifest.disposition.coming_soon:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-001",
            message_key="integrations.refusal.not_available",
            params={"provider": manifest.display_name, "wave": manifest.disposition.wave},
        )
    if environment not in models.ENVIRONMENTS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="integrations.refusal.environment",
            params={"environment": environment},
        )
    if cadence not in models.CADENCES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="integrations.refusal.cadence",
            params={"cadence": cadence},
        )
    config = dict(config or {})
    secret_names = {one.name for one in manifest.fields if one.is_secret}
    leaked = sorted(secret_names & set(config))
    if leaked:
        raise ValueError(
            f"{leaked} are secret fields and may not be written to integration_connection.config "
            "(BR-INT-003) — use record_credential()"
        )
    row = models.IntegrationConnection.objects.create(
        tenant_id=tenant_id,
        provider_key=provider_key,
        label=label,
        environment=environment,
        status=models.STATUS_UNTESTED,
        enabled=True,
        cadence=cadence,
        next_run_at=None,
        config=config,
        connected_by_id=getattr(actor, "id", None),
        connected_at=timezone.now(),
    )
    ensure_rate_limits(row, registry=registry)
    core_audit.money_action(
        actor,
        "integration.connected",  # US-INT-004 TC-1 names the four lifecycle rows
        "integration_connection",
        row.id,
        after={
            "provider_key": provider_key,
            "environment": environment,
            "label": label,
            "cadence": cadence,
            # config is NON-SECRET by construction (guarded above), so it may
            # travel in the audit payload — that is the point of the split.
            "config": config,
        },
    )
    return row


def ensure_rate_limits(
    connection: models.IntegrationConnection,
    *,
    registry: Registry = REGISTRY,
) -> int:
    """Seed one call-limit row per operation on this connection. Returns how many it wrote.

    `CR-110-BRC04`, PO 2026-09-16: *"keep the limit in database so if we want
    to change it later it is easy to do"*. The manifest carries the DEFAULT and
    provisioning copies it in — the blueprint's p017 split, because a quota is
    a fact about one utility's agreement and a manifest is shared by every
    tenant.

    ⚠ **IDEMPOTENT, AND THE `IntegrityError` ARM IS A SAVEPOINT RATHER THAN A
    BARE `except` — CLAUDE.md hard-won law 14, and this comment is the thing
    that stops the next lane simplifying it away.** On PostgreSQL a failed
    statement ABORTS THE WHOLE TRANSACTION: every later query raises
    `InFailedSqlTransaction` and the work is lost at COMMIT, so
    `try: create() except IntegrityError: continue` skips the duplicate row and
    then silently discards the connection row, the audit row and everything
    else in flight. **A nested `transaction.atomic()` is not the tidy option,
    it is the ONLY option.** And the trap is invisible here: the suite runs on
    SQLite (`config/settings/test.py` hardcodes it), SQLite has no
    aborted-transaction state, and the broken version passes every test on
    every machine. `tests/test_cr110_rate_limits_pg.py` proves this arm against
    a real PostgreSQL, which is the only place it can be proved.

    ⚠ **IT IS CALLED INSIDE `connect()`'s TRANSACTION**, so a connection made
    without its limits is not a state this product can reach. A connection with
    no rows would not be unlimited — `serve.rate_limit_for` falls back to the
    default ceiling — but it would be a connection whose limits nobody can see
    or change, which is the thing the PO ruled into the database.
    """
    from apps.integrations.runners.serve import DEFAULT_RATE_LIMIT_PER_MINUTE

    manifest = registry.get(connection.provider_key)
    if manifest is None:  # pragma: no cover — `connect()` validated it already
        return 0
    written = 0
    for operation in manifest.operations:
        try:
            with transaction.atomic():
                models.IntegrationRateLimit.objects.create(
                    tenant_id=connection.tenant_id,
                    connection=connection,
                    operation=operation.name,
                    calls_per_minute=(
                        operation.rate_limit_per_minute or DEFAULT_RATE_LIMIT_PER_MINUTE
                    ),
                )
            written += 1
        except IntegrityError:
            # The row is already there — a re-provision, or two lanes seeding
            # one connection. Its VALUE is deliberately left alone: a utility
            # that bought a bigger quota must not have it reset to the
            # manifest's default by a housekeeping call.
            continue
    return written


# ── credentials ─────────────────────────────────────────────────────────────

#: The "caller said nothing" sentinel for `record_credential(audit_action=…)`.
#: It is NOT `None`, because `None` is a meaningful value there — it means
#: *write no row, I am writing my own*.
_AUDIT_DEFAULT = object()


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def record_credential(
    *,
    actor: Any,
    connection: models.IntegrationConnection,
    payload: str,
    masked_hint: str,
    expires_at: datetime | None = None,
    blind_index: str | None = None,
    scope: Sequence[str] | None = None,
    audit_action: str | None | object = _AUDIT_DEFAULT,
    slot: str = models.CREDENTIAL_SLOT_PRIMARY,
) -> models.IntegrationCredential:
    """Write version n+1 and deactivate n — never update in place (BR-INT-025).

    ⚠ `slot` (CR-173-BRC10) — n is the active credential IN THIS SLOT. The
    version number is still counted across the whole connection, so
    `uq_integration_credential_version` holds and the history reads in one
    order; deactivation is per slot, so storing New World's SFTP password does
    not revoke the key we issued the City (migration `0015`).

    The payload goes through `EncryptedTextField` on the way in; nothing here
    reads it back. The audit row carries the masked hint and the version
    number, never the payload (BR-INT-003).

    ⚠ `scope` IS FOR ISSUED KEYS ONLY AND DEFAULTS TO *NOTHING GRANTED*
    (`CR-110-BRC04`). Ten of the twelve connectors hold somebody else's secret,
    which authorises nothing at OUR door, so `None` here writes `[]` and that
    is correct rather than a gap: a stored vendor password that somehow reached
    `serve.resolve_caller` would be refused by the scope guard, which is the
    safe direction. `machine_auth.issue_key` is the one caller that passes a
    real list, and it validates it against the manifest first.

    ⚠ `audit_action=None` SUPPRESSES THE ROW THIS FUNCTION WRITES, and it has
    exactly one caller: `machine_auth.issue_key`, which writes its own
    `integration.key_issued` / `key_replaced` row instead (wave R, 2026-09-06).
    Two rows for one act is not "more audit", it is an auditor reading the same
    event twice and having to work out that it is one — and a key we ISSUE is
    a different event from a password we STORE, so it gets its own word rather
    than a second copy of this one. The sentinel default keeps every existing
    caller on the behaviour it had; passing `None` is a deliberate act, and
    hard rule 7 is satisfied by the row the caller writes, never by silence.
    """
    hint = _masked(masked_hint)
    current = (
        models.IntegrationCredential.objects.filter(
            connection=connection, is_active=True, slot=slot
        )
        .order_by("-version")
        .first()
    )
    next_version = (
        models.IntegrationCredential.objects.filter(connection=connection)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    now = timezone.now()
    if current is not None:
        # Deactivate FIRST, in the same transaction: the database's one-active
        # guard would refuse the insert otherwise, which is the point of it.
        models.IntegrationCredential.objects.filter(pk=current.pk).update(
            is_active=False, rotated_at=now
        )
    row = models.IntegrationCredential.objects.create(
        tenant_id=connection.tenant_id,
        connection=connection,
        version=next_version,
        is_active=True,
        slot=slot,
        payload_enc=payload,
        blind_index=blind_index,
        masked_hint=hint,
        expires_at=expires_at,
        scope=list(scope or []),
    )
    # ⚠ **AN ISSUED KEY HAS TO BE FINDABLE BEFORE A UTILITY IS OPEN, AND THIS IS
    # THE ONE LINE THAT MAKES IT SO (`DEF-INT-5546`, 2026-09-16).** The five
    # partner addresses carry no `{utility}` segment since the PO's ruling of
    # that date, so a request arrives with a key and nothing else;
    # `integration_key_directory` is the only table readable at that moment (it
    # is not a tenant table — migration `0011` carries the argument), and this
    # writes its row.
    #
    # ⚠ **HERE AND NOT IN `machine_auth.issue_key`, WHICH IS WHERE THE FIRST
    # DRAFT PUT IT.** This function is the ONE write path for a credential (B1),
    # so a directory row exists for every issued key BY CONSTRUCTION rather than
    # because the minting path remembered. `key_directory.record` skips a
    # credential with no blind index, which is the ten connectors that hold
    # somebody ELSE's secret — those authorise nothing at our door and have
    # nothing to resolve.
    #
    # A key that existed with no directory row would be refused at every call,
    # and refused in exactly the way a WRONG key is — five words, one code, no
    # diagnosis — so the failure would be silent in both directions. That is the
    # same trap `ISSUED_KEY_BLIND_INDEX_CONTEXT` carries a warning about two
    # files away, and it is why this is not left to a caller.
    key_directory.record(row)
    if audit_action is None:
        return row  # the caller writes the one audit row for this act — see above
    core_audit.money_action(
        actor,
        (
            (AUDIT_CREDENTIAL_ROTATED if current is not None else "integration.credential.record")
            if audit_action is _AUDIT_DEFAULT
            else str(audit_action)
        ),
        "integration_connection",
        connection.id,
        before=(
            {"version": current.version, "masked_hint": current.masked_hint} if current else None
        ),
        after=(
            {
                "version": next_version,
                "masked_hint": hint,
                "expires_at": expires_at,
                # US-INT-024 TC-1: `••••3F9A → ••••A17C` AND NOTHING ELSE. The
                # arrow is the whole readable content of a rotation row, and
                # both sides are masks — the payload is not in this function's
                # audit call at all, so there is nothing to forget to strip.
                "hints": f"{current.masked_hint} → {hint}",
            }
            if current is not None
            else {"version": next_version, "masked_hint": hint, "expires_at": expires_at}
        ),
    )
    return row


# ── runs ────────────────────────────────────────────────────────────────────


def start_run(
    *,
    connection: models.IntegrationConnection,
    operation: str,
    direction: str,
    trigger: str,
    job_id: Any = None,
    input_hash: str | None = None,
    request_key: str | None = None,
    registry: Registry = REGISTRY,
) -> models.IntegrationRun:
    """Open a run row with a fresh trace id. The operation must be one the
    provider's manifest declares — a run against an operation nobody declared
    is a row no screen can place.

    ⚠ `input_hash` IS AN ARGUMENT HERE, AND NOT ONLY ON `finish_run`, BECAUSE
    OF WHAT IT IS FOR (`BR-INT-020` C, `CR-069` wave I). For a file arriving,
    the hash is of the BYTES AS THEY ARRIVED and is computed BEFORE anything
    parses them. A hash that could only be written when the run closes would
    be a hash of a file we had already read, and the duplicate refusal — which
    has to happen before any parse work is spent — would have nothing to match
    against. Writing it at OPEN is what makes the ordering a fact about the
    row rather than a claim in a comment (hard-won law 1).

    ⚠ `request_key` IS THE SAME ARGUMENT RUNNING THE OTHER WAY (`BR-INT-020`,
    `BR-INT-050`, `CR-069` wave K). For an operation that CHANGES THE PARTNER'S
    STATE — Neptune's export carries `CloseOnExport` and closes billing routes
    on their side — the key is minted and written **before the request leaves**,
    so a retry after a timeout finds it and refuses rather than closing the
    routes a second time. A key written when the call RETURNS would not exist
    during the one window where a retry is most likely, which is exactly the
    moment the far end went quiet."""
    manifest = _manifest(connection.provider_key, registry)
    if operation not in {one.name for one in manifest.operations}:
        raise ValueError(
            f"{connection.provider_key} declares no operation {operation!r}; "
            f"declared: {[one.name for one in manifest.operations]}"
        )
    if direction not in models.RUN_DIRECTIONS:
        raise ValueError(f"direction {direction!r} is not one of {list(models.RUN_DIRECTIONS)}")
    if trigger not in models.RUN_TRIGGERS:
        raise ValueError(f"trigger {trigger!r} is not one of {list(models.RUN_TRIGGERS)}")
    return models.IntegrationRun.objects.create(
        tenant_id=connection.tenant_id,
        connection=connection,
        operation=operation,
        job_id=job_id,
        direction=direction,
        trigger=trigger,
        outcome=models.OUTCOME_RUNNING,
        input_hash=input_hash,
        request_key=request_key,
        trace_id=secrets.token_hex(TRACE_ID_HEX // 2).upper(),
    )


def outcome_for(
    *,
    attempted: int,
    succeeded: int,
    failed: int,
    skipped: int,
    confirmed: bool,
    indeterminate: bool = False,
    never_dialled: bool = False,
) -> str:
    """BR-INT-018 as arithmetic — the one place the outcome word is chosen.

    `succeeded` only when attempted = succeeded + failed + skipped AND the far
    end confirmed a count. A provider that returned 200 and would not say how
    many it accepted has not succeeded; it has left us unable to say —
    `unconfirmed`, never rounded down to `failed`. `indeterminate` is the third
    outcome of a call that timed out (BR-INT-052): *we do not know*.

    ⚠ **`never_dialled` IS TESTED FIRST AND IT HAD TO BE ADDED (`CR-069` wave
    F, `BR-INT-024`).** A run the breaker refused to place has `failed = 0`, so
    every clause below it says `succeeded` — the arithmetic is right and the
    word is a lie, because nothing was sent. It is a THIRD kind of not-knowing
    and the three are worth keeping apart: `unconfirmed` is *they would not
    say*, `indeterminate` is *we asked and cannot tell*, `skipped` is **we did
    not ask**. Only the last one has an action attached to it.
    """
    if never_dialled:
        return models.OUTCOME_SKIPPED
    if indeterminate:
        return models.OUTCOME_INDETERMINATE
    if not confirmed or attempted != succeeded + failed + skipped:
        return models.OUTCOME_UNCONFIRMED
    if failed == 0:
        return models.OUTCOME_SUCCEEDED
    if succeeded == 0 and skipped == 0:
        return models.OUTCOME_FAILED
    return models.OUTCOME_PARTIAL


#: `finish_run(input_hash=...)`'s "not supplied" marker. It cannot be `None`,
#: because `None` is a MEANINGFUL value for that column (a run with no file in
#: it) and because every caller that omits the argument would otherwise erase a
#: hash `start_run` wrote at open — silently, on the one column whose whole
#: purpose is to still be there on the next arrival (`CR-069` wave I).
KEEP = object()


def finish_run(
    run: models.IntegrationRun,
    *,
    attempted: int,
    succeeded: int,
    failed: int,
    skipped: int,
    confirmed: bool,
    changed: int = 0,
    summary: str | None = None,
    provider_error: str | None = None,
    input_hash: Any = KEEP,
    artifact_link: str | None = None,
    indeterminate: bool = False,
    never_dialled: bool = False,
    items: Any = (),
) -> models.IntegrationRun:
    """Close the run with its five counts. The outcome is COMPUTED (BR-INT-018).

    Refuses to finish a run twice: once `finished_at` is set the row is
    append-only (BR-INT-039); on PostgreSQL the trigger refuses below this too.

    `items` is the adapter's per-item results (`RunResult.items`, or plain
    mappings of the same shape). **Only the ones that did not succeed are
    stored** — the seven addresses a clerk has to go and fix — capped at
    `ITEM_CAP`; see `models.IntegrationRun.items` and migration 0003.

    ⚠ EVERY PROVIDER STRING THAT ARRIVES HERE IS SCRUBBED AT THIS LINE, NOT AT
    THE ADAPTER'S GOOD INTENTIONS. `US-INT-020` §1 puts the scrub in the
    adapter, and that is where the provider-specific knowledge belongs; but a
    guarantee that depends on nineteen adapters each remembering is hard-won
    law 1 — a comment claiming a guarantee is not the guarantee. `scrub` is
    idempotent, so an adapter that already scrubbed loses nothing and one that
    forgot is still caught.
    """
    if run.finished_at is not None:
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-INT-039",
            message_key="integrations.refusal.run_finished",
        )
    for name, value in (
        ("attempted", attempted),
        ("succeeded", succeeded),
        ("failed", failed),
        ("skipped", skipped),
        ("changed", changed),
    ):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
    run.attempted = attempted
    run.succeeded = succeeded
    run.failed = failed
    run.skipped = skipped
    run.changed = changed
    run.outcome = outcome_for(
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        confirmed=confirmed,
        indeterminate=indeterminate,
        never_dialled=never_dialled,
    )
    run.summary = summary
    run.provider_error = scrub(provider_error)
    # ⚠ NOT `run.input_hash = input_hash`. A file's hash is written by
    # `start_run` BEFORE the bytes are parsed (`BR-INT-020` C), and this
    # function is called by five runners that know nothing about files. With a
    # `None` default, every one of them would blank the column at close and the
    # NEXT arrival of the same file would find nothing to match — a duplicate
    # refusal that cannot fire, passing every test, on the one guarantee this
    # wave exists to give (hard-won law 7: ask what makes a check pass wrongly).
    if input_hash is not KEEP:
        run.input_hash = input_hash
    run.artifact_link = artifact_link
    run.items = unsuccessful_items(items)
    run.finished_at = timezone.now()
    fields = [
            "attempted",
            "succeeded",
            "failed",
            "skipped",
            "changed",
            "outcome",
            "summary",
            "provider_error",
            "artifact_link",
            "items",
            "finished_at",
        ]
    if input_hash is not KEEP:
        fields.append("input_hash")
    run.save(update_fields=fields)
    _first_partner_call_is_the_test(run)
    return run


def _first_partner_call_is_the_test(run: models.IntegrationRun) -> None:
    """`DEF-INT-10018` — a partner's first SUCCESSFUL call moves `untested` to `working`.

    A *they call us* connector cannot be tested from our side — its own page
    says *"Cannot be tested until first use"* — so `connection.status` stayed
    `untested` for ever and the header read *Not tested yet* over three APIs
    reading *Working* (walk 2026-10-07, USPayments).

    ⚠ **THE CONNECTOR'S OWN FACT, NOT AN AGGREGATE OF ITS APIs.** `display_state`
    still reads `connection.status` and nothing else (`DEF-INT-5597`, PO: *"it
    should be for conenctor not for APis"*). This moves that column once, on the
    first call from THIS partner to THIS utility that worked — which is what a
    test of an inbound connector would have proved. Only `untested` moves: a
    connector somebody tested, turned off or saw fail is never re-judged here
    (that is `DEF-INT-5598`'s open question, not this one). A refused call
    proves nothing and moves nothing.
    """
    if run.trigger != "partner" or run.outcome != models.OUTCOME_SUCCEEDED:
        return
    models.IntegrationConnection.objects.filter(
        pk=run.connection_id, status=models.STATUS_UNTESTED
    ).update(status=models.STATUS_WORKING, updated_at=timezone.now())


def unsuccessful_items(items: Any) -> list[dict[str, Any]]:
    """The items a run could NOT do, in storable form (BR-INT-040).

    Accepts `ItemResult`s or plain mappings of the same shape, keeps `failed`
    and `skipped`, drops `succeeded`, scrubs every provider string, and stops
    at `ITEM_CAP`. An item whose outcome is a word this product does not know
    is KEPT rather than dropped — an unrecognised outcome is exactly the thing
    a clerk needs to see, and silently discarding it would be the batch boolean
    BR-INT-040 exists to forbid, wearing a filter.
    """
    kept: list[dict[str, Any]] = []
    for one in items or ():
        outcome = str(_item_field(one, "outcome") or "")
        if outcome == adapters_base.ITEM_SUCCEEDED:
            continue
        if len(kept) >= ITEM_CAP:
            break
        kept.append(
            {
                "ref": _text_or_none(_item_field(one, "ref")),
                "detail": _text_or_none(_item_field(one, "detail")),
                "outcome": outcome or adapters_base.ITEM_FAILED,
                "provider_text": scrub(_text_or_none(_item_field(one, "provider_text"))),
            }
        )
    return kept


def _item_field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ═════════════════════════════════════════════════════════════════════════════
# WAVE B — the write path a clerk reaches: validate, then write, and NOTHING
# on a refusal (US-INT-002 · 017 · 019 · 004 · 016)
# ═════════════════════════════════════════════════════════════════════════════
#
# THE ORDER IS THE RULE. Every entry point below does, in this order:
#   1  the manifest — unknown → 404 identical to any absent resource;
#      coming-soon → refused BEFORE anything else is read, with an audit row
#      that carries the key and the wave and NO payload (BR-INT-001, US-INT-017
#      TC-6). A disabled button is a convenience; this is the refusal.
#   2  the adapter — a LIVE provider with no adapter bound is refused too
#      (*Cannot be connected yet.*): the product may not store a real
#      credential before `core/crypto.py`'s sign-off, and the first adapter
#      arrives with that sign-off (execution plan E1/E4).
#   3  the shape — `validate_fields` (the manifest's) then `adapter.validate()`
#      (the provider's), BOTH before `transaction.atomic()` opens. A malformed
#      connect stores nothing — not the connection, not a partial credential.
#   4  the write, in one transaction; the UNIQUE race caught OUTSIDE it
#      (hard-won law 14 — a refused statement inside the block would poison
#      the PostgreSQL transaction, and SQLite would never show it).
#
# THE ONE PLACE `payload_enc` IS READ is `credential_secrets()`; a grep for
# it finds one caller per runner and nothing else (BR-INT-003).

#: The refusal sentences below are catalogue keys in all eleven languages
#: (G32 baseline 0), each ≤ 6 words (B14 rule 33).
REFUSAL_NOT_AVAILABLE = "integrations.refusal.not_available"  # coming soon
REFUSAL_PLATFORM_PROVIDED = "integrations.refusal.platform_provided"  # CR-198-BRC10
REFUSAL_NOT_CONNECTABLE = "integrations.refusal.not_connectable"  # live, no adapter yet
REFUSAL_NO_ADAPTER = "integrations.refusal.no_adapter"  # test/run on a live key with no adapter
REFUSAL_ALREADY_CONNECTED = "integrations.refusal.already_connected"
REFUSAL_NOT_CONNECTED = "integrations.refusal.not_connected"
REFUSAL_NO_TEST_ACTION = "integrations.refusal.no_test_action"  # BR-INT-019
REFUSAL_RECIPIENT_NEEDED = "integrations.refusal.recipient_needed"  # BR-INT-026
REFUSAL_SANDBOX_ONLY = "integrations.refusal.sandbox_only"  # BR-INT-026
REFUSAL_NO_WORKER = "integrations.refusal.no_worker"  # BR-INT-041 / DEF-2487
REFUSAL_RUN_IN_FLIGHT = "integrations.refusal.run_in_flight"
#: `CR-174-BRC10` — a connector whose vocabulary names a FALLBACK word may not
#: be switched on while that word points at nothing of ours.
REFUSAL_FALLBACK_UNMAPPED = "integrations.refusal.fallback_unmapped"
REFUSAL_NOT_OURS_TO_START = "integrations.refusal.not_ours_to_start"
REFUSAL_UNKNOWN_OPERATION = "integrations.refusal.unknown_operation"
REFUSAL_UNKNOWN_FIELD = "integrations.refusal.unknown_field"
REFUSAL_FIELDS = "integrations.refusal.fields"
# ⚠ `REFUSAL_OAUTH_NOT_AVAILABLE` WAS HERE AND IS GONE (wave H, 2026-09-06).
# Its sentence read *"Sign-in arrives in a later release."*, which stopped
# being true the moment this wave landed the round trip. A refusal that has
# quietly become false is hard-won law 1, and leaving the constant would have
# left the next lane a ready-made way to raise it again. The eleven catalogue
# entries stay: nothing can reach them now, and deleting a key from eleven
# shared JSON files is a whole-file rewrite for no gain (law 11).
#: Wave I (US-INT-033) — the two file-arrival refusals, ≤ 6 words each.
REFUSAL_FILE_REQUIRED = "integrations.refusal.file_required"
REFUSAL_FILE_EMPTY = "integrations.refusal.file_empty"
#: Wave E (US-INT-024 TC-4 · TC-5) — the two roll-back refusals, ≤ 6 words each.
REFUSAL_NOTHING_TO_ROLL_BACK = "integrations.refusal.nothing_to_roll_back"
REFUSAL_PREVIOUS_EXPIRED = "integrations.refusal.previous_expired"

#: Audit actions — the lifecycle rows US-INT-004 TC-1 names, plus the refusal.
AUDIT_CONNECT_REFUSED = "integration.connect_refused"
AUDIT_REFUSED = "integration.refused"
AUDIT_TEST_RUN = "integration.test_run"
AUDIT_UPDATED = "integration.updated"
AUDIT_DISCONNECTED = "integration.disconnected"
#: Wave E. `integration.credential.record` (wave A) stays the word for writing
#: the FIRST version — nothing was replaced, so nothing rotated. Replacing one
#: is a different event with a real before-and-after, and it gets its own name
#: (US-INT-024 TC-1 · TC-2).
AUDIT_CREDENTIAL_ROTATED = "integration.credential_rotated"
AUDIT_CREDENTIAL_ROLLED_BACK = "integration.credential_rolled_back"
#: Wave I. An arrival is a lifecycle event of the CONNECTION — *a file landed
#: here* — and not a statement about what was in it (BR-INT-054).
AUDIT_FILE_ARRIVED = "integration.file_arrived"
AUDIT_FILE_REFUSED = "integration.file_refused_duplicate"
#: Wave J, the mirror. A departure is a lifecycle event of the CONNECTION —
#: *this period was asked for here* — and not a statement about the figures
#: inside it (BR-INT-054, CR-069 §20.4).
AUDIT_PERIOD_EXPORTED = "integration.period_exported"
AUDIT_PERIOD_REFUSED = "integration.period_refused_duplicate"


def scrub(text: str | None) -> str | None:
    """Provider text before it is stored — THE one seam, and it now masks.

    Wave C (US-INT-020) landed the rule in `apps/integrations/scrubbing.py`:
    an email address, an account-number-shaped token, a street address and the
    place name after it, and a post-office box each become `••••`; the
    provider's status code and their own sentence survive whole, because that
    string is the entire reason support asks for this column.

    ⚠ IT IS A REDUCTION, NOT A GUARANTEE — a provider can put a customer's
    NAME in a message and no pattern catches it. The two guarantees that do
    not depend on a regular expression are that `provider_error` is never in a
    list payload, an audit row or a notification, and that it is rendered on
    one screen to the owning tenant only. Both are asserted in
    `tests/test_us_int_020_runs.py`; neither is this function's doing.
    """
    return scrubbing.scrub(text)


def _refuse_by_disposition(actor: Any, manifest: Manifest, *, route: str) -> None:
    """A coming-soon provider is refused at the API, not only by the button
    (BR-INT-001). The audit row is a lifecycle event (BR-INT-014) and carries
    the key and the wave — no field, no payload (US-INT-017 TC-6)."""
    if not manifest.disposition.coming_soon:
        return
    core_audit.money_action(
        actor,
        AUDIT_CONNECT_REFUSED if route == "connect" else AUDIT_REFUSED,
        "integration_connection",
        None,
        after={"provider_key": manifest.key, "wave": manifest.disposition.wave, "route": route},
    )
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-INT-001",
        message_key=REFUSAL_NOT_AVAILABLE,
        params={"provider": manifest.display_name, "wave": manifest.disposition.wave},
    )


def _live_manifest(actor: Any, provider_key: str, *, route: str, registry: Registry) -> Manifest:
    """Step 1 of every write: unknown → 404 identical to absent; coming-soon →
    refused with its audit row; otherwise the manifest."""
    manifest = registry.get(provider_key)
    if manifest is None:
        raise errors.NotFoundError()
    _refuse_by_disposition(actor, manifest, route=route)
    return manifest


def _adapter_or_refuse(actor: Any, manifest: Manifest, *, route: str, registry: Registry) -> type:
    """Step 2: a LIVE provider whose adapter has not arrived is refused too."""
    adapter_cls = registry.adapter_for(manifest.key)
    if adapter_cls is None:
        core_audit.money_action(
            actor,
            AUDIT_CONNECT_REFUSED if route == "connect" else AUDIT_REFUSED,
            "integration_connection",
            None,
            after={"provider_key": manifest.key, "wave": None, "route": route, "reason": "no adapter"},
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-037",
            message_key=REFUSAL_NOT_CONNECTABLE if route == "connect" else REFUSAL_NO_ADAPTER,
            params={"provider": manifest.display_name},
        )
    return adapter_cls


def _has_active_credential(connection: models.IntegrationConnection) -> bool:
    return models.IntegrationCredential.objects.filter(connection=connection, is_active=True).exists()


def connection_for(tenant_id: Any, provider_key: str) -> models.IntegrationConnection | None:
    """The row a write route acts on: production first, else the only row."""
    rows = list(
        models.IntegrationConnection.objects.filter(tenant_id=tenant_id, provider_key=provider_key)
    )
    rows.sort(key=lambda one: 0 if one.environment == models.ENVIRONMENT_PRODUCTION else 1)
    return rows[0] if rows else None


def _connected_or_refuse(tenant_id: Any, provider_key: str) -> models.IntegrationConnection:
    row = connection_for(tenant_id, provider_key)
    if row is None or not row.enabled:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-002", message_key=REFUSAL_NOT_CONNECTED
        )
    return row


def ungrouped(manifest: Manifest, values: dict[str, Any]) -> dict[str, Any]:
    """`values` without the fields a named group owns (CR-173-BRC10)."""
    grouped = {one.name for one in manifest.fields if one.group}
    return {name: value for name, value in dict(values or {}).items() if name not in grouped}


def _hint(secrets: dict[str, str]) -> str:
    """`••••3F9A` — the last four characters of the FIRST secret, display only.
    `_masked()` refuses anything longer, so the payload cannot ride the hint."""
    value = next(iter(secrets.values()))
    return "••••" + value[-4:]


def _field_refusal(problems: list) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=REFUSAL_FIELDS,
        field_errors=[one.envelope() for one in problems],
    )


@require_role(SYSTEM_ADMIN)
def connect_with_fields(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    environment: str,
    cadence: str,
    label: str | None,
    fields: dict[str, Any],
    registry: Registry = REGISTRY,
) -> models.IntegrationConnection:
    """`POST /integrations/{key}/connect` — the modal's one mapping, split by
    the manifest, validated, then written in one transaction.

    Returns the connection row with credential v1 recorded (when the manifest
    declares a secret). A REFUSAL AT ANY STEP WRITES NOTHING — the tests read
    the row counts back (US-INT-017 TC-1 · TC-4).
    """
    manifest = _live_manifest(actor, provider_key, route="connect", registry=registry)
    # ⚠ `CR-198-BRC10` — A PROVIDER THE PLATFORM HOLDS IS NEVER CONNECTED BY A
    # UTILITY. Its credential is a server secret (`platform_sms.py`); a
    # connection row here would invite a clerk to type our Twilio token into a
    # tenant table. Refused BEFORE anything is read or written, by name.
    if manifest.auth.mode == MODE_PLATFORM_HOLDS_OURS:
        core_audit.money_action(
            actor,
            AUDIT_CONNECT_REFUSED,
            "integration_connection",
            None,
            after={"provider_key": manifest.key, "route": "connect", "reason": "platform"},
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-084",
            message_key=REFUSAL_PLATFORM_PROVIDED,
            params={"provider": manifest.display_name},
        )
    # ⚠ `DEF-INT-4215` — A CONNECTOR WE NEVER DIAL HAS NO ADAPTER AND IS NOT
    # WAITING FOR ONE. The adapter requirement below was written for
    # `we_hold_theirs`, where the adapter IS the thing that talks to the
    # provider, and it was applied to all four auth modes; both
    # `they_hold_ours` connectors — the partner reading from us, the kiosk
    # posting to us — were therefore refused *Cannot be connected yet.* at the
    # last step of a modal that draws perfectly. Read as DATA off the manifest
    # (`Manifest.we_never_dial`, every operation `initiative = them`), so a
    # nineteenth such connector needs no line here and G77 stays satisfied.
    adapter_cls = (
        None
        if manifest.we_never_dial
        else _adapter_or_refuse(actor, manifest, route="connect", registry=registry)
    )
    # ⚠ `VAL_UNKNOWN_LOOKUP` AND NOT A CODE INVENTED HERE (`DEF-INT-4254`).
    # These three sites read `errors.VAL_UNKNOWN_LOOKUP` from wave B until 2026-09-06,
    # and that attribute HAS NEVER EXISTED — so each of them answered HTTP 500
    # with an `AttributeError` instead of the refusal it was written to give.
    # Nothing caught it: Python resolves a module attribute at CALL time, the
    # modal offers `production | sandbox` as a two-value control and `manual` as
    # a default, so no screen can reach the branch, and no test sent a value
    # outside the vocabulary. A browser walkthrough that omitted `environment`
    # by accident is what found it. A value outside a closed vocabulary is an
    # UNKNOWN LOOKUP, which is the code integrations already uses for an unknown
    # operation and an unmapped word.
    if environment not in models.ENVIRONMENTS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="integrations.refusal.environment",
            params={"environment": environment},
        )
    if cadence not in models.CADENCES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="integrations.refusal.cadence",
            params={"cadence": cadence},
        )
    # CR-173-BRC10 — a field in a named GROUP (New World's *Send to City
    # folder*) is saved by `file_drop` and never here: its secret belongs to
    # the group's own credential slot, and recording it as this connection's
    # primary credential would be the password standing where the key should.
    config, secrets = split_fields(manifest, ungrouped(manifest, fields or {}))
    problems = validate_fields(manifest, config, secrets)
    if not problems and adapter_cls is not None:
        problems = list(adapter_cls().validate(config))
    if problems:
        raise _field_refusal(problems)  # before any write
    refuse_unmapped_fallback(tenant_id, manifest)  # CR-174-BRC10, before any write
    existing = models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, provider_key=provider_key, environment=environment
    ).first()
    if existing is not None and (existing.enabled or _has_active_credential(existing)):
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_ALREADY_CONNECTED
        )
    try:
        with transaction.atomic():
            if existing is None:
                row = connect(
                    actor=actor,
                    tenant_id=tenant_id,
                    provider_key=provider_key,
                    environment=environment,
                    label=label,
                    config=config,
                    cadence=cadence,
                    registry=registry,
                )
            else:
                row = _reconnect(actor, existing, label=label, config=config, cadence=cadence)
            if secrets:
                record_credential(
                    actor=actor,
                    connection=row,
                    payload=json.dumps(secrets),
                    masked_hint=_hint(secrets),
                )
            # CR-174-BRC10 — the manifest's suggestions, for words still red.
            from apps.integrations import mappings as _mappings

            _mappings.apply_suggestions(actor=actor, tenant_id=tenant_id, manifest=manifest)
    except IntegrityError as clash:
        # The UNIQUE (tenant, key, environment) fired under a race. Caught
        # OUTSIDE the atomic block on purpose (law 14): inside it, PostgreSQL
        # would refuse every later statement and SQLite would not — the
        # refusal below then reads identically on both.
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_ALREADY_CONNECTED
        ) from clash
    return row


def _reconnect(
    actor: Any,
    row: models.IntegrationConnection,
    *,
    label: str | None,
    config: dict[str, Any],
    cadence: str,
) -> models.IntegrationConnection:
    """A disconnected row (`off`, credentials destroyed) is reused rather than
    duplicated — the UNIQUE triple says one row per environment. Fresh
    credentials are required (BR-INT-016), and `connect_with_fields` records
    them right after this."""
    before = {"status": row.status, "enabled": row.enabled, "cadence": row.cadence, "config": row.config}
    row.label = label
    row.config = config
    row.cadence = cadence
    row.status = models.STATUS_UNTESTED
    row.enabled = True
    row.next_run_at = None
    row.last_test_at = None
    row.last_test_ok = None
    row.last_test_text = None
    row.connected_by_id = getattr(actor, "id", None)
    row.connected_at = timezone.now()
    row.save()
    core_audit.money_action(
        actor,
        "integration.connected",
        "integration_connection",
        row.id,
        before=before,
        after={"status": row.status, "enabled": True, "cadence": cadence, "config": config},
    )
    return row


def refuse_unmapped_fallback(tenant_id: Any, manifest: Manifest) -> None:
    """`CR-174-BRC10` — refuse to switch a connector on while its fallback word
    points at nothing of ours, BY NAME.

    A payment agent's method words resolve through the mapping screen, and a
    word nobody listed resolves to the vocabulary's FALLBACK (*"unknown →
    OTHER, never refuse"*). With the fallback unmapped, the first payment in
    a new tender would land with no method of the utility's at all — so the
    connector cannot be switched on until it is mapped. Read off
    `Vocabulary.fallback` as data; a vocabulary declaring none (the kiosk's)
    is never refused here (G77).
    """
    from apps.integrations import mappings as _mappings

    for vocabulary in manifest.vocabularies:
        if vocabulary.fallback is None:
            continue
        if _mappings.local_for(tenant_id, manifest.key, vocabulary.entity_type, vocabulary.fallback) is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-INT-031",
                message_key=REFUSAL_FALLBACK_UNMAPPED,
                params={"word": vocabulary.fallback, "label": vocabulary.label},
            )


def credential_secrets(
    connection: models.IntegrationConnection, slot: str = models.CREDENTIAL_SLOT_PRIMARY
) -> dict[str, str]:
    """THE ONE READER OF `payload_enc` (BR-INT-003). Called by a runner for the
    length of one adapter call and dropped by it. Never by a screen, a log,
    an audit payload or a selector — a grep for this name is the audit.

    `slot` (CR-173-BRC10): every existing caller reads `primary`, the one
    secret every connector has; New World's SFTP password is the second slot
    and only `receipt_push` / `file_drop` ask for it."""
    row = (
        models.IntegrationCredential.objects.filter(
            connection=connection, is_active=True, slot=slot
        )
        .only("payload_enc")
        .first()
    )
    if row is None or not row.payload_enc:
        return {}
    loaded = json.loads(row.payload_enc)
    return {str(k): str(v) for k, v in loaded.items()}


# ═══════════════════════════════════════════════════════════════════════════
# The guard in front of every provider call — `runtime.py`'s policy, wired
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS FUNCTION IS THE WHOLE OF `DEF-INT-4015`, AND ITS ABSENCE COST
# NOTHING VISIBLE FOR A DAY.** `runtime.py` landed on 2026-09-04 with 427 lines
# of correct policy, 297 lines of passing tests and **no importer** — the four
# places that dial a provider each called the adapter directly, so the
# ninety-second hang the module exists to contain was exactly as uncontained
# after that commit as before it. `runtime.py` is deliberately pure (no Django,
# no models, so the policy can be asserted without a database); the price of
# that purity is that SOMETHING has to join it to a connection row, and that
# something is this file, because `services.py` is the module's one write path.
#
# ⚠ **WHY THE BREAKER IS PERSISTED HERE AND NOT LEFT IN MEMORY** — the decision
# log of 2026-09-04 has the argument: with eight workers, each counting only
# its own consecutive timeouts, a connection that has failed eight times in a
# row has failed once as far as each of them knows and the breaker never opens.
# The count lives on the connection's NON-SECRET `config` where every worker
# reads the same number.


def _breaker_now() -> float:
    """Wall clock, in epoch seconds — **not** `time.monotonic()` (`DEF-INT-4016`).

    ⚠ **A DURABLE BREAKER AND A MONOTONIC CLOCK ARE INCOMPATIBLE AND THE FIRST
    VERSION USED BOTH.** `open_until` is written by one process and read by
    another, so it must mean the same thing in both. `time.monotonic()` counts
    from an arbitrary origin — on Linux, boot — so a value written on one host
    is meaningless on a second, and a value written before a restart can sit
    arbitrarily far in the future and hold a healthy connection shut. It looked
    fine because every test injects its own clock as bare floats, and because
    on ONE kernel the origin happens to be shared.

    Durations are still measured monotonically inside `runtime.guarded_call`;
    that is the half a monotonic clock is for.
    """
    return time.time()


def _persist_breaker(
    connection: models.IntegrationConnection,
    state: "runtime.BreakerState",
    *,
    sentence: str | None,
) -> None:
    """Write the breaker's count and window back onto the connection.

    Also moves the connection's WORD when the breaker opens: `BR-INT-022` says
    the card reads *Not working* with the reason in words, and a breaker that
    is open while the card still says *Working* is hard-won law 1 — a claim
    that was true and is no longer known to be (which is exactly what
    `DEF-INT-3762` was).

    ⚠ **NO `try/except` AROUND THIS WRITE, DELIBERATELY (hard-won law 14).** A
    caught database error here would be the naive skip-and-continue: harmless
    on the SQLite suite, which has no aborted-transaction state, and on
    PostgreSQL it would poison the transaction the run row is being written in
    and lose the record of the very failure it is describing. If this write
    cannot happen the call fails loudly.
    """
    config = dict(connection.config or {})
    before = config.get(runtime.BREAKER_KEY)
    after = state.as_config()
    fields = ["config", "updated_at"]
    config[runtime.BREAKER_KEY] = after
    connection.config = config
    opened = runtime.is_open(state, now=_breaker_now())
    if opened and sentence and connection.last_test_text != sentence:
        connection.status = models.STATUS_NOT_WORKING
        connection.last_test_ok = False
        connection.last_test_text = sentence
        fields += ["status", "last_test_ok", "last_test_text"]
    elif before == after and not opened:
        return  # nothing moved; do not touch the row
    connection.save(update_fields=fields)


def guarded_adapter_call(
    *,
    connection: models.IntegrationConnection,
    operation: Any,
    call: Any,
    registry: Registry = REGISTRY,
) -> "runtime.Outcome":
    """Run one provider call under the timeout, the cap and the breaker.

    Every adapter call in this module goes through here — `runners/deliver.py`,
    `runners/fetch.py`, `jobs.py`'s test path and `seams/notifications.py`'s
    dispatch. Returns `runtime.Outcome`; `outcome.skipped` means **the call was
    never placed** and the caller owes a skipped run row (`BR-INT-024`).

    ⚠ **THE CAP IS KEYED ON THE CONNECTION AND NOTHING ELSE.** Keying it on the
    provider key would make Brazos Bend's dead mailbox throttle Silver Creek's
    healthy one — `BR-INT-041`'s exact failure wearing the fix's clothes — and
    both utilities run the same `email_smtp` manifest, so the mistake would not
    show on a single-tenant test.
    """
    manifest = registry.get(connection.provider_key)
    provider_name = manifest.display_name if manifest is not None else connection.provider_key
    limits = runtime.limits_for(operation, connection.config)
    state = runtime.BreakerState.from_config(connection.config)
    outcome = runtime.guarded_call(
        call,
        connection_id=connection.pk,
        limits=limits,
        state=state,
        now=_breaker_now,
        provider_name=provider_name,
    )
    if outcome.breaker is not None:
        _persist_breaker(connection, outcome.breaker, sentence=outcome.sentence)
    return outcome


def record_skipped_run(
    *,
    connection: models.IntegrationConnection,
    operation: Any,
    direction: str,
    trigger: str,
    outcome: "runtime.Outcome",
    attempted: int = 0,
    job_id: Any = None,
) -> models.IntegrationRun:
    """A window we did not dial, written down (`BR-INT-024`).

    `US-INT-022` §5 asks for *"attempted 0, summary names the reason"*, and
    that is what this writes: five zero counts and the sentence the card is
    showing. **The row exists so the skip is not silent** — a connection that
    quietly stops running is indistinguishable, on every screen this product
    has, from one that has nothing to do.
    """
    run = start_run(
        connection=connection,
        operation=operation.name,
        direction=direction,
        trigger=trigger,
        job_id=job_id,
    )
    return finish_run(
        run,
        attempted=0,
        succeeded=0,
        failed=0,
        skipped=0,
        confirmed=True,
        never_dialled=True,
        summary=outcome.sentence,
    )


def record_test_result(
    *,
    actor: Any,
    connection: models.IntegrationConnection,
    run: models.IntegrationRun,
    result: TestResult,
) -> models.IntegrationRun:
    """Close the test's run row and stamp the connection (US-INT-015 §5).

    `succeeded` or `failed` — a test is one attempt at one thing, and the far
    end answered, so it is confirmed. The connection's word follows:
    `working` on ok, `not_working` otherwise (frame 48.1 states 3 and 4).
    """
    closed = finish_run(
        run,
        attempted=1,
        succeeded=1 if result.ok else 0,
        failed=0 if result.ok else 1,
        skipped=0,
        confirmed=True,
        summary=result.sentence,
        provider_error=scrub(result.provider_text),
    )
    connection.last_test_at = closed.finished_at
    connection.last_test_ok = result.ok
    connection.last_test_text = result.sentence
    connection.status = models.STATUS_WORKING if result.ok else models.STATUS_NOT_WORKING
    connection.save(update_fields=["last_test_at", "last_test_ok", "last_test_text", "status", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_TEST_RUN,
        "integration_connection",
        connection.id,
        after={
            "provider_key": connection.provider_key,
            "outcome": closed.outcome,
            "sentence": result.sentence,
            "trace_id": closed.trace_id,
        },
    )
    return closed


def _ready_or_refuse(kind: str) -> None:
    """DEF-2487 — never queued into a void. A 202 is a promise; with no
    consumer on the `integrations` queue it would be a lie of DEF-320's shape."""
    ready, _reason = core_jobs.dispatch_is_ready(kind)
    if not ready:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-041", message_key=REFUSAL_NO_WORKER)


@require_role(SYSTEM_ADMIN)
def request_test(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    recipient: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`POST /integrations/{key}/test` → the job record for the 202.

    The `jobs` row is written before the broker message and before the reply
    — `core.jobs.enqueue`'s own order (US-INT-016 TC-1). The body is
    `jobs.run_test_job`, in a different process from this request.
    """
    from apps.integrations import jobs as integration_jobs  # a cycle at import time, not at call time

    manifest = _live_manifest(actor, provider_key, route="test", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    operation = integration_jobs.testable_operation(manifest)
    if operation is None:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-019", message_key=REFUSAL_NO_TEST_ACTION)
    if operation.test_needs_recipient and not (recipient or "").strip():
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_RECIPIENT_NEEDED)
    _adapter_or_refuse(actor, manifest, route="test", registry=registry)
    _ready_or_refuse(integration_jobs.TEST_JOB)
    return core_jobs.enqueue(
        integration_jobs.TEST_JOB,
        scope_key=f"{connection.id}:test",
        payload={
            "connection_id": str(connection.id),
            "recipient": (recipient or "").strip() or None,
            "actor_user_id": None if getattr(actor, "id", None) is None else str(actor.id),
        },
    )


@require_role(SYSTEM_ADMIN)
def receive_file(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    operation: str,
    body: bytes,
    registry: Registry = REGISTRY,
) -> Any:
    """`POST /integrations/{key}/arrival` — a file landed. Record it; refuse a repeat.

    Returns an `arrivals.Arrival`. The write route for the UPLOAD source: a
    clerk hands us Tuesday's lockbox file and we record that it arrived on the
    named bank connection, hashing the bytes BEFORE anything reads them
    (`BR-INT-020` C). A second arrival of the same bytes on the same connection
    is refused naming the first by day and time.

    ⚠ WHAT THIS ROUTE DOES NOT DO IS THE POINT OF `CR-069` WAVE I. It does not
    parse the file, match a payment to an account, or write a payment — that is
    Runbooks' half under `BR-INT-054` as amended 2026-09-06, and the run row it
    leaves open is the seam. A caller wanting the rows inside the file reads
    them from the bytes it already holds; nothing here interprets them.

    The same refusals guard it as `request_run`, and for the same reasons: a
    coming-soon provider is refused at the API rather than only by the button,
    a connection that is not connected or not enabled cannot receive anything,
    and a SANDBOX connection is never handed a real file (BR-INT-026).
    """
    from apps.integrations import arrivals as integration_arrivals

    manifest = _live_manifest(actor, provider_key, route="run", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    if connection.environment == models.ENVIRONMENT_SANDBOX:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_SANDBOX_ONLY)
    declared: Operation | None = next(
        (one for one in manifest.operations if one.name == operation), None
    )
    if declared is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_UNKNOWN_OPERATION,
            params={"operation": operation},
        )
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key=REFUSAL_FILE_REQUIRED
        )
    if not bytes(body):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key=REFUSAL_FILE_EMPTY
        )

    arrival = integration_arrivals.record_arrival(
        connection=connection,
        operation=operation,
        body=bytes(body),
        trigger="manual",
        registry=registry,
    )
    #: A lifecycle row for the connection (BR-INT-014 · hard rule 7). The HASH
    #: is recorded and the CONTENT is not — an audit row is not a place to keep
    #: a copy of a customer's bank file.
    core_audit.money_action(
        actor,
        AUDIT_FILE_ARRIVED if arrival.accepted else AUDIT_FILE_REFUSED,
        "integration_run",
        arrival.run.id,
        after={
            "provider_key": provider_key,
            "operation": operation,
            "input_hash": arrival.input_hash,
            "accepted": arrival.accepted,
        },
    )
    return arrival


@require_role(SYSTEM_ADMIN, BILLING_CLERK)
def request_export(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    operation: str,
    period_start: Any,
    period_end: Any,
    target: str,
    registry: Registry = REGISTRY,
) -> Any:
    """`POST /integrations/{key}/export` — a period was asked for. Record it; refuse a repeat.

    The MIRROR of `receive_file` above, and the two are worth reading together:
    that one keys on the BYTES THAT ARRIVED, this one keys on the WINDOW AND
    TARGET THAT WERE ASKED FOR, because when the question has to be answered
    the file does not exist yet (`BR-INT-020` B against C).

    Returns a `departures.Departure`. A second request for the same window on
    the same connection is refused naming the first handover by date, and an
    unregistered format is refused BY NAME with the list of what this
    connection offers before a run row exists at all (`BR-INT-031`).

    ⚠ WHAT THIS ROUTE DOES NOT DO IS THE POINT OF `CR-069` WAVE J. It does not
    read the books, compose a journal, count unmapped accounts, or write a
    file's contents — that is Runbooks' half under `BR-INT-054` as amended
    2026-09-06, and the run row it leaves open is the seam. `departures`'
    `journal_rows` and `export_readiness` are the two doors it arrives through.

    ⚠ AND IT MOVES NOTHING IN THE LEDGER. `apps/ledger/exports.py` keeps its own
    signed key (`uq_export_batches_period_target`, `BR-LED-004`) and its own
    four gates. This is a SECOND guard, on the CONNECTION, and it is looser in
    one deliberate way: two saved targets at one utility do not refuse each
    other's July.

    The same refusals guard it as `receive_file`, and for the same reasons: a
    coming-soon provider is refused at the API rather than only by the button,
    a connection that is not connected or not enabled cannot be exported to,
    and a SANDBOX connection is never handed a real period (`BR-INT-026`).
    """
    from apps.integrations import departures as integration_departures

    manifest = _live_manifest(actor, provider_key, route="run", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    if connection.environment == models.ENVIRONMENT_SANDBOX:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_SANDBOX_ONLY)
    declared: Operation | None = next(
        (one for one in manifest.operations if one.name == operation), None
    )
    if declared is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_UNKNOWN_OPERATION,
            params={"operation": operation},
        )
    try:
        departure = integration_departures.record_departure(
            connection=connection,
            operation=operation,
            period_start=period_start,
            period_end=period_end,
            target=target,
            trigger="manual",
            registry=registry,
        )
    except integration_departures.UnregisteredFormat as refusal:
        #: ⚠ TRANSLATED AT THE BOUNDARY, NEVER RAISED THROUGH. A clerk needs the
        #: catalogue key and both parameters — what they asked for and what
        #: exists — and `BR-INT-031` is explicit that outbound REFUSES rather
        #: than substituting. The 400 is the refusal; there is no second-best
        #: format to fall back to.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=refusal.message_key,
            params={
                "asked": refusal.asked,
                "offered": ", ".join(
                    integration_departures.FORMAT_NAMES.get(one, one) for one in refusal.offered
                ),
            },
        ) from None

    #: A lifecycle row for the connection (BR-INT-014 · hard rule 7). The KEY is
    #: recorded and no figure is — an audit row is not a place to keep a copy of
    #: a utility's month.
    core_audit.money_action(
        actor,
        AUDIT_PERIOD_EXPORTED if departure.accepted else AUDIT_PERIOD_REFUSED,
        "integration_run",
        departure.run.id,
        after={
            "provider_key": provider_key,
            "operation": operation,
            "period": [str(period_start), str(period_end)],
            "target": target,
            "export_key": departure.export_key,
            "accepted": departure.accepted,
        },
    )
    return departure


def request_run(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    operation: str,
    work: list[dict[str, Any]] | None = None,
    parameters: dict[str, Any] | None = None,
    window: dict[str, Any] | None = None,
    request_key: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`POST /integrations/{key}/run` — a manual attempt. Enqueues; never inline.

    A SANDBOX connection is never handed a real batch (BR-INT-026, US-INT-019
    TC-6); an operation the partner starts is not ours to run; a run already
    in flight for the same operation is refused rather than folded silently.

    ⚠ **WAVE K'S THREE ARGUMENTS ARE CARRIED, NOT INTERPRETED** (`CR-069`
    wave K). `parameters` is what the request states — including the four whose
    default is unsafe; `window` is `{from, to}` for a walk; `request_key` is the
    key a partner-state write is refused a second time on. This function checks
    none of them: the RUNNER refuses a request that leaves a safety parameter
    unset, and it does so where the request is actually made, so a caller
    reaching the runner by any other route is refused too. A check here as well
    would be the same rule in two places, and the second place is the one that
    goes stale.
    """
    from apps.integrations import jobs as integration_jobs

    manifest = _live_manifest(actor, provider_key, route="run", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    if connection.environment == models.ENVIRONMENT_SANDBOX:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-026", message_key=REFUSAL_SANDBOX_ONLY)
    declared: Operation | None = next((one for one in manifest.operations if one.name == operation), None)
    if declared is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=REFUSAL_UNKNOWN_OPERATION,
            params={"operation": operation},
        )
    if declared.they_call_us:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-028", message_key=REFUSAL_NOT_OURS_TO_START)
    _adapter_or_refuse(actor, manifest, route="run", registry=registry)
    scope_key = f"{connection.id}:{declared.name}"
    if core_jobs._store is not None and core_jobs._store.find_active(tenant_id, integration_jobs.RUN_JOB, scope_key):
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-039", message_key=REFUSAL_RUN_IN_FLIGHT)
    _ready_or_refuse(integration_jobs.RUN_JOB)
    return core_jobs.enqueue(
        integration_jobs.RUN_JOB,
        scope_key=scope_key,
        payload={
            "connection_id": str(connection.id),
            "operation": declared.name,
            "work": list(work or []),
            "parameters": dict(parameters or {}),
            "from": (window or {}).get("from"),
            "to": (window or {}).get("to"),
            "request_key": request_key,
            "actor_user_id": None if getattr(actor, "id", None) is None else str(actor.id),
        },
    )


_PATCHABLE = frozenset({"label", "cadence", "enabled", "config"})


@require_role(SYSTEM_ADMIN)
def update_connection(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    changes: dict[str, Any],
    registry: Registry = REGISTRY,
) -> models.IntegrationConnection:
    """`PATCH /integrations/{key}` — non-secret settings only, audited before/after.

    A secret never comes this way: the manifest's secret fields are refused
    as unknown here and rotate through `rotate_credential` (BR-INT-003).
    """
    manifest = _live_manifest(actor, provider_key, route="update", registry=registry)
    row = connection_for(tenant_id, provider_key)
    if row is None:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-002", message_key=REFUSAL_NOT_CONNECTED)
    unknown = sorted(set(changes) - _PATCHABLE)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=REFUSAL_UNKNOWN_FIELD,
            field_errors=[
                {"field": name, "code": errors.VAL_FORMAT, "message_key": REFUSAL_UNKNOWN_FIELD, "params": {}}
                for name in unknown
            ],
        )
    before = {"label": row.label, "cadence": row.cadence, "enabled": row.enabled, "config": dict(row.config or {})}
    after = dict(before)
    if "cadence" in changes:
        if changes["cadence"] not in models.CADENCES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="integrations.refusal.cadence",
                params={"cadence": changes["cadence"]},
            )
        after["cadence"] = changes["cadence"]
    if "label" in changes:
        after["label"] = changes["label"] or None
    if "enabled" in changes:
        after["enabled"] = bool(changes["enabled"])
        if after["enabled"] and not before["enabled"]:
            refuse_unmapped_fallback(row.tenant_id, manifest)  # CR-174-BRC10
    if "config" in changes:
        supplied = dict(changes["config"] or {})
        # ⚠ **THE STORED HALF IS PRUNED TO WHAT THE MANIFEST STILL DECLARES,
        # AND THE SUPPLIED HALF IS NOT (`DEF-INT-5582`).** A field that leaves a
        # manifest leaves its VALUES behind in `integration_connection.config`,
        # and `validate_fields` refuses any name it does not recognise — so the
        # merge below carried `scopes` and `client_id`, retired from the five
        # ERP manifests by `CR-110-BRC04` wave A, into every later PATCH and
        # `PATCH /integrations/erp_aclarian` answered `422 · integrations.field.
        # unknown` for BOTH of them, forever, whatever the clerk had actually
        # changed. Measured on the demo tenant on 2026-09-17: the row's raw
        # config was `{'scopes': 'payments', 'client_id': 'aclarian',
        # 'allowed_addresses': '127.0.0.0/8'}` and no edit to it could ever be
        # saved again.
        #
        # ⚠ **PRUNING THE STORED HALF IS NOT WIDENING THE DOOR, AND THE
        # ASYMMETRY IS THE WHOLE POINT.** An unknown name a CALLER sends is
        # still refused by name, exactly as before — that guard is what stops a
        # client writing values nothing declares. An unknown name already AT
        # REST was written by an earlier manifest through that same guard; it is
        # our own rot, and turning it into a permanent refusal punishes the
        # clerk for our field rename. A secret still cannot arrive this way:
        # `split_fields` puts it in `secrets` and the line below refuses it.
        declared = {one.name for one in manifest.fields}
        kept = {name: value for name, value in dict(row.config or {}).items() if name in declared}
        # CR-173-BRC10 — a GROUPED field keeps its stored value whatever this
        # body says: the group has its own save (`file_drop.save`), which
        # checks the group as a whole, and the generic form re-posts every
        # value it was seeded with.
        merged = {**kept, **ungrouped(manifest, supplied)}
        config, secrets = split_fields(manifest, merged)
        problems = validate_fields(manifest, config, secrets=None, require_secrets=False)
        # A secret never comes through PATCH — it rotates through /credential.
        problems.extend(FieldError(name, REFUSAL_UNKNOWN_FIELD) for name in secrets)
        if problems:
            raise _field_refusal(problems)
        after["config"] = config
    row.label = after["label"]
    row.cadence = after["cadence"]
    row.enabled = after["enabled"]
    row.config = after["config"]
    if row.cadence == models.CADENCE_MANUAL:
        row.next_run_at = None
    row.save()
    core_audit.money_action(
        actor,
        AUDIT_UPDATED,
        "integration_connection",
        row.id,
        before={k: v for k, v in before.items() if before[k] != after[k]},
        after={k: v for k, v in after.items() if before[k] != after[k]},
    )
    return row


@require_role(SYSTEM_ADMIN)
def disconnect(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    registry: Registry = REGISTRY,
) -> models.IntegrationConnection:
    """`DELETE /integrations/{key}` — every credential version destroyed NOW,
    the row set `off`, every run row kept (BR-INT-016 · BR-INT-042).

    A secret's retention differs from a record's: the credential rows are
    deleted, the connection and its history are not. The audit row carries
    the masked hints that were destroyed — never a payload (BR-INT-003).
    A secret's retention differs from a record's: the credential rows are
    deleted, the connection and its history are not. The audit row carries
    the masked hints that were destroyed — never a payload (BR-INT-003).

    ⚠ THIS PATH WAS WRITTEN BEFORE THE FIRST REAL CREDENTIAL COULD BE STORED,
    which is the design's own ordering and the reason wave E's task list puts
    it before the adapter: a product that can accept a secret and cannot
    remove it is worse than one that cannot accept it at all. `US-INT-025`
    TC-6 is the standing form of that ordering — the disconnect test lands in
    the same commit as, or before, the first adapter that stores a credential.

    WHAT THIS DOES NOT TOUCH, AND THE NOT-TOUCHING IS THE RULE (BR-INT-016):
    the run history (every row kept, append-only), and the notification queue.
    Queued messages rest exactly `queued`; nothing cancels them, nothing fails
    them, and NOTHING falls back to a shared sender — the utility's own
    address or it does not go (A15 addendum). They surface as config-missing
    on the dispatch home by themselves, because the connection is now `off`
    and `provider_seam.channel_route` reads that. The count is read through
    `seams/notifications.py` only so the audit row and the confirm can state
    the figure; reading it changes nothing.
    """
    _live_manifest(actor, provider_key, route="disconnect", registry=registry)
    row = connection_for(tenant_id, provider_key)
    if row is None or (not row.enabled and not _has_active_credential(row)):
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-INT-002", message_key=REFUSAL_NOT_CONNECTED)
    manifest = registry.require(provider_key)
    credentials = models.IntegrationCredential.objects.filter(connection=row)
    destroyed = list(credentials.order_by("version").values_list("masked_hint", flat=True))
    kept_runs = models.IntegrationRun.objects.filter(connection=row).count()
    _channel, waiting = notifications_seam.waiting_for_category(manifest.category)
    with transaction.atomic():
        credentials.delete()
        # ⚠ **THE DIRECTORY ROWS GO WITH THEM, AND ONLY HERE** (`DEF-INT-5546`,
        # 2026-09-16). `integration_key_directory` says which utility an issued
        # key belongs to, so that a partner request carrying nothing but a key
        # can be resolved at all. A row outliving its credential would resolve a
        # utility for a key whose credential no longer exists — refused
        # correctly, recorded uselessly. `revoke_key` deliberately does NOT do
        # this: a revoked credential is kept and readable, so its refusal can be
        # written down as *key revoked* rather than as *key unknown*, and that
        # distinction is the half of `BR-INT-044` meant to survive in our own
        # record. Disconnecting is the relationship ending; revoking is not.
        key_directory.forget_connection(row.id)
        row.status = models.STATUS_OFF
        row.enabled = False
        row.next_run_at = None
        row.save(update_fields=["status", "enabled", "next_run_at", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_DISCONNECTED,
        "integration_connection",
        row.id,
        before={"status": models.STATUS_WORKING, "credentials": destroyed},
        after={
            "status": models.STATUS_OFF,
            "provider_key": provider_key,
            "destroyed": destroyed,
            # The sentence US-INT-025 TC-1 asks for, in a clerk's words, with
            # no rule id and no table name in it (B14 rule 32, G71).
            "summary": (", ".join(destroyed) + " destroyed") if destroyed else "no password was stored",
            "runs_kept": kept_runs,
            "messages_waiting": waiting,
        },
    )
    return row


def disconnect_preview(
    tenant_id: Any,
    provider_key: str,
    *,
    registry: Registry = REGISTRY,
) -> dict[str, Any] | None:
    """What the IS-6 confirm shows BEFORE anything is destroyed (US-INT-003).

    Two halves, and they are two halves because the frame draws them in two
    colours: **what happens straight away** (the password destroyed, sending
    stopped) and **what is kept** (every run, every queued message). The
    server sends the CATEGORY and the FIGURES; the sentences are catalogue
    lines in eleven languages — the argument `ConnectionDetailPage` already
    makes about the run counts, for the same reason.

    `None` when there is nothing to disconnect. `messages_waiting` is `None`
    rather than `0` when notifications cannot answer: a zero would tell a
    utility nothing is waiting when the truth is that nobody looked.
    """
    row = connection_for(tenant_id, provider_key)
    if row is None or (not row.enabled and not _has_active_credential(row)):
        return None
    manifest = registry.require(provider_key)
    channel, waiting = notifications_seam.waiting_for_category(manifest.category)
    return {
        "category": manifest.category,
        "label": row.label,
        "versions": models.IntegrationCredential.objects.filter(connection=row).count(),
        "runs_kept": models.IntegrationRun.objects.filter(connection=row).count(),
        "channel": channel,
        "messages_waiting": waiting,
    }


@require_role(SYSTEM_ADMIN)
def rotate_credential(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    fields: dict[str, Any],
    registry: Registry = REGISTRY,
) -> tuple[models.IntegrationCredential, dict[str, Any] | None]:
    """`POST /integrations/{key}/credential` — v(n+1) written, n deactivated,
    and a test requested when the provider has one. Returns the new
    credential row and the test's job record (or None).

    `credential_versions()` is the read half — the short history under
    *Replace password* (frame 54.2) — and `rollback_credential()` below is the
    undo. Together they are `US-INT-024`.
    """
    from apps.integrations import jobs as integration_jobs

    manifest = _live_manifest(actor, provider_key, route="credential", registry=registry)
    row = _connected_or_refuse(tenant_id, provider_key)
    config_part, secrets = split_fields(manifest, fields or {})
    # Only secret fields come this way; a non-secret setting is PATCH's.
    problems = [FieldError(name, REFUSAL_UNKNOWN_FIELD) for name in config_part]
    # CR-173-BRC10 — a grouped secret is its group's, and replacing it here
    # would put it in the PRIMARY slot over the connection's own key.
    grouped = {one.name for one in manifest.fields if one.group}
    problems.extend(FieldError(name, REFUSAL_UNKNOWN_FIELD) for name in secrets if name in grouped)
    for one in manifest.fields:
        if one.kind == "secret" and one.required and not secrets.get(one.name):
            problems.append(FieldError(one.name, "integrations.field.required"))
    if problems:
        raise _field_refusal(problems)
    _adapter_or_refuse(actor, manifest, route="credential", registry=registry)
    credential = record_credential(
        actor=actor, connection=row, payload=json.dumps(secrets), masked_hint=_hint(secrets)
    )
    operation = integration_jobs.testable_operation(manifest)
    if operation is None or operation.test_needs_recipient:
        # No safe instance, or one that needs a typed address — the modal's
        # Test it now asks for it; nothing is queued blind.
        #
        # ⚠ AND THE CONNECTION'S WORD GOES BACK TO *Not tested yet* WHEN IT
        # DOES (DEF-INT-3762, found by clicking the screen). `status`,
        # `last_test_ok` and `last_test_text` were all taken against the
        # password that has just been REPLACED, so leaving them is a card that
        # says *Working* about a credential nobody has tried — hard-won law 1
        # exactly, a claim that WAS true and is no longer known to be.
        # `rollback_credential` below already does this and says why; the two
        # halves of one story disagreed until a browser walkthrough noticed.
        row.status = models.STATUS_UNTESTED
        row.last_test_ok = None
        row.last_test_text = None
        row.save(update_fields=["status", "last_test_ok", "last_test_text", "updated_at"])
        return credential, None
    _ready_or_refuse(integration_jobs.TEST_JOB)
    record = core_jobs.enqueue(
        integration_jobs.TEST_JOB,
        scope_key=f"{row.id}:test",
        payload={
            "connection_id": str(row.id),
            "recipient": None,
            "actor_user_id": None if getattr(actor, "id", None) is None else str(actor.id),
        },
    )
    return credential, record



def credential_versions(connection: models.IntegrationConnection) -> list[dict[str, Any]]:
    """The short history under *Replace password* (frame 54.2) — newest first.

    `masked_hint` and dates. `payload_enc` is not in the `.only()` list and is
    not read here; the ONE reader of that column is `credential_secrets`, and
    a grep for its name is the audit (BR-INT-003).
    """
    rows = (
        models.IntegrationCredential.objects.filter(
            connection=connection, slot=models.CREDENTIAL_SLOT_PRIMARY
        )
        .only("version", "is_active", "masked_hint", "expires_at", "rotated_at", "created_at")
        .order_by("-version")
    )
    return [
        {
            "version": one.version,
            "is_active": one.is_active,
            "hint": one.masked_hint,
            "expires_at": one.expires_at,
            "rotated_at": one.rotated_at,
            "created_at": one.created_at,
        }
        for one in rows
    ]


@require_role(SYSTEM_ADMIN)
def rollback_credential(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    registry: Registry = REGISTRY,
) -> models.IntegrationCredential:
    """`POST /integrations/{key}/credential/rollback` — the 5 pm Friday undo.

    THE WHOLE STORY IN ONE SENTENCE (US-INT-024): the previous version is
    re-activated and the current one deactivated, IN ONE ROW EACH, and nobody
    re-authorises with the provider — because the previous secret was never
    thrown away, only stood down.

    TWO REFUSALS, BOTH ≤ 6 WORDS AND BOTH BY NAME:
      * *Nothing to roll back to.* — one version, or none (TC-4).
      * *Previous credential has expired.* — the version underneath has an
        `expires_at` in the past, so re-activating it would put the connection
        back to *Working* against a secret the provider has already retired.
        Re-authorisation is the only path, and the refusal says so (TC-5).

    ⚠ THE ORDER OF THE TWO WRITES IS LOAD-BEARING AND IS THE DATABASE'S RULE,
    NOT THIS FUNCTION'S. Exactly one row per connection may carry
    `is_active` (an EXCLUDE constraint on PostgreSQL, a partial unique index
    on SQLite — migration 0001). So the CURRENT row is stood down first and
    the previous one raised second, inside one transaction; reverse them and
    the database refuses the second statement. That refusal is the guard that
    holds if this code is ever wrong, which is the point of putting it there.

    The connection row is not written at all: it holds no secret, so a
    roll-back changes nothing about it (US-INT-024 §1). What DOES change is
    the connection's word — `untested` — because the last test result was
    taken against the version we have just stood down, and leaving *Not
    working* on the card after a successful undo would be a lie of the exact
    shape hard-won law 1 is about.
    """
    _live_manifest(actor, provider_key, route="credential_rollback", registry=registry)
    row = _connected_or_refuse(tenant_id, provider_key)
    versions = list(
        models.IntegrationCredential.objects.filter(
            connection=row, slot=models.CREDENTIAL_SLOT_PRIMARY
        ).order_by("-version")[:2]
    )
    if len(versions) < 2:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-025", message_key=REFUSAL_NOTHING_TO_ROLL_BACK
        )
    current, previous = versions[0], versions[1]
    if previous.expires_at is not None and previous.expires_at <= timezone.now():
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-025", message_key=REFUSAL_PREVIOUS_EXPIRED
        )
    now = timezone.now()
    with transaction.atomic():
        models.IntegrationCredential.objects.filter(pk=current.pk).update(
            is_active=False, rotated_at=now
        )
        models.IntegrationCredential.objects.filter(pk=previous.pk).update(
            is_active=True, rotated_at=None
        )
        row.status = models.STATUS_UNTESTED
        row.last_test_ok = None
        row.last_test_text = None
        row.save(update_fields=["status", "last_test_ok", "last_test_text", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_CREDENTIAL_ROLLED_BACK,
        "integration_connection",
        row.id,
        before={"version": current.version, "masked_hint": current.masked_hint},
        after={
            "version": previous.version,
            "masked_hint": previous.masked_hint,
            "hints": f"{current.masked_hint} → {previous.masked_hint}",
        },
    )
    previous.is_active = True
    previous.rotated_at = None
    return previous


# ⚠ `refuse_oauth_start` WAS HERE AND IS GONE — WAVE H BUILT THE TRIP IT WAS
# REFUSING (2026-09-06). It read, correctly for its day: *"the trip itself is
# wave G/H's (US-INT-027). A button wired to nothing is hard-won law 2, so the
# route exists and states the absence in ≤ 6 words."* That hold has now
# EXPIRED, which is the moment law 2's mirror is about — a live screen behind a
# dead control — so the refusal was deleted in the same commit that landed the
# thing it pointed at, rather than left to rot into a button that refuses over
# a feature that shipped.
#
# `apps/integrations/oauth.py` owns both halves now. The two names below are
# re-exported so that the ADDRESS a neighbour looks at does not move: wave B's
# `api.py` and anything resolving `apps.integrations.services` by name keep
# working, which is the same reason `seams/notifications.py`'s two functions are
# published on this module.
from apps.integrations.oauth import complete as complete_oauth  # noqa: E402
from apps.integrations.oauth import start as start_oauth  # noqa: E402

#: Wave H — `expiry.sweep_expiry` is the sweep BODY and `services` is the
#: address a caller resolves. ⚠ It is a callable and NOT a schedule: deciding
#: when to run it is Runbooks' (BR-INT-054 as amended 2026-09-06).
from apps.integrations.expiry import sweep_expiry  # noqa: E402
from apps.integrations.expiry import view_for as credential_expiry  # noqa: E402


# ── the key we ISSUE (wave R, US-INT-040) ───────────────────────────────────
#
# The minting, the revoking and the one authentication decision live in
# `machine_auth.py` — beside `mappings.py`, and re-exported here for the same
# reason (DEF-075's rule): `services.py` is this module's one write path (B1)
# and therefore its one ADDRESS, so a neighbour importing
# `apps.integrations.services.issue_partner_key` keeps working whatever the
# file layout does next.


def issue_partner_key(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    scope: Sequence[str],
    registry: Registry = REGISTRY,
) -> tuple[models.IntegrationCredential, str]:
    """`POST /integrations/{key}/key` — issue or replace. Returns `(row, key)`.

    ⚠ THE SECOND ELEMENT IS THE ONLY COPY OF THE KEY THAT WILL EVER EXIST; it
    goes into one response body and nowhere else.

    ⚠ `scope` IS REQUIRED AND HAS NO DEFAULT (`CR-110-BRC04`) — which of this
    connector's operations the key may call. A key with nothing ticked is
    refused rather than minted, so the route must ask. See
    `machine_auth.issue_key`.
    """
    _live_manifest(actor, provider_key, route="key", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    return machine_auth.issue_key(
        actor=actor, connection=connection, scope=scope, registry=registry
    )


def revoke_partner_key(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    registry: Registry = REGISTRY,
) -> models.IntegrationCredential:
    """`DELETE /integrations/{key}/key` — the partner's very next call is refused."""
    _live_manifest(actor, provider_key, route="key", registry=registry)
    connection = _connected_or_refuse(tenant_id, provider_key)
    return machine_auth.revoke_key(actor=actor, connection=connection, registry=registry)


#: S144's rows. ⚠ THERE IS NO `authenticate` RE-EXPORT HERE AND THERE MUST NOT
#: BE ONE: the single answer to *may this machine read* is
#: `runners/serve.resolve_caller`, wave S's, and a convenience alias at this
#: address would be a second name for a security decision — the first step
#: towards a second implementation of it.
issued_keys = machine_auth.issued_keys



# ══════════════════════════════════════════════════════════════════════════
# CR-083 · THE SAMPLE-DATA SEAM (PO 2026-09-07 — "Step 30, Integrations")
# ══════════════════════════════════════════════════════════════════════════
#
# `apps/tenancy/seams.resolve` looks a block up as
# `apps.<module>.services.<seam>` and nowhere else, so the NAME lives here and
# the CODE lives in `sample_data.py` — the same split `apps/work/services.py`
# and every other seeding module already uses. The import is inside each
# function because `sample_data` imports this module.


def seed_sample_records(actor: Any) -> int:
    """`BR-TEN-056/057` — this module's block of the sample set: three
    connections, the five runs of `US-INT-020` §4, one landed payment
    notification and one recorded accounting handover. See
    `apps/integrations/sample_data.py`, which says why each is there."""
    from apps.integrations import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_records_note() -> str:
    """The sentence S62 renders beside the block, read after it has run."""
    from apps.integrations import sample_data

    return sample_data.seed_sample_records_note()


def remove_sample_records() -> dict[str, Any]:
    """`BR-TEN-061/066` — remove what is free, report the rest BY NAME. A
    connection that has runs is switched OFF and RETAINED: `integration_run` is
    append-only, so deleting it is not something this product can do."""
    from apps.integrations import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    """How many sample connections this module holds right now, read live."""
    from apps.integrations import sample_data

    return sample_data.sample_record_count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-014@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packets US-INT-018@62d3643 · US-INT-001@a63a1b7)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D=deferred(wave B mounts the write routes — US-INT-017/019; wave A serves the READ only) E=deferred(no write control on S8 in wave A — law 2, no button wired to nothing) F✔ G✔ H=n/a(the 🔒 half is the RLS migration, ledgered there)
# gates: pytest tests/test_us_int_014_tables.py tests/test_us_int_018_operations.py (SQLite) · tests/test_us_int_014_pg.py (PostgreSQL) · G77 (no `provider_key ==` here — the registry decides, by key) · G32 (every message_key raised here resolves in en.json)
# exceptions: SKELETON by design — test/disconnect/enable/roll-back/target references arrive with waves B–E and their own stories · no writer for integration_consent (OQ-INT-1482 OPEN) · `finish_run` computes the outcome and never accepts the word from a caller
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
