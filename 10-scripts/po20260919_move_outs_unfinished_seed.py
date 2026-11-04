"""Plant ONE parked move-out on the demo tenant, and print the counts.

⚠ **THROUGH THE OWNING MODULE'S DOOR** — `customers.seams.park_wizard_draft`
forwards to `tenancy.wizard_parks.park`, which is the only lawful route from
customers into a tenancy-hosted table (B1 / BR-TEN-013). Nothing here writes a
row by hand, so what is proved in the browser is what a clerk's `Park` produces.

Paired with `purge_park.py`: the beta is left exactly as it was found.
"""
import django  # noqa: E402

django.setup()

from apps.customers import models as cmodels  # noqa: E402
from apps.customers import seams as customers_seams  # noqa: E402
from apps.identity.models import TenantMembership  # noqa: E402
from apps.tenancy.models import Tenant, WizardPark  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

tenant = Tenant.objects.get(subdomain="brazosbend")
with tenant_context(tenant.id):
    print("BEFORE parked move_out rows:", WizardPark.objects.filter(flow="move_out").count())
    account = (
        cmodels.Account.objects.filter(closed_at__isnull=True).order_by("account_no").first()
    )
    # ⚠ THE ACTOR IS THE USER PLUS THE ROLE `require_role` READS. `TenantMembership`
    # is where a role lives; the service reads `actor.role`, which a bare `User`
    # does not carry. The fixture suite's `marcus` has the identical shape.
    # ⚠ **`role` IS THE ROLE'S CODE, NOT THE `Role` ROW.** `require_role` compares
    # `actor.role` against the platform's role STRINGS, and a membership joins to a
    # `roles` catalogue row — so handing the object through is a silent refusal.
    membership = (
        TenantMembership.objects.select_related("user", "role")
        .filter(role__code="system_admin")
        .first()
    )
    user = membership.user
    actor = SimpleNamespace(id=user.id, pk=user.id, user=user, role=membership.role.code)
    print("actor:", user.email, "role:", actor.role)
    label = account.account_no
    contact = account.contact_set.filter(deleted_at__isnull=True).first()
    if contact is not None and contact.full_name:
        label = contact.full_name
    row = customers_seams.park_wizard_draft(
        actor,
        {
            "flow": "move_out",
            "step": 2,
            "subject_label": label,
            "subject_ref": {"account_id": str(account.id)},
            "values": {"account_id": str(account.id), "moved_out_on": "2026-09-30"},
            "waiting_on": "the customer",
        },
    )
    print("PLANTED park id:", row.id, "on account", account.account_no, "label", label)
    print("AFTER parked move_out rows:", WizardPark.objects.filter(flow="move_out").count())
