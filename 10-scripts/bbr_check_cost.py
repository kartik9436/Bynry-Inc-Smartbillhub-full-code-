#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B27
#           step 1 (*"measure ms/account before and after"*) · changes row 55
# Rulings:  decision log 2026-09-30 — *"BULK CHECK BATCH SIZE = 500 ACCOUNTS"*
#           and *"PRODUCTION SCALES BILLING WORKERS THROUGH INFRASTRUCTURE"*
# Findings: 04-docs/05-modules/07-billing/19-check-cost-measured.md
# Rules:    CLAUDE.md hard rule 1 (every read inside tenant_context, on a role
#           that RLS FORCE applies to) · hard-won law 7 (a check that measures
#           nothing must say so) · law 14 (real PostgreSQL, never SQLite)
# Pattern:  10-scripts/cr138_p4_debtor_cost.py (median of 3 after a discarded
#           warm-up; an execute_wrapper counter, never connection.queries) ·
#           10-scripts/cr051_run_benchmark.py (the within-tenant clone)
# ───────────────────────────────────────────────────────
"""WHAT THE BULK CHECK COSTS PER ACCOUNT, AND WHERE THE STATEMENTS GO.

A MEASUREMENT, NOT A FIXTURE AND NOT A TEST. It changes no product code. It
answers B27 step 1: how many milliseconds and how many SQL statements one
account costs the bulk Check (`check_store.check_run`) today, which of those
statements are the same read asked once per account, and what would be left
if each such read were asked once per batch of 500.

THREE SUBCOMMANDS
-----------------
``seed``     Builds the population on a tenant provisioned through the REAL
             signup service with electric + water + sewer + trash and the
             sample plant (`provision_tenant` + `run_provisioning_plant`, the
             `cr081_seed_sewer_utility.py` path). ONE sample account is the
             TEMPLATE; through the product's own helpers it gets a SECOND
             water meter and a Sep 30 reading on every meter (the
             `seed_j72_bulk_run.py` helpers: `a_meter`, `commit_read`). It
             then CLONES that account's whole subtree — unit, service points,
             meters and their assignments, plan assignment, account, service
             agreements, readings, its issued bills and their lines, its
             payments and their allocations — into a dedicated cycle
             (`B27-COST`), until the cycle holds N accounts. Idempotent: it
             tops up, never doubles.
``measure``  For each size, tops the cycle up to N, then times
             `check_store.check_run` over the whole cycle: one DISCARDED
             warm-up, then the MEDIAN of ``--repeat`` runs. Every run is the
             full job body — the per-account savepoints, the engine, and the
             write of each account's saved result.
``profile``  Checks ONE account and then TEN (`only_accounts`), recording
             every statement with the Python frame that issued it, and prints
             the per-account statements grouped by the read they come from,
             each group's DB time, and whether its SQL is IDENTICAL for every
             account (a pass-wide answer) or differs only by the account's own
             ids (a read one `IN (...)` per batch of 500 could answer).

WHY A CLONE AND NOT 5,000 PASSES THROUGH THE SERVICES
----------------------------------------------------
`cr051_run_benchmark.py` says it and it is still true: seeding 5,000 accounts
through the service layer takes longer than the measurement. The PRICED world
is real — the tenant's own plans, rate schedules, charge codes, taxes and
settings, resolved through the same seams — and so is the template's history
(its August bill was issued by the sample plant's real bill run, its payments
were recorded by the payments service). What is synthetic is the COUNT, which
is the variable being measured. **A clone is not a fixture and must never be
used as one.** Its fidelity is CHECKED rather than assumed: `seed` prints the
template's Check findings beside the first clone's, and `profile` compares
their statement counts; a clone that checks differently from its template is
a different world and the script says so.

⚠ WHAT WOULD MAKE THIS PASS WRONGLY — each answered, not assumed
-----------------------------------------------------------------
* **Measuring nothing.** A superuser or BYPASSRLS role ignores RLS FORCE and a
  role with no `app.tenant_id` sees zero rows in a microsecond. The script
  refuses a bypassing role (exit 2) and refuses a cycle holding 0 accounts
  (exit 2); every line it prints carries the account count it measured over.
* **A warm cache on one run and a cold one on another.** One discarded warm-up
  per size, then the median.
* **A per-pass cost read as a per-account cost.** `profile` measures one
  account and ten and reports the DIFFERENCE ÷ 9 as per-account; the rest is
  the pass's fixed cost (scope, summary counts), printed separately.
* **Django's 9,000-statement log cap.** Statements are counted by an
  `execute_wrapper`, never `connection.queries`, and DEBUG is off.

WHAT IT DOES NOT MEASURE: HTTP, the job queue, and concurrency — one process,
one connection. The machine is shared with other lanes; `measure` prints the
load average beside every figure, and the STATEMENT counts are the figures
that do not depend on it.

USAGE (real PostgreSQL 16, a role subject to RLS)
    cd 06-backend && export DJANGO_SETTINGS_MODULE=config.settings.local \\
        DATABASE_URL=postgres://sbh_b27:sbh_b27@127.0.0.1:55433/sbh_b27cost
    python ../10-scripts/bbr_check_cost.py seed --count 100
    python ../10-scripts/bbr_check_cost.py measure --sizes 100 1000 5000 --repeat 3
    python ../10-scripts/bbr_check_cost.py profile
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import traceback
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.apps import apps as django_apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

settings.DEBUG = False  # no connection.queries log: it caps at 9,000 and costs memory

from core import tenancy as core_tenancy  # noqa: E402
from core.dbfields import uuid7  # noqa: E402

SUBDOMAIN = "b27-cost"
PAYLOAD = {
    "name": "B27 Check Cost",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "B27 Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    "services": ["electric", "water", "sewer", "trash"],
    "load_defaults": True,
}
#: The sample plant's account with electric, water, trash (one cart) and sewer
#: on plan SCW-RES, an issued August bill and two payments.
TEMPLATE_NO = "AC-2026-00003"
SECOND_WATER = "W-B27-T2"
CYCLE_CODE = "B27-COST"
CLONE_PREFIX = "B27-"
PERIOD = (date(2026, 9, 1), date(2026, 9, 30))
BILL_DATE = date(2026, 10, 1)
DUE_DAYS = 21
BATCH = 500


# ── environment ──────────────────────────────────────────────────────────────
def _refuse_bypass() -> None:
    if connection.vendor != "postgresql":
        sys.exit("REFUSED: PostgreSQL only (hard-won law 14).")
    with connection.cursor() as cursor:
        cursor.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        superuser, bypass = cursor.fetchone()
    if superuser or bypass:
        print(
            "REFUSED: this role bypasses row-level security, so tenant_context scopes "
            "nothing and every figure would be RLS-free (DEF-2717, hard rule 1).",
            file=sys.stderr,
        )
        sys.exit(2)


def _load() -> str:
    try:
        return "load %.2f %.2f %.2f" % os.getloadavg()
    except OSError:
        return "load n/a"


def _tenant():
    from apps.tenancy import models as tm

    tenant = tm.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if tenant is not None:
        return tenant
    from apps.tenancy import sample_data
    from apps.tenancy import services as ts
    from core import jobs as core_jobs

    previous = core_jobs._dispatcher  # noqa: SLF001 — no broker in a dev database
    core_jobs.set_job_dispatcher(lambda _record: None)
    try:
        result = ts.provision_tenant(PAYLOAD)
    finally:
        core_jobs.set_job_dispatcher(previous)
    tenant = tm.Tenant.objects.get(pk=result["id"])
    plant = result.get("sample_plant")
    if plant is not None:
        with core_tenancy.tenant_context(str(tenant.id)):
            core_jobs.run_job(plant["job_id"], sample_data.run_provisioning_plant)
    return tenant


def _actor(tenant):
    from types import SimpleNamespace

    from apps.identity import models as im

    user = im.User.objects.filter(tenant=tenant).order_by("created_at").first()
    membership = (
        im.TenantMembership.objects.filter(tenant=tenant, user=user).select_related("role").first()
    )
    return SimpleNamespace(
        id=user.id, pk=user.id, user=user, email=user.email, role=membership.role.code
    )


def _model(table: str):
    for model in django_apps.get_models():
        if model._meta.db_table == table:
            return model
    raise LookupError(table)


# ── the template ─────────────────────────────────────────────────────────────
def ensure_template(tenant, actor):
    """The template account, given a second water meter and a Sep 30 reading
    on every meter through the product's own helpers (the J72 seed's)."""
    from apps.assets import models as am
    from apps.customers import models as cm
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    account = cm.Account.objects.get(tenant=tenant, account_no=TEMPLATE_NO)
    unit_id = str(account.unit_id)
    if not am.Asset.objects.filter(tenant=tenant, asset_no=SECOND_WATER).exists():
        a_meter(actor, asset_no=SECOND_WATER, service="water", uom="kgal", unit_id=unit_id)
    from apps.metering.models import MeterRead

    assigned = am.AssetAssignment.objects.filter(
        tenant=tenant, unit_id=unit_id, to_date__isnull=True
    ).select_related("asset")
    for row in assigned:
        asset = row.asset
        if asset.unit not in ("kWh", "kgal"):
            continue  # the trash cart is counted, not read
        reads = MeterRead.objects.filter(tenant=tenant, asset_id=asset.id, channel="total")
        if reads.filter(read_at=at("2026-09-30")).exists():
            continue
        last = reads.order_by("-read_at").first()
        if last is None:
            commit_read(actor, asset.id, day="2026-08-31", value="100", unit=asset.unit)
            prior = Decimal("100")
        else:
            prior = last.current_value
        step = Decimal("620") if asset.unit == "kWh" else Decimal("8")
        commit_read(
            actor,
            asset.id,
            day="2026-09-30",
            value=str(prior + step),
            prior_value=str(prior),
            consumption=str(step),
            unit=asset.unit,
        )
    return account


def ensure_cycle(tenant):
    from apps.metering import models as mm

    cycle, _ = mm.Cycle.objects.get_or_create(
        tenant=tenant,
        code=CYCLE_CODE,
        defaults={
            "name": "B27 check cost",
            "frequency": "Monthly",
            "start_day": 1,
            "days_to_complete": 30,
            "bill_day": 1,
            "due_days": DUE_DAYS,
            "first_run_date": date(2026, 9, 1),
        },
    )
    return cycle


# ── the clone ────────────────────────────────────────────────────────────────
def _clone(row, **overrides):
    """cr051_run_benchmark._clone: every concrete column, a fresh id."""
    fresh = row.__class__()
    for field in row._meta.concrete_fields:
        if field.primary_key:
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        setattr(fresh, field.attname, getattr(row, field.attname))
    fresh.id = uuid7()
    for name, value in overrides.items():
        setattr(fresh, name, value)
    fresh._state.adding = True
    return fresh


class Subtree:
    """The template's rows, read ONCE, that every clone copies."""

    def __init__(self, tenant, account, cycle):
        from apps.assets import models as am
        from apps.metering import models as mm
        from apps.metering.models import MeterRead
        from apps.rating import models as rm

        self.tenant_id = tenant.id
        self.cycle = cycle
        self.account = account
        self.unit = mm.Unit.objects.get(pk=account.unit_id)
        self.points = list(
            mm.ServicePoint.objects.filter(unit_id=self.unit.id, deleted_at__isnull=True)
        )
        self.assignments = list(
            am.AssetAssignment.objects.filter(
                unit_id=self.unit.id, to_date__isnull=True
            ).select_related("asset")
        )
        asset_ids = [a.asset_id for a in self.assignments]
        self.reads = list(MeterRead.objects.filter(asset_id__in=asset_ids))
        self.plan_rows = list(rm.UnitPlanAssignment.objects.filter(unit_id=self.unit.id))
        self.agreements = list(
            _model("service_agreements").objects.filter(account_id=account.id)
        )
        Invoice = _model("invoices")
        self.invoices = list(Invoice.objects.filter(account_id=account.id).exclude(status="draft"))
        inv_ids = [i.id for i in self.invoices]
        self.lines = list(_model("invoice_lines").objects.filter(invoice_id__in=inv_ids))
        self.payments = list(_model("payments").objects.filter(account_id=account.id))
        pay_ids = [p.id for p in self.payments]
        Allocation = _model("allocations")
        self.allocations = list(Allocation.objects.filter(payment_id__in=pay_ids))

    def shape(self) -> str:
        return (
            f"{len(self.points)} service points · {len(self.assignments)} meters/carts · "
            f"{len(self.reads)} readings · {len(self.invoices)} issued bills "
            f"({len(self.lines)} lines) · {len(self.payments)} payments "
            f"({len(self.allocations)} allocations) · {len(self.agreements)} agreements"
        )

    def write(self, index: int) -> None:
        tag = f"{CLONE_PREFIX}{index:06d}"
        unit = _clone(self.unit, unit_no=tag, label=f"B27 {index}", external_ref=None)
        unit.save(force_insert=True)
        points = {}
        for point in self.points:
            fresh = _clone(point, unit_id=unit.id, cycle_id=self.cycle.id, route_id=None)
            fresh.save(force_insert=True)
            points[point.id] = fresh.id
        assets = {}
        for n, assignment in enumerate(self.assignments):
            asset = _clone(
                assignment.asset,
                asset_no=f"{tag}-{n}",
                serial_no=f"{tag}-{n}",
                external_ref=None,
                service_point_id=points.get(assignment.asset.service_point_id),
            )
            asset.save(force_insert=True)
            assets[assignment.asset_id] = asset.id
            _clone(assignment, unit_id=unit.id, asset_id=asset.id).save(force_insert=True)
        for row in self.plan_rows:
            _clone(row, unit_id=unit.id).save(force_insert=True)
        account = _clone(self.account, unit_id=unit.id, account_no=tag)
        account.save(force_insert=True)
        for agreement in self.agreements:
            sp = points.get(agreement.service_point_id)
            if sp is None:
                continue
            _clone(agreement, account_id=account.id, service_point_id=sp).save(force_insert=True)
        for read in self.reads:
            fresh = _clone(
                read,
                asset_id=assets[read.asset_id],
                account_id=None if read.account_id is None else account.id,
                superseded_by_id=None,
            )
            fresh.save(force_insert=True)
        invoices = {}
        for invoice in self.invoices:
            fresh = _clone(
                invoice,
                account_id=account.id,
                invoice_no=None if invoice.invoice_no is None else f"{invoice.invoice_no}-{tag}",
                corrects_invoice_id=None,
            )
            fresh.save(force_insert=True)
            invoices[invoice.id] = fresh.id
        for line in self.lines:
            overrides = {"invoice_id": invoices[line.invoice_id]}
            if hasattr(line, "service_point_id") and line.service_point_id in points:
                overrides["service_point_id"] = points[line.service_point_id]
            _clone(line, **overrides).save(force_insert=True)
        payments = {}
        for payment in self.payments:
            fresh = _clone(
                payment,
                account_id=account.id,
                payment_no=None if payment.payment_no is None else f"{payment.payment_no}-{tag}",
                webhook_key=None if payment.webhook_key is None else f"{payment.webhook_key}-{tag}",
            )
            fresh.save(force_insert=True)
            payments[payment.id] = fresh.id
        for allocation in self.allocations:
            _clone(
                allocation,
                payment_id=payments[allocation.payment_id],
                invoice_id=invoices.get(allocation.invoice_id, allocation.invoice_id),
            ).save(force_insert=True)


def _population(tenant, cycle) -> list[Any]:
    from apps.customers import models as cm

    return list(
        cm.Account.objects.filter(tenant=tenant, account_no__startswith=CLONE_PREFIX)
        .order_by("account_no")
        .values_list("id", flat=True)
    )


def top_up(tenant, cycle, subtree: Subtree, count: int) -> int:
    have = len(_population(tenant, cycle))
    started = time.monotonic()
    for index in range(have + 1, count + 1):
        with transaction.atomic():
            subtree.write(index)
        if index % 500 == 0:
            print(f"    cloned {index:,} ({time.monotonic() - started:.0f}s)", flush=True)
    return max(have, count)


# ── the run and the pass ─────────────────────────────────────────────────────
def the_run(cycle):
    from apps.billing import models as bm
    from apps.billing import runs

    run = bm.BillRun.objects.filter(
        cycle=cycle, period_start=PERIOD[0], period_end=PERIOD[1], parent_run__isnull=True
    ).first()
    return run or runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD[0],
        period_end=PERIOD[1],
        bill_date=BILL_DATE,
        due_days=DUE_DAYS,
        label="B27 check cost",
    )


class _Counter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


def _findings_of(run, account_id) -> list[str]:
    from apps.billing import check_models

    return sorted(
        check_models.BillRunFinding.objects.filter(bill_run=run, account_id=account_id)
        .values_list("code", flat=True)
    )


# ── seed ─────────────────────────────────────────────────────────────────────
def cmd_seed(args) -> int:
    from apps.billing import check_store

    tenant = _tenant()
    with core_tenancy.tenant_context(str(tenant.id)):
        actor = _actor(tenant)
        with transaction.atomic():
            account = ensure_template(tenant, actor)
            cycle = ensure_cycle(tenant)
        subtree = Subtree(tenant, account, cycle)
        print(f"template {TEMPLATE_NO}: {subtree.shape()}")
        total = top_up(tenant, cycle, subtree, args.count)
        print(f"cycle {CYCLE_CODE} holds {total:,} cloned accounts")
        # Fidelity: the template checked in its OWN cycle, the first clone in B27.
        from apps.metering import models as mm

        own_cycle = mm.Cycle.objects.get(pk=subtree.points[0].cycle_id)
        own_run = the_run(own_cycle)
        check_store.check_run(own_run, only_accounts=[account.id])
        first = _population(tenant, cycle)[0]
        run = the_run(cycle)
        check_store.check_run(run, only_accounts=[first])
        mine, theirs = _findings_of(own_run, account.id), _findings_of(run, first)
        print(f"template's findings    : {mine}  (its own cycle {own_cycle.code})")
        print(f"first clone's findings : {theirs}  (cycle {CYCLE_CODE})")
        if mine != theirs:
            print("⚠ FIDELITY: the clone checks differently from its template.")
            return 1
    return 0


# ── measure ──────────────────────────────────────────────────────────────────
def cmd_measure(args) -> int:
    from apps.billing import check_store

    tenant = _tenant()
    record = []
    with core_tenancy.tenant_context(str(tenant.id)):
        account = ensure_template(tenant, _actor(tenant))
        cycle = ensure_cycle(tenant)
        subtree = Subtree(tenant, account, cycle)
        for size in args.sizes:
            have = len(_population(tenant, cycle))
            if have > size and args.subset:
                # ⚠ A cycle that has already grown past `size` cannot shrink:
                # the clones carry issued bills and payments, which hard rule 4
                # forbids deleting. `--subset` checks the FIRST `size` accounts
                # through `only_accounts` — the same per-account work (the
                # engine, the savepoints, the save), and the pass's fixed part
                # (scope over the whole cycle) paid once per run as before. It
                # is printed on the RESULT line, so the figure says what it is.
                subset = _population(tenant, cycle)[:size]
                run = the_run(cycle)
                print(f"  N={size:,} of {have:,} (subset): warm-up (discarded) … {_load()}", flush=True)
                check_store.check_run(run, only_accounts=subset)
                timings, statements = [], 0
                for attempt in range(args.repeat):
                    counter = _Counter()
                    started = time.monotonic()
                    with connection.execute_wrapper(counter):
                        summary = check_store.check_run(run, only_accounts=subset)
                    timings.append(time.monotonic() - started)
                    statements = counter.count
                    print(
                        f"    run {attempt + 1}: {timings[-1]:.1f}s · {counter.count:,} statements · {_load()}",
                        flush=True,
                    )
                median = statistics.median(timings)
                row = {
                    "accounts": size,
                    "subset_of": have,
                    "seconds": round(median, 3),
                    "ms_per_account": round(1000 * median / size, 1),
                    "statements": statements,
                    "statements_per_account": round(statements / size, 1),
                    "runs": [round(t, 3) for t in timings],
                }
                record.append(row)
                print(f"  RESULT {json.dumps(row)}", flush=True)
                continue
            if have > size:
                print(f"  SKIP {size:,}: the cycle already holds {have:,} (populations only grow)")
                continue
            top_up(tenant, cycle, subtree, size)
            n = len(_population(tenant, cycle))
            if n == 0:
                print("REFUSED: the cycle holds 0 accounts — this would measure nothing.")
                return 2
            run = the_run(cycle)
            # ⚠ `--warmup-accounts` exists for the 5,000 size only, where one
            # full pass is ~an hour: the warm-up's job is the connection and the
            # plan cache, which one batch of 500 pays as fully as 5,000 do. It is
            # printed on the line, so a reader knows which warm-up a figure had.
            if args.warmup_accounts and args.warmup_accounts < n:
                warm = _population(tenant, cycle)[: args.warmup_accounts]
                print(
                    f"  N={n:,}: warm-up on the first {len(warm):,} accounts (discarded) … {_load()}",
                    flush=True,
                )
                check_store.check_run(run, only_accounts=warm)
            else:
                print(f"  N={n:,}: warm-up (discarded) … {_load()}", flush=True)
                check_store.check_run(run)
            timings, statements = [], 0
            for attempt in range(args.repeat):
                counter = _Counter()
                started = time.monotonic()
                with connection.execute_wrapper(counter):
                    summary = check_store.check_run(run)
                timings.append(time.monotonic() - started)
                statements = counter.count
                print(
                    f"    run {attempt + 1}: {timings[-1]:.1f}s · {counter.count:,} statements · "
                    f"{summary.get('accounts')} checked · {_load()}",
                    flush=True,
                )
            median = statistics.median(timings)
            row = {
                "accounts": n,
                "seconds": round(median, 3),
                "ms_per_account": round(1000 * median / n, 1),
                "statements": statements,
                "statements_per_account": round(statements / n, 1),
                "tiles": {k: summary.get(k) for k in ("ready", "decisions", "blocked", "silent")},
                "runs": [round(t, 3) for t in timings],
            }
            record.append(row)
            print(f"  RESULT {json.dumps(row)}", flush=True)
    if len(record) >= 2:
        xs = [r["accounts"] for r in record]
        ys = [r["seconds"] for r in record]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        fixed = my - slope * mx
        print(f"\n  fit: {fixed:.1f}s fixed + {1000 * slope:.1f} ms/account")
        for n in (1_000, 10_000, 40_000):
            secs = fixed + slope * n
            print(f"    {n:>6,} accounts ≈ {secs / 60:.1f} min on one worker")
    return 0


# ── profile ──────────────────────────────────────────────────────────────────
_TABLE = re.compile(r'(?:FROM|INTO|UPDATE)\s+"?([a-z0-9_]+)"?', re.I)
_APPS = str(BACKEND / "apps") + os.sep


class _Recorder:
    """Every statement with its SQL, params, DB time and the frame that asked."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def __call__(self, execute, sql, params, many, context):
        stack = [f for f in traceback.extract_stack() if f.filename.startswith(_APPS)]
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed = time.perf_counter() - started
            self.rows.append(
                {
                    "sql": sql,
                    "params": repr(params),
                    "params_raw": None if many else params,
                    "ms": elapsed * 1000,
                    "origin": _origin(stack),
                    "stage": _stage(stack),
                    "table": _table(sql),
                }
            )


def _short(frame) -> str:
    rel = frame.filename[len(_APPS):].removesuffix(".py").replace(os.sep, ".")
    return f"{rel}.{frame.name}"


def _origin(stack) -> str:
    """The innermost product frame, skipping the billing seam plumbing, so a
    read is named by the module that OWNS it (`metering.derivation.…`)."""
    skip = ("billing/gather.py:_resolve", "billing/seam_batch.py")
    for frame in reversed(stack):
        where = f"{frame.filename[len(_APPS):]}:{frame.name}"
        if any(where.startswith(s) for s in skip):
            continue
        return _short(frame)
    return "?"


_ENGINE = ("billing/check_engine.py", "billing/check_store.py")
#: Frames that only WRAP a check (the guard, the account savepoint): the stage
#: is then named by the function they called, one frame in.
_WRAPPERS = ("<lambda>", "run", "_check_all", "check_account", "on_account")


def _stage(stack) -> str:
    """Which step of the Check asked: the innermost check_engine/check_store
    frame, or — when that frame is only the guard's lambda — the function it
    called (`billing.gather.gather_account`, `billing.runs.readings_for_account`,
    `billing.midperiod.gather_split` …)."""
    last = None
    for index, frame in enumerate(stack):
        if frame.filename.endswith(_ENGINE):
            last = index
    if last is None:
        for frame in reversed(stack):
            if frame.filename.endswith("billing/runs.py"):
                return f"runs.{frame.name}"
        return "?"
    name = stack[last].name
    if name in _WRAPPERS and last + 1 < len(stack):
        return _short(stack[last + 1])
    return name


def _table(sql: str) -> str:
    head = sql.lstrip()[:12].upper()
    if head.startswith(("SAVEPOINT", "RELEASE", "ROLLBACK")):
        return "(savepoint)"
    found = _TABLE.search(sql)
    return found.group(1) if found else head.split()[0].lower()


#: Which kind of fact a table holds — the families the B27 findings are
#: grouped by. A table not named here prints as itself.
FAMILY = {
    "meter_reads": "readings",
    "rate_tiers": "plan / rate schedule",
    "tariff_versions": "plan / rate schedule",
    "rate_size_rows": "plan / rate schedule",
    "rate_plans": "plan / rate schedule",
    "plan_services": "plan / rate schedule",
    "plan_rate_schedules": "plan / rate schedule",
    "unit_plan_assignments": "plan / rate schedule",
    "discount_versions": "plan / rate schedule",
    "plan_discount_rules": "plan / rate schedule",
    "discount_enrolments": "plan / rate schedule",
    "charges": "charge codes",
    "charge_code_amounts": "charge codes",
    "taxes": "taxes",
    "plan_tax_rules": "taxes",
    "tax_exemption_certificates": "taxes",
    "assets": "meters (assets)",
    "asset_assignments": "meters (assets)",
    "service_points": "service points / units",
    "services": "service points / units",
    "tenant_services": "service points / units",
    "units": "service points / units",
    "service_agreements": "agreements",
    "invoices": "previous bills",
    "invoice_lines": "previous bills",
    "payments": "payments",
    "allocations": "payments",
    "contacts": "customer",
    "disconnect_cases": "customer",
    "accounts": "customer",
    "bill_run_account_checks": "saving the result",
    "bill_run_findings": "saving the result",
    "audit_log": "audit",
    "(savepoint)": "savepoints",
}


def _own_ids(account_id) -> set[str]:
    """Every id in the account's subtree: account, unit, points, assets, bills, payments."""
    from apps.assets import models as am
    from apps.customers import models as cm
    from apps.metering import models as mm

    account = cm.Account.objects.get(pk=account_id)
    ids = {str(account.id), str(account.unit_id)}
    ids |= {str(i) for i in mm.ServicePoint.objects.filter(unit_id=account.unit_id).values_list("id", flat=True)}
    ids |= {str(i) for i in am.AssetAssignment.objects.filter(unit_id=account.unit_id).values_list("asset_id", flat=True)}
    ids |= {str(i) for i in _model("invoices").objects.filter(account_id=account.id).values_list("id", flat=True)}
    ids |= {str(i) for i in _model("payments").objects.filter(account_id=account.id).values_list("id", flat=True)}
    ids |= {str(i) for i in _model("meter_reads").objects.filter(asset_id__in=[x for x in ids]).values_list("id", flat=True)}
    return {i for i in ids if i and i != "None"} | {account.account_no}


def cmd_profile(args) -> int:
    from apps.billing import check_store

    tenant = _tenant()
    with core_tenancy.tenant_context(str(tenant.id)):
        cycle = ensure_cycle(tenant)
        population = _population(tenant, cycle)
        if len(population) < args.k:
            print(f"REFUSED: {len(population)} accounts; seed at least {args.k}.")
            return 2
        run = the_run(cycle)
        chosen = population[: args.k]
        check_store.check_run(run, only_accounts=chosen[:1])  # warm-up, discarded
        one, many = _Recorder(), _Recorder()
        t0 = time.monotonic()
        with connection.execute_wrapper(one):
            check_store.check_run(run, only_accounts=chosen[:1])
        t1 = time.monotonic()
        with connection.execute_wrapper(many):
            check_store.check_run(run, only_accounts=chosen)
        t2 = time.monotonic()
        k = len(chosen)
        per_ms = 1000 * ((t2 - t1) - (t1 - t0)) / (k - 1)
        per_st = (len(many.rows) - len(one.rows)) / (k - 1)
        print(f"accounts profiled: 1 and {k} · {_load()}")
        print(f"  1 account : {len(one.rows):,} statements · {1000 * (t1 - t0):.0f} ms")
        print(f"  {k} accounts: {len(many.rows):,} statements · {1000 * (t2 - t1):.0f} ms")
        print(f"  per account (difference ÷ {k - 1}): {per_st:.1f} statements · {per_ms:.1f} ms")
        print(f"  fixed per pass: {len(one.rows) - per_st:.1f} statements")
        # B27 — what the batch reads did on the K pass (counts only).
        from apps.billing import batch_seams
        from core import batch_reads

        print(f"  batch loaders: {batch_seams.LAST}")
        asked = batch_reads.last_counts().get("asked") or {}
        print(f"  reads still asked in the batch: {sum(asked.values())} over {len(asked)} reads")

        # Group both passes by (stage, origin, table). The per-account share of
        # a group is (count in the K pass − count in the 1 pass) ÷ (K − 1).
        def grouped(rows):
            out = defaultdict(list)
            for row in rows:
                out[(row["stage"], row["origin"], row["table"])].append(row)
            return out

        g1, gk = grouped(one.rows), grouped(many.rows)
        owns = [_own_ids(a) for a in chosen]

        def blank(row) -> str:
            text = row["sql"] + " " + row["params"]
            for ids in owns:
                for one_id in ids:
                    if one_id in text:
                        text = text.replace(one_id, "<id>")
            return text

        table = []
        for key, rows in gk.items():
            base = g1.get(key, [])
            per = (len(rows) - len(base)) / (k - 1)
            ms = (sum(r["ms"] for r in rows) - sum(r["ms"] for r in base)) / (k - 1)
            raw = {r["sql"] + " " + r["params"] for r in rows}
            blanked = {blank(r) for r in rows}
            in_one = {r["sql"] + " " + r["params"] for r in base}
            c1 = max(len(base), 1)
            # SAME: all K accounts asked the identical statements — a pass-wide
            # answer (plan, tariff, tax, charge code). OWN IDS: the same question
            # about each account's own rows — one IN (...) per batch answers it.
            if len(raw) <= c1:
                kind = "same for every account"
            elif len(blanked) <= c1:
                kind = "own ids (batchable)"
            else:
                kind = "varies"
            table.append(
                {
                    "stage": key[0],
                    "origin": key[1],
                    "table": key[2],
                    "family": FAMILY.get(key[2], key[2]),
                    "per_account": round(per, 2),
                    "db_ms_per_account": round(ms, 3),
                    "in_one_account": len(base),
                    "distinct_in_one_account": len(in_one),
                    "distinct_k_pass": len(raw),
                    "distinct_blanked": len(blanked),
                    "kind": kind,
                    "example": rows[0]["sql"][:400],
                }
            )
        table.sort(key=lambda r: -r["per_account"])
        print("\n  per-account statements by read — (K pass − 1 pass) ÷ (K − 1):")
        print(f"  {'/acct':>6} {'db ms':>7} {'1-acct asks/distinct':>20}  kind · stage · origin · table")
        for row in table:
            if row["per_account"] <= 0:
                continue
            print(
                f"  {row['per_account']:>6.1f} {row['db_ms_per_account']:>7.2f} "
                f"{row['in_one_account']:>12}/{row['distinct_in_one_account']:<7} "
                f"{row['kind']} · {row['stage']} · {row['origin']} · {row['table']}",
                flush=True,
            )
        families: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for row in table:
            if row["per_account"] > 0:
                families[row["family"]][0] += row["per_account"]
                families[row["family"]][1] += row["db_ms_per_account"]
        print("\n  by family (statements / DB ms per account):")
        for name, (st, fms) in sorted(families.items(), key=lambda kv: -kv[1][0]):
            print(f"    {st:>6.1f}  {fms:>7.2f} ms  {name}")
        db_total = sum(r["db_ms_per_account"] for r in table if r["per_account"] > 0)
        print(
            f"\n  DB time per account: {db_total:.1f} ms of {per_ms:.1f} ms wall "
            "(this wall INCLUDES the recorder's stack walk; `measure` has the clean figure)"
        )
        if args.explain:
            # The plan of the SLOWEST statement actually issued in each of the
            # costliest groups — the statement itself, never a hand-written proxy
            # (cr138_p4_debtor_cost.py's `_SqlRecorder` lesson).
            costly = sorted(
                (r for r in table if r["per_account"] > 0),
                key=lambda r: -r["db_ms_per_account"],
            )[: args.explain]
            for row in costly:
                key = (row["stage"], row["origin"], row["table"])
                worst = max(gk[key], key=lambda r: r["ms"])
                if worst["params_raw"] is None or not worst["sql"].lstrip().upper().startswith("SELECT"):
                    continue
                with connection.cursor() as cursor:
                    cursor.execute(
                        "explain (analyze, buffers) " + worst["sql"], worst["params_raw"]
                    )
                    plan = "\n".join("      " + line[0] for line in cursor.fetchall())
                print(f"\n  EXPLAIN · {row['origin']} ({worst['ms']:.2f} ms when issued):\n{plan}")
        if args.json:
            Path(args.json).write_text(
                json.dumps(
                    {
                        "k": k,
                        "per_account_statements": per_st,
                        "per_account_ms": per_ms,
                        "one_pass_statements": len(one.rows),
                        "k_pass_statements": len(many.rows),
                        "groups": table,
                        "families": dict(families),
                    },
                    indent=1,
                )
            )
            print(f"  wrote {args.json}")
    return 0


# ── race ─────────────────────────────────────────────────────────────────────
def cmd_race(args) -> int:
    """PROVE, on PostgreSQL, what a batch load of a money fact does TODAY.

    The Check already loads ONE read per batch of 500: the payment facts
    (`CheckContext.load_payment_facts`, before the batch's first account). An
    account's saved result is stamped `checked_at` when it is SAVED, and the
    staleness sweep re-checks an account only for a payment changed AFTER that
    stamp (`check_staleness.stale_account_ids`). So a payment recorded after the
    batch loaded its facts and before a later account of that batch is saved
    is in NEITHER: the saved findings miss it and the sweep never flags it.

    This checks three accounts of the template's own cycle (a separate run
    from `measure`'s), records a payment posted Oct 1 (after the Sep 30
    cut-off, before the Oct 1 bill date — the J72 Hannah Lee case) on the THIRD
    account the moment the FIRST is saved, then prints the third account's saved
    findings and the sweep's stale list. It writes one payment per run, on an
    account that has none from this script yet.
    """
    from datetime import UTC, datetime

    from apps.billing import check_staleness, check_store
    from apps.customers import models as cm
    from apps.metering import models as mm
    from apps.payments import models as pm
    from apps.payments import services as psvc

    tenant = _tenant()
    with core_tenancy.tenant_context(str(tenant.id)):
        actor = _actor(tenant)
        template = cm.Account.objects.get(tenant=tenant, account_no=TEMPLATE_NO)
        cycle = mm.Cycle.objects.get(
            pk=mm.ServicePoint.objects.filter(unit_id=template.unit_id).first().cycle_id
        )
        run = the_run(cycle)
        marked = set(
            pm.Payment.objects.filter(confirmation__startswith="B27-RACE").values_list(
                "account_id", flat=True
            )
        )
        pool = list(
            cm.Account.objects.filter(tenant=tenant, account_no__startswith="AC-2026-")
            .exclude(pk=template.pk)
            .order_by("account_no")
        )
        victims = [a for a in pool if a.id not in marked]
        if len(victims) < 3:
            print("REFUSED: no three unmarked accounts left in the template's cycle.")
            return 2
        first, _second, third = victims[:3]
        ids = [first.id, _second.id, third.id]
        fired = []

        def on_progress(done, account_no):
            if done == 1 and not fired:
                psvc.record_payment(
                    actor.user,
                    account_id=third.id,
                    amount=Decimal("120.0000"),
                    posted_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
                    confirmation=f"B27-RACE-{third.account_no}",
                    memo="B27 race proof: paid after the cut-off, mid-batch",
                )
                fired.append(datetime.now(UTC))

        check_store.check_run(run, only_accounts=ids, on_progress=on_progress)
        saved = _findings_of(run, third.id)
        stale = check_staleness.stale_account_ids(run)
        print(f"payment recorded on {third.account_no} at {fired[0].isoformat() if fired else '—'}")
        print(f"  its saved findings : {saved}")
        print(f"  sweep says stale   : {str(third.id) in stale}")
        check_store.check_run(run, only_accounts=[third.id])
        print(f"  a fresh check finds: {_findings_of(run, third.id)}")
        missed = "paid_after_cutoff" not in " ".join(saved) and str(third.id) not in stale
        print(
            "RACE REPRODUCED: the batch's payment facts missed a payment and the sweep "
            "will never flag it." if missed else "not reproduced"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    seed = sub.add_parser("seed")
    seed.add_argument("--count", type=int, default=100)
    measure = sub.add_parser("measure")
    measure.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 5000])
    measure.add_argument("--repeat", type=int, default=3)
    measure.add_argument("--warmup-accounts", type=int, default=0)
    measure.add_argument(
        "--subset", action="store_true", help="measure a size smaller than the cycle via only_accounts"
    )
    profile = sub.add_parser("profile")
    profile.add_argument("--k", type=int, default=10)
    profile.add_argument("--json", default=None)
    profile.add_argument("--explain", type=int, default=0, help="EXPLAIN the N costliest groups")
    sub.add_parser("race")
    args = parser.parse_args()
    _refuse_bypass()
    return {"seed": cmd_seed, "measure": cmd_measure, "profile": cmd_profile, "race": cmd_race}[
        args.cmd
    ](args)


if __name__ == "__main__":
    sys.exit(main())
