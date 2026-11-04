# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data) · US-IDN-005 (add a
#           user — the service this drives)   Screens: S8 (Users & roles ·
#           Sample data panel)
# Rules:    CR-010 new mandate 1 (PO 2026-08-17: *"along with member login i
#           will create 2 new sample users"*) · BR-IDN-008 (exactly 3 platform
#           roles) · BR-IDN-011 (invited status) · BR-IDN-021/022 (temp
#           password shown once, never stored readable — here it is shown to
#           NOBODY) · BR-IDN-029 (same email in another tenant is a different
#           user) · BR-TEN-063 (idempotent, audited) · BR-TEN-066 (removal is
#           partial-and-named) · CLAUDE.md rule 7
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the seam)
# ───────────────────────────────────────────────────────
"""identity's block of the sample set: SIX sample staff users (CR-010, CR-070).

WHY THESE EXIST — the PO's mandate, verbatim (decision log 2026-08-17):
*"along with member login i will create 2 new sample users"* — so a trial
tenant's Users & roles screen shows a team rather than one lonely owner, and
the role-permission differences (A4) have live subjects: a **Billing Clerk**
and an **Executive**, one of each non-admin office role (BR-IDN-008).

⚠ **AND FOUR FIELD TECHNICIANS SINCE 2026-09-07 — see `SAMPLE_STAFF` for the
reason, which is `work.technicians.user` being NOT NULL rather than a wish for
a larger team.** The PO's mandate of 2026-08-17 said *"2 new sample users"* and
that mandate is untouched: those two are still the office pair it names. The
field four arrive under `CR-070`, whose crews screen has nobody on it without
them, and they are `surface_scope = mobile` so the phone-only rule
(`BR-WRK-043`) has live subjects instead of a comment claiming it.

THE OWNER STAYS THE ONLY CREDENTIALED LOGIN, BY CONSTRUCTION
--------------------------------------------------------------
Both users are created through `add_user` — the S8 "Add user" action's own
service — which mints an INVITED membership (BR-IDN-011) and a one-time temp
password (BR-IDN-021/022). That password is DISCARDED here, deliberately and
loudly: it is never logged, never stored, never printed. So the two rows are
genuinely invitation-pending — `must_change_password` set, temp credential
expiring in 7 days and known to nobody — and neither can sign in unless a
System Admin issues a fresh temp password from the Users screen, which is the
product's own re-invite path. `seed_demo`'s production refusal exists because
it PUBLISHES an owner password; this block publishes nothing, which is why it
may run at provisioning (BR-TEN-064's own distinction).

WHAT THE SCHEMA DOES NOT ALLOW, STATED RATHER THAN WORKED AROUND
------------------------------------------------------------------
`users` carries no `is_sample` column — BR-TEN-057 put the tag on the tables
of the 2026-08-10 sample set, and identity was never in it. Adding the column
is a B2 schema decision this block must not smuggle in, so SAMPLE-NESS IS THE
ADDRESS: both emails live on the fixed, unroutable `@sample.test` domain
(RFC 2606 reserves .test), which is what removal and counting key on. The
domain is shared across tenants ON PURPOSE — BR-IDN-029: *"the same email in
another tenant is a different user and never a conflict"* — so no per-tenant
subdomain needs to be resolved across a module boundary to build it.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.identity import models, selectors
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.identity")

#: The clearly-sample domain every sample staff address lives on (module
#: docstring: RFC 2606 `.test` — unroutable by standard, shared across
#: tenants lawfully per BR-IDN-029).
SAMPLE_STAFF_DOMAIN = "sample.test"

#: (full name, local part, platform role code, surface scope). One of each
#: non-admin OFFICE role — BR-IDN-008's catalog is closed at three, and the
#: owner already IS the System Admin — then the FIELD half.
#:
#: ⚠ **THE FOUR FIELD TECHNICIANS WERE ADDED 2026-09-07, AND THE REASON IS A
#: FOREIGN KEY RATHER THAN A WISH FOR A BIGGER TEAM.** `work.technicians.user`
#: is NOT NULL and unique per tenant (`BR-WRK-028`, *"a profile beside an
#: existing identity.User, not a second identity"*), so a crew with anybody in
#: it needs logins that exist BEFORE Work's block runs. Work may not create
#: them: it reads users through `apps/work/seams/identity_seam.py` and writes
#: no other module's table (`BR-WRK-002`, and `G78` fails the merge). So the
#: logins are seeded HERE, by the module that owns `users`, and Work's block
#: attaches a profile to each — which is the same two-step a real utility
#: performs on Settings → Team and then on Work → Crews.
#:
#: ⚠ **THEIR SURFACE SCOPE IS `mobile` AND THE OFFICE ROLES' IS `both`.**
#: `BR-WRK-043` keeps a technician's login off the web app, and
#: `identity_seam.enforce_surface` is the read that answers it. `add_user`
#: does not take the field — it is not part of the S8 Add-user form — so this
#: block sets it on identity's OWN table immediately afterwards. Seeding four
#: `both` logins would leave that rule with no live subject at all, which is
#: hard-won law 2's shape: built, and not wired.
#:
#: ⚠ **FOUR, NOT FOURTEEN.** The ICP is a utility of up to 40,000 accounts run
#: by 10–20 staff (CLAUDE.md), so four field technicians in two crews plus one
#: contractor is what that utility actually looks like on a Tuesday. A seeded
#: workforce of fifty would demonstrate a product nobody in scope is buying.
SAMPLE_STAFF: tuple[tuple[str, str, str, str], ...] = (
    ("Sam Reyes", "sam.reyes", "billing_clerk", "both"),
    ("Avery Cole", "avery.cole", "executive", "both"),
    ("D. Ortiz", "d.ortiz", "field_technician", "mobile"),
    ("R. Patel", "r.patel", "field_technician", "mobile"),
    ("M. Chen", "m.chen", "field_technician", "mobile"),
    ("J. Okoro", "j.okoro", "field_technician", "mobile"),
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def sample_staff_emails() -> tuple[str, ...]:
    return tuple(f"{local}@{SAMPLE_STAFF_DOMAIN}" for _, local, _, _ in SAMPLE_STAFF)


def _owner_as_actor() -> models.User:
    """The tenant's provisioning owner, shaped as `add_user`'s actor.

    `add_user` is @require_role(SYSTEM_ADMIN) and records `invited_by` as a
    REAL `users` FK, so the actor must be an actual User row — the orchestrator
    hands us an attribution shim, and a shim in that FK would corrupt it. The
    owner is the right person twice over: they are the System Admin the tenant
    is guaranteed to have (BR-TEN-001/BR-IDN-013), and the sample load is
    performed on their behalf. `.role` is attached exactly the way
    `apps/identity/auth.py` attaches it after authentication.
    """
    tenant_id = _tenant_id()
    membership = (
        models.TenantMembership.objects.filter(
            tenant_id=tenant_id,
            role__code="system_admin",
            status=models.TenantMembership.STATUS_ACTIVE,
        )
        .select_related("user", "role")
        .order_by("created_at")
        .first()
    )
    if membership is None:
        raise fixture.BlockCannotRun(
            "no sample staff user was created: this tenant has no ACTIVE System "
            "Admin, and `add_user` records who invited whom (BR-IDN-011) — an "
            "invitation from nobody would corrupt the trail. Provisioning creates "
            "the owner (BR-TEN-001); if that failed, the fix is there, not here."
        )
    owner = membership.user
    owner.role = membership.role.code  # what auth.py attaches after sign-in
    return owner


def seed_sample_records(actor: Any) -> int:
    """THE SEAM: the six sample staff users, invited and uncredentialed.

    Idempotent (BR-TEN-063): an address already present is skipped, so a
    replay writes nothing. The orchestrator's `actor` is accepted for the
    seam's signature but the AUDITED actor is the owner row — see
    `_owner_as_actor` for why a shim cannot travel into `invited_by`.
    """
    del actor  # attribution must be a real users row — the owner's
    from apps.identity import services

    owner = _owner_as_actor()
    tenant_id = _tenant_id()
    written = 0
    for full_name, local, role_code, surface_scope in SAMPLE_STAFF:
        email = f"{local}@{SAMPLE_STAFF_DOMAIN}"
        if selectors.user_by_email(tenant_id, email) is not None:
            continue  # BR-TEN-063: a replay changes no count
        user, _, temp_password = services.add_user(
            actor=owner,
            tenant_id=tenant_id,
            full_name=full_name,
            email=email,
            role_code=role_code,
        )
        # BR-WRK-043 — a field technician signs in on the phone and not on the
        # web app. Since 2.548.2 (`DEF-IDN-9748`) `add_user` derives the scope
        # from the role itself, so for the four technicians this now writes
        # nothing; it stays as the seed's own statement of the scope it wants.
        if surface_scope != user.surface_scope:
            models.User.objects.filter(pk=user.pk).update(surface_scope=surface_scope)
        # ⚠ THE TEMP PASSWORD IS DISCARDED, ON PURPOSE — see the module
        # docstring. Deleting the name is the whole security posture: the
        # owner stays the only credentialed login (CR-010; BR-IDN-021/022).
        del temp_password
        written += 1
    return written


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-066 — and for USERS, "remove" can only ever mean DEACTIVATE.

    BR-IDN-030 (PO 2026-08-09) rules removal of a user is PERMANENT
    DEACTIVATION: the row, email and name stay (audit history intact) and the
    email is never freed. So this drives `remove_user` — the S8 row action's
    own service, which deactivates — and reports the rows as RETAINED BY NAME
    with `removed: 0`, because zero rows left the database and saying
    otherwise is the sentence a utility would act on and be wrong about.
    A sample user somebody already activated is left entirely alone.
    """
    from apps.identity import services

    tenant_id = _tenant_id()
    retained: list[dict[str, Any]] = []
    owner: models.User | None
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            owner = _owner_as_actor()
    except fixture.BlockCannotRun:
        owner = None
    for email in sample_staff_emails():
        user = selectors.user_by_email(tenant_id, email)
        if user is None:
            continue
        membership = selectors.membership_for_user(tenant_id, user.id)
        if membership is None or owner is None:
            retained.append(
                {
                    "label": f"sample user {email}",
                    "reason": "no membership row (or no System Admin to act) — left as found",
                }
            )
            continue
        if membership.status == models.TenantMembership.STATUS_DEACTIVATED:
            continue  # already done — a replay changes nothing (BR-TEN-063)
        if membership.status != models.TenantMembership.STATUS_INVITED:
            retained.append(
                {
                    "label": f"sample user {email}",
                    "reason": (
                        "no longer invitation-pending — a human activated this row, so "
                        "it is theirs to manage on Settings > Users, not this job's"
                    ),
                }
            )
            continue
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
            # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
            # (this block runs inside tenancy's per-module `atomic`), so without it the
            # work already done is lost at COMMIT. NOT tidiness — do not remove.
            with transaction.atomic():
                services.remove_user(actor=owner, user=user, membership=membership)
                retained.append(
                    {
                        "label": f"sample user {email}",
                        "reason": (
                            "DEACTIVATED, not deleted — BR-IDN-030: user removal is "
                            "permanent deactivation, the row and its audit history stay "
                            "and the email is never freed"
                        ),
                    }
                )
        except Exception as exc:  # noqa: BLE001 — BR-TEN-066: name it, keep going
            retained.append(
                {"label": f"sample user {email}", "reason": f"{type(exc).__name__}: {exc}"}
            )
    return {"removed": 0, "retained": retained}


def sample_record_count() -> int:
    """Sample staff rows still LIVE (invited or active) — a deactivated one is
    as removed as BR-IDN-030 allows a user to be, so it is not counted."""
    tenant_id = _tenant_id()
    held = 0
    for email in sample_staff_emails():
        user = selectors.user_by_email(tenant_id, email)
        if user is None:
            continue
        membership = selectors.membership_for_user(tenant_id, user.id)
        if membership is not None and membership.status != (
            models.TenantMembership.STATUS_DEACTIVATED
        ):
            held += 1
    return held


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 Part-10 (decision log 2026-08-17: new mandate 1 — "along with member login i will create 2 new sample users") + US-TEN-019@c3b7d18
# generated: 2026-08-18 by story-coder (CR-010 transactional-seeds lane)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel; the users render on the existing S8 Users list) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: `users` has NO is_sample column and none is added — BR-TEN-057's tag belongs to a B2 schema decision this block must not smuggle in, so sample-ness is keyed on the fixed @sample.test domain (argued in the module docstring) · the temp password is DISCARDED unread — the OWNER stays the only credentialed login, which is the PO's stated posture and the reason this may run at provisioning where seed_demo may not · a sample user somebody activated is RETAINED by name on removal (BR-TEN-066), never deleted from under their audit trail
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
