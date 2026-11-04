# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4. The server half of
#          screen `2·3` (schedule a report), `4·1` (the Scheduled tab) and
#          `4·2` (a schedule opened). Drawings p34, p40, p41, read as IMAGES
#          per B14 rule 42.
# Rules:   BR-REP-020 CONFIRMED (internal staff only) · B14 rule 31 (no
#          database id is ever the visible value of a field) · NFR-3 (universal
#          server pagination) · NFR-5 (no hard caps) · CLAUDE.md hard rule 1
#          (tenant scoping) · hard rule 7 (every money action writes audit_log)
# Tests:   06-backend/tests/test_cr142_p4_schedules_api.py
# Impacts: apps/reports/api.py (its `urlpatterns` extends with these) ·
#          apps/reports/schedules.py (the arithmetic and the ruling) ·
#          07-frontend/src/features/reports/ScheduledTab.tsx
# ───────────────────────────────────────────────────────
"""`/reports/schedules` — the five routes `4·1`, `4·2` and `2·3` need.

⚠ **THIS IS A SEPARATE FILE FROM `api.py` ON PURPOSE, AND THE REASON IS LAW
11 RATHER THAN TIDINESS.** `apps/reports/api.py` is 35 KB and two sibling
lanes are editing it this week; a pathspec commit takes the WHOLE file, so the
second lane to commit silently reverts the first (`DEF-165`, a money fix that
left HEAD twelve minutes after landing with every test green). Adding ~300
lines to it would have put this phase's work in exactly that path. `api.py` is
touched here by ONE line — its `urlpatterns` extends with `SCHEDULE_URLS`.

════════════════════════════════════════════════════════════════════════════
THE STATUS COLUMN IS DERIVED, NEVER STORED — `P4.8`
════════════════════════════════════════════════════════════════════════════
`4·1` draws **On · Paused · Failing** (p40 callout ③). Only two of those are
columns: `enabled` is a column, and *failing* is a fact about the job
`last_job_id` points at. It is computed on every read, exactly as
`run_history.RUN_EXPIRED` is, and for the same reason that file states: a
STORED status gets stuck saying `failing` because the run that would have
cleared it never wrote back, and a derived one cannot.

⚠ **AND `next_run_at IS NULL` ON AN ENABLED SCHEDULE IS ALSO FAILING**, not
paused. That is the tenant with no accounting period configured whose
`monthly_on_cycle_close` cadence cannot compute a date — the schedule is
switched on, it will never fire, and the only honest word for that on a screen
is the one that makes somebody look.

════════════════════════════════════════════════════════════════════════════
NO `POST` FROM THIS TAB — `2·3` IS THE ONLY DOOR
════════════════════════════════════════════════════════════════════════════
p40: *"There is deliberately **no + New schedule** button here — you schedule
FROM the report you are looking at, so a create button on this screen would
need a report picker that `2·3` gets for free."* The POST route below is
reachable and is what `2·3` calls; what is absent is a control on `4·1`, and
that absence is the FRONT END's to honour. Stated here because a server route
existing is the usual reason somebody adds a button to reach it.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.urls import path
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import audit as core_audit
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import current_tenant_id, require_tenant

from . import report_seams, role_gate, run_history, schedules as scheduler
from .models import CADENCES, FORMATS, ReportDefinition, ReportSchedule

#: `4·1`'s status vocabulary, in the order a schedule passes through them.
#: MACHINE TOKENS — the screen renders the word from its own catalogue (TD-16:
#: the server sends keys, the UI renders language).
STATUS_ON = "on"
STATUS_PAUSED = "paused"
STATUS_FAILING = "failing"
SCHEDULE_STATUSES = (STATUS_ON, STATUS_PAUSED, STATUS_FAILING)

#: The default page. `NFR-3` — paged ALWAYS, and `P4.5`'s own ⚠ says why the
#: four rows a utility has today get a pager anyway: *"rule 16 has no
#: small-list exemption, and a utility with forty schedules is the case it is
#: for."* ⚠ NFR-5: this is a PAGE SIZE, never a ceiling — nothing here limits
#: how many schedules a tenant may hold.
DEFAULT_PER = 50


def _positive_int(raw: Any, fallback: int) -> int:
    """A counting number from the query string, or the fallback. Never raises.

    BR-SHL-011's posture, and `api._positive_int`'s exact behaviour — restated
    rather than imported so this file adds no coupling to a 35 KB module two
    lanes are editing (see the module docstring).
    """
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


def _job(job_id: Any) -> dict[str, Any] | None:
    """The `jobs` row `last_job_id` points at, through tenancy's own selector.

    ⚠ **A SEAM AND NOT `from apps.tenancy.models import Job`.** `jobs` is
    tenancy's table; B2 §2 keeps cross-module reach to the reviewed interface
    set and `G6`/`G20` refuse the import. `None` means *we cannot say*, which
    the caller renders as `on` rather than as `failing` — accusing a healthy
    schedule of failing because a lookup was unavailable is the worse error of
    the two.
    """
    if not job_id:
        return None
    found = report_seams.resolve("tenancy", "report_run", kind="selectors")
    if found is None:  # pragma: no cover — tenancy is always published
        return None
    try:
        # ⚠ **`resources` AND `kinds` ARE REQUIRED KEYWORD ARGUMENTS AND THE
        # FIRST DRAFT PASSED NEITHER.** `report_run(job_id)` raises
        # `TypeError`, which the `except` below swallows into `None`, which
        # this function's contract renders as `on` — so **every failing
        # schedule would have drawn green**, silently, with every test passing.
        # Caught by reading `apps/tenancy/selectors.report_run`'s signature
        # rather than by any check, which is the brief's own instruction: find
        # things by symbol, never by assuming the call.
        #
        # They come from `run_history`'s own registries rather than from
        # literals here, so a fifth export resource or a second job kind is
        # picked up by this status column for free — the same reason
        # `report_resources()` is read from `exports.RESOURCES`.
        return found(
            job_id,
            resources=run_history.report_resources(),
            kinds=run_history.RUN_KINDS,
        )
    except Exception:  # noqa: BLE001 — a lookup failure is not a failing schedule
        return None


def status_of(schedule: ReportSchedule) -> str:
    """`On` · `Paused` · `Failing`, derived. See the module docstring."""
    if not schedule.enabled:
        return STATUS_PAUSED
    if schedule.next_run_at is None:
        # Enabled, and it will never fire. See the module docstring.
        return STATUS_FAILING
    job = _job(schedule.last_job_id)
    if job is not None and str(job.get("status")) == "failed":
        return STATUS_FAILING
    return STATUS_ON


def present(schedule: ReportSchedule, *, names: dict[str, str] | None = None) -> dict[str, Any]:
    """One row of `4·1`, in the drawing's own seven fields.

    ⚠ **`id` IS SERVED AND IS NEVER THE VISIBLE VALUE OF A FIELD** (B14 rule
    31). It is the ADDRESS of `4·2` and the target of pause / run-now / delete;
    the row a clerk reads says the report's name, the cadence in words, a date
    and a list of people.

    ⚠ **`recipient_names` AND NOT `recipients`** on the wire for the same rule.
    The ids travel too, because `4·2` has to re-open the picker with the right
    people ticked, and a picker that could only render names would have to
    match them back by string.
    """
    directory = names if names is not None else _names_for([schedule])
    return {
        "id": str(schedule.pk),
        "report": schedule.definition.name,
        "report_key": schedule.definition.key,
        "cadence": schedule.cadence,
        "format": schedule.format,
        "next_run_at": schedule.next_run_at,
        "recipients": [str(value) for value in (schedule.recipients or [])],
        "recipient_names": [directory.get(str(value), "") for value in (schedule.recipients or [])],
        "status": status_of(schedule),
        "params": dict(schedule.params or {}),
    }


def _names_for(rows: list[ReportSchedule]) -> dict[str, str]:
    """Every recipient on this page, resolved in ONE pass.

    ⚠ **ONE LOOKUP PER TENANT, NOT ONE PER ROW PER PERSON.**
    `run_history.actor_names` records the same measurement: a page is fifty
    rows and a utility has ten to twenty staff, so the naive shape is hundreds
    of queries where one will do.
    """
    wanted = {str(value) for row in rows for value in (row.recipients or [])}
    if not wanted:
        return {}
    return {
        person.user_id: person.name
        for person in scheduler.tenant_staff(current_tenant_id())
        if person.user_id in wanted
    }


def _schedules_queryset():
    """⚠ **NO `.filter(tenant_id=…)`, AND THAT IS NOT AN OVERSIGHT.**

    `report_schedules` is RLS FORCE (reports `0005`) and `require_tenant` has
    established the session's tenant. A second enforcement in Python would make
    a MISSING context look like an empty list instead of like the bug it is,
    and is how a lane comes to believe the database half is optional.
    """
    return ReportSchedule.objects.select_related("definition")


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # A4 Reports: Staff/Clerk R/run, Executive Full
def schedules_collection(request: Any) -> Response:
    """`GET /reports/schedules` — `4·1`'s rows · `POST` — `2·3` commits.

    ⚠ **PAGED, ALWAYS, AND CUT IN SQL** (`NFR-3`). Four rows today need no
    pager and get one anyway: `P4.5`'s own ⚠ — *"rule 16 has no small-list
    exemption, and a utility with forty schedules is the case it is for."*
    """
    require_tenant(request)
    if request.method == "POST":
        return _create(request)
    params = request.query_params
    page = _positive_int(params.get("page"), 1)
    per = _positive_int(params.get("per"), DEFAULT_PER)
    query = str(params.get("q") or "").strip()
    rows = _schedules_queryset()
    if query:
        rows = rows.filter(definition__name__icontains=query)
    status_filter = params.get("f.status")
    total = rows.count()
    ordered = list(rows.order_by("next_run_at", "id")[(page - 1) * per : page * per])
    names = _names_for(ordered)
    presented = [present(row, names=names) for row in ordered]
    if status_filter in SCHEDULE_STATUSES:
        # ⚠ **FILTERED AFTER PRESENTING, BECAUSE STATUS IS DERIVED AND NOT A
        # COLUMN.** Filtering in SQL would need `failing` to be stored, which
        # is the thing `P4.8` is written to avoid. The cost is that the page
        # is cut before the filter — acceptable while `enabled` is the only
        # SQL-expressible half and a utility has tens of schedules, and stated
        # here rather than discovered. If a tenant ever holds thousands,
        # `enabled` moves into the queryset and `failing` stays here.
        presented = [row for row in presented if row["status"] == status_filter]
    return Response(
        {
            "rows": presented,
            "total": total,
            "page": page,
            "per": per,
            # The picker's options and the two selects', served WITH the page so
            # the screen needs one call and types no list out by hand (B14 rule
            # 2's worked case: an eleventh service that never appeared).
            "cadences": list(CADENCES),
            "formats": list(FORMATS),
            "statuses": list(SCHEDULE_STATUSES),
            "staff": [
                {"id": person.user_id, "name": person.name}
                for person in scheduler.tenant_staff(current_tenant_id())
            ],
        }
    )


def _create(request: Any) -> Response:
    """`POST /reports/schedules` — `2·3`'s three fields plus what it inherits.

    The report and its parameters come from the screen behind (p34: *"The
    report, its parameters and its name are inherited from the screen behind"*),
    so the body carries `definition_key` and `params` as well as the three
    fields a person actually filled in.
    """
    body = request.data if isinstance(request.data, dict) else {}
    definition = _definition_or_refuse(body.get("definition_key"))
    # ⚠ BEFORE ANY OTHER VALIDATION. A refused role must not be able to probe
    # the cadence or format vocabularies by reading which field the 422 names.
    _role_gate_or_refuse(definition, request)
    cadence = _one_of(body.get("cadence"), CADENCES, field="cadence")
    fmt = _one_of(_format_or_tenant_default(body.get("format")), FORMATS, field="format")
    people = _recipients_or_refuse(body.get("recipients"))
    schedule = ReportSchedule(
        tenant_id=current_tenant_id(),
        definition=definition,
        cadence=cadence,
        params=dict(body.get("params") or {}),
        format=fmt,
        recipients=[person.user_id for person in people],
        enabled=True,
        created_by_user_id=getattr(request.user, "id", None),
    )
    # ⚠ **COMPUTED BEFORE THE FIRST SAVE, NOT AFTER.** A row saved with
    # `next_run_at = NULL` and corrected a statement later is, for that instant,
    # a schedule the sweep cannot see — and if the second statement fails it
    # stays that way for ever, looking enabled.
    schedule.next_run_at = scheduler.next_run_at(cadence, after=timezone.now())
    schedule.save()
    # CLAUDE.md rule 7 — this is not a money action, and the row is written
    # anyway: a standing instruction to send a utility's own financial reports
    # to named people is exactly the kind of act a support cycle has to be able
    # to reconstruct. `p34 ④` names `audit_log` explicitly.
    core_audit.money_action(
        request.user,
        "report_schedule.created",
        "report_schedules",
        str(schedule.pk),
        after={
            "report": definition.key,
            "cadence": cadence,
            "format": fmt,
            "recipients": [person.user_id for person in people],
        },
    )
    return Response(present(schedule), status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def schedule_detail(request: Any, schedule_id: uuid.UUID) -> Response:
    """`4·2` — one schedule opened, edited, paused/resumed, or deleted.

    ⚠ **ABSENT, MALFORMED AND ANOTHER TENANT'S ARE ALL THE SAME PLAIN 404**
    (HR-1 / 11b G4: existence must not leak, and a distinguishable message
    would confirm the id). Under RLS FORCE another tenant's row is not visible
    to this query at all, so this is the database's answer rather than a check
    that could be forgotten.
    """
    require_tenant(request)
    schedule = _schedules_queryset().filter(pk=schedule_id).first()
    if schedule is None:
        raise errors.NotFoundError()
    if request.method == "GET":
        return Response(present(schedule))
    if request.method == "DELETE":
        # p41 ④: *"Delete removes the schedule and LEAVES EVERY PAST RUN ON
        # 5·1, because a run is a historical fact."* That falls out of the
        # design rather than being enforced here — the runs are `jobs` rows and
        # this table does not own them.
        core_audit.money_action(
            request.user,
            "report_schedule.deleted",
            "report_schedules",
            str(schedule.pk),
            before={"report": schedule.definition.key, "cadence": schedule.cadence},
        )
        schedule.delete()
        return Response(status=204)
    return _update(request, schedule)


def _update(request: Any, schedule: ReportSchedule) -> Response:
    """PATCH — the three fields, and pause/resume.

    ⚠ **PAUSE CLEARS `next_run_at` AND RESUME RECOMPUTES IT** (p41 ④, verbatim:
    *"Pause writes `enabled=false` on one schedule row and clears
    `next_run_at`; nothing else moves"*). Resuming does NOT restore the old
    date: a schedule paused in August and resumed in October would otherwise be
    due two months ago and fire immediately, which is not what *resume* means to
    the person pressing it.
    """
    body = request.data if isinstance(request.data, dict) else {}
    before = {
        "cadence": schedule.cadence,
        "format": schedule.format,
        "recipients": list(schedule.recipients or []),
        "enabled": schedule.enabled,
    }
    if "cadence" in body:
        schedule.cadence = _one_of(body.get("cadence"), CADENCES, field="cadence")
    if "format" in body:
        schedule.format = _one_of(body.get("format"), FORMATS, field="format")
    if "recipients" in body:
        schedule.recipients = [
            person.user_id for person in _recipients_or_refuse(body.get("recipients"))
        ]
    if "enabled" in body:
        schedule.enabled = bool(body.get("enabled"))
    if not schedule.enabled:
        schedule.next_run_at = None
    else:
        schedule.next_run_at = scheduler.next_run_at(schedule.cadence, after=timezone.now())
    schedule.save()
    core_audit.money_action(
        request.user,
        "report_schedule.updated",
        "report_schedules",
        str(schedule.pk),
        before=before,
        after={
            "cadence": schedule.cadence,
            "format": schedule.format,
            "recipients": list(schedule.recipients or []),
            "enabled": schedule.enabled,
        },
    )
    return Response(present(schedule))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def schedule_run_now(request: Any, schedule_id: uuid.UUID) -> Response:
    """`POST /reports/schedules/{id}/run-now` — `4·1`'s ▶ row action.

    ⚠ **IT DOES NOT ADVANCE `next_run_at`** (p41 ④, verbatim: *"Run now writes
    a job row, which appears on `5·1` within a second and produces a file — ⚠
    it does NOT advance `next_run_at`, so the scheduled run still happens."*)
    A clerk checking that a schedule works must not thereby cancel Monday's run.

    ⚠ **AND ITS SCOPE KEY CARRIES THE MOMENT, NOT THE DUE DATE**, so pressing
    ▶ twice deliberately produces two files while the SWEEP still folds. Two
    people pressing it in the same second is the one case that folds, which is
    the right answer for that case too.
    """
    require_tenant(request)
    schedule = _schedules_queryset().filter(pk=schedule_id).first()
    if schedule is None:
        raise errors.NotFoundError()
    now = timezone.now()
    record = scheduler._enqueue(
        schedule,
        scope=scheduler.scope_key(schedule.pk, now),
        actor=request.user,
    )
    schedule.last_job_id = record["id"]
    schedule.save(update_fields=["last_job_id", "updated_at"])
    return Response({"job_id": record["id"], "schedule": present(schedule)}, status=202)


# ── refusals ───────────────────────────────────────────────────────────────


def _definition_or_refuse(key: Any) -> ReportDefinition:
    """The report being scheduled, or `VAL-005` naming what was asked for.

    ⚠ **A 404 WOULD BE WRONG HERE.** The caller is not addressing a resource;
    it is naming one inside a body, and an unknown name there is a validation
    fault the screen can show against the field. `api.report`'s own docstring
    makes the same choice for the same reason.
    """
    wanted = str(key or "").strip()
    found = (
        ReportDefinition.objects.filter(key=wanted).order_by("tenant_id").first()
        if wanted
        else None
    )
    if found is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.schedule.unknown_report",
            params={"key": wanted},
            field_errors=[{"field": "definition_key", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    return found


def _role_gate_or_refuse(definition: ReportDefinition, request: Any) -> None:
    """`P5.9`'s role floor, applied HERE and not only on the read path.

    ⚠ **`DEF-REP-6907`'s SIBLING, AND IT WAS A REAL HOLE** (`DEF-REP-6923`).
    `BR-REP-023` gives a report a `min_role`, and `api.report` refuses a run of
    one with `403 AUTH-002`. This endpoint resolved the SAME definition and
    never asked — so a Billing Clerk refused `staff-directory` at `2·1` could
    `POST` a schedule for that key and have the file delivered to themselves
    every month. A role floor that one endpoint enforces and another does not
    is not a floor; it is a detour.

    ⚠ **IT WAS UNREACHABLE FROM THE PRODUCT UNTIL TODAY, WHICH IS WHY NOTHING
    FOUND IT.** `DEF-REP-6913` hung the Schedule door on `2·1`; before that no
    screen posted here at all, so the only walk that could have shown it was
    one nobody could perform. A gap behind an unbuilt door is still a gap, and
    it becomes a live one the moment the door is hung.

    The refusal is `role_gate.refusal`, the SAME one the viewer answers, so a
    clerk who is refused the report never meets two different sentences for one
    fact.
    """
    # ⚠ **`request.tenant_role`, NOT `request.user.role` (DEF-REP-9161).** The
    # role is the one the server attached for THIS tenant — the attribute every
    # BE-04 permission class and `api.report`'s own floor read. Sign-in sets the
    # two from the same membership, so a browser could not tell them apart; a
    # gate reading a different attribute from its sibling is still two gates.
    if not role_gate.may_run(role_gate.for_key(definition.key), getattr(request, "tenant_role", None)):
        raise role_gate.refusal(definition.key)


def _format_or_tenant_default(value: Any) -> Any:
    """The format the body named, or THIS utility's default when it named none.

    `CR-142-BRC07` `P4.6` — the *Default format* card's whole reason to exist.
    A setting nothing reads is a stored preference, not a setting, so the one
    place a format is chosen without a person choosing it asks the kernel that
    writes the file.

    ⚠ **IT NEVER INVENTS A VALUE.** `_one_of` below still refuses anything
    outside `FORMATS`, so a tenant row holding a format this product cannot
    produce is refused BY NAME rather than written into a schedule that would
    then fail every time it fired.
    """
    named = str(value or "").strip()
    if named:
        return named
    default = report_seams.resolve("tenancy", "default_download_format", kind="exports")
    return default() if default is not None else value


def _one_of(value: Any, allowed: tuple[str, ...], *, field: str) -> str:
    """One of a SIGNED vocabulary, or `VAL-005`.

    ⚠ **THE CHECK CONSTRAINT IS NOT ENOUGH ON ITS OWN.** A fifth cadence
    reaching the database raises `IntegrityError`, which reaches a clerk as a
    500 and says nothing. This is the same refusal one layer up, with a field
    name the form can point at.
    """
    wanted = str(value or "").strip()
    if wanted not in allowed:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=f"reports.schedule.unknown_{field}",
            params={field: wanted, "allowed": list(allowed)},
            field_errors=[{"field": field, "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    return wanted


def _recipients_or_refuse(value: Any) -> tuple[scheduler.Recipient, ...]:
    """`BR-REP-020` at the boundary — internal staff only, refused BY NAME.

    ⚠ **THE MODULE REFUSES AND THIS TRANSLATES; NEITHER FILTERS.** See
    `schedules.resolve_recipients`: a silently dropped recipient is a month-end
    pack that never reaches the person it was scheduled for, with nothing on
    screen saying why.
    """
    wanted = value if isinstance(value, list) else []
    try:
        return scheduler.resolve_recipients(current_tenant_id(), wanted)
    except scheduler.RecipientError as refusal:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.schedule.recipient_not_internal",
            params={"recipients": list(refusal.unknown)},
            field_errors=[{"field": "recipients", "code": errors.VAL_UNKNOWN_LOOKUP}],
        ) from refusal


#: Extended onto `api.urlpatterns`. ⚠ **DECLARED ABOVE `reports/<key>` BY THE
#: ORDER OF THAT EXTENSION** — `schedules` sits in the same URL position as a
#: report key, so a catch-all declared first would swallow it and a client
#: asking for the list would get a 422 about a report named *schedules*. It is
#: the same fault `P0.11` ranks the four reserved segments above `{key}` for.
SCHEDULE_URLS = [
    path("reports/schedules", schedules_collection),
    path("reports/schedules/<uuid:schedule_id>", schedule_detail),
    path("reports/schedules/<uuid:schedule_id>/run-now", schedule_run_now),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.4 · P4.5 (server half) (05-prototype/09 Reports Build Brief.pdf pp34, 40, 41, read as images per B14 rule 42)
# screens: 2·3 · 4·1 · 4·2
# generated: 2026-09-27 by lane REP-P4
# checklist: A✔ B=n/a(the screens are P4.4/P4.5's own files) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p4_schedules_api.py was run before this file existed and reported `django.urls.exceptions.Resolver404` on /api/brazosbend/reports/schedules.
# exceptions: (1) the `f.status` filter is applied AFTER the page is cut, because status is DERIVED and not a column — stated in `schedules_collection` rather than discovered · (2) this file is separate from `api.py` for hard-won law 11's reason, not for tidiness
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
