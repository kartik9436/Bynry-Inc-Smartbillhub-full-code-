#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   DS-INVOICES — the `invoices` dataset query's COST, on real
#           PostgreSQL 16. Brief §8.2 (p91, read as an image per B14 rule 42):
#           *"the left path never fetches more than a page; the right path
#           never holds one."*
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           CLAUDE.md hard-won law 14 (`config/settings/test.py` hardcodes
#           in-memory SQLite and ignores `DATABASE_URL`, so the suite CANNOT
#           see a `LIMIT` — on twenty rows a LIMIT and a Python slice are the
#           same two numbers).
# ───────────────────────────────────────────────────────
"""HOW MUCH THE `invoices` DATASET COSTS, MEASURED AND NOT ESTIMATED.

Run it against a proof-db clone, never against a database somebody is using:

    PROOF_DB_PYTHON=06-backend/.venv/bin/python \\
      10-scripts/proof-db.sh clone dsinv --template sbh_tpl_dsinv --export
    eval "$(…)"
    06-backend/.venv/bin/python 10-scripts/ds_invoices_cost.py --seed 40000
    06-backend/.venv/bin/python 10-scripts/ds_invoices_cost.py --measure

⚠ **THE COMPARISON THAT MATTERS IS PAGE ONE AGAINST THE LAST PAGE.** A read
that pages in SQL costs the same at both ends of the book; a read that pages in
Python costs the whole book at both ends and looks fine on page one. Reporting
only page one is a measurement that cannot fail.

⚠ **AND THE SECOND ONE IS THE PAGE AGAINST THE STREAM.** The page must read a
page whatever the tenant's size; the stream must read every row. A stream that
quietly stopped at a page would report a *faster* time and a wrong file.

Median of three after a discarded warm-up, the shape `cr138_p4_debtor_cost.py`
established, because a first run pays for a cold cache and a first run is not
what a clerk gets.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django

django.setup()

from apps.billing import models as billing_models
from apps.billing import reporting
from core import tenancy as core_tenancy
from django.db import connection, reset_queries

UTC = timezone.utc
START = date(2026, 1, 1)
END = date(2026, 12, 31)


def _tenant():
    from apps.tenancy.models import Tenant

    row = Tenant.objects.using("default").first()
    if row is None:
        raise SystemExit("no tenant in this database — clone a seeded template")
    return row


def seed(count: int) -> None:
    """`count` ISSUED bills, each with three lines, on ONE existing account.

    One account on purpose: this measures the DATASET's cost, and spreading the
    book over 40,000 accounts would measure the customers seam's batched name
    read instead. The name read is bounded by the PAGE either way, which is the
    property being proved.
    """
    from apps.customers import models as customer_models

    tenant = _tenant()
    with core_tenancy.tenant_context(tenant.id):
        account = customer_models.Account.objects.first()
        if account is None:
            raise SystemExit("no account in this database")
        base_no = billing_models.Invoice.objects.count()
        bulk: list[billing_models.Invoice] = []
        for index in range(count):
            amount = Decimal(f"{10 + (index % 400)}.0000")
            bulk.append(
                billing_models.Invoice(
                    tenant=tenant,
                    account=account,
                    invoice_no=f"BM-{base_no + index + 1:08d}",
                    bill_type="cycle",
                    status=billing_models.INVOICE_ISSUED,
                    service_date=START + timedelta(days=index % 360),
                    period_start=START + timedelta(days=index % 360),
                    period_end=START + timedelta(days=(index % 360) + 27),
                    due_date=END,
                    issued_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
                    + timedelta(days=index % 360),
                    subtotal=amount,
                    tax_total=Decimal("2.0000"),
                    total=amount + Decimal("2.0000"),
                    currency="USD",
                    payload_version=1,
                )
            )
            if len(bulk) >= 2000:
                billing_models.Invoice.objects.bulk_create(bulk)
                _lines(tenant, account, bulk)
                bulk = []
                print(f"  seeded {index + 1}/{count}", flush=True)
        if bulk:
            billing_models.Invoice.objects.bulk_create(bulk)
            _lines(tenant, account, bulk)
        print(f"total invoices now {billing_models.Invoice.objects.count()}")


def _lines(tenant, account, invoices) -> None:
    rows = []
    for invoice in invoices:
        rows.append(
            billing_models.InvoiceLine(
                tenant=tenant,
                invoice=invoice,
                account=account,
                kind="base",
                description="Base charge",
                amount=Decimal("10.0000"),
            )
        )
        rows.append(
            billing_models.InvoiceLine(
                tenant=tenant,
                invoice=invoice,
                account=account,
                kind="usage",
                description="Electric usage 684 kWh",
                quantity=Decimal(684),
                unit="kWh",
                amount=invoice.subtotal - Decimal("10.0000"),
            )
        )
        rows.append(
            billing_models.InvoiceLine(
                tenant=tenant,
                invoice=invoice,
                account=account,
                kind="tax",
                description="Tax",
                amount=Decimal("2.0000"),
            )
        )
    billing_models.InvoiceLine.objects.bulk_create(rows)


def _timed(label: str, call, *, repeats: int = 3) -> None:
    call()  # warm-up, DISCARDED — a first run pays for a cold cache.
    samples = []
    statements = 0
    for _ in range(repeats):
        reset_queries()
        started = time.perf_counter()
        result = call()
        samples.append(time.perf_counter() - started)
        statements = len(connection.queries)
    print(f"  {label:<44} {statistics.median(samples):7.3f}s  {statements:>4} statements  {result}")


def measure() -> None:
    tenant = _tenant()
    with core_tenancy.tenant_context(tenant.id):
        total = billing_models.Invoice.objects.filter(
            status__in=reporting.REGISTER_STATUSES
        ).count()
        lines = billing_models.InvoiceLine.objects.count()
        per = 50
        last = max(1, -(-total // per))
        print(f"tenant {tenant.id} · {total} issued bills · {lines} invoice lines · {per}/page")

        _timed(
            "page 1",
            lambda: len(
                reporting.invoices_dataset(start=START, end=END, page=1, per=per)["rows"]
            ),
        )
        _timed(
            f"last page ({last})",
            lambda: len(
                reporting.invoices_dataset(start=START, end=END, page=last, per=per)["rows"]
            ),
        )
        _timed(
            "page 1, sorted by amount desc",
            lambda: len(
                reporting.invoices_dataset(
                    start=START, end=END, page=1, per=per, sort="amount", direction="desc"
                )["rows"]
            ),
        )
        _timed(
            "page 1, searched",
            lambda: len(
                reporting.invoices_dataset(
                    start=START, end=END, page=1, per=per, search="BM-0000"
                )["rows"]
            ),
        )
        _timed(
            "the whole file, streamed",
            lambda: sum(
                1 for _ in reporting.invoices_dataset_stream(start=START, end=END)
            ),
            repeats=1,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("set DATABASE_URL to a proof-db CLONE — never a shared database")
    if args.seed:
        seed(args.seed)
    if args.measure:
        measure()
