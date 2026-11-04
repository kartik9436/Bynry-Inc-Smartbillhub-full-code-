# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) — the draft that survives a closed tab ·
#           US-CWP-014 — the recorded paperless consent · US-CWP-015 — the
#           quick-service cards read from the tenant's own list.
#           Screens: CWP-047 · CWP-009 · CWP-010
# Rules:    BR-CWP-087 / CR-068 R5 (paperless is a recorded consent — a
#           timestamp, the wording version, and a way to withdraw) ·
#           03-field-map.md §1 `portal_consent` (⚠ *"May never be in the
#           future"* on `agreed_on`) · BR-CUS-093 (a service request is
#           NUMBERED at creation — which is why the draft is its own table) ·
#           CLAUDE.md hard rule 1 (RLS follows in 0004) · law 14 (the
#           future-date CHECK exists on PostgreSQL and the proof is
#           PostgreSQL-only)
# Tests:    06-backend/tests/test_us_cwp_013_about_you.py ·
#           test_us_cwp_014_check_and_send.py ·
#           test_us_cwp_014_pg.py (the constraint, on PostgreSQL 16)
# Impacts:  apps/portal/models.py · apps/portal/applications.py ·
#           apps/portal/services.py · migrations/0004_rls_consent_and_draft.py
# ───────────────────────────────────────────────────────
"""portal 0003 — two tables and one column.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

THE ONE THING IN HERE THAT IS NOT ORDINARY DDL
----------------------------------------------
`ck_portal_consent_agreed_on_not_future` is a database CHECK that a consent
cannot be dated after the moment it is written. It is added by RAW SQL under a
`RunPython` that answers only on PostgreSQL, and it has to be, for a reason
worth stating rather than discovering:

  * `now()` is not `IMMUTABLE`, so Django's `CheckConstraint` cannot express
    it and PostgreSQL will not accept it inside `ADD CONSTRAINT … CHECK` as a
    plain expression — it is accepted only because `now()` is `STABLE` and
    PostgreSQL permits a STABLE function in a CHECK when it is written this
    way. The constraint is therefore evaluated per statement, which is exactly
    what *"never in the future"* means at the moment of the write.
  * **SQLite, which the default suite runs on (CLAUDE.md law 14), has no such
    state and would accept the row.** A green suite is not evidence here. The
    proof is `tests/test_us_cwp_014_pg.py`, which runs only against real
    PostgreSQL and asserts the refusal in the database's own words.

`ck_portal_consent_wording_version_present` is the other half and holds on
every engine: a consent without the version of the words is not a consent.

⚠ **SUPERSEDED THE SAME DAY BY `portal 0005` (DEF-CWP-3709): `now()` IS THE
WRONG CLOCK.** In PostgreSQL `now()` is the TRANSACTION'S start time and never
moves again, so a consent written later in the same transaction than the work
before it — which is exactly what the submit does — was refused, on every
honest submit, in the browser. `portal 0005` rebuilds the same constraint name
around `clock_timestamp()`, the wall clock, which is what *"never in the
future"* meant all along. The DDL below is left exactly as it was applied; the
repair is a new migration, never an edit to this one.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone

from core.dbfields import uuid7_pk

#: The CHECK a Django `CheckConstraint` cannot express — see the docstring.
AGREED_ON_NOT_FUTURE = (
    "ALTER TABLE portal_consent ADD CONSTRAINT ck_portal_consent_agreed_on_not_future "
    "CHECK (agreed_on <= now());"
)
DROP_AGREED_ON_NOT_FUTURE = (
    "ALTER TABLE portal_consent DROP CONSTRAINT IF EXISTS ck_portal_consent_agreed_on_not_future;"
)


def add_future_check(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(AGREED_ON_NOT_FUTURE)


def drop_future_check(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_AGREED_ON_NOT_FUTURE)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_rls_portal_settings"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalsettings",
            name="quick_service_categories",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="PortalApplicationDraft",
            fields=[
                ("id", uuid7_pk()),
                ("token", models.TextField()),
                ("address_as_given", models.TextField(blank=True, null=True)),
                ("address_unit_as_given", models.TextField(blank=True, null=True)),
                ("matched_premises_id", models.UUIDField(blank=True, null=True)),
                ("service_codes", models.JSONField(blank=True, default=list)),
                ("applicant_kind", models.TextField(blank=True, null=True)),
                ("first_name", models.TextField(blank=True, null=True)),
                ("last_name", models.TextField(blank=True, null=True)),
                ("company_name", models.TextField(blank=True, null=True)),
                ("email", models.TextField(blank=True, null=True)),
                ("phone", models.TextField(blank=True, null=True)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("tax_id", models.TextField(blank=True, null=True)),
                ("requested_start", models.DateField(blank=True, null=True)),
                ("service_request_id", models.UUIDField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "portal_application_drafts",
            },
        ),
        migrations.CreateModel(
            name="PortalConsent",
            fields=[
                ("id", uuid7_pk()),
                ("account_id", models.UUIDField(blank=True, null=True)),
                ("service_request_id", models.UUIDField(blank=True, null=True)),
                ("kind", models.TextField(default="paperless")),
                ("wording_version", models.TextField()),
                ("agreed_on", models.DateTimeField(default=timezone.now)),
                ("withdrawn_on", models.DateTimeField(blank=True, null=True)),
                ("taken_on_screen", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "portal_consent",
            },
        ),
        migrations.AddConstraint(
            model_name="portalapplicationdraft",
            constraint=models.UniqueConstraint(
                fields=("tenant", "token"), name="uq_portal_application_drafts_token"
            ),
        ),
        migrations.AddIndex(
            model_name="portalapplicationdraft",
            index=models.Index(
                fields=["tenant", "token"], name="ix_portal_app_drafts_token"
            ),
        ),
        migrations.AddConstraint(
            model_name="portalconsent",
            constraint=models.CheckConstraint(
                condition=~models.Q(wording_version=""),
                name="ck_portal_consent_wording_version_present",
            ),
        ),
        migrations.AddIndex(
            model_name="portalconsent",
            index=models.Index(
                fields=["tenant", "service_request_id"], name="ix_portal_consent_request"
            ),
        ),
        migrations.RunPython(add_future_check, drop_future_check),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-013@d6d31c46 · US-CWP-014@d6d31c46 · US-CWP-015@d6d31c46 (EP-CWP-04 + 03-field-map.md §1 snapshot)
# generated: 2026-09-04 by the CR-068 wave C build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · migrate on PostgreSQL 16 and on the SQLite suite · tests/test_us_cwp_014_pg.py
# exceptions: the future-date CHECK is PostgreSQL-only and SQLite would accept the row — law 14 names this exact shape, and the test that proves it skips rather than passes on SQLite
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
