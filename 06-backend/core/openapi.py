# ── Trace ──────────────────────────────────────────────
# Component: BE-11 OpenAPI publisher support (B13 §3, TD-19) — the one schema hook the
#            2026-08-10 path-tenancy ruling needs.
# Contract:  A11 + 11b as ratified by A11 Addendum r2 (the CI-diff baseline) · FI-01
#            (the typed frontend client is GENERATED from this schema) ·
#            PO ruling 2026-08-10 (API routes are /api/{tenant}/…)
# Rules:     BR-TEN-003 (the tenant is resolved server-side, never taken from a view kwarg)
# Tests:     06-backend/tests/test_be11_openapi.py
# Impacts:   06-backend/openapi/schema.json (the committed snapshot CI diffs against) ·
#            07-frontend FI-01 client generation
# ───────────────────────────────────────────────────────
"""Schema-generation support for BE-11.

config/urls.py mounts the tenant-scoped API behind a NON-CAPTURING regex, so
that no view is handed a `tenant=` kwarg it must not read (BR-TEN-003 — the
tenant is the middleware's to resolve, once, from the path). drf-spectacular
renders a path from the pattern it finds, and a non-capturing character class
renders literally:

    /api/[-a-zA-Z0-9_]/assets          ← what the router honestly says
    /api/{tenant}/assets               ← what the contract says, and what FI-01
                                         must generate a client from

This hook is the ONE place that translates between them. It is cosmetic to the
server and load-bearing to the client, which is exactly why it lives in its own
module with its own test rather than as a lambda in settings.
"""

from typing import Any

#: The literal drf-spectacular renders for config/urls.py's tenant mount. Kept
#: as a constant so a change to the router that forgets this file fails the
#: BE-11 test loudly instead of silently publishing a broken path.
TENANT_MOUNT_LITERAL = "/api/[-a-zA-Z0-9_]/"
TENANT_MOUNT_PARAMETER = "/api/{tenant}/"


def name_the_tenant_segment(endpoints: list[Any], **_kwargs: Any) -> list[Any]:
    """PREPROCESSING_HOOKS entry: give the tenant segment its contract name."""
    return [
        (path.replace(TENANT_MOUNT_LITERAL, TENANT_MOUNT_PARAMETER, 1), regex, method, callback)
        for path, regex, method, callback in endpoints
    ]


def key_security_schemes() -> dict[str, dict[str, Any]]:
    """Every credential a door proves itself with that is NOT an authenticator.

    ⚠ **THE IMPORT IS DEFERRED AND THAT IS A REAL CONSTRAINT, NOT A STYLE
    CHOICE** — the same one `integrations.machine_auth.crypto_context()`
    records. This module is named in `SPECTACULAR_SETTINGS`, which
    `config/settings/base.py` builds at settings-import time, long before the
    app registry is ready; a module-level `from apps.integrations import
    partner_api` here would not load at all.

    ⚠ **THE DEFINITIONS ARE IMPORTED, NEVER RETYPED, AND THAT IS THE WHOLE
    REASON THIS FUNCTION EXISTS.** A scheme NAME spelled one way on the
    operation and another way in `components.securitySchemes` produces a
    document that is invalid OpenAPI, that every client generator treats
    differently, and that nothing in this repository would have gone red over.
    It is `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`'s lesson at the contract
    layer: one spelling, in the file that owns the door.
    """
    from apps.integrations import inbound_api, partner_api

    # `DEF-INT-10020` — plus one scheme per header a PUBLISHED inbound door
    # reads (US Payments: `password`), derived from the manifests.
    return {
        partner_api.PARTNER_KEY_SCHEME_NAME: partner_api.PARTNER_KEY_SECURITY_SCHEME,
        **inbound_api.published_key_schemes(),
    }


def declare_the_key_schemes(result: Any, **_kwargs: Any) -> Any:
    """POSTPROCESSING_HOOKS entry: define every scheme an operation NAMES.

    ADDED 2026-09-24 with `DEF-INT-6529`. drf-spectacular declares a security
    scheme only when it can resolve one off a view's AUTHENTICATORS, and the
    partner surface deliberately has none — a partner presents a key, never a
    session cookie, so `authentication_classes = []` is what makes that door a
    door. The consequence was that 23 partner operations, `POST
    /api/partner/v1/make-payment/` among them, published `security: [{}]`,
    which in OpenAPI means **this endpoint needs no credentials**. The door
    was shut the whole time; the contract said otherwise.

    ⚠ **IT DECLARES ONLY WHAT IS REFERENCED, AND THAT IS DELIBERATE.** A
    scheme left defined after the last operation stopped naming it is exactly
    the kind of stale claim nothing re-checks (`CLAUDE.md`, hard-won law 1),
    and a scheme defined "just in case" would go on describing a door that had
    been rebuilt under it. Reading the document back means the definitions and
    the requirements cannot disagree: if every partner view lost its
    decorator, `partnerKey` would vanish from the components too.

    ⚠ **IT NEVER OVERWRITES.** A scheme drf-spectacular resolved from a real
    authenticator — `sessionCookie`, from `apps/identity/auth.py` — is the
    authoritative one; this hook fills gaps and settles nothing.
    """
    referenced = {
        name
        for operations in (result.get("paths") or {}).values()
        for operation in operations.values()
        if isinstance(operation, dict)
        for requirement in (operation.get("security") or [])
        for name in requirement
    }
    if not referenced:
        return result
    declared = result.setdefault("components", {}).setdefault("securitySchemes", {})
    for name, definition in key_security_schemes().items():
        if name in referenced and name not in declared:
            declared[name] = definition
    return result


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-01@87ece49 (path-tenancy lane co-packet — the routing half of the PO ruling 2026-08-10; BE-11 is the component it serves)
# generated: 2026-08-10 by story-coder (path-tenancy lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — FI-01 regeneration is the frontend lane's) F✔ G✔ H=n/a(not a 🔒 file)
# gates: ruff✔ black✔ · pytest tests/test_be11_openapi.py 4/4✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: the schema's `tenant` path parameter carries no type/description block — drf-spectacular only knows the segment exists because this hook renamed it; a proper OpenAPI parameter object needs an A11 Addendum row naming it, which does not exist yet (REPORTED)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
