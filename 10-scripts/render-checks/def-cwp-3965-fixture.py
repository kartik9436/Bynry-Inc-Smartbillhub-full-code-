# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-3965 — `CWP-022` drawn as a stack of cards with no balance
#          strip, no right rail and a one-line attention panel.
# Rules:   BR-CWP-029 (a credential attaches to somebody ALREADY ON FILE) ·
#          BR-MET-106 (a month's usage is derived from reads, never typed) ·
#          hard rule 1 (every write inside one tenant's context)
# Tests:   this is fixture prep for
#          10-scripts/render-checks/cr068-f-home-accounts-details.mjs
#          (⚠ it named `def-cwp-3965-home-layout.mjs` until 2026-09-06 and NO
#           SUCH FILE HAS EVER EXISTED — `DEF-CWP-4139`. The fixture shipped;
#           the walkthrough it was written to feed did not, so both this line
#           and `Home.tsx`'s claimed a browser check was watching a screen the
#           PO had personally rejected for its shape. Hard-won law 1.)
# ───────────────────────────────────────────────────────
"""A LOGIN FOR PINE HILL, AND TWELVE MONTHS BEHIND IT.

WHY THIS FILE EXISTS
--------------------
`10-scripts/cwp_portal_walkthrough.mjs` and `render-checks/fix2-holds-and-
refusals.mjs` both sign in as **`ana@example.test` / `Pine-Hill-2026!`**, and
**nothing in this repository creates that login.** `seed_portal_demo` provisions
the two utilities and plants the sample estate; `portal_credential` comes out of
it with **zero rows**, and sign-in then answers `{"ok":false,"reason":"wrong"}`
— which reads exactly like a broken product. The walkthrough's own header warns
about this in capitals and names the command that rules it out
(`select count(*) from portal_credential`); what it could not do is enrol
anybody, because `create_credential` is Python and the walkthrough is Node.

So this is that missing half, written where every other render-check writes its
fixture, and it is IDEMPOTENT: run it twice and the second run re-uses the
credentials it finds and writes nothing new.

WHICH CUSTOMER, AND WHY IT MATTERS MORE THAN IT LOOKS
----------------------------------------------------
The walkthrough's own sentence: *"the login decides what this proves — a
customer holding an account with no bills exercises every signed-in screen in
its EMPTY state, which reads as a clean run."* `CWP-022` is the screen that
sentence was written for: at a zero balance there is **no attention panel at
all** (`BR-CWP-093`), so a run against a settled account proves nothing about
the panel this defect is mostly about.

Two logins, therefore, chosen by what they HOLD rather than by name:

  * `ana@example.test`   — the householder. One account, an amount owing, a due
                           date, two bills and eight reads. This is the shape
                           `08-screen-layouts.md` draws `CWP-022` in.
  * `maria@example.test` — the landlord. Three accounts that share a plan and
                           sit at three addresses, so the rail's **YOUR
                           SERVICE** panel has to say *varies by account* on the
                           address and state the plan on the same panel. Every
                           unit test in the repo passes one account.

Both are picked by QUERY, not by account number: the sample estate is generated
and its numbers move. The script prints who it chose.

THE TWELVE MONTHS
-----------------
`monthly_usage_service.recompute_account` is metering's own derivation over
`meter_reads` (`BR-MET-106`). It is called rather than `MonthlyUsage` rows being
written here, for the reason `cr070-b-fixture.py` gives about its own tables:
a fixture that wrote the derived row directly would prove the screen renders and
prove nothing about the figure on it.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone <label> --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/def-cwp-3965-fixture.py)
"""

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.metering import monthly_usage_service
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.portal.seams import payments_seam
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

PASSWORD = "Pine-Hill-2026!"
HOUSEHOLDER = "ana@example.test"
LANDLORD = "maria@example.test"


def _candidates(tenant_id):
    """Every customer on this tenant, with what each one actually holds.

    ⚠ **FILTERED ON `tenant_id` EXPLICITLY, AND THAT IS NOT BELT-AND-BRACES
    (`DEF-CWP-4130`).** The first draft walked `CustomerAccount.objects.all()`
    inside `tenant_context()` and trusted row-level security to keep it inside
    Pine Hill. **The setup this file's own header prescribes does not enforce
    RLS:** `proof-db.sh` + `config.settings.local` connects as `smartbillhub`,
    which is `rolsuper=t`, so `FORCE RLS` is skipped for every query this
    process makes — Django prints exactly that at boot, on every command, which
    is why it reads as noise. The walk therefore returned all three seeded
    tenants' links, the first account it reached belonged to Brazos Bend, and
    `payments_seam.account_balance` refused it by name.

    **`tenant_context()` sets the GUC; it does not filter the queryset.** In
    this repository it is necessary and never sufficient.
    """
    holdings: dict[str, list] = {}
    links = customers_models.CustomerAccount.objects.filter(tenant_id=tenant_id)
    for link in links:
        account = customers_models.Account.objects.filter(
            pk=link.account_id, tenant_id=tenant_id
        ).first()
        if account is None:
            continue
        holdings.setdefault(str(link.customer_id), []).append(account)
    out = []
    for customer_id, accounts in holdings.items():
        owing = 0.0
        reads = 0
        bills = 0
        for account in accounts:
            owing += float(payments_seam.account_balance(account.pk).get("owing") or 0)
            reads += metering_models.MeterRead.objects.filter(account_id=account.pk).count()
            bills += billing_models.Invoice.objects.filter(
                account_id=account.pk, status=billing_models.INVOICE_ISSUED
            ).count()
        out.append(
            {
                "customer_id": customer_id,
                "accounts": accounts,
                "owing": owing,
                "reads": reads,
                "bills": bills,
            }
        )
    return out


def _enrol(tenant_id, email, holding):
    existing = credentials.credential_by_email(tenant_id, email)
    account = holding["accounts"][0]
    if existing is not None:
        print(f"  {email:22s} already enrolled — left alone")
        return existing
    credentials.create_credential(
        tenant_id,
        account=account,
        email=email,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    print(
        f"  {email:22s} → {len(holding['accounts'])} account(s), "
        f"${holding['owing']:.2f} owing, {holding['bills']} bill(s), {holding['reads']} read(s)"
    )
    return credentials.credential_by_email(tenant_id, email)


tenant = Tenant.objects.filter(name__icontains="Pine Hill").first()
if tenant is None:  # pragma: no cover — a run against an unseeded database
    raise SystemExit("no Pine Hill tenant — run `manage.py seed_portal_demo` first")

with tenant_context(tenant.pk):
    holdings = _candidates(tenant.pk)
    # The householder: ONE account, the largest amount owing, and reads behind it.
    single = [h for h in holdings if len(h["accounts"]) == 1 and h["reads"] and h["owing"] > 0]
    single.sort(key=lambda h: h["owing"], reverse=True)
    # The landlord: the most accounts, then the most owing.
    many = [h for h in holdings if len(h["accounts"]) > 1 and h["reads"]]
    many.sort(key=lambda h: (len(h["accounts"]), h["owing"]), reverse=True)
    if not single or not many:
        raise SystemExit(
            "the sample estate holds no account with reads AND an amount owing — "
            "a run against it would exercise CWP-022's EMPTY state and prove half of one"
        )

    print("enrolling:")
    chosen = [(HOUSEHOLDER, single[0]), (LANDLORD, many[0])]
    for email, holding in chosen:
        _enrol(tenant.pk, email, holding)

    print("stating the months every read supports (BR-MET-106):")
    for _, holding in chosen:
        for account in holding["accounts"]:
            counts = monthly_usage_service.recompute_account(account.pk)
            months = metering_models.MonthlyUsage.objects.filter(
                account_id=account.pk, superseded_by_id__isnull=True
            ).count()
            print(f"  {account.account_no}: {counts} → {months} stated month(s)")

    print(f"\nsign in as {HOUSEHOLDER} or {LANDLORD}, password {PASSWORD}")
