# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the native field app's sign-in, server half
#           (`07-endpoints.md` N24; Security §1/§4; AD-21; rules R105, R113,
#           R115, R127). The client's `field-app/src/security/authApi.ts`
#           `SERVER_GAPS` is the list this answers.
# Rules:    BR-IDN-001/002 (tenant-first, one generic failure) · BR-IDN-006 (a
#           credential is bound to ONE tenant; foreign path ⇒ 404) · BR-IDN-020
#           (allowed addresses) · BR-IDN-025 (lockout, password rules, last-5,
#           7-day first credential) · BR-WRK-043 (one login, one surface) ·
#           hard rule 1 (RLS FORCE) · hard rule 7 (every act audited)
# Tests:    06-backend/tests/test_cr187_native_auth.py (SQLite) ·
#           06-backend/tests/test_cr187_native_auth_pg.py (PostgreSQL 16, RLS)
# Impacts:  apps/identity/api.py (five routes) · apps/identity/native_auth.py
#           (the bearer class) · apps/work (device registry, capture credential)
# ───────────────────────────────────────────────────────
"""The native app's two identity acts: BEARER TOKENS and ACTIVATION.

HUMAN-REVIEW-PENDING — 🔒 identity/credentials, AI-authored 2026-10-21 under
the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*). The review-ledger row is owed by the coordinator (this lane may not
edit shared registers); not RATIFIED without a recorded sign-off.
HUMAN-REVIEW-PENDING again, 2026-10-24, for `DEF-FLD-10580` (beta MQ-006): the
platform-wide code register (`_claim_unique_code`, the savepoint redraw) and
the utility-free lookup door (`lookup_activation_code`). Its own ledger row is
*"MQ-006 (b)"* of 2026-10-24; a sign-off of the 2026-10-21 row does not cover it.

⚠ **ADDITIVE. THE WEB'S COOKIE SESSION IS NOT TOUCHED.** `services.sign_in`
was split into `verify_credentials` + the session half so that both doors run
the SAME lockout, allowed-addresses check, generic failure and surface rule —
one place for each, never two that can drift (hard-won law 5's shape).

WHAT IS RULED AND WHAT IS NOT, SAID PLAINLY (hard-won law 1)
------------------------------------------------------------
* **Access token: one hour.** Design (Security §1, AD-21): *"Short-lived, one
  hour, refreshed whenever there is a signal."*
* **Refresh token: single use, rotated, and its life is THE UTILITY'S FIELD
  CAPTURE LIFE** — `selectors.field_capture_seconds(tenant)`, Settings →
  Security, seeded 7 days. PO 2026-10-21, *"this should come from settings"*
  (decision log *"Field app: the PO corrects four of the ten answers"* item 2).
  The design names no refresh life; it follows the capture credential because
  a refresh token that died sooner would leave a handset holding a capture
  credential it could never renew. **Until 2026-10-21 this was the process
  setting `NATIVE_REFRESH_TOKEN_MAX_AGE_S`; that setting is GONE, not kept as
  an override** — two sources for one life is how the Security tab and the
  handset come to disagree. A change applies to tokens minted AFTER it; a
  refresh token already issued keeps the `expires_at` it was minted with.
* **Activation code: six characters, seven days, single use** (FF-56; `R105`).
  Seven is also `TEMP_PASSWORD_VALID_DAYS`, the signed life of any first
  credential the office hands out (BR-IDN-025).
* **The utility's lockout count (Settings › Security, seed 5) of wrong emails burns a code** (PO 2026-10-22) — mirroring the
  default lockout count; a code is a password-equivalent and is never left open
  to unlimited guessing.

THE SIGNAL THE PHONE READS (`remote-sign-out` in `SERVER_GAPS`)
---------------------------------------------------------------
Every refusal is the ordinary BE-02 envelope. The ones the phone must tell
apart carry **`params.reason`** — a machine token, never a sentence (the words
are the app's own catalogue):

  401 · `code: AUTH-001` · `params.reason: "device_signed_out"`
        the office signed this handset out. Drop the mirror, KEEP the outbox
        (`R115`); a password signs back in.
  401 · `params.reason: "access_token_expired"`   — refresh, it is normal.
  401 · `params.reason: "refresh_token_expired"`  — a password is needed.
  401 · `params.reason: "token_revoked"`          — signed out / reused.
  403 · `message_key: errors.auth.password_change_required`
        · `params.reason: "password_change_required"` — the login holds a
        temporary or expired password; claim it with an activation code.

No new catalogue key is minted: the `message_key` is the existing generic one
for its code, which already resolves in all eleven web catalogues (so
`core.refusal_catalogue` passes), and the reason carries the distinction.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction

from apps.identity import phones, selectors, services
from apps.identity.models import (
    ActivationCode,
    ActivationCodeRegister,
    NativeToken,
    TenantMembership,
    User,
)
from apps.identity.seams import work_seam
from core import audit as core_audit
from core import errors

# ── Lifetimes ────────────────────────────────────────────────────────────────
#: Design, Security §1: *"Short-lived, one hour"*.
ACCESS_TOKEN_TTL = timedelta(hours=1)
#: The seeded refresh life (7 days) — what a utility with no Security row
#: reads. The live value is the tenant's setting; see the docstring.
NATIVE_REFRESH_TOKEN_MAX_AGE_S_DEFAULT = 7 * 24 * 3600
#: FF-56 *"It lasts seven days"*; BR-IDN-025's 7-day first credential.
ACTIVATION_CODE_VALID_DAYS = services.TEMP_PASSWORD_VALID_DAYS
ACTIVATION_CODE_LENGTH = 6
#: No 0/O, 1/I/L — the code is read aloud over a phone or off an email.
ACTIVATION_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
#: `DEF-FLD-10580`: the register's digest context. Changing it makes every code
#: already issued unfindable by the utility-free door — never change it.
ACTIVATION_REGISTER_CONTEXT = "identity.activation-register.v1"
#: Redraws on a collision before giving up (a collision is ~1 in a million).
ACTIVATION_DRAW_ATTEMPTS = 8
#: ⚠ NOT A CONSTANT ANY MORE (PO 2026-10-22, *"this should come from security
#: settings"*): the wrong-email count that cancels a code is the utility's own
#: Settings › Security lockout count (`lockout_max_failed`, 3–10, seed 5) —
#: the same number that locks a password sign-in. This name is the seed only.
ACTIVATION_MAX_FAILED = 5


def activation_max_failed(tenant_id: Any) -> int:
    """The tenant's lockout count from Settings › Security (seed 5)."""
    value = selectors.security_policy_values(tenant_id).get("lockout_max_failed")
    return int(value) if value else ACTIVATION_MAX_FAILED
#: The ticket FF-56 hands to FF-57: thirty minutes to type a password twice.
ACTIVATION_TICKET_MAX_AGE_S = 30 * 60
ACTIVATION_TICKET_SALT = "identity.native.activation-ticket.v1"

# ── Token format ─────────────────────────────────────────────────────────────
#: `sbh_fa_<tenant uuid hex>_<43 url-safe chars>` (access) and `sbh_fr_…`
#: (refresh). The tenant is IN the plaintext so the bearer class can compare it
#: with the path's tenant BEFORE reading a row — the 404 `BR-IDN-006` demands —
#: and then read under that tenant's own RLS context. A tenant id is not a
#: secret; the 256 random bits after it are.
ACCESS_PREFIX = "sbh_fa_"
REFRESH_PREFIX = "sbh_fr_"
TOKEN_BYTES = 32

REASON_SIGNED_OUT = "signed_out"
REASON_DEVICE_SIGNED_OUT = "device_signed_out"
REASON_REFRESH_REUSE = "refresh_reuse"
REASON_PASSWORD_CHANGED = "password_changed"


def refresh_token_max_age_s(tenant_id: Any) -> int:
    """The refresh token's life in seconds — the utility's field capture life
    (Settings → Security, PO 2026-10-21). One read, `selectors`'s."""
    return selectors.field_capture_seconds(tenant_id)


def hash_token(plaintext: str) -> str:
    """SHA-256 hex. 256 random bits: nothing to guess, so no slow KDF."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _mint(prefix: str, tenant_id: Any) -> str:
    return f"{prefix}{uuid.UUID(str(tenant_id)).hex}_{secrets.token_urlsafe(TOKEN_BYTES)}"


def parse_tenant(plaintext: str, prefix: str) -> uuid.UUID | None:
    """The tenant a token names, or None when it is not one of ours."""
    if not plaintext.startswith(prefix):
        return None
    rest = plaintext[len(prefix):]
    tenant_hex, sep, secret = rest.partition("_")
    if not sep or len(tenant_hex) != 32 or not secret:
        return None
    try:
        return uuid.UUID(hex=tenant_hex)
    except ValueError:
        return None


def refusal(reason: str, *, code: str = errors.AUTH_UNAUTHENTICATED) -> errors.AuthError:
    """The one refusal shape the phone reads: the generic key + `params.reason`."""
    return errors.AuthError(code, params={"reason": reason}, br_ref="BR-IDN-006")


def _password_change_required() -> errors.AuthError:
    return errors.AuthError(
        errors.AUTH_PERMISSION_DENIED,
        message_key="errors.auth.password_change_required",
        params={"reason": "password_change_required"},
        br_ref="BR-IDN-022",
    )


def _display_name(user: User) -> str:
    return user.full_name or user.email


# ── The one sign-in field: work email OR phone number ────────────────────────
#: `CR-187-BRC10`, PO 2026-10-21: a technician signs in with their work email
#: OR their phone number, in ONE field. The server decides by SHAPE
#: (`phones.identifier_kind`): a value containing `@` is an email; one that
#: normalises to E.164 is a phone, looked up on `users.phone_e164` — identity's
#: own column, so no other module is read. The utility is already fixed by the
#: path (BR-IDN-001), so a number need only be unique inside it: the same
#: number at two utilities is two people and they never meet.


def email_for_identifier(tenant_id: Any, identifier: Any) -> str:
    """The email `services.verify_credentials` should look up for what was typed.

    An email is returned as typed (trimmed). A phone number is resolved to the
    ONE login at this utility whose `phone_e164` it normalises to.

    ⚠ **AN UNKNOWN OR MALFORMED NUMBER IS RETURNED AS ITSELF, NOT REFUSED
    HERE.** It contains no `@`, so it matches no login's email, and
    `verify_credentials` then runs its OWN unknown-name path — the timing
    equaliser and the one generic failure (BR-IDN-002). Refusing here would be
    a second, faster refusal, and the difference in time is an oracle for
    which numbers belong to somebody."""
    text = str(identifier or "").strip()
    if phones.identifier_kind(text) == phones.KIND_EMAIL:
        return text
    user = selectors.user_by_phone(tenant_id, text)
    if user is None or not user.email:
        return text
    return user.email


def mask_identifier(identifier: Any) -> str:
    """BR-AUD-006: what was typed enters the trail MASKED only — an email as
    `services._mask_email` masks it, anything else as its last two digits."""
    text = str(identifier or "").strip()
    if phones.identifier_kind(text) == phones.KIND_EMAIL:
        return services._mask_email(text)
    return phones.mask_phone(text)


def _clean_device(device_id: Any, device_name: Any = "") -> tuple[str, str]:
    """A device id is REQUIRED on every native sign-in (the token is bound to
    it); the name is optional free text, trimmed. Refused by name, VAL-001."""
    device = str(device_id or "").strip()
    if not device or len(device) > 200:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[
                {"field": "device_id", "code": errors.VAL_REQUIRED, "params": {}},
            ],
            br_ref="BR-IDN-006",
        )
    return device, str(device_name or "").strip()[:80]


# ── Minting ──────────────────────────────────────────────────────────────────
def _issue_pair(
    *,
    user: User,
    tenant_id: Any,
    family_id: Any,
    device_uid: str,
    device_name: str,
    ip: str | None,
    now,
) -> dict[str, Any]:
    access = _mint(ACCESS_PREFIX, tenant_id)
    refresh = _mint(REFRESH_PREFIX, tenant_id)
    refresh_life = refresh_token_max_age_s(tenant_id)
    common = {
        "tenant_id": tenant_id,
        "user": user,
        "family_id": family_id,
        "device_uid": device_uid,
        "device_name": device_name,
        "issued_at": now,
        "ip": ip,
    }
    NativeToken.objects.create(
        kind=NativeToken.KIND_ACCESS,
        token_hash=hash_token(access),
        expires_at=now + ACCESS_TOKEN_TTL,
        **common,
    )
    NativeToken.objects.create(
        kind=NativeToken.KIND_REFRESH,
        token_hash=hash_token(refresh),
        expires_at=now + timedelta(seconds=refresh_life),
        **common,
    )
    return {
        "token_type": "Bearer",
        "access_token": access,
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "refresh_token": refresh,
        "refresh_expires_in": refresh_life,
    }


def _sign_in_payload(user: User, membership: TenantMembership, tokens: dict, device: dict) -> dict:
    return {
        **tokens,
        "user": {
            "id": str(user.id),
            "display_name": _display_name(user),
            "role": membership.role.code,
            "role_name": membership.role.name,
        },
        "device": device,
    }


# ── POST auth/token ──────────────────────────────────────────────────────────
#: ⚠ NOT `@transaction.atomic`, deliberately: a wrong password must leave its
#: failed-attempt count and lockout COMMITTED when the refusal is raised, which
#: an outer atomic block would roll back (`services.sign_in` is not atomic for
#: the same reason). The writes after a successful check go in their own block.
def sign_in_native(
    *,
    tenant_id: Any,
    identifier: str | None = None,
    email: str | None = None,
    password: str,
    device_id: Any,
    device_name: Any = "",
    ip: str | None = None,
) -> dict[str, Any]:
    """Password sign-in for the native app → a one-hour access token and a
    single-use refresh token, both bound to `device_id`.

    ⚠ **THE SAME DOOR AS THE WEB'S, CHECK FOR CHECK.** `verify_credentials` is
    the function `services.sign_in` runs: the utility's lockout (count and
    minutes), its allowed addresses, the one generic failure, the surface rule
    (`mobile`). A wrong password here counts towards the SAME lock a wrong
    password on the web does.

    ⚠ **A TEMPORARY OR EXPIRED PASSWORD IS REFUSED, NOT SIGNED IN.** The web
    sends that person to its change-password page; the native app has none,
    and the bearer reaches no `/me/password`. The phone's door for that person
    is activation (FF-56/57), which sets their own password. 403 with
    `params.reason = password_change_required`.

    ⚠ **ONE FIELD, TWO KEYS (`CR-187-BRC10`, 2026-10-21).** `identifier` is a
    work email or a phone number (`email_for_identifier`); the older `email`
    argument is still accepted and means the same field. Either way the SAME
    `verify_credentials` runs, so the lockout, the generic failure and the
    surface rule are one, whichever key was typed.
    """
    device_uid, name = _clean_device(device_id, device_name)
    typed = identifier if identifier not in (None, "") else email
    now = services._now()
    user, membership, policy_values = services.verify_credentials(
        tenant_id=tenant_id,
        email=email_for_identifier(tenant_id, typed),
        password=password,
        ip=ip,
        surface=services.SURFACE_MOBILE,
        now=now,
    )
    user.failed_attempts = 0
    user.locked_until = None
    if services.password_expired(user, policy_values, now):
        user.must_change_password = True  # what the web sign-in does too
    user.save(
        update_fields=["failed_attempts", "locked_until", "must_change_password", "updated_at"]
    )
    if user.must_change_password:
        core_audit.write_row(
            action="auth.token_refused_password_change",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={"device": device_uid[-6:]},
        )
        raise _password_change_required()

    family_id = uuid.uuid4()
    with transaction.atomic():
        tokens = _issue_pair(
            user=user,
            tenant_id=tenant_id,
            family_id=family_id,
            device_uid=device_uid,
            device_name=name,
            ip=ip,
            now=now,
        )
        membership.last_active_at = now
        membership.save(update_fields=["last_active_at", "updated_at"])
        core_audit.write_row(
            action="auth.token_issued",
            entity_type="native_token_family",
            entity_id=family_id,
            actor_user_id=user.id,
            after={
                "email": services._mask_email(user.email),
                "device_name": name,
                "signed_in_with": phones.identifier_kind(typed),
                "identifier": mask_identifier(typed),
            },
        )
    return _sign_in_payload(user, membership, tokens, {"device_id": device_uid, "name": name})


# ── POST auth/token/refresh ──────────────────────────────────────────────────
def _row_for(plaintext: str, prefix: str, tenant_id: Any, kind: str) -> NativeToken | None:
    """The row for a presented token, under the PATH tenant's RLS context.

    Raises the 404 when the token names another tenant (`BR-IDN-006`); answers
    None when it names this one and matches nothing."""
    named = parse_tenant(plaintext, prefix)
    if named is None:
        return None
    if tenant_id is None or str(named) != str(tenant_id):
        raise errors.deny_as_not_found(br_ref="BR-IDN-006")
    return (
        NativeToken.objects.filter(token_hash=hash_token(plaintext), kind=kind)
        .select_related("user")
        .first()
    )


def _revoke_family(family_id: Any, reason: str, now) -> int:
    return NativeToken.objects.filter(family_id=family_id, revoked_at__isnull=True).update(
        revoked_at=now, revoked_reason=reason
    )


def refresh_native(
    *, tenant_id: Any, refresh_token: Any, device_id: Any = None, ip: str | None = None
) -> dict[str, Any]:
    """Spend a refresh token once → a new access + refresh pair, same family.

    ⚠ **A SPENT REFRESH TOKEN PRESENTED AGAIN REVOKES THE WHOLE FAMILY.** The
    honest phone never does it — it swaps the pair atomically — so a second
    use means a copy exists somewhere else, and the safe answer is to end the
    sign-in for both holders (`params.reason = token_revoked`).

    ⚠ **A REVOKE IS COMMITTED EVEN THOUGH THE CALL IS REFUSED.** The reuse
    revocation runs in its own atomic block and the refusal is raised after it,
    so the 401 does not roll the revocation back."""
    plaintext = str(refresh_token or "").strip()
    now = services._now()
    row = _row_for(plaintext, REFRESH_PREFIX, tenant_id, NativeToken.KIND_REFRESH)
    if row is None:
        raise refusal("token_unknown")
    if row.revoked_at is not None:
        raise refusal(
            REASON_DEVICE_SIGNED_OUT
            if row.revoked_reason == REASON_DEVICE_SIGNED_OUT
            else "token_revoked"
        )
    if row.used_at is not None:
        with transaction.atomic():
            _revoke_family(row.family_id, REASON_REFRESH_REUSE, now)
            core_audit.write_row(
                action="auth.token_reuse_detected",
                entity_type="native_token_family",
                entity_id=row.family_id,
                actor_user_id=row.user_id,
                after={"device": row.device_uid[-6:]},
            )
        raise refusal("token_revoked")
    if now >= row.expires_at:
        raise refusal("refresh_token_expired")
    if device_id not in (None, "") and str(device_id).strip() != row.device_uid:
        # Bound to the handset it was issued to: a copy on another device is
        # not a refresh, it is a theft. Refused, and the family is left alone
        # (the honest holder may still be using it).
        raise refusal("token_unknown")
    membership = selectors.membership_for_user(tenant_id, row.user_id)
    if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
        raise refusal("token_revoked")  # BR-IDN-012: deactivation kills access at once
    user = row.user
    if user.must_change_password:
        raise _password_change_required()
    with transaction.atomic():
        spent = NativeToken.objects.filter(pk=row.pk, used_at__isnull=True).update(used_at=now)
        if not spent:
            # Two refreshes raced; the other one won. This one is the reuse.
            raise refusal("token_revoked")
        # The access token(s) the old pair carried stop now — one live access
        # token per family at a time.
        NativeToken.objects.filter(
            family_id=row.family_id, kind=NativeToken.KIND_ACCESS, revoked_at__isnull=True
        ).update(revoked_at=now, revoked_reason="rotated")
        tokens = _issue_pair(
            user=user,
            tenant_id=tenant_id,
            family_id=row.family_id,
            device_uid=row.device_uid,
            device_name=row.device_name,
            ip=ip,
            now=now,
        )
        core_audit.write_row(
            action="auth.token_refreshed",
            entity_type="native_token_family",
            entity_id=row.family_id,
            actor_user_id=user.id,
        )
    return _sign_in_payload(
        user, membership, tokens, {"device_id": row.device_uid, "name": row.device_name}
    )


# ── DELETE auth/token ────────────────────────────────────────────────────────
def sign_out_native(*, token: NativeToken) -> int:
    """Revoke the sign-in this access token belongs to — access AND refresh.
    Never touches the handset's outbox: that is the phone's, not ours.

    ⚠ **AND THE HANDSET STOPS RINGING FOR THIS PERSON (`DEF-WRK-10352`).** The
    push token on their registration of this handset is released in the SAME
    transaction, through work's own service (`seams/work_seam.py`): a
    technician who signs out of one utility to sign into another must not go
    on receiving the first one's jobs, and neither must the next person to
    pick the phone up. The registration row and its capture credential stay."""
    now = services._now()
    with transaction.atomic():
        count = _revoke_family(token.family_id, REASON_SIGNED_OUT, now)
        work_seam.release_push_on_sign_out(
            tenant_id=token.tenant_id, user_id=token.user_id, device_uid=token.device_uid
        )
        core_audit.write_row(
            action="auth.token_revoked",
            entity_type="native_token_family",
            entity_id=token.family_id,
            actor_user_id=token.user_id,
            after={"tokens": count},
        )
    return count


def revoke_device(*, tenant_id: Any, device_uid: str, actor_user_id: Any) -> int:
    """The office's remote sign-out, identity half (`R115`): every live token
    of this handset, for every technician who signed in on it, revoked with
    reason `device_signed_out` — the reason the phone is then told.

    Called by work's `mobile.remote_sign_out` through `work.seams.identity_seam`
    (a SERVICE call into identity, the door `BR-WRK-002` sanctions — never an
    ORM write from work). The tenant is the caller's context; RLS confines the
    update to it whatever `device_uid` says."""
    now = services._now()
    count = NativeToken.objects.filter(
        tenant_id=tenant_id, device_uid=device_uid, revoked_at__isnull=True
    ).update(revoked_at=now, revoked_reason=REASON_DEVICE_SIGNED_OUT)
    core_audit.write_row(
        action="auth.device_tokens_revoked",
        entity_type="native_device",
        entity_id=None,
        actor_user_id=actor_user_id,
        after={"device": device_uid[-6:], "tokens": count},
    )
    return count


def revoke_user_tokens(*, user: User, reason: str = REASON_PASSWORD_CHANGED) -> int:
    """Every live native token of this login — called where the web revokes
    the login's other sessions (a password change, BR-IDN-005/016)."""
    return NativeToken.objects.filter(user_id=user.id, revoked_at__isnull=True).update(
        revoked_at=services._now(), revoked_reason=reason
    )


# ── Activation (FF-56 / FF-57; R105) ─────────────────────────────────────────
def _code_hmac(tenant_id: Any, code: str) -> str:
    key = str(settings.SECRET_KEY).encode("utf-8")
    message = f"{tenant_id}:{code.strip().upper()}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def normalise_code(raw: Any) -> str:
    """As the phone does: spaces and dashes dropped, upper case."""
    return "".join(ch for ch in str(raw or "") if ch not in " -\t").upper()


def _register_digest(code: str) -> str:
    """The PLATFORM-WIDE digest of a code (`DEF-FLD-10580`): HMAC under the
    server secret and a fixed context, never the tenant — the same code must be
    the same digest at every utility, or the register's UNIQUE constraint could
    not see two utilities drawing it."""
    key = str(settings.SECRET_KEY).encode("utf-8")
    message = f"{ACTIVATION_REGISTER_CONTEXT}:{normalise_code(code)}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _draw_code() -> str:
    """Six characters at random from the 31 unambiguous ones (31⁶ ≈ 887M).
    A function of its own so a test can force a collision."""
    return "".join(secrets.choice(ACTIVATION_ALPHABET) for _ in range(ACTIVATION_CODE_LENGTH))


def _claim_unique_code(tenant_id: Any, now) -> str:
    """Draw a code no utility has EVER held, and record it — `DEF-FLD-10580`.

    The register's UNIQUE constraint decides, not a read before the write: two
    offices issuing at the same instant cannot both pass a check-then-insert,
    and the database refuses the second. Each INSERT runs in its own SAVEPOINT
    (a nested `transaction.atomic()`), and that is not tidiness — on PostgreSQL
    a refused statement aborts the whole transaction, so without the savepoint
    the redraw would raise `InFailedSqlTransaction` and the office's *Create
    user* would be lost (CLAUDE.md hard-won law 14; proved on PostgreSQL in
    `tests/test_def_fld_10580_activation_lookup_pg.py`).
    """
    for _attempt in range(ACTIVATION_DRAW_ATTEMPTS):
        code = _draw_code()
        try:
            with transaction.atomic():
                ActivationCodeRegister.objects.create(
                    code_digest=_register_digest(code), tenant_id=tenant_id, created_at=now
                )
        except IntegrityError:
            continue  # held by some utility, now or ever: draw again
        return code
    # 887M codes; eight collisions in a row is a broken random source.
    raise errors.SysError(errors.SYS_INTERNAL)


def issue_activation_code(*, actor: Any, user: User) -> dict[str, Any]:
    """The office hands a technician a code (`R105`). Voids every earlier
    unused code of the same login; the plaintext is returned ONCE and never
    stored (HMAC only). Audited.

    The code is unique across EVERY utility, for ever (`_claim_unique_code`,
    `DEF-FLD-10580`), because the phone learns the utility from it."""
    now = services._now()
    tenant_id = user.tenant_id
    ActivationCode.objects.filter(
        user_id=user.id, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now)
    code = _claim_unique_code(tenant_id, now)
    digest = _code_hmac(tenant_id, code)
    row = ActivationCode.objects.create(
        tenant_id=tenant_id,
        user=user,
        code_hmac=digest,
        issued_at=now,
        expires_at=now + timedelta(days=ACTIVATION_CODE_VALID_DAYS),
        issued_by=core_audit.actor_user_id(actor),
    )
    core_audit.write_row(
        action="auth.activation_code_issued",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=core_audit.actor_user_id(actor),
        after={"expires_at": row.expires_at.isoformat()},
    )
    return {"activation_code": code, "activation_code_expires_at": row.expires_at.isoformat()}


def _activation_failure() -> errors.AuthError:
    """ONE refusal for unknown, expired, used, burnt and wrong-email — the
    BR-IDN-002 posture: a refusal that told them apart would tell a guesser
    which codes are real."""
    return refusal("activation_code_not_accepted")


def _live_code(row: ActivationCode | None, now) -> bool:
    return (
        row is not None
        and row.used_at is None
        and row.revoked_at is None
        and now < row.expires_at
    )


def _identifier_matches(user: User, identifier: Any) -> bool:
    """Is what was typed THIS login's email, or THIS login's phone number in
    the one normal form? (A number left NULL by the backfill matches nothing.)"""
    text = str(identifier or "").strip()
    if not text:
        return False
    if phones.identifier_kind(text) == phones.KIND_EMAIL:
        return text.lower() == (user.email or "").lower()
    number = phones.normalise_phone(text)
    return number is not None and number == user.phone_e164


def lookup_activation_code(*, code: Any) -> dict[str, Any]:
    """`POST /api/auth/activation/lookup` — the utility-free door (`DEF-FLD-10580`).

    The phone knows only the code. The register says which utility holds it;
    then THAT utility's own `activation_codes` row is read under its RLS
    context, and only a LIVE code (unused, not voided, not expired) answers
    with the utility's slug and name. Nothing is listed and nothing else is
    returned — not who the code is for (that is `check_activation`'s answer,
    after the person proves their email or phone).

    ONE refusal for a malformed, unknown, expired, used or voided code — the
    BR-IDN-002 posture. Guessing is held
    off by the platform-wide per-address and per-device limits on the door
    (`api.ActivationLookupThrottle*`, PO 2026-10-24: no utility's setting can
    apply before the code names the utility); once it has, wrong emails count
    against the code under that utility's own lockout count, in
    `check_activation`, unchanged."""
    from apps.tenancy.models import Tenant  # the registry; RLS-exempt by B2 §3
    from core import tenancy as core_tenancy

    normalised = normalise_code(code)
    if len(normalised) != ACTIVATION_CODE_LENGTH:
        raise _activation_failure()
    found = (
        ActivationCodeRegister.objects.filter(code_digest=_register_digest(normalised))
        .values_list("tenant_id", flat=True)
        .first()
    )
    if found is None:
        services._equalize_timing()
        raise _activation_failure()
    tenant = Tenant.objects.filter(pk=found).first()
    if tenant is None or not tenant.subdomain:
        raise _activation_failure()
    now = services._now()
    with core_tenancy.tenant_context(tenant.pk):
        row = ActivationCode.objects.filter(
            tenant_id=tenant.pk, code_hmac=_code_hmac(tenant.pk, normalised)
        ).first()
        if not _live_code(row, now):
            raise _activation_failure()
        core_audit.write_row(
            action="auth.activation_code_looked_up",
            entity_type="user",
            entity_id=row.user_id,
            actor_user_id=None,  # nobody is signed in yet
        )
    return {"tenant": tenant.subdomain, "utility_name": tenant.name or ""}


def check_activation(
    *, tenant_id: Any, code: Any, email: Any = None, identifier: Any = None
) -> dict[str, Any]:
    """FF-56: is this code real, live, and for THIS person? → who it is for, the
    utility, the tenant's password rules, and a 30-minute ticket for FF-57.

    The person is named by their work email OR their phone number
    (`identifier`, `CR-187-BRC10`; the older `email` argument means the same).
    A wrong one against a real code counts; the fifth burns the code. The
    check does NOT spend the code — completing does (single use)."""
    typed = identifier if identifier not in (None, "") else email
    now = services._now()
    normalised = normalise_code(code)
    if len(normalised) != ACTIVATION_CODE_LENGTH:
        raise _activation_failure()
    row = (
        ActivationCode.objects.filter(tenant_id=tenant_id, code_hmac=_code_hmac(tenant_id, normalised))
        .select_related("user")
        .first()
    )
    if not _live_code(row, now):
        if row is None:
            services._equalize_timing()
        raise _activation_failure()
    if not _identifier_matches(row.user, typed):
        row.failed_attempts += 1
        burnt = row.failed_attempts >= activation_max_failed(tenant_id)
        update = ["failed_attempts"]
        if burnt:
            row.revoked_at = now
            update.append("revoked_at")
        row.save(update_fields=update)
        core_audit.write_row(
            action="auth.activation_failed",
            entity_type="user",
            entity_id=row.user_id,
            actor_user_id=None,  # unauthenticated attempt
            after={"burnt": burnt},
        )
        raise _activation_failure()
    membership = selectors.membership_for_user(tenant_id, row.user_id)
    if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
        raise _activation_failure()
    policy_values = selectors.security_policy_values(tenant_id)
    ticket = signing.dumps(
        {"c": str(row.id), "u": str(row.user_id), "t": str(tenant_id)},
        salt=ACTIVATION_TICKET_SALT,
    )
    core_audit.write_row(
        action="auth.activation_checked",
        entity_type="user",
        entity_id=row.user_id,
        actor_user_id=None,
    )
    return {
        "display_name": _display_name(row.user),
        "role": membership.role.code,
        "role_name": membership.role.name,
        "utility_name": _utility_name(tenant_id),
        "password_policy": {
            "min_length": policy_values["pw_min_length"],
            "require_mixed": policy_values["pw_require_mixed"],
            "require_symbol": policy_values["pw_require_symbol"],
        },
        "activation_ticket": ticket,
        "ticket_expires_in": ACTIVATION_TICKET_MAX_AGE_S,
    }


def _utility_name(tenant_id: Any) -> str:
    from apps.tenancy.models import Tenant  # the registry; RLS-exempt by B2 §3

    return Tenant.objects.filter(pk=tenant_id).values_list("name", flat=True).first() or ""


def complete_activation(
    *,
    tenant_id: Any,
    activation_ticket: Any,
    password: Any,
    device_id: Any,
    device_name: Any = "",
    ip: str | None = None,
) -> dict[str, Any]:
    """FF-57: the technician's OWN password (the utility's rules AND the last-5
    reuse check — `services.change_password`, the function the web runs), the
    code spent, the membership activated, and then signed in on this device.

    ⚠ **ALL OR NOTHING.** A password the policy refuses rolls the whole thing
    back, so a typo never burns the code; the code is spent with a conditional
    UPDATE inside the same transaction, so two phones racing one code get one
    sign-in and one refusal."""
    device_uid, name = _clean_device(device_id, device_name)
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[{"field": "device_name", "code": errors.VAL_REQUIRED, "params": {}}],
            br_ref="BR-IDN-006",
        )
    try:
        data = signing.loads(
            str(activation_ticket or ""),
            salt=ACTIVATION_TICKET_SALT,
            max_age=ACTIVATION_TICKET_MAX_AGE_S,
        )
    except signing.BadSignature:  # SignatureExpired is a subclass
        raise _activation_failure() from None
    if str(data.get("t")) != str(tenant_id):
        raise errors.deny_as_not_found(br_ref="BR-IDN-006")
    now = services._now()
    row = (
        ActivationCode.objects.filter(tenant_id=tenant_id, pk=data.get("c"), user_id=data.get("u"))
        .select_related("user")
        .first()
    )
    if not _live_code(row, now):
        raise _activation_failure()
    user = row.user
    membership = selectors.membership_for_user(tenant_id, user.id)
    if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
        raise _activation_failure()
    if not services._surface_allowed(user.surface_scope, services.SURFACE_MOBILE):
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            message_key=services.SURFACE_REFUSED_WEB_ONLY_MESSAGE_KEY,
            br_ref="BR-WRK-043",
        )
    with transaction.atomic():
        spent = ActivationCode.objects.filter(
            pk=row.pk, used_at__isnull=True, revoked_at__isnull=True
        ).update(used_at=now)
        if not spent:
            raise _activation_failure()
        # Claiming an account with an office-issued code IS the forced first
        # change (BR-IDN-022): the same service, so the same policy, the same
        # last-5 refusal, the same session revocation and membership activation.
        user.must_change_password = True
        services.change_password(
            actor=user, new_password=str(password or ""), confirm_password=str(password or "")
        )
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        membership.refresh_from_db()
        membership.last_active_at = now
        membership.save(update_fields=["last_active_at", "updated_at"])
        family_id = uuid.uuid4()
        tokens = _issue_pair(
            user=user,
            tenant_id=tenant_id,
            family_id=family_id,
            device_uid=device_uid,
            device_name=name,
            ip=ip,
            now=now,
        )
        core_audit.write_row(
            action="auth.activation_completed",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={"device_name": name},
        )
        core_audit.write_row(
            action="auth.token_issued",
            entity_type="native_token_family",
            entity_id=family_id,
            actor_user_id=user.id,
            after={"email": services._mask_email(user.email), "device_name": name},
        )
    return _sign_in_payload(user, membership, tokens, {"device_id": device_uid, "name": name})


__all__ = [
    "ACCESS_PREFIX",
    "REFRESH_PREFIX",
    "check_activation",
    "complete_activation",
    "issue_activation_code",
    "lookup_activation_code",
    "refresh_native",
    "revoke_device",
    "revoke_user_tokens",
    "sign_in_native",
    "sign_out_native",
]
