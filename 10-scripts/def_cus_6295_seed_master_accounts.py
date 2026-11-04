"""Seed the two master accounts `BR-CUS-1093` and `DEF-CUS-6295` are ABOUT, so a
browser can be pointed at them.

⚠ **IT WRITES, AND IT IS THE ONLY SCRIPT IN THIS PAIR THAT DOES.** The readback
beside it (`br_cus_1093_master_services_readback.py`) rolls everything back; this
one has to leave rows behind, because the thing being proved is what a clerk SEES
on the Accounts register and a rolled-back row is not on any screen. **Run it
against a private clone** — `10-scripts/proof-db.sh clone <label>` — and never
against a database another lane is seeding.

WHAT IT MAKES, AND WHY TWO
--------------------------
The register's Services cell has to tell two ABSENCES apart, and one address
cannot show both:

  * `77 Owner Way`  — `services_available = ["water"]`, **nothing shared**. The
    owner's account holds NO service agreement, so before `BR-CUS-1093` this row
    read *No services*. It must now draw the WATER chip.
  * `79 Owner Way`  — `services_available = None`, nobody ever asked. The owner's
    account must read **No services at this address** — the `DEF-CUS-6295`
    sentence, a FACT at B14 rule 33's six-word cap, naming the ADDRESS so a clerk
    can tell a correct empty cell from a broken screen.

    USAGE
    -----
        10-scripts/proof-db.sh clone maservices
        cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
          DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/sbh_clone_maservices \
          JOBS_EAGER=false python3 manage.py shell \
            < ../10-scripts/def_cus_6295_seed_master_accounts.py

It is idempotent: an address it already made is reused rather than refused, so a
re-run after a code change costs nothing and changes nothing.
"""

from types import SimpleNamespace

from apps.customers import models as cus
from apps.customers import selectors as csel
from apps.customers import services as csvc
from apps.identity import models as ident
from apps.metering import models as met
from apps.metering import services as msvc
from apps.tenancy import models as ten
from core import tenancy

TENANT = "brazosbend"

#: (address, `services_available`, what the register's Services cell must draw)
CASES = (
    ("77 Owner Way", ["water"], "the WATER chip"),
    ("79 Owner Way", None, "No services at this address"),
)

tenant = ten.Tenant.objects.get(subdomain=TENANT)
with tenancy.tenant_context(str(tenant.id)):
    user = ident.User.objects.filter(tenant=tenant).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)

    for index, (address, services, expected) in enumerate(CASES):
        row = met.Premises.objects.filter(
            tenant=tenant, address_line=address, deleted_at__isnull=True
        ).first()
        if row is None:
            made = msvc.create_premises(
                actor,
                {
                    "address_line": address,
                    "owner_manager": f"Owner Way Holdings {index + 1}",
                    "owner_kind": "company",
                    # A distinct identifier per owner: `BR-CUS-1024` refuses a
                    # master account whose party cannot be identified, and two
                    # owners sharing one tax id would be one party.
                    "owner_tax_id": f"74-900000{index + 1}",
                    "owner_account_type": "commercial",
                    "services_available": services,
                },
            )
            premises_id = made["id"]
        else:
            premises_id = str(row.id)

        master = cus.Account.objects.filter(
            tenant=tenant, premises_id=premises_id, kind=csvc.ACCOUNT_KIND_MASTER
        ).first()
        if master is None:
            # The premises door opens the owner's account itself on most paths
            # (`metering.premises_owners` resolves `create_master_account`
            # through the customers seam), so this only runs where it did not.
            from tests import identity_fixtures  # noqa: PLC0415 — proof script

            made = csvc.create_master_account(
                actor,
                {
                    "premises_id": premises_id,
                    "account_type": "commercial",
                    "customer": identity_fixtures.customer_block(
                        f"Owner Way Holdings {index + 1}", kind="company"
                    ),
                },
            )
            master = cus.Account.objects.get(pk=made["id"])

        stored = met.Premises.objects.get(pk=premises_id).services_available
        print(f"{address}")
        print(f"  premises.services_available = {stored!r}")
        print(f"  master {master.account_no}  unit_id={master.unit_id}")
        print(f"  agreements {len(csel.service_agreements_for(master))}")
        print(f"  services cell = {csel.service_codes_for(master)!r}")
        print(f"  the register must draw: {expected}")
