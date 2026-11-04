# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — phone number as a field-app sign-in name
#           (`identity/0013`)
# Rules:    BR-IDN-001/029 (unique inside one utility) · BR-AUD-006 (PII
#           masked) · CLAUDE.md hard rule 1 (each tenant read in its own context)
# Tests:    06-backend/tests/test_cr187_phone_sign_in.py
# ───────────────────────────────────────────────────────
"""`manage.py phone_sign_in_duplicates [--tenant <subdomain>]`

Lists, per utility, the logins that SHARE one phone number and so were left
without a phone sign-in by `identity/0013` (their `phone_e164` is NULL). Those
people still sign in by email. The office fixes it by giving each person a
number of their own on Settings › Users; the save then fills `phone_e164`.

Each line names the person and their email and shows the number MASKED to its
last two digits (BR-AUD-006). Read only: it changes nothing. Exit 0 always —
a duplicate is a fact for the office, not a failure of this command.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand

from apps.identity.phones import mask_phone, normalise_phone
from core import tenancy as core_tenancy


def duplicates_for_tenant(tenant_id: Any) -> list[dict[str, Any]]:
    """Every valid number at one utility that signs nobody in, with the logins
    holding it — read in the caller's tenant context. These are the numbers the
    backfill could not give out because two or more people shared them. A
    group of ONE means the others have since moved: re-saving that person's
    number on Settings › Users switches their phone sign-in on."""
    from apps.identity.models import User

    holders: dict[str, list[Any]] = defaultdict(list)
    rows = (
        User.objects.filter(tenant_id=tenant_id, phone_e164__isnull=True, phone__isnull=False)
        .order_by("email")
        .values("full_name", "email", "phone")
    )
    for row in rows:
        number = normalise_phone(row["phone"])
        if number is not None:
            holders[number].append(row)
    return [
        {
            "phone": mask_phone(number),
            "people": [{"name": r["full_name"] or "—", "email": r["email"]} for r in people],
        }
        for number, people in sorted(holders.items())
    ]


class Command(BaseCommand):
    help = "List logins that share a phone number at one utility (no phone sign-in for them)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", help="one utility, by its subdomain")

    def handle(self, *args, **options):
        from apps.tenancy.models import Tenant

        tenants = Tenant.objects.order_by("subdomain")
        if options.get("tenant"):
            tenants = tenants.filter(subdomain=options["tenant"])
        found = 0
        for tenant in tenants:
            with core_tenancy.tenant_context(str(tenant.id)):
                groups = duplicates_for_tenant(tenant.id)
            for group in groups:
                found += 1
                names = "; ".join(f"{p['name']} <{p['email']}>" for p in group["people"])
                self.stdout.write(f"{tenant.subdomain}\t{group['phone']}\t{names}")
        self.stdout.write(f"{found} shared number(s).")
