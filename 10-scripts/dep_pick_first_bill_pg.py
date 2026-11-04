"""DEF-CUS-9521 (lane DEP-PICK) — the FIRST BILL honours the size the clerk
picked, proved on PostgreSQL (after `dep_pick_walk_prep.py` and the walk).

PO 2026-10-04, verbatim: *"(c) Let the clerk pick the size on the Deposit
step."* A deposit owed and NOT taken at the counter goes on the first bill
(BR-BIL-012). Billing asks rating by ACCOUNT, and an account opened on a unit
with no meter has no connection size — so the first bill must read the size the
counter picked, or it would refuse the bill (`size_not_recorded`).

1. Opens an account on `SCW-U-353` (no meter) with the deposit DEFERRED to the
   first bill and 2" picked — through `customers.services.create_account`, the
   write the New account screen makes.
2. Asks `billing.first_bill.deposit_line_for` — the function the first bill
   runs — for that account (expects a **$600.00** deposit line) and for the
   walk's `AC-2026-00054` (2" picked, $600.00 taken at the counter: expects NO
   line, $600.00 already paid).

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_deppick \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/dep_pick_first_bill_pg.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402

from apps.billing import first_bill  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.customers import services as customer_services  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

Unit = apps.get_model("metering", "Unit")


def line_for(account) -> str:
    unit = Unit.objects.get(pk=account.unit_id)
    data = SimpleNamespace(
        rate_plan_id=unit.rate_plan_id,
        account_no=account.account_no,
        account_id=account.id,
        currency="USD",
    )
    answer = first_bill.deposit_line_for(data, account_type_id=account.account_type_id)
    lines = [(line.kind, str(line.amount)) for line in answer.lines]
    return (
        f"{account.account_no}: size {account.deposit_size_class} · first-bill deposit lines {lines} "
        f"· asked {answer.deposit_asked} · already paid {answer.deposit_already_paid}"
    )


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    core_tenancy.set_current_tenant(tenant.id)
    dana = identity_models.User.objects.get(tenant_id=tenant.id, email="dana@brazosbendutilities.com")
    actor = SimpleNamespace(id=dana.id, pk=dana.id, role="system_admin", roles=("system_admin",), is_authenticated=True)
    unit = Unit.objects.get(tenant_id=tenant.id, unit_no="SCW-U-353")
    deferred = customer_models.Account.objects.filter(unit_id=unit.id, deposit_size_class="W-2").first()
    if deferred is None:
        created = customer_services.create_account(
            actor,
            {
                "unit_id": str(unit.id),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-10-04",
                "contact": {"full_name": "Ben Ortiz"},
                "customer": {"display_name": "Ben Ortiz", "kind": "person", "identity": {"phone": "+1 (281) 555-0177"}},
                "deposit": {"decision": "required", "amount": "600.00", "size_class": "W-2", "take_now": False},
            },
        )
        print(f"created {created['account_no']} deposit {created['deposit']}")
        deferred = customer_models.Account.objects.get(pk=created["id"])
    print(line_for(deferred))
    print(line_for(customer_models.Account.objects.get(tenant_id=tenant.id, account_no="AC-2026-00054")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
