"""Remove every parked move-out this lane planted, and print the counts.

The other half of `po20260919_move_outs_unfinished_seed.py`; see its header
for why `PYTHONPATH=.` is required.

⛔ **IT DELETES EVERY `move_out` DRAFT IN THE TENANT, NOT ONLY THE SEEDED
ONE.** That is safe on the demo tenant, which seeds none, and the BEFORE count
is printed so a run over a tenant holding real drafts is visible BEFORE the
fact rather than after it."""
import django  # noqa: E402

django.setup()

from apps.tenancy.models import Tenant, WizardPark  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

tenant = Tenant.objects.get(subdomain="brazosbend")
with tenant_context(tenant.id):
    rows = WizardPark.objects.filter(flow="move_out")
    print("BEFORE parked move_out rows:", rows.count())
    rows.delete()
    print("AFTER parked move_out rows:", WizardPark.objects.filter(flow="move_out").count())
