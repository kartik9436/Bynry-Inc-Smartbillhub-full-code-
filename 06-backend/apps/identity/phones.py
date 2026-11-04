# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the field app signs in by work EMAIL or PHONE NUMBER
#           (PO ruling 2026-10-21, relayed by the coordinator: there is NO
#           Technician ID; a technician signs in with email or phone)
# Rules:    BR-IDN-001 (tenant-first: a sign-in name is unique inside ONE
#           utility, never across) · BR-IDN-029 (per-tenant uniqueness) ·
#           BR-AUD-006 (PII masked in the trail)
# Tests:    06-backend/tests/test_cr187_phone_sign_in.py ·
#           06-backend/tests/test_cr187_phone_sign_in_pg.py
# Impacts:  apps/identity/models.py (`User.phone_e164`) · services.py (every
#           write of `User.phone`) · native.py (sign-in, activation)
# ───────────────────────────────────────────────────────
"""A phone number as a sign-in name: one normal form, compared and nothing else.

THE RULE, IN ONE PLACE
----------------------
A typed value is a PHONE when, after stripping spaces, dashes, dots and
brackets, what is left is digits with an optional leading `+`. It is then
written in E.164 with the North American default:

  * 10 digits                       → `+1` + the digits   (`512 555 0104`)
  * 11 digits starting with `1`     → `+` + the digits    (`1-512-555-0104`)
  * a leading `+` and 8–15 digits   → kept as typed       (`+15125550104`)
  * anything else                   → NOT a phone (None)

So `(512) 555-0104`, `512-555-0104`, `512.555.0104` and `+15125550104` are one
number, `+15125550104`, and only that form is ever compared or stored in
`users.phone_e164`. The raw `users.phone` the person typed is kept as typed for
display; it is never compared.

⚠ **A VALUE CONTAINING `@` IS AN EMAIL, NEVER A PHONE** — `identifier_kind`
decides that first, so a strange email cannot be read as a number.

⚠ **A MALFORMED NUMBER IS NOT A SEPARATE REFUSAL AT SIGN-IN.** It simply finds
nobody, and sign-in gives the one generic failure (BR-IDN-002). Only a SAVE of
a malformed number is refused by name (`errors.identity.phone_invalid`),
because there the person typing it is the office, who can fix it.
"""

from __future__ import annotations

from typing import Any

KIND_EMAIL = "email"
KIND_PHONE = "phone"
KIND_OTHER = "other"

#: E.164 allows at most 15 digits after the `+`; under 8 is no real number.
_MIN_DIGITS = 8
_MAX_DIGITS = 15
_STRIP = str.maketrans("", "", " -.()\t")


def normalise_phone(raw: Any) -> str | None:
    """`(512) 555-0104` → `+15125550104`; None when it is not a phone number."""
    text = str(raw or "").strip()
    if not text or "@" in text:
        return None
    compact = text.translate(_STRIP)
    plus = compact.startswith("+")
    digits = compact[1:] if plus else compact
    if not digits or not digits.isascii() or not digits.isdigit():
        return None
    if plus:
        return f"+{digits}" if _MIN_DIGITS <= len(digits) <= _MAX_DIGITS else None
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def identifier_kind(identifier: Any) -> str:
    """`email` when it contains `@`; `phone` when it normalises; else `other`."""
    text = str(identifier or "").strip()
    if "@" in text:
        return KIND_EMAIL
    return KIND_PHONE if normalise_phone(text) else KIND_OTHER


def mask_phone(raw: Any) -> str:
    """BR-AUD-006: a phone enters the trail as its last two digits only."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return f"***{digits[-2:]}" if len(digits) >= 2 else "***"


__all__ = [
    "KIND_EMAIL",
    "KIND_OTHER",
    "KIND_PHONE",
    "identifier_kind",
    "mask_phone",
    "normalise_phone",
]
