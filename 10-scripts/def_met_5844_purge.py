"""Purge what `def_met_5844_owner_account_walkthrough.mjs` wrote.

⚠ **A WALK THAT LEAVES ROWS BEHIND MAKES THE NEXT PERSON'S BETA LIE TO THEM.**
An earlier walk on 2026-09-19 left 26 discounts and a blocking draft, and they
were cleaned up by hand. The browser walk cannot roll back — it goes through
HTTP, so every save really commits — so the purge is a separate act and this is
it.

**It deletes by the run's own tag and nothing else.** Every address the walk
creates begins `W5844-` followed by that run's timestamp, so this cannot reach a
row a person made: no clerk types that prefix. It refuses to run without one.

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/<db> \
      MET5844_PURGE=W5844-633481 \
      python3 manage.py shell < ../10-scripts/def_met_5844_purge.py

`MET5844_PURGE=W5844-` purges every run's leftovers at once.

⚠ **IT DELETES ACCOUNTS AND IT SAYS SO.** The walk's addresses really do open
owner accounts now — `OQ-MET-12472` was settled on 2026-09-19 and the form
collects an identifier — so those accounts are walk-made rows on walk-made
addresses and go with them. CLAUDE.md hard rule 4 freezes issued invoices,
invoice lines, payments and journal entries; an account opened and closed inside
one walk has none of those, and this prints what it found before it removes
anything so a surprise is visible rather than silent.

⚠ **AND SINCE THE RULING IT HAS THREE MORE THINGS TO UNDO, WHICH IS WHY THIS
FILE CHANGED AT ALL (`OQ-MET-12472`).** An account that actually opens leaves a
trail the old purge could not see, and every one of them is PROTECTed, so
deleting the account alone would simply raise:

  * `premises_owners.master_account_id` — a REAL owner row, one of the beta's
    five, now pointing at a walk-made account. **The row is not deleted; the
    LINK is cleared**, because the party is the utility's and only the link is
    the walk's.
  * `customer_accounts` — the `BR-CUS-054` link row between the account and
    whoever the door matched or created.
  * `customers` — the party the door CREATED when no existing one matched. **A
    customer that already existed is left alone**, and telling the two apart is
    what `walk_made_customers` below does: only a customer whose every link is
    to an account this purge is removing can have been made by this walk.

**So the beta's own numbers — 79 properties · 1 master account · 5 owners · 55
customers — come back exactly**, and the script prints all four at the end
rather than asking anyone to take that on trust.
"""

import os

from django.db import transaction

from apps.customers import models as cus
from apps.metering import models as met
from apps.tenancy import models as ten
from core import tenancy

TAG = os.environ.get("MET5844_PURGE", "").strip()
if not TAG or not TAG.startswith("W5844-"):
    raise SystemExit(
        "MET5844_PURGE must be set to the run's tag, e.g. W5844-633481 "
        "(or W5844- for every run). Refusing to guess what to delete."
    )

# ⚠ **ONE TRANSACTION, AND THIS WAS LEARNED THE HARD WAY ON 2026-09-19.** The
# first version deleted in steps with no transaction around them. It cleared
# `premises_owners.master_account_id` and the `customer_accounts` links, then hit
# a `ProtectedError` on a `Contact` nobody had listed — **and the two completed
# steps were the very evidence the re-run needed to tell a walk-made customer
# from the utility's own.** The second run saw zero links, concluded the walk had
# created nobody, and left `C-00056 Ridge Property LLC` orphaned in the beta.
# A purge that half-runs must leave nothing behind, so it either all happens or
# none of it does.
tenant = ten.Tenant.objects.get(subdomain=os.environ.get("MET5844_TENANT", "brazosbend"))
with tenancy.tenant_context(str(tenant.id)), transaction.atomic():
    rows = list(
        met.Premises.objects.filter(tenant=tenant, address_line__startswith=TAG)
        .values_list("id", "premise_no", "address_line")
    )
    if not rows:
        print(f"nothing to purge for {TAG}")
    else:
        ids = [row[0] for row in rows]
        accounts = list(
            cus.Account.objects.filter(tenant=tenant, premises_id__in=ids)
            .values_list("account_no", "kind")
        )
        units = met.Unit.objects.filter(tenant=tenant, premises_id__in=ids)
        account_ids = list(
            cus.Account.objects.filter(tenant=tenant, premises_id__in=ids)
            .values_list("id", flat=True)
        )
        # ── WHICH CUSTOMERS DID THIS WALK MAKE? ──────────────────────────────
        # ⚠ **ASKED BEFORE ANYTHING IS DELETED, BECAUSE AFTERWARDS IT IS
        # UNANSWERABLE** — the links that carry the answer are about to go. A
        # customer counts as the walk's only when EVERY account it is linked to
        # is one of the walk's; a customer the door MATCHED has at least one
        # other link and is the utility's. Deleting one of those would take a
        # real party out of the beta and nothing downstream would notice.
        linked = cus.CustomerAccount.objects.filter(tenant=tenant, account_id__in=account_ids)
        candidates = set(linked.values_list("customer_id", flat=True))
        walk_made_customers = [
            customer_id
            for customer_id in candidates
            if not cus.CustomerAccount.objects.filter(tenant=tenant, customer_id=customer_id)
            .exclude(account_id__in=account_ids)
            .exists()
        ]
        # The owner rows are the utility's five; only the LINK is the walk's.
        owner_links = met.PremisesOwner.objects.filter(
            tenant=tenant, master_account_id__in=account_ids
        )
        print(f"purging {len(rows)} address(es) tagged {TAG}:")
        for _, number, address in rows:
            print(f"  {number}  {address}")
        print(f"  units: {units.count()}   accounts on them: {accounts or 'none'}")
        print(
            f"  owner links to clear: {owner_links.count()}   "
            f"customer links: {linked.count()}   "
            f"customers the walk created: {len(walk_made_customers)}"
        )
        # ── EVERYTHING THAT POINTS AT ONE OF THESE ACCOUNTS ─────────────────
        # ⚠ **EVERY ONE OF THESE IS `on_delete=PROTECT`, SO A MISSED ONE IS A
        # `ProtectedError` RATHER THAN A SILENT LEFTOVER** — which is the good
        # kind of failure and is how this list was found: `Contact` was missing
        # and the purge stopped with the row it could not delete NAMED. The
        # contact exists because the owner account door now forwards the
        # owner's own contact details (`DEF-MET-5847`); before that fix no
        # account was ever created here, so no contact ever was either.
        protected = [
            ("contacts", cus.Contact.objects.filter(tenant=tenant, account_id__in=account_ids)),
            ("addresses", cus.Address.objects.filter(tenant=tenant, account_id__in=account_ids)),
            (
                "service agreements",
                cus.ServiceAgreement.objects.filter(tenant=tenant, account_id__in=account_ids),
            ),
            ("notes", cus.AccountNote.objects.filter(tenant=tenant, account_id__in=account_ids)),
            (
                "opening buckets",
                cus.AccountOpeningBucket.objects.filter(
                    tenant=tenant, account_id__in=account_ids
                ),
            ),
        ]
        for name, qs in protected:
            count = qs.count()
            if count:
                print(f"  {name}: {count}")
                qs.delete()
        # Order matters: everything that POINTS AT an account first, then the
        # accounts, then the children of the address, then the address.
        owner_links.update(master_account_id=None)
        linked.delete()
        cus.Account.objects.filter(tenant=tenant, premises_id__in=ids).delete()
        if walk_made_customers:
            cus.Customer.objects.filter(tenant=tenant, id__in=walk_made_customers).delete()
        units.delete()
        met.Premises.objects.filter(tenant=tenant, id__in=ids).delete()

    # ⚠ **ALL FOUR NUMBERS, BECAUSE THREE OF THEM CAN NOW MOVE.** *The
    # property count came back* passes over a customer this walk invented and
    # an owner link it left pointing at nothing (CLAUDE.md hard-won law 7 — a
    # check that cannot fail on the thing that changed).
    print(f"premises now: {met.Premises.objects.filter(tenant=tenant).count()}")
    print(
        "master accounts now: "
        f"{cus.Account.objects.filter(tenant=tenant, kind='master').count()}"
    )
    print(f"premises owners now: {met.PremisesOwner.objects.filter(tenant=tenant).count()}")
    print(f"customers now: {cus.Customer.objects.filter(tenant=tenant).count()}")
    print(
        "owner rows still linked to an account: "
        f"{met.PremisesOwner.objects.filter(tenant=tenant, master_account_id__isnull=False).count()}"
    )
