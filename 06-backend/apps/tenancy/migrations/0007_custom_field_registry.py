# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (the invoice stamp this registry feeds — the R2 one-way
#           door of B12 r7.2)   Screens: S8 (Settings → Reference data)
# Rules:    BR-TEN-046 (custom fields are tenant-defined DATA, never schema;
#           tenant-scoped with RLS FORCE) · BR-TEN-049 (`key` immutable once
#           created) · BR-TEN-050 (deactivate only — no delete path) ·
#           BR-TEN-051 (cap: 10 active per entity per tenant) · BR-TEN-053
#           (the cached registry read and its version segment) · BR-TEN-048
#           (a custom field can never influence money) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""tenancy 0007 — the `custom_field` definition registry (B2 addendum r17.1).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHY DDL IS WRITTEN NOW WHEN r17 SAYS IT MUST NOT BE
----------------------------------------------------
B2 r17 opens *"No DDL is written until the OQ rows below are answered"* and
r17.6 names three: OQ-075, OQ-076, OQ-077. **All three closed on 2026-08-10**
(12-governance/01-open-questions.md):

  · OQ-075 — warn, do not block, and the field may carry a default value.
  · OQ-076 — *"Dont put SSN on invoices"*, and the MECHANISM was confirmed the
    same day as INVERTED: a field is NOT snapshotted unless the tenant
    explicitly marks it document-safe. Hard-won law 3, in the PO's own framing:
    the unsafe option is the one you have to type.
  · OQ-077 — the machine-translation publish gate → BR-SHL-043.

So the block has lifted; the doc text has not yet been amended, and this
migration does not amend it (B2 is not this lane's file). REPORTED in the lane
report so the propagation pass is owed, not lost.

TWO DEPARTURES FROM r17.1's COLUMN TABLE, BOTH TRACEABLE TO A PO RULING
-------------------------------------------------------------------------
1. **`is_document_safe` is ADDED.** r17.1 predates the OQ-076 confirmation and
   still describes the REJECTED opt-out (`contains_pii`, a flag the tenant
   ticks to exclude). Building that would have inverted the ruling: an unflagged
   SSN field would stamp permanently into append-only `invoices`, which
   BR-TEN-044's day-91 deletion can never reach. `default=False` IS the ruling.
2. **`default_value` is NOT added**, though OQ-075's closure grants it. Nothing
   in R2 reads it — a default is what a document renders for a DEACTIVATED
   field, rendering is R3 (US-NOT-016), and US-BIL-028 TC-6 excludes deactivated
   fields from new snapshots. The closure's own words put the BR-ID "at
   propagation", i.e. with EP-TEN-09's own lane. Recorded in
   12-governance/02-decision-log.md rather than left to memory.

WHAT THE TABLE DOES AND DOES NOT ENFORCE
-----------------------------------------
Enforced HERE, because only the database can hold them under concurrency: the
`(tenant, entity, key)` uniqueness, the eight-entity CHECK (r17.2's exclusions
each have a stated reason — the rating tables are the calculation boundary, the
financial tables are append-only, `meter_reads` is partitioned and cold-detached)
and the six-value `data_type` CHECK.

NOT enforced here, and each belongs to EP-TEN-09's own stories: the
`^[a-z][a-z0-9_]{1,39}$` key shape and its immutability (BR-TEN-049,
US-TEN-015), the cap of 10 active per entity (BR-TEN-051 — a partial-count
constraint PostgreSQL cannot express), `options` ≥2 for the select types, and
the placement slot allow-list (BR-TEN-052). A definition-write service that
does not exist cannot be half-enforced by a column.

`tenant_settings.custom_field_version` (BR-TEN-053) rides this migration rather
than the later one that will bump it, because the bump must happen in the SAME
TRANSACTION as a definition write — adding the column after that service exists
would make the first version of it wrong.

The RLS policy is `0008_rls_custom_field`, separate by this repo's convention
(customers 0002, metering 0004, billing 0008 all split it out).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0006_service_gl_attributes"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantsettings",
            name="custom_field_version",
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name="CustomField",
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
                ("entity", models.TextField()),
                ("key", models.TextField()),
                ("label", models.TextField()),
                ("help_text", models.TextField(blank=True, null=True)),
                ("data_type", models.TextField()),
                ("options", models.JSONField(blank=True, null=True)),
                ("is_required", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_document_safe", models.BooleanField(default=False)),
                ("placement", models.JSONField(blank=True, default=dict)),
                ("display_order", models.IntegerField(default=0)),
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
                "db_table": "custom_field",
                "indexes": [
                    models.Index(
                        condition=models.Q(("is_active", True)),
                        fields=["tenant", "entity"],
                        name="ix_custom_field_active",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "entity", "key"), name="uq_custom_field_key"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "entity__in",
                                (
                                    "premises",
                                    "units",
                                    "service_points",
                                    "assets",
                                    "accounts",
                                    "contacts",
                                    "addresses",
                                    "service_agreements",
                                ),
                            )
                        ),
                        name="ck_custom_field_entity",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "data_type__in",
                                ("text", "number", "date", "boolean", "select", "multi_select"),
                            )
                        ),
                        name="ck_custom_field_data_type",
                    ),
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17 ·
#         EP-TEN-09-custom-fields.md · 01-tenancy/02-business-rules.md
#         BR-TEN-046..053 · 12-governance/01-open-questions.md OQ-075/076/077)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean · migrate from empty on
#         sqlite and on a live Postgres cluster · the RLS half is 0008
# exceptions: (1) r17.6's "no DDL until the OQs are answered" is SATISFIED, not
#         overridden — OQ-075/076/077 all closed 2026-08-10; B2's text has not
#         been amended and that propagation is REPORTED, not done here ·
#         (2) `is_document_safe` is ADDED to r17.1's column table, from the
#         OQ-076 mechanism confirmation (INVERTED / fail-closed), replacing the
#         rejected opt-out `contains_pii` the table still describes ·
#         (3) `default_value` is NOT added though OQ-075 grants it — nothing in
#         R2 reads it and an unread column is what hard-won law 2 warns about;
#         owed to EP-TEN-09's propagation pass, recorded in the decision log ·
#         (4) the key regex, its immutability, the 10-per-entity cap, the
#         `options` ≥2 rule and the placement allow-list are NOT enforced here —
#         they are the definition-write service's (US-TEN-015/016), which does
#         not exist; half-enforcing them in a column would look like a guarantee
#         and not be one · (5) NOTHING WRITES THIS TABLE YET. The registry lands
#         ahead of its S8 UI because the invoice stamp is a one-way door and
#         cannot read a table that does not exist (B12 r7.2). Stated, not implied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
