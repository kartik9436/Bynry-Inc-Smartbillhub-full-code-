# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision logs *"Staff invitation
#           email: a one-time sign-in link, not a password; six answers"*,
#           *"Account-access emails are sent instantly, at the highest
#           priority"* and *"Account-access emails: languages via template
#           variants, and 'don't do any hardcoding'"*
# Rules:    BR-IDN-021 (SUPERSEDED for invitations and resets, 2026-10-22) ·
#           BR-IDN-022/023 (the on-screen temporary password — UNCHANGED and
#           issued beside the link) · BR-IDN-025 (password rules; the link's
#           life is now a Security setting seeded at the same 7 days) ·
#           BR-IDN-011 (a completed set-password ACTIVATES an invited
#           membership) · BR-IDN-002 (one generic refusal) · BR-IDN-005 ·
#           CLAUDE.md hard rule 1 · rule 7 · hard-won laws 3 and 14
# Tests:    06-backend/tests/test_cr188_staff_invite_email.py (+ `_pg`)
# Impacts:  apps/identity/api.py (UsersView.post, UserTempPasswordView,
#           UserResendInvitationView, PasswordLinkCheckView/CompleteView) ·
#           apps/identity/seams/notifications_seam.py · services.change_password
#           (voids live links) · services.issue_temp_password (voids them too)
# ───────────────────────────────────────────────────────
"""🔒 A STAFF MEMBER'S ONE-TIME SIGN-IN LINK — issue, email, check, spend.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — credentials are a 🔒 identity path. AI-
authored 2026-10-22 under the PO ruling of 2026-08-09 (*"AI will do it; we will
review it later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT THE PO RULED (answers 1, 4, 5)
──────────────────────────────────
*Create user*, *Reset temp password* and *Resend invitation* each still put a
temporary password on screen, exactly as before (*"we will keep exsisting
functionality as it is"*) — **and** now email a ONE-TIME SIGN-IN LINK, never a
password. The link opens `/{tenant}/set-password`, where the person chooses
their own password under the utility's rules.

THE TOKEN
─────────
* 256 random bits (`secrets.token_urlsafe(32)`); only its SHA-256 digest is
  stored (`password_links.token_hash`, RLS + FORCE). A dump opens nothing.
* Valid for the utility's `password_link_valid_days` (Settings → Security,
  seeded 7 — BR-IDN-025's figure). Single use.
* VOID when a newer link is issued, when the temporary password is reset, and
  when the password is changed by ANY route — a link left live after the person
  chose a password would let whoever reads that mailbox later choose another.

THE PUBLIC DOOR (`auth/password-link/check`, `/complete`)
─────────────────────────────────────────────────────────
Unknown, expired, spent, voided, or for a deactivated login: ONE refusal,
`errors.identity.password_link_not_accepted`, the BR-IDN-002 posture — a
refusal that told them apart would tell a guesser which tokens exist. A 409
rather than a 401, because the front end reads a 401 as *your session ended*.

THE EMAIL NEVER HOLDS UP THE USER
─────────────────────────────────
`email_access_link` NEVER raises and is called AFTER the user row is written: an
admin whose utility has no mail provider still creates the user and shares the
on-screen password (`not_sent` + reason). The queue call is inside a SAVEPOINT
in the seam, because on PostgreSQL a caught failure would otherwise abort the
caller's own transaction (hard-won law 14).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.db import transaction

from apps.identity import selectors, services
from apps.identity.models import PasswordLink, TenantMembership, User
from apps.identity.seams import notifications_seam
from core import audit as core_audit
from core import errors, public_origin

#: The route the link opens, relative to the tenant — the front end's
#: `SET_PASSWORD_ROUTE` (`07-frontend/src/features/identity/SignInPage.tsx`).
SET_PASSWORD_SEGMENT = "set-password"
TOKEN_PARAM = "token"
TOKEN_BYTES = 32

LINK_NOT_ACCEPTED_MESSAGE_KEY = "errors.identity.password_link_not_accepted"

STATUS_QUEUED = "queued"
STATUS_NOT_SENT = "not_sent"
REASON_NO_EMAIL = "no_email_address"
REASON_NO_PUBLIC_ADDRESS = "public_address_not_configured"
REASON_UNAVAILABLE = "email_unavailable"


def hash_token(plaintext: str) -> str:
    """SHA-256 hex. 256 random bits: nothing to guess, so no slow KDF."""
    return hashlib.sha256(str(plaintext).encode("utf-8")).hexdigest()


def link_valid_days(tenant_id: Any) -> int:
    """The utility's setting (PO 2026-10-22, *"don't do any hardcoding"*)."""
    return int(selectors.security_policy_values(tenant_id)["password_link_valid_days"])


def void_links(user: User, *, reason: str, now: Any = None) -> int:
    """Every live link of this login, voided at once. Returns how many."""
    moment = now or services._now()
    return PasswordLink.objects.filter(
        user_id=user.id, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=moment, revoked_reason=reason)


def issue_link(*, actor: Any, user: User, purpose: str) -> tuple[PasswordLink, str]:
    """A NEW link for this login; every earlier live one is void. The plaintext
    is returned ONCE and never stored. Audited (hard rule 7)."""
    now = services._now()
    void_links(user, reason=PasswordLink.REVOKED_SUPERSEDED, now=now)
    plaintext = secrets.token_urlsafe(TOKEN_BYTES)
    row = PasswordLink.objects.create(
        tenant_id=user.tenant_id,
        user=user,
        purpose=purpose,
        token_hash=hash_token(plaintext),
        issued_at=now,
        expires_at=now + timedelta(days=link_valid_days(user.tenant_id)),
        issued_by=core_audit.actor_user_id(actor),
    )
    core_audit.money_action(
        actor,
        "auth.password_link_issued",
        "user",
        user.id,
        after={"purpose": purpose, "expires_at": row.expires_at.isoformat()},
    )
    return row, plaintext


def _tenant_facts(tenant_id: Any) -> tuple[str, str]:
    """(slug, name) — the registry is RLS-exempt by B2 §3 (`native` reads it too)."""
    from apps.tenancy.models import Tenant

    row = Tenant.objects.filter(pk=tenant_id).values_list("subdomain", "name").first()
    return (str(row[0]), str(row[1] or "")) if row else ("", "")


def _answer(status: str, reason: str | None = None, *, email: str = "") -> dict[str, Any]:
    return {"status": status, "reason_code": reason, "email": email or None}


def email_access_link(*, actor: Any, user: User, purpose: str) -> dict[str, Any]:
    """Issue a link and queue the email for it — or say exactly why not.

    Returns `{"status": "queued" | "not_sent", "reason_code", "email"}` for the
    admin's screen. NEVER raises. Order of the questions is the order an admin
    can act on: no address on the user → no public address on this server →
    email cannot leave (no provider / status unknown / switched off) → queued.
    """
    email = (user.email or "").strip()
    try:
        if not email:
            outcome = _answer(STATUS_NOT_SENT, REASON_NO_EMAIL)
        else:
            slug, utility_name = _tenant_facts(user.tenant_id)
            if public_origin.public_app_link(f"/{slug}/{SET_PASSWORD_SEGMENT}") is None:
                outcome = _answer(STATUS_NOT_SENT, REASON_NO_PUBLIC_ADDRESS, email=email)
            else:
                unreachable = notifications_seam.email_reachability()
                if unreachable is not None:
                    outcome = _answer(STATUS_NOT_SENT, unreachable, email=email)
                else:
                    row, plaintext = issue_link(actor=actor, user=user, purpose=purpose)
                    # The secret in the FRAGMENT, never the query (decision
                    # log 2026-10-22): no server or proxy log ever holds it.
                    link = public_origin.public_app_link(
                        f"/{slug}/{SET_PASSWORD_SEGMENT}", fragment={TOKEN_PARAM: plaintext}
                    )
                    queued = notifications_seam.queue_access_email(
                        kind=purpose,
                        link_id=row.id,
                        email=email,
                        staff_name=user.full_name or "",
                        username=email,
                        utility_name=utility_name,
                        sign_in_link=link or "",
                        expires_at=row.expires_at,
                        actor=actor,
                    )
                    outcome = _answer(
                        queued.get("status") or STATUS_NOT_SENT,
                        queued.get("reason"),
                        email=email,
                    )
    except Exception:  # noqa: BLE001 — the user is created whatever happens here
        outcome = _answer(STATUS_NOT_SENT, REASON_UNAVAILABLE, email=email)
    action = (
        "user.invitation_emailed" if outcome["status"] == STATUS_QUEUED else "user.invitation_not_emailed"
    )
    try:
        core_audit.money_action(
            actor,
            action,
            "user",
            user.id,
            after={
                "purpose": purpose,
                "email": services._mask_email(email) if email else None,
                "reason": outcome["reason_code"],
            },
        )
    except Exception:  # noqa: BLE001 — pragma: no cover; never block the admin
        pass
    return outcome


def _refused() -> errors.BizError:
    return errors.BizError(
        errors.BIZ_STATE, br_ref="BR-IDN-002", message_key=LINK_NOT_ACCEPTED_MESSAGE_KEY
    )


def _live(tenant_id: Any, token: Any) -> tuple[PasswordLink, User, TenantMembership]:
    text = str(token or "").strip()
    row = None
    if text:
        row = (
            PasswordLink.objects.filter(tenant_id=tenant_id, token_hash=hash_token(text))
            .select_related("user")
            .first()
        )
    now = services._now()
    if row is None:
        services._equalize_timing()
        raise _refused()
    if row.used_at is not None or row.revoked_at is not None or now >= row.expires_at:
        raise _refused()
    membership = selectors.membership_for_user(tenant_id, row.user_id)
    if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
        raise _refused()
    return row, row.user, membership


def check_link(*, tenant_id: Any, token: Any) -> dict[str, Any]:
    """Is this link live? → who it is for and the utility's password rules.
    Does NOT spend it."""
    row, user, _membership = _live(tenant_id, token)
    policy = selectors.security_policy_values(tenant_id)
    return {
        "email": user.email,
        "purpose": row.purpose,
        "utility_name": _tenant_facts(tenant_id)[1],
        "expires_at": row.expires_at.isoformat(),
        "password_policy": {
            "min_length": policy["pw_min_length"],
            "require_mixed": policy["pw_require_mixed"],
            "require_symbol": policy["pw_require_symbol"],
        },
    }


def complete_link(
    *, tenant_id: Any, token: Any, new_password: str, confirm_password: str
) -> User:
    """Spend the link and set the person's OWN password.

    It IS the forced first change (BR-IDN-022): the same `change_password`, so
    the same policy, the same last-5 refusal, every session ended (BR-IDN-005)
    and an invited membership ACTIVATED (BR-IDN-011). ALL OR NOTHING — a
    password the policy refuses rolls back, so a typo never spends the link;
    the spend is a conditional UPDATE so two tabs racing one link get one.
    """
    row, user, _membership = _live(tenant_id, token)
    now = services._now()
    with transaction.atomic():
        spent = PasswordLink.objects.filter(
            pk=row.pk, used_at__isnull=True, revoked_at__isnull=True
        ).update(used_at=now)
        if not spent:
            raise _refused()
        user.must_change_password = True
        services.change_password(
            actor=user, new_password=new_password, confirm_password=confirm_password
        )
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        core_audit.write_row(
            action="auth.password_link_used",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={"purpose": row.purpose},
        )
    return user


__all__ = [
    "check_link",
    "complete_link",
    "email_access_link",
    "issue_link",
    "void_links",
]
