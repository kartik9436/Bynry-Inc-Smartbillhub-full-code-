#!/usr/bin/env python3
"""cr190_movein_messages_readback — what the walk's move-in actually queued.

CR-190-BRC10 lane MOVEIN-MSG. Run after `cr190_movein_messages_walkthrough.mjs`
on the SAME private walk database:

    DATABASE_URL=postgres://…/sbh_moveinmsg_walk \
        python3 10-scripts/cr190_movein_messages_readback.py [tenant-slug]

Prints the newest move-in's welcome rows (channel, template, version) and the
welcome RENDERED from its pinned version and stored context — the body a
customer would read — plus whether the unticked service agreement was queued
and the audit row that records the untick. Reads only; writes nothing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.audit import models as audit_models  # noqa: E402
from apps.notifications import models as nm  # noqa: E402
from apps.notifications import rendering  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "brazosbend"
    code = sys.argv[2] if len(sys.argv) > 2 else "email_welcome"
    tenant = tm.Tenant.objects.get(subdomain=slug)
    with core_tenancy.tenant_context(tenant.id):
        latest = (
            nm.OutboundMessage.objects.filter(tenant_id=tenant.id, template_code=code)
            .order_by("-created_at")
            .first()
        )
        if latest is None:
            print("no welcome queued")
            return 1
        rows = nm.OutboundMessage.objects.filter(
            tenant_id=tenant.id, source_type="move", source_id=latest.source_id
        )
        for row in rows:
            print(f"queued: {row.template_code} on {row.channel} (v{row.template_version})")
        agreement = nm.OutboundMessage.objects.filter(
            tenant_id=tenant.id,
            account_id=latest.account_id,
            template_code="contract_service_agreement",
        ).count()
        print(f"service agreement rows for this account: {agreement}")
        audit = (
            audit_models.AuditLog.objects.filter(
                tenant_id=tenant.id, action="move_in.default_message_changed"
            )
            .order_by("-created_at")
            .first()
        )
        print(f"audit: {audit.after if audit else None}")
        artifact = rendering.render_for_dispatch(latest)
        print("\n── subject ──")
        print(artifact.subject)
        print("── body ──")
        print(artifact.body)
        print(f"── absences: {len(artifact.absences)} · dash present: {rendering.ABSENT_MARK in artifact.body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
