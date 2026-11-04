"""imp2_walk_prep — four accounts and two payments files, for the Q6/Q7 walk.

Decision log 2026-10-30 *"Eight open payment questions answered (PO)"*: Q6 (the
store network's name from a column in the file) and Q7 (save the column layout
as a template; next week's file with the same headers maps itself).

Creates, in the seeded demo tenant, four accounts on fresh units, then writes
into OUT (default `/tmp/imp2-walk`):

    week1.csv  Store Acct · Paid · Txn Date · Receipt · Network
               two lockbox rows ($100.00, $50.00, Network empty) and two Hy-Vee
               rows ($253.00, $60.00, Network = Hy-Vee), all dated 2026-10-29
    week2.csv  the SAME header row, two new Hy-Vee receipts — for Q7's second
               upload, which should be mapped by the saved template

Walk database only — never a shared or demo database:

    DATABASE_URL=postgres://…/sbh python 10-scripts/imp2_walk_prep.py
"""

from __future__ import annotations

import csv
import importlib.util
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

_spec = importlib.util.spec_from_file_location(
    "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
)
sjf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sjf)  # type: ignore[union-attr]

HEADERS = ["Store Acct", "Paid", "Txn Date", "Receipt", "Network"]


def main() -> int:
    sjf.django_setup()
    from django.db import transaction

    from apps.customers import models as customer_models
    from core import tenancy as core_tenancy
    from tests.test_us_met_helpers import make_premises, make_unit

    out = Path(os.environ.get("OUT", "/tmp/imp2-walk"))
    out.mkdir(parents=True, exist_ok=True)
    tenant, actor = sjf.tenant_and_actor()
    numbers = []
    with core_tenancy.tenant_context(tenant.id), transaction.atomic():
        for n in range(6):
            premises = make_premises(
                actor, address_line=f"{4100 + n} Hy-Vee Walk Ln", services_available=["electric"]
            )
            unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
            account = customer_models.Account.objects.create(
                tenant=tenant,
                unit_id=unit["id"],
                status=customer_models.AccountStatus.objects.filter(
                    tenant=tenant, code="active"
                ).first()
                or customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
                account_type=customer_models.AccountType.objects.first(),
                account_no=f"HV-{uuid.uuid4().hex[:6].upper()}",
            )
            numbers.append(account.account_no)
    week1 = [
        [numbers[0], "100.00", "2026-10-29", "CHK-4101", ""],
        [numbers[1], "50.00", "2026-10-29", "CHK-4102", ""],
        [numbers[2], "253.00", "2026-10-29", "HV-1029-0006", "Hy-Vee"],
        [numbers[3], "60.00", "2026-10-29", "HV-1029-0007", "Hy-Vee"],
    ]
    week2 = [
        [numbers[4], "41.25", "2026-10-29", "HV-1029-0101", "Hy-Vee"],
        [numbers[5], "18.00", "2026-10-29", "HV-1029-0102", "Hy-Vee"],
    ]
    for name, rows in (("week1.csv", week1), ("week2.csv", week2)):
        with open(out / name, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(rows)
    print("accounts:", ", ".join(numbers))
    print("files:", out / "week1.csv", out / "week2.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
