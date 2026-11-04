# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-018 (EP-CWP-03) — *Choose a password*. Screens: CWP-018
# Rules:    BR-CWP-037 (password policy is read from the TENANT'S EXISTING
#           settings — length, mix and expiry are already tenant settings; the
#           portal adds no second policy) · BR-CWP-004 (a portal credential
#           must never resolve into a staff role) · BR-CWP-012 (read through a
#           seam, no second copy)
# Tests:    06-backend/tests/test_us_cwp_018_password.py TC-3 (eight characters
#           refused on a tenant whose pw_min_length is twelve)
# Impacts:  apps/portal/credentials.py (its only caller)
# ───────────────────────────────────────────────────────
"""The ONE thing the portal reads from `identity`, and the one place it may.

⚠ **THIS FILE IS THE WHOLE OF THE PORTAL'S CONTACT WITH `apps.identity`, AND
THAT IS ENFORCED RATHER THAN INTENDED.** `BR-CWP-004` forbids a customer
credential resolving into a staff role, so `credentials.py`, `session.py` and
`api.py` may not import `apps.identity` at all — G91 fails the build if one
does. The password POLICY is a different thing from the staff USER: it is the
utility's own rule about how long a password must be, it already has a screen
and an owner, and `BR-CWP-037` says in as many words that the portal adds no
second one.

⚠ **AND IT READS EXACTLY ONE MODEL.** `SecurityPolicy` and nothing else — not
`User`, not `Session`, not `TenantMembership`. G91 reads this file with `ast`
and fails on a second identity model appearing here, because the seam is the
door and a door that widens is not a door.

**A tenant with no policy row gets Django's own defaults**, which are the same
defaults `identity.models.SecurityPolicy` declares — eight characters, mixed
case and digits, no symbol required. Failing closed here would mean a utility
that never opened the security screen could not enrol a single customer.
"""

from __future__ import annotations

from typing import Any

from apps.identity.models import SecurityPolicy

#: `identity/models.py` §SecurityPolicy — repeated here as the ANSWER for a
#: tenant with no row, not as a second policy. BR-IDN-025 owns the values.
DEFAULT_POLICY: dict[str, Any] = {
    "pw_min_length": 8,
    "pw_require_mixed": True,
    "pw_require_symbol": False,
}


def password_policy(tenant_id: Any) -> dict[str, Any]:
    """The tenant's own password rule, as three plain facts.

    Returns `pw_min_length`, `pw_require_mixed` and `pw_require_symbol` — the
    three that describe a password a person is about to type. `pw_expiry_days`,
    `session_timeout_minutes`, `absolute_session_hours` and `ip_allowlist` are
    NOT returned: expiry and the allowlist are staff controls (`BR-IDN-020` is
    an office network rule and a customer has no office), and the two session
    limits are read by `session.py` through their own calls below.
    """
    row = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    if row is None:
        return dict(DEFAULT_POLICY)
    return {
        "pw_min_length": int(row.pw_min_length),
        "pw_require_mixed": bool(row.pw_require_mixed),
        "pw_require_symbol": bool(row.pw_require_symbol),
    }


def absolute_session_hours(tenant_id: Any) -> int:
    """How long a portal session may live at all, idle or busy — the UTILITY'S
    OWN hard limit, the same number its staff get.

    ⚠ **THE PORTAL GETS NO SETTING OF ITS OWN, AND THAT IS A RULING RATHER
    THAN A SHORTCUT (`CR-145-BRC08`, PO 2026-09-28).** Asked whether the
    customer portal should keep following the staff setting or gain its own,
    the PO answered *"Yes"* to keeping it: *"one setting is less for an admin
    to get wrong."* `session.py` carried `ABSOLUTE_LIFETIME_HOURS = 12` as a
    fixed number until that day.

    It is the same argument `session_timeout_minutes` below already makes, one
    line further on: a utility that shortens how long an unattended browser is
    safe has said something about its premises, and there is no reading of
    that sentence which excludes the customer looking at the same building's
    bills. Making the two consistent is the whole of this function.

    **A tenant with no policy row gets 12**, which is the column default and
    the number every portal session has had since the portal shipped.
    """
    row = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    return int(getattr(row, "absolute_session_hours", 12) or 12)


def session_timeout_minutes(tenant_id: Any) -> int:
    """How long a portal session may sit idle — *"mirroring the staff policy"*
    (field map §1 `portal_session`).

    One number, one screen, one owner: a utility that shortens its idle timeout
    for staff has said something about how long an unattended browser is safe
    on its premises, and there is no reading of that sentence which excludes
    the customer looking at the same building's bills.
    """
    row = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    return int(getattr(row, "session_timeout_minutes", 60) or 60)


def password_link_valid_days(tenant_id: Any) -> int:
    """How many days an emailed password link stays valid — the UTILITY'S OWN
    `password_link_valid_days`, the same number its staff links get.

    PO 2026-10-22, *"don't do any hardcoding"* (decision log *"Account-access
    emails: languages via template variants"* (4)): a link's lifetime is a
    setting beside the other sign-in policy settings, not a constant. ONE
    setting for staff and customer links, `absolute_session_hours`'s reasoning
    above (`CR-145-BRC08`, *"one setting is less for an admin to get wrong"*).

    **A tenant with no policy row — or a build where the column has not landed
    yet (the staff-invite lane adds it) — gets 7**, the seeded default and the
    number every portal reset link has had since `US-CWP-020` shipped.
    """
    row = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    return int(getattr(row, "password_link_valid_days", 7) or 7)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-018@c05e4dd4 (EP-CWP-03 story + BR-CWP-037 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(credentials.py) E✔(CWP-018's helper line) F✔ G✔ H=n/a(reads only; the 🔒 half is credentials.py and session.py)
# gates: G91 (this is the only file under apps/portal that may import apps.identity, and it may read only SecurityPolicy) · pytest tests/test_us_cwp_018_password.py
# exceptions: a tenant with no policy row reads BR-IDN-025's own defaults rather than failing closed — stated above, not hidden
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
