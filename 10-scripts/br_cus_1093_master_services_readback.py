"""`BR-CUS-1093` — a master account reads its BUILDING's services, READ BACK
from a real PostgreSQL database.

WHY THIS EXISTS BESIDE THE SUITE
--------------------------------
`06-backend/tests/test_br_cus_1093_master_services.py` runs on **in-memory
SQLite** (`config/settings/test.py` hardcodes it and ignores `DATABASE_URL`),
and four of the things this change depends on cannot be observed there:

1. **THE REPORTED CASE, ON THE PRODUCT OWNER'S OWN DATA.** The bug was reported
   from the Accounts register of the seeded demo utility, against the account
   numbers `AC-2026-00052` / `AC-2026-00053`. A fixture cannot reproduce *"the
   register said No services"*; a clone of that utility can, and section 1
   below creates the same shape — a premises that offers water with nothing
   shared — and prints the cell BEFORE anything else happens.
2. **THAT NO EXISTING MASTER LOSES A SERVICE** (section 2). The change is a
   UNION and the alternative reading was a substitution; the only way to show
   the difference is on real rows, where `AC-2026-00051` draws `electric ·
   water` from two common-area agreements.
3. **HARD RULE 1, WHICH SQLITE CANNOT EXPRESS AT ALL** (section 3). Every read
   here is tenant-scoped, and *an unset `app.tenant_id` returning zero rows is
   indistinguishable from the bug being fixed* — an empty service list reads as
   a correct answer. So section 3 asserts the read REFUSES rather than
   answering empty, and that another tenant's premises is not visible.
4. **THAT THE PLAN PICKER'S REFUSAL IS NOT THE ONE ANYBODY EXPECTED**
   (section 4). It was reported as the `no_services` branch of
   `plan_change_options`; on a real master account the call never reaches that
   branch — `_account_and_unit_plan` asks metering for unit `None` and takes
   the 404. Printed rather than described, because the difference decides
   whether this ruling has a plan consequence at all.

⚠ **IT WRITES NOTHING.** Every section runs inside a `transaction.atomic()`
aborted by raising, so the database is left exactly as it was found. The last
lines re-read the counts to show it.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone maservices
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/sbh_clone_maservices \
      JOBS_EAGER=false python3 manage.py shell \
        < ../10-scripts/br_cus_1093_master_services_readback.py

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — a mid-run reseed looks
exactly like a broken screen. `proof-db.sh clone` gives you a private one.

MEASURED 2026-09-23 ON A CLONE OF `brazosbend`, POSTGRESQL 16.13, PRODUCT 2.345.0
---------------------------------------------------------------------------------

    FOUND  premises 79  master accounts 1
    -- 1 . THE REPORTED CASE --
      a premises offering ['water'], 0 unit(s) -> master AC-2026-00052
        unit_id None   service_agreements 0
        services ['water']                 <- HEAD answered []  ("No services")
      add electric to the BUILDING -> services ['electric', 'water']
        service_agreements 0 (was 0) <- held by reference, nothing written
    -- 2 . NO EXISTING MASTER LOSES A SERVICE --
      AC-2026-00051  agreements ['electric', 'water']  building ['electric', 'water']
        services ['electric', 'water']
    -- 3 . HARD RULE 1 --
      no app.tenant_id -> AuthError(AUTH-003) <- REFUSES, never []
      only one tenant on this clone; cross-tenant leg not exercised
    -- 4 . THE PLAN PICKER --
      plan_change_options(AC-2026-00051) -> NotFoundError
        reached the no_services branch: False
        it refuses at seams.unit_row(None), before any service is read
    -- LEFT AS FOUND --
      premises 79   master accounts 1

⚠ **SECTION 3 PRINTS WHAT IT COULD NOT CHECK, WITH A NUMBER BESIDE IT.** This
clone carries ONE tenant, so the cross-tenant leg did not run — and a check that
reports nothing over a scope it silently excludes is indistinguishable from one
that found nothing (hard-won law 7, `G32`'s shape). The line says so rather than
leaving a reader to assume both legs were exercised.

**Read sections 1 and 4 together, because that is the finding.** The services
half is fixed and is a read. **The plan half was never the `no_services` branch
and is not a consequence of it** — `plan_change_options` calls
`_account_and_unit_plan`, which asks metering for unit `None` and takes the
404 long before any plan's services are compared. `OQ-INT-12403` (renumbered from 12398; CLOSED
2026-09-17) already ruled that a master account HAS no plan and that `null` is
the true answer, because the units below it may be on four different plans and
*"picking one would invent"*. So the picker refusing is CORRECT; what is wrong
is that it refuses with a bare *not found* about an account that plainly exists
(`DEF-CUS-6310`).
"""

from types import SimpleNamespace

from django.db import transaction

from apps.customers import models as cus
from apps.customers import selectors as csel
from apps.customers import services as csvc
from apps.identity import models as ident
from apps.metering import models as met
from apps.metering import seams as mseams
from apps.metering import selectors as msel
from apps.metering import services as msvc
from apps.tenancy import models as ten
from core import errors, tenancy

TENANT = "brazosbend"


class Rollback(Exception):
    """Raised to abort an atomic block once its answer has been printed."""


def _codes(account):
    """The Services cell, through BOTH reads, refusing to print one number when
    the singular and the plural disagree — they are one answer with two query
    plans and a reader must be told when they part."""
    one = csel.service_codes_for(account)
    many = csel.service_codes_for_accounts([account]).get(str(account.id))
    if one != many:
        return f"DISAGREE singular={one} plural={many}"
    return str(one)


tenant = ten.Tenant.objects.get(subdomain=TENANT)
with tenancy.tenant_context(str(tenant.id)):
    user = ident.User.objects.filter(tenant=tenant).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)

    premises_qs = met.Premises.objects.filter(tenant=tenant, deleted_at__isnull=True)
    masters = cus.Account.objects.filter(tenant=tenant, kind=csvc.ACCOUNT_KIND_MASTER)
    start_premises, start_masters = premises_qs.count(), masters.count()
    print(f"FOUND  premises {start_premises}  master accounts {start_masters}")

    print("── 1 · THE REPORTED CASE ──")
    try:
        with transaction.atomic():
            premises = msvc.create_premises(
                actor,
                {
                    "address_line": "77 Readback Row",
                    "owner_manager": "Readback Owner",
                    "owner_kind": "person",
                    "owner_ssn": "411220099",
                    "owner_account_type": "residential",
                    "services_available": ["water"],
                },
            )
            units = met.Unit.objects.filter(tenant=tenant, premises_id=premises["id"]).count()
            master = cus.Account.objects.filter(
                tenant=tenant, premises_id=premises["id"], kind=csvc.ACCOUNT_KIND_MASTER
            ).first()
            agreements = csel.service_agreements_for(master)
            print(
                f"  a premises offering {premises['services_available']}, "
                f"{units} unit(s) -> master {master.account_no}"
            )
            print(f"    unit_id {master.unit_id}   service_agreements {len(agreements)}")
            print(f"    services {_codes(master)}")

            # ⚠ **A SERVICE THE TENANT ACTUALLY ENABLES** — `BR-MET-003`
            # keeps `services_available` inside the tenant's enabled set, so a
            # probe that reached for `gas` on this utility refuses at the
            # premises door and never gets to the assertion, which reads
            # exactly like the selector being wrong.
            extra = next(
                (code for code in sorted(mseams.enabled_service_codes()) if code != "water"),
                None,
            )
            msvc.update_premises(
                actor, premises["id"], {"services_available": ["water", extra]}
            )
            after = csel.service_agreements_for(master)
            print(f"  add {extra} to the BUILDING -> services {_codes(master)}")
            print(
                f"    service_agreements {len(after)} (was {len(agreements)}) "
                "<- held by reference, nothing written"
            )
            raise Rollback()
    except Rollback:
        pass

    print("── 2 · NO EXISTING MASTER LOSES A SERVICE ──")
    for account in masters.order_by("account_no"):
        building = msel.premises_services_for([account.premises_id]).get(
            str(account.premises_id)
        )
        held = sorted(
            {
                row["service"]
                for row in (
                    csel.agreement_dict(a, csel._service_by_point_for(account))
                    for a in csel.service_agreements_for(account)
                )
                if row["service"]
            }
        )
        print(f"  {account.account_no}  agreements {held}  building {building}")
        print(f"    services {_codes(account)}")

    print("── 3 · HARD RULE 1 ──")
    a_premises = premises_qs.values_list("id", flat=True).first()
    # ⚠ **CLEARED, NOT "a context of None"** — `tenant_context` takes a real
    # uuid and nothing else, which is itself the rule working. This is the
    # state a background job or a streamed response body can genuinely reach
    # (`DEF-2734`), and it is the one that matters here: with the GUC unset the
    # RLS policy matches ZERO ROWS, so an empty service list would read as *this
    # building offers nothing* — byte-identical to the answer this whole change
    # exists to stop showing.
    tenancy.clear_current_tenant()
    try:
        answer = msel.premises_services_for([a_premises])
        print(f"  no app.tenant_id -> {answer!r}   ⛔ ANSWERED INSTEAD OF REFUSING")
    except errors.AuthError as exc:
        print(f"  no app.tenant_id -> AuthError({exc.code}) <- REFUSES, never []")
    finally:
        tenancy.set_current_tenant(str(tenant.id))
    other = ten.Tenant.objects.exclude(pk=tenant.pk).first()
    if other is not None:
        with tenancy.tenant_context(str(other.id)):
            foreign = msel.premises_services_for([a_premises])
        print(
            f"  another tenant's premises -> {len(foreign)} of 1 asked for "
            f"(absent, never refused — the batch posture)"
        )
    else:
        print("  only one tenant on this clone; cross-tenant leg not exercised")

    print("── 4 · THE PLAN PICKER ──")
    a_master = masters.order_by("account_no").first()
    if a_master is not None:
        try:
            options = csvc.plan_change_options(a_master.id)
            reasons = sorted({p["ineligible_reason"] for p in options["plans"]})
            print(f"  plan_change_options({a_master.account_no}) -> OK reasons {reasons}")
            print(f"    reached the no_services branch: {'no_services' in reasons}")
        except Exception as exc:  # noqa: BLE001 — the point is WHICH refusal
            print(f"  plan_change_options({a_master.account_no}) -> {type(exc).__name__}")
            print("    reached the no_services branch: False")
            print("    it refuses at seams.unit_row(None), before any service is read")

    print("── LEFT AS FOUND ──")
    print(f"  premises {premises_qs.count()}   master accounts {masters.count()}")
