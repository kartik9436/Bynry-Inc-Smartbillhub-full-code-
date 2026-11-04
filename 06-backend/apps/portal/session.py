# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-021 (🔒, EP-CWP-03) — the session and the account set ·
#           US-CWP-020 (sign in / sign out) · US-CWP-023 (the set is flat)
#           Screens: CWP-015 · CWP-020 · CWP-023
# Rules:    BR-CWP-005 (the tenant is resolved from the FIRST PATH SEGMENT,
#           `app.tenant_id` set and RLS forced, BEFORE the question "who is
#           this" is asked) · BR-CWP-004 (never resolves into a staff role) ·
#           BR-CWP-008 (a session carries a tenant, the person, and a SET of
#           (account, what they may do) — never a customer id on its own) ·
#           BR-CWP-009 (the set is built from EXACTLY TWO SOURCES) ·
#           BR-CWP-010 (every query filtered on BOTH halves, in the query) ·
#           BR-CWP-011 (a portal session must not call a staff route; the guest
#           surface must not reach the portal edge) · BR-CWP-013 (the set is
#           FLAT) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_cwp_020_session.py ·
#           test_us_cwp_023_account_set.py · test_us_cwp_021_pg.py (RLS on
#           real PostgreSQL under the non-superuser probe role — law 14)
# Impacts:  apps/portal/api.py (its only mounting) · config/urls.py
# ───────────────────────────────────────────────────────
"""🔒 THE PORTAL SESSION — a second front door that shares no lock with the first.

HUMAN-OWNED · HUMAN-REVIEW-PENDING (CLAUDE.md 🔒 sensitive paths; row in
12-governance/09-human-review-ledger.md). AI-authored under the PO ruling of
2026-08-09.

THE ORDER OF THE FIRST FOUR LINES OF `authenticate` IS THE WHOLE RULE
--------------------------------------------------------------------
`BR-CWP-005`, verbatim: *"The tenant is resolved from the first path segment,
`app.tenant_id` is set and RLS is forced, **before** the question 'who is this'
is asked."* `TenantContextMiddleware` (BE-01) has already done both by the time
DRF runs authentication, and this class reads `request.tenant_id` — the
RESOLVED id — rather than resolving anything of its own. **A session row is
then read under that tenant's RLS context**, so a session id from another
utility resolves to no row at all rather than to a row this code has to
remember to check.

⚠ **A STALE STAFF COOKIE MUST NOT 401 A VISITOR AND MUST NOT ENTER ANY
CONTEXT.** The portal edge declares `authentication_classes([PortalSession
Authentication])`, which REPLACES the default list rather than adding to it, so
`sbh_session` is never read on a portal route: a person who was signed into the
back office last week and now opens `/pine-hill/portal` is simply not signed
in. That is why this is a class of its own and not a second branch in
`identity.auth`.

⚠ **AND NOTHING IN THIS FILE IMPORTS `apps.identity`.** `BR-CWP-004` is not a
convention here; G91 parses this file and fails the build on the import. The
one thing the portal legitimately reads from identity — the tenant's password
and idle-timeout POLICY — goes through `seams/identity_seam.py`, which may read
`SecurityPolicy` and no other model.

THE ACCOUNT SET, AND WHY THE STORED COLUMN IS NOT THE ANSWER
------------------------------------------------------------
`BR-CWP-009` names **exactly two sources**: the customer-to-account links the
person already holds, and delegate grants somebody else gave them. `BR-CWP-013`
says the result is **FLAT** — a master account over common areas is one more
entry, not a parent, and confers nothing over anybody else's account.

**It is re-derived on every request** (field map §1). `portal_session.account_set`
is kept as the record of what was true at issue, because a dispute about who
could see what is answered by that row — but it never authorises anything. A
stored set that authorised would be a landlord still holding a tenant's bills
a month after the tenancy ended, and the session would have to be revoked by
somebody who noticed.

⚠ **THE SECOND SOURCE IS DECLARED AND EMPTY.** `portal_delegate` is blocked on
`OQ-1396` (how long access may run, and who may revoke it), so `_delegated`
returns nothing today and says so by name. It is a function rather than a
comment so the day the table lands there is one place to fill in, and so that
`US-CWP-023` TC-3's *"four ids and no fifth"* is asserted against the real
composition rather than against a single query that happens to be complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import exceptions as drf_exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from apps.customers import models as customers_models
from apps.portal import models
from apps.portal.seams import identity_seam
from core import errors

#: ⚠ **A DIFFERENT NAME FROM `sbh_session`, AND THAT IS LOAD-BEARING.** Two
#: cookies means a person can be a clerk in one tab and a customer in another
#: without either session standing on the other, and it means a portal id
#: presented on a staff route is not even looked at.
PORTAL_SESSION_COOKIE = "sbh_portal"

#: The permissions an account holder has over their OWN account. The vocabulary
#: is `portal_delegate.permissions`' (field map §1) so a holder's entry and an
#: invited helper's entry are the same shape and a screen reads one rule.
#: ⚠ `close_account`, `change_owner` and `move_out` are NOT here and never are —
#: the field map says a delegate may never hold them, and a login is not the
#: instrument for them either (`CWP-018`'s consequence panel says so out loud).
HOLDER_PERMISSIONS: tuple[str, ...] = ("see", "download", "pay")

#: How long a session lives whatever it is doing — the ceiling, where the idle
#: timeout is the sliding window.
#:
#: ⚠ **THIS WAS A FIXED `12` UNTIL 2026-09-28 AND IS NOW A FALLBACK
#: (`CR-145-BRC08`).** `issue()` reads the utility's own hard limit through
#: `identity_seam.absolute_session_hours`, exactly as the idle check three
#: hundred lines down already read the utility's own inactivity setting. The
#: PO ruled the portal gets NO setting of its own — *"one setting is less for
#: an admin to get wrong"* — so the pair is now consistent instead of one
#: number following the utility and the other ignoring it.
#:
#: ⚠ **NOTHING READS THIS CONSTANT (checked 2026-09-28, backend lane).** This
#: comment used to say it was "the answer for a tenant with no policy row";
#: it is not — `identity_seam.absolute_session_hours` carries its own `12`
#: for that case, and `issue()` reads only the seam. It is kept as a
#: statement of the number a utility with no Security row gets, and changing
#: it changes nothing: change the column default and the seam's fallback.
ABSOLUTE_LIFETIME_HOURS = 12


@dataclass(frozen=True)
class AccountEntry:
    account_id: str
    permissions: tuple[str, ...]
    source: str  # "holder" | "delegate" — which of BR-CWP-009's two sources

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "permissions": list(self.permissions),
            "source": self.source,
        }


@dataclass(frozen=True)
class PortalPrincipal:
    """Who is signed in. **Not a `User`, and it does not pretend to be one.**

    `is_authenticated` is False on purpose: DRF's `IsAuthenticated` and every
    staff permission class in this product read that attribute, and a principal
    that answered True would satisfy them. `IsPortalCustomer` below reads
    `is_portal_customer` instead, which nothing in the staff app has ever heard
    of — so a portal principal reaching a staff view is refused by the staff
    view's own permission class rather than by a check somebody remembered to
    add (`BR-CWP-011`).
    """

    session_id: str
    credential_id: str
    customer_id: str
    tenant_id: Any
    accounts: tuple[AccountEntry, ...]

    is_authenticated = False
    is_portal_customer = True

    @property
    def account_ids(self) -> tuple[str, ...]:
        return tuple(entry.account_id for entry in self.accounts)

    def may(self, account_id: Any, permission: str) -> bool:
        wanted = str(account_id)
        for entry in self.accounts:
            if entry.account_id == wanted:
                return permission in entry.permissions
        return False


class IsPortalCustomer(BasePermission):
    """The portal edge's ONLY permission class. Reads `is_portal_customer`."""

    message = "Sign in to see this."

    def has_permission(self, request: Any, view: Any) -> bool:
        return bool(getattr(getattr(request, "user", None), "is_portal_customer", False))


# ═══════════════════════════════════════════════════════════════════════════
# The account set — BR-CWP-009's two sources, re-derived on every read
# ═══════════════════════════════════════════════════════════════════════════


def _held(tenant_id: Any, customer_id: Any) -> list[AccountEntry]:
    """Source one: the accounts this customer is linked to (`customer_accounts`).

    ⚠ **A TERMINAL ACCOUNT IS EXCLUDED**, the same reading `customers` itself
    uses (`BR-CUS-055`) and the same one the deleted `premises_is_occupied` took. A closed
    account is still the customer's history, and `US-CWP-032`'s final bill is
    wave J's job through a different door; what it is not is something to
    re-scope every tab to.
    """
    rows = (
        customers_models.CustomerAccount.objects.filter(
            tenant_id=tenant_id, customer_id=customer_id
        )
        .exclude(account__status__behavior_class="terminal")
        .values_list("account_id", flat=True)
    )
    return [
        AccountEntry(account_id=str(account_id), permissions=HOLDER_PERMISSIONS, source="holder")
        for account_id in rows
    ]


def _delegated(tenant_id: Any, credential_id: Any) -> list[AccountEntry]:
    """Source two: grants somebody else gave this login — `portal_delegate`.

    ⚠ **EMPTY TODAY, AND BY NAME RATHER THAN BY OMISSION.** The table is blocked
    on `OQ-1396` (`03-field-map.md` §1: *"How long access may run, and who may
    revoke it"*), so there is nothing to read. This function exists so the
    composition below is visibly the two sources `BR-CWP-009` names, and so the
    day the table lands there is exactly one place to fill in.
    """
    return []


def account_set(tenant_id: Any, *, customer_id: Any, credential_id: Any) -> tuple[AccountEntry, ...]:
    """`BR-CWP-009` and `BR-CWP-013` in six lines: two sources, one FLAT list.

    Sorted by account id so the set a screen renders and the set a test asserts
    are in the same order every time, and de-duplicated on the account so a
    person who both holds an account and was delegated it appears once with the
    union of what they may do — never twice, which would double a landlord's
    total on `CWP-023`.
    """
    merged: dict[str, AccountEntry] = {}
    for entry in _held(tenant_id, customer_id) + _delegated(tenant_id, credential_id):
        existing = merged.get(entry.account_id)
        if existing is None:
            merged[entry.account_id] = entry
            continue
        merged[entry.account_id] = AccountEntry(
            account_id=entry.account_id,
            permissions=tuple(sorted(set(existing.permissions) | set(entry.permissions))),
            source=existing.source,
        )
    return tuple(merged[key] for key in sorted(merged))


# ═══════════════════════════════════════════════════════════════════════════
# Issuing, revoking, and reading a session back
# ═══════════════════════════════════════════════════════════════════════════


def issue(tenant_id: Any, credential: Any, *, device_fingerprint: str | None = None):
    """One session row. The id IS the opaque cookie value — the same disposition
    `identity` took for the staff table (US-IDN-003 §4: *"session ids UUID v7;
    tokens opaque, httpOnly"*), so there is no second secret to leak."""
    now = timezone.now()
    entries = account_set(
        tenant_id, customer_id=credential.customer_id, credential_id=credential.pk
    )
    return models.PortalSession.objects.create(
        tenant_id=tenant_id,
        portal_credential_id=credential.pk,
        account_set=[entry.as_dict() for entry in entries],
        last_seen_at=now,
        # `CR-145-BRC08` — the utility's hard limit, through the one seam this
        # module may read `identity` through (`BR-CWP-012`, G91).
        expires_at=now + timedelta(hours=identity_seam.absolute_session_hours(tenant_id)),
        device_fingerprint=device_fingerprint or None,
    )


def revoke(session_row: Any) -> None:
    session_row.revoked_at = timezone.now()
    session_row.save(update_fields=["revoked_at"])


def purge_dead_sessions(tenant_id: Any) -> int:
    """Delete this utility's expired and signed-out portal sessions. Returns how many.

    ⚠ **THE CALLER IS `identity`'S NIGHTLY SWEEP AND IT DOES NOT IMPORT THIS
    MODULE (`CR-145-BRC08` task B10).** `apps/identity/session_cleanup.py`
    resolves this function BY NAME at call time, so the DELETE on
    `portal_session` is executed by the module that owns the table — B1's
    boundary rule — and no import statement binds identity to the portal's
    models. The reverse direction is not available at all: `G91` refuses any
    file under `apps/portal/` that imports `apps.identity` except the one
    declared seam, so the sweep has to come to us.

    ⚠ **TWO POSITIVE CONDITIONS, NEVER THE NEGATION OF *live*.** Expired
    (`expires_at` is past) or signed out (`revoked_at` is set). A `NOT (…)`
    over three nullable columns is one `OR` away from matching every row in
    the table, and this is a DELETE on the rows customers are signed in with.

    ⚠ **AN IDLE SESSION IS NOT DELETED HERE.** Idleness is a sliding
    comparison made per request in `PortalSessionAuthentication` against the
    utility's inactivity setting; a row past that window is still a row the
    hard limit has not caught up with. It leaves through `expires_at`.

    The caller has already entered this tenant's context, so the filter is
    belt and braces over RLS rather than instead of it.
    """
    now = timezone.now()
    rows = models.PortalSession.objects.filter(tenant_id=tenant_id)
    dead = (
        rows.filter(expires_at__lt=now) | rows.filter(revoked_at__isnull=False)
    ).distinct()
    deleted, _by_model = dead.delete()
    return int(deleted)


def revoke_all(tenant_id: Any, credential_id: Any) -> int:
    """*Sign out everywhere* (`CWP-024`). Returns how many were live."""
    live = models.PortalSession.objects.filter(
        tenant_id=tenant_id, portal_credential_id=credential_id, revoked_at__isnull=True
    )
    count = live.count()
    live.update(revoked_at=timezone.now())
    return count


class PortalSessionAuthentication(BaseAuthentication):
    """DRF authentication backed by `portal_session`, and by nothing else.

    Returns `(PortalPrincipal, session_row)` or None. **Never raises for an
    absent cookie** — an anonymous caller on the portal edge is refused by
    `IsPortalCustomer` with the ordinary *sign in* answer, not by an exception
    that would distinguish "you have a broken session" from "you have none".
    """

    def authenticate(self, request):
        raw = request.COOKIES.get(PORTAL_SESSION_COOKIE)
        if not raw:
            return None

        # BR-CWP-005 — the tenant is ALREADY resolved and `app.tenant_id` is
        # ALREADY set (BE-01, config/settings MIDDLEWARE). This reads it; it
        # never resolves one, because a resolver here would be a second answer
        # to "which utility is this" and the two could disagree.
        tenant_id = getattr(request, "tenant_id", None)
        if tenant_id is None:
            # No tenant in the path means this is not a portal address at all.
            # 404 rather than 401: the same body an unknown utility gets, so a
            # probe cannot map which slugs exist (BR-TEN-003 / HR-1).
            raise errors.deny_as_not_found(br_ref="BR-CWP-005")

        session = models.PortalSession.objects.filter(pk=_uuid_or_none(raw)).first()
        if session is None or session.revoked_at is not None:
            raise drf_exceptions.AuthenticationFailed()
        if str(session.tenant_id) != str(tenant_id):
            # One tenant per session. The RLS context above already makes this
            # unreachable on PostgreSQL; the explicit check is what keeps the
            # law true on the SQLite unit tier, exactly as every selector in
            # this product filters on tenant as well as trusting the policy.
            raise errors.deny_as_not_found(br_ref="BR-CWP-005")

        now = timezone.now()
        idle_limit = identity_seam.session_timeout_minutes(tenant_id) * 60
        last_seen = session.last_seen_at or session.issued_at
        if now > session.expires_at or (now - last_seen).total_seconds() > idle_limit:
            raise drf_exceptions.AuthenticationFailed()

        credential = models.PortalCredential.objects.filter(
            tenant_id=tenant_id, pk=session.portal_credential_id
        ).first()
        if credential is None or credential.status == models.CREDENTIAL_DISABLED:
            raise drf_exceptions.AuthenticationFailed()

        session.last_seen_at = now
        session.save(update_fields=["last_seen_at"])

        principal = PortalPrincipal(
            session_id=str(session.pk),
            credential_id=str(credential.pk),
            customer_id=str(credential.customer_id),
            tenant_id=tenant_id,
            # BR-CWP-009 — RE-DERIVED, never read off the row. See the module
            # docstring for what a stored set that authorised would cost.
            accounts=account_set(
                tenant_id, customer_id=credential.customer_id, credential_id=credential.pk
            ),
        )
        return (principal, session)


def _uuid_or_none(raw: str):
    import uuid

    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        # A cookie holding anything but a uuid is a forged or a stale value; it
        # resolves to no row, which is the same answer as an unknown session.
        return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-020@c05e4dd4 · US-CWP-021@c05e4dd4 · US-CWP-023@c05e4dd4 (EP-CWP-03 stories + BR-CWP-004..013 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(api.py) E✔(PortalShell) F✔ G✔ H=PENDING(🔒 sessions — ledger row 09-human-review-ledger.md, plain English with the figure: a defeated portal session reaches ONE login's flat set of accounts — Maria's one, the landlord's four — and no staff route at all)
# gates: G91 (no apps.identity import here) · G81/G84 (declared in write_points.py with the one model it writes) · pytest tests/test_us_cwp_020_session.py tests/test_us_cwp_023_account_set.py · tests/test_us_cwp_021_pg.py on PostgreSQL 16
# exceptions: (1) `_delegated` is EMPTY and says so — portal_delegate is blocked on OQ-1396. (2) `PortalPrincipal.is_authenticated` is False deliberately, so a portal principal cannot satisfy a staff permission class.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
