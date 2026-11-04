# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3: the seven tables.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE on every tenant table —
#           migrations/0002_rls_force) · hard rule 2 (money 4 decimals, CHAR(3)
#           currency, never float) · hard rule 6 (idempotency by a UNIQUE key) ·
#           BR-RBS-001 (kind is check|action, immutable after creation) ·
#           BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-004 (the
#           plan is written before any act) · BR-RBS-008 (the idempotency key) ·
#           BR-RBS-011 (a failure with no fix route is a defect in the runbook) ·
#           BR-RBS-017 (a work item is UPSERTED by fingerprint) · BR-RBS-019
#           (the unit of work is never the raw row) · BR-RBS-024 (one category,
#           from sixteen held in code) · BR-RBS-035 (a volume runbook keeps a
#           count, not a row per subject) · BR-RBS-038 (every edit makes a new
#           version; a run pins the version it used)
# Tests:    06-backend/tests/test_us_rbs_041_module.py (the shapes, on SQLite) ·
#           06-backend/tests/test_us_rbs_041_pg.py (TC-RBS-7 — the isolation
#           probe and the idempotency index, on PostgreSQL only)
# Impacts:  apps/runbooks/migrations/0001_initial.py · 0002_rls_force.py ·
#           04-docs/02-decisions/02-database-design-brief.md §2 Module: runbooks
#           + Addendum r24 (anchored FIRST — CR-075 wave A task A1)
# ───────────────────────────────────────────────────────
"""runbooks models — seven tables, one module, and no join into anyone else's.

WHAT THIS MODULE OWNS, AND WHY THESE SEVEN
------------------------------------------
* `runbooks` — one row per runbook a tenant has. `kind` is `check` or `action`
  and is **immutable after creation** (`BR-RBS-001`): the whole safety promise
  of a Check is that it holds no writer, and a kind that could be edited would
  turn a Check into an Action on a live schedule.
* `runbook_versions` — an immutable snapshot per edit. A run stores the version
  it used, so a later edit never rewrites history.
* `runbook_runs` — one row per run. `report` is the block list **as composed
  when the run closed**, frozen: a past run reopened draws exactly what it drew
  that day, which is the thing a regulator asks for.
* `runbook_run_records` — one row per record examined, carrying **the plan and
  then the outcome in the SAME row**. *What did it say it would do versus what
  it did* is the audit; two tables would make that comparison a join, and the
  audit becomes a query nobody writes.
* `work_items` — everything waiting on a person, whatever raised it, **upserted
  by fingerprint**. Thirty daily sweeps over one missing read are one item
  ageing, not thirty rows.
* `cutover_plans` / `cutover_plan_items` — a go-live plan. An item with a NULL
  `runbook_key` is a human task the engine never performs.

⚠ THE ENGINE WRITES `work_items`, NEVER A RUNBOOK. A Check produces findings and
the engine upserts them when the run closes. That is precisely how a Check
populates the work list **while being constructed with no writer at all**
(`BR-RBS-002` / `BR-RBS-022`) — and it is why `raise_work_item` is NOT one of the
thirteen ports. The specification's architecture section says a runbook writes
through *"four named calls"* and lists *raise a work item* among them; that
sentence is stale in two ways at once and the contract corrects it
(`12-the-contract.md` §6, `03-field-map.md` D-1). A lane building the four-call
version gives every Check a writer, and `BR-RBS-002` is gone.

⚠ `work_items` IS NOT THE `work` MODULE'S TABLE, AND THE NAMES ARE NOT A
COLLISION (`03-field-map.md` D-4). `apps/work` owns crews, technicians, parts and
WORK ORDERS. This is findings, exceptions and human tasks on one surface. No
`work_items` table exists anywhere else in the product.

⚠ `runbook_run_records.subject_id` CARRIES NO FOREIGN KEY, DELIBERATELY. Which
table it points at is decided by `subject_type` on the same row, so a real FK
would need twelve nullable columns and would give this module a hard link into
tables it is FORBIDDEN to write. The rows behind it are read through
`apps/runbooks/seams/`, never joined. **The cost is stated rather than hidden:**
a deleted account leaves a record row pointing at nothing, which is correct for
an audit record — *what did this run say it would do* is a fact about the past
and should not vanish because its subject did. B2 Addendum r24 records this.

TWO VENDORS, RECORDED HONESTLY (the same posture as `apps/integrations/models.py`)
----------------------------------------------------------------------------------
On PostgreSQL every table carries RLS ENABLE + FORCE (`migrations/0002_rls_force`)
and the two UNIQUE constraints are real indexes. On the SQLite test database the
plain tables stand and the PostgreSQL-only guarantees are asserted in
`tests/test_us_rbs_041_pg.py`, which SKIPS rather than passing vacuously —
hard-won law 14, and `G5` once called 192 skips a pass.

`tags` IS `JSONField`, NOT `ArrayField`, and that is the repository's existing
answer rather than a new one: `django.contrib.postgres` types have no SQLite
form, `config/settings/test.py` hardcodes in-memory SQLite, and both
`apps/work/models.py` and `apps/portal/models.py` record the identical
substitution in their own comments. Tags help a search and nothing else
(`BR-RBS-024`), so no query needs array containment. B2 r24 departure 1.

WRITE PATH: `apps/runbooks/services.py` and nothing else (B1). READS:
`apps/runbooks/selectors.py`. Another module's rows: `apps/runbooks/seams/`,
read-only. Another module's WRITES: `apps/runbooks/ports/`, and nothing is bound
to a writer before wave L.
"""

from django.db import models

from core import dbfields
from core.money_fields import money_field

# ── closed vocabularies (17-runbooks/03-field-map.md §1-§7, 12-the-contract.md) ──
# Held in code rather than in a lookup table, on purpose: the category NAMES the
# owning module whose ports a runbook may call (`BR-RBS-024`), which is an
# engineering fact and not tenant reference data. A runbook module declaring a
# value outside these lists fails the conformance suite (wave B).

KIND_CHECK = "check"
KIND_ACTION = "action"
#: `BR-RBS-001` — declared at creation and NEVER changed afterwards.
KINDS = (KIND_CHECK, KIND_ACTION)

ORIGIN_SHIPPED = "shipped"
ORIGIN_CLONED = "cloned"
ORIGIN_COMPOSED = "composed"
ORIGINS = (ORIGIN_SHIPPED, ORIGIN_CLONED, ORIGIN_COMPOSED)

TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULE = "schedule"
TRIGGER_EVENT = "event"
#: THREE KINDS over five trigger rows, of which three are event names. The
#: specification's heading reads "three kinds, five events"; the five is the row
#: count (`12-the-contract.md` §4).
TRIGGER_KINDS = (TRIGGER_MANUAL, TRIGGER_SCHEDULE, TRIGGER_EVENT)

EVENT_BATCH_LANDED = "batch.landed"
EVENT_FEEDBACK_LANDED = "feedback.landed"
EVENT_BILL_RUN_COMPLETED = "bill_run.completed"
#: ⚠ The first two are BLOCKED-BY the integrations substrate (`CR-069`) and are
#: phase 5's dependency. Manual and schedule wait on nothing. A runbook whose
#: only trigger is an unbuilt event is not runnable, and a screen must SAY so
#: rather than offering a Run ▶ that refuses (`RB-022`).
EVENT_KINDS = (EVENT_BATCH_LANDED, EVENT_FEEDBACK_LANDED, EVENT_BILL_RUN_COMPLETED)

GATE_APPROVE_EACH_RUN = "approve_each_run"
GATE_APPROVED_UP_FRONT = "approved_up_front"
#: ⚠ **TWO VALUES, AND THE SECOND ONE IS A PO RULING RATHER THAN A DESIGN
#: CHOICE — `BR-RBS-041`, CONFIRMED 2026-09-06** (`OQ-RBS-1733` CLOSED with a
#: FOURTH option nobody offered). *"Ask for permission from user upfront - if
#: they are okay we complete the run and action, otherwise not."* An admin turns
#: the switch on for one runbook; with it on a run goes plan → act in ONE pass,
#: with it off it stops and waits at Review exactly as before.
#: ⚠ **THE PLAN IS COMPUTED AND STORED EITHER WAY — THE SWITCH REMOVES THE WAIT,
#: NEVER THE PLAN**, so `BR-RBS-004` (an Action always produces a plan first)
#: survives intact and every run stays reproducible and auditable. A lane
#: reading `approved_up_front` as *skip the plan* has read it backwards.
#: ⚠ **AND THE THREE-CLEAN-RUN RATCHET WAS RECOMMENDED AND NOT TAKEN.** There is
#: no third value here and adding one is a new ruling, not this one.
GATE_MODES = (GATE_APPROVE_EACH_RUN, GATE_APPROVED_UP_FRONT)

#: The role codes `Runbook.visible_to_roles` may hold (`RB-050`). Kept as a
#: literal tuple rather than imported from `core.permissions`, for the reason
#: `api.py`'s `CsvRenderer` gives about a four-line cross-module import: the
#: three codes are `A4`'s ratified set and `test_us_rbs_038_definition_surface`
#: asserts this tuple AGAINST `core.permissions.ROLES`, so the two cannot drift
#: without a red naming both.
VISIBILITY_ROLES = ("system_admin", "billing_clerk", "executive")

MODE_DRY = "dry"
MODE_LIVE = "live"
#: ONE code path. The difference between the two is whether the writer is bound,
#: never a branch inside a step (`BR-RBS-003`, `TC-RBS-2`).
MODES = (MODE_DRY, MODE_LIVE)

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_AWAITING_APPROVAL = "awaiting_approval"
RUN_STATUS_APPROVED = "approved"
RUN_STATUS_ACTING = "acting"
RUN_STATUS_DONE = "done"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_STOPPED = "stopped"
RUN_STATUSES = (
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_AWAITING_APPROVAL,
    RUN_STATUS_APPROVED,
    RUN_STATUS_ACTING,
    RUN_STATUS_DONE,
    RUN_STATUS_FAILED,
    RUN_STATUS_STOPPED,
)

#: The TWELVE subjects a runbook may walk (`12-the-contract.md` §3).
#: ⚠ `premise` is `premises`, the product's own word and its ONE ADDRESS HOME
#: (hard rule 8, `BR-MET-1161`). A runbook that wants an address WALKS TO THE
#: PREMISES; it never reads an address column off an account, a meter, a route
#: or a work order, because none of them has one.
SUBJECT_TYPES = (
    "tenant",
    "account",
    "premise",
    "meter",
    "meter_day",
    "bill",
    "payment",
    "bank_line",
    "deposit",
    "parcel",
    "contact_feedback",
    "period",
)

#: The SIXTEEN categories, eleven of them in use (`12-the-contract.md` §5).
#: Three things read this: the template library filters by it, role visibility
#: defaults from it, and — the one that makes it an engineering fact rather than
#: a label — IT NAMES THE OWNING MODULE WHOSE PORTS THE RUNBOOK MAY CALL.
#: ⚠ The category is `premises`, NOT `service_points`: decision log 2026-09-06,
#: category names use the product's OWN existing word wherever it has one.
#: ⚠ A seventeenth category needs THREE runbooks that fit nowhere else
#: (`BR-RBS-025`), and a category with no runbook is never drawn as a filter.
CATEGORIES = (
    "platform",
    "onboarding_cutover",
    "data_hygiene",
    "premises",
    "plans_rates",
    "assets",
    "accounts",
    "reads",
    "billing",
    "collections",
    "payments",
    "finance",
    "work",
    "customer_portal",
    "business",
    "data_sync",
)

#: The owning module each category names — the module whose ports a runbook of
#: that category may call. A Check reaches NONE of them, whatever its category.
CATEGORY_OWNING_MODULE = {
    "platform": "tenancy",
    "onboarding_cutover": "tenancy",
    "data_hygiene": "customers",
    "premises": "metering",
    "plans_rates": "rating",
    "assets": "metering",
    "accounts": "customers",
    "reads": "metering",
    "billing": "billing",
    "collections": "payments",
    "payments": "payments",
    "finance": "ledger",
    "work": "work",
    "customer_portal": "customers",
    "business": "reports",
    "data_sync": "integrations",
}

#: WHO SEES A RUNBOOK OF THIS CATEGORY BY DEFAULT — `BR-RBS-024` clause 2,
#: `RB-050`, `CR-075` wave D task `D5`.
#:
#: `12-the-contract.md` §5 states it in one sentence and one table column:
#: *"Role visibility defaults from it. Owner and Admin see every runbook; the
#: last column below says who else does by default; an Admin may widen or
#: narrow it per runbook."* This dict IS that column, transcribed row for row —
#: `+ Staff`, `+ Finance`, `+ Staff · Finance`, or a bare `—`.
#:
#: ⚠ **THE SOURCE NAMES FOUR ROLES AND THIS PRODUCT HAS THREE, SO THE MAPPING IS
#: WRITTEN DOWN RATHER THAN LEFT TO BE INFERRED.** `04-roles-permissions.md`
#: line 7 lists Owner · Admin · Billing Clerk/Staff · Finance among the roles the
#: specification *implies*; `A4`'s ratified set is exactly three —
#: `system_admin`, `billing_clerk`, `executive` (CONFIRMED 2026-08-07, and
#: `core/permissions.py` is the enforcement). So:
#:
#:     Owner · Admin  →  system_admin   ("full access to all modules + settings")
#:     Staff          →  billing_clerk  ("full on Premises/Accounts/Reads/
#:                                        Billing/Payments … no settings/users")
#:     Finance        →  executive      ("full on Finance + Reports")
#:
#: The example `07-endpoints.md` gives is the check on this table: *"a Finance
#: user's Templates page shows Finance, Payments and Collections runbooks and
#: not Platform."* Read `executive` down the four rows below and that is exactly
#: what comes back — `finance`, `payments`, `collections`, `billing`, and no
#: `platform`. `TC-RBS-19b` asserts that sentence rather than the dict.
#:
#: ⚠ **THIS IS A DEFAULT AND NEVER A PERMISSION.** It decides what a signed-in
#: staff member is SHOWN, not what they may call: every read route in this
#: module stays `AnyTenantRole` and the server refuses nothing on the strength
#: of this map. A narrower list here that leaked into the permission class would
#: turn a library filter into a 403 on a route `07-endpoints.md` §1 marks
#: *Staff reads*. `Runbook.visible_to_roles` overrides it per runbook, NULL
#: meaning *use this table* — an admin may widen (add a role) or narrow (drop
#: one), and the column holds the whole answer rather than a delta, so a
#: category's default moving later never silently re-widens a runbook an admin
#: deliberately narrowed.
ROLE_VISIBILITY_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    # Category                    Contract §5's last column      → roles
    "platform": ("system_admin",),  # —
    "onboarding_cutover": ("system_admin",),  # —
    "data_hygiene": ("system_admin", "billing_clerk"),  # + Staff
    "premises": ("system_admin", "billing_clerk"),  # + Staff
    "plans_rates": ("system_admin",),  # —
    "assets": ("system_admin", "billing_clerk"),  # + Staff
    "accounts": ("system_admin", "billing_clerk"),  # + Staff
    "reads": ("system_admin", "billing_clerk"),  # + Staff
    "billing": ("system_admin", "billing_clerk", "executive"),  # + Staff · Finance
    "collections": ("system_admin", "executive"),  # + Finance
    "payments": ("system_admin", "executive"),  # + Finance
    "finance": ("system_admin", "executive"),  # + Finance
    "work": ("system_admin", "billing_clerk"),  # + Staff
    "customer_portal": ("system_admin", "billing_clerk"),  # + Staff
    "business": ("system_admin",),  # —
    "data_sync": ("system_admin",),  # —
}


def roles_that_see(
    category: str, override: "list[str] | tuple[str, ...] | None" = None
) -> tuple[str, ...]:
    """The roles a runbook of this category is SHOWN to — `BR-RBS-024`, `RB-050`.

    `override` is `Runbook.visible_to_roles`: `None` means *take the category's
    default*, a list means *an admin set this runbook's own answer*. An override
    is stored whole rather than as a delta, for the reason
    `ROLE_VISIBILITY_BY_CATEGORY` gives.

    ⚠ **A `system_admin` IS NEVER REMOVED, EVEN BY AN OVERRIDE.** *Owner and
    Admin see every runbook* is the fixed half of the sentence and the widenable
    half is what follows it. Without this line an admin could narrow a runbook
    until nobody — including them — could find it again on any screen, and the
    only route back would be a database edit. Law 3: the unsafe option must be
    the one you type, and there is no way to type this one.

    An empty tuple is never returned: an unknown category falls back to
    system-admin-only, which is the closed direction.
    """
    if override is None:
        roles = ROLE_VISIBILITY_BY_CATEGORY.get(category, ("system_admin",))
    else:
        roles = tuple(str(role) for role in override)
    return tuple(dict.fromkeys(("system_admin", *roles)))


WORK_ITEM_SOURCE_FINDING = "finding"
WORK_ITEM_SOURCE_EXCEPTION = "exception"
WORK_ITEM_SOURCE_HUMAN_TASK = "human_task"
#: One table, three sources (`03-field-map.md` §5).
WORK_ITEM_SOURCE_KINDS = (
    WORK_ITEM_SOURCE_FINDING,
    WORK_ITEM_SOURCE_EXCEPTION,
    WORK_ITEM_SOURCE_HUMAN_TASK,
)

#: The seven tables, as the schema brief lists them. Kept here so
#: `migrations/0002_rls_force` and the isolation suite read one list.
TENANT_TABLES = (
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "work_items",
    "cutover_plans",
    "cutover_plan_items",
)


def _choices(values: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(value, value) for value in values]


class Runbook(models.Model):
    """One runbook available to the tenant — a Check or an Action, never both.

    `kind` is immutable after creation (`BR-RBS-001`) and `cap` has NO DEFAULT
    (`OQ-RBS-1731` is open on what the default should be): an Action therefore
    cannot be enabled until an admin types one. That is the safe shape — an
    answer to the question can only ever WIDEN it, never narrow it.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The runbook's address: `/runbooks/{key}`. Stable and unique per tenant.
    key = models.TextField()
    name = models.TextField()
    kind = models.TextField(choices=_choices(KINDS))
    category = models.TextField(choices=_choices(CATEGORIES))
    #: ⚠ jsonb, not text[] — B2 r24 departure 1. Tags help a SEARCH and nothing
    #: else, so no query needs array containment.
    tags = models.JSONField(default=list, blank=True)
    origin = models.TextField(choices=_choices(ORIGINS), default=ORIGIN_SHIPPED)
    template_key = models.TextField(null=True, blank=True)
    cloned_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    subject_type = models.TextField(choices=_choices(SUBJECT_TYPES))
    #: ⚠ NEVER the raw row (`BR-RBS-019`): read validation walks the METER-DAY,
    #: so 176,640 intervals become 1,840 records and a per-record savepoint
    #: stays cheap.
    unit_of_work = models.TextField()
    enabled = models.BooleanField(default=True)
    trigger_kind = models.TextField(choices=_choices(TRIGGER_KINDS), default=TRIGGER_MANUAL)
    cron = models.TextField(null=True, blank=True)
    event_kind = models.TextField(choices=_choices(EVENT_KINDS), null=True, blank=True)
    #: The TENANT's own timezone, as the notification schedule already does.
    timezone = models.TextField(default="UTC")
    #: REFUSES the run; never truncates (`BR-RBS-006`). Null until an admin
    #: types one — see the class docstring and `OQ-RBS-1731`.
    cap = models.IntegerField(null=True, blank=True)
    gate_mode = models.TextField(
        choices=_choices(GATE_MODES), default=GATE_APPROVE_EACH_RUN
    )
    current_version = models.IntegerField(default=1)
    #: ⚠ **WHO SEES THIS RUNBOOK — NULL MEANS *THE CATEGORY DECIDES*** (`RB-050`,
    #: `BR-RBS-024` clause 2, wave `D5`). An admin may widen or narrow it per
    #: runbook and the column then holds the WHOLE answer, never a delta, so a
    #: later change to `ROLE_VISIBILITY_BY_CATEGORY` cannot silently re-widen a
    #: runbook somebody deliberately narrowed. Read it through
    #: `roles_that_see()`, which is also where *Owner and Admin see every
    #: runbook* is kept true whatever an override says.
    #: ⚠ It is a VISIBILITY default, not a permission: every read route in this
    #: module is `AnyTenantRole` and refuses nothing on the strength of it.
    visible_to_roles = models.JSONField(null=True, blank=True)
    #: ⚠ **THE TRUST RATCHET'S STATE — `BR-RBS-036`, wave `E2`.** The version
    #: number whose dry run has been reviewed. An Action may run LIVE only while
    #: this equals `current_version`; an edit that mints a new version leaves it
    #: behind, and the runbook is dry-run only until one clean dry run is
    #: reviewed. Set to 1 when a runbook is added or cloned — the shipped
    #: definition is the one WE reviewed, and `BR-RBS-036` restricts an EDITED
    #: Action, not a fresh one.
    #: ⚠ **NOTHING RAISES IT AGAIN YET, AND THAT IS THE SAFE DIRECTION RATHER
    #: THAN AN OVERSIGHT.** The act that clears the ratchet is a person
    #: reviewing a clean dry run, which is `POST /runbooks/runs/{id}/approve` —
    #: `07-endpoints.md` row 12, wave `L`. Until it lands, an edited Action can
    #: only ever run dry, which is exactly what phase 1 promises anyway
    #: (*"nothing can be written: no writer is bound"*). `services.open_run` is
    #: the reader and refuses there, at the one door every run passes through,
    #: rather than at an HTTP route that does not exist yet.
    trusted_version = models.IntegerField(null=True, blank=True)
    #: ⚠ **WHAT THIS TENANT SET ITS INPUTS TO — `BR-RBS-042`, wave `T`.**
    #: `{parameter name: value}`, and **a name that is absent means *the
    #: declared default***. Nothing is backfilled and nothing is copied out of a
    #: definition into here: a tenant that has never touched an input has an
    #: empty document and runs exactly what the runbook shipped with.
    #:
    #: ⚠ **THE WORD `all` IS STORED AS THE WORD** (clause 1). A list written
    #: here at configure time freezes the domain: a utility that sets *all
    #: services* with Water and Sewer and enables Trash next month would be
    #: silently outside every runbook set to *all*, with nothing on any screen
    #: to see. `services.run_parameters()` expands it when the RUN starts and
    #: `BR-RBS-009` pins it there.
    #:
    #: ⚠ **NO COLUMN CAN HOLD THIS TO ITS RULES AND THAT IS WHY THE VALIDATION
    #: IS `services._validated_parameters`.** This is `jsonb`; a value naming a
    #: parameter the runbook does not declare, or a service the tenant does not
    #: sell, is refused there or it is not refused at all
    #: (`03-field-map.md` D-3, the same reasoning `Parameter` gives for money).
    #:
    #: ⚠ **IT IS THE TENANT'S HALF, LIKE `cap` AND `gate_mode`** — it travels
    #: into every version document through `services.settings_document()`, so an
    #: input change writes a version (`BR-RBS-038`), shows on the Activity tab,
    #: and drops the trust ratchet (`BR-RBS-036`) with no code of its own.
    parameters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "runbooks"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_runbooks_tenant_key"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category"], name="ix_runbooks_category"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.key} · {self.kind}"


class RunbookVersion(models.Model):
    """An immutable snapshot of the definition. Every edit makes a new one.

    A run stores the version it used, so a later edit never rewrites history
    (`BR-RBS-038`); `TC-RBS-13` goes red on a definition read live at display
    time.

    ⚠ `money` AND `percent` PARAMETERS LIVE INSIDE `definition`, WHERE NO COLUMN
    TYPE HOLDS THEM TO 4 AND 6 DECIMALS. There is no `NUMERIC(18,4)` inside a
    `jsonb` document, so the precision is the parameter renderer's and the
    validator's to enforce, and a float written in there is a hard-rule-2 breach
    **no database constraint can see** (`03-field-map.md` D-3). Named here so no
    build lane assumes the database is enforcing it.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    runbook = models.ForeignKey(Runbook, on_delete=models.CASCADE, related_name="versions")
    version = models.IntegerField()
    definition = models.JSONField(default=dict)
    #: ⚠ **WHAT CHANGED, IN A CLERK'S WORDS — `DEF-RBS-4285`'s ENGINE HALF, WAVE
    #: `E2`.** `RBS-004.7` draws four change summaries (*Cap raised to 400* ·
    #: *Paused* · *Schedule set to Mondays* · *Added from templates*) and this
    #: table held only a `jsonb` document. **A diff of two documents is not
    #: those four sentences**, and computing one at render time would put screen
    #: copy in Python and out of the eleven catalogues. So the WRITER records
    #: what it did, as a machine-readable list of `{field, from, to}` changes,
    #: and the Activity tab composes the sentence from it in the reader's
    #: language.
    #: ⚠ **A LIST OF FACTS, NEVER A SENTENCE.** *Cap raised to 400* is English;
    #: `[{"field": "cap", "from": 100, "to": 400}]` is a fact eleven catalogues
    #: can each say in their own language, which is B14 rule 35. The one word
    #: that is not a field change — a runbook's FIRST version — carries
    #: `[{"field": "origin", "to": "shipped"}]` and the screen says *Added from
    #: templates*.
    summary = models.JSONField(default=list, blank=True)
    changed_by = models.ForeignKey(  # ⚠ reviewed cross-module FK runbooks → identity (B2 r24)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="changed_by",
        related_name="+",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "runbook_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "runbook", "version"], name="uq_runbook_versions_number"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.runbook_id} v{self.version}"


class RunbookRun(models.Model):
    """One run. The version is PINNED at start and never re-read.

    `report` is the block list **as composed when the run closed**, and it is
    frozen there: a later change to a report function never alters a past
    result. Without that, a result screen reads differently every time the code
    moves — and the thing a regulator asks for is gone.

    NOT PARTITIONED, and unlike `integration_run` that is a decision rather than
    an oversight: this table takes one row per RUN, not per attempt. The
    per-record volume lives in `RunbookRunRecord`. A tenant at the top of the
    ICP (40,000 accounts) running nineteen scheduled runbooks daily writes about
    7,000 rows a year. B2 Addendum r24 records it.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    runbook = models.ForeignKey(Runbook, on_delete=models.PROTECT, related_name="runs")
    version = models.IntegerField()
    mode = models.TextField(choices=_choices(MODES), default=MODE_DRY)
    trigger = models.TextField(choices=_choices(TRIGGER_KINDS), default=TRIGGER_MANUAL)
    #: The landed batch that started it — named as the scope on the run header.
    event_ref = models.TextField(null=True, blank=True)
    #: The caller's run when this is a REQUIRED Check (`BR-RBS-027`): if it
    #: fails, every later step of the caller reads "Never reached".
    parent_run = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    status = models.TextField(choices=_choices(RUN_STATUSES), default=RUN_STATUS_QUEUED)
    #: The pinned id list, frozen at start (`BR-RBS-009`) — a run acts on the
    #: set it saw, never on the set as it is now.
    scope_fingerprint = models.TextField(null=True, blank=True)
    #: Per-outcome counts, INCLUDING the outcomes that have no record row —
    #: that is what makes a volume runbook honest (`BR-RBS-035`).
    counts = models.JSONField(default=dict, blank=True)
    report = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(  # ⚠ reviewed cross-module FK runbooks → identity (B2 r24)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="approved_by",
        related_name="+",
    )
    #: Must MATCH the plan as it stands, or the approval CONFLICTS
    #: (`BR-RBS-005`, `TC-RBS-8`) — approving "812 to send" and acting on 900 is
    #: the failure this column exists to refuse.
    approved_count = models.IntegerField(null=True, blank=True)
    stopped_by = models.ForeignKey(  # ⚠ reviewed cross-module FK runbooks → identity (B2 r24)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="stopped_by",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "runbook_runs"
        indexes = [
            models.Index(
                fields=["tenant", "runbook", "-started_at"], name="ix_runbook_runs_recent"
            ),
            models.Index(fields=["tenant", "status"], name="ix_runbook_runs_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.runbook_id} · {self.status}"


class RunbookRunRecord(models.Model):
    """One record examined: THE PLAN, THEN THE OUTCOME, IN THE SAME ROW.

    *What did it say it would do versus what it did* is the audit. Two tables
    would make that comparison a join, and the audit becomes a query nobody
    writes. A Check's FINDING is a record whose `planned_action` is `report` —
    one shape, one query, one CSV writer, and no second renderer.

    ⚠ `UNIQUE (tenant, idempotency_key)` IS WHAT MAKES A RETRY SAFE, and it is
    the whole of hard rule 6 for this module. Worked from the fixture: running
    the collections ladder twice queues **248 notices in total, not 496**, and
    the second Done screen reads *0 queued* while naming the 248 already sent.
    `TC-RBS-4` goes red with the key removed. It is a UNIQUE INDEX and not
    application code **on purpose** — a retry arrives concurrently, and two
    workers each finding no row and each writing one is exactly the race an
    index refuses and a `SELECT`-then-`INSERT` does not.

    ⚠ A VOLUME RUNBOOK DOES NOT WRITE A ROW PER SUBJECT (`BR-RBS-035`). Read
    validation over 80,000 meter-days writes **38** rows here — 31 estimated, 7
    queued — and a count of 80,000 in `RunbookRun.counts`.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    run = models.ForeignKey(RunbookRun, on_delete=models.CASCADE, related_name="records")
    subject_type = models.TextField(choices=_choices(SUBJECT_TYPES))
    #: ⚠ THE ID OF ANOTHER MODULE'S ROW, READ THROUGH A SEAM — deliberately NOT
    #: a foreign key. See the module docstring and B2 Addendum r24.
    subject_id = models.UUIDField(null=True, blank=True)
    #: Written at EVALUATION, before any act (`BR-RBS-004`).
    planned_action = models.TextField()
    #: The rule that decided it, in words a clerk can read (`BR-RBS-010`).
    decided_by_rule = models.TextField(null=True, blank=True)
    #: Written AFTER the act.
    outcome = models.TextField(null=True, blank=True)
    #: Plain language. No rule id reaches a clerk (B14 rule 32).
    reason = models.TextField(null=True, blank=True)
    #: ⚠ A FAILURE WITH NO ROUTE IS A DEFECT IN THE RUNBOOK (`BR-RBS-011`,
    #: `TC-RBS-14`) — a finding a clerk cannot act on is a finding we should not
    #: have shown them.
    fix_route = models.TextField(null=True, blank=True)
    decision = models.TextField(null=True, blank=True)
    decided_by = models.ForeignKey(  # ⚠ reviewed cross-module FK runbooks → identity (B2 r24)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="decided_by",
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    #: Stored to 4 decimals, DISPLAYED to 2 (hard rule 2). Never a float.
    amount = money_field(null=True, blank=True)
    #: ⚠ THE CURRENCY PARTNER hard rule 2 REQUIRES — the field map's D-2 gap,
    #: closed in B2 Addendum r24. NULLable because most record rows carry no
    #: amount at all (a missing-read finding has nothing to denominate); **where
    #: `amount` is not null, `currency` is not null either.** Deriving it from
    #: the tenant was rejected: a tie-out compares OUR figure with THEIRS, and a
    #: tenant currency change would silently re-denominate every historical row.
    currency = models.CharField(max_length=3, null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    #: ⚠ **HOW THIS KEY IS COMPOSED IS UNRESOLVED — `DEF-RBS-4246`, `OQ-RBS-1737`
    #: — AND WAVE A DELIBERATELY COMPOSES NONE.** `BR-RBS-008` and
    #: `03-field-map.md` §4 say *"runbook + run + record + action kind"*. **Three
    #: other statements need the RUN out of it**: the same field map four lines
    #: later (*"the second run of the ladder on the same day queues nothing,
    #: because every key it computes is already in this index"*), `04-flows.md`,
    #: and `TC-RBS-4`'s worked figure — **248 notices in total, not 496**. With
    #: the run in the key a second run mints a fresh key for every record and
    #: the guarantee is void **exactly when it is needed**, because a retry that
    #: matters IS a second run.
    #: ⚠ **AND THE OBVIOUS FIX IS ALSO WRONG.** Dropping the run and keeping
    #: *runbook + record + action kind* means the ladder can never send the same
    #: account the same notice twice, so a customer past due in October is
    #: written to **never** because they were written to in September. The
    #: honest key probably carries a **period or a tier**, and that is engine
    #: design with the ladder in front of it — wave L, not this migration.
    #: **The INDEX below is correct under every candidate answer**, which is why
    #: it is laid now and the composition is not. If you are about to write a
    #: `_key(...)` helper here: read `OQ-RBS-1737` first. The cost of guessing
    #: is in the field map's own words — *496 notices instead of 248, and no
    #: test that can see it*.
    idempotency_key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "runbook_run_records"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"], name="uq_runbook_run_records_idem"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "run"], name="ix_runbook_records_run"),
            models.Index(
                fields=["tenant", "subject_type", "subject_id"], name="ix_runbook_records_subject"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.subject_type} · {self.planned_action}"


class WorkItem(models.Model):
    """Everything waiting on a person, whatever raised it — UPSERTED BY FINGERPRINT.

    `UNIQUE (tenant, fingerprint)` is what the upsert needs, and it is
    load-bearing: the daily pre-bill sweep raises the same missing read for
    thirty days, and that must be **one item ageing, not thirty items**.
    `TC-RBS-10` goes red on an INSERT instead of an upsert. The age a clerk sees
    is `created_at`, never the last sighting.

    ⚠ THE ENGINE WRITES THIS TABLE, NEVER A RUNBOOK — see the module docstring.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    source_kind = models.TextField(choices=_choices(WORK_ITEM_SOURCE_KINDS))
    #: Provenance back to the run that raised it. NULL for a human task, which
    #: is why it is nullable rather than required.
    source_run = models.ForeignKey(
        RunbookRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_items"
    )
    fingerprint = models.TextField()
    title = models.TextField()
    weight = models.IntegerField(default=0)
    subject_ref = models.TextField(null=True, blank=True)
    fix_route = models.TextField(null=True, blank=True)
    owner_user = models.ForeignKey(  # ⚠ reviewed cross-module FK runbooks → identity (B2 r24)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="owner_user_id",
        related_name="+",
    )
    due_on = models.DateField(null=True, blank=True)
    status = models.TextField(default="open")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_items"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "fingerprint"], name="uq_work_items_fingerprint"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-weight"], name="ix_work_items_list"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return self.title


class CutoverPlan(models.Model):
    """A go-live plan, one per cutover.

    `status` open-or-closed is what ORDERS the library (`BR-RBS-026`):
    Onboarding & Cutover sorts first while a plan is open and last once it
    closes. Nothing else in the catalogue behaves that way, which is why the
    category exists at all.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()
    go_live_on = models.DateField(null=True, blank=True)
    status = models.TextField(default="open")
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cutover_plans"
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_cutover_plans_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return self.name


class CutoverPlanItem(models.Model):
    """A plan's task. A NULL `runbook_key` is a human task the engine never performs.

    ⚠ `owner` IS `text` AND NOT A USER REFERENCE, and that is decided rather
    than left over (`03-field-map.md` D-7, B2 r24 departure 3). Every other
    actor column in these seven tables is a uuid because each records **one of
    our users performing an act**; this one records **who is responsible for a
    task**, and on a cutover that is very often the implementer — a person with
    no row in `users` at all. A uuid would refuse the commonest case. Text is
    the honest superset and it is the reversible direction: adding
    `owner_user_id` beside it later is an addition, while narrowing text → uuid
    would be a data migration over rows already typed by hand.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    plan = models.ForeignKey(CutoverPlan, on_delete=models.CASCADE, related_name="items")
    seq = models.IntegerField()
    title = models.TextField()
    owner = models.TextField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    runbook_key = models.TextField(null=True, blank=True)
    #: The run whose result is this item's evidence.
    last_run = models.ForeignKey(
        RunbookRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    #: The run id and its figures, stored ON the item — "Evidence attached ·
    #: $1,204.05 variance" — so an item reads correctly after the run is pruned.
    evidence_ref = models.TextField(null=True, blank=True)
    status = models.TextField(default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cutover_plan_items"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "plan", "seq"], name="uq_cutover_plan_items_seq"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.seq}. {self.title}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01; 17-runbooks/03-field-map.md §1-§7 + B2 r24)
# generated: 2026-09-06 by the CR-075 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave A) E=n/a(no screen — stated in the plan) F✔ G✔ H✔(the two migrations are 🔒 and carry HUMAN-REVIEW-PENDING)
# gates: pytest tests/test_us_rbs_041_module.py · tests/test_us_rbs_041_pg.py · G115
# exceptions: `tags` is JSONField not ArrayField (SQLite; B2 r24 departure 1) ·
#             `subject_id` carries no FK (twelve possible targets; r24) ·
#             `cutover_plan_items.owner` is text (r24 departure 3)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
