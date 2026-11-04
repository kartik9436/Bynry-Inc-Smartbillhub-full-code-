"""Prepare a PRIVATE database copy for the Account age / Aging walk (2026-10-17).

`DEF-CUS-10180` (Account age) · `DEF-CUS-10181` (Aging reads bills). Run ONLY
against a throwaway copy (`createdb -T smartbillhub smartbillhub_accage`):

    DATABASE_URL=postgres://…/smartbillhub_accage \\
    DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/walk_account_age_2026_10_17_prep.py [--apply]

Without `--apply` it only LISTS the tenant's accounts (number, status, opened,
closed, ageing). With it, it shapes four accounts on the copy so the walk can
show each case the PO was shown: one closed, one pending activation (no Opened
date), one reopened on 10/14/2026, and one whose oldest unpaid bill is moved to
fall due 08/01/2026 (77 days before 10/17/2026). It refuses to touch a database
whose name does not end in `_accage`.
"""

from __future__ import annotations

import itertools
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django

django.setup()

from apps.customers import models as cm
from apps.customers import selectors
from apps.tenancy.models import Tenant
from core import tenancy
from django.conf import settings
from django.db import connection, transaction

TENANT = os.environ.get("TENANT", "brazosbend")


def main() -> int:
    name = settings.DATABASES["default"]["NAME"]
    apply = "--apply" in sys.argv
    if apply and not str(name).endswith("_accage"):
        print(f"refusing: database {name!r} is not a walk copy")
        return 2
    tenant = Tenant.objects.get(subdomain=TENANT)
    if "--csv" in sys.argv:
        # This sandbox has no DOCUMENT_STORAGE_BUCKET, so the export job builds
        # its file and then cannot PUBLISH it (refused by name, DEF-MET-4954).
        # This writes the same file through the kernel's own `row_stream` and
        # `write_csv`, so the bytes are the job's bytes.
        from zoneinfo import ZoneInfo

        from apps.customers import exports
        from apps.tenancy import exports as kernel
        from core.pagination import ListParams

        out = Path(sys.argv[sys.argv.index("--csv") + 1])
        with tenancy.tenant_context(tenant.id):
            resource = exports.ACCOUNTS
            params = ListParams(sort="account_age", dir="asc", per=50)
            columns = kernel.columns_for(resource)
            selection = resource.select(params)
            count = kernel.write_csv(
                out,
                [c.name for c in columns],
                kernel.row_stream(resource, selection, ZoneInfo("America/Chicago"), columns),
            )
        print(f"wrote {count} rows to {out}")
        return 0
    with tenancy.tenant_context(tenant.id):
        accounts = list(
            cm.Account.objects.filter(tenant_id=tenant.id)
            .select_related("status")
            .order_by("account_no")
        )
        ageing = selectors.ageing_segments_for([a.id for a in accounts])
        for a in accounts:
            print(
                f"{a.account_no:16} {a.status.code:20} opened={a.opened_at} "
                f"closed={a.closed_at} ageing={ageing.get(str(a.id))}"
            )
        if not apply:
            return 0
        from apps.billing import models as bm

        plan = [x for x in os.environ.get("SHAPE", "").split(",") if x]
        # SHAPE=closed:AC-1,pending:AC-2,reopened:AC-3,overdue:AC-4
        with transaction.atomic():
            for item in plan:
                kind, number = item.split(":", 1)
                account = cm.Account.objects.get(tenant_id=tenant.id, account_no=number)
                if kind == "closed":
                    account.closed_at = date(2026, 6, 30)
                    account.save(update_fields=["closed_at"])
                elif kind == "pending":
                    account.opened_at = None
                    account.status = cm.AccountStatus.objects.get(
                        tenant_id=tenant.id, code="pending_activation"
                    )
                    account.save(update_fields=["opened_at", "status"])
                elif kind == "reopened":
                    # The CR-181 reopen writes opened_at = the move-in date and
                    # clears closed_at; this reproduces its result on the copy.
                    account.opened_at = date(2026, 10, 14)
                    account.closed_at = None
                    account.save(update_fields=["opened_at", "closed_at"])
                elif kind == "overdue":
                    bill = (
                        bm.Invoice.objects.filter(
                            tenant_id=tenant.id, account_id=account.id, status="issued"
                        )
                        .order_by("due_date")
                        .first()
                    )
                    if bill is None:
                        print(f"{number}: no issued bill to date")
                        continue
                    # invoices are immutable after issue (hard rule 4) — on the
                    # COPY only, the trigger is bypassed for this one column.
                    with connection.cursor() as cur:
                        cur.execute("SET LOCAL session_replication_role = replica")
                        cur.execute(
                            "UPDATE invoices SET due_date = %s WHERE id = %s",
                            [date(2026, 8, 1), str(bill.id)],
                        )
                    print(f"{number}: bill {bill.invoice_no} due 2026-08-01")
                print(f"shaped {kind}: {number}")
        if "--import" in sys.argv:
            run_import(tenant)
    return 0


def run_import(tenant) -> None:
    """Import a two-row accounts file through the ONE runner on the copy: one
    row with an Opened date from the old system (03/01/2012, the tenant's own
    MM/DD/YYYY) and one dated in the future, which must be refused."""
    # The signed-in clerk WITH her own membership role (`require_role` reads
    # `actor.role`), the same posture as `seed_journey_fixture.tenant_and_actor`.
    import importlib.util

    from apps.metering import import_runs
    from apps.metering import models as mm

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", ROOT / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    sjf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sjf)
    _tenant, actor = sjf.tenant_and_actor()
    tenancy.set_current_tenant(tenant.id)  # the helper leaves no tenant set
    live = set(
        cm.Account.objects.filter(tenant_id=tenant.id, closed_at__isnull=True)
        .exclude(unit_id=None)
        .values_list("unit_id", flat=True)
    )
    free = [
        u for u in mm.Unit.objects.filter(tenant_id=tenant.id).order_by("unit_no")
        if u.id not in live and u.unit_no
    ]
    print(f"free units: {len(free)}")
    headers = "UNIT_REF,ACCT,NAME,TYPE,STATUS,OPENED,KIND,PHONE"
    mapping = {
        "UNIT_REF": "unit_ref", "ACCT": "account_no", "NAME": "customer_name",
        "TYPE": "account_type", "STATUS": "status", "OPENED": "opened_at",
        "KIND": "customer_kind", "PHONE": "phone",
    }
    for first, second in itertools.pairwise(free):
        content = (
            f"{headers}\n"
            f"{first.unit_no},A-2012-OLD,\"Harmon, Ruth\",residential,active,03/01/2012,person,+1 (512) 555-0171\n"
            f"{second.unit_no},A-FUTURE,\"Okafor, Ade\",residential,active,01/15/2027,person,+1 (512) 555-0172\n"
        )
        run = import_runs.extract(actor, {
            "target": import_runs.TARGET_ACCOUNTS, "source_kind": "file",
            "file_name": "legacy-accounts-2012.csv", "content": content,
            "session_ref": "walk_accage", "write_mode": "insert",
        })
        import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": {
            key: False for key in import_runs.ROW_HANDLING_KEYS}})
        import_runs.validate(actor, run["id"])
        rows = {r.row_no: r for r in mm.ImportRunRow.objects.filter(run_id=run["id"])}
        print(f"run {run['id']}: " + "; ".join(f"row {n} {r.outcome} {r.problem or ''}" for n, r in sorted(rows.items())))
        if rows[1].outcome == "staged":
            receipt = import_runs.load(actor, run["id"], {"write_mode": "insert", "approved": True})
            print(f"loaded: {receipt['counts']}")
            return
    print("no unit pair staged the good row")


if __name__ == "__main__":
    raise SystemExit(main())
