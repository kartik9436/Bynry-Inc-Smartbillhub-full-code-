# ── Trace ──────────────────────────────────────────────
# Change:   CR-078 (PO ruling 2026-09-07, finance re-signed the same day)
# Rules:    BR-RAT-1011 (a plan names the charge code its late fee is taken
#           from; naming none charges ZERO)
# Tests:    06-backend/tests/test_cr078_late_fee_from_the_plans_charge_code.py
# ───────────────────────────────────────────────────────
"""`manage.py cr078_late_fee_codes` — which plans charge a late fee, and which
charge nothing.

**WHY THIS COMMAND EXISTS AND IS NOT A NICETY.** `CR-078` makes a NULL
`rate_plans.late_fee_charge_id` mean *charge zero*. That is the PO's ruling and
it is correct — and it is also, left unwatched, indistinguishable from a
utility whose late fees quietly stopped working. Nothing raises, nothing logs,
and a customer simply is not charged. CLAUDE.md records the general form twice:
*an absence is invisible to every check this repo has*, and *a declared blind
spot with no NUMBER attached is indistinguishable from an empty one*.

So the state is COUNTABLE, on demand, per tenant, with the numbers printed:
how many plans charge a late fee, how many charge nothing, and WHICH.

It reads and writes nothing. It is the query that answered step 3 of the CR's
prescribed order — *prove none is unpopulated* — and it is the same query a
utility runs six months from now when someone asks why a customer was not
charged.

⚠ **IT CROSSES TENANTS ON PURPOSE, AND SETS `app.tenant_id` FOR EACH.**
CLAUDE.md hard rule 1 forbids touching a tenant table without the scope set; it
does not forbid a console tool from looping over tenants and setting it once
per tenant, which is what `seed_demo` and the provisioning commands already do.
There is no cross-tenant queryset here — there are N scoped ones.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.rating import selectors
from apps.tenancy.models import Tenant
from core import tenancy as core_tenancy


class Command(BaseCommand):
    help = "Report which rate plans name a late-fee charge code (CR-078 / BR-RAT-1011)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            default=None,
            help="Limit to one tenant subdomain. Default: every tenant.",
        )
        parser.add_argument(
            "--fail-on-missing",
            action="store_true",
            help=(
                "Exit non-zero when any plan names no live late-fee charge code. "
                "This is what gate G121 runs."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.rating import models as rating_models

        tenants = Tenant.objects.all().order_by("subdomain")
        if options["tenant"]:
            tenants = tenants.filter(subdomain=options["tenant"])

        total_plans = 0
        total_missing = 0
        for tenant in tenants:
            with core_tenancy.tenant_context(tenant.pk):
                plans = rating_models.RatePlan.objects.filter(tenant_id=tenant.pk).count()
                missing = selectors.plans_missing_late_fee_charge()
            total_plans += plans
            total_missing += len(missing)
            self.stdout.write(
                f"{tenant.subdomain}: {plans - len(missing)}/{plans} plan(s) name a live "
                f"late-fee charge code; {len(missing)} charge $0.00."
            )
            for row in missing:
                self.stdout.write(f"    - {row['code']} ({row['status']}) — {row['reason']}")

        self.stdout.write(
            f"TOTAL: {total_plans - total_missing}/{total_plans} plan(s) across "
            f"{tenants.count()} tenant(s) name a live late-fee charge code; "
            f"{total_missing} charge $0.00 (BR-RAT-1011)."
        )
        if options["fail_on_missing"] and total_missing:
            raise SystemExit(1)
