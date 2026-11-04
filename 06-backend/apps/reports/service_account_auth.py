# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 · `P2.20` — BI tier 1, the authentication half.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping — RLS FORCE, `app.tenant_id`,
#          no cross-tenant queryset) · hard-won law 1 · brief §7.8 p88
#          (*"a BI tool cannot see anything a signed-in person could not, and
#          RLS is doing the work"*)
# Tests:   06-backend/tests/test_rep_p2_20_service_accounts.py
# ───────────────────────────────────────────────────────
"""`Authorization: Bearer sbh_rpt_…` → a tenant, a principal, and nothing else.

⚠ **THE PATH SAYS WHICH TENANT. THE TOKEN ONLY SAYS WHO.** That is the whole
shape of this class and it was NOT the first design — the first one resolved the
tenant FROM the token, and `10-scripts/rep_p2_20_service_account_rls_proof.py`
refused it on real PostgreSQL before it reached a test:

    FAIL  5 · brazosbend's token resolves to brazosbend — resolved to nothing

**That failure is the policy working.** A lookup outside a tenant context runs
with `app.tenant_id` unset; the policy's `tenant_id = NULLIF(current_setting(…))`
is then NULL, which is not TRUE, so `report_service_accounts` yields ZERO rows
and there is nothing to authenticate against. The only way to make the first
design work would have been to read the credential OUTSIDE row-level security —
setting the tenant GUC from an unauthenticated header — which is precisely the
hole this table exists to keep shut. CLAUDE.md hard-won law 14's shape: the
default suite is SQLite, which has no RLS at all, and would have passed the
broken version green on every machine.

**So the token is looked up EXACTLY as a screen's data is: inside the tenant
context `TenantContextMiddleware` has already set from the `/api/{tenant}/…`
path segment.** Three things follow, and all three are better than the version
the proof rejected:

  1. **There is no bypass anywhere.** Every read this class makes is under the
     same policy as every other read in the product.
  2. **The cross-tenant refusal is FREE and cannot be forgotten.** A token
     belonging to tenant B, presented on tenant A's path, is not *found and then
     rejected* — it is NOT THERE, because RLS does not show it. The first design
     compared two slugs in Python and got the same answer only while somebody
     remembered to write the comparison.
  3. **It is the same rule `apps/identity/auth.py` applies to a session**, which
     is bound to one tenant and answers 404 on another's path (the acceptance
     criterion of the 2026-08-10 path-tenancy ruling).

⚠ **AN UNKNOWN TOKEN AND A FOREIGN TOKEN ARE THEREFORE THE SAME REFUSAL**, which
is what HR-1 wants: neither the status nor the body can be used to ask *does
this token exist somewhere else in this deployment?*
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from rest_framework import exceptions as drf_exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.throttling import SimpleRateThrottle

from . import service_accounts

logger = logging.getLogger("smartbillhub.reports")

SCHEME = "Bearer"


class ServiceAccountPrincipal:
    """What `request.user` becomes for a machine caller.

    ⚠ **IT IS NOT A `User` AND MUST NEVER PRETEND TO BE ONE.** Borrowing a user
    identity is what `BR-RBS-015` forbids for runbooks and what §7.8 forbids
    here in its own words — *"a person's password in a BI config file"*. So this
    object answers `is_authenticated` truthfully and carries **no** `role`: a
    permission class that asks for one gets an attribute error at build time
    rather than a quiet `None` that compares equal to nothing and denies for the
    wrong reason.
    """

    #: DRF reads this. It is the only thing this class shares with a person.
    is_authenticated = True

    def __init__(self, account: Any) -> None:
        self.account = account
        self.id = None
        self.service_account_id = getattr(account, "id", None)
        self.full_name = getattr(account, "name", None)

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return f"service account {self.full_name!r}"


class ReportServiceAccountAuthentication(BaseAuthentication):
    """`Authorization: Bearer <token>` for the report API, and for nothing else.

    Returns `None` — *"not my business"* — for a request carrying no bearer
    token or a bearer token that is not ours, so the session authentication
    behind it still runs and a browser is unaffected. It raises only when a
    token IS ours and IS wrong, because at that point silence would make an
    expired credential look like an anonymous request and a BI tool would be
    told it needs to sign in.
    """

    def authenticate(self, request: Any):
        header = request.META.get("HTTP_AUTHORIZATION", "") or ""
        parts = header.split(maxsplit=1)
        if len(parts) != 2 or parts[0] != SCHEME:
            return None
        token = parts[1].strip()
        if not token.startswith(service_accounts.TOKEN_PREFIX):
            # Somebody else's bearer scheme. Not ours to refuse.
            return None

        from apps.reports.models import ReportServiceAccount

        # ⚠ **THE TENANT CONTEXT IS ALREADY SET, FROM THE PATH** — see the
        # module docstring. If it is not, this request named no tenant and there
        # is no tenant-scoped credential to find; `require_tenant` in the view
        # will say so properly, and authenticating here would be answering a
        # question nobody asked.
        if getattr(request, "tenant_id", None) is None:
            raise drf_exceptions.AuthenticationFailed()

        # BY HASH, ON THE GLOBALLY UNIQUE COLUMN, UNDER RLS. Never by prefix,
        # never a scan, and never over anything a caller can widen. A token
        # belonging to another tenant is not visible here AT ALL — that is the
        # policy and not a comparison this code has to remember to make.
        account = ReportServiceAccount.objects.filter(
            token_hash=service_accounts.hash_token(token)
        ).first()
        if account is None or not service_accounts.is_live(account):
            # ⚠ ONE REFUSAL FOR THREE CASES — unknown, revoked, and belonging to
            # another tenant — and it says which of the three it was to nobody.
            # A refusal that distinguished them would tell a holder that their
            # token was once real, or that it is real somewhere else.
            raise drf_exceptions.AuthenticationFailed()

        return ServiceAccountPrincipal(account), token


class ServiceAccountThrottle(SimpleRateThrottle):
    """`P2.20`: *"Revocable, audited, rate-limited"* — the third of the three.

    ⚠ **THE BUCKET IS THE CREDENTIAL, NOT THE ADDRESS AND NOT THE TENANT.** A
    BI tool calls from one machine, so an address bucket would be one bucket for
    every account a utility holds — revoke one and the others would still wear
    its spike. A tenant bucket has the same fault one level up. Counting per
    credential is what makes *"revocable without touching a person"* true of the
    throttle as well as of the row: retiring a runaway board pack stops ITS
    traffic and nobody else's.

    ⚠ **IT COUNTS NOTHING FOR A BROWSER.** `get_cache_key` returns `None` for
    any request that is not a service account, and DRF reads `None` as *not
    throttled here* — so a person's session is unaffected and this class can sit
    on a shared route.

    ⚠ **NOT AN `NFR-5` CAP.** `NFR-5` forbids a ceiling that would have to be
    REMOVED when T4 arrives — a per-tenant account maximum, a row cap, an
    unpaginated list. A request RATE on one credential is a property of the
    credential: a larger utility is given a larger number in settings, or a
    second account, and neither is a migration.
    """

    scope = "report_service_account"

    def get_rate(self) -> str:
        return getattr(
            settings,
            "REPORT_SERVICE_ACCOUNT_RATE",
            f"{service_accounts.RATE_PER_MINUTE}/min",
        )

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        principal = getattr(request, "user", None)
        if not isinstance(principal, ServiceAccountPrincipal):
            return None
        ident = getattr(principal, "service_account_id", None)
        if ident is None:  # pragma: no cover - a principal always carries one
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(ident)}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.20 (05-prototype/09 Reports Build Brief.pdf p88, read as an image per B14 rule 42)
# screens: none — tier 1 is an API
# generated: 2026-09-27 by lane REP-P2-TAIL
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the cross-tenant case was run against this class with the slug check removed and returned another tenant's rows
# exceptions: (1) the token lookup runs before any tenant context exists and must; the docstring states why that is the only honest shape and what bounds it
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (🔒 a credential + RLS path)
# ──────────────────────────────────────────────────────────
