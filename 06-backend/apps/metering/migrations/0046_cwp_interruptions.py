# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-008 (EP-CWP-03) — the interruption record. CR-068 wave B.
# Rules:    BR-CWP-027 (free-text location, nullable premises) · BR-CWP-012
#           (the record belongs to metering — B2 §2) · BR-TEN-035 (the `RP-`
#           reference, unique per tenant)
# Tests:    06-backend/tests/test_us_cwp_008_interruption.py ·
#           06-backend/tests/test_us_cwp_008_pg.py (RLS, on real PostgreSQL)
# Impacts:  apps/metering/interruptions.py · interruption_service.py ·
#           migrations/0047_rls_interruptions.py (the 🔒 policy half)
# ───────────────────────────────────────────────────────
"""metering 0046 — `interruptions`, the record nothing in this product held.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md (the row was
written on the day and named BOTH migrations; these two lines were not —
`DEF-CWP-3742`).

⚠ **AND THIS IS THE SECOND TIME THEY HAVE BEEN ADDED.** They landed at
`5cb4d970` and were removed by `5bfc2492`, a whole-file pathspec commit
from a base that predated them — the same commit, and the same mechanism,
that took `write_points.py`'s wave-E declaration with it and turned `G81`
red for the whole branch (`DEF-CWP-3754`, hard-won law 11 mechanism two).
Two casualties, one commit, and neither was visible in its diff.

⚠ **THE FK TO `customers.ServiceRequest` IS A NEW CROSS-MODULE FK** (B2 §2's
reviewed interface set), the same shape and the same disposition as
`work_orders.account_id`: a POINTER, never a write. It exists because one
portal report raises both records in one act.

⚠ **`premises_id` IS NULLABLE ON PURPOSE AND IT IS THE RULE, NOT A CONVENIENCE**
(`BR-CWP-027`). Making it NOT NULL would refuse the person standing over a
burst main in the street, which is the exact user this table was built for.

The RLS policy is a SEPARATE migration (`0047_rls_interruptions`) so it lands
under `human_owned.txt`'s `*rls*` glob with its own review-ledger row.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0039_def2847_mailing_address_line2_country"),
        ("metering", "0045_cr070_c_template_type_and_no"),
        ("tenancy", "0036_def3422_drop_bell_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="Interruption",
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
                ("reference", models.TextField(blank=True, null=True)),
                ("kind", models.TextField()),
                ("status", models.TextField(default="looking_into_it")),
                ("reported_at", models.DateTimeField()),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("location_text", models.TextField()),
                ("affected_area", models.JSONField(blank=True, null=True)),
                ("reporter_name", models.TextField(blank=True, null=True)),
                ("reporter_phone", models.TextField(blank=True, null=True)),
                ("expected_back_on", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "premises",
                    models.ForeignKey(
                        blank=True,
                        db_column="premises_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="interruptions",
                        to="metering.premises",
                    ),
                ),
                (
                    "service_request",
                    models.ForeignKey(
                        blank=True,
                        db_column="service_request_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.servicerequest",
                    ),
                ),
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
                "db_table": "interruptions",
                "indexes": [
                    models.Index(fields=["tenant", "status"], name="ix_interruptions_status")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("reference__isnull", False)),
                        fields=("tenant", "reference"),
                        name="uq_interruptions_tenant_reference",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@d6d31c46 (EP-CWP-03 story + 03-field-map.md § interruption)
# generated: 2026-09-04 by the CR-068 wave B build lane (makemigrations, then headed)
# checklist: A✔ B=deferred(table half — the cases assert through the service) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(the 🔒 half is 0047)
# gates: makemigrations --check clean · migrate applied on sqlite and on PostgreSQL 16
# exceptions: the table is `interruptions` where 03-field-map.md §2 writes `interruption` — the code wins, the field map is stamped by this wave
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
