# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 0 · P0.1 (`report_definitions`) · P0.2
#           (`report_categories`) · P0.3 (`report_tenant_settings`).
#           Screens: none — Phase 0 ships no screen, deliberately.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE in reports/0002) ·
#           hard rule 2 (money 4 dp stored, percentages 6, both DISPLAY 2 — the
#           money-basis declaration lives in `datasets.py`, not here) ·
#           B14 rule 31 (no database id is ever the visible value of a field —
#           which is why `key` exists beside `id`) · B2 §2 (cross-module FKs
#           are the reviewed interface set; the only one here is `tenancy.Tenant`)
# Tests:    06-backend/tests/test_rep_p0_schema_spine.py
#           ⚠ The RLS half has NO test file in this repo yet and this line does
#           not pretend otherwise: `P0.10` owns it, it must run on PostgreSQL,
#           and a `Tests:` line naming a file that does not exist tells the next
#           lane the case is covered when it is not (G95 / G116, DEF-RBS-4335).
# Impacts:  apps/reports/migrations/0001_initial.py · 0002_rls_force.py ·
#           0003_seed_catalogue.py · apps/reports/catalog.py (superseded) ·
#           apps/reports/datasets.py (the `dataset` column's vocabulary)
# ───────────────────────────────────────────────────────
"""reports tables — B2 (04-docs/decisions/database-design-brief.md §reports).

**DATASETS ARE CODE. DEFINITIONS ARE DATA.** That one sentence is the whole of
the Reports Build Brief §7.1 and the whole reason this file exists. A dataset
is a registered, reviewed query against one module's read model — nine of them,
written by us, changed by a pull request (`apps/reports/datasets.py`). A
definition is a ROW: which dataset, which columns, which filters, how it groups
and sorts, where it sits in the catalogue. The 46 reports this product ships are
46 rows, and a utility writing its own writes a forty-seventh rather than
waiting for a release.

WHAT `tenant_id IS NULL` MEANS, AND WHY IT IS NOT AN ACCIDENT
─────────────────────────────────────────────────────────────
A NULL `tenant_id` is a PLATFORM row: shipped by us, readable by every tenant,
**writable by none**. The brief's §7.7 states it in those words. A tenant that
wants a shipped report changed does not edit it — the row is copied, the copy
carries that tenant's id, and the platform original is untouched. That is
copy-on-write, and it is the mechanism the whole framework rests on.

The RLS consequence is the one thing a reader of `0002_rls_force.py` must hold:
these two tables do **not** take the plain `tenant_id = current_tenant` policy
every other tenant table in this product takes. Their `USING` clause admits the
platform row as well, and their `WITH CHECK` clause does not — so a tenant
session SELECTs its own rows plus the platform's, and can INSERT, UPDATE or
DELETE only its own. `report_tenant_settings` is the ordinary shape, because an
overlay on a platform row is always the tenant's own row.

⚠ `visibility` IS A CHECK CONSTRAINT AND `report_categories` IS A TABLE, AND
THE DIFFERENCE IS DELIBERATE (brief P0.1, its own ⚠)
─────────────────────────────────────────────────────────────────────────────
A CHECK makes a third value a MIGRATION. That is exactly right for a signed
two-value enum — `private` and `shared`, ruled in §8 (*"A saved report is
visible to its author until shared"*) — and exactly wrong for a catalogue
grouping, which a utility must be able to extend without a release. So
visibility is a constraint and the category list is a table, and a tenant
inserting a category called *Board pack* sees it on the catalogue screen with
no deployment at all.

WHAT IS NOT HERE
────────────────
No `report_runs`. The brief is explicit and §05 says why: an export inserts a
`jobs` row in tenancy and **the job record IS the run record**. A second table
recording the same act is two answers to *"what ran, when, over what"*.

`report_schedules` IS here, as of `CR-142-BRC07` `P4.1`. ⚠ The paragraph this
replaces said *"That is `CR-142` phase 5"* and the brief's own task table puts
it in **Phase 4** — the table lands with the scheduler that reads it, not a
phase later. Corrected rather than deleted, because the next reader of this
file will otherwise re-derive the wrong boundary from a stale sentence
(hard-won law 1).
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk

#: The two values `report_definitions.visibility` admits, as a CHECK constraint
#: rather than as a lookup table. Brief §8: *"Private by default — a saved
#: report is visible to its author until shared."* Adding a third is a
#: migration ON PURPOSE: who may see a report is a security statement and not a
#: label a tenant renames.
VISIBILITY_PRIVATE = "private"
VISIBILITY_SHARED = "shared"
VISIBILITIES: tuple[str, ...] = (VISIBILITY_PRIVATE, VISIBILITY_SHARED)


class ReportCategory(models.Model):
    """One catalogue grouping — a GROUP when `parent_code` is null, a SUB-GROUP
    when it names one. Six groups and nineteen sub-groups are seeded as platform
    rows in `0003`; a tenant adds its own and they appear with no release.

    `parent_code` is a CODE and not a self-FK on purpose: a tenant's sub-group
    may hang off a PLATFORM group it does not own and cannot write, and a
    foreign key across the platform/tenant line would either have to be
    nullable-and-unenforced or would forbid the common case.
    """

    id = uuid7_pk()
    #: NULL = a platform row. See the module docstring.
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.PROTECT,
        db_column="tenant_id",
        null=True,
        blank=True,
    )
    code = models.TextField()
    name = models.TextField()
    #: The eleven catalogues, keyed by locale. B14 rule 35 — a catalogue is
    #: written in its own language, never translated from English — so this is
    #: empty on a row nobody has translated, and the reader falls back to `name`.
    name_i18n = models.JSONField(default=dict, blank=True)
    parent_code = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_categories"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "code"), name="uq_report_categories_tenant_code"
            ),
            # ⚠ AND A SECOND, PARTIAL ONE, BECAUSE THE FIRST DOES NOT COVER THE
            # PLATFORM ROWS. In PostgreSQL `NULL != NULL`, so a UNIQUE over
            # `(tenant_id, code)` constrains nothing at all when `tenant_id` is
            # NULL — two platform categories with the same code would both
            # insert, and the catalogue would show one heading twice with the
            # reports split between them. The constraint that looks like it is
            # protecting the shipped rows is the one that is not.
            models.UniqueConstraint(
                fields=("code",),
                condition=models.Q(tenant__isnull=True),
                name="uq_report_categories_platform_code",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "parent_code"), name="ix_rep_cat_tenant_parent"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return self.code


class ReportDefinition(models.Model):
    """One report. Forty-six of these are platform rows; the rest are a
    utility's own.

    ⚠ `columns`, `filters`, `group_by` and `sort` are **user input that NAMES
    columns, never SQL**. The brief says so twice and it is the wall the whole
    framework leans on: every name in them is validated against the dataset's
    own declaration (`apps/reports/datasets.py`) before it reaches a query, so
    everything a clerk can express has already been reviewed for tenant
    isolation, for money precision and for cost. You cannot invent a column the
    dataset does not produce — that is the architecture, not an oversight.
    """

    id = uuid7_pk()
    #: NULL = a platform row: readable by every tenant, writable by none.
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.PROTECT,
        db_column="tenant_id",
        null=True,
        blank=True,
    )
    #: The stable slug in `GET /reports/{key}` and in an export's filename.
    #: ⚠ A key sits in the same URL position as a tab name, so `custom`,
    #: `dashboard`, `scheduled` and `history` are refused BY NAME when a
    #: definition is saved (`P5.2`). That refusal is not this table's — a CHECK
    #: here would make the reserved list a migration, and the list belongs to
    #: the router.
    key = models.TextField()
    name = models.TextField()
    #: The eleven catalogues, keyed by locale — see `ReportCategory.name_i18n`.
    name_i18n = models.JSONField(default=dict, blank=True)
    #: One of the nine dataset codes in `apps/reports/datasets.py`. Not a FK:
    #: datasets are CODE, so the referent is a Python declaration reviewed by a
    #: pull request and there is no table to point at.
    dataset = models.TextField()
    #: The catalogue group and sub-group, by `report_categories.code`.
    group_code = models.TextField()
    sub_group_code = models.TextField(null=True, blank=True)
    #: Ordered column names, each one declared by the dataset.
    columns = models.JSONField(default=list, blank=True)
    #: Bound parameters — `{"basis": "posting", "window": "current_period"}`.
    filters = models.JSONField(default=dict, blank=True)
    group_by = models.JSONField(default=list, blank=True)
    sort = models.JSONField(default=list, blank=True)
    #: The services this report is offered for, by service code. EMPTY means
    #: every service — which is not the same as "all eleven", because a water
    #: utility must never be shown a gas report (`P0.3`'s own outcome).
    service_codes = models.JSONField(default=list, blank=True)
    visibility = models.TextField(default=VISIBILITY_SHARED)
    #: `P5.9` — the role floor for RUNNING this report, or NULL for no floor
    #: beyond the route's own `AnyTenantRole`. Read in exactly one place,
    #: `apps/reports/role_gate.py`, which carries the reasoning and the
    #: declared set of lawful values. NOT a CHECK constraint: the values are
    #: role codes owned by `apps/identity`, and freezing another module's
    #: vocabulary into this schema would make adding a role a migration here.
    #: `access_review` is the only row that carries one (`BR-REP-023`).
    min_role = models.TextField(null=True, blank=True)
    #: Who saved it. NULL on every platform row — nobody owns what we shipped.
    owner_user_id = models.UUIDField(null=True, blank=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_definitions"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "key"), name="uq_report_definitions_tenant_key"
            ),
            # ⚠ The platform half, for the reason `report_categories` states:
            # `NULL != NULL`, so the constraint above does not constrain the 46
            # rows we ship. Two platform rows on one key would give
            # `runner.resolve()` two answers and it would return whichever the
            # database happened to order first.
            models.UniqueConstraint(
                fields=("key",),
                condition=models.Q(tenant__isnull=True),
                name="uq_report_definitions_platform_key",
            ),
            models.CheckConstraint(
                check=models.Q(visibility__in=VISIBILITIES),
                name="ck_report_definitions_visibility",
            ),
        ]
        indexes = [
            #: P0.1's own index. The catalogue reads by tenant; the runner and
            #: `P2.12`'s paging assertion read by dataset.
            models.Index(fields=("tenant", "dataset"), name="ix_rep_def_tenant_dataset"),
            models.Index(fields=("tenant", "group_code"), name="ix_rep_def_tenant_group"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return self.key


class ReportServiceAccount(models.Model):
    """A MACHINE PRINCIPAL THAT READS A NAMED LIST OF REPORTS — `P2.20`, tier 1.

    ⚠ **WHAT THIS IS NOT, AND IT IS THE WHOLE REASON THE TABLE EXISTS.** Brief
    §7.8, p89, read as an image (B14 rule 42): *"What a service account is not:
    a person's password in a BI config file. That is how a clerk who leaves
    takes the reporting with them, how an audit log stops meaning anything, and
    how a revoked account silently breaks a board pack."* So it is **its own
    principal** — named, scoped to a tenant, carrying a named list of reports,
    revocable without touching a person, and it appears in *Started by* on
    History like anyone else.

    ⚠ **RULED, AND THE RULING IS NARROWER THAN THE OBVIOUS READING** (§7.8,
    p89). The PO wrote *"a · Administrators only … M. Okonkwo creates it and
    hands Dana the token + clerk"*, and Dana is a billing clerk. The brief reads
    that as **an administrator ISSUES one and any staff member, clerk included,
    may HOLD and USE it** — two different acts by two different people. Whether
    a clerk may also CREATE one is *"one line"* and is NOT assumed here; the
    narrower reading ships, because this is a credential.

    ⚠ **RLS APPLIES TO IT UNCHANGED, WHICH IS THE POINT OF THE WHOLE TIER.**
    §7.8: *"a BI tool cannot see anything a signed-in person could not, and RLS
    is doing the work rather than a second set of rules nobody maintains."* A
    request authenticated by this row sets `app.tenant_id` to `tenant_id` and
    takes every policy in the database exactly as a browser session does. This
    table takes the ORDINARY policy — `tenant_id = current_tenant` on USING and
    WITH CHECK alike. It is deliberately NOT the asymmetric platform-row policy
    `report_definitions` needs: a NULL tenant here would be a credential every
    utility could use, which is the one row this product must never hold.

    ⚠ **THE TOKEN IS STORED AS A HASH AND THE PLAINTEXT IS SHOWN ONCE.** A
    credential a support engineer can read out of a table is a credential the
    audit log cannot speak for — which is the same failure as the password in
    the config file, one table over.

    ⚠ **`report_keys` IS A NAMED LIST AND AN EMPTY ONE GRANTS NOTHING.** §7.8:
    *"a connection granted Revenue Analysis and Trial Balance can read those two
    and nothing else; AR Ageing later means somebody grants it."* Empty must
    therefore deny everything, never everything-by-default — the direction an
    allow list fails in is the whole of its value, and a `[]` that meant *all*
    would turn a half-finished create into a key to the building.
    """

    id = uuid7_pk()
    #: NEVER NULL. See the RLS note above: a platform service account would be
    #: a credential every tenant could use.
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    #: What a person calls it — *"Power BI · board pack"*. It is what appears in
    #: `Started by` on History, so it is a NAME and never an id (B14 rule 31).
    name = models.TextField()
    #: The token, hashed. The plaintext is returned once, at create, and is not
    #: recoverable from this row by us or by anybody.
    token_hash = models.TextField()
    #: The first characters of the token, for telling two apart on screen
    #: without holding either. Not a secret and not an id.
    token_prefix = models.TextField()
    #: The report keys this principal may read. EMPTY DENIES EVERYTHING.
    report_keys = models.JSONField(default=list, blank=True)
    #: The administrator who issued it — provenance, never displayed.
    created_by_user_id = models.UUIDField(null=True, blank=True)
    #: Revocation is a TIMESTAMP and not a delete: a revoked credential that
    #: vanished would take its history in `audit_log` with it, and *"a revoked
    #: account silently breaks a board pack"* is a thing somebody has to be able
    #: to look up afterwards.
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by_user_id = models.UUIDField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_service_accounts"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name"), name="uq_report_service_accounts_tenant_name"
            ),
            #: ⚠ **GLOBALLY UNIQUE, AND DELIBERATELY NOT SCOPED TO THE TENANT.**
            #: The token is what IDENTIFIES the tenant on an incoming request —
            #: there is no path segment to read it from and no cookie — so two
            #: tenants holding one hash would make the lookup ambiguous at
            #: exactly the moment isolation depends on it.
            models.UniqueConstraint(
                fields=("token_hash",), name="uq_report_service_accounts_token"
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "revoked_at"), name="ix_rep_svc_tenant_live"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return self.name


class ReportTenantSetting(models.Model):
    """One tenant's overlay on one definition — usually a PLATFORM definition.

    This is the table that makes *"a water utility stops being shown gas
    reports"* true without editing what we shipped. `tenant` is NOT nullable
    here: an overlay is always somebody's, so this table takes the ordinary
    tenant-isolation policy and admits no platform row at all.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        db_column="definition_id",
        related_name="tenant_settings",
    )
    enabled = models.BooleanField(default=True)
    pinned = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    #: What this utility calls it. NULL means "what we called it".
    name_override = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_tenant_settings"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "definition"),
                name="uq_report_tenant_settings_tenant_definition",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return f"{self.tenant_id}:{self.definition_id}"



#: `report_schedules.cadence` — the FOUR signed values, as a CHECK constraint.
#:
#: ⚠ **A CHECK MAKES A FIFTH CADENCE A MIGRATION, WHICH IS CORRECT HERE** — the
#: brief's own ⚠ on `P4.1`, in those words. Cadence is not a label a utility
#: renames: each value is a branch of `next_run_at` arithmetic somebody has to
#: WRITE (`schedules.next_run_at`), so a value with no branch behind it is a
#: schedule that never fires and says nothing. That is the opposite trade from
#: `report_categories`, which is a table precisely so a tenant can extend it.
#:
#: ⚠ **THEY ARE RENDERED AS WORDS AND NEVER AS A CRON STRING** (drawing p40
#: callout ①: *"rendered as words, never a cron string — 'monthly, on cycle
#: close', not `0 0 1 * *`"*). `monthly_on_cycle_close` is the one a utility
#: actually wants and the one a generic cron picker cannot express at all,
#: because the close date is a fact about the tenant's billing calendar rather
#: than a day of the month.
CADENCE_DAILY = "daily"
CADENCE_WEEKLY = "weekly"
CADENCE_MONTHLY = "monthly"
CADENCE_MONTHLY_ON_CYCLE_CLOSE = "monthly_on_cycle_close"

#: In the order the dialog offers them (drawing p34 callout ②).
CADENCES = (
    CADENCE_DAILY,
    CADENCE_WEEKLY,
    CADENCE_MONTHLY,
    CADENCE_MONTHLY_ON_CYCLE_CLOSE,
)

#: `report_schedules.format`. ⚠ **ONE VALUE, AND THE HOLE IS SIGNED** (drawing
#: p34 callout ③): *"CSV only, because no PDF renderer is declared anywhere in
#: the product. Adding PDF here puts a control on screen that produces
#: nothing."* `apps/reports/exports.py` has said the same since 2026-08-16.
#: A CHECK with one value is deliberate: it is the place a PDF renderer's
#: arrival has to be noticed.
FORMAT_CSV = "csv"
FORMATS = (FORMAT_CSV,)


class ReportSchedule(models.Model):
    """One standing instruction: run THIS report, THIS often, send it to THESE
    people (`CR-142-BRC07` `P4.1`; screens `2·3`, `4·1`, `4·2`).

    ════════════════════════════════════════════════════════════════════════
    WHAT THIS TABLE IS NOT: IT IS NOT A RUN RECORD
    ════════════════════════════════════════════════════════════════════════
    A schedule is *a run that has not happened yet*; a run is *a schedule that
    fired, or somebody pressing a button* (drawing p38, ① of Tabs 3 and 4, in
    those words). The RUN stays where `run_history.py` already puts it — the
    `jobs` row — and `last_job_id` is a POINTER at the most recent one, never a
    copy of its status. A second copy of *did it work* is the `bell_events`
    shape (DEF-3422) and would need somebody to remember to keep it in step.

    ⚠ **SO DELETING A SCHEDULE LEAVES EVERY PAST RUN ON `5·1`** (p41 ④, *"a run
    is a historical fact"*), and that falls out of the design rather than being
    a rule anybody has to enforce: the runs are not in this table.

    ════════════════════════════════════════════════════════════════════════
    `recipients` IS A LIST OF THIS TENANT'S OWN USER IDS — `BR-REP-020`, RULED
    ════════════════════════════════════════════════════════════════════════
    ⚠ **THERE IS NO EMAIL COLUMN AND THERE MUST NOT BE.** External recipients
    arrive at W6 with an explicit confirm step, because an external send means
    data leaves the tenant. A free-text email box breaks a signed ruling
    (drawing p34 callout ④, and the brief's `P4.3`).

    A `JSONField` of user ids rather than a join table, deliberately: the list
    is read whole, written whole, and never queried BY recipient — *"which
    schedules is Dana on"* is not a question any screen asks. A join table
    would buy an index nothing uses and cost a second write path. The
    membership check that makes the ruling true is `schedules.resolve_recipients`,
    at the API boundary, where it can refuse with a message.

    ⚠ **A user id is stored and a NAME is rendered** (B14 rule 31): `4·1`'s
    *Send to* column reads *"Dana W. +1"*, never a uuid.

    ════════════════════════════════════════════════════════════════════════
    `next_run_at` IS NULLABLE AND NULL MEANS PAUSED
    ════════════════════════════════════════════════════════════════════════
    Pause *"writes `enabled=false` on one schedule row and clears
    `next_run_at`; nothing else moves"* (p41 ④, verbatim). Two columns saying
    one thing looks redundant until you ask what the sweep reads: the partial
    index below is `WHERE enabled`, so a paused row is not merely skipped, it
    is **not in the index the sweep scans**. Resuming recomputes the date from
    the cadence rather than restoring a stale one, which is why clearing it
    loses nothing.

    ⚠ **`failing` IS NOT A COLUMN** (p40 callout ③). A schedule whose report
    now errors *"stays in the list marked failing and is not silently dropped"*
    — and that status is DERIVED on read from `last_job_id`'s job, exactly as
    `run_history.RUN_EXPIRED` is. A stored status can get stuck saying
    `failing` because the run that would have cleared it never wrote back; a
    derived one cannot.
    """

    id = uuid7_pk()
    #: NOT nullable — a schedule is always somebody's. Ordinary tenant
    #: isolation on both clauses, unlike `report_definitions` above.
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    #: The report this runs. `PROTECT` and not `CASCADE`: a definition with a
    #: live schedule on it may not be deleted out from under the sweep, and the
    #: refusal is the database's rather than something a service must remember.
    definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.PROTECT,
        db_column="definition_id",
        related_name="schedules",
    )
    cadence = models.TextField()
    #: The report's parameters, FROZEN AT SCHEDULE TIME. The dialog is opened
    #: from a report you are already looking at (p34: *"The report, its
    #: parameters and its name are inherited from the screen behind"*), so this
    #: is a copy of what was on screen and not a pointer at whatever the
    #: definition says next month.
    params = models.JSONField(default=dict, blank=True)
    format = models.TextField(default=FORMAT_CSV)
    #: This tenant's own user ids. See the class docstring.
    recipients = models.JSONField(default=list, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    #: The most recent `jobs` row this schedule produced. A POINTER, never a
    #: copy of its status. Not a FK: `jobs` is tenancy's table and B2 §2 keeps
    #: cross-module FKs to the reviewed interface set, which this is not on.
    last_job_id = models.UUIDField(null=True, blank=True)
    #: `P4.14` — WHERE THE FILE ALSO GOES, when an administrator has set a
    #: destination up and somebody picked it. NULL is the ordinary case and
    #: means *the outbound queue and nothing else* (`P4.10`), so every schedule
    #: written before this column behaves exactly as it did.
    #:
    #: ⚠ **A POINTER AT AN ADMIN-OWNED ROW, NEVER AN ADDRESS TYPED HERE.** The
    #: ruling (brief p090, FINAL) is that destinations are *"set up by an
    #: administrator and never by whoever creates the schedule"*, and a column
    #: holding a host or an email would be that person typing it. `PROTECT`
    #: because a destination with live schedules on it may not be deleted out
    #: from under the sweep — the same refusal `definition` already takes, and
    #: the database's rather than something a service must remember.
    destination = models.ForeignKey(
        "reports.ReportDestination",
        on_delete=models.PROTECT,
        db_column="destination_id",
        related_name="schedules",
        null=True,
        blank=True,
    )
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_schedules"
        constraints = [
            models.CheckConstraint(
                check=models.Q(cadence__in=CADENCES),
                name="ck_report_schedules_cadence",
            ),
            models.CheckConstraint(
                check=models.Q(format__in=FORMATS),
                name="ck_report_schedules_format",
            ),
        ]
        indexes = [
            #: `P4.1`'s own index: *"Index on `next_run_at` where enabled"*.
            #: PARTIAL on purpose — the sweep asks *what is due* once a minute
            #: across every tenant, and a paused schedule is not an answer it
            #: ever wants. ⚠ NFR-5: this is an index, not a cap; nothing here
            #: limits how many schedules a tenant may hold.
            models.Index(
                fields=("next_run_at",),
                condition=models.Q(enabled=True),
                name="ix_rep_sched_due",
            ),
            models.Index(fields=("tenant", "definition"), name="ix_rep_sched_tenant_def"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return f"{self.definition_id}:{self.cadence}"



# ═══════════════════════════════════════════════════════════════════════════
# `CR-142-BRC07` Phase 4 · `P4.14` — BI TIER 2, SCHEDULED DELIVERY
# ═══════════════════════════════════════════════════════════════════════════

#: The two transports the brief names, p015: *"send it to **SFTP or a signed
#: URL** on a timer"*. No third is invented here.
DESTINATION_LINK = "signed_link"
DESTINATION_SFTP = "sftp"
DESTINATION_KINDS = (DESTINATION_LINK, DESTINATION_SFTP)


class ReportDestination(models.Model):
    """WHERE A SCHEDULED FILE MAY GO — set up by an ADMINISTRATOR, once.

    ⚠ **RULED, brief p090's decisions register, FINAL:** *"A scheduled file may
    leave the product — **Yes** — admin-set destinations, encrypted in transit,
    every delivery logged."* Three conditions, and this table is the first of
    them made structural: a destination is a ROW an administrator creates, and
    a schedule POINTS at one.

    ⚠ **THIS IS WHY IT IS A TABLE AND NOT A FIELD ON THE SCHEDULE.** p015:
    *"Without the first, a clerk schedules the debtor list — 412 names,
    addresses and balances — to a personal address and nothing records it."* A
    column on `report_schedules` would be filled in by whoever creates the
    schedule, which is the precise act the ruling forbids. Two tables means two
    acts by two people, and the narrower right (create a schedule) cannot reach
    the wider one (choose where data leaves the tenant).

    ⚠ **IT DOES NOT REOPEN `BR-REP-020`, AND p089 SAYS SO IN AS MANY WORDS:**
    *"That rule is about a **free-text email box on the schedule form** — anyone
    can type anything into it. This is about **a destination an administrator
    configured once**, which is a different act by a different person. The form
    still offers no free text."* The schedule form gains a PICKER over this
    table and never an input.

    ⚠ **`config` HOLDS NO SECRET TODAY AND THE `sftp` KIND IS NOT REACHABLE.**
    `OQ-REP-7040` is OPEN: nothing has ruled whose host key an SFTP transport
    trusts, and no SSH client is installed on this deployment either. The kind
    is in the vocabulary because the ruling names it and a `CHECK` written now
    saves a migration later; `destinations.py` refuses it BY NAME with that id
    (prime directive — a lane never resolves an open question by choosing a
    value). See that module for the whole of it.

    ⚠ **THE ORDINARY TENANT POLICY, BOTH CLAUSES, NO `IS NULL`** — the same
    reasoning `ReportServiceAccount` records: a platform-wide destination row
    would be somewhere every utility's data could be sent.
    """

    id = uuid7_pk()
    #: NEVER NULL. See the RLS note above.
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    #: What a person calls it — *"Finance SFTP drop"*. A NAME, never an id
    #: (B14 rule 31): it is what the schedule form's picker shows.
    name = models.TextField()
    kind = models.TextField()
    #: Transport settings. **No secret is stored here yet** — see the class
    #: docstring and `OQ-REP-7040`.
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    #: The ADMINISTRATOR who set it up. Provenance for the ruling's first
    #: condition, and what the audit row names.
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_destinations"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name"), name="uq_report_destinations_tenant_name"
            ),
            #: Four values would be a migration, which is correct here — the
            #: same posture `P4.1` took with `cadence`.
            models.CheckConstraint(
                check=models.Q(kind__in=DESTINATION_KINDS),
                name="ck_report_destinations_kind",
            ),
        ]
        indexes = [
            #: ⚠ NFR-5: an index, never a cap. Nothing here limits how many
            #: destinations a utility may hold.
            models.Index(fields=("tenant", "enabled"), name="ix_rep_dest_tenant_live"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return self.name


#: A delivery either happened or it did not. Module level so the CHECK
#: constraint below can name it — a class attribute is not in scope inside
#: `Meta`, which is a Python fact and not a style choice.
DELIVERY_SENT = "sent"
DELIVERY_FAILED = "failed"
DELIVERY_STATUSES = (DELIVERY_SENT, DELIVERY_FAILED)


class ReportDelivery(models.Model):
    """ONE FILE, ONE DESTINATION, ONE ATTEMPT — the ruling's third condition.

    ⚠ **"EVERY DELIVERY LOGGED" IS THIS TABLE AND `audit_log` BOTH, AND THEY
    ARE NOT THE SAME RECORD.** `audit_log` answers *who caused data to leave
    the tenant* and is pruned on the utility's retention schedule (hard rule 4's
    closing clause). This row answers *did the file go, and may this link still
    be redeemed* — it is OPERATIONAL state the delivery sweep reads back, which
    is why it is not a second copy of the audit row. Hard-won law 5 is about one
    generated file, not about two records answering two questions.

    ⚠ **THE TOKEN IS NOT STORED.** A signed link is self-describing (see
    `signed_links.py`): it needs no row to be valid and this row could not
    revoke it if it held one. What is kept is `expires_at`, so a screen can say
    *the link has expired* rather than offering a dead address — which is
    exactly the shape `P3.5` already took with a purged artifact.

    ⚠ **`status` IS STORED AND NOT DERIVED, WHICH IS THE OPPOSITE OF
    `ReportSchedule.failing` AND FOR A REASON.** A schedule's failing-ness is
    derivable because the run it points at holds the truth. A delivery ATTEMPT
    has no other record anywhere — the transport either accepted the bytes or
    it did not, and if this row does not say so nothing does.
    """

    STATUS_SENT = DELIVERY_SENT
    STATUS_FAILED = DELIVERY_FAILED
    STATUSES = DELIVERY_STATUSES

    id = uuid7_pk()
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    destination = models.ForeignKey(
        ReportDestination,
        on_delete=models.PROTECT,
        db_column="destination_id",
        related_name="deliveries",
    )
    schedule = models.ForeignKey(
        ReportSchedule,
        on_delete=models.PROTECT,
        db_column="schedule_id",
        related_name="deliveries",
    )
    #: The `jobs` row whose artifact was delivered. Not a FK — `jobs` is
    #: tenancy's table and B2 §2 keeps cross-module FKs to the reviewed
    #: interface set, which this is not on. Same posture as
    #: `ReportSchedule.last_job_id`.
    job_id = models.UUIDField()
    status = models.TextField()
    #: Why it failed, in a sentence a person can act on. NULL when it did not.
    detail = models.TextField(null=True, blank=True)
    #: When the link this delivery handed out stops working. NULL for a
    #: transport that pushed the bytes rather than handing out an address.
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "report_deliveries"
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=DELIVERY_STATUSES),
                name="ck_report_deliveries_status",
            ),
            #: **CLAUDE.md hard rule 6 — idempotency.** The sweep reconciles
            #: rather than hooks (see `delivery.py`), so it will meet the same
            #: (schedule, job, destination) again on the next beat and must not
            #: send the file twice. The database refuses the second attempt;
            #: nothing depends on the sweep remembering.
            models.UniqueConstraint(
                fields=("schedule", "job_id", "destination"),
                name="uq_report_deliveries_once",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "created_at"), name="ix_rep_deliv_tenant"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging affordance
        return f"{self.destination_id}:{self.status}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 0 (12-governance/change-requests/CR-142-BRC07-reports-framework.md · 05-prototype/09 Reports Build Brief.pdf p6-p9 read as images per B14 rule 42 · §05 p75-77 · §07 p82-85)
# screens: none — Phase 0 ships no screen, stated in the brief's own words
# generated: 2026-09-26 by lane REP-P0A
# checklist: A✔ B=n/a(no frontend half in Phase 0) C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p0_schema_spine.py could not import these models before this file existed
# exceptions: (1) `parent_code` is a CODE, not a self-FK, because a tenant sub-group may hang off a platform group it cannot write · (2) `dataset` is not a FK: datasets are code · (3) the reserved-segment refusal is the router's and is deliberately NOT a CHECK here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
