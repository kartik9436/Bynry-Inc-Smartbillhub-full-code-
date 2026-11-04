"""Give the seeded tenant a Billing Clerk who can actually SIGN IN.

    PYTHONPATH=06-backend DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=… python3 10-scripts/render-checks/def-shl-4283-fixture.py

⚠ **THIS FILE EXISTS BECAUSE THE ABSENCE IT FILLS IS PART OF THE DEFECT'S OWN
STORY.** `seed_demo` creates ONE user — the System Admin — and
`apps/identity/sample_data.py` leaves any other role INVITED AND UNCREDENTIALED
by design. So for sixteen days there was no way to click through this product as
a Billing Clerk without first writing a script like this one, and every
walkthrough in the repository signed in as an administrator. `DEF-SHL-4272` (a
clerk could not use the product AT ALL) and `DEF-SHL-4283` (two of their screens
were still broken after that fix) both survived a green suite for exactly that
reason.

It is idempotent: run it twice and the second run resets the same password.

It writes ONLY to `users` and `tenant_memberships`, in the demo database named
by `DATABASE_URL`. **Never point it at anything but a throwaway fixture
database** — it sets a known password on a real login.
"""

from __future__ import annotations

import os
import sys

import django

django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402

from apps.identity.models import Role, TenantMembership, User  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

EMAIL = os.environ.get("SMOKE_CLERK_EMAIL", "sam.reyes@sample.test")
PASSWORD = os.environ.get("SMOKE_CLERK_PASSWORD", "Cl3rk!passw0rd")
SUBDOMAIN = os.environ.get("SMOKE_TENANT", "brazosbend")


def main() -> int:
    tenant = Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if tenant is None:
        print(f"no tenant with subdomain {SUBDOMAIN!r} — run seed_demo first", file=sys.stderr)
        return 2
    clerk_role = Role.objects.filter(code="billing_clerk").first()
    if clerk_role is None:
        print("no billing_clerk role — the identity fixture has not run", file=sys.stderr)
        return 2

    # Hard rule 1: `users` and `tenant_memberships` are tenant tables under RLS
    # FORCE, so every read and write below happens inside the tenant context.
    with tenant_context(str(tenant.id)):
        user = User.objects.filter(email=EMAIL).first()
        if user is None:
            user = User.objects.create(
                tenant=tenant,
                email=EMAIL,
                full_name="Sam Reyes",
                password_hash=make_password(PASSWORD),
                must_change_password=False,
            )
            made = "created"
        else:
            user.password_hash = make_password(PASSWORD)
            # A forced change would land the walkthrough on the change-password
            # screen instead of the dashboard, and the run would fail for a
            # reason that has nothing to do with what it is checking.
            user.must_change_password = False
            user.save(update_fields=["password_hash", "must_change_password"])
            made = "re-credentialed"

        membership, created = TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": clerk_role, "status": "active"},
        )
        if not created:
            membership.role = clerk_role
            membership.status = "active"
            membership.save(update_fields=["role", "status"])

    print(f"{made} {EMAIL} as billing_clerk on {SUBDOMAIN} (password from SMOKE_CLERK_PASSWORD)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
