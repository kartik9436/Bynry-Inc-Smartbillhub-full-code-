# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 lane 4 — the inbound door's three verification styles
#           (`registry.INBOUND_VERIFICATIONS`). This file is the ONE answer to
#           *where does this connector's webhook secret live*.
# Rules:    BR-INT-003 (a secret lives in `integration_credential.payload_enc`
#           and is read in ONE place) · BR-INT-037 / G77 (configuration is
#           data — no branch on a provider key) · BR-TEN-003 (the tenant is
#           the path) · CLAUDE.md hard rule 1 (RLS FORCE; no cross-tenant
#           queryset) · hard-won law 3 (fail closed) · law 1 (a comment
#           claiming a guarantee is not the guarantee)
# Tests:    06-backend/tests/test_cr115_inbound_verification.py
# Impacts:  apps/integrations/inbound.py (the ONE caller) ·
#           apps/integrations/registry.py (`InboundVerification.secret_field`
#           names WHICH field this reads)
# ───────────────────────────────────────────────────────
"""WHERE A CONNECTOR'S WEBHOOK SECRET LIVES — one function, and the branch named.

WHAT THIS IS FOR
----------------
A signature-verified webhook (`registry.VERIFY_SIGNATURE`) needs a shared
secret before it can decide anything. Reading it is one line; deciding WHOSE
it is turns out to be a live product question, and this file exists so that
the question has exactly one home instead of being answered again inside the
door, inside an adapter and inside a screen — which is how an operation's
address came to be decided in five disagreeing places (`addressing.py`'s own
docstring counts them).

TWO POSSIBLE HOMES, AND ONLY ONE OF THEM IS BUILT
-------------------------------------------------
**PO ruling 2026-09-17, verbatim: _"our account - we will provdie servcie to
utilities as platform provider"_.** We hold the SendGrid and Postmark accounts
ourselves and sell email to utilities as a service; a utility supplies no
credentials of its own. That ruling does NOT by itself decide where the
webhook secret lives, because it leaves two shapes open:

  * **`SCOPE_PER_CONNECTION` — BUILT, and it is what this file does today.**
    Each utility gets its own SendGrid *subuser* or its own Postmark *Server*,
    each with its own webhook and therefore its own verification key. The key
    is then an ordinary tenant secret: `integration_credential.payload_enc`,
    one row per connection, RLS-scoped like every other credential, read
    through `services.credential_secrets` — the ONE reader (`BR-INT-003`).

  * **`SCOPE_PLATFORM` — NAMED, NOT BUILT, AND IT CANNOT BE BOLTED ON TO THE
    LINE ABOVE.** If instead ONE platform-level webhook serves every utility,
    the secret belongs to no tenant, and `integration_credential` **cannot
    hold it**: the table has RLS ENABLED AND FORCED, so a read with no
    `app.tenant_id` set yields zero rows for every key including the right one
    (CLAUDE.md hard rule 1, and law 7's *incapable of passing*). The
    non-tenant precedent in this repo is `platform_number_series`. A
    platform-scope branch therefore goes HERE — a second arm of `secret_for`
    reading that store, chosen by `scope_for` — and nowhere else.

⚠ **`scope_for()` ANSWERS `SCOPE_PER_CONNECTION` FOR EVERY CONNECTOR TODAY AND
SAYS SO RATHER THAN PRETENDING TO DECIDE.** It is not a manifest field yet
because which shape each connector takes is UNRULED (see the report and the
open question this lane filed); minting a manifest word for it now would put
a guess inside a closed vocabulary that `registry.py` refuses by name, which
is the expensive kind of guess.

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
* **It does not authenticate.** It hands back a secret and the connection it
  belongs to. Whether a caller may come in is `runners/serve.resolve_caller`'s
  and remains the only answer to that question (`inbound.py`'s *ONE
  AUTHENTICATOR, NOT TWO*).
* **It does not decrypt anything itself.** `services.credential_secrets` is
  the one reader of `payload_enc` and a grep for that name is the audit; a
  second reader here would make the grep a lie.
* **It never returns a partial answer.** No connection, no active credential,
  no value under the declared name → `None`, and the door refuses. A webhook
  secret that is missing must never read as a webhook that needs no secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.integrations.registry import Manifest
from core.tenancy import current_tenant_id

#: The secret is this utility's own, in `integration_credential.payload_enc`.
SCOPE_PER_CONNECTION = "per_connection"
#: The secret is the PLATFORM's, shared by every utility. Named so the branch
#: has a word before it has an implementation; see the module docstring.
SCOPE_PLATFORM = "platform"
SECRET_SCOPES = (SCOPE_PER_CONNECTION, SCOPE_PLATFORM)


@dataclass(frozen=True)
class InboundSecret:
    """A webhook secret, the connection it belongs to, and where it came from.

    ⚠ **THE PLAINTEXT IS ON THIS OBJECT AND THE OBJECT IS SHORT-LIVED.** It
    exists for the length of one verification and is dropped. It has no
    `__str__`, no `envelope()` and no screen: nothing in this module puts it
    on a run row, in an audit payload or in a log line, which is the same
    posture `serve.PartnerCaller` takes by carrying a MASK instead of a key.
    """

    connection: Any
    secret: str
    scope: str


def scope_for(manifest: Manifest) -> str:
    """WHERE this connector's webhook secret lives.

    ⚠ **ONE ANSWER TODAY, AND THE HONEST ONE.** Every connector's webhook
    secret is per-connection, because that is the only store that is built.
    The platform-level branch is described in the module docstring and lands
    here, as a second arm, on the day the subuser-versus-shared question is
    ruled — with `manifest` already in hand so the choice can be per connector
    without any caller changing.
    """
    return SCOPE_PER_CONNECTION


def secret_for(manifest: Manifest) -> InboundSecret | None:
    """The shared secret this connector's inbound signatures verify against.

    `None` when there is no connection in this tenant, no active credential on
    it, or no value stored under the field name the manifest declares. The
    caller REFUSES on `None`; it never treats it as *no verification needed*.

    ⚠ **THE TENANT IS WHATEVER `app.tenant_id` THE PATH ALREADY SET.** This
    function takes no tenant argument, exactly as `serve._connection_for` takes
    none, so it cannot be pointed across the boundary. With no tenant open it
    answers `None` and the door refuses — the safe direction.

    ⚠ **WHICH FIELD IT READS IS THE MANIFEST'S TO SAY** (`BR-INT-037`).
    `auth.inbound.secret_field` names it, `registry.py` has already refused at
    load a manifest naming a field it does not declare or one of a non-secret
    kind, so by the time this runs the name resolves and the value is in
    `payload_enc` rather than in `config`.
    """
    declared = manifest.auth.inbound
    if declared is None or not declared.secret_field:
        return None
    if scope_for(manifest) != SCOPE_PER_CONNECTION:  # pragma: no cover — one arm today
        return None
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    # Imported here rather than at module import: `services` imports the
    # registry, and the registry is this module's own import.
    from apps.integrations import services

    connection = services.connection_for(tenant_id, manifest.key)
    if connection is None:
        return None
    stored = services.credential_secrets(connection).get(str(declared.secret_field), "")
    if not stored:
        return None
    return InboundSecret(
        connection=connection, secret=str(stored), scope=SCOPE_PER_CONNECTION
    )


__all__ = [
    "SCOPE_PER_CONNECTION",
    "SCOPE_PLATFORM",
    "SECRET_SCOPES",
    "InboundSecret",
    "scope_for",
    "secret_for",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 lane 4 (the inbound door's verification styles); PO ruling 2026-09-17 *"our account - we will provdie servcie to utilities as platform provider"*
# generated: 2026-09-17 by the CR-115-BRC05 lane-4 build lane
# checklist: A✔ B=n/a(no screen — a vendor POSTs to the door this serves) C✔ D=n/a(no route of its own) E=n/a F✔ G✔ H=pending(it reads a credential; the 🔒 half is inbound.py's verifier and the review-ledger row is filed with it)
# gates: pytest tests/test_cr115_inbound_verification.py · G77 (no provider-key branch) · G6 (no cross-module model import)
# exceptions: `scope_for` has ONE arm and says so — the platform-level store is named and not built, because the subuser-versus-shared question is unruled
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
