# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-040 · US-CWP-041 · US-CWP-043 (EP-CWP-08) — the customer
#          portal's Usage, Every reading and Meters-and-equipment screens.
#          Screens CWP-033 · CWP-034 · CWP-037.
# Rules:   BR-CWP-029 (a credential attaches to somebody ALREADY ON FILE) ·
#          hard rule 1 (every read and write names its tenant EXPLICITLY —
#          `tenant_context()` sets the GUC and does not filter the queryset,
#          and the setup below runs as a superuser with RLS skipped)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-h-usage-readings.mjs
# ───────────────────────────────────────────────────────
"""A LOGIN ON THE METER'S OWN ACCOUNT, AND NOT ON WHICHEVER ONE A QUERY FINDS.

WHY THIS FILE EXISTS, AND WHY THE EXISTING ONE WILL NOT DO
----------------------------------------------------------
`seed_portal_demo` now plants wave H's history — twenty-four readings, the
corrected June, and the three assets — and it plants ALL of it on ONE account:
`1408 Elm St · A`, the portal fixture's own. That is the account
`US-CWP-040` §4, `US-CWP-041` §4 and `US-CWP-043` §4 describe, down to the
serial on the box.

`def-cwp-3965-fixture.py` already makes two logins, and neither is any use here:
it picks its customers **by query** over the generated sample estate — *"the
largest amount owing, and reads behind it"* — and the estate's accounts are not
Elm St. Signing in as one of those and opening `/usage` would draw a real chart
off a real meter and prove nothing about a single figure this wave asserts. It
would also read as a clean run, which is the expensive kind of wrong.

So this enrols the customer who actually holds the meter, **found through the
premises rather than by account number**, because `AC-2026-00052` is minted by a
counter and moves whenever the estate ahead of it changes size.

⚠ **AND THE ACCOUNT NUMBER IS NOT `ACC-10432-A` (`DEF-CWP-4174`).** Every
wave-E document — the execution plan's demo script, `EP-CWP-05`, the story
files, `cr068-e-getting-in.mjs`'s own default — names Maria's account
`ACC-10432-A`. `seed_portal_demo` has never produced that number: it opens the
account through `customers.create_account`, which takes the next number off the
tenant's own series. The walkthrough that hard-codes it cannot enrol anybody on
a freshly seeded database. This script prints the number it found, so the
person running the demo can read it off rather than guess.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone cwph --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-h-fixture.py)

Idempotent: a second run re-uses the credential it finds and writes nothing.
"""

from apps.assets import models as asset_models
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

PASSWORD = "Pine-Hill-2026!"
ELM_EMAIL = "elm@example.test"
ELM_ST = "1408 Elm St"
WATER_METER_SERIAL = "88-40219"

tenant = Tenant.objects.filter(subdomain="pine-hill").first()
if tenant is None:  # pragma: no cover — a run against an unseeded database
    raise SystemExit("no Pine Hill tenant — run `manage.py seed_portal_demo` first")

with tenant_context(tenant.pk):
    # ⚠ **EVERY FILTER NAMES `tenant_id` (`DEF-CWP-4173`'s lesson).** This runs
    # as `smartbillhub`, which is `rolsuper=t`, so `FORCE RLS` is skipped for
    # every query in this process — Django says so at boot on every command,
    # which is exactly why it reads as noise. Three tenants are seeded here.
    unit = (
        metering_models.Unit.objects.filter(
            tenant_id=tenant.pk, premises__address_line=ELM_ST, label="A"
        )
        .select_related("premises")
        .first()
    )
    if unit is None:
        raise SystemExit(f"no {ELM_ST} · A on this tenant — seed_portal_demo did not run")

    account = customers_models.Account.objects.filter(
        tenant_id=tenant.pk, unit_id=unit.id
    ).first()
    if account is None:
        raise SystemExit(f"nobody holds an account at {ELM_ST} · A")

    # The three facts the walkthrough is about to assert, stated HERE as well,
    # so a fixture that ran against a half-seeded database says so rather than
    # handing the browser an empty screen to be blamed for.
    reads = metering_models.MeterRead.objects.filter(
        tenant_id=tenant.pk, account_id=account.pk, superseded_by_id__isnull=True
    ).count()
    months = metering_models.MonthlyUsage.objects.filter(
        tenant_id=tenant.pk, account_id=account.pk, superseded_by_id__isnull=True
    ).count()
    meter = asset_models.Asset.objects.filter(
        tenant_id=tenant.pk, serial_no=WATER_METER_SERIAL
    ).first()

    print(f"  account       {account.account_no}   ({ELM_ST} · {unit.label})")
    print(f"  live readings {reads}")
    print(f"  stated months {months}")
    print(f"  water meter   {WATER_METER_SERIAL}: {'present' if meter else 'MISSING'}")
    if reads == 0 or meter is None:
        raise SystemExit(
            "wave H's history is not planted on this account. `seed_portal_demo` should "
            "have printed a `wave H:` line; if it printed `wave H SKIPPED`, read the "
            "reason it gave. The walkthrough would open CWP-033 and honestly draw "
            "nothing, which reads exactly like a broken screen."
        )

    existing = credentials.credential_by_email(tenant.pk, ELM_EMAIL)
    if existing is not None:
        print(f"  {ELM_EMAIL} already enrolled — left alone")
    else:
        credentials.create_credential(
            tenant.pk,
            account=account,
            email=ELM_EMAIL,
            password=PASSWORD,
            otp_channel=portal_models.CHANNEL_SMS,
        )
        print(f"  {ELM_EMAIL} enrolled on {account.account_no}")

    print()
    print(f"sign in as {ELM_EMAIL}, password {PASSWORD}")
