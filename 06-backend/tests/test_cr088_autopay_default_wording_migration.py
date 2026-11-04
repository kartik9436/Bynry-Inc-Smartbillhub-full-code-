"""CR-088 R.2 item 1 — existing utilities' saved auto-pay wording (notifications/0021).

PO 2026-10-02, verbatim: *"update it"* — option A as recommended: rewrite
"SMARTBillHub" → "SMART360 Next" in a utility's saved automatic-payment (ACH)
authorization ONLY where the stored text is still byte-identical to the seeded
default; an edited copy is left alone.

The worked case: Brazos Bend saved the platform's wording untouched, so its
template gains version 2 reading *"SMART360 Next gives you default wording …"*;
Lone Star Ridge added one sentence of its own, so its version 1 still says
SMARTBillHub and nothing is written for it. A second run writes nothing, and the
rollback removes exactly Brazos Bend's version 2.

The PostgreSQL cases skip by name on sqlite (hard-won law 14 — the savepoint and
RLS cannot be shown there). Run them the whole line:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://postgres@127.0.0.1:55433/<db>?sslmode=disable" \\
      pytest -q --reuse-db tests/test_cr088_autopay_default_wording_migration.py

WHAT WOULD MAKE THESE PASS WRONGLY (law 7): a migration that matched on
"contains SMARTBillHub" would rewrite Lone Star's edited copy too — the edited
case asserts its chain is still exactly one version. A migration that updated in
place would leave one version — the untouched case asserts TWO, the first still
reading the old words.
"""

from __future__ import annotations

import importlib
from datetime import date
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.audit.models import AuditLog
from apps.notifications import seed_templates, template_service
from apps.notifications import template_models as tm

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import staff_actor, tenant_ctx

MIGRATION = importlib.import_module(
    "apps.notifications.migrations.0021_cr088_autopay_default_wording"
)
CODE = "contract_autopay_authorization"


def _historical_apps():
    """The models AS THE MIGRATION SEES THEM — not the live ones, so a field the
    historical state lacks (the audit table's composite key, say) fails here."""
    return (
        MigrationExecutor(connection)
        .loader.project_state(("notifications", "0021_cr088_autopay_default_wording"))
        .apps
    )


EFFECTIVE = date(2026, 11, 1)


def test_the_frozen_new_wording_is_todays_seed_and_the_old_differs_by_one_sentence():
    assert MIGRATION.NEW_BODY == seed_templates.CONTRACT_AUTOPAY_PLACEHOLDER_BODY
    assert MIGRATION.OLD_BODY != MIGRATION.NEW_BODY
    assert MIGRATION.OLD_BODY.count("SMARTBillHub") == 1
    assert "SMARTBillHub" not in MIGRATION.NEW_BODY
    assert MIGRATION.OLD_BODY.replace("SMARTBillHub", "SMART360 Next") == MIGRATION.NEW_BODY


def _save(tenant, actor, body):
    with tenant_ctx(tenant):
        template, _ = template_service.register(
            code=CODE, name="Automatic payment authorization", actor=actor
        )
        template_service.save_draft(
            template=template, body=body, actor=actor, effective_from=EFFECTIVE
        )
        return template


def _chain(tenant, template):
    with tenant_ctx(tenant):
        return list(
            tm.NotificationTemplateVersion.objects.filter(template=template).order_by("version")
        )


def _ours_audited(tenant, action):
    with tenant_ctx(tenant):
        return [
            row
            for row in AuditLog.objects.filter(tenant_id=tenant.id, action=action)
            if (row.after or {}).get("source", "").startswith(MIGRATION.JOB)
        ]


@pytest.mark.django_db
@requires_postgres
def test_unedited_is_rewritten_edited_is_untouched_rerun_is_a_no_op_and_rollback_is_exact(
    brazos, lonestar, dana
):
    lone_admin = staff_actor(lonestar, "system_admin", "admin@lonestarridge.test")
    edited_body = MIGRATION.OLD_BODY + "\n\nCall our bank desk on Mondays."
    brazos_t = _save(brazos, dana, MIGRATION.OLD_BODY)
    lone_t = _save(lonestar, lone_admin, edited_body)

    editor = SimpleNamespace(connection=connection)
    MIGRATION.rewrite_unedited(_historical_apps(), editor)

    chain = _chain(brazos, brazos_t)
    assert [v.version for v in chain] == [1, 2]
    assert chain[0].body == MIGRATION.OLD_BODY  # history kept, not rewritten in place
    assert chain[1].body == MIGRATION.NEW_BODY
    assert chain[1].status == tm.VERSION_DRAFT
    assert chain[1].created_by is None  # "platform seed", never a person
    assert chain[1].effective_from == EFFECTIVE
    saved = _ours_audited(brazos, MIGRATION.AUDIT_SAVED)
    assert len(saved) == 1
    assert saved[0].after["changed_fields"] == ["body"]
    assert saved[0].after["changed_from_version"] == 1

    lone_chain = _chain(lonestar, lone_t)
    assert [v.body for v in lone_chain] == [edited_body]
    assert _ours_audited(lonestar, MIGRATION.AUDIT_SAVED) == []

    # A second run writes nothing anywhere.
    MIGRATION.rewrite_unedited(_historical_apps(), editor)
    assert [v.version for v in _chain(brazos, brazos_t)] == [1, 2]
    assert len(_chain(lonestar, lone_t)) == 1
    assert len(_ours_audited(brazos, MIGRATION.AUDIT_SAVED)) == 1

    # Rollback removes exactly the version it wrote, and only once.
    MIGRATION.remove_rewrites(_historical_apps(), editor)
    MIGRATION.remove_rewrites(_historical_apps(), editor)
    assert [(v.version, v.body) for v in _chain(brazos, brazos_t)] == [(1, MIGRATION.OLD_BODY)]
    assert [v.body for v in _chain(lonestar, lone_t)] == [edited_body]
    assert len(_ours_audited(brazos, MIGRATION.AUDIT_DELETED)) == 1


@pytest.mark.django_db
@requires_postgres
def test_a_draft_saved_on_top_of_ours_survives_the_rollback(brazos, dana):
    brazos_t = _save(brazos, dana, MIGRATION.OLD_BODY)
    editor = SimpleNamespace(connection=connection)
    MIGRATION.rewrite_unedited(_historical_apps(), editor)
    with tenant_ctx(brazos):
        template_service.save_draft(
            template=brazos_t,
            body=MIGRATION.NEW_BODY + "\n\nOur own line.",
            actor=dana,
            effective_from=EFFECTIVE,
        )
    MIGRATION.remove_rewrites(_historical_apps(), editor)
    assert [v.version for v in _chain(brazos, brazos_t)] == [1, 2, 3]
