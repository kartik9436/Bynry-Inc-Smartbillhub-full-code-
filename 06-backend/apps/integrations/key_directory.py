# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 — `DEF-INT-5546`. The utility leaves the
#           partner URL; the key resolves it. PO 2026-09-16, verbatim: *"we
#           agreed not to use utility names in partner apis that was our rule -
#           so these urls are not corect - we will resolve utility name using
#           keys"*.
# Rules:    BR-TEN-003 (the tenant is never read from a value the caller
#           ASSERTS — a key is proof, not a claim) · CLAUDE.md hard rule 1
#           (RLS FORCE does the isolating, once a utility is open) ·
#           BR-INT-044 (a refusal teaches nothing, including by timing) ·
#           hard-won law 3 (the unsafe option is the one you type)
# Tests:    06-backend/tests/test_cr110_partner_tenant_from_key.py
# Impacts:  apps/integrations/runners/serve.py (calls `adopt_tenant_for`) ·
#           apps/integrations/services.py (`record_credential` writes a row;
#           `disconnect` drops them when a connection ends)
# ───────────────────────────────────────────────────────
"""Which utility an issued key belongs to — the one read before a utility is open.

⚠ **THIS FILE IS A SIGNPOST AND NOT A GUARD.** It answers *which door do I
open*, and nothing else. Whether the key is live, unexpired, in scope, from a
permitted address, on an enabled connector at a live utility is decided
afterwards by `runners/serve.resolve_caller`, reading the real credential row
under the utility this file opened — so a directory row that named the WRONG
utility buys nothing: the credential lookup under that utility would not find the
key, and the caller would be refused in the ordinary way with the ordinary five
words. Treat anything here that starts to look like an authorisation decision as
a bug, and put it in `serve.py` where the other eight checks are.

WHY IT EXISTS AT ALL
---------------------
The blueprint (p159, *WHY NOT PUT IT IN THE PATH*) draws the partner surface as

    key ──► connection ──► tenant ──► app.tenant_id set ──► RLS does the isolating

and the first arrow is the only one this product did not have. Every tenant table
answers zero rows with no `app.tenant_id` set, so the credential itself could not
be found — which is what pushed the first build of these routes to put the
utility in the URL instead. `integration_key_directory` is not a tenant table
(models.py and migration `0011` carry the argument), so the first arrow works and
the other four are the ones this product already had.

⚠ **THE DIRECTORY IS NOT WHERE `is_active` LIVES, AND A REVOKED KEY KEEPS ITS
ROW.** `serve.record_refusal` can only write the run row a manager reads —
*"Aclarian refused: key revoked"* — when it has a connection to hang it on, and
it gets one by resolving the utility first. Delete the row on revoke and a
revoked key becomes indistinguishable from an unknown one **in our own record**,
which is the half of `BR-INT-044` that is meant to stay distinguishable.

⚠ **TIMING: ONE QUERY, HIT OR MISS.** `adopt_tenant_for` costs exactly one
statement whether or not the key is known, so the directory itself adds no
signal. What follows it does: a hit then costs the credential query and a miss
does not, which is the pre-existing `KEY_UNKNOWN`-is-cheaper asymmetry that
`serve.REFUSAL_FLOOR_S` exists to absorb. The floor is measured from the top of
`resolve_caller`, so this call is inside the padded window (`test_cr110_partner_
tenant_from_key.py` puts a known-but-revoked key and an invented one side by side
and compares elapsed times against the floor).
"""

from __future__ import annotations

import uuid
from typing import Any

from core import crypto
from core.tenancy import adopt_partner_tenant, clear_current_tenant, current_tenant_id


def _blind_index_context() -> str:
    """Imported at call time, never retyped.

    ⚠ **IF THIS STRING EVER DIFFERS FROM THE ONE `machine_auth` WRITES UNDER,
    EVERY VALID KEY IS REFUSED AND THE DOOR STILL LOOKS LIKE IT IS WORKING** —
    a refused key is exactly what a wrong key looks like, in both directions,
    with nothing raising. `serve.py` says the same thing about the same
    constant; there is one of them and this reads it.
    """
    from apps.integrations.runners import serve

    return serve.ISSUED_KEY_BLIND_INDEX_CONTEXT


def record(credential: Any) -> None:
    """Write (or refresh) the directory row for one issued credential.

    Called from `services.record_credential`, which is the ONE write path for a
    credential (B1) — so a directory row exists for every issued key BY
    CONSTRUCTION rather than because the minting path remembered. A credential
    with no blind index is not an issued key — ten of the twelve connectors hold
    somebody ELSE's secret, which authorises nothing at our door — and is simply
    skipped rather than written as a row pointing at nothing.

    `update_or_create` rather than `create`: re-recording the same key is a
    no-op instead of an `IntegrityError`, and the blind index is the primary key
    so there can never be two rows claiming one key for two utilities.
    """
    from apps.integrations import models

    if not getattr(credential, "blind_index", None):
        return
    models.IntegrationKeyDirectory.objects.update_or_create(
        blind_index=credential.blind_index,
        defaults={
            "tenant_id": credential.tenant_id,
            "connection_id": credential.connection_id,
            "credential_id": credential.id,
        },
    )


def forget_connection(connection_id: Any) -> int:
    """Drop every directory row for a connection whose credentials are gone.

    `services.disconnect()` destroys every credential version — that is a
    relationship ENDING, unlike `revoke_key`, which deactivates one row and
    leaves it readable. A directory row outliving its credential would resolve a
    utility for a key whose row no longer exists, which refuses correctly and
    records nothing useful; dropping it here keeps the two in step.
    """
    from apps.integrations import models

    deleted, _ = models.IntegrationKeyDirectory.objects.filter(
        connection_id=connection_id
    ).delete()
    return deleted


def tenant_for(presented_key: str | None) -> uuid.UUID | None:
    """The utility this key was issued by, or `None` — ONE query, hit or miss.

    The lookup is `blind_index__in candidates` rather than an equality, because
    the index is keyed and the keyring can hold more than one key during a
    rotation (`core/crypto.py` says so): equality against the ACTIVE token alone
    would stop resolving every key indexed under the previous one, and every one
    of them would then read as an unknown key.
    """
    if not presented_key:
        return None
    candidates = crypto.blind_index_candidates(presented_key, context=_blind_index_context())
    if not candidates:
        return None
    from apps.integrations import models

    found = (
        models.IntegrationKeyDirectory.objects.filter(blind_index__in=candidates)
        .values_list("tenant_id", flat=True)
        .first()
    )
    if found is None:
        return None
    return found if isinstance(found, uuid.UUID) else uuid.UUID(str(found))


def open_utility_for(request: Any, presented_key: str | None) -> uuid.UUID | None:
    """Open the utility this key names, on a request that named none.

    ⚠ **A NO-OP WHEN A CONTEXT IS ALREADY SET, AND THAT IS A REFUSAL RATHER THAN
    A CONVENIENCE.** The phase-1 addresses still carry the utility in the path
    (`/api/{utility}/v1/payments`), and on those the path has already decided.
    Letting a key OVERRIDE a context the path set would be a tenant switch
    reachable by presenting a key — exactly what `adopt_session_tenant` refuses
    on tenant-scoped paths, for the same reason and in the same words.

    ⚠ **A MISS SETS NOTHING AND THAT IS THE WHOLE ERROR PATH.** There is no
    refusal built here: with no context, `serve._credential_matching` finds
    nothing, `resolve_caller` computes every guard, records `KEY_UNKNOWN` and
    raises the one refusal, padded to the floor. Building a second, earlier
    refusal here is how this surface would acquire a fast 404 that a stopwatch
    can tell apart from a slow one — a caller would learn from the timing that
    its key is at least REAL, which is the enumeration oracle `BR-INT-044`
    closes. There is deliberately nothing to raise.

    ⚠ **TWO STATEMENTS ON EVERY PATH, HIT OR MISS, AND THE SECOND ONE IS WHY
    THE `else` EXISTS.** This runs BEFORE `resolve_caller` starts the clock its
    `REFUSAL_FLOOR_S` pads against, so whatever it costs is added on top of the
    floor rather than absorbed by it — and a hit that sets the GUC while a miss
    sets nothing would be one `set_config` round trip of difference, measurable,
    and it would mean *your key is at least one we issued*. So a miss CLEARS the
    context instead of leaving it alone: the same two statements, the same cost,
    and the clear is fail-closed in its own right (hard-won law 3) rather than
    trusting that nothing upstream left a context behind.
    """
    if current_tenant_id() is not None:
        return current_tenant_id()
    tenant_id = tenant_for(presented_key)
    if tenant_id is None:
        clear_current_tenant()
        return None
    return adopt_partner_tenant(request, tenant_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 (DEF-INT-5546)
# generated: 2026-09-16 by the DEF-INT-5546 lane
# checklist: A✔ B=n/a(no screen) C✔ D✔ E=n/a F✔ G✔ H=deferred(🔒 rows in 09-human-review-ledger.md)
# gates: pytest tests/test_cr110_partner_tenant_from_key.py · tests/test_tenant_isolation.py::test_g5_the_rls_exempt_list_is_exactly_what_b2_declares
# exceptions: the table it reads is RLS-EXEMPT by B2 §3 — declared, not omitted; the argument is in migration 0011
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
