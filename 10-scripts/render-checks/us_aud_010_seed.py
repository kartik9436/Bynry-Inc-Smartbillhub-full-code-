#!/usr/bin/env python3
"""Plant US-AUD-010's worked scenario in a REAL database, for the browser check.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL="postgres://…/sbh_aud010_smoke" \
      python3 10-scripts/render-checks/us_aud_010_seed.py [<tenant subdomain>]

⚠ **IT WRITES THROUGH `core.audit`, NOT THROUGH THE MODEL.** The point of the
story is what the ONE writer will and will not assemble, so a fixture that
INSERTed the row directly would seed a screen the product could not actually
produce — a walkthrough proving a thing the running code cannot do. The row this
plants is the row a runbook would write.

⚠ **AND IT WRITES A PERSON'S ROW AND AN UNNAMED JOB'S ROW BESIDE IT**, because
the browser check's real assertion is a NEGATIVE one: the automation's cell must
hold no colleague's name. That assertion cannot be made on a screen with no
colleague's name on it.

The three rows are the three answers the Actor column can now give:

    Returned payments, version 4   ← a NAMED automation      (US-AUD-010)
    <the tenant's owner>           ← a person                (unchanged)
    System job                     ← an UNNAMED system job   (BR-AUD-003)
"""

import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.audit.models import AuditLog  # noqa: E402
from apps.audit import services as audit_services  # noqa: E402
from apps.customers.models import Account  # noqa: E402
from apps.identity.models import User  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core import audit as audit_kernel  # noqa: E402
from core import tenancy as tenancy_kernel  # noqa: E402

RETURNED_PAYMENTS = audit_kernel.AutomationActor(
    kind=audit_kernel.ACTOR_KIND_RUNBOOK,
    name="Returned payments",
    version="4",
)


def main() -> int:
    subdomain = sys.argv[1] if len(sys.argv) > 1 else "brazosbend"
    tenant = Tenant.objects.get(subdomain=subdomain)

    audit_kernel.set_audit_sink(audit_services.store_row)
    # ⚠ EVERY TENANT-TABLE READ IS INSIDE THE CONTEXT, INCLUDING THE LOOKUPS.
    # This script's first draft read `Account` and `User` OUTSIDE it and found
    # nothing, then reported "no account — seed the tenant first" about a
    # database holding 48 accounts. `FORCE ROW LEVEL SECURITY` applies to the
    # owner too and the GUC is unset out here, so the honest answer to a
    # contextless query IS zero rows. The failure looks like missing DATA and is
    # actually missing CONTEXT — worth the comment, because it reads as a seeding
    # problem and sends you to the wrong place.
    with tenancy_kernel.tenant_context(tenant.id):
        # The row must land on a REAL account: step 4 of the walkthrough opens
        # that account's own History tab and looks for it there.
        account = Account.objects.filter(tenant_id=tenant.id).order_by("account_no").first()
        if account is None:
            print(f"no account under {subdomain} — seed the tenant first")
            return 1
        person = User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
        # 1 · the automation — named and versioned, and carrying no user id.
        audit_kernel.money_action(
            RETURNED_PAYMENTS,
            "payment.fee_applied",
            "account",
            account.id,
            after={"fee": "25.0000", "reason": "returned payment", "count": 43},
        )
        # 2 · a person, so the negative assertion has something to be negative about.
        audit_kernel.money_action(
            person,
            "account.note_added",
            "account",
            account.id,
            after={"note": "Called about the returned payment fee"},
        )
        # 3 · an UNNAMED system job — BR-AUD-003, still the honest answer for one.
        audit_kernel.money_action(
            None,
            "invoice.issued",
            "account",
            account.id,
            after={"job": "bill_run:09-A", "total": "247.30"},
        )
        planted = AuditLog.objects.filter(
            tenant_id=tenant.id, entity_id=account.id
        ).order_by("-created_at")[:3]
        for row in planted:
            print(
                f"  {row.action:<24} actor_user_id={row.actor_user_id} "
                f"kind={row.actor_kind} label={row.actor_label!r} version={row.actor_version!r}"
            )
    print(f"planted on {subdomain} account {account.account_no} ({account.id})")
    # The walkthrough must be TOLD which account, never guess: its first draft
    # opened whatever the list sorted first and went red over an account that
    # has no runbook row and never would.
    print(f"    export SMOKE_ACCOUNT={account.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
