# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 (EP-CWP-12) — help answers in the back office ·
#           US-CWP-072 — help on the portal · US-CWP-073 — tips ·
#           US-CWP-074 — service centres, and *hidden* is a state.
#           Screens: CWP-071 · CWP-072 · CWP-073 · CWP-074 · CWP-075 ·
#           CWP-011 · CWP-060 · CWP-013 · CWP-014
# Rules:    BR-CWP-093 (nothing shows until something is published, and nothing
#           empty ever appears) · BR-CWP-094 (only `published` leaves the back
#           office; a missing translation falls back to English) ·
#           BR-CWP-095 (a tip shows only when ON and today is inside its month
#           range; one per screen; position breaks the tie) · BR-CWP-096
#           (`is_shown_to_customers = false` is a REAL STATE, not a deletion;
#           holiday closures come from the tenant's own calendar) ·
#           03-field-map.md §2 (published content is per-tenant reference data
#           and belongs to **tenancy** — B2 §2, the owning module owns its
#           data) · CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE)
# Tests:    06-backend/tests/test_us_cwp_071_help.py ·
#           test_us_cwp_072_help_portal.py · test_us_cwp_073_tips.py ·
#           test_us_cwp_074_centres.py · test_us_cwp_071_pg.py (RLS)
# Impacts:  migrations/0037_cr068_d_published_content.py ·
#           migrations/0038_rls_cr068_d_published_content.py (🔒) ·
#           apps/tenancy/published_content.py (every read and every write) ·
#           apps/portal/seams/tenancy_seam.py (the portal's read side)
# ───────────────────────────────────────────────────────
"""The six tables behind *Help & answers*, *Tips* and *Where you can walk in*.

WHY THESE LIVE IN `tenancy` AND NOT IN `apps/portal`
-----------------------------------------------------
`03-field-map.md` §2 puts them here in as many words: *"published content is
per-tenant reference data and lives in `tenancy`. A lane that puts all fourteen
in `apps/portal/` has made the portal a second billing system."* The portal
READS them through `apps/portal/seams/tenancy_seam.py` and cannot write them —
B2 §2 forbids a cross-module write, and `G81` enforces it file by file.

THREE THINGS THAT LOOK LIKE ONE AND ARE NOT
-------------------------------------------
* **`draft` and `not_shown` are two states, and neither leaves the back
  office.** Draft is *not finished*; not-shown is *finished and deliberately
  withheld* — the blueprint's own §16 records that its first public help page
  listed all eight answers including both. The exclusion is the QUERY's
  (`published_content.published_answers`), never a template's.
* **A read and a vote are different events**, counted separately
  (`help_answer_feedback.event`): opening a page is not the same statement as
  pressing *No*, and a schema that adds them together cannot be un-added later.
* **Hidden is not deleted.** `service_centre.is_shown_to_customers = False`
  keeps the depot in the clerk's list and off the public page. Removal is a
  separate, danger-tier act, because a printed address may still be in
  circulation.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
* **A holiday row.** `service_centre_hour` carries the weekly pattern only.
  Closures come from `HolidayCalendar` (`models.py`, `holiday_calendars`), the
  list the utility already keeps in Reference data — *"which is what stops a
  portal telling someone to walk to a closed door on Thanksgiving"*
  (`BR-CWP-096`). A second list would be a second thing to remember.
* **A per-viewer dismissal of a tip.** `US-CWP-073` TC-6 dismisses a tip *for
  that viewer*; the guest surface has no viewer to key it to (`BR-CWP-021` —
  never a person), so dismissal is browser-side and writes no row.
* **A translation workflow.** `OQ-1398` — who keeps the answers current, and in
  how many languages — is OPEN. `needs_translating` is a VISIBLE STATE and
  nothing here schedules, assigns or chases a translation. See the module
  docstring of `published_content.py`.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk

# ── The eleven languages that ship ──────────────────────────────────────────
#: The locale codes of `07-frontend/src/i18n/locales/*.json`, in that folder's
#: order. `help_answer_variant` carries one row per language per answer, so a
#: utility can SEE what its Spanish-speaking customers are not being shown
#: (US-CWP-071 TC-7). Read from here by the service and by the fixture; a
#: twelfth catalogue is one row in this tuple and a data migration.
LOCALES: tuple[str, ...] = (
    "de",
    "en",
    "es-MX",
    "es",
    "fr-FR",
    "hi",
    "id-ID",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "pt-BR",
)

#: The language every fallback lands on (BR-CWP-094: *"a missing translation is
#: better than a missing answer"*).
FALLBACK_LOCALE = "en"

# ── Statuses, as data ───────────────────────────────────────────────────────
ANSWER_DRAFT = "draft"
ANSWER_PUBLISHED = "published"
ANSWER_NOT_SHOWN = "not_shown"
#: ⚠ Exactly one of these leaves the back office, and it is in the QUERY.
ANSWER_STATUSES: tuple[str, ...] = (ANSWER_DRAFT, ANSWER_PUBLISHED, ANSWER_NOT_SHOWN)

VARIANT_PUBLISHED = "published"
VARIANT_NEEDS_TRANSLATING = "needs_translating"
VARIANT_STATUSES: tuple[str, ...] = (VARIANT_PUBLISHED, VARIANT_NEEDS_TRANSLATING)

FEEDBACK_READ = "read"
FEEDBACK_HELPFUL = "helpful"
FEEDBACK_NOT_HELPFUL = "not_helpful"
#: ⚠ Three events, counted SEPARATELY (`CP-34`). A vote is not a read.
FEEDBACK_EVENTS: tuple[str, ...] = (FEEDBACK_READ, FEEDBACK_HELPFUL, FEEDBACK_NOT_HELPFUL)

#: `US-CWP-073` §1: *"keep tips under fifteen words or nobody reads them"*. The
#: editor FLAGS a longer tip and still accepts it (TC-7) — the rule is on the
#: screen, not in a policy document, and not in a CHECK constraint either.
TIP_WORD_GUIDANCE = 15


class HelpAnswer(models.Model):
    """`help_answer` — `CP-31`. One question, its topic, its state and its
    place in the list. **The order here is the order on the portal.**"""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The stable, human, id-free handle a URL carries (B14 rule 31 — no
    #: database id is ever the visible value of a field, and a help URL is a
    #: visible value). Minted from the question, unique per tenant.
    slug = models.TextField()
    question = models.TextField()
    topic = models.TextField()
    status = models.TextField(default=ANSWER_DRAFT)
    position = models.IntegerField(default=0)
    #: ⚠ THE HIGHEST-VALUE FIELD IN THIS EPIC (US-CWP-071 §1): one field makes
    #: the same answer appear under a bill as well as in the list, and the
    #: utility does not write it twice. Null = the help list only.
    also_show_on_screen = models.TextField(null=True, blank=True)
    last_changed_by = models.TextField(null=True, blank=True)
    last_changed_on = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "help_answers"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="uq_help_answer_slug"),
            models.CheckConstraint(
                condition=models.Q(status__in=list(ANSWER_STATUSES)),
                name="ck_help_answer_status",
            ),
        ]
        indexes = [
            # The portal's read is `tenant + status`, ordered by position — the
            # index the guest query rides (NFR-30, NFR-40: a customer of a
            # 4,000-connection utility waits no longer than one of a 400).
            models.Index(fields=["tenant", "status", "position"], name="ix_help_answer_live"),
        ]


class HelpAnswerVariant(models.Model):
    """`help_answer_variant` — one row per language per answer.

    ⚠ `needs_translating` is a **visible state**, not a hidden one: the back
    office shows it so a utility can see what its Spanish-speaking customers
    are not being shown, and the portal falls back to English rather than
    hiding the answer (`BR-CWP-094`). Nothing here promises a workflow —
    `OQ-1398` is open.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    answer = models.ForeignKey(
        HelpAnswer, on_delete=models.CASCADE, db_column="help_answer_id", related_name="variants"
    )
    locale = models.TextField()
    body = models.TextField(blank=True, default="")
    status = models.TextField(default=VARIANT_NEEDS_TRANSLATING)
    last_changed_on = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "help_answer_variants"
        constraints = [
            models.UniqueConstraint(
                fields=["answer", "locale"], name="uq_help_answer_variant_locale"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(VARIANT_STATUSES)),
                name="ck_help_answer_variant_status",
            ),
        ]


class HelpAnswerFeedback(models.Model):
    """`help_answer_feedback` — `CP-34`. One row per event.

    ⚠ **NO PERSON IS RECORDED HERE, AND THAT IS THE DESIGN** (`BR-CWP-021` — a
    guest sees an amount and a status, never a person; and the reverse holds:
    the utility learns that an answer was read, never by whom). The row carries
    the answer, the language it was read in, the event and the day. There is no
    customer id, no account, no address and no session.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    answer = models.ForeignKey(
        HelpAnswer, on_delete=models.CASCADE, db_column="help_answer_id", related_name="feedback"
    )
    locale = models.TextField()
    event = models.TextField()
    occurred_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "help_answer_feedback"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event__in=list(FEEDBACK_EVENTS)),
                name="ck_help_answer_feedback_event",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "answer", "occurred_on"], name="ix_help_feedback_month"),
        ]


class Tip(models.Model):
    """`tip` — `CP-32`, the smallest table in the module.

    ⚠ A tip shows only when **`is_on` AND today is inside `month_from…month_to`**
    (`BR-CWP-095`). Null months mean all year. `position` breaks the tie when
    two match one screen, and **exactly one renders**.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    text = models.TextField()
    #: The one screen it shows on — a `CWP-###` id or the portal's own screen
    #: key. One screen, never a list: a tip on four screens is four tips, and
    #: the back office shows *where it shows* as one value a clerk can read.
    target_screen = models.TextField()
    month_from = models.SmallIntegerField(null=True, blank=True)
    month_to = models.SmallIntegerField(null=True, blank=True)
    is_on = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tips"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(month_from__isnull=True)
                | models.Q(month_from__gte=1, month_from__lte=12),
                name="ck_tip_month_from",
            ),
            models.CheckConstraint(
                condition=models.Q(month_to__isnull=True)
                | models.Q(month_to__gte=1, month_to__lte=12),
                name="ck_tip_month_to",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "target_screen", "position"], name="ix_tip_screen"),
        ]


class ServiceCentre(models.Model):
    """`service_centre` — `CP-33`. Where a customer can walk in.

    ⚠ **NOTHING ELSE IN THIS PRODUCT MODELS A PHYSICAL PLACE** (US-CWP-074 §1):
    no office, branch, counter or location record exists anywhere in the
    schema, so this record is genuinely new. The screen is not — it is a card
    in Configure → Reference data, a shape this product already repeats.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    slug = models.TextField()
    name = models.TextField()
    address = models.TextField()
    phone = models.TextField(null=True, blank=True)
    directions_note = models.TextField(null=True, blank=True)
    #: ⚠ **UNTICKED RENDERS AS *CANNOT*, NOT AS ABSENT** (US-CWP-074 §5). The
    #: guest screen draws all five rows and marks the four this centre cannot
    #: do — *"a list that also shows what it cannot do is an answer, and it is
    #: the difference between one journey and two"*. JSON, not `text[]`: the
    #: default suite runs on SQLite (CLAUDE.md law 14) and `ArrayField` has no
    #: SQLite form, while what matters — the values are the catalogue's — is
    #: the service's business and not the column's.
    allowed_actions = models.JSONField(default=list, blank=True)
    payment_methods_accepted = models.JSONField(default=list, blank=True)
    #: ⚠ A REAL STATE, NOT A DELETION (`BR-CWP-096`): how a depot stays off the
    #: public page without leaving the clerk's list.
    is_shown_to_customers = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    last_changed_on = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_centres"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="uq_service_centre_slug"),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_shown_to_customers", "position"], name="ix_centre_shown"
            ),
        ]


class ServiceCentreHour(models.Model):
    """`service_centre_hour` — the weekly pattern, and **only** the weekly
    pattern. ⚠ Holiday closures are NOT rows here (`BR-CWP-096`)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    centre = models.ForeignKey(
        ServiceCentre,
        on_delete=models.CASCADE,
        db_column="service_centre_id",
        related_name="hours",
    )
    #: Monday = 0 … Sunday = 6 — Python's `date.weekday()`, so the clock read
    #: in `published_content.centre_today()` needs no conversion table.
    day_of_week = models.SmallIntegerField()
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_centre_hours"
        constraints = [
            models.UniqueConstraint(
                fields=["centre", "day_of_week"], name="uq_service_centre_hour_day"
            ),
            models.CheckConstraint(
                condition=models.Q(day_of_week__gte=0, day_of_week__lte=6),
                name="ck_service_centre_hour_day",
            ),
        ]


#: Every tenant-scoped table this file adds. The RLS migration and the
#: PostgreSQL isolation test both read this tuple, so a seventh table cannot
#: land without a policy.
TENANT_TABLES: tuple[str, ...] = (
    "help_answers",
    "help_answer_variants",
    "help_answer_feedback",
    "tips",
    "service_centres",
    "service_centre_hours",
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-071 · US-CWP-072 · US-CWP-073 · US-CWP-074 (EP-CWP-12 + BR-CWP-093..096 verbatim)
# generated: 2026-09-04 by the CR-068 wave D build lane
# checklist: A✔ B✔ C✔ D✔(published_content_api.py) E✔(CWP-071..075, CWP-011/013/014/060) F✔ G✔ H=n/a(the 🔒 half is migrations/0038_rls_cr068_d_published_content.py)
# gates: pytest tests/test_us_cwp_07*.py · tests/test_us_cwp_071_pg.py on PostgreSQL · G88 (published content is queried, never filtered in a template) · G74 (every table has a reader: published_content.py)
# exceptions: allowed_actions / payment_methods_accepted are JSON, not text[] — SQLite has no array column (law 14); the field map is stamped
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
