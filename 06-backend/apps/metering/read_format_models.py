# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 utility-defined meter-read FORMATS (task 10
#           of 13: the server). Decision log 2026-10-24, the three "MQ-033"
#           rows.
# Rules:    BR-MET-1210 … BR-MET-1218 · BR-WRK-008 (a version is stamped, so a
#           re-worded format never re-words an answer already given) ·
#           BR-TEN-046 (tenant DATA, never schema) · CLAUDE.md hard rules 1,
#           3, 7 · NFR-5 (no cap on formats, versions, questions or answers)
# Tests:    06-backend/tests/test_mq033_read_formats.py ·
#           06-backend/tests/test_mq033_read_answers.py ·
#           06-backend/tests/test_mq033_read_answers_pg.py
# Impacts:  apps/metering/models.py (registers these; `Route.read_format`,
#           `Cycle.read_format`) · apps/metering/migrations/0080_mq033_read_formats.py
# ───────────────────────────────────────────────────────
"""A utility's own meter-read FORMAT: the extra questions a reader answers.

THE RULING, VERBATIM (decision log 2026-10-24, three rows headed "MQ-033")
────────────────────────────────────────────────────────────────────────────
*"B. Reading templates, like work templates - we understand your
recommendation , but utility users want customizations they wantt to collect
various data during meter reads hence we need to create meter read format
templates so that the customization can be handled"*

*"3. Settings → Reads; The template is chosen automatically: route → cycle →
service. A route can override its cycle, and a cycle its service. we can set
it once or we can create another format for same service and replace it
later"* — and of the worked five-question example: *"this is all user defined
we dont have to provide anything readymade , this will be similar to custom
fields"*.

*"this is correct"* — confirming that the first release carries **asked
when** (every reading · out of range · can't read · once per stop),
**follow-ups** (an answer reveals another question or requires a photo) and
**raise a work order** (an answer raises a job of a utility-chosen type,
linked back to the reading); that answers travel inside the reading's own
item, are checked on the server against the same version, and **never cause a
reading to be dropped (stored and flagged instead)**.

THE SHAPE
────────────────────────────────────────────────────────────────────────────
* `ReadFormat` — the thing a utility names and points at, for ONE service.
  `draft` until first published, `published` once a version is live,
  `retired` when withdrawn. Pointers (`routes.read_format_id`,
  `cycles.read_format_id`, `read_format_defaults`) name the FORMAT, never a
  version: replacing a format is moving a pointer, and publishing a new
  version moves every reading that comes after it — never one already taken.
* `ReadFormatVersion` — the questions as they stood. **IMMUTABLE ONCE
  PUBLISHED**: editing a published format opens a NEW draft version and
  publishing it gives it the next number. At most one draft per format.
* `ReadFormatQuestion` — one question of one version. Typed exactly like a
  custom field (`tenancy.CUSTOM_FIELD_DATA_TYPES`, read through
  `metering.seams.custom_field_data_types`, never copied) plus `photo`.
* `ReadFormatDefault` — the per-service default, one row per service.
* `ReadAnswer` — one answer to one question on one field reading, stamped
  with the VERSION it was asked under (`BR-WRK-008`'s reason). `issue` names
  why the server flagged it; a flagged answer is STORED, never dropped.

NOTHING IS SEEDED (*"we dont have to provide anything readymade"*): no row in
any of these tables exists until a utility makes one, and a route that
resolves to no format reads exactly as it did before this change.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

FORMAT_DRAFT = "draft"
FORMAT_PUBLISHED = "published"
FORMAT_RETIRED = "retired"
FORMAT_STATUSES: tuple[str, ...] = (FORMAT_DRAFT, FORMAT_PUBLISHED, FORMAT_RETIRED)

VERSION_DRAFT = "draft"
VERSION_PUBLISHED = "published"
VERSION_STATES: tuple[str, ...] = (VERSION_DRAFT, VERSION_PUBLISHED)

#: The one type a read question adds to the custom-field list (PO: *"questions
#: typed like custom fields plus Photo"*). The other six are NOT listed here —
#: they are read from tenancy's constant through the seam, so a seventh custom
#: field type reaches read questions without a second edit.
PHOTO = "photo"

#: *"asked when (every reading · out of range · can't read · once per stop)"*.
ASKED_EVERY_READING = "every_reading"
ASKED_OUT_OF_RANGE = "out_of_range"
ASKED_CANT_READ = "cant_read"
ASKED_ONCE_PER_STOP = "once_per_stop"
ASKED_WHEN: tuple[str, ...] = (
    ASKED_EVERY_READING,
    ASKED_OUT_OF_RANGE,
    ASKED_CANT_READ,
    ASKED_ONCE_PER_STOP,
)

#: Why the server flagged an answer — machine words, the screen writes the
#: sentence (B14 rule 35). A flag never drops the reading or the answer.
ISSUE_UNKNOWN_QUESTION = "unknown_question"
ISSUE_WRONG_TYPE = "wrong_type"
ISSUE_NOT_AN_OPTION = "not_an_option"
ISSUE_NOT_ASKED = "not_asked"
ISSUE_NOT_SHOWN = "not_shown"
ISSUE_REQUIRED_MISSING = "required_missing"
ISSUE_VERSION_UNKNOWN = "version_unknown"
ISSUES: tuple[str, ...] = (
    ISSUE_UNKNOWN_QUESTION,
    ISSUE_WRONG_TYPE,
    ISSUE_NOT_AN_OPTION,
    ISSUE_NOT_ASKED,
    ISSUE_NOT_SHOWN,
    ISSUE_REQUIRED_MISSING,
    ISSUE_VERSION_UNKNOWN,
)


class ReadFormat(models.Model):
    """`read_formats` — a utility's named format for one service."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: Tenant PROSE, like a custom field's label (B2 r17.5 #1's exception).
    name = models.TextField()
    #: ⚠ cross-module FK → tenancy (the reviewed `service_id` direction every
    #: metering table already carries). A format belongs to ONE service: a
    #: water walk and an electric walk ask different things.
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    status = models.TextField(default=FORMAT_DRAFT)
    #: The version readings are taken under NOW — the latest published one.
    #: NULL until first published. A pointer never names a version, so moving
    #: this moves every later reading and no earlier one.
    current_version = models.ForeignKey(
        "metering.ReadFormatVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="current_version_id",
        related_name="+",
    )
    created_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="created_by", related_name="+",
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_formats"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uq_read_formats_name"),
            models.CheckConstraint(
                condition=Q(status__in=FORMAT_STATUSES), name="ck_read_formats_status"
            ),
            # A published format always has a live version; a draft never.
            models.CheckConstraint(
                condition=Q(status=FORMAT_DRAFT, current_version__isnull=True)
                | Q(status__in=(FORMAT_PUBLISHED, FORMAT_RETIRED), current_version__isnull=False),
                name="ck_read_formats_current_version",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "service", "status"], name="ix_read_formats_service"),
        ]


class ReadFormatVersion(models.Model):
    """`read_format_versions` — the questions as they stood. A published
    version is never edited (BR-WRK-008's reason); `version_no` is given at
    publish, so a draft carries none."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    read_format = models.ForeignKey(
        ReadFormat, on_delete=models.PROTECT, db_column="read_format_id", related_name="versions"
    )
    state = models.TextField(default=VERSION_DRAFT)
    version_no = models.IntegerField(null=True, blank=True)
    change_note = models.TextField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="published_by", related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_format_versions"
        constraints = [
            models.CheckConstraint(
                condition=Q(state__in=VERSION_STATES), name="ck_read_format_versions_state"
            ),
            models.CheckConstraint(
                condition=Q(state=VERSION_DRAFT, version_no__isnull=True, published_at__isnull=True)
                | Q(state=VERSION_PUBLISHED, version_no__isnull=False, published_at__isnull=False),
                name="ck_read_format_versions_published",
            ),
            models.UniqueConstraint(
                fields=["read_format", "version_no"],
                condition=Q(version_no__isnull=False),
                name="uq_read_format_versions_no",
            ),
            # At most ONE draft per format: "editing a published format
            # creates a new draft version".
            models.UniqueConstraint(
                fields=["read_format"],
                condition=Q(state=VERSION_DRAFT),
                name="uq_read_format_versions_one_draft",
            ),
        ]


class ReadFormatQuestion(models.Model):
    """`read_format_questions` — one question of one version, defined like a
    custom field (`data_type`, `options`, `is_required`) plus the three
    behaviours the PO confirmed: `asked_when`, `show_if`, `raise_work`."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    version = models.ForeignKey(
        ReadFormatVersion, on_delete=models.CASCADE, db_column="version_id", related_name="questions"
    )
    seq = models.IntegerField(default=0)
    #: The identity an answer is stored under, forever (the custom field's
    #: BR-TEN-049 reason). Unique within a version.
    key = models.TextField()
    label = models.TextField()
    help_text = models.TextField(null=True, blank=True)
    #: A custom-field data type, or `photo`. Validated by the service against
    #: tenancy's constant read through the seam — a CHECK here would be a
    #: second copy of a list this module does not own.
    data_type = models.TextField()
    options = models.JSONField(null=True, blank=True)
    is_required = models.BooleanField(default=False)
    asked_when = models.TextField(default=ASKED_EVERY_READING)
    #: `{"question_key": "<an EARLIER question>", "answer": <value>}` or NULL.
    show_if = models.JSONField(null=True, blank=True)
    #: `{"on_answer": <value>, "template_id": "<a published Work template>"}`
    #: or NULL — the job type a utility chose, raised through Work's own door.
    raise_work = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_format_questions"
        constraints = [
            models.UniqueConstraint(fields=["version", "key"], name="uq_read_format_questions_key"),
            models.CheckConstraint(
                condition=Q(asked_when__in=ASKED_WHEN), name="ck_read_format_questions_asked_when"
            ),
        ]
        indexes = [
            models.Index(fields=["version", "seq"], name="ix_read_format_questions_seq"),
        ]


class ReadFormatDefault(models.Model):
    """`read_format_defaults` — the bottom of route → cycle → service: the
    format a service's readings use when neither route nor cycle names one."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    read_format = models.ForeignKey(
        ReadFormat, on_delete=models.PROTECT, db_column="read_format_id", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_format_defaults"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "service"], name="uq_read_format_defaults_service"),
        ]


class ReadAnswer(models.Model):
    """`read_answers` — one answer on one field reading, AS RECEIVED.

    Stamped with the version it was asked under. `value` is what the handset
    sent; `value_text` is its searchable form (the Reads list's
    `answer[<key>]=<value>` filter). `issue` is NULL for a clean answer.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    field_read = models.ForeignKey(
        "metering.FieldRead", on_delete=models.CASCADE, db_column="field_read_id",
        related_name="answers",
    )
    #: NULL only when the handset named a version this server does not hold
    #: (`version_unknown`) — the answer is still kept.
    version = models.ForeignKey(
        ReadFormatVersion, on_delete=models.PROTECT, null=True, blank=True,
        db_column="version_id", related_name="+",
    )
    question_key = models.TextField()
    value = models.JSONField(null=True, blank=True)
    value_text = models.TextField(null=True, blank=True)
    #: A `photo` answer's id — the SAME id a route photograph's declaration
    #: carries (`field_read_photos`), so the bytes use that one upload door.
    photo_id = models.UUIDField(null=True, blank=True)
    issue = models.TextField(null=True, blank=True)
    #: `raise_work`: the Work finding key this answer raised its job under
    #: (idempotent on reading + question) and the job, once raised. Work's
    #: rows are Work's; these are references, not foreign keys.
    work_finding_key = models.TextField(null=True, blank=True)
    work_order_id = models.UUIDField(null=True, blank=True)
    #: The job's number as Work answered it (`WO-4870`) — what the reading's
    #: page shows without reading Work's table per answer (B14 rule 31).
    work_order_no = models.TextField(null=True, blank=True)
    work_raise_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "read_answers"
        constraints = [
            models.UniqueConstraint(
                fields=["field_read", "question_key"], name="uq_read_answers_question"
            ),
            models.CheckConstraint(
                condition=Q(issue__isnull=True) | Q(issue__in=ISSUES), name="ck_read_answers_issue"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "question_key", "value_text"], name="ix_read_answers_filter"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-192-BRC10 (MQ-033 task 10 — read formats server; decision log 2026-10-24 ×3)
# generated: 2026-10-24 by lane MQ033-SERVER
# checklist: A✔ B✔ C✔ D✔ E=deferred(task 11 Settings screens · task 12 phone) F✔ G✔ H=deferred(metering/0080 is 🔒 migration ordering / RLS — HUMAN-REVIEW-PENDING)
# gates: see the lane report
# exceptions: `raise_work` names a published Work TEMPLATE (the job's type is the template's) — a judgment, reported
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
