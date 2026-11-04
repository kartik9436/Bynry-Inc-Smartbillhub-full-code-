#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 `P2.10` / `P2.11` — the fixture the browser walk needs.
# Rules:   CLAUDE.md hard-won law 6 (a rendered-output check needs a real,
#          seeded database) · hard rule 1 (tenant scoping) · `P0.6` (a deposit
#          batch is one till and one tender)
# ───────────────────────────────────────────────────────
"""Seed the four batch populations `P2.10` has to keep apart. Measurement only.

`P2.1` (`POST /counters`) is NOT STARTED, so nothing in the product opens a
till yet. This writes what `P2.1` will write — an open till and its batch — so
`P2.10` can be MEASURED against a real database rather than reasoned about.
It is a fixture, not a second path: the product's own code will replace it.

    legacy      session_id IS NULL   banked before tills existed  → must SHOW
    system      born closed          ACH, card, wire, lockbox     → must SHOW
    counted     a person sealed it   the phase's happy path       → must SHOW
    still open  closed_at IS NULL    a drawer taking money        → must be HELD

⚠ **THE LEGACY ROW GOES IN PAST `trg_deposit_batch_needs_session`**, which is
right: that trigger refuses a NEW batch with no session, and this row stands for
one written before the trigger existed. The trigger is disabled and re-enabled
around the single INSERT, in its own transaction each time — `ALTER TABLE`
inside the same transaction as the INSERT fails with *"pending trigger events"*.

Run it against a clone nobody else is seeding:

    10-scripts/proof-db.sh clone p2wire
    DATABASE_URL=postgres://…/sbh_clone_p2wire python3 10-scripts/p2_10_11_seed_tills.py
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
from decimal import Decimal

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from core import tenancy as core_tenancy  # noqa: E402

from apps.identity import models as identity_models  # noqa: E402
from apps.payments import bankrec_models as bankrec  # noqa: E402
from apps.payments import counter_session_models as tills  # noqa: E402
from apps.payments import models as pay  # noqa: E402
from apps.payments import reconciliation  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import published_content_models as published  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")
DAY = dt.date.fromisoformat(os.environ.get("DAY", "2026-09-23"))


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT)
    with core_tenancy.tenant_context(tenant.pk):
        dana = identity_models.User.objects.get(email="dana@brazosbendutilities.com")
        sam = (
            identity_models.User.objects.filter(email="sam.reyes@sample.test").first()
            or dana
        )
        centre = published.ServiceCentre.objects.order_by("name").first()
        cash = tenancy_models.PaymentMethod.objects.get(code="cash")
        check = tenancy_models.PaymentMethod.objects.get(code="check")

        with transaction.atomic():
            open_till, _ = tills.CounterSession.objects.get_or_create(
                tenant_id=tenant.pk,
                owner=dana,
                closed_at=None,
                defaults=dict(
                    service_centre=centre,
                    opening_float=Decimal("200.0000"),
                    currency="USD",
                    opened_at=timezone.now() - dt.timedelta(hours=6),
                ),
            )
            open_batch, _ = bankrec.DepositBatch.objects.get_or_create(
                tenant_id=tenant.pk,
                session=open_till,
                method=cash,
                defaults=dict(
                    code="DEP-260923-9001",
                    deposited_on=DAY,
                    recorded_total=Decimal("612.5000"),
                    status=bankrec.BATCH_IN_TRANSIT,
                ),
            )

            closed_till = tills.CounterSession.objects.filter(
                tenant_id=tenant.pk, owner=sam, closed_at__isnull=False
            ).first()
            if closed_till is None:
                closed_till = tills.CounterSession.objects.create(
                    tenant_id=tenant.pk,
                    owner=sam,
                    service_centre=centre,
                    opening_float=Decimal("200.0000"),
                    currency="USD",
                    opened_at=timezone.now() - dt.timedelta(hours=9),
                    closed_at=timezone.now() - dt.timedelta(hours=1),
                    closed_by=sam,
                    close_kind=pay.COUNTER_CLOSE_COUNTED,
                    counted_totals={str(cash.pk): "884.0000"},
                    difference=Decimal("0.0000"),
                )
            closed_batch, _ = bankrec.DepositBatch.objects.get_or_create(
                tenant_id=tenant.pk,
                session=closed_till,
                method=cash,
                defaults=dict(
                    code="DEP-260923-9002",
                    deposited_on=DAY,
                    recorded_total=Decimal("884.0000"),
                    status=bankrec.BATCH_IN_TRANSIT,
                ),
            )

            system_till = reconciliation._system_session(tenant_id=tenant.pk, day=DAY)
            system_batch, _ = bankrec.DepositBatch.objects.get_or_create(
                tenant_id=tenant.pk,
                session=system_till,
                method=check,
                defaults=dict(
                    code="DEP-260923-9003",
                    deposited_on=DAY,
                    recorded_total=Decimal("1284.6000"),
                    status=bankrec.BATCH_IN_TRANSIT,
                ),
            )

        legacy = bankrec.DepositBatch.objects.filter(
            tenant_id=tenant.pk, code="DEP-260808-CHK-LEGACY"
        ).first()
        if legacy is None:
            _insert_legacy(tenant.pk, cash.pk)

        print(
            f"open till    {open_till.pk} closed_at={open_till.closed_at} -> {open_batch.code}"
        )
        print(
            f"closed till  {closed_till.pk} {closed_till.close_kind} -> {closed_batch.code}"
        )
        print(
            f"system till  {system_till.pk} {system_till.close_kind} -> {system_batch.code}"
        )
        print("legacy batch DEP-260808-CHK-LEGACY (session_id IS NULL)")
    return 0


def _insert_legacy(tenant_id, method_id) -> None:
    """One session-less batch, past the trigger that refuses NEW ones.

    Three separate transactions on purpose: `ALTER TABLE … ENABLE TRIGGER` in
    the same transaction as the INSERT is refused with *"cannot ALTER TABLE
    because it has pending trigger events"*, and the whole thing then rolls
    back leaving the trigger DISABLED — which is worse than not seeding at all.
    """
    name = "trg_deposit_batch_needs_session"
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE deposit_batches DISABLE TRIGGER {name}")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO deposit_batches (
                    id, tenant_id, code, session_id, method_id, recorded_total,
                    bank_total, status, deposited_on, created_at, updated_at)
                VALUES (gen_random_uuid(), %s, 'DEP-260808-CHK-LEGACY', NULL, %s,
                        4400.000000, NULL, 'in_transit', DATE '2026-08-08', now(), now())
                """,
                [str(tenant_id), str(method_id)],
            )
    finally:
        # ALWAYS re-enable, even if the insert failed — a trigger left off is a
        # database that silently accepts the row P0.6 exists to refuse.
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE deposit_batches ENABLE TRIGGER {name}")


if __name__ == "__main__":
    raise SystemExit(main())
