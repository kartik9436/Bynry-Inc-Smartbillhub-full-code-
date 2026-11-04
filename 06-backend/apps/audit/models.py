# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (EP-AUD-01 — the append-only, RLS-forced, monthly-partitioned
#           trail table, exactly per B2 §audit) · US-AUD-007 (EP-AUD-03 — the
#           `archive_job_runs` record the retention job appends, shared with
#           US-MET-020: "one mechanism, two tables")   Screens: S61 (the store it feeds)
# Rules:    BR-AUD-002 (append-only — no mutation path anywhere) · BR-AUD-007 (RLS
#           FORCE, reads/writes under app.tenant_id) · BR-AUD-012 (monthly range
#           partitions on created_at — NFR-24/28) · BR-AUD-015 (tenant_id deliberately
#           NOT FK-constrained, so removing a tenant row never cascades here.
#           That is a CASCADE statement, NOT a retention promise: PO 2026-08-10
#           ruled the day-91 offboarding purge DOES delete the tenant's audit rows
#           (BR-TEN-044 + the single BR-AUD-002 carve-out).)
# Tests:    06-backend/tests/test_w0_models.py (shape + insert on sqlite) ·
#           06-backend/tests/test_be10_partitioning.py (TC-1 partition math) ·
#           RLS/trigger/partition TCs (TC-3..6) = G5 isolation suite on live Postgres
# Impacts:  BE-03 audit writer sink (the write-service story lane, EP-AUD-01) · every
#           module's money/settings rows · S61 viewer (EP-AUD-02) · EP-AUD-03 archival
# ───────────────────────────────────────────────────────
"""audit models — `audit_log` exactly per B2 §audit (US-AUD-001 §1).

The model gives the ORM the table's shape; the PARTITIONED reality is created
by migration 0001 (Postgres: parent `PARTITION BY RANGE (created_at)`, PK
(tenant_id, created_at, id) including the partition key, bootstrap partitions
current+3 per B2 §5, and the append-only trigger; sqlite test DB: plain table
so constraint tests can run — honestly recorded, RLS/trigger assertions live
in the G5 isolation suite).

Deliberate departures from every other module's models, each one law:
- `tenant_id` is a bare uuid column, NOT a ForeignKey — BR-AUD-015: audit rows
  must survive tenant purge, so no FK may cascade or block it.
- `actor_user_id` is a bare uuid — null means system job (BR-AUD-003), and the
  trail outlives any user row.
- No `updated_at`, and no update/delete API will ever exist here — append-only
  (BR-AUD-002); the writer contract is core.audit (BE-03), single INSERT.

US-AUD-010 (2026-09-06) adds three NULLABLE columns — `actor_kind`,
`actor_label`, `actor_version` — so an actor that is NOT a person can say what
it is. **Nullable is not a convenience here, it is BR-AUD-002:** this table
allows no UPDATE, so a backfill is not merely undesirable, it is forbidden and
the append-only trigger would refuse it. Every row written before that story
therefore keeps exactly the meaning it had — a user id, or a NULL that means an
unnamed system job — and the new columns are how a row written afterwards can
say more. See `core/audit.py` for what it cost not to have them.
"""

from django.db import models

from core.dbfields import uuid7, uuid7_pk

# The B2 §4 entity-lookup index name, shared with the Postgres DDL in 0001.
AUDIT_ENTITY_INDEX = "ix_audit_entity"

#: US-AUD-010 / BR-RBS-015 at the last line of defence: a row that NAMES a
#: non-person actor carries no user id, and a named actor is never anonymous.
#: The writer refuses both (`core.audit.write_row`); this is the table refusing
#: them too, so a future writer cannot reintroduce either by accident. Shared
#: with migration 0007 by name.
AUDIT_ACTOR_CONSTRAINT = "ck_audit_actor_named_never_borrows_a_login"


class AuditLog(models.Model):
    """One appended trail row (BR-AUD-003 payload standard fills it)."""

    pk = models.CompositePrimaryKey("tenant_id", "created_at", "id")  # includes partition key
    id = models.UUIDField(default=uuid7, editable=False)
    tenant_id = models.UUIDField()  # BR-AUD-015: NOT an FK — no cascade; survives tenant purge
    actor_user_id = models.UUIDField(null=True, blank=True)  # null = system job
    #: BR-AUD-019 — WHAT acted, when it was not a person: runbook | job |
    #: import | integration (`core.audit.AUTOMATION_ACTOR_KINDS`). NULL on a
    #: person's row AND on an unnamed system job, which is why the reader can
    #: still tell those two apart by `actor_user_id` exactly as it always did.
    actor_kind = models.TextField(null=True, blank=True)
    #: Its NAME, as a clerk reads it: "Returned payments". Never an id
    #: (B14 rule 31), and never a composed English sentence — see below.
    actor_label = models.TextField(null=True, blank=True)
    #: Its VERSION, as text and optional. ⚠ SEPARATE FROM THE NAME ON PURPOSE:
    #: storing "Returned payments, version 4" would put English in a database
    #: column that eleven catalogues then cannot translate (B14 rule 35), so the
    #: screen composes that sentence from these two facts in its own language.
    #: Text rather than an integer because a runbook numbers itself `4` while a
    #: platform job would name a build like `2.209.0`.
    actor_version = models.TextField(null=True, blank=True)
    action = models.TextField()  # catalog code (US-AUD-002; validated at the writer)
    entity_type = models.TextField()
    entity_id = models.UUIDField(null=True, blank=True)
    before = models.JSONField(null=True, blank=True)  # changed fields / masked PII only
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # partition key (RANGE monthly)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(
                fields=["tenant_id", "entity_type", "entity_id", "created_at"],
                name=AUDIT_ENTITY_INDEX,
            ),
        ]
        constraints = [
            models.CheckConstraint(
                # Either the row says nothing about a non-person actor — every
                # row written before US-AUD-010, and every row a person writes
                # after it — or it NAMES one, and then it has a label and NO
                # user id (BR-RBS-015: "it never borrows a user identity").
                condition=(
                    models.Q(actor_kind__isnull=True, actor_label__isnull=True)
                    | models.Q(
                        actor_kind__isnull=False,
                        actor_label__isnull=False,
                        actor_user_id__isnull=True,
                    )
                ),
                name=AUDIT_ACTOR_CONSTRAINT,
            ),
        ]


class ArchiveJobRun(models.Model):
    """US-MET-020 §5 / US-AUD-007 §5 PROPOSED-SCHEMA `archive_job_runs` — the
    append-only, rerun-safe record of one retention run over one table.

    **Deliberately NOT tenant-scoped, and this is the one thing to understand
    about it.** A partition is physically shared across every tenant
    (US-AUD-007 TC-7), so a run that detaches `audit_log_2026_08` is a platform
    storage operation, not a tenant's action: there is no tenant it could
    belong to and no `tenant_id` column to scope it by. The TENANT-visible
    record of the same event is the self-audit row the job writes into
    `audit_log` under each affected tenant's own context (BR-AUD-012's "audited"
    clause), which is where a tenant's staff see it and where RLS applies.
    This table is the operator's record and carries no tenant data — the row
    payloads hold partition names, counts and digests only.

    Hosted in apps.audit because EP-AUD-03 owns the trail's lifecycle and
    US-AUD-007 §5 asks for "one mechanism, two tables"; `core.archival` writes
    it through a registered recorder so core imports no app model (the same
    split apps.tenancy/core.jobs already uses for `jobs`).

    Append-only in practice: `core.archival` only ever INSERTs, and there is no
    update or delete function anywhere in this module for it.
    """

    id = uuid7_pk()
    table_name = models.TextField()  # 'meter_reads' | 'audit_log'
    run_date = models.DateField()
    hot_window_months = models.IntegerField()  # BR-MET-055 / BR-AUD-012: 24
    retention_months = models.IntegerField()  # 7 years, stated in months
    #: One entry per detached partition: name, row_count, sha256, tenants,
    #: destination, shipped + reason (see core/archival.py on what shipped means).
    archived = models.JSONField(default=list, blank=True)
    purged = models.JSONField(default=list, blank=True)
    #: success | skipped | partial. `partial` since 2026-09-07 (`OQ-AUD-1724`): the run
    #: reads each partition ONE UTILITY AT A TIME, and a partition whose utilities could
    #: not all be read is left exactly where it is rather than filed under a manifest that
    #: under-counts it. Free text rather than choices, so this needed no migration — and
    #: `archive_status` already surfaces `last_run_status` and `last_run_note` on S61, so
    #: a held partition is visible with no new column and no new screen.
    status = models.TextField(default="success")
    note = models.TextField(null=True, blank=True)  # why a run was a no-op
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "archive_job_runs"
        indexes = [
            models.Index(fields=["table_name", "run_date"], name="ix_archive_runs_table_date"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@b2ae555 (story+rules snapshot hash — EP-AUD-01 lead story of the W0 migrations lane)
# packet: US-AUD-007@6b3d915 (EP-AUD-03 retention story — archive_job_runs, added 2026-08-15)
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations lane)
# checklist: A✔ B=deferred(table-half — writer/catalog TCs land with US-AUD-002/003 lanes; live RLS/trigger TCs = G5) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff✔ black✔ py_compile✔ pytest tests/test_w0_models.py✔ tests/test_be10_partitioning.py✔ · suite 180/180✔ (147 baseline + 33 W0) · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: [US-AUD-007 lane 2026-08-15] `archive_job_runs` carries NO tenant_id and therefore no RLS policy — a month-partitioned table's archival is a platform storage op belonging to no tenant, and the tenant-visible record is the per-tenant self-audit row in audit_log; the table is absent from B2 §3's apply-list for the same reason · no unique on (table_name, run_date): a rerun is a LAWFUL no-op run that must still be recorded · AUD-D2 (S61 Source column + request metadata — no B2 column) NOT invented; anchoring stays with the Eng batch/PO per US-AUD-002 §5 — reported
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
