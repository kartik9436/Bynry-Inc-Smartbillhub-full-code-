# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — the five tables, and why not one.
#           Screens: S8 · S141 · S142 (the read models that draw these rows)
# Rules:    BR-INT-003 (no credential is ever rendered back, logged or put in an
#           audit payload — masked refs only) · BR-INT-025 (a credential is
#           versioned, never updated; exactly one active, enforced by the
#           database) · BR-INT-026 (production and sandbox are two rows) ·
#           BR-INT-032 (a foreign name for one of our things is a ROW, UNIQUE on
#           the external side) · BR-INT-036 (a consent is revoked, never deleted
#           — OPEN, OQ-INT-1482: the table exists and nothing writes it) ·
#           BR-INT-039 (every attempt is a durable, append-only record with a
#           trace id) · CLAUDE.md hard rule 1 (RLS FORCE on every tenant table —
#           migrations/0002_rls_force) · hard rule 4's shape (a finished run is
#           never updated; corrections are new rows)
# Tests:    06-backend/tests/test_us_int_014_tables.py (SQLite) ·
#           06-backend/tests/test_us_int_014_pg.py (PostgreSQL: the EXCLUDE, the
#           isolation probe, the append-only trigger)
# Impacts:  apps/integrations/migrations/0001_initial.py · 0002_rls_force.py ·
#           core/partitioning.py (integration_run joins the yearly registry) ·
#           04-docs/02-decisions/02-database-design-brief.md §2 Module:
#           integrations + Addendum r22 (anchored FIRST — C34, US-INT-014 TC-7)
# ───────────────────────────────────────────────────────
"""integrations models — five tables, one module, no secret where a reader can see it.

FIVE TABLES AND WHY NOT ONE (US-INT-014)
-----------------------------------------
* `integration_connection` — rarely changes. **Holds no secret material**, so it
  is safe to `SELECT *`, to log, and to put in an audit payload. A gate asserts
  it: no `EncryptedTextField` and no column whose name says `secret`, `token`,
  `password` or `payload` may ever be added here (US-INT-014 TC-3).
* `integration_credential` — versioned, never overwritten. Rotation writes
  version n+1 and deactivates n; **exactly one active row per connection is
  enforced by the DATABASE** (`EXCLUDE … WHERE (is_active)` on PostgreSQL, a
  partial unique index on SQLite), not by application code. Rollback
  re-activates the previous version in one row. The hint (`••••3F9A`) is
  display only and is never the secret.
* `integration_run` — constantly. Append-only once finished, partitioned
  YEARLY on `started_at` through `core/partitioning.py`, carrying the eight
  characters of trace id a clerk reads down the phone. Five counts, seven
  outcomes. `provider_error` is its own column because it is the one column
  that can carry another tenant's words out of a provider's message.
* `integration_target_reference` — their word for our thing. UNIQUE on the
  EXTERNAL side on purpose: one of their words means exactly one of ours, and
  two of theirs may share one of ours (`ACHCHECK` and `ACHSAVINGS` both mean
  *bank transfer*). Added BESIDE `ledger_accounts.qbo_ref` / `.xero_ref` until
  `OQ-INT-1480` rules on retiring them; no third vendor column is ever added.
* `integration_consent` — conditional on `OQ-INT-1482`. In the schema so that
  the feature, if ruled in, costs rows and not a migration; **nothing writes it
  until the question is ruled**, and rows are revoked, never deleted.

⚠ THE CREDENTIAL TABLE IS SEPARATE FROM THE CONNECTION TABLE ON PURPOSE. *"Audit
is a consumer of the connection table, never of the credential table."* A lane
that merges them has made every audit read touch encrypted secrets.

⚠ THE MANIFEST IS NOT A TABLE. Provider identity, category, disposition, fields
and operations are code data in `apps/integrations/manifests/` (US-INT-013);
`provider_key` here names one of them. Adding a provider adds a manifest and no
migration (BR-INT-037).

Two vendors, recorded honestly (the same posture as `apps/audit/models.py`):
on PostgreSQL `integration_run` is a partitioned parent with an append-only
trigger and every table carries RLS FORCE; on the SQLite test database the
plain tables stand, the one-active guard is a partial unique index, and the
PostgreSQL-only guarantees are asserted in `tests/test_us_int_014_pg.py` and
never faked.

Write path: `apps/integrations/services.py` and nothing else (B1). Reads:
`apps/integrations/selectors.py`.
"""

from django.db import models

from apps.integrations.registry import MAPPING_ENTITY_TYPES
from core import dbfields
from core.crypto import EncryptedTextField

# ── closed vocabularies (03-field-map.md §5) ────────────────────────────────

ENVIRONMENT_PRODUCTION = "production"
ENVIRONMENT_SANDBOX = "sandbox"
ENVIRONMENTS = (ENVIRONMENT_PRODUCTION, ENVIRONMENT_SANDBOX)

#: The five connection states. *Reading from us* is NOT a sixth value — it is a
#: computed display state (08-screen-layouts.md S8; selectors.display_state).
STATUS_NOT_SET_UP = "not_set_up"
STATUS_UNTESTED = "untested"
STATUS_WORKING = "working"
STATUS_NOT_WORKING = "not_working"
STATUS_OFF = "off"
STATUSES = (STATUS_NOT_SET_UP, STATUS_UNTESTED, STATUS_WORKING, STATUS_NOT_WORKING, STATUS_OFF)

CADENCE_NIGHTLY = "nightly"
CADENCE_HOURLY = "hourly"
CADENCE_MANUAL = "manual"
CADENCES = (CADENCE_NIGHTLY, CADENCE_HOURLY, CADENCE_MANUAL)

RUN_DIRECTION_OUTBOUND = "outbound"
RUN_DIRECTION_INBOUND = "inbound"
RUN_DIRECTION_INBOUND_READ = "inbound_read"
RUN_DIRECTIONS = (RUN_DIRECTION_OUTBOUND, RUN_DIRECTION_INBOUND, RUN_DIRECTION_INBOUND_READ)

#: ⚠ **THE SIXTH WORD, ADDED 2026-09-06 BY THE `CR-069` WAVE M LANE, AND IT IS
#: NOT `manual` (`BR-INT-048`, `C15`).** `manual` means *a person pressed Run
#: it now and a job was queued*; `inline` means *no job row exists at all* —
#: the call went out inside the request a clerk was already waiting on. The
#: distinction is the whole of `C15`: an inline operation has a latency budget
#: and no queue, so a screen reading these rows must not offer to poll one.
#: **One row per SEARCH SESSION**, not one per keystroke — fourteen lookups and
#: one pick is one row (`US-INT-042` TC-1), because a row per keystroke would
#: write fourteen partitioned rows to record one thing a clerk did.
RUN_TRIGGERS = ("manual", "scheduled", "dispatcher", "webhook", "partner", "inline")

#: ── 2026-09-17 · `CR-115-BRC05` R31 · `BR-INT-074` AS AMENDED ───────────────
#: **WHAT A RUN WAS ALLOWED TO CHANGE.** PO, verbatim: *"i dont have Run button
#: here"* — and the control that answers it offers two things rather than one,
#: `Preview` and `Apply`, because one button that does the dangerous thing is
#: how a clerk finds out what a reconciliation would have done by letting it
#: happen.
#:
#: ⚠ **A PREVIEW IS STILL AN ATTEMPT, SO IT STILL WRITES A RUN ROW
#: (`BR-INT-039`).** That is not a contradiction of *a preview writes nothing*:
#: the rule is about the rows being reconciled — the keys, the address fields,
#: the verified stamp — and this column is the record that somebody looked.
#: Without it a preview is invisible in RECENT ACTIVITY and the question *who
#: ran this and what did it change* has no answer for half the runs.
#:
#: `NULL` on every run that has no such choice to make, which is every run in
#: this product today except the parcel reconciliation. A default of `apply`
#: would have been the unsafe option arriving without anybody typing it
#: (hard-won law 3).
RUN_MODE_PREVIEW = "preview"
RUN_MODE_APPLY = "apply"
RUN_MODES = (RUN_MODE_PREVIEW, RUN_MODE_APPLY)

OUTCOME_QUEUED = "queued"
OUTCOME_RUNNING = "running"
OUTCOME_SUCCEEDED = "succeeded"
OUTCOME_PARTIAL = "partial"
OUTCOME_FAILED = "failed"
OUTCOME_UNCONFIRMED = "unconfirmed"
OUTCOME_INDETERMINATE = "indeterminate"
#: ⚠ **THE EIGHTH WORD, ADDED 2026-09-05 BY THE `CR-069` WAVE F LANE, AND IT IS
#: NOT A SYNONYM FOR ANY OF THE SEVEN ABOVE.** `BR-INT-024` says a skipped
#: window is RECORDED as skipped and never silent, and `US-INT-022` §5 asks for
#: an `outcome = skipped`-shaped row — hedged, because the vocabulary was seven.
#: There was no honest word for it: a run we never dialled has `failed = 0`, so
#: `outcome_for`'s arithmetic returned **`succeeded`** for it, and the screen
#: would have read *93 of 93* over a batch nobody sent. `unconfirmed` is the
#: provider's silence, `indeterminate` is *we asked and do not know the answer*
#: (`BR-INT-052`), and this one is **we did not ask**, which is a different fact
#: and the only one a clerk can act on.
OUTCOME_SKIPPED = "skipped"
OUTCOMES = (
    OUTCOME_QUEUED,
    OUTCOME_RUNNING,
    OUTCOME_SUCCEEDED,
    OUTCOME_PARTIAL,
    OUTCOME_FAILED,
    OUTCOME_UNCONFIRMED,
    OUTCOME_INDETERMINATE,
    OUTCOME_SKIPPED,
)
#: An outcome that means the run is over. `queued` and `running` are not.
FINISHED_OUTCOMES = frozenset(OUTCOMES) - {OUTCOME_QUEUED, OUTCOME_RUNNING}

#: ONE list, owned by the registry (wave D, 2026-09-03): a manifest's
#: vocabulary and this column's choices are validated against the same tuple.
TARGET_ENTITY_TYPES = MAPPING_ENTITY_TYPES

#: CR-173-BRC10 — the credential slots. `primary` is every connector's own
#: secret; a manifest field group (`registry.Field.group`) that carries a
#: secret stores it under the group's name. See `IntegrationCredential.slot`.
CREDENTIAL_SLOT_PRIMARY = "primary"


def _choices(values: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(value, value) for value in values]


class IntegrationConnection(models.Model):
    """One provider, one environment, one tenant — and NO secret material.

    `config` holds NON-SECRET fields only: host, port, send-from address,
    allowlist, budget override, authority grants. A password, key or token
    lives in `IntegrationCredential.payload_enc` and nowhere else. Two
    environments are two rows (BR-INT-026): the UNIQUE below is the sandbox /
    production mix-up that ranks first in the design's failure list, made
    impossible.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The manifest key (`email_smtp`). Code data, not a foreign key — the
    #: registry refuses an unknown key at the service boundary.
    provider_key = models.TextField()
    label = models.TextField(null=True, blank=True)
    environment = models.TextField(choices=_choices(ENVIRONMENTS))
    status = models.TextField(choices=_choices(STATUSES))
    enabled = models.BooleanField(default=True)
    cadence = models.TextField(choices=_choices(CADENCES), default=CADENCE_MANUAL)
    next_run_at = models.DateTimeField(null=True, blank=True)  # NULL when cadence = manual
    config = models.JSONField(default=dict, blank=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_ok = models.BooleanField(null=True, blank=True)
    last_test_text = models.TextField(null=True, blank=True)  # one sentence a clerk can read
    connected_by = models.ForeignKey(  # ⚠ reviewed cross-module FK integrations → identity (B2 r22)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="connected_by",
        related_name="+",
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_connection"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider_key", "environment"],
                name="uq_integration_connection_key_env",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "provider_key"], name="ix_intg_connection_provider"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.provider_key} · {self.environment}"


class IntegrationCredential(models.Model):
    """A versioned secret. Written by `services.record_credential`, read by an
    adapter at use time, and never handed to a screen or a log.

    `payload_enc` is an `EncryptedTextField` (AES-256-GCM, key id in the
    ciphertext, `core/crypto.py`); equality lookups on it are refused by the
    field itself. `blind_index` exists for ISSUED secrets only — a key WE hand a
    partner and must find again without decrypting every row (US-INT-040).
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.PROTECT,
        db_column="connection_id",
        related_name="credentials",
    )
    version = models.IntegerField()
    is_active = models.BooleanField()
    #: CR-173-BRC10 — **WHICH SECRET OF THE CONNECTION THIS IS.** `primary` is
    #: the one every connector has always had — the vendor's password, or the
    #: key we issue. A second slot exists because New World / Logos holds BOTH
    #: a key we issue (the City dials us) AND the password of the City's SFTP
    #: folder (we dial them), and one-active-per-connection would have made
    #: storing the password REVOKE the partner's key (decision log 2026-10-07).
    #: The one-active guard is per (connection, slot) — migration `0015`.
    slot = models.TextField(default=CREDENTIAL_SLOT_PRIMARY)
    payload_enc = EncryptedTextField(crypto_context="integration_credential.payload_enc")
    blind_index = models.TextField(null=True, blank=True)
    masked_hint = models.TextField()  # "••••3F9A" — display only, never the secret
    expires_at = models.DateTimeField(null=True, blank=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    #: BR-INT-042 (wave H) — the tenant's own calendar date this credential was
    #: last warned about, so the sweep says it once a day and never twice.
    #:
    #: ⚠ **IT IS ON THE CREDENTIAL AND NOT ON THE CONNECTION, AND THAT CHOICE
    #: IS WHAT MAKES RE-AUTHORISING NEED NO RESET AT ALL.** A warning is about
    #: one secret's lapse date, so when `record_credential` writes v(n+1) the
    #: new row arrives with this NULL and its own later `expires_at` — the
    #: warning stops because the thing it was about is no longer the active
    #: credential, not because anybody remembered to clear a flag. Had it lived
    #: on the connection, every re-authorisation would have owed a second write
    #: that a lane could forget, and forgetting it would leave a utility being
    #: told to re-authorise a credential it had already replaced.
    expiry_warned_on = models.DateField(null=True, blank=True)
    #: CR-110-BRC04 — **WHICH OF OUR APIS THIS KEY MAY CALL.** A list of
    #: operation names off the connection's own manifest; the door refuses an
    #: operation that is not in it.
    #:
    #: ⚠ **EMPTY GRANTS NOTHING, AND THAT IS THE OPPOSITE OF WHAT THE DRAWING
    #: SAYS.** The blueprint puts *"Leave blank for everything the key allows"*
    #: under the Scope box — the widest permission as the default — and
    #: `CR-110-BRC04` decision 5 refuses it under hard-won law 3: the unsafe
    #: option must be the one you type. `machine_auth.issue_key` will not mint
    #: a key with nothing ticked, so a row here is never legitimately empty;
    #: the default exists so that a row written by some future path that
    #: forgets it is powerless rather than omnipotent.
    #:
    #: ⚠ **NOT A SECRET, AND IT LIVES ON THE CREDENTIAL ANYWAY.** A scope
    #: belongs to ONE key, not to the connection: replacing a key is the moment
    #: a partner's permissions are meant to be reconsidered, and a scope on the
    #: connection would silently carry the old key's reach onto the new one.
    scope = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_credential"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "version"], name="uq_integration_credential_version"
            ),
            # The ONE-ACTIVE guard is vendor-specific and lives in migration
            # 0001: an EXCLUDE constraint on PostgreSQL (the shape the design
            # names), a partial unique index on SQLite. Not declared here, so
            # the two vendors cannot end up with two guards on one.
        ]
        indexes = [
            models.Index(fields=["tenant", "blind_index"], name="ix_intg_credential_blind"),
        ]


class IntegrationRun(models.Model):
    """Every attempt is a durable record, not a log line (BR-INT-039).

    Composite primary key `(tenant_id, started_at, id)` because on PostgreSQL
    this is a partitioned parent ranged on `started_at`, and the partition key
    must be inside every unique constraint — the shape `audit_log` already has.
    `started_at` is therefore NOT NULL (a NULL RANGE key routes to no
    partition); a queued run's `started_at` is the moment it was queued and
    `finished_at` is the honest marker of completion.

    Five counts (`attempted · succeeded · failed · skipped · changed`) and seven
    outcomes. BR-INT-018: an outcome is `succeeded` only when the arithmetic
    holds AND the far end confirmed a count; otherwise `unconfirmed`. The rule
    is applied by `services.finish_run`, never by a caller typing the word.

    Append-only once `finished_at` is set — a trigger refuses UPDATE and DELETE
    on PostgreSQL (migration 0001); the service refuses on every vendor.

    `items` (wave C, migration 0003) is BR-INT-040 made storable: *"per-item
    results, never a batch boolean"*. It holds the items the run could not do
    — the seven addresses a clerk has to go and fix — and not the ones it
    could.
    """

    pk = models.CompositePrimaryKey("tenant_id", "started_at", "id")
    id = models.UUIDField(default=dbfields.uuid7, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.PROTECT,
        db_column="connection_id",
        related_name="runs",
    )
    operation = models.TextField()  # C1: which of the provider's operations
    job_id = models.UUIDField(null=True, blank=True)  # the core/jobs record
    direction = models.TextField(choices=_choices(RUN_DIRECTIONS))
    trigger = models.TextField(choices=_choices(RUN_TRIGGERS))
    #: ⚠ **`preview` OR `apply`, AND NULL WHERE THE OPERATION HAS NO SUCH
    #: CHOICE** (`CR-115-BRC05` R31). See `RUN_MODES` above.
    mode = models.TextField(choices=_choices(RUN_MODES), null=True, blank=True)
    #: ⚠ **WHO PRESSED IT — AND `trigger` ALREADY SAYS *WHETHER* A PERSON DID.**
    #: `trigger="scheduled"` is the schedule and `trigger="manual"` is a person,
    #: so a second column spelling `schedule | person` would be one fact in two
    #: places and the second is the one that goes stale (`DEF-INT-5589`'s shape,
    #: and this file's own note on `request_key` vs `input_hash`). What the
    #: existing columns genuinely cannot answer is **which** person, and that is
    #: what this holds: *"a schedule did it"* and *"D. Whitfield did it at 4pm"*
    #: are different answers to the question somebody asks a week later.
    #: NULL on a scheduled run, and NULL on every run nobody has named.
    started_by_name = models.TextField(null=True, blank=True)
    attempted = models.IntegerField(default=0)
    succeeded = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    changed = models.IntegerField(default=0)  # the fifth count: "1,240 read · 6 revised"
    outcome = models.TextField(choices=_choices(OUTCOMES), null=True, blank=True)
    summary = models.TextField(null=True, blank=True)  # plain language, no rule id
    #: ⚠ Another tenant's data can arrive here from a provider's message. It is
    #: scrubbed by the adapter and rendered only on S142, to the owning tenant.
    provider_error = models.TextField(null=True, blank=True)
    input_hash = models.TextField(null=True, blank=True)  # file in: computed BEFORE parse
    #: ⚠ **THE KEY WE MINT BEFORE THE REQUEST LEAVES** (`BR-INT-020`,
    #: `BR-INT-052`, wave K migration 0007). Its own column rather than a second
    #: use of `input_hash`, and the reason is on the SCREEN: S142 labels
    #: `input_hash` *Content hash* — a fact about a file that ARRIVED — and
    #: putting an outbound request key behind that label would be a lie a clerk
    #: reads. They are also computed at opposite ends of a call: one from bytes
    #: we received, one from a period and a target before anything is sent.
    #: Set only for an operation the manifest marks `mutates_partner_state`;
    #: NULL everywhere else, which is what makes the duplicate lookup cheap.
    request_key = models.TextField(null=True, blank=True)
    artifact_link = models.TextField(null=True, blank=True)
    #: ⚠ THE ITEMS THIS RUN COULD NOT DO — never the ones it could (wave C,
    #: US-INT-020). `[{ref, detail, outcome, provider_text}]`, failed and
    #: skipped only, capped at `services.ITEM_CAP`. A run of 93 messages with
    #: seven refusals stores SEVEN rows, because the 86 that went are already
    #: per-item rows in the notification queue and duplicating them here would
    #: cost 720,000 runs a year × 93 items for nothing. `attempted -
    #: len(items)` is not the arithmetic to read: what was omitted for the cap
    #: is `failed + skipped - len(items)`, and the screen says so in words.
    items = models.JSONField(default=list, blank=True)
    trace_id = models.TextField()  # the eight characters support searches by
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integration_run"
        indexes = [
            models.Index(
                fields=["tenant", "connection", "operation", "-started_at"],
                name="ix_intg_run_latest_per_op",
            ),
            models.Index(fields=["tenant", "trace_id"], name="ix_intg_run_trace"),
            models.Index(fields=["tenant", "input_hash"], name="ix_intg_run_input_hash"),
            #: The duplicate lookup for a partner-state write — the same shape
            #: as the content-hash index one line up, and narrowed by
            #: connection at the query (`fetch.previous_request`).
            models.Index(fields=["tenant", "request_key"], name="ix_intg_run_request_key"),
        ]


class IntegrationTargetReference(models.Model):
    """Their word for one of our things — a ROW, never a column (BR-INT-032).

    `entity_id` names one of our rows (a ledger account, a route); when the
    mapping is to an ENUM value (a tender, a reversal reason) it is NULL and
    `local_value` carries our value instead. The UNIQUE is on the EXTERNAL side:
    `ACHCHECK` means exactly one of ours, and `ACHSAVINGS` may mean the same one.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    target_key = models.TextField()  # which outside system: "qbo" | "xero" | "kiosk" …
    entity_type = models.TextField(choices=_choices(TARGET_ENTITY_TYPES))
    entity_id = models.UUIDField(null=True, blank=True)
    local_value = models.TextField(null=True, blank=True)
    external_value = models.TextField()  # "001.100.51200" | "ACHCHECK" | "R01"

    class Meta:
        db_table = "integration_target_reference"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "target_key", "entity_type", "external_value"],
                name="uq_integration_target_ref_external",
            ),
        ]


class IntegrationRateLimit(models.Model):
    """How many calls a minute a partner may make — one row per connection AND per operation.

    CR-110-BRC04, PO 2026-09-16: *"keep the limit in database so if we want to
    change it later it is easy to do"*.

    ⚠ **A ROW PER OPERATION, NOT ONE NUMBER PER CONNECTOR, AND THE BLUEPRINT
    GIVES THE REASON ON ITS PAGE 17:** *"a larger utility buys a larger quota.
    So the limit cannot live where the operation lives. It is a row per
    connection and per operation, with the manifest carrying the default that
    provisioning copies in."* A quota is a commercial fact about ONE utility's
    agreement, so it cannot live on the manifest, which is code data shared by
    every tenant; and one number for a whole connector would give a partner
    permitted six hundred meter readings a minute six hundred refunds a minute
    for free.

    ⚠ **DISPLAY ONLY — THERE IS NO CLERK WRITE PATH TO THIS TABLE AND THAT IS
    THE RULING, NOT AN OMISSION.** PO, same day: *"so wecant allow clark to
    reset it"*. The blueprint's own line agrees — *"78 operation rows across 56
    screens, display only"*. `services.ensure_rate_limits` seeds a row from the
    manifest default when a connection is made; nothing in `api.py` updates
    one. A clerk who could raise their own ceiling is not protected by it.

    ⚠ **THE VALUE HERE IS A CEILING AND NOT A COUNT.** What has been USED is
    deliberately not built (`CR-110-BRC04`, struck under the PO's *"thats
    it"*); a lane that adds a `used` column here has widened a ruling that did
    not mention it.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ **`CASCADE` HERE IS DJANGO'S AND NOT THE DATABASE'S**, which is the one
    #: thing about this model worth knowing before copying it. Django issues the
    #: child DELETE itself, in Python, and writes `NO ACTION DEFERRABLE
    #: INITIALLY DEFERRED` into PostgreSQL. So an ORM `.delete()` removes the
    #: ceilings and a RAW `DELETE FROM integration_connection` does not — it is
    #: REFUSED at commit instead, which is the safe direction. It is `CASCADE`
    #: rather than this module's usual `PROTECT` because a ceiling is a
    #: SETTING, not a record: `PROTECT` would mean a connection could not be
    #: disconnected until somebody deleted rows nobody has a screen for.
    #: `migrations/0009`'s docstring has the three rounds of failing test that
    #: produced this sentence.
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        db_column="connection_id",
        related_name="rate_limits",
    )
    #: The operation's name off the manifest (`read_payments`). Code data, not
    #: a foreign key — the same shape as `IntegrationConnection.provider_key`,
    #: so a nineteenth connector adds a manifest and no migration
    #: (`BR-INT-037`).
    operation = models.TextField()
    calls_per_minute = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_rate_limit"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "operation"],
                name="uq_integration_rate_limit_operation",
            ),
            # A ceiling of zero or less is not a tighter limit, it is a
            # connector that can never be called — and it would arrive as a
            # typo rather than as a decision. The door treats an absent row as
            # the default ceiling, never as "no limit", so the database and the
            # code fail closed in the same direction.
            models.CheckConstraint(
                condition=models.Q(calls_per_minute__gt=0),
                name="ck_integration_rate_limit_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "connection"], name="ix_intg_rate_limit_conn"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.operation} · {self.calls_per_minute}/min"


class IntegrationConsent(models.Model):
    """A consent belongs to the customer (BR-INT-036) — CONDITIONAL on OQ-INT-1482.

    In the schema so that, if the question is ruled in, the feature costs rows
    and no migration. **No service writes this table until then**, and there is
    deliberately no writer in `services.py` to reach for.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ reviewed cross-module FK integrations → customers (B2 r22)
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="+",
    )
    grantee = models.TextField()  # who the customer allowed
    scope = models.JSONField()  # what, and how much history
    granted_at = models.DateTimeField()
    granted_by = models.UUIDField(null=True, blank=True)  # the CUSTOMER, not a member of staff
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)  # set, never deleted
    revoked_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "integration_consent"


class IntegrationKeyDirectory(models.Model):
    """WHICH UTILITY AN ISSUED KEY BELONGS TO — the one read that happens before
    a utility is chosen.

    ⚠ **THE SEVENTH TABLE AND THE ONLY ONE THAT IS NOT A TENANT TABLE.** It is
    deliberately absent from `TENANT_TABLES` below and it carries no RLS policy,
    because a policy would make it unreadable at the one moment it is needed:
    a partner's request arrives with a key and NOTHING else, so there is no
    tenant context yet and a tenant table yields zero rows for a perfectly valid
    key (CLAUDE.md law 7's *incapable of passing*). It is declared in
    `tests/isolation_helpers.RLS_EXEMPT_TABLES` and in B2 §3 beside the six that
    were already there, and `test_g5_the_rls_exempt_list_is_exactly_what_b2_
    declares` is what keeps that honest.

    ⚠ **IT IS THE SAME CLASS AS `sessions`, WHICH IS WHY THE EXEMPTION IS NOT A
    NEW IDEA (`CR-110-BRC04` phase 2, `DEF-INT-5546`).** A signed-in request on
    `/api/jobs/{id}` carries no utility either; `core.tenancy.adopt_session_tenant`
    reads the session row — RLS-exempt for exactly this reason — and opens the
    utility the row names. Its own docstring states the principle this table
    rests on: *"the cookie selects a row, the row states the tenant. Adopting it
    is not client input."* A bearer key is the same shape. A path segment is a
    claim; a key is proof.

    ⚠ **WHAT IT HOLDS IS THE WHOLE OF WHY IT MAY BE EXEMPT.** Three ids and a
    one-way fingerprint. No secret — `blind_index` is the same keyed digest
    `integration_credential` stores and cannot be reversed into a key. No name,
    no address, no money, nothing a customer would recognise. Read in full by an
    attacker it yields a count of issued keys and a set of opaque uuids.

    ⚠ **AND IT DECIDES NOTHING EXCEPT WHICH DOOR TO OPEN.** Whether the key is
    live, unexpired, in scope, from a permitted address, on an enabled connector
    at a live utility is decided afterwards by `runners/serve.resolve_caller`,
    reading `integration_credential` UNDER that utility's own walls. A row here
    that pointed at the wrong utility would buy nothing: the credential lookup
    under that utility would not find the key, and the caller would be refused in
    the ordinary way. So this table is a hint about where to look, never an
    authorisation.

    ⚠ **A REVOKED KEY KEEPS ITS ROW, ON PURPOSE.** `serve.record_refusal` can
    only write the run row a manager reads — *"WorldPay refused: key revoked"* —
    when it has a connection to hang it on, and it gets one by resolving the
    utility first. Delete the row on revoke and a revoked key becomes
    indistinguishable from an unknown one IN OUR OWN RECORD, which is the half
    of `BR-INT-044` that is supposed to stay distinguishable. Rows are removed
    only when the connection itself is disconnected and its credentials are
    destroyed.
    """

    #: The blind index IS the identity — one row per key we have ever issued,
    #: and a second key hashing to the same value is refused by the database at
    #: issue time rather than resolving two utilities.
    blind_index = models.TextField(primary_key=True)
    #: Plain UUID columns, not FKs: this table is read with no tenant context and
    #: a join into a tenant table from here would return nothing. The ids are
    #: carried so the resolution is one query, and `serve.py` re-reads the real
    #: rows under the tenant it opens.
    tenant_id = models.UUIDField()
    connection_id = models.UUIDField()
    credential_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integration_key_directory"
        #: NAMED, not auto-derived: `0011` creates it under this name and an
        #: unnamed `Index` makes Django hash one from the model, which then
        #: differs from the migration and `makemigrations --check` reports drift
        #: on a fresh checkout for ever.
        indexes = [
            models.Index(fields=["connection_id"], name="integration_key_dir_conn_idx")
        ]


#: The four states a sending domain can be in, as the panel draws them. Kept
#: here as well as in `adapters/esp_email.py` for the reason every `_choices`
#: vocabulary in this file is here: a model field's choices are a database
#: constraint, and importing an adapter module from `models.py` would make the
#: ORM depend on the transport layer. `test_cr115_esp_adapters` asserts the two
#: tuples are identical, so they cannot drift.
SENDING_DOMAIN_STATES = ("verified", "partial", "unverified", "not_found")


class IntegrationSendingDomain(models.Model):
    """What the ESP last said about one utility's sending domain — the LONG POLE.

    PO, 2026-09-17, on why this table earns its keep: *"whoever runs that
    utility's website must add three short records to their domain settings. It
    is a ten-minute job for them; getting it asked for, approved and done
    usually takes ONE TO THREE WEEKS … that wait is theirs and we cannot shorten
    it, and everything we build is finished long before those records are."*
    **Production is gated behind that wait**, so the records have to be in the
    IT team's hands on day one and the answer has to survive everything in
    between.

    ⚠ **WHY THIS IS A TABLE AND NOT `integration_connection.config`.** The
    obvious home is the connection's own JSON, and it would be silently
    destroyed: `services.update_connection` PRUNES the stored config to the
    names the manifest still declares (`DEF-INT-5582`), so the first time a
    clerk saved any setting, the whole DNS answer would vanish with a correct
    file count and a green test. That pruning is right and is not being worked
    around — this is simply not connection CONFIG. It is a provider FACT with a
    timestamp on it.

    ⚠ **`verified_at` IS STAMPED ONCE AND NEVER CLEARED, AND THAT IS THE CLOCK
    SOMEBODY WILL ASK ABOUT.** *When did Ottumwa finish their DNS* is a question
    with a real answer and a short memory: a domain can go back to unverified if
    a record is removed, and overwriting the stamp would make the first
    completion unrecoverable. `checked_at` says *when we last looked*;
    `verified_at` says *when it first came good*; `state` says *what is true
    now*. Three columns because they are three different questions and one of
    them is asked months later.

    ⚠ **ONE ROW PER (connection, domain).** A utility that changes its sending
    domain starts a new row rather than overwriting the old one's history, and
    the UNIQUE is what makes a re-check an update rather than a pile.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.PROTECT,
        db_column="connection_id",
        related_name="sending_domains",
    )
    #: Lower-cased, no trailing dot — the form `esp_email` matches on.
    domain = models.TextField()
    state = models.TextField(choices=_choices(SENDING_DOMAIN_STATES))
    #: The provider's own records, as `esp_email.DnsRecord.as_dict()` shapes
    #: them, PLUS the one DMARC line we compose — which carries
    #: `source: "ours"` so no reader can mistake it for a provider value.
    #: ⚠ **NOTHING HERE IS EVER COMPOSED FROM A PATTERN.** SendGrid's `em1234`
    #: prefix and its DKIM selectors differ per account; a made-up record
    #: publishes cleanly, verifies never, and costs the utility's
    #: one-to-three-week cycle a second time.
    records = models.JSONField(default=list, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    #: THEIRS, scrubbed at the write like every other provider text in this
    #: module, and shown to the owning tenant only.
    provider_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_sending_domain"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "connection", "domain"],
                name="uq_integration_sending_domain",
            ),
        ]


class IntegrationApi(models.Model):
    """ONE API ON ONE CONNECTION — ours or theirs — and whether it is switched on.

    `CR-115-BRC05` §7, PO ruling 2026-09-17. The reasoning, the five rules and
    the two deliberate absences (no field mapping, no per-API key) are in
    `apps/integrations/custom_apis.py`'s own docstring rather than paraphrased
    here; this class is the storage that ruling needs.

    ⚠ **THE SCHEMA CHANGE THE BLUEPRINT COUNTED AS AVOIDED.** Its 14-September
    ruling (`CR-3`, p164) noted that a clerk-owned API name *"would need a
    per-connection field that does not exist"* and banked *"no schema change"*
    as the saving. The PO ruled that too broad three days later, so the cost is
    paid here, knowingly.

    ⚠ **TWO KINDS OF ROW IN ONE TABLE, AND `is_standard` IS THE DIFFERENCE.**
    §7.4 asks for *"ours and theirs in ONE list"*, and one table is what makes
    a single ordered list possible at all:

    * `is_standard = True` — an ENABLEMENT RECORD for an API that ships with
      the connector. `name` and `url` are NULL because both are ours: the
      manifest holds the name, the address ladder holds the address. The row
      exists only once somebody has touched the switch; **absence means ON**
      (`custom_apis.is_enabled`), so every connection that predates this table
      goes on behaving exactly as it did.
    * `is_standard = False` — an API a clerk ADDED. `operation` names which of
      OUR operations runs it, which is why there is no `kind` column: the Kind
      and the operation are one fact, and the copy nobody reads is the one that
      drifts.

    ⚠ **NOT IN `integration_connection.config`, AND THE REASON IS A SHIPPED
    DEFECT.** `services.update_connection` PRUNES `config` to what the manifest
    still declares (`DEF-INT-5582`), so rows kept there would be silently
    deleted by the next Edit save — every test green and the clerk's layers
    gone. A table cannot be pruned by a field validator.

    ⚠ **NO SECRET COLUMN, EVER.** A per-API key would be a credential, and
    `IntegrationCredential` is where credentials live (`BR-INT-003`,
    `US-INT-014` TC-3). §7.6 defers them and `DEF-INT-5680` carries it.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ **CASCADE, AND IT IS A DECISION.** These rows are configuration OF a
    #: connection and mean nothing without it; `PROTECT` would make
    #: `services.disconnect` fail on any connector a clerk had configured,
    #: which is a screen breaking on the successful path. The runs, which are a
    #: RECORD of what happened rather than configuration, keep their own
    #: lifetime and are untouched by this.
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        db_column="connection_id",
        related_name="apis",
    )
    #: WHICH OF OUR OPERATIONS RUNS THIS. Code data, not a foreign key — the
    #: same posture as `provider_key` above, and `custom_apis.kinds_for` refuses
    #: a name the manifest does not declare at the service boundary.
    operation = models.TextField()
    is_standard = models.BooleanField()
    #: THEIRS. NULL on a standard row, where the manifest's label is the name.
    name = models.TextField(null=True, blank=True)
    #: THEIRS. NULL on a standard row, where the address ladder decides.
    url = models.TextField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_api"
        constraints = [
            #: ⚠ **THIS CONSTRAINT IS §7.4's *"one configuration per API, never
            #: two"*, IN THE DATABASE.** The form drops a configured Kind out of
            #: the dropdown and `custom_apis.add` refuses a duplicate by name;
            #: this is the half that is still true when two clerks press Add in
            #: the same second. It also holds the standard half to one
            #: enablement record per operation, so a switch cannot end up with
            #: two rows disagreeing about whether an API is on.
            models.UniqueConstraint(
                fields=["connection", "operation", "is_standard"],
                name="uq_integration_api_connection_operation",
            ),
        ]
        indexes = [
            models.Index(fields=["connection"], name="ix_integration_api_connection"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug only
        return f"{self.operation} · {'standard' if self.is_standard else self.name}"


#: The tenant tables, in the order the brief lists them — read by the RLS
#: migration, the gates and the isolation tests, so the list exists once.
#:
#: CR-173-BRC10 — the states of one placed file.
DELIVERY_SENDING = "sending"
DELIVERY_SENT = "sent"
DELIVERY_FAILED = "failed"
DELIVERY_STATUSES = (DELIVERY_SENDING, DELIVERY_SENT, DELIVERY_FAILED)


class IntegrationFileDelivery(models.Model):
    """ONE FILE WE PLACED IN A PARTNER'S FOLDER, FOR ONE DAY — and the guard that it happens once.

    `CR-173-BRC10`. PO 2026-10-07 (Q4): *"(a) refuse if already sent"* — a
    second file for a day New World has already imported would be imported
    again, and every receipt in it would post twice in the City's books.

    ⚠ **THE PARTIAL UNIQUE INDEX IS THE REFUSAL; THE `SELECT` BEFORE IT IS
    ONLY THE SENTENCE** (hard rule 6). Two runs for the same day — a schedule
    and a person pressing Run in the same minute — each find no row and each
    insert one; only `uq_intg_file_delivery_one_per_day` refuses the second,
    and it does so on PostgreSQL by making the second INSERT WAIT for the
    first transaction and then fail. `receipt_push` takes the claim inside its
    own SAVEPOINT for the reason CLAUDE.md law 14 gives.

    ⚠ **`sending` IS IN THE INDEX, `failed` IS NOT.** A failed attempt must
    not lock the day for ever — the next run tries again — and an attempt in
    flight must block a second one. `is_resend` rows are outside the index:
    a resend is a PERSON's deliberate act (*"a resend is a deliberate act"*),
    named, audited and never available to a schedule.

    Not `integration_run`: that table is partitioned on `started_at`, and a
    partitioned table cannot carry a unique index without its partition key,
    which would make *one per day* *one per day per instant* — no guard at all.
    The run row still exists for every attempt and is what Settings →
    Integrations shows; this row is the lock and its outcome.
    """

    id = dbfields.uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.PROTECT,
        db_column="connection_id",
        related_name="file_deliveries",
    )
    operation = models.TextField()
    #: The TENANT-LOCAL day the file covers — the day in its name, never the
    #: day it was sent (PO Q2).
    data_day = models.DateField()
    filename = models.TextField()
    folder = models.TextField()
    status = models.TextField(choices=_choices(DELIVERY_STATUSES))
    is_resend = models.BooleanField(default=False)
    trigger = models.TextField(choices=_choices(RUN_TRIGGERS))
    started_by_name = models.TextField(null=True, blank=True)
    #: Why a person resent it. Required on a resend, NULL otherwise.
    reason = models.TextField(null=True, blank=True)
    receipt_count = models.IntegerField(default=0)
    unbalanced_count = models.IntegerField(default=0)
    unresolved_gl_count = models.IntegerField(default=0)
    byte_count = models.IntegerField(default=0)
    #: One sentence a clerk can read — the fixed ≤ 6-word refusal, never the
    #: far end's raw words and never a password.
    failure = models.TextField(null=True, blank=True)
    #: `integration_run.id` of the attempt that wrote this row.
    run_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integration_file_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "connection", "operation", "data_day"],
                condition=models.Q(status__in=("sending", "sent"), is_resend=False),
                name="uq_intg_file_delivery_one_per_day",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "connection", "-data_day"], name="ix_intg_file_delivery_day"
            ),
        ]


#: ⚠ **SIX SINCE 2026-09-16 AND SEVEN SINCE 2026-09-17.** `integration_rate_limit` arrived with
#: `CR-110-BRC04` and its RLS policy is in the SAME migration that creates it
#: (`0009`), not in `0002` — a tenant table that exists for even one migration
#: without a policy is a hard-rule-1 breach with a window in it. This tuple is
#: what the isolation probe walks, so a seventh table added without being named
#: here is a table nothing proves.
TENANT_TABLES = (
    "integration_connection",
    "integration_credential",
    "integration_run",
    "integration_target_reference",
    "integration_consent",
    "integration_rate_limit",
    #: ⚠ **SEVEN SINCE 2026-09-17** (`CR-115-BRC05`). Its policy is in the SAME
    #: migration that creates it (`0013`), like `integration_rate_limit`'s — a
    #: tenant table that exists for even one migration without a policy is a
    #: hard-rule-1 breach with a window in it.
    "integration_sending_domain",
    #: ⚠ **EIGHT SINCE 2026-09-17** (`CR-115-BRC05` §7 — the per-API rows a
    #: clerk adds). Its policy is in the SAME migration that creates it, like
    #: the two above, for the reason the note at the top of this tuple gives.
    #: ⚠ **THE COUNT WORD ABOVE SAID SEVEN AND TWO LANES BOTH ADDED THE
    #: SEVENTH ON ONE DAY** — a number in a comment is a claim nothing
    #: re-checks. The tuple itself is what the isolation probe walks; count
    #: IT, never this sentence.
    "integration_api",
    #: CR-173-BRC10 — one placed file per day. Its policy is in the SAME
    #: migration that creates it (`0015`).
    "integration_file_delivery",
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-014@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packet US-INT-013@62d3643)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D✔(GET /integrations reads these through selectors.py) E✔(features/integrations/IntegrationsTab.tsx) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 rows in 09-human-review-ledger.md for migrations 0001/0002)
# gates: makemigrations --check clean · pytest tests/test_us_int_014_tables.py (SQLite) · tests/test_us_int_014_pg.py on PostgreSQL 16 (EXCLUDE · isolation probe · append-only trigger) · G75 (no secret column on the connection table) · G16 (integration_run in the yearly registry AND created partitioned)
# exceptions: `integration_consent` has no writer, on purpose (OQ-INT-1482) · the one-active credential guard is vendor-specific and lives in migration 0001, not in Meta · SQLite carries no partition, no trigger and no RLS — those assertions are PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
