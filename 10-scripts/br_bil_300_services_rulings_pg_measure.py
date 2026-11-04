#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Rulings: PO 2026-09-30 (decision log, top seven rows) — build plan B1 · B2 ·
#          B3 · B5 · B6 · B8 · DB1 (04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md, task T2).
# Rules:   BR-BIL-300 · BR-BIL-301 · BR-BIL-1048 · BR-RAT-1015 · BR-RAT-090 ·
#          CLAUDE.md law 14 (money paths proved on real PostgreSQL 16, never
#          only on the SQLite default).
# ───────────────────────────────────────────────────────
"""THE 2026-09-30 SERVICES RULINGS, END TO END ON REAL POSTGRESQL 16.

    DATABASE_URL=postgres://… DJANGO_SETTINGS_MODULE=config.settings.local \\
        python 10-scripts/br_bil_300_services_rulings_pg_measure.py provision
    …  all --label after          # every account gathered + priced, one JSON
    …  compare before after       # which accounts moved, and by how much
    …  two-meters                 # a 2nd in-service water meter + its read
    …  sewer-no-point             # the account's sewer point soft-deleted
    …  meter-detached             # electric's meter detached (the seed sells no gas)

**`two-meters`, `sewer-no-point` and `meter-detached` run through
`runs.calculate_account` — the stage-6 writer — and then read `invoices` and
`invoice_lines` back with SQL, inside ONE transaction that is ROLLED BACK at
the end**, so the seeded tenant is unchanged between commands and `all` can be
re-run to compare. The rows are read before the rollback, which is the only
moment they exist; that is enough to prove the partitioned table accepted the
new `asset_id` column and what landed in it.

`all` prices every account WITHOUT writing (`runs.price_account`), exactly as
`def_bil_6759_zero_line_measure.py` does. Run it with the lane's base code on
`PYTHONPATH` for `--label before` and with this worktree for `--label after`,
then `compare`: every moved account must be explained by one of the rulings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(os.environ.get("BACKEND") or Path(__file__).resolve().parent.parent / "06-backend")
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from django.core.management import call_command  # noqa: E402
from django.db import connection, transaction  # noqa: E402

from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = os.environ.get("TENANT", "svc930")
OUT = Path(os.environ.get("OUTDIR", "/tmp/claude-0/svc930"))
PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)

PAYLOAD = {
    "name": "SVC930 Utility",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "SVC930 Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    "services": ["electric", "water", "sewer", "trash", "fire"],
    "load_defaults": True,
}


class Rollback(Exception):
    """Raised on purpose to roll a measurement's writes back."""


def provision():
    existing = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if existing is not None:
        print(f"tenant {SUBDOMAIN} already exists — reusing it")
        return existing
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(lambda _record: None)
    try:
        result = tenancy_services.provision_tenant(PAYLOAD)
    finally:
        core_jobs.set_job_dispatcher(previous)
    tenant = tenancy_models.Tenant.objects.get(pk=result["id"])
    plant = result.get("sample_plant")
    if plant is not None:
        with core_tenancy.tenant_context(str(tenant.id)):
            from apps.tenancy import sample_data as tenancy_sample_data

            core_jobs.run_job(plant["job_id"], tenancy_sample_data.run_provisioning_plant)
    print(f"provisioned {SUBDOMAIN}")
    call_command("seed_demo", tenant=SUBDOMAIN)
    call_command("load_sample_data", tenant=SUBDOMAIN)
    return tenant


def _money(value):
    return format(Decimal(str(value)).quantize(Decimal("0.0001")), "f")


def _gather(account):
    from apps.billing import gather as gather_mod
    from apps.billing import runs

    readings, _ = runs.readings_for_account(
        account,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        scope_services=None,
        anchor_to_last_billed=True,
    )
    return gather_mod.gather_account(
        account=account,
        service_date=PERIOD_END,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=(PERIOD_END - PERIOD_START).days + 1,
        readings=readings,
    )


def price(account) -> dict:
    from apps.billing import gather as gather_mod
    from apps.billing import runs

    try:
        data = _gather(account)
        priced = runs.price_account(data)
    except gather_mod.GatherProblem as problem:
        return {"outcome": "refused", "reason": str(getattr(problem, "reason", "")),
                "detail": str(problem)[:400]}
    except Exception as exc:  # noqa: BLE001 — recorded, never hidden
        return {"outcome": "error", "reason": type(exc).__name__, "detail": str(exc)[:400]}
    return {
        "outcome": "priced",
        "total": _money(priced.priced.total),
        "unconnected": list(getattr(data, "unconnected_services", ()) or ()),
        "warnings": [w.get("key") for w in getattr(priced, "warnings", ()) or ()],
        "lines": [
            [str(line.service or ""), str(line.description or ""), _money(line.amount),
             str(getattr(line, "asset_id", None) or "")]
            for line in priced.priced.lines
        ],
    }


def draft(account) -> dict:
    """Stage 6 for real — `calculate_account` — then the rows read back by SQL."""
    from apps.billing import runs

    data = _gather(account)
    invoice = runs.calculate_account(data, service_date=PERIOD_END, bill_type="interim")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tableoid::regclass::text, kind, description, amount, asset_id "
            "FROM invoice_lines WHERE invoice_id = %s ORDER BY kind, description, asset_id",
            [str(invoice.id)],
        )
        rows = cursor.fetchall()
    services = (invoice.bill_payload or {}).get("services") or []
    return {
        "invoice_no": invoice.invoice_no,
        "total": _money(invoice.total),
        "partition_rows": [
            [part, kind, desc, _money(amount), str(asset or "")]
            for part, kind, desc, amount, asset in rows
        ],
        "snapshot_services": [[s.get("code"), s.get("asset_id")] for s in services],
        "unconnected": list(data.unconnected_services),
    }


def _accounts(tenant):
    from apps.customers import models as customer_models

    return list(customer_models.Account.objects.filter(tenant_id=tenant.id).order_by("account_no"))


def _points(tenant, account, code):
    from apps.metering import models as metering_models

    return list(
        metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id, unit_id=account.unit_id, service__code=code,
            deleted_at__isnull=True,
        )
    )


def _first_priced_with(tenant, services: set[str], needs_asset: str | None = None):
    from apps.assets import selectors as asset_selectors

    # `getattr` so the SAME script runs under the lane's base code (which has
    # no in-service read) for the before-figures.
    in_service = getattr(
        asset_selectors,
        "in_service_asset_ids_for_service_point",
        asset_selectors.asset_ids_for_service_point,
    )
    for account in _accounts(tenant):
        if account.unit_id is None:
            continue
        if not all(_points(tenant, account, code) for code in services):
            continue
        water = _points(tenant, account, "water")
        if water and not in_service(water[0].id):
            continue
        if needs_asset and not asset_selectors.asset_ids_for_service_point(
            _points(tenant, account, needs_asset)[0].id
        ):
            continue
        result = price(account)
        if result["outcome"] == "priced":
            return account, result
    raise SystemExit(f"no priced account with {sorted(services)}")


def two_meters(tenant) -> dict:
    """A SECOND in-service water meter on the same point, with its own read."""
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models

    account, before = _first_priced_with(tenant, {"water"})
    point = _points(tenant, account, "water")[0]
    meter = asset_models.Asset.objects.filter(tenant_id=tenant.id, service_point_id=point.id).first()
    read = (
        metering_models.MeterRead.objects.filter(
            tenant_id=tenant.id, asset_id=meter.id,
            read_at__date__gte=PERIOD_START, read_at__date__lte=PERIOD_END,
        )
        .order_by("-read_at", "-id")
        .first()
    )
    assert read is not None, "the seeded meter has no read in the period"
    second = asset_models.Asset.objects.get(pk=meter.pk)
    second.pk = None
    second.id = None
    second.asset_no = f"{meter.asset_no}-B"
    for field in ("serial_no", "serial_number", "external_id"):
        if hasattr(second, field) and getattr(second, field):
            setattr(second, field, f"{getattr(second, field)}-B")
    second.save()
    for assignment in asset_models.AssetAssignment.objects.filter(
        tenant_id=tenant.id, asset_id=meter.id, to_date__isnull=True
    ):
        assignment.pk = None
        assignment.id = None
        assignment.asset_id = second.id
        assignment.save()
    # `meter_reads` has a COMPOSITE primary key (tenant_id, read_at, id), so
    # `pk = None` would blank the partition key too — the row is rebuilt from
    # its concrete field values with a new id and the second meter instead.
    import uuid

    values = {
        field.attname: getattr(read, field.attname)
        for field in metering_models.MeterRead._meta.concrete_fields
    }
    values.update(id=uuid.uuid4(), asset_id=second.id)
    metering_models.MeterRead.objects.create(**values)
    after = price(account)
    written = draft(account)
    return {"account_no": account.account_no, "meters": [str(meter.id), str(second.id)],
            "read_consumption": str(read.consumption), "before_second_meter": before,
            "priced": after, "draft": written}


def sewer_no_point(tenant) -> dict:
    """The account's SEWER point soft-deleted: sewer must follow water anyway."""
    from apps.metering import models as metering_models

    account, before = _first_priced_with(tenant, {"water", "sewer"})
    metering_models.ServicePoint.objects.filter(
        tenant_id=tenant.id, unit_id=account.unit_id, service__code="sewer"
    ).update(deleted_at=datetime.now(timezone.utc))
    after = price(account)
    return {"account_no": account.account_no, "with_sewer_point": before,
            "without_sewer_point": after, "draft": draft(account)}


def no_meter(tenant, code: str) -> dict:
    """A point whose meter/assets are DETACHED: not in service, no line, no refusal."""
    from apps.assets import models as asset_models

    account, before = _first_priced_with(tenant, {"water", code}, needs_asset=code)
    point = _points(tenant, account, code)[0]
    asset_models.Asset.objects.filter(tenant_id=tenant.id, service_point_id=point.id).update(
        service_point=None
    )
    return {"account_no": account.account_no, "service": code, "before": before,
            "after": price(account), "draft": draft(account)}


def compare(before: dict, after: dict) -> int:
    """Two counts, because a `$0.00` line removed moves no money and is still a
    change: MONEY/OUTCOME moved, and LINE SET moved with the money unchanged."""
    moved = 0
    lines_only: dict[tuple, int] = {}
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key, {}), after.get(key, {})
        if (b.get("outcome"), b.get("total")) == (a.get("outcome"), a.get("total")):
            bl = {tuple(x[:3]) for x in b.get("lines", [])}
            al = {tuple(x[:3]) for x in a.get("lines", [])}
            if bl != al:
                shape = (tuple(sorted(bl - al)), tuple(sorted(al - bl)))
                lines_only[shape] = lines_only.get(shape, 0) + 1
            continue
        moved += 1
        print(f"{key}: {b.get('outcome')} {b.get('total') or b.get('reason')} -> "
              f"{a.get('outcome')} {a.get('total') or a.get('reason')}  unconnected={a.get('unconnected')}")
        bl = {tuple(x[:3]) for x in b.get("lines", [])}
        al = {tuple(x[:3]) for x in a.get("lines", [])}
        for line in sorted(bl - al):
            print("     -", line)
        for line in sorted(al - bl):
            print("     +", line)
    print(f"{moved} of {len(set(before) | set(after))} accounts moved in money or outcome")
    for (removed, added), count in sorted(lines_only.items(), key=lambda kv: -kv[1]):
        print(f"{count} account(s), same total, lines removed={list(removed)} added={list(added)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["provision", "all", "compare", "two-meters",
                                        "sewer-no-point", "meter-detached", "fire-no-asset"])
    parser.add_argument("names", nargs="*")
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.cmd == "compare":
        before = json.loads((OUT / f"all_{args.names[0]}.json").read_text())
        after = json.loads((OUT / f"all_{args.names[1]}.json").read_text())
        return compare(before, after)
    if args.cmd == "provision":
        provision()
        return 0

    tenant = tenancy_models.Tenant.objects.get(subdomain=SUBDOMAIN)
    with core_tenancy.tenant_context(str(tenant.id)):
        if args.cmd == "all":
            records = {a.account_no: price(a) for a in _accounts(tenant)}
            (OUT / f"all_{args.label}.json").write_text(json.dumps(records, indent=1, sort_keys=True))
            summary: dict[str, int] = {}
            for record in records.values():
                summary[record["outcome"]] = summary.get(record["outcome"], 0) + 1
            print(args.label, len(records), "accounts", summary)
            return 0
        result: dict = {}
        try:
            with transaction.atomic():
                if args.cmd == "two-meters":
                    result = two_meters(tenant)
                elif args.cmd == "sewer-no-point":
                    result = sewer_no_point(tenant)
                elif args.cmd == "meter-detached":
                    result = no_meter(tenant, "electric")
                elif args.cmd == "fire-no-asset":
                    result = no_meter(tenant, "fire")
                raise Rollback
        except Rollback:
            pass
        (OUT / f"{args.cmd}.json").write_text(json.dumps(result, indent=1))
        print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
