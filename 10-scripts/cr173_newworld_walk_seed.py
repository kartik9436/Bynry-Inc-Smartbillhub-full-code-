"""CR-173-BRC10 walkthrough seed — a New World connection and three online payments on
the demo utility, so the *Send to City folder* section and the runbook can be walked.

Run against a LOCAL database only (never a deployed one):

    DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgres://… \\
        python 10-scripts/cr173_newworld_walk_seed.py

It creates NO SFTP setting and NO password: the walkthrough types those on the
screen, against the in-process fake server (`06-backend/tests/fake_sftp_server.py`),
with the obviously fake password `test-password-not-real`.
Idempotent: a second run finds what the first made.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.customers import models as customer_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.integrations import models  # noqa: E402
from apps.integrations import services as integration_services  # noqa: E402
from apps.integrations.registry import REGISTRY  # noqa: E402
from apps.integrations.runners import serve  # noqa: E402
from apps.payments import idempotency  # noqa: E402
from apps.payments import services as payment_services  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services as runbook_services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import crypto  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TENANT = os.environ.get("WALK_TENANT", "brazosbend")
ADMIN = os.environ.get("WALK_ADMIN", "dana@brazosbendutilities.com")


class _Actor:
    def __init__(self, user):
        self.id = user.id
        self.user = user
        self.role = "system_admin"


tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT)
with core_tenancy.tenant_context(tenant.id):
    user = identity_models.User.objects.get(email=ADMIN)
    actor = _Actor(user)
    settings_row = tenancy_models.TenantSettings.objects.filter(tenant=tenant).first()
    zone = ZoneInfo(settings_row.timezone if settings_row and settings_row.timezone else "UTC")
    conn = models.IntegrationConnection.objects.filter(tenant=tenant, provider_key="erp_newworld").first()
    if conn is None:
        conn = models.IntegrationConnection.objects.create(
            tenant=tenant, provider_key="erp_newworld", label="New World / Logos",
            environment=models.ENVIRONMENT_PRODUCTION, status=models.STATUS_WORKING,
            enabled=True, cadence=models.CADENCE_MANUAL, config={},
        )
        integration_services.record_credential(
            actor=actor, connection=conn, payload="{}", masked_hint="••••WALK",
            blind_index=crypto.blind_index("sbh_walk_only_key", context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
            scope=[one.name for one in REGISTRY.require("erp_newworld").operations if one.they_call_us],
        )
    if not runbook_models.Runbook.objects.filter(tenant=tenant, key="newworld_receipt_push").exists():
        runbook_services.add_template(tenant.id, "newworld_receipt_push", actor_id=user.id)
    account = customer_models.Account.objects.filter(tenant=tenant).order_by("account_no").first()
    day = datetime.now(zone).date() - timedelta(days=2)
    for index, (hour, amount) in enumerate(((9, "42.18"), (14, "118.50"), (21, "63.07"))):
        at = datetime(day.year, day.month, day.day, hour, 5, tzinfo=zone)
        try:
            payment_services.record_payment(
                actor, account_id=account.id, amount=Decimal(amount), posted_at=at, cleared_at=at,
                method_code="check", idempotency_source=idempotency.SOURCE_WEBHOOK,
                idempotency_reference=f"cr173-walk-{day.isoformat()}-{index}",
            )
        except Exception as exc:  # noqa: BLE001 — a re-run finds the same reference
            print("payment", index, "not recorded:", type(exc).__name__)
    print(f"connection={conn.id} day_with_receipts={day.isoformat()} zone={zone}")
