"""Plant THREE transfers on the demo tenant so the Transfers tab has a table.

⚠ **THROUGH THE REAL DOORS** — `transfers.start_transfer`,
`set_new_customer`, `set_sale_date`, `acknowledge_money` and, for the third
row, `reassign_account`. Nothing here writes a `transfers` row by hand, so what
the browser walk reads is exactly what a clerk's wizard produces. A hand-built
fixture would let the screen pass over a shape the product never makes, which
is the whole failure mode `10-scripts/*_walkthrough.mjs` exists to close.

**Why three, and why these three** — each is a state the tab must draw
differently, and the middle one is the case the ruling created:

  1. an OPEN transfer, part-way through  → `Sold to` states its absence
  2. an OPEN transfer with a sale date within 7 days → `Selling this week` = 1
  3. a COMMITTED transfer               → `Sold to` names the BUYER, and the
     account is NOT closed, which is `BR-CUS-1030` in one row
  4. an OPEN transfer on an account CARRYING A BALANCE → `Taken on` shows a
     FIGURE rather than a dash

⚠ **THE FOURTH NEEDS A SELLER AND THE DEMO'S INDEBTED ACCOUNTS HAVE NONE.**
Every account in the seed that carries a balance has no `customer_accounts`
row, and `start_transfer` refuses one — *"no account may exist with nobody
identifiable behind it"* (`CR-058` task 14). So this script MAKES its own
seller, links it, and the purge removes both the link and the customer. It
touches no row it did not create.

⚠ **AND WITHOUT IT THE BROWSER NEVER SEES A FIGURE.** The three accounts above
all sit at a zero balance, so `Taken on` reads `—` on every one — which is
correct, and is also the one cell state that cannot tell a working money column
from a broken one.

Paired with `po20260920_transfers_tab_purge.py`: the beta is left exactly as it
was found, and both print their counts so that claim is checked and not merely
asserted.

⚠ **THE PURGE READS AN ID FILE AND NOT A NAME, AND THE FIRST DRAFT LEARNED WHY
THE HARD WAY.** It matched `transfer.customer__display_name`, which on an OPEN
transfer is the **SELLER** — a real demo customer — and only becomes the seeded
buyer once `reassign_account` overwrites it at commit. So it found ONE of three
rows and reported success. That is the same one-name-two-jobs mechanic this
whole walk exists to check, biting the tool that checks it.
"""
import datetime  # noqa: E402
import json  # noqa: E402
import pathlib  # noqa: E402
import django  # noqa: E402

django.setup()

from types import SimpleNamespace  # noqa: E402

from apps.customers import models as cmodels  # noqa: E402
from apps.customers import transfers  # noqa: E402
from apps.identity.models import TenantMembership  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

MARKER = "WALK-20260920"
#: What the purge reads. Beside the scripts, not in the scratchpad — a
#: scratchpad does not survive a container restart and neither would the only
#: record of what is planted in a live beta.
STATE = pathlib.Path(__file__).with_name("po20260920_transfers_tab_planted.json")

tenant = Tenant.objects.get(subdomain="brazosbend")
with tenant_context(tenant.id):
    print("BEFORE transfers:", transfers.Transfer.objects.count())

    # ⚠ THE ACTOR IS THE USER PLUS THE ROLE `require_role` READS, and `role` is
    # the role's CODE rather than the `Role` row — handing the object through is
    # a silent refusal. Copied from the move-out seeder, which learned it.
    membership = (
        TenantMembership.objects.select_related("user", "role")
        .filter(role__code="system_admin")
        .first()
    )
    user = membership.user
    actor = SimpleNamespace(id=user.id, pk=user.id, user=user, role=membership.role.code)
    print("actor:", user.email, "role:", actor.role)

    # Only an OCCUPANT may sell (`BR-CUS-018` / `BR-MET-036`), and the account
    # must have somebody on file — `_seller_of` refuses one that does not.
    sellable = [
        account
        for account in cmodels.Account.objects.filter(
            closed_at__isnull=True, unit_id__isnull=False
        ).order_by("account_no")
        if cmodels.CustomerAccount.objects.filter(account=account).exists()
    ]
    if len(sellable) < 3:
        raise SystemExit(f"need 3 sellable accounts, found {len(sellable)}")

    today = datetime.date.today()
    plan = [
        ("open, part-way through", sellable[0], today + datetime.timedelta(days=45), False),
        ("selling this week", sellable[1], today + datetime.timedelta(days=3), False),
        ("committed", sellable[2], today - datetime.timedelta(days=9), True),
    ]

    # ── the fourth: an account carrying a real balance ──────────────────
    indebted = (
        cmodels.Account.objects.filter(closed_at__isnull=True, unit_id__isnull=False)
        .exclude(balance=0)
        .order_by("-balance")
        .last()
    )
    if indebted is not None and not cmodels.CustomerAccount.objects.filter(
        account=indebted
    ).exists():
        seller = cmodels.Customer.objects.create(
            tenant_id=tenant.id,
            display_name=f"{MARKER} seller",
            kind="person",
            customer_no=f"C-{MARKER[-5:]}",
        )
        cmodels.CustomerAccount.objects.create(
            tenant_id=tenant.id, account=indebted, customer=seller
        )
        print(f"MADE seller {seller.customer_no} for {indebted.account_no} (balance {indebted.balance})")
        plan.append(
            ("carries a balance", indebted, today + datetime.timedelta(days=20), False)
        )
    else:
        print("! no indebted account without a seller — the balance case is SKIPPED")

    planted: list[dict[str, str]] = []
    for label, account, sold_on, commit in plan:
        row = transfers.start_transfer(actor, {"from_account_id": str(account.id)})
        buyer = {
            "display_name": f"{MARKER} buyer {label}",
            "kind": "person",
            # One identifier is enough (`BR-CUS-1023`); a phone identifies a
            # person here, and it is the cheapest one to make unique.
            "identity": {"phone": f"5550{abs(hash(label)) % 100000:05d}"},
            "email": f"walk-{abs(hash(label)) % 10000}@example.invalid",
        }
        transfers.set_new_customer(actor, row["id"], {"customer": buyer})
        transfers.set_sale_date(actor, row["id"], {"sold_on": sold_on.isoformat()})
        transfers.acknowledge_money(actor, row["id"], {"acknowledged": True})
        if commit:
            transfers.reassign_account(
                actor, row["id"], {"from_account_id": str(account.id), "customer": buyer}
            )
        after = transfers.Transfer.objects.get(id=row["id"])
        planted.append({"id": str(after.id), "label": label, "account_no": account.account_no})
        print(
            f"PLANTED {label}: {after.transfer_no or '(no series)'} "
            f"account={account.account_no} sold_on={after.out_date} "
            f"state={after.state} step={after.step} closed={account.closed_at}"
        )

    STATE.write_text(json.dumps(planted, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {STATE.name}: {len(planted)} id(s)")
    print("AFTER transfers:", transfers.Transfer.objects.count())
