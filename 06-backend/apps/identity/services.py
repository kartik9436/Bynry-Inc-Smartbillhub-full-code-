# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-001 (sign-in + lockout) · US-IDN-002 (temp password, no-email v1) ·
#           US-IDN-003 (sessions + sign-out) · US-IDN-005 (add a user) ·
#           US-IDN-006 (edit role / deactivate / reactivate) · US-IDN-007 (remove) ·
#           US-IDN-008 (profile + change password) · US-IDN-010 (security policy) ·
#           US-TEN-001 (identity half of the S114 provisioning seam — owner user,
#           documented in apps/tenancy/seams.py) · US-TEN-003 (member_count for S62)
#           Screens: S2/S3 · S8 · S48 · S114/S62 (seam halves)
# Rules:    BR-IDN-001/002 (tenant-first — the /api/{tenant}/ path segment since the PO
#           ruling 2026-08-10, was the subdomain; one generic failure) · BR-IDN-025 (5-fail →
#           15-min lock · temp password 7 d · policy seed) · BR-IDN-005/011/021/022/023
#           (no-email v1 temp-password lifecycle) · BR-IDN-006/007/026 (sessions) ·
#           BR-IDN-008/009/010/029 (3 roles · SysAdmin-only · per-tenant users) ·
#           BR-IDN-012 (deactivate-first) · BR-IDN-030 (remove = PERMANENT deactivation;
#           email retained; add-on-deactivated-email → 409 pointing to Reactivate —
#           PO 2026-08-09, supersedes the BR-IDN-012 delete-membership remove) ·
#           BR-IDN-013 (last-admin guard) · BR-IDN-015/016/017/027 (self-service) ·
#           BR-IDN-019/020 (policy save, self-lockout guard) · BR-TEN-010 (replay
#           check input via owner_email_for)
# Tests:    06-backend/tests/test_us_idn_001..010*.py (per-TC; RLS halves = G5 suite) ·
#           tests/test_us_ten_001_004_provisioning.py (seam integration, now live)
# Impacts:  apps/identity/api.py + auth.py · core.permissions (role attachment) ·
#           apps/tenancy/seams.py resolve-at-call-time consumers (provision_owner ·
#           owner_email_for · member_count) · every module's actor columns
# ───────────────────────────────────────────────────────
"""identity service layer — the ONLY write path into this module's tables (B1
boundary rule). Other modules call these functions; they never touch this
module's ORM directly. api.py stays thin; selectors.py owns reads (LAW 0).

⚠ **AMENDED 2026-09-28 (`CR-145-BRC08`, PO: *"Im okay with these limit"*).**
This paragraph read *"Platform-fixed v1 values (BR-IDN-025/026 — per
US-IDN-010 §5 these are NOT tab controls, so they live here as named
constants): lockout 5 failed → 15-minute lock · temp password valid 7 days ·
absolute session lifetime 12 h · keep-me-signed-in trusted-device window 30
days."* **Four of those five ARE tab controls now.** The lockout count, the
lockout length, the absolute session lifetime and the keep-me-signed-in window
are columns on the utility's own `security_policies` row, read per call
through `selectors.security_policy_values`; `SETTING_LIMITS` above holds the
only thing still platform-fixed about them, which is what an admin may choose.
**`TEMP_PASSWORD_VALID_DAYS = 7` and the password rules are NOT in that change
and stay exactly where they were** — the ruling says so in as many words.

Eng dispositions (recorded, not invented):
- Forced change (BR-IDN-022): `current_password` is optional while
  `must_change_password` is set — the anchored forced-change screen carries
  New/Confirm only; possession of the temp password was just proven at
  sign-in.
- Trusted-device refresh (BR-IDN-026): re-establishes the SAME persistent
  session row (last_seen/expiry reset) within 30 days of its creation — no
  refresh-token storage is anchored, so none is minted.
- BR-IDN-025's last-5 password-history block: ⚠ **BUILT 2026-10-08
  (`DEF-IDN-10023`, PO: *"go - build the last 5 passwords check"*).** This
  line read *"has NO anchored storage … the check is honestly absent and
  reported"* while Settings → Security told every admin *"The last 5
  passwords are blocked"* — a comment holding a gap nobody had filed (hard-won
  law 1). Storage is `password_history` (`identity/0010`, RLS + FORCE); the
  check is `_refuse_reused_password`, run by `change_password` on BOTH its
  paths. See the block at `PASSWORD_HISTORY_BLOCK`.
- Password expiry (`pw_expiry_days`): ⚠ **ENFORCED 2026-10-08
  (`DEF-IDN-10022`).** The setting was stored, validated and served and
  NOTHING compared it with `password_changed_at`. `sign_in` now sends an
  expired password to the existing forced change — see `password_expired`.
- BR-IDN-012 reference counting reads the referencing tables that exist in
  W0 (audit_log.actor_user_id · tenant_memberships.invited_by ·
  user_preferences.user_id) via selectors; later waves append theirs.
"""

import secrets
from datetime import timedelta
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.identity import selectors
from apps.identity.models import (
    PasswordHistory,
    PasswordLink,
    SecurityPolicy,
    Session,
    TenantMembership,
    User,
)
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import FIELD_TECHNICIAN, SYSTEM_ADMIN, require_role

# ── Platform-fixed v1 values (BR-IDN-025) ───────────────────────────────────
#
# ⚠ **WHAT IS LEFT IN THIS BLOCK IS LEFT DELIBERATELY (`CR-145-BRC08`).** Four
# constants moved out of it on 2026-09-28 — `LOCKOUT_MAX_FAILED`,
# `LOCKOUT_MINUTES`, `ABSOLUTE_SESSION_HOURS` and `TRUSTED_DEVICE_REFRESH_DAYS`
# — because the PO ruled each of them a per-utility setting. **These two did
# not**, and the ruling names them: *"`TEMP_PASSWORD_VALID_DAYS = 7` and the
# password rules are NOT in this change and stay fixed"*. They sat in the same
# block and appear on the same screen, which is exactly why they are called out
# here rather than left to be inferred. A lane widening `CR-145` to them has
# widened a ruling nobody made.
TEMP_PASSWORD_VALID_DAYS = 7  # BR-IDN-025 — FIXED, explicitly not in CR-145
#: BR-IDN-025 — FIXED, and ⚠ **THE CHECK EXISTS FROM 2026-10-08
#: (`DEF-IDN-10023`).** Until then this line read *"storage NOT anchored; check
#: absent (reported)"* — reported nowhere a register could count it, while the
#: Security tab printed *"The last 5 passwords are blocked"* to every admin.
#: The PO chose to BUILD rather than delete the sentence (2026-10-08, *"go -
#: build the last 5 passwords check"*). **What it means, exactly:** a new
#: password is refused when it matches the CURRENT password or any of the FIVE
#: before it; the sixth-oldest is allowed again. Hashes live in
#: `password_history` (`identity/0010`), pruned to this many per user on every
#: write. It stays a constant and not a setting — `CR-145-BRC08` left the
#: password half of BR-IDN-025 fixed, in as many words.
PASSWORD_HISTORY_BLOCK = 5

#: `DEF-IDN-10023`. Six words (B14 rule 33, an instruction). It names no
#: number, so the day `PASSWORD_HISTORY_BLOCK` moves the sentence stays true.
PASSWORD_REUSED_MESSAGE_KEY = "errors.identity.password_recently_used"

# Tab-controlled option sets (US-IDN-010 §5 validation column) — now DERIVED
# views of `SETTING_LIMITS` below (DEF-IDN-7501), kept under their old names
# because they are what the password check reads. The values did not move.

# ── What an admin may CHOOSE (`CR-145-BRC08`, PO 2026-09-28) ────────────────
#
# **ONE PLACE, AND IT IS THE LIMITS THAT LIVE HERE — NOT THE VALUES.** The
# value in force for a utility is a column on its own `security_policies` row;
# what it is allowed to be is this table. `_validate_policy_values` refuses
# against it and `selectors.security_policy_values` SERVES it beside the
# policy, so the Security tab renders the choices from the server and keeps no
# second copy of them (hard-won law 5's shape for a rule rather than a file).
#
# Two shapes, because the two questions differ: a CHOICE LIST is rendered as a
# dropdown of exactly those values, and a RANGE is a number with a floor and a
# ceiling. Reading the shape off the entry is what lets one validator and one
# screen handle both.
#
# ⚠ **`session_timeout_minutes` IS 15/30/45/60 AND NO LONGER 30/60/240/480.**
# 240 and 480 are WITHDRAWN (PO 2026-09-28) and 15 and 45 are new. A utility
# sitting on a withdrawn value is moved to 60 by `identity/0007`; a PUT asking
# for one now is refused by name and range, which is `T2`'s 240-minute case.
#
# ⚠⚠ **AND ON 2026-09-29 THE LAST FOUR RANGES BECAME CHOICE LISTS TOO** — the
# approved Settings → Security redesign (`05-prototype/security-redesign-
# 2026-09-29/`, PO verbatim: *"(a) Short dropdown, list chosen from real use -
# Dropdown"*). So every one of the eight entries below is now a CHOICE LIST
# and the `min`/`max` shape has no member left. **The range BRANCH of
# `_validate_policy_values` is kept on purpose** — it is the shape the table
# declares it supports, and deleting the branch would make the next range
# entry silently unvalidated rather than obviously unsupported.
#
# ⚠ **A LIST IS A WITHDRAWAL, WHICH IS WHY TWO OF THESE FOUR ARE PROVISIONAL.**
# Converting a range to a list withdraws every value left off it. On
# 2026-09-28 exactly that moved utilities from 480 minutes to 60 and signed
# their staff out seven hours earlier (`identity/0007` and `0008`). The PO's
# answer says the list is *"chosen from real use"* precisely so that **nobody
# moves**, and that is a precondition rather than a detail. See the four
# constants below for which two are settled and which two are waiting.

#: **FINAL.** Every hour of the old 4–12 range, so the list IS the range and
#: **no utility can be moved by it** — offering a whole range withdraws
#: nothing, whatever anybody holds. That is an argument from arithmetic
#: rather than from data, which is why this one did not have to wait for the
#: count; the count then confirmed it
#: (`05-prototype/security-redesign-2026-09-29/value-census-2026-09-29.md`).
ABSOLUTE_SESSION_HOURS_CHOICES = (4, 5, 6, 7, 8, 9, 10, 11, 12)

#: **FINAL**, for exactly that reason: every value of the old 3–10 range,
#: eight options, nothing withdrawn.
LOCKOUT_MAX_FAILED_CHOICES = (3, 4, 5, 6, 7, 8, 9, 10)

#: ⚠ **PROVISIONAL — THE COUNT AGAINST PRODUCTION DECIDES THIS LIST, NOT THIS
#: FILE.** Drawn from `approved-proposed-1440.png`; the old range was 5–60, so
#: this list WITHDRAWS 51 values (every minute except these six).
#:
#: ⚠ **THE CENSUS HAS RUN AND IT DOES NOT SETTLE IT.**
#: `10-scripts/cr145_security_dropdown_value_census.py`, 2026-09-29: every
#: utility on this container holds the seeded default 15, and the six tenant
#: rows are four tenant ids of ONE utility cloned across databases. **So the
#: tests here are green and that greenness is not evidence.** The same command
#: against the production database is what settles it; when it lands, this
#: tuple is replaced by the measured list plus any held value missing from it.
#: Until then nobody is moved: a value already stored is still read and still
#: saved (`_validate_policy_values`'s `current` exemption), and widening this
#: list later is a one-line change here and never a data migration.
LOCKOUT_MINUTES_CHOICES = (5, 10, 15, 30, 45, 60)

#: ⚠ **PROVISIONAL, for the reason above, and on the same evidence** — every
#: utility counted holds the seeded default 30. The old range was 1–30, so
#: this list withdraws 26 values. The production count replaces it.
KEEP_SIGNED_IN_DAYS_CHOICES = (1, 7, 14, 30)

#: **The field app's capture life, in HOURS** (PO 2026-10-21, *"this should
#: come from settings"*; decision log *"Field app: the PO corrects four of the
#: ten answers"* item 2). Seeded 168 = the 7 days `BR-WRK-060` signed.
#:
#: **The bounds are ours, and here is why.** FLOOR one hour: anything shorter
#: and a technician driving between two dead spots is asked for a password in
#: the middle of a job, which is the failure the capture credential exists to
#: prevent. CEILING 720 hours = 30 days, the longest *keep me signed in* a
#: utility can choose for the web (`KEEP_SIGNED_IN_DAYS_CHOICES`), so a lost
#: handset can never outlive the longest credential the same utility allows
#: anywhere else. A CHOICE LIST, not a range, because every Security setting is
#: one since the 2026-09-29 redesign (*"Short dropdown"*). **36 is on it on
#: purpose** — it is the design's own figure (Security §1, `OQ-FLD-12798`), so
#: a utility that wants the drawn behaviour picks it rather than asking us.
#: Between the floor and a day there is only 12 — one long shift; a value
#: under a shift asks for a password mid-day and buys nothing a 1-hour
#: utility would not choose outright.
#: Nobody is moved by this list: it is new, and the default is on it.
FIELD_CAPTURE_HOURS_CHOICES = (1, 12, 24, 36, 48, 72, 168, 336, 720)
FIELD_CAPTURE_HOURS_DEFAULT = 168

#: `CR-188-BRC10` — an emailed sign-in link's life, DAYS. See SETTING_LIMITS.
PASSWORD_LINK_VALID_DAYS_CHOICES = (1, 2, 3, 7, 14)
PASSWORD_LINK_VALID_DAYS_DEFAULT = 7

SETTING_LIMITS: dict[str, dict[str, Any]] = {
    # ⚠ **DEF-IDN-7501 — THE TWO PASSWORD DROPDOWNS, PUBLISHED AND NOT
    # CHANGED.** The password rules are OUTSIDE `CR-145` and stay exactly as
    # `BR-IDN-025` / US-IDN-010 §5 set them; these two entries hold the values
    # the validator already enforced, so the Security tab can read them
    # instead of typing `[8, 10, 12]` and `[null, 90, 180]` out by hand (which
    # no gate compares with a Python tuple). `None` is a real choice —
    # "never expires" — and is the default. First in the dict so a refusal
    # naming several fields lists them in the order it always did.
    #
    # ⚠ **THERE IS NO `unit` HERE AND THERE WAS FOR ONE AFTERNOON.** The
    # redesign puts the unit inside the option (`12 hours`, `5 tries`), so a
    # `unit` key was added here for the server to compose those words with —
    # and the Security tab labels its own options through
    # `securityValueLabel` and the eleven catalogues, which is the only
    # renderer that can. The key was read by nothing and travelled to the
    # browser to be ignored, so it is gone. **THE VALUES A UTILITY MAY CHOOSE
    # ARE THIS TABLE'S; WHAT THEY ARE CALLED IS THE CATALOGUE'S.**
    "pw_min_length": {"choices": (8, 10, 12), "default": 8},
    "pw_expiry_days": {"choices": (None, 90, 180), "default": None},
    "session_timeout_minutes": {"choices": (15, 30, 45, 60), "default": 60},
    "absolute_session_hours": {"choices": ABSOLUTE_SESSION_HOURS_CHOICES, "default": 12},
    "keep_signed_in_offered": {"boolean": True, "default": True},
    "keep_signed_in_days": {"choices": KEEP_SIGNED_IN_DAYS_CHOICES, "default": 30},
    "lockout_max_failed": {"choices": LOCKOUT_MAX_FAILED_CHOICES, "default": 5},
    "lockout_minutes": {"choices": LOCKOUT_MINUTES_CHOICES, "default": 15},
    "field_capture_hours": {
        "choices": FIELD_CAPTURE_HOURS_CHOICES,
        "default": FIELD_CAPTURE_HOURS_DEFAULT,
    },
    # CR-188-BRC10 (PO 2026-10-22, *"don't do any hardcoding"*): how long an
    # emailed one-time sign-in link stays valid. Seeded 7 = BR-IDN-025's
    # temporary-password life, so no utility moves. Our choice list: 1 day (a
    # link a person will use today) up to 14 (a new hire starting in a fortnight).
    "password_link_valid_days": {
        "choices": PASSWORD_LINK_VALID_DAYS_CHOICES,
        "default": PASSWORD_LINK_VALID_DAYS_DEFAULT,
    },
}

#: The old spelling, kept as a DERIVED view of the one table above rather than
#: as a second list — `test_us_idn_010_security_policy.py` and the seed test
#: both read it, and two lists of allowed timeouts is how they drift.
SESSION_TIMEOUT_OPTIONS = SETTING_LIMITS["session_timeout_minutes"]["choices"]
PW_MIN_LENGTH_OPTIONS = SETTING_LIMITS["pw_min_length"]["choices"]
PW_EXPIRY_OPTIONS = SETTING_LIMITS["pw_expiry_days"]["choices"]

GENERIC_SIGN_IN_MESSAGE_KEY = "errors.auth.sign_in_failed"  # BR-IDN-002: the ONE message
#: `DEF-IDN-10620` — *"Too many wrong attempts. Try again in {{minutes}} minutes."*
#: The ONE exception to BR-IDN-002's single sentence; see `_locked_refusal`.
LOCKED_MESSAGE_KEY = "auth.sign_in.locked"

_TEMP_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _now():
    """Injection point for the frozen-time tests (monkeypatched there)."""
    return timezone.now()


def _generic_sign_in_failure() -> errors.AuthError:
    """BR-IDN-002: every authentication failure is THIS error — no enumeration,
    no factor disclosure. 401 AUTH-001 through the BE-02 envelope."""
    return errors.AuthError(errors.AUTH_UNAUTHENTICATED, message_key=GENERIC_SIGN_IN_MESSAGE_KEY)


def _locked_refusal(policy_values: dict[str, Any]) -> errors.AuthError:
    """`DEF-IDN-10620` — the refusal a LOCKED login gets, on the attempt that
    locks it and on every attempt while `locked_until` is in the future, at
    both doors (the web cookie and the field app's `auth/token`, which share
    `verify_credentials`).

    ⚠ **`minutes` IS THE UTILITY'S `lockout_minutes`, READ AT THE REFUSAL —
    NEVER A CONSTANT AND NEVER THE TIME LEFT.** PO 2026-10-27, verbatim: *"the
    lockout period, account lock after x wrong passwords should not be
    hardcoded, it should follow what the user mentions in the settings and the
    same message has to appear when the user was locked out"*. The sentence the
    PO approved (*"Try again in **M** minutes"*, M = the setting) is what is
    sent; a countdown would be a second, unapproved message.

    ⚠ **THE ENUMERATION TRADE-OFF, STATED RATHER THAN HIDDEN.** BR-IDN-002 made
    every failure one sentence so that no answer tells a stranger whether an
    address has an account. A *locked* answer does tell them that: only a real
    login can be locked. The PO asked for the message knowing what it is for —
    so the person locked out is not sent to reset a password that works — and
    the leak is bounded three ways: an UNKNOWN address never locks and so never
    gets this sentence (it stays generic however often it is tried); the
    sentence names no address and no reason beyond the wait; and reaching it
    costs the same N wrong attempts that lock the account anyway. Every other
    failure is still the one generic sentence.
    """
    return errors.AuthError(
        errors.AUTH_UNAUTHENTICATED,
        message_key=LOCKED_MESSAGE_KEY,
        params={"minutes": int(policy_values["lockout_minutes"])},
        br_ref="BR-IDN-025",
    )


def _mask_email(email: str) -> str:
    """BR-AUD-006: PII enters the trail MASKED only."""
    local, _, domain = email.partition("@")
    if not local:
        return "***"
    return f"{local[0]}***@{domain}" if domain else f"{local[0]}***"


def generate_temp_password() -> str:
    """System-generated temp password, `Xxxx-Xxxx-Xxxx` shape (US-IDN-002 §4
    fixtures). Shown once on screen, never stored raw, never logged."""
    groups = ["".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


# ── Password policy (BR-IDN-016/025 — values from the tenant policy) ────────
def validate_new_password(policy_values: dict[str, Any], password: str) -> None:
    """Validate against the tenant policy; VAL errors carry field_errors so
    the form renders inline (IS-7).

    The last-5 history is NOT checked here, deliberately: this function sees a
    password and a policy and no person, and `provision_owner` calls it for a
    user who does not exist yet. The history half is
    `_refuse_reused_password`, which `change_password` runs after this."""
    field_errors: list[dict[str, Any]] = []
    min_length = policy_values["pw_min_length"]
    if len(password) < min_length:
        field_errors.append(
            {
                "field": "new_password",
                "code": errors.VAL_RANGE,
                "message_key": "errors.identity.password_too_short",
                "params": {"min_length": min_length},
            }
        )
    if policy_values["pw_require_mixed"] and not (
        any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
    ):
        field_errors.append(
            {
                "field": "new_password",
                "code": errors.VAL_FORMAT,
                "message_key": "errors.identity.password_needs_mixed",
                "params": {},
            }
        )
    if policy_values["pw_require_symbol"] and not any(not c.isalnum() for c in password):
        field_errors.append(
            {
                "field": "new_password",
                "code": errors.VAL_FORMAT,
                "message_key": "errors.identity.password_needs_symbol",
                "params": {},
            }
        )
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key="errors.identity.password_policy",
            field_errors=field_errors,
        )


def _check_ip_allowed(policy_values: dict[str, Any], ip: str | None) -> bool:
    """BR-IDN-020: empty list = unrestricted; else the IP must fall inside one
    of the IPv4 CIDR ranges."""
    import ipaddress

    allowlist = policy_values.get("ip_allowlist") or []
    if not allowlist:
        return True
    if not ip:
        return False
    try:
        address = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    for cidr in allowlist:
        try:
            if address in ipaddress.IPv4Network(cidr):
                return True
        except ValueError:  # a bad stored value can only narrow, never open
            continue
    return False


# ── Password history + expiry (BR-IDN-025, `DEF-IDN-10022/10023`) ────────────
#
# HUMAN-REVIEW-PENDING — 🔒 identity/credentials, AI-authored 2026-10-08 under
# the PO ruling of that date. Row in `12-governance/09-human-review-ledger.md`.


def holds_temp_password(user: User) -> bool:
    """True while the password on the row is a SYSTEM-GENERATED temporary one.

    `must_change_password` alone cannot answer it any more: from 2026-10-08 an
    EXPIRED password raises the same flag (`password_expired` → `sign_in`), and
    that password is one the person chose. A temporary password always carries
    its 7-day `temp_password_expires_at` (`add_user`, `issue_temp_password`);
    an expired one never does, which is what tells the two apart.
    """
    return bool(user.must_change_password and user.temp_password_expires_at is not None)


def password_expired(user: User, policy_values: dict[str, Any], now) -> bool:
    """Has this user's password outlived the utility's `pw_expiry_days`?

    ⚠ **`DEF-IDN-10022`: UNTIL 2026-10-08 NOTHING ASKED THIS.** The setting was
    stored, validated and served, and no password ever expired.

    * `None` (the default, *Never*) → never expires. BR-IDN-025's *"no forced
      expiry"* is that default, unchanged; expiry happens only where an admin
      chose 90 or 180.
    * **Older than** the setting expires, so 90 days is still good on day 90
      and expired on day 91 — the worked figure put to the PO.
    * **The anchor is `password_changed_at`, and where that is empty, the day
      the login was created (`users.created_at`).** Recorded in the decision
      log 2026-10-08. A login whose change date was never written (seeded rows,
      logins older than the column being kept) is NOT treated as never
      expiring: that would exempt exactly the oldest passwords from the rule.
      The creation day is the earliest moment the password can have been set,
      so it errs towards asking — never towards a password older than allowed.
    * **A temporary password is out of scope** — it has its own 7-day clock
      (`TEMP_PASSWORD_VALID_DAYS`) and its own forced change already.
    """
    days = policy_values.get("pw_expiry_days")
    if not days or holds_temp_password(user):
        return False
    anchor = user.password_changed_at or user.created_at
    if anchor is None:
        return False
    return now - anchor > timedelta(days=int(days))


def _refuse_reused_password(user: User, new_password: str) -> None:
    """Refuse the CURRENT password and the last `PASSWORD_HISTORY_BLOCK`.

    Each comparison is Django's `check_password` against a stored hash — the
    password is never stored or compared in the clear. It stops at the first
    match. The cost is one hash per stored password, at most six, on an act a
    person performs a few times a year.
    """
    hashes = [user.password_hash] if user.password_hash else []
    hashes += list(
        PasswordHistory.objects.filter(user_id=user.id)
        .order_by("-created_at", "-id")
        .values_list("password_hash", flat=True)[:PASSWORD_HISTORY_BLOCK]
    )
    for stored in hashes:
        if check_password(new_password, stored):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key=PASSWORD_REUSED_MESSAGE_KEY,
                field_errors=[
                    {
                        "field": "new_password",
                        "code": errors.VAL_FORMAT,
                        "message_key": PASSWORD_REUSED_MESSAGE_KEY,
                        "params": {},
                    }
                ],
                br_ref="BR-IDN-025",
            )


def _record_outgoing_password(user: User, now) -> None:
    """Keep the hash the user is LEAVING, then prune to the newest five.

    Called BEFORE `password_hash` is overwritten. A temporary password is not
    recorded (`holds_temp_password`): nobody chose it, and it would spend one
    of five slots on a value the person could never pick again anyway.
    """
    if not user.password_hash or holds_temp_password(user):
        return
    PasswordHistory.objects.create(
        tenant_id=user.tenant_id,
        user_id=user.id,
        password_hash=user.password_hash,
        created_at=now,
    )
    keep = list(
        PasswordHistory.objects.filter(user_id=user.id)
        .order_by("-created_at", "-id")
        .values_list("id", flat=True)[:PASSWORD_HISTORY_BLOCK]
    )
    PasswordHistory.objects.filter(user_id=user.id).exclude(id__in=keep).delete()


# ── Sign-in / sign-out / session lifecycle (EP-IDN-01) ──────────────────────
#: Which app a request came from. `sign_in` defaults to `web`; the field app
#: declares `mobile` through `POST /auth/session`'s `surface` field.
#: ⚠ **THIS COMMENT SAID *"the phone passes `mobile` when `US-WRK-030` lands"*
#: UNTIL 2026-10-04, AND NOTHING EVER PASSED IT (`DEF-WRK-9583`)** — the
#: endpoint dropped the argument, so every field-scoped login was refused on
#: every door while the tests that called this function directly stayed green.
#: Kept as a constant pair so a typo is a NameError rather than a
#: silently-allowed sign-in.
SURFACE_WEB = "web"
SURFACE_MOBILE = "mobile"
SURFACE_BOTH = "both"

#: `OQ-WRK-1494`, ruled 2026-09-04. The server sends only the KEY; the words
#: are the catalogue's. ⚠ **IT READ SIX WORDS — *"Sign in on the field app."* —
#: UNTIL 2026-10-06**, when the PO ruled two sentences for this one message as
#: an exception to B14 rule 33's cap (`DEF-IDN-9777`, decision log): *"Field
#: Technicians do not have access to the staff portal. Please sign in on the
#: Field Technician mobile app instead."* The second sentence is its own key.
SURFACE_REFUSED_MESSAGE_KEY = "identity.signIn.fieldAppOnly"

#: DEF-WRK-9583 — the same refusal in the OTHER direction: a login scoped to
#: `web` knocking on the field app. Until 2026-10-04 both directions sent
#: *"Sign in on the field app."*, which told an office-only clerk standing on
#: the phone to go to the phone. Six words (B14 rule 33).
SURFACE_REFUSED_WEB_ONLY_MESSAGE_KEY = "identity.signIn.webAppOnly"

#: `CR-145-BRC08`. Six words, B14 rule 33's cap for an instruction, and it says
#: what to do rather than why the utility chose it (rule 33 puts RATIONALE at
#: zero words on screen).
KEEP_SIGNED_IN_REFUSED_MESSAGE_KEY = "identity.signIn.keepSignedInUnavailable"


def sign_in(
    *,
    tenant_id: Any,
    email: str,
    password: str,
    keep_signed_in: bool = False,
    ip: str | None = None,
    user_agent: str | None = None,
    surface: str = SURFACE_WEB,
) -> Session:
    """US-IDN-001: the PATH resolved the tenant FIRST (BR-IDN-001/029, PO ruling
    2026-08-10 — the caller passes the middleware-resolved tenant_id, the
    same one the URL named, never client input);
    then (tenant, email) credentials + active-or-invited membership.

    Every failure path raises the ONE generic error (BR-IDN-002); wrong
    passwords count toward the 5-fail → 15-min lock (BR-IDN-025)."""
    now = _now()
    user, membership, policy_values = verify_credentials(
        tenant_id=tenant_id, email=email, password=password, ip=ip, surface=surface, now=now
    )
    return _sign_in_after_verification(
        tenant_id=tenant_id,
        user=user,
        membership=membership,
        policy_values=policy_values,
        now=now,
        keep_signed_in=keep_signed_in,
        ip=ip,
        user_agent=user_agent,
    )


def verify_credentials(
    *,
    tenant_id: Any,
    email: str,
    password: str,
    ip: str | None,
    surface: str,
    now,
) -> tuple[User, TenantMembership, dict[str, Any]]:
    """The credential half of `sign_in`, shared with the native app's
    `POST auth/token` (`CR-187-BRC10`) so BOTH doors run ONE lockout, ONE
    allowed-addresses check, ONE generic failure and ONE surface rule.

    ⚠ **EXTRACTED, NOT REWRITTEN (2026-10-21).** The statements below are the
    ones `sign_in` ran, in the same order, moved verbatim; `sign_in` calls this
    first and then does exactly what it did after them. The web cookie path is
    therefore unchanged, and its own tests (`test_us_idn_001*`, `_003*`) are
    the proof. HUMAN-REVIEW-PENDING — 🔒 identity/credentials.
    """
    policy_values = selectors.security_policy_values(tenant_id)
    if not _check_ip_allowed(policy_values, ip):
        # BR-IDN-020 / US-IDN-010 TC-6: enforced at sign-in — 403, generic
        # denial; the BE-02 handler writes the BR-AUD-018 attempt row.
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            message_key=GENERIC_SIGN_IN_MESSAGE_KEY,
            br_ref="BR-IDN-020",
        )

    user = selectors.user_by_email(tenant_id, email)
    if user is None:
        _equalize_timing()
        raise _generic_sign_in_failure()

    if user.locked_until is not None and user.locked_until > now:
        # BR-IDN-025: even correct credentials are refused while locked (TC-8).
        # One hash first, so the locked answer takes as long as a wrong
        # password's (BR-IDN-002 timing equalisation); then the named refusal
        # with the utility's own minutes (`DEF-IDN-10620`).
        _equalize_timing()
        raise _locked_refusal(policy_values)

    password_ok = bool(user.password_hash) and check_password(password, user.password_hash)
    if password_ok and user.must_change_password:
        expiry = user.temp_password_expires_at
        if expiry is not None and expiry < now:
            # Expired temp password signs in never (BR-IDN-025); generic error.
            raise _generic_sign_in_failure()

    if not password_ok:
        if _register_failed_attempt(user, now, policy_values):
            raise _locked_refusal(policy_values)  # the attempt that locks (DEF-IDN-10620)
        raise _generic_sign_in_failure()

    membership = selectors.membership_for_user(tenant_id, user.id)
    if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
        raise _generic_sign_in_failure()  # TC-4: no disclosure of the reason

    # ⚠ **ONE LOGIN, ONE SURFACE — `OQ-WRK-1494`, ruled 2026-09-04, option (a)**
    # (`BR-WRK-043`, `US-WRK-023` TC-2). PO verbatim: *"Field technicians will
    # not logn to web app; they will login to mobile app only"*.
    #
    # ⚠ **AND THIS REFUSAL IS NAMED, WHERE EVERY OTHER ONE ABOVE IS GENERIC.**
    # `BR-IDN-002` makes a failed sign-in say nothing — wrong password, no such
    # email and a deactivated membership are one sentence, because anything
    # else is an oracle for whether an address exists. This one is different in
    # kind and telling the truth costs nothing: the credentials were CORRECT
    # and the person is standing at the wrong door. *"Sign in on the field
    # app."* discloses no account that the person signing in does not already
    # know they have, and a generic failure here would send a technician to
    # reset a password that works perfectly.
    if not _surface_allowed(user.surface_scope, surface):
        core_audit.write_row(
            action="auth.sign_in_wrong_surface",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={"email": _mask_email(user.email), "surface": surface},
        )
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            message_key=(
                SURFACE_REFUSED_MESSAGE_KEY
                if surface == SURFACE_WEB
                else SURFACE_REFUSED_WEB_ONLY_MESSAGE_KEY
            ),
            br_ref="BR-WRK-043",
        )
    return user, membership, policy_values


def _sign_in_after_verification(
    *,
    tenant_id: Any,
    user: User,
    membership: TenantMembership,
    policy_values: dict[str, Any],
    now,
    keep_signed_in: bool,
    ip: str | None,
    user_agent: str | None,
) -> Session:
    """`sign_in`'s second half — everything after the credentials passed."""
    # ── `CR-145-BRC08` · *"Keep me signed in"* may be switched OFF ─────────
    #
    # ⚠ **REFUSED, NOT SILENTLY IGNORED, AND THE REFUSAL IS NOT THE GENERIC
    # ONE.** Dropping the flag to `False` would sign the person in with a
    # session that quietly dies at the end of the day, which is the tick box
    # lying rather than being absent. And the generic sign-in failure would be
    # WRONG here in the same way `BR-WRK-043`'s surface refusal is: the
    # credentials were correct and nothing about the account is being
    # disclosed — the utility has turned an option off, and the screen must be
    # able to say so and stop offering it.
    #
    # A browser that never sees the box cannot send the flag, so in practice
    # this is reached by a stale tab, a saved form or a direct caller. The
    # screen reads `keep_signed_in_offered` from
    # `GET auth/sign-in-options` and does not render the box at all.
    if keep_signed_in and not policy_values["keep_signed_in_offered"]:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=KEEP_SIGNED_IN_REFUSED_MESSAGE_KEY,
            field_errors=[
                {
                    "field": "keep_signed_in",
                    "code": errors.VAL_RANGE,
                    "message_key": KEEP_SIGNED_IN_REFUSED_MESSAGE_KEY,
                    "params": {},
                }
            ],
            br_ref="BR-IDN-026",
        )

    user.failed_attempts = 0
    user.locked_until = None
    # ⚠ **`DEF-IDN-10022` — AN EXPIRED PASSWORD SIGNS IN TO THE FORCED CHANGE.**
    # Reuse, not a new screen: raising `must_change_password` is exactly what
    # a temporary password does, so `routeAfterSignIn` lands on the existing
    # change-password page and `auth.py`'s gate refuses every other call until
    # the change is made. It is raised only on a SUCCESSFUL sign-in — after the
    # password, the lock, the membership and the surface all passed — so a
    # wrong password still counts towards the lockout and says nothing about
    # expiry. A temporary password is never touched (`password_expired`
    # returns False for one), so the invite path is unchanged.
    expired = password_expired(user, policy_values, now)
    if expired:
        user.must_change_password = True
    user.save(
        update_fields=["failed_attempts", "locked_until", "must_change_password", "updated_at"]
    )

    session = Session.objects.create(
        user=user,
        tenant_id=tenant_id,
        persistent=keep_signed_in,  # off by default (BR-IDN-026)
        last_seen_at=now,
        # `CR-145-BRC08` — the utility's own hard limit, not a platform
        # constant. `policy_values` was already read at the top of this
        # function for the IP allowlist, so this costs no extra query.
        expires_at=now + timedelta(hours=policy_values["absolute_session_hours"]),
        ip=ip,
        user_agent=user_agent or "",
    )
    membership.last_active_at = now
    membership.save(update_fields=["last_active_at", "updated_at"])
    core_audit.write_row(
        action="auth.sign_in",
        entity_type="session",
        entity_id=session.id,
        actor_user_id=user.id,
        after={
            "email": _mask_email(user.email),
            "persistent": keep_signed_in,
            **({"password_expired": True} if expired else {}),
        },
    )
    return session


def _surface_allowed(scope: str | None, surface: str) -> bool:
    """`both` opens every door; anything else must match exactly.

    A NULL or empty scope reads as `both`, which is what every login that
    existed before `identity/0005` has and is why the column changed nothing
    for anyone on the day it landed.
    """
    return (scope or SURFACE_BOTH) in (SURFACE_BOTH, surface)


def surface_scope_for_role(
    role_code: str, current_scope: str | None, *, before_role: str | None = None
) -> str:
    """`DEF-IDN-9748` — the ONE place a role decides which door a login opens.

    `OQ-WRK-1494` (PO 2026-09-04, verbatim: *"Field technicians will not logn
    to web app; they will login to mobile app only"*) is enforced by `sign_in`
    reading `users.surface_scope`, and until 2.548.2 nothing but the demo seed
    ever wrote that column — so every technician a utility added in Settings ›
    Users kept the default `both`, opened the staff web app and dead-ended on
    *"We couldn't load your regional settings."* (customer, sandbox,
    2026-10-05). `add_user` and `update_user` both answer through here:

      * TO `field_technician` → `mobile`, whatever the scope was.
      * AWAY from `field_technician`, while the scope is `mobile` → `both`, the
        default every office login is created with. A staff user must never be
        left stuck on the phone by a role they no longer hold. (Decision log
        2026-10-05; ours, not put to the PO — law 13.)
      * Between two OFFICE roles → unchanged. A `web`-only scope somebody chose
        is a choice, not a default this function may overwrite.
    """
    if role_code == FIELD_TECHNICIAN:
        return SURFACE_MOBILE
    if before_role == FIELD_TECHNICIAN and (current_scope or SURFACE_BOTH) == SURFACE_MOBILE:
        return SURFACE_BOTH
    return current_scope or SURFACE_BOTH


def _register_failed_attempt(user: User, now, policy_values: dict[str, Any]) -> bool:
    """BR-IDN-025 lockout counter: audit every failure; the Nth locks for M minutes.

    Returns True when THIS attempt locked the login, so the caller can answer
    it with the locked sentence rather than the generic one (`DEF-IDN-10620`).

    ⚠ **N AND M ARE THE UTILITY'S OWN (`CR-145-BRC08`), NOT 5 AND 15.** This
    docstring said *"the 5th locks 15 min"* until 2026-09-28, which is still
    what a utility that has never opened the Security tab gets — the column
    defaults are today's values — but it is no longer what the CODE says, and a
    docstring naming a number the code does not hold is hard-won law 1.
    """
    max_failed = policy_values["lockout_max_failed"]
    lock_minutes = policy_values["lockout_minutes"]
    user.failed_attempts += 1
    lockout = user.failed_attempts >= max_failed
    if lockout:
        user.locked_until = now + timedelta(minutes=lock_minutes)
        user.failed_attempts = 0  # counter restarts after the lock window
    user.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    core_audit.write_row(
        action="auth.sign_in_failed",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=None,  # the attempt is unauthenticated
        after={"email": _mask_email(user.email)},
    )
    if lockout:
        core_audit.write_row(
            action="auth.lockout",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=None,
            after={"locked_minutes": lock_minutes},
        )
    return lockout


_dummy_hash: str | None = None  # lazily built with the ACTIVE hasher config


def _equalize_timing() -> None:
    """BR-IDN-002 (US-IDN-001 TC-3): unknown-email responses take the same
    hashing time as wrong-password responses — no timing enumeration."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = make_password("smartbillhub-timing-equalizer")
    check_password("timing-equalizer", _dummy_hash)


def sign_out(*, session: Session) -> None:
    """US-IDN-003 TC-1 (BR-IDN-007): revoke server-side, immediately."""
    now = _now()
    session.revoked_at = now
    session.save(update_fields=["revoked_at"])
    core_audit.write_row(
        action="auth.sign_out",
        entity_type="session",
        entity_id=session.id,
        actor_user_id=session.user_id,
    )


def touch_session(session: Session) -> None:
    """Sliding idle window (US-IDN-003 TC-4): last_seen_at follows activity."""
    session.last_seen_at = _now()
    session.save(update_fields=["last_seen_at"])


def refresh_persistent_session(session: Session) -> None:
    """BR-IDN-026 trusted-device refresh: silently re-establish a persistent
    session within the utility's renewal window (Eng disposition: same row —
    last_seen/expiry reset; no refresh-token storage is anchored).

    ⚠ **THE NEW EXPIRY IS THE UTILITY'S HARD LIMIT (`CR-145-BRC08`)**, which
    was a fixed 12 hours until 2026-09-28. Whether this function may be called
    at all — persistent, unrevoked, and inside the renewal window — is
    `auth.IdentitySessionAuthentication._refreshable`'s question, and that one
    now reads the utility's renewal days.
    """
    now = _now()
    policy_values = selectors.security_policy_values(session.tenant_id)
    session.last_seen_at = now
    session.expires_at = now + timedelta(hours=policy_values["absolute_session_hours"])
    session.save(update_fields=["last_seen_at", "expires_at"])


def revoke_sessions(*, user: User, except_session: Session | None = None) -> int:
    """Server-side, immediate (BR-IDN-006). Users are per-tenant rows
    (BR-IDN-029), so 'all this user's sessions' is already tenant-scoped."""
    queryset = Session.objects.filter(user=user, revoked_at__isnull=True)
    if except_session is not None:
        queryset = queryset.exclude(pk=except_session.pk)
    return queryset.update(revoked_at=_now())


def _revoke_native_tokens(user: User) -> int:
    """`CR-187-BRC10` — where a password change signs the login's OTHER web
    sessions out, it signs its native-app tokens out too: a password changed
    because a phone was lost must end that phone's access, not only the
    browser's. Lazy import: `native` imports this module."""
    from apps.identity import native

    return native.revoke_user_tokens(user=user)


# ── User management (EP-IDN-02 — System Admin only, server-enforced) ────────
#: `CR-187-BRC10` — a phone number is a sign-in name on the field app (PO
#: 2026-10-21: work email OR phone), so it is unique inside one utility.
PHONE_IN_USE_MESSAGE_KEY = "errors.identity.phone_in_use"
PHONE_INVALID_MESSAGE_KEY = "errors.identity.phone_invalid"


def clean_phone(
    tenant_id: Any, raw: Any, *, user_id: Any = None, field: str = "phone"
) -> str | None:
    """The phone to store for a save, or None to clear it — refused BY NAME
    when it is not a number (`phone_invalid`) or another login at THIS utility
    already holds it (`phone_in_use`). A login at another utility holding the
    same number is never a conflict and is never revealed (BR-IDN-029's shape).

    Checked BEFORE the write rather than caught after it: a unique violation
    poisons a PostgreSQL transaction (hard-won law 14). The partial index
    `uq_users_tenant_phone_e164` is the guarantee; this is the sentence."""
    from apps.identity.phones import normalise_phone

    text = str(raw or "").strip()
    if not text:
        return None
    if normalise_phone(text) is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=PHONE_INVALID_MESSAGE_KEY,
            field_errors=[
                {"field": field, "code": errors.VAL_FORMAT,
                 "message_key": PHONE_INVALID_MESSAGE_KEY, "params": {}}
            ],
        )
    if selectors.phone_holder(tenant_id, text, exclude_user_id=user_id) is not None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=PHONE_IN_USE_MESSAGE_KEY,
            field_errors=[
                {"field": field, "code": errors.VAL_FORMAT,
                 "message_key": PHONE_IN_USE_MESSAGE_KEY, "params": {}}
            ],
        )
    return text


def _phone_changes(user: User, raw: str) -> bool:
    """A save of `raw` would change something: the number as typed, OR its
    sign-in form — so re-saving a number the `identity/0013` backfill left
    NULL (it was shared then, and is free now) switches its sign-in on."""
    from apps.identity.phones import normalise_phone

    text = raw.strip() or None
    return text != user.phone or normalise_phone(text) != user.phone_e164


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def add_user(
    *,
    actor: User,
    tenant_id: Any,
    full_name: str,
    email: str,
    role_code: str,
    phone: str | None = None,
) -> tuple[User, TenantMembership, str]:
    """US-IDN-005: create the tenant-scoped user + invited membership and
    return the ONE-TIME temp password (BR-IDN-022 — the caller shows it once
    and never sees it again).

    ⚠ **AMENDED 2026-10-22 (`CR-188-BRC10`).** This read *"BR-IDN-021 — no
    email is sent"*. The PO superseded BR-IDN-021 for invitations: the API
    now ALSO emails a one-time sign-in link (`password_links.email_access_link`),
    AFTER this returns, so a utility with no mail provider still creates the
    user. This function is unchanged; the email is never a password."""
    role = selectors.role_by_code(role_code)
    if role is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="errors.identity.unknown_role",
            field_errors=[
                {
                    "field": "role",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "errors.identity.unknown_role",
                    "params": {"role": role_code},
                }
            ],
        )
    existing = selectors.user_by_email(tenant_id, email)
    if existing is not None:
        existing_membership = selectors.membership_for_user(tenant_id, existing.id)
        if (
            existing_membership is not None
            and existing_membership.status == TenantMembership.STATUS_DEACTIVATED
        ):
            # BR-IDN-030 (PO 2026-08-09): a deactivated email is NEVER freed for
            # re-use and the person is never re-added — the returning person is
            # REACTIVATED (existing row). 409 BIZ-STATE; the message key points
            # the admin to the Reactivate row action (US-IDN-006 TC-3).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-IDN-030",
                message_key="errors.identity.email_deactivated_reactivate",
                params={"user_id": str(existing.id)},
            )
        # BR-IDN-010/029: already a member of THIS tenant → rejected. The same
        # email in ANOTHER tenant is a different user and never a conflict.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-IDN-010",
            message_key="errors.identity.already_a_member",
        )
    stored_phone = clean_phone(tenant_id, phone)  # CR-187-BRC10: unique per utility
    now = _now()
    temp_password = generate_temp_password()
    user = User.objects.create(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        phone=stored_phone,
        password_hash=make_password(temp_password),
        must_change_password=True,  # BR-IDN-022
        temp_password_expires_at=now + timedelta(days=TEMP_PASSWORD_VALID_DAYS),
        # DEF-IDN-9748 — a technician is created on the phone only (BR-WRK-043).
        surface_scope=surface_scope_for_role(role.code, None),
    )
    membership = TenantMembership.objects.create(
        tenant_id=tenant_id,
        user=user,
        role=role,
        status=TenantMembership.STATUS_INVITED,  # BR-IDN-011
        invited_at=now,
        invited_by_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081 — never the object
    )
    core_audit.money_action(
        actor,
        "user.invited",
        "user",
        user.id,
        after={"email": _mask_email(email), "role": role.code, "status": "invited"},
    )
    return user, membership, temp_password


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def issue_temp_password(*, actor: User, user: User, membership: TenantMembership) -> str:
    """US-IDN-002 TC-2 / US-IDN-005 TC-5: issue (forgot-password assist) or
    reset (invited row) a temp password — prior value void IMMEDIATELY
    (BR-IDN-011/023), 7-day validity (BR-IDN-025), shown once.

    ⚠ `CR-188-BRC10` (2026-10-22): every live emailed sign-in link of this
    login is VOIDED here too — a reset replaces every way in. The API then
    issues a fresh link and emails it (PO answer 4, *"email it as well"*)."""
    now = _now()
    PasswordLink.objects.filter(
        user_id=user.id, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now, revoked_reason=PasswordLink.REVOKED_SUPERSEDED)
    temp_password = generate_temp_password()
    # `DEF-IDN-10023` — the password the reset REPLACES joins the history, so
    # the forced change that follows cannot go straight back to it.
    _record_outgoing_password(user, now)
    user.password_hash = make_password(temp_password)
    user.must_change_password = True
    user.temp_password_expires_at = now + timedelta(days=TEMP_PASSWORD_VALID_DAYS)
    user.save(
        update_fields=[
            "password_hash",
            "must_change_password",
            "temp_password_expires_at",
            "updated_at",
        ]
    )
    action = (
        "user.temp_password_reset"
        if membership.status == TenantMembership.STATUS_INVITED
        else "auth.temp_password_issued"
    )
    core_audit.money_action(
        actor,
        action,
        "user",
        user.id,
        after={"expires_at": user.temp_password_expires_at.isoformat()},
    )
    return temp_password


def _guard_last_admin(membership: TenantMembership, *, br_action: str) -> None:
    """BR-IDN-013: a tenant always retains ≥1 ACTIVE System Admin — the last
    one cannot be demoted, deactivated, or removed."""
    if not selectors.is_active_system_admin(membership):
        return
    if selectors.active_system_admin_count(membership.tenant_id) <= 1:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-IDN-013",
            message_key="errors.identity.last_system_admin",
            params={"action": br_action},
        )


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def update_user(
    *,
    actor: User,
    user: User,
    membership: TenantMembership,
    full_name: str | None = None,
    email: str | None = None,
    role_code: str | None = None,
    phone: str | None = None,
) -> User:
    """US-IDN-006 TC-1 (role) + BR-IDN-017 v1 (email is changed by a System
    Admin through THIS endpoint — the 11b §2.2 ratified row; see the E2 note
    on US-IDN-008 TC-2 in the build report). Every change audited."""
    if role_code is not None and role_code != membership.role.code:
        role = selectors.role_by_code(role_code)
        if role is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="errors.identity.unknown_role"
            )
        if membership.status == TenantMembership.STATUS_DEACTIVATED:
            # Deactivated rows offer Reactivate/Remove only (EP-IDN-02 matrix).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-IDN-012",
                message_key="errors.identity.row_state_disallows",
            )
        if role.code != SYSTEM_ADMIN:
            _guard_last_admin(membership, br_action="demote")
        before_role = membership.role.code
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
        core_audit.money_action(
            actor,
            "user.role_changed",
            "tenant_membership",
            membership.id,
            before={"role": before_role},
            after={"role": role.code},
        )
        # DEF-IDN-9748 — the role decides the door: to technician → the phone
        # only; back to an office role → both again (see the helper).
        scope = surface_scope_for_role(role.code, user.surface_scope, before_role=before_role)
        if scope != user.surface_scope:
            before_scope = user.surface_scope
            user.surface_scope = scope
            user.save(update_fields=["surface_scope", "updated_at"])
            core_audit.money_action(
                actor,
                "user.surface_scope_changed",
                "user",
                user.id,
                before={"surface_scope": before_scope},
                after={"surface_scope": scope},
            )
    if email is not None and email.lower() != user.email.lower():
        other = selectors.user_by_email(user.tenant_id, email)
        if other is not None and other.pk != user.pk:
            # BR-IDN-029 per-tenant uniqueness (US-IDN-008 TC-9); a match in a
            # DIFFERENT tenant is not a conflict and is never revealed.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-IDN-029",
                message_key="errors.identity.email_taken",
            )
        before_email = user.email
        user.email = email
        user.save(update_fields=["email", "updated_at"])
        core_audit.money_action(
            actor,
            "user.email_changed",
            "user",
            user.id,
            before={"email": _mask_email(before_email)},
            after={"email": _mask_email(email)},  # no verification mail v1 (BR-IDN-027/021)
        )
    if phone is not None and _phone_changes(user, phone):
        # CR-187-BRC10 — the office sets a technician's phone here; it is a
        # field-app sign-in name, so unique inside this utility. An empty
        # value clears it. The trail holds it masked (BR-AUD-006).
        from apps.identity.phones import mask_phone

        stored = clean_phone(user.tenant_id, phone, user_id=user.id)
        before_phone = user.phone
        user.phone = stored
        user.save(update_fields=["phone", "updated_at"])
        core_audit.money_action(
            actor,
            "user.phone_changed",
            "user",
            user.id,
            before={"phone": mask_phone(before_phone) if before_phone else None},
            after={"phone": mask_phone(stored) if stored else None},
        )
    if full_name is not None and full_name != user.full_name:
        before_name = user.full_name
        user.full_name = full_name
        user.save(update_fields=["full_name", "updated_at"])
        core_audit.money_action(
            actor,
            "user.profile_updated",
            "user",
            user.id,
            before={"full_name": before_name},
            after={"full_name": full_name},
        )
    return user


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def deactivate_user(*, actor: User, user: User, membership: TenantMembership) -> TenantMembership:
    """US-IDN-006 TC-2 (BR-IDN-012): block sign-in + revoke this tenant's
    sessions at once; the row and all history are kept."""
    if membership.status != TenantMembership.STATUS_ACTIVE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-IDN-012",
            message_key="errors.identity.row_state_disallows",
        )
    _guard_last_admin(membership, br_action="deactivate")
    before_status = membership.status
    membership.status = TenantMembership.STATUS_DEACTIVATED
    membership.save(update_fields=["status", "updated_at"])
    revoke_sessions(user=user)
    core_audit.money_action(
        actor,
        "user.deactivated",
        "tenant_membership",
        membership.id,
        before={"status": before_status},
        after={"status": membership.status},
    )
    return membership


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def reactivate_user(*, actor: User, user: User, membership: TenantMembership) -> TenantMembership:
    """US-IDN-006 TC-3: back to active — the existing password works again."""
    if membership.status != TenantMembership.STATUS_DEACTIVATED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-IDN-012",
            message_key="errors.identity.row_state_disallows",
        )
    before_status = membership.status
    membership.status = TenantMembership.STATUS_ACTIVE
    membership.save(update_fields=["status", "updated_at"])
    core_audit.money_action(
        actor,
        "user.reactivated",
        "tenant_membership",
        membership.id,
        before={"status": before_status},
        after={"status": membership.status},
    )
    return membership


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def remove_user(*, actor: User, user: User, membership: TenantMembership) -> None:
    """US-IDN-007 as REWORKED by BR-IDN-030 (PO 2026-08-09): removal is
    PERMANENT DEACTIVATION. The user row, email, and name stay exactly as
    they are (audit history intact); the email is NEVER freed for re-use;
    nothing is deleted — so the BR-IDN-012 reference-count audit-lock has
    nothing left to protect and no longer blocks (E2 tension with the
    unamended BR-IDN-012/US-IDN-007 §2 wording reported, not resolved).
    Sessions die at once; a returning person is REACTIVATED (existing row,
    US-IDN-006 TC-3), never re-added — the add path answers 409 BIZ-STATE
    pointing to Reactivate (BR-IDN-030)."""
    _guard_last_admin(membership, br_action="remove")
    revoke_sessions(user=user)
    before_status = membership.status
    if membership.status != TenantMembership.STATUS_DEACTIVATED:
        membership.status = TenantMembership.STATUS_DEACTIVATED
        membership.save(update_fields=["status", "updated_at"])
    core_audit.money_action(
        actor,
        "user.removed",
        "tenant_membership",
        membership.id,
        before={"email": _mask_email(user.email), "status": before_status},
        after={"email": _mask_email(user.email), "status": membership.status},
    )


# ── Self-service (EP-IDN-03 — any authenticated role, own row only) ─────────
@transaction.atomic
def update_profile(*, actor: User, full_name: str | None = None, phone: str | None = None) -> User:
    """US-IDN-008 TC-1 (BR-IDN-015): name/phone on the actor's OWN row. Role
    and email are handled by the API layer as privilege-guarded fields
    (BR-IDN-027 role-never / BR-IDN-017 email = admin endpoint in v1)."""
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    if full_name is not None and full_name != actor.full_name:
        before["full_name"], after["full_name"] = actor.full_name, full_name
        actor.full_name = full_name
    if phone is not None and _phone_changes(actor, phone):
        # CR-187-BRC10 — unique per utility, refused by name (`phone_in_use`).
        phone = clean_phone(actor.tenant_id, phone, user_id=actor.id)
        before["phone"], after["phone"] = actor.phone, phone
        actor.phone = phone
    if not after:
        return actor
    actor.save(update_fields=[*after.keys(), "updated_at"])
    core_audit.money_action(
        actor, "user.profile_updated", "user", actor.id, before=before, after=after
    )
    return actor


@transaction.atomic
def change_password(
    *,
    actor: User,
    new_password: str,
    confirm_password: str,
    current_password: str | None = None,
    sign_out_other_sessions: bool = True,
    current_session: Session | None = None,
) -> User:
    """US-IDN-008 TC-3..6 + the forced first-sign-in change (US-IDN-002 TC-3,
    BR-IDN-022): one service, two audit actions. Forced completion revokes
    ALL prior sessions (BR-IDN-005) and activates an invited membership
    (BR-IDN-011)."""
    forced = actor.must_change_password
    if not forced:
        if not current_password or not (
            actor.password_hash and check_password(current_password, actor.password_hash)
        ):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="errors.identity.current_password_incorrect",
                field_errors=[
                    {
                        "field": "current_password",
                        "code": errors.VAL_FORMAT,
                        "message_key": "errors.identity.current_password_incorrect",
                        "params": {},
                    }
                ],
            )
    if new_password != confirm_password:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="errors.identity.password_confirm_mismatch",
            field_errors=[
                {
                    "field": "confirm_password",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.password_confirm_mismatch",
                    "params": {},
                }
            ],
        )
    policy_values = selectors.security_policy_values(actor.tenant_id)
    validate_new_password(policy_values, new_password)
    # `DEF-IDN-10023` — on BOTH paths, the forced one included: an expired
    # password must not be "changed" to itself, and a reset user must not go
    # straight back to the password they had before the reset.
    _refuse_reused_password(actor, new_password)

    now = _now()
    was_temp = holds_temp_password(actor)
    # `CR-188-BRC10` — a password chosen by ANY route voids every emailed
    # sign-in link still live: a link left behind would let whoever reads that
    # mailbox later choose another password.
    PasswordLink.objects.filter(
        user_id=actor.id, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now, revoked_reason=PasswordLink.REVOKED_PASSWORD_CHANGED)
    _record_outgoing_password(actor, now)
    actor.password_hash = make_password(new_password)
    actor.password_changed_at = now
    actor.must_change_password = False
    actor.temp_password_expires_at = None
    actor.save(
        update_fields=[
            "password_hash",
            "password_changed_at",
            "must_change_password",
            "temp_password_expires_at",
            "updated_at",
        ]
    )
    if forced:
        # BR-IDN-005: the successful forced change revokes ALL prior sessions.
        revoke_sessions(user=actor, except_session=current_session)
        _revoke_native_tokens(actor)
        membership = selectors.membership_for_user(actor.tenant_id, actor.id)
        if membership is not None and membership.status == TenantMembership.STATUS_INVITED:
            membership.status = TenantMembership.STATUS_ACTIVE  # BR-IDN-011 activation
            membership.save(update_fields=["status", "updated_at"])
        # A temporary password being replaced is a RESET; an expired one the
        # person chose being replaced is an ordinary CHANGE (`DEF-IDN-10022`).
        core_audit.money_action(
            actor, "auth.password_reset" if was_temp else "auth.password_changed", "user", actor.id
        )
    else:
        if sign_out_other_sessions:  # default on (BR-IDN-016)
            revoke_sessions(user=actor, except_session=current_session)
            _revoke_native_tokens(actor)
        core_audit.money_action(actor, "auth.password_changed", "user", actor.id)
    return actor


# ── Security policy (EP-IDN-04) ─────────────────────────────────────────────
@require_role(SYSTEM_ADMIN)
@transaction.atomic
def save_security_policy(
    *, actor: User, tenant_id: Any, values: dict[str, Any], actor_ip: str | None
) -> SecurityPolicy:
    """US-IDN-010 (BR-IDN-019): one tenant-wide record, atomic save,
    before/after audit. Self-lockout guard per BR-IDN-020: the saving
    admin's current IP must fall inside the new allowlist."""
    # ⚠ **READ BEFORE VALIDATE, AND DO NOT CREATE THE ROW YET.** The stored
    # values are what `_validate_policy_values`'s retained-value exemption
    # tests against (2026-09-29 redesign). A rowless utility has nothing
    # stored, so it gets no exemption — and it needs none, because every
    # column default is an offered value. `get_or_create` stays BELOW the
    # validation: a refused save must leave no row behind (US-IDN-010 T2).
    existing = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    current = {field: getattr(existing, field) for field in SETTING_LIMITS} if existing else {}
    _validate_policy_values(values, current)
    allowlist = values.get("ip_allowlist", [])
    if allowlist and not _check_ip_allowed({"ip_allowlist": allowlist}, actor_ip):
        raise errors.BizError(
            errors.BIZ_STATE,  # E2 note: 11b row says "422 BIZ-STATE"; the B12
            br_ref="BR-IDN-020",  # §3 catalog maps BIZ-STATE→409 — reported.
            message_key="errors.identity.allowlist_self_lockout",
            params={"ip": actor_ip},
        )
    policy, _created = SecurityPolicy.objects.get_or_create(tenant_id=tenant_id)
    editable = (
        "pw_min_length",
        "pw_require_mixed",
        "pw_require_symbol",
        "pw_expiry_days",
        "session_timeout_minutes",
        # `CR-145-BRC08` — the five new ones. They are in the SAME tuple as the
        # six that were already here, which is what makes the before/after
        # audit row cover them: `before`, `after` and `changed` are all derived
        # from this one list, so adding a column here is the whole of B11.
        "absolute_session_hours",
        "keep_signed_in_offered",
        "keep_signed_in_days",
        "lockout_max_failed",
        "lockout_minutes",
        "ip_allowlist",
        # PO 2026-10-21 item 2 — the field app's capture life. In this tuple
        # for the same reason as the five above: the audit row is derived
        # from it, so a change to the capture life is audited before/after.
        "field_capture_hours",
        # CR-188-BRC10 — audited before/after like every setting above.
        "password_link_valid_days",
    )
    before ={field: getattr(policy, field) for field in editable if field in values}
    for field in editable:
        if field in values:
            setattr(policy, field, values[field])
    policy.save()
    after = {field: getattr(policy, field) for field in before}
    changed = {field for field in before if before[field] != after[field]}
    core_audit.money_action(
        actor,
        "settings.security_updated",
        "security_policy",
        policy.id,
        before={field: before[field] for field in changed},
        after={field: after[field] for field in changed},
    )
    return policy


def _validate_policy_values(values: dict[str, Any], current: dict[str, Any] | None = None) -> None:
    """Option-set + CIDR validation per the US-IDN-010 §5 validation column.

    ⚠ **`current` IS THE ONE EXEMPTION, AND IT EXISTS SO THAT NOBODY IS MOVED
    (Settings → Security redesign, 2026-09-29).** Four ranges became choice
    lists on that date, and two of those lists are narrower than the range
    they replace, so a utility can be sitting on a value the screen no longer
    offers. It must still be able to save the tab — the browser sends the
    whole policy, so refusing the untouched field would refuse every save it
    ever makes and take the Security tab down for that utility until somebody
    noticed. **A value EQUAL to what is already stored is therefore allowed;
    a value that is neither stored nor offered is refused by name.**

    ⚠ **IT IS ONE VALIDATOR AND ONE LOOP, DELIBERATELY.** The exemption is a
    guard clause inside the existing loop, not a second pass beside it: two
    validators for eight settings is how the list a screen renders drifts
    from the list the server accepts, which is the defect this whole table
    was built to prevent.

    ⚠ **AND IT IS A ONE-WAY DOOR.** The exemption tests the value ALREADY IN
    THE DATABASE, so once a utility moves off an unoffered value it can never
    move back to it. That is the intended asymmetry: the value is retained,
    not restored.
    """
    import ipaddress

    current = current or {}
    field_errors: list[dict[str, Any]] = []
    # ⚠ The two password option checks that stood here are now entries in
    # `SETTING_LIMITS` and are refused by the loop below (DEF-IDN-7501) — same
    # code, same key, same `allowed`, so no refusal a person sees has moved.
    # ── `CR-145-BRC08` · the six settings, against `SETTING_LIMITS` ────────
    #
    # ⚠ **ONE LOOP, AND `session_timeout_minutes` IS INSIDE IT.** That field
    # used to have a hand-written block here of exactly the shape below. Two
    # validators for six settings is how a list of allowed timeouts drifts
    # from the list a screen renders, so the choice-list branch is the old
    # block generalised rather than a new path beside it.
    #
    # ⚠ **EVERY REFUSAL NAMES THE FIELD AND WHAT IS ALLOWED.** The `params`
    # carry the choices or the floor and ceiling, so the message the clerk
    # reads can say *"between 3 and 10"* without the server composing an
    # English sentence into a JSON column (B14 rule 35: eleven catalogues).
    for field, limits in SETTING_LIMITS.items():
        if field not in values:
            continue
        value = values[field]
        # The retained-value exemption (see the docstring). Compared by value
        # AND by type — `True == 1` in Python, so a bare `==` would let a
        # boolean through for a numeric field whose stored value happens to
        # be 1, which is the trap the two `isinstance` guards below exist for.
        if field in current and type(value) is type(current[field]) and value == current[field]:
            continue
        if limits.get("boolean"):
            if not isinstance(value, bool):
                field_errors.append(
                    {
                        "field": field,
                        "code": errors.VAL_RANGE,
                        "message_key": "errors.identity.option_not_allowed",
                        "params": {"allowed": [True, False]},
                    }
                )
            continue
        choices = limits.get("choices")
        if choices is not None:
            # ⚠ `True in (8, 10, 12)` is False but `1 in (1, …)` would be True
            # for a boolean — refuse a bool for a numeric choice by TYPE, as
            # the range branch below does.
            if isinstance(value, bool) or value not in choices:
                field_errors.append(
                    {
                        "field": field,
                        "code": errors.VAL_RANGE,
                        "message_key": "errors.identity.option_not_allowed",
                        # `None` ("never") is a choice but not something a
                        # refusal lists — the pre-DEF-IDN-7501 shape, kept.
                        "params": {"allowed": [c for c in choices if c is not None]},
                    }
                )
            continue
        # ⚠ `isinstance(True, int)` is True in Python, so a boolean sent for a
        # numeric setting would sail through `min <= value <= max` as 0 or 1
        # and be stored. It is refused by TYPE first, deliberately.
        if isinstance(value, bool) or not isinstance(value, int):
            field_errors.append(
                {
                    "field": field,
                    "code": errors.VAL_RANGE,
                    "message_key": "errors.identity.value_out_of_range",
                    "params": {"min": limits["min"], "max": limits["max"]},
                }
            )
            continue
        if not (limits["min"] <= value <= limits["max"]):
            field_errors.append(
                {
                    "field": field,
                    "code": errors.VAL_RANGE,
                    "message_key": "errors.identity.value_out_of_range",
                    "params": {"min": limits["min"], "max": limits["max"]},
                }
            )
    for cidr in values.get("ip_allowlist") or []:
        try:
            ipaddress.IPv4Network(str(cidr).strip())
        except ValueError:
            field_errors.append(
                {
                    "field": "ip_allowlist",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.invalid_cidr",
                    "params": {"value": str(cidr)},
                }
            )
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key="errors.identity.policy_invalid",
            field_errors=field_errors,
        )


# ── Tenancy provisioning seam (US-TEN-001 · S114 · apps/tenancy/seams.py) ───
# These four functions ARE the documented tenancy→identity seam contract.
# tenancy resolves them at call time (seams.resolve) — authoring them here is
# the wiring act; no registration step exists or is needed.
def provision_owner(
    *, tenant_id: Any, email: str, full_name: str, password: str, phone: str | None = None
) -> Any:
    """Create the OWNER of a freshly provisioned tenant INSIDE the caller's
    open provisioning transaction (seam contract in apps/tenancy/seams.py).

    - Per-tenant user (BR-IDN-029) with the password the owner chose on the
      signup form (EP-TEN-03/US-TEN-001 §5: "password policy per Security
      settings" — validated against the tenant's effective policy, which for
      a fresh tenant is the BR-IDN-025 seed defaults). No temp-password flow:
      the owner set their own password, so the membership is ACTIVE at once
      and must_change_password stays False.
    - System Admin membership (A4: owner role is System Admin).

    The owner's FIRST SESSION is no longer opened here: it is
    start_owner_session() below, called by tenancy immediately after this
    function inside the same transaction. Until 2026-08-10 this function
    created a session no one could ever present — provisioning ran on the apex
    host and the tenant lived on its own subdomain, so BR-TEN-045 sent the
    owner to a success screen to sign in again. Path tenancy removes the host
    boundary, so the session can finally be RETURNED; splitting it out is what
    lets its id reach the cookie without widening this seam's return value.

    Returns the owner user id (the seam's documented return value)."""
    try:
        validate_new_password(selectors.security_policy_values(tenant_id), password)
    except errors.ValidationError as exc:
        # The S114 form field is owner.password (US-TEN-001 §5) — remap so the
        # refusal renders inline on the signup form (IS-7).
        raise errors.ValidationError(
            exc.code,
            message_key="errors.identity.password_policy",
            field_errors=[{**fe, "field": "owner.password"} for fe in exc.field_errors],
        ) from exc
    role = selectors.role_by_code(SYSTEM_ADMIN)
    if role is None:  # platform catalog missing = broken deployment, loud
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="errors.identity.role_catalog_missing"
        )
    now = _now()
    user = User.objects.create(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        # A fresh utility holds no other login, so no number can be in use; a
        # value that is not a number is kept as typed and signs in nobody
        # (`phone_e164` stays NULL) rather than failing the whole sign-up.
        phone=phone,
        password_hash=make_password(password),
        must_change_password=False,  # owner chose this password on the signup form
        password_changed_at=now,
    )
    membership = TenantMembership.objects.create(
        tenant_id=tenant_id,
        user=user,
        role=role,
        status=TenantMembership.STATUS_ACTIVE,  # active immediately — no invite loop
    )
    membership.last_active_at = now  # signed in as part of provisioning
    membership.save(update_fields=["last_active_at", "updated_at"])
    core_audit.write_row(
        action="user.owner_provisioned",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,  # the signup owner is the acting party (self)
        after={"email": _mask_email(email), "role": role.code, "status": membership.status},
    )
    return user.id


def start_owner_session(
    *, tenant_id: Any, user_id: Any, ip: str | None = None, user_agent: str | None = None
) -> str:
    """Seam: open the new owner's first session at the end of provisioning.

    PO ruling 2026-08-10 supersedes BR-TEN-045. Under path tenancy the signup
    form and the new tenant share ONE origin, so the session created here rides
    home on the `POST /api/tenants` response as the ordinary httpOnly cookie
    and the owner lands signed in on S62 — the friction the PO wanted removed,
    with no one-time provisioning token invented to do it.

    Same row shape sign_in() writes, and bound to the tenant like every other
    session (BR-IDN-006): the utility's own absolute window, non-persistent
    (BR-IDN-026's keep-me-signed-in is an explicit sign-in choice and there is
    no such checkbox on the signup form).

    ⚠ **THE WINDOW IS READ RATHER THAN ASSUMED (`CR-145-BRC08`)**, and for a
    tenant being provisioned right now the read returns the column default —
    12 hours, the number this docstring used to state. It is read anyway,
    because a seeded policy row arriving one day inside the provisioning
    transaction would otherwise be ignored here and obeyed everywhere else,
    and a setting honoured on five paths out of six is the harder bug.

    No audit row of its own: `user.owner_provisioned` (written a few lines up,
    in the same transaction) already records that this owner came into
    existence signed in. A second row would double-count one event.

    Returns the session id — the cookie value. It is the CREDENTIAL, so the
    caller puts it in a Set-Cookie header and never in a response body.
    """
    now = _now()
    policy_values = selectors.security_policy_values(tenant_id)
    session = Session.objects.create(
        user_id=user_id,
        tenant_id=tenant_id,
        persistent=False,
        last_seen_at=now,
        expires_at=now + timedelta(hours=policy_values["absolute_session_hours"]),
        ip=ip,
        user_agent=user_agent or "",
    )
    return str(session.id)


def owner_email_for(tenant_id: Any) -> str | None:
    """Seam (BR-TEN-010 replay check): the provisioning owner's email — the
    FIRST System Admin membership created for the tenant (provisioning creates
    the owner before any other member can exist, US-TEN-001)."""
    membership = (
        TenantMembership.objects.filter(tenant_id=tenant_id, role__code=SYSTEM_ADMIN)
        .select_related("user")
        .order_by("created_at", "id")
        .first()
    )
    return membership.user.email if membership else None


def user_exists(user_id: Any) -> bool:
    """Seam: does this id name a real `users` row?

    Added 2026-08-16 (US-TEN-019 / DEF-153). Several tables carry a DEFERRED
    foreign key to `users`, which is checked at COMMIT rather than at INSERT —
    so a caller holding an id that names nobody does not fail where the row is
    written, it fails at commit and takes the whole transaction with it. This
    lets a caller ask BEFORE it writes, through identity's own service layer
    (B1), instead of every module learning the `users` table.

    Deliberately NOT tenant-scoped: the question is whether the row exists at
    all, which is what the foreign key checks. Ownership is a different
    question with a different answer, and conflating them here would make a
    cross-tenant id look absent rather than look wrong.
    """
    if user_id in (None, ""):
        return False
    try:
        return User.objects.filter(pk=user_id).exists()
    except (ValueError, TypeError, ValidationError):
        # A malformed id names nobody. Answering False is the same fact the FK
        # would report, without raising out of a read.
        return False


def owner_user_id_for(tenant_id: Any) -> Any | None:
    """Seam: the provisioning OWNER's user id — the same row `owner_email_for`
    names, answered as an id rather than as an email.

    Added 2026-08-16 for the sample-data repair path (US-TEN-019 / DEF-153).
    A command-line load has no session, and every service it drives writes an
    `audit_log` row that must say WHO asked (CLAUDE.md rule 7). The tenant's own
    owner is that person; without this seam the caller had no id at all and the
    audit rows would have been unattributed — or worse, attributed to a user id
    somebody invented.

    Same row, same ordering as `owner_email_for`, deliberately: two seams that
    disagreed about which user is "the owner" would attribute one tenant's
    actions to two different people.
    """
    membership = (
        TenantMembership.objects.filter(tenant_id=tenant_id, role__code=SYSTEM_ADMIN)
        .select_related("user")
        .order_by("created_at", "id")
        .first()
    )
    return membership.user.id if membership else None


def member_count() -> int:
    """Seam (S62 "Invite your team" checklist item): membership rows of the
    current-context tenant — all statuses, the literal reading of the seam
    contract ("members of the current-context tenant")."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE)
    return TenantMembership.objects.filter(tenant_id=tenant_id).count()


def seed_security_policy(actor: Any = None) -> dict[str, Any]:
    """WRITE the tenant's `security_policies` row at provisioning.

    ── THE DELEGATION THIS ANSWERS (CR-011 item 8, PO 2026-08-18) ────────────
    The PO was asked whether provisioning should write this row and answered
    *"you decide"* — an explicit delegation, banked as such in the decision log
    the same day. This function is the decision, and the reasoning is here
    rather than in a chat reply because that is where the next agent will look.

    **The state it changes.** `selectors.security_policy_values` has always
    served an UNSAVED `SecurityPolicy(tenant_id=…)` when no row exists, so the
    effective policy of a tenant that never opened the Security tab is a set of
    PYTHON CLASS DEFAULTS. Reads never write, by design, and the row appears
    only on the first save.

    **Why writing it is the better half of the choice, in one sentence a person
    can check:** if BR-IDN-025's ratified minimum ever moves from 8 to 10, every
    tenant on the host that never opened that screen has its password rule
    changed by a deploy — with no author, no before/after and no `audit_log`
    row, because nothing was saved. A written row pins each tenant to the
    figures it was provisioned under, and every later move goes through
    `save_security_policy`, which audits. The absence was also unanswerable from
    the database: 0 rows meant "never looked", indistinguishable from nothing.

    **Nothing changes for anybody on day one, and that is the point.** The
    values are the model's OWN column defaults — minimum length 8, upper+lower+
    number required, symbol optional, expiry never, idle timeout 60 minutes, no
    IP restriction (BR-IDN-025/026) — deliberately not restated here so they
    cannot drift from what the read-side fallback would have returned. A tenant
    provisioned before and a tenant provisioned after get the identical policy;
    only its storage moves.

    **The precedent is exact, which is most of the argument.** CR-010 item 7
    made the same call for `notification_settings` on 2026-08-17 —
    *"WRITE the dispatch-settings row at provisioning instead of on first
    read"* — for the same two reasons, and it kept the first-read fallback as
    the repair path. So does this: `security_policy_values` is untouched, and it
    remains the answer for every tenant provisioned before today.

    ⚠ **NEW TENANTS ONLY** — hard-won law 4 in its data form. The repair for a
    tenant that already exists is `manage.py seed_demo --tenant <subdomain>`,
    which reaches this through `seed_reference_data_for_tenant`.

    Idempotent by `get_or_create` (BR-TEN-063): a replay writes nothing and an
    admin's edited policy is never overwritten. `actor` is accepted for the
    seam's signature and unused — this writes a ratified default, not a
    decision anybody made, so there is no before/after to audit and
    `save_security_policy` stays the only audited door.
    """
    del actor
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    row, created = SecurityPolicy.objects.get_or_create(tenant_id=tenant_id)
    return {
        "created": created,
        "pw_min_length": int(row.pw_min_length),
        "session_timeout_minutes": int(row.session_timeout_minutes),
    }


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — identity's block (CR-010 new mandate 1, PO
# 2026-08-17: "along with member login i will create 2 new sample users")
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders: the seam contract names this path, G20 harvests it, and the
# implementation lives in `sample_data.py` because it drives the same
# `add_user` the S8 "Add user" action uses.


def seed_sample_records(actor: Any) -> int:
    """Two sample staff users — a Billing Clerk and an Executive — invited,
    uncredentialed (their temp passwords are discarded unread). See
    sample_data for the whole posture."""
    from apps.identity import sample_data

    return sample_data.seed_sample_records(actor)


def remove_sample_records() -> dict[str, Any]:
    """Deactivate-and-name — BR-IDN-030 forbids deleting a user. See
    sample_data."""
    from apps.identity import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    from apps.identity import sample_data

    return sample_data.sample_record_count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-001@402b6db (EP-IDN-01 lead; also US-IDN-002/003@402b6db · US-IDN-005/006/007@9d61512 · US-IDN-008@c4e29d2 · US-IDN-010@493ea2f — hash = sha256/7 of each source epic)
# packet: US-TEN-001@d5f8c32 (identity half of the EP-TEN-03 provisioning seam — amended 2026-08-09 by the W0 wiring lane: provision_owner/owner_email_for/member_count authored to the apps/tenancy/seams.py contract; add/remove reworked to BR-IDN-030, PO ruling 2026-08-09)
# generated: 2026-08-09 by story-coder v1 (identity W0 feature-story lane; amended same day by the W0 signup-loop wiring lane, backend only) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — screens come later) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: py_compile✔ · pytest tests -m "not golden and not isolation" 339 passed / 6 skipped / 20 deselected (wiring touch: 335-green baseline + 3 new BR-IDN-030/seam TCs + the unskipped seam-integration TC; RLS halves honestly G5-skipped) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · ruff E4/E7/E9/F✔ + black✔ on the wiring additions (pre-existing identity-lane spots untouched — that lane's recorded bar was py_compile) · mypy NOT INSTALLED in this environment — flagged: B8 strict scope includes services; deferred with the CI lane · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: last-5 history block — NO anchored storage, check absent, reported · forced change current_password optional (anchored screen has New/Confirm only) · trusted-device refresh re-establishes the same row (no token storage anchored) · self-lockout 409-vs-11b-"422 BIZ-STATE" — catalog wins, E2 reported · US-IDN-008 TC-2 self-email-change vs BR-IDN-017/11b admin-only — 11b ratified row implemented, E2 reported · BR-IDN-030 vs BR-IDN-012/US-IDN-007-§2 (delete-membership + audit-lock) — newer PO ruling implemented, register tension REPORTED not resolved · owner session ISSUED at provisioning but the POST /tenants response/cookie half lives in tenancy's result shape (outside the seam return contract and this lane's territory) — REPORTED · "user.owner_provisioned" audit action + member_count counting ALL statuses = Eng naming/literal-reading dispositions, flagged · [path-tenancy lane 2026-08-10] provision_owner no longer opens the owner session; start_owner_session does, so its id can reach the POST /api/tenants cookie. No new audit row — user.owner_provisioned already records the event
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
