"""Remove the three transfers `po20260920_transfers_tab_seed.py` planted.

⚠ **IT DELETES ONLY THE IDS THE SEED WROTE DOWN.** A purge that matched on
*"every transfer"* would take a sibling lane's work with it, and in this beta
the tab is the only place a transfer can be seen at all.

⚠ **AND IT MATCHED ON A NAME UNTIL IT WAS RUN.** The first draft filtered
`transfer.customer__display_name` for the seed's marker — which on an OPEN
transfer is the **SELLER**, a real demo customer, and only becomes the seeded
buyer once `reassign_account` overwrites it at commit. It found ONE row of
three, deleted it, and printed a clean BEFORE/AFTER. The same one-name-two-jobs
mechanic the tab was rebuilt for, in the tool that checks the rebuild.

⚠⚠ **IT NEVER DELETES A CUSTOMER IT DID NOT CREATE, AND THE FIRST DRAFT DID.**
`row.customer` is the SELLER on an open transfer — a real demo customer — and
only becomes the seeded buyer once `reassign_account` overwrites it. The first
draft read it as *"the buyer"* unconditionally, and on the open row it deleted
**every `customer_accounts` link belonging to Ana Alvarez, C-00001**, then tried
to delete her and was stopped only by a `PROTECT` from `PortalCredential`. The
link was restored by hand; the customer survived by luck. `DEF-CUS-5945`.

**So the guard is now the NAME and not the position:** nothing is deleted unless
its `display_name` carries `MARKER`, which only this seed's own rows do. The same
one-name-two-jobs mechanic the tab was rebuilt for, found twice in one hour — once
in the screen and once in the tool that checks the screen.

⚠ **THE COMMITTED ROW REASSIGNED A REAL ACCOUNT, AND THAT IS PUT BACK** —
`reassign_account` deletes the seller's `customer_accounts` link and writes the
buyer's. Deleting the transfer alone would leave a demo account owned by a
walkthrough's invented buyer, which is a worse leftover than the row itself.
The seller's id is read back out of `audit_log`'s `transfer.reassigned` row,
which is where the ruling put it (hard rule 4 — the value a correction replaces
lives only there, and `OQ-1340` is open on whether it is pruned).

Prints BEFORE and AFTER counts, so "the beta is as it was found" is measured.
"""
import json  # noqa: E402
import pathlib  # noqa: E402

import django  # noqa: E402

django.setup()

from apps.customers import models as cmodels  # noqa: E402
from apps.customers import transfers  # noqa: E402
from apps.audit.models import AuditLog  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

MARKER = "WALK-20260920"
STATE = pathlib.Path(__file__).with_name("po20260920_transfers_tab_planted.json")

def _drop_customer(customer) -> None:
    """Remove a customer THIS SEED CREATED, and whatever protects it.

    ⚠ `reassign_account` resolves the buyer through `link_customer`, which also
    mints a `PortalCredential` — a `PROTECT` edge. Deleting the customer without
    it raises `ProtectedError` halfway through the loop, which is how the first
    draft aborted after doing its damage and before reporting any of it.
    """
    if MARKER not in (customer.display_name or ""):
        raise SystemExit(f"REFUSED: {customer.customer_no} is not this seed's row")
    from apps.portal import models as pmodels

    creds = pmodels.PortalCredential.objects.filter(customer=customer)
    links = cmodels.CustomerAccount.objects.filter(customer=customer)
    print(
        f"  removing seeded customer {customer.customer_no}: "
        f"{links.count()} link(s), {creds.count()} credential(s)"
    )
    creds.delete()
    links.delete()
    customer.delete()


tenant = Tenant.objects.get(subdomain="brazosbend")
with tenant_context(tenant.id):
    print("BEFORE transfers:", transfers.Transfer.objects.count())
    if not STATE.exists():
        raise SystemExit(f"no {STATE.name} — nothing is recorded as planted, so nothing is removed")
    wanted = json.loads(STATE.read_text(encoding="utf-8"))
    planted = list(transfers.Transfer.objects.filter(id__in=[one["id"] for one in wanted]))
    print(f"recorded {len(wanted)} id(s); still present: {len(planted)}")
    for one in wanted:
        if not any(str(row.id) == one["id"] for row in planted):
            print(f"  ! already gone: {one['label']} on {one['account_no']}")

    def is_ours(customer) -> bool:
        """The ONLY licence to delete a customer row. See the header."""
        return customer is not None and MARKER in (customer.display_name or "")

    for row in planted:
        buyer = row.customer
        # Put the account back with whoever held it before the commit.
        entry = (
            AuditLog.objects.filter(action="transfer.reassigned", entity_id=row.id)
            .order_by("-created_at")
            .first()
        )
        if entry is not None:
            block = (entry.after or {}).get("reassignment") or {}
            for seller_id in block.get("from_customer_ids") or []:
                cmodels.CustomerAccount.objects.get_or_create(
                    tenant_id=tenant.id, account_id=row.from_account_id, customer_id=seller_id
                )
                print(f"  restored seller {seller_id} on {block.get('account_no')}")
            cmodels.CustomerAccount.objects.filter(
                account_id=row.from_account_id, customer=buyer
            ).delete()
        row.delete()
        if not is_ours(buyer):
            # An OPEN transfer still points at the SELLER, who is a real demo
            # customer. Deleting the row is the whole job here.
            print(f"  left {buyer.customer_no} alone — not this seed's row")
            continue
        if not transfers.Transfer.objects.filter(customer=buyer).exists():
            _drop_customer(buyer)

    # ── the seller the seed MADE for the balance case ───────────────────
    # It exists only because every indebted demo account has nobody on file,
    # and `start_transfer` refuses such an account. Removing it puts that
    # account back to having no customer link, which is how it was found.
    for seeded in cmodels.Customer.objects.filter(display_name__contains=MARKER):
        _drop_customer(seeded)

    print("AFTER transfers:", transfers.Transfer.objects.count())
    print("AFTER marker customers:", cmodels.Customer.objects.filter(display_name__contains=MARKER).count())
    STATE.unlink(missing_ok=True)
    print(f"removed {STATE.name}")
