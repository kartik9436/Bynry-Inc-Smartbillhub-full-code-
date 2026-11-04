"""CR-171-BRC10 lane MVI-WIZ-CUST — give a lane database a person and a company
that *Search customer ID* can FIND, for the photographs beside images 34, 37, 40.

Run inside the backend with the lane's settings, AFTER `seed_demo` and
`load_sample_data --tenant brazosbend`:

    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python manage.py shell < ../10-scripts/cr171_wiz_cust_seed.py

The sample tenant holds no PERSON with a Social Security number on file, so no
search can answer *Existing customer* for a person. This commits two move-ins
through the real service (never a direct row write), each on a unit nobody has
ever occupied:

  * **Nilesh G** — a person, SSN 210-80-9662, born 06/18/2001;
  * **Kestrel Holdings LLC** — a company, Tax ID 47-1234567, contact Nilesh G.

Every name, number and date is an illustration (B14 rule 37). It prints the
unit each was put on and the unit LEFT vacant for the walkthrough to use.
"""

from types import SimpleNamespace

from apps.customers import models as cmodels
from apps.customers import services as customers_services
from apps.identity.models import User
from apps.metering.models import Unit
from apps.tenancy.models import Tenant
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
user = User.objects.get(email="dana@brazosbendutilities.com")
actor = SimpleNamespace(id=user.id, role="system_admin", user=user, tenant_id=tenant.id)

with core_tenancy.tenant_context(tenant.id):
    occupied = set(cmodels.Account.objects.filter(tenant_id=tenant.id).values_list("unit_id", flat=True))
    never = [
        unit
        for unit in Unit.objects.filter(tenant_id=tenant.id, rate_plan_id__isnull=False).order_by("unit_no")
        if unit.id not in occupied
    ]
    if len(never) < 3:
        raise SystemExit(f"need three never-occupied units, found {len(never)}")
    person_unit, company_unit = never[0], never[1]

    person = customers_services.move_in_to_unit(
        actor,
        person_unit.id,
        {
            "account_type": "residential",
            "opened_at": "2026-09-01",
            "contact": {"full_name": "Nilesh G", "email": "nilesh@example.invalid", "phone": "732-630-0285"},
            "customer": {
                "kind": "person",
                "display_name": "Nilesh G",
                "identity": {"ssn": "210-80-9662", "date_of_birth": "2001-06-18", "phone": "732-630-0285"},
            },
        },
    )
    company = customers_services.move_in_to_unit(
        actor,
        company_unit.id,
        {
            "account_type": "commercial",
            "opened_at": "2026-09-01",
            "contact": {
                "full_name": "Nilesh G",
                "job_title": "Owner",
                "email": "nilesh@example.invalid",
                "phone": "732-630-0285",
                "contact_by": "email",
            },
            "customer": {
                "kind": "company",
                "display_name": "Kestrel Holdings LLC",
                "identity": {"tax_id": "47-1234567"},
            },
            "company": {"trading_as": "Kestrel Bakery", "business_type": "llc", "registered_in": "IA"},
        },
    )
    print("person", person["account_no"], "on", person_unit.unit_no)
    print("company", company["account_no"], "on", company_unit.unit_no)
    print("vacant for the walk:", ", ".join(unit.unit_no for unit in never[2:5]))
