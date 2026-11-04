"""tenancy 0002 — `user_preferences` (US-SHL-013 PROPOSED-SCHEMA, BR-SHL-024).
HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09;
row in 12-governance/09-human-review-ledger.md; not RATIFIED without human
sign-off.

Deliberately split out of 0001: the table FKs `users` (cross-module → identity,
the B2 §2 reviewed FK set), and B2 §7 orders tenancy BEFORE identity — so this
forward FK lands in a deferred second pass AFTER identity 0001, exactly the
B11 F-3 pattern for forward references. Hosted by tenancy because
platform-shell (doc module 0, the table's owner per US-SHL-013) has no Django
app — Eng disposition, flagged in the build report.

RLS for this table rides 0003_rls_w0_policies with the rest of the W0 set.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0001_initial"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("key", models.TextField()),
                ("value", models.JSONField()),
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
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "user_preferences",
            },
        ),
        migrations.AddConstraint(
            model_name="userpreference",
            constraint=models.UniqueConstraint(
                fields=("tenant", "user", "key"), name="uq_user_prefs"
            ),
        ),
    ]
