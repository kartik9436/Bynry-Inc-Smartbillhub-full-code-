# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — `C14`: a page-security policy generated
#           from the registered browser operations
# Rules:    BR-INT-048 · hard-won law 3 (defaults fail closed) · CLAUDE.md hard
#           rule 1 (the tenant comes from the resolved context, never from a
#           header a caller controls)
# Tests:    06-backend/tests/test_us_int_042_gis.py
# Impacts:  config/settings/base.py (one MIDDLEWARE line) ·
#           apps/integrations/page_policy.py (the generator)
# ───────────────────────────────────────────────────────
"""The generated policy, on every API response.

⚠ **THIS IS THE SECOND OF THE TWO PLACES, AND IT IS NOT THE IMPORTANT ONE.** A
browser enforces a Content-Security-Policy against the DOCUMENT it arrived
with; a header on a JSON response governs nothing it will ever fetch. The
enforcing header is set by `07-frontend/server.mjs` on `index.html`, and
`page_policy.py`'s docstring records the reasoning for both.

What this one buys is real but smaller: an API response that carries the same
generated string is one a test, a walkthrough and a support call can read
without a browser in the loop, and it means a client hitting the API directly
(a partner tool, a script) is not served under a weaker policy than the app.

⚠ **IT FAILS CLOSED.** A request with no resolved tenant — an unauthenticated
call, a platform path with no slug, a 404 — gets `BASE_POLICY`, which is
`'self'` and nothing third-party. The permissive answer has to be earned.

⚠ **AND IT NEVER RAISES.** A middleware that throws turns every response in the
product into a 500. The policy is a hardening header: if it cannot be computed
the response goes out with the base one, which is stricter, not weaker.
"""

from __future__ import annotations

from typing import Any, Callable

HEADER = "Content-Security-Policy"


class PagePolicyMiddleware:
    """Attach the tenant's generated policy to every response."""

    def __init__(self, get_response: Callable[[Any], Any]) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        response = self.get_response(request)
        if HEADER in response:
            # Somebody upstream already decided. Never widen another layer's
            # policy from here.
            return response
        response[HEADER] = _with_app_ancestors(self._policy())
        return response

    @staticmethod
    def _policy() -> str:
        from apps.integrations import page_policy
        from core.tenancy import current_tenant_id

        try:
            tenant_id = current_tenant_id()
        except Exception:  # noqa: BLE001 — no context is a real, ordinary state
            tenant_id = None
        if not tenant_id:
            return page_policy.BASE_POLICY
        try:
            return page_policy.policy_for(tenant_id)
        except Exception:  # noqa: BLE001 — see the docstring: stricter, never 500
            return page_policy.BASE_POLICY


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 story + BR-INT-048 verbatim)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py
# exceptions: two bare `except Exception` — both fail CLOSED to the stricter policy and the docstring says why a raise here would 500 the whole product
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


#: An origin as CORS stores it: scheme and host (and port), nothing after.
_ORIGIN_RE = __import__("re").compile(r"^https?://[A-Za-z0-9.-]+(?::[0-9]{1,5})?$")


def _with_app_ancestors(policy: str) -> str:
    """`DEF-INT-9707` — let the APP frame this API's documents, and nobody else.

    `frame-ancestors 'self'` was written when the app and the API were one
    origin (`DEF-INT-4410`). Since `CR-144-BRC07` they are two hosts, so 'self'
    is the API alone and the app's frames of a bill, a layout preview or a
    portal document were refused (*"refused to connect"*). The origins added
    are EXACTLY `CORS_ALLOWED_ORIGINS` — the app this API already trusts with
    its session — each checked to be a bare origin, never a wildcard, so a
    malformed setting cannot write a new directive into the header.
    """
    from django.conf import settings

    origins = [
        str(o).strip()
        for o in (getattr(settings, "CORS_ALLOWED_ORIGINS", None) or [])
        if _ORIGIN_RE.match(str(o).strip())
    ]
    if not origins:
        return policy
    parts = []
    for part in policy.split(";"):
        piece = part.strip()
        if piece.startswith("frame-ancestors"):
            present = piece.split()[1:]
            piece = " ".join(["frame-ancestors", *present, *[o for o in origins if o not in present]])
        parts.append(piece)
    return "; ".join(parts)
