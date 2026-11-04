# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 utility-defined meter-read FORMATS, the
#           server (task 10 of 13). Decision log 2026-10-24, the three rows
#           headed "MQ-033".
# Rules:    BR-MET-1210 (formats are the utility's own, nothing seeded) ·
#           BR-MET-1211 (questions typed like custom fields, plus Photo) ·
#           BR-MET-1212 (route → cycle → service → none; replace = move a
#           pointer; only a published format is pointed at) · BR-MET-1213
#           (versioned; a published version never changes) · BR-MET-1214
#           (asked when · follow-ups) · BR-MET-1215 (answers travel in the
#           reading's item, stamped with the version) · BR-MET-1216 (never
#           dropped — stored and flagged) · BR-MET-1217 (raise a work order) ·
#           BR-MET-1218 (shown on the reading, filterable) · BR-WRK-008 ·
#           BR-WRK-067 · CLAUDE.md hard rules 1, 3, 7 · hard-won law 14 ·
#           NFR-3 / NFR-5
# Tests:    06-backend/tests/test_mq033_read_formats.py ·
#           06-backend/tests/test_mq033_read_answers.py ·
#           06-backend/tests/test_mq033_read_answers_pg.py
# Impacts:  apps/metering/read_formats_api.py · apps/metering/field_reads.py
#           (answers on each reading item) · apps/metering/field_routes.py
#           (the resolved format rides with the route) · apps/metering/api.py
#           (answers on the reading detail; `answer[<key>]=` on the reads list)
#           · apps/work/route_findings.py (`raise_for_read_answer`)
# ───────────────────────────────────────────────────────
"""Settings → Reads: a utility's own meter-read FORMATS, and the answers.

THE RULING, VERBATIM — read these before changing anything here
────────────────────────────────────────────────────────────────────────────
Decision log 2026-10-24, *"MQ-033: METER-READ FORMAT TEMPLATES (option B)"*:
*"B. Reading templates, like work templates - we understand your
recommendation , but utility users want customizations they wantt to collect
various data during meter reads hence we need to create meter read format
templates so that the customization can be handled"*.

*"MQ-033 read templates: WHERE, WHAT CHOOSES ONE, AND NOTHING READY-MADE"*:
*"3. Settings → Reads; The template is chosen automatically: route → cycle →
service. A route can override its cycle, and a cycle its service. we can set
it once or we can create another format for same service and replace it
later"* — and *"this is all user defined we dont have to provide anything
readymade , this will be similar to custom fields"*.

*"MQ-033 read formats: SUMMARY CONFIRMED, ALL THREE QUESTION BEHAVIOURS IN
THE FIRST RELEASE"*: *"this is correct"* — to: questions typed like custom
fields plus Photo, versioned; **asked when** (every reading · out of range ·
can't read · once per stop), **follow-ups** (an answer reveals another
question or requires a photo) and **raise a work order** (an answer raises a
job of a utility-chosen type, linked back to the reading); answers travel
inside the reading's own item (batches of 50 unchanged), are checked on the
server against the same version, **never cause a reading to be dropped
(stored and flagged instead)**, and are shown on the reading, filterable in
Reads lists and exported.

JUDGMENTS WHERE THE RULING RAN OUT (decision log 2026-10-24, lane
MQ033-SERVER — recorded, not put to the PO, law 13)
────────────────────────────────────────────────────────────────────────────
1. **A *"utility-chosen type"* is a published Work job TEMPLATE.** Work raises
   a job only from a template (`BR-WRK-008`), and a template carries its type.
   So `raise_work = {"on_answer": …, "template_id": …}`.
2. **"Every reading" means every reading a FIGURE was taken for**, and "can't
   read" every item marked *could not read*. The PO listed them as two
   options; read as one, "can't read" would be a subset of "every reading" and
   pointless. An answer given where its question was not asked is KEPT and
   flagged `not_asked`.
3. **"Out of range" is the ENGINE's verdict**, not the phone's: the question
   applies when the posted reading carries a HIGH, LOW or ZERO warning
   (`field_reads.OUT_OF_RANGE_RULES` — not every flag: a vacant unit is not
   out of range), or the reader accepted a warned figure anyway (R80). The phone asks from its own
   expected range; a disagreement is flagged, never refused.
4. **"Once per stop" is satisfied by ANY reading at the same stop on the same
   route on the same capture day** — this request or an earlier one. Only
   when none answered it is a missing required answer flagged.
5. **A reading item whose version this server does not hold keeps its answers**
   with `version_unknown` (`version_id` NULL); a draft version id is
   unknown too, because no handset is ever sent one.
6. **The raise happens for a reading that was STORED as posted or recorded**;
   a reading on a meter awaiting acceptance (R85) raises nothing until the
   office accepts the meter — nothing here re-runs it then (reported).
7. **Retiring a format still pointed at is refused**, naming the counts:
   *"replace it later"* is moving the pointer first.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.metering import models, seams
from apps.metering.read_format_models import (
    ASKED_CANT_READ,
    ASKED_EVERY_READING,
    ASKED_ONCE_PER_STOP,
    ASKED_OUT_OF_RANGE,
    ASKED_WHEN,
    FORMAT_DRAFT,
    FORMAT_PUBLISHED,
    FORMAT_RETIRED,
    FORMAT_STATUSES,
    ISSUE_NOT_AN_OPTION,
    ISSUE_NOT_ASKED,
    ISSUE_NOT_SHOWN,
    ISSUE_REQUIRED_MISSING,
    ISSUE_UNKNOWN_QUESTION,
    ISSUE_VERSION_UNKNOWN,
    ISSUE_WRONG_TYPE,
    PHOTO,
    VERSION_DRAFT,
    VERSION_PUBLISHED,
    ReadAnswer,
    ReadFormat,
    ReadFormatDefault,
    ReadFormatQuestion,
    ReadFormatVersion,
)
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

#: The envelope key every refusal of a format edit carries; the field errors
#: under it name each field (BR-SHL-037's one envelope).
INVALID = "metering.readFormats.invalid"
BR = "BR-MET-1212"

#: A text answer is kept whole up to this; the handset's own cap is lower.
TEXT_ANSWER_MAX = 2000
#: Field-reading `answers` beyond this many in one item are not a form any
#: utility built; they are kept in the item's `received_payload` (as every
#: field is) and not expanded into rows. Not a cap on questions (NFR-5): a
#: version may hold any number; an item answers each question at most once.
ANSWERS_PER_ITEM_MAX = 500


# ══════════════════════════════════════════════════════════════════════════
# Small helpers
# ══════════════════════════════════════════════════════════════════════════
def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]], message_key: str = INVALID) -> None:
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key=message_key, field_errors=field_errors, br_ref=BR
        )


def _text(value: Any, limit: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit] if limit else text


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _vocab() -> dict[str, Any]:
    return seams.custom_field_vocabulary()


def data_types() -> tuple[str, ...]:
    """The custom-field types (read from tenancy, never copied) plus `photo`."""
    return (*_vocab()["data_types"], PHOTO)


def _audit(actor: Any, action: str, entity_type: str, entity_id: Any, **after: Any) -> None:
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=_actor_id(actor),
        after={**after, "br_ref": BR},
    )


def _format_or_404(format_id: Any) -> ReadFormat:
    if not _is_uuid(format_id):
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    row = (
        ReadFormat.objects.filter(tenant_id=_tenant_id(), pk=format_id)
        .select_related("service", "current_version")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return row


def _draft_of(fmt: ReadFormat) -> ReadFormatVersion | None:
    return ReadFormatVersion.objects.filter(
        tenant_id=fmt.tenant_id, read_format=fmt, state=VERSION_DRAFT
    ).first()


def _draft_or_refuse(fmt: ReadFormat) -> ReadFormatVersion:
    """The draft a question edit lands on. A published version is NEVER
    edited (BR-MET-1213): with no draft open the edit is refused by name and
    the screen offers *New draft*."""
    if fmt.status == FORMAT_RETIRED:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.retired"
        )
    draft = _draft_of(fmt)
    if draft is None:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.published_locked"
        )
    return draft


# ══════════════════════════════════════════════════════════════════════════
# Serialisers — every value a screen draws is a word or a number a clerk
# quotes; `id`s are ADDRESSES (B14 rule 31)
# ══════════════════════════════════════════════════════════════════════════
def question_dict(q: ReadFormatQuestion, *, templates: dict[str, Any] | None = None) -> dict[str, Any]:
    raise_work = None
    if q.raise_work:
        template_id = str(q.raise_work.get("template_id") or "")
        template = (templates or {}).get(template_id)
        raise_work = {
            "on_answer": q.raise_work.get("on_answer"),
            "template_id": template_id or None,
            "template": (
                {"name": template["name"], "template_no": template.get("template_no")}
                if template
                else None
            ),
        }
    return {
        "id": str(q.id),
        "seq": q.seq,
        "key": q.key,
        "label": q.label,
        "help_text": q.help_text,
        "data_type": q.data_type,
        "options": q.options,
        "is_required": q.is_required,
        "asked_when": q.asked_when,
        "show_if": q.show_if,
        "raise_work": raise_work,
    }


def _questions(version: ReadFormatVersion) -> list[ReadFormatQuestion]:
    return list(
        ReadFormatQuestion.objects.filter(tenant_id=version.tenant_id, version=version).order_by(
            "seq", "created_at", "id"
        )
    )


def _templates_for(questions: list[ReadFormatQuestion]) -> dict[str, Any]:
    """The job templates the page's questions name — one Work read per
    DISTINCT template, never per row (DEF-324's shape)."""
    out: dict[str, Any] = {}
    for q in questions:
        template_id = str((q.raise_work or {}).get("template_id") or "")
        if template_id and template_id not in out:
            out[template_id] = seams.work_job_template(template_id)
    return out


def version_dict(version: ReadFormatVersion, *, with_questions: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(version.id),
        "read_format_id": str(version.read_format_id),
        "state": version.state,
        "version_no": version.version_no,
        "change_note": version.change_note,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "published_by": (
            (getattr(version.published_by, "full_name", None) or None)
            if version.published_by_id
            else None
        ),
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
    if with_questions:
        questions = _questions(version)
        templates = _templates_for(questions)
        out["questions"] = [question_dict(q, templates=templates) for q in questions]
    return out


def _use_counts(format_ids: list[Any]) -> dict[str, dict[str, int]]:
    """How many routes, cycles and service defaults point at each format —
    three grouped COUNTs for the whole page, never one per row."""
    tenant_id = _tenant_id()
    out: dict[str, dict[str, int]] = {
        str(f): {"routes": 0, "cycles": 0, "services": 0} for f in format_ids
    }
    if not format_ids:
        return out
    for model, name in ((models.Route, "routes"), (models.Cycle, "cycles")):
        for row in (
            model.objects.filter(
                tenant_id=tenant_id, read_format_id__in=format_ids, deleted_at__isnull=True
            )
            .values("read_format_id")
            .annotate(n=Count("id"))
        ):
            out[str(row["read_format_id"])][name] = row["n"]
    for row in (
        ReadFormatDefault.objects.filter(tenant_id=tenant_id, read_format_id__in=format_ids)
        .values("read_format_id")
        .annotate(n=Count("id"))
    ):
        out[str(row["read_format_id"])]["services"] = row["n"]
    return out


def format_dict(
    fmt: ReadFormat,
    *,
    use: dict[str, int] | None = None,
    draft: ReadFormatVersion | None = None,
    detail: bool = False,
) -> dict[str, Any]:
    current = fmt.current_version if fmt.current_version_id else None
    out: dict[str, Any] = {
        "id": str(fmt.id),
        "name": fmt.name,
        "service": {"code": fmt.service.code, "name": fmt.service.name},
        "status": fmt.status,
        "current_version": (
            {
                "id": str(current.id),
                "version_no": current.version_no,
                "published_at": current.published_at.isoformat() if current.published_at else None,
            }
            if current is not None
            else None
        ),
        "draft_version_id": str(draft.id) if draft is not None else None,
        "used_by": use if use is not None else _use_counts([fmt.id])[str(fmt.id)],
        "retired_at": fmt.retired_at.isoformat() if fmt.retired_at else None,
        "created_at": fmt.created_at.isoformat() if fmt.created_at else None,
        "updated_at": fmt.updated_at.isoformat() if fmt.updated_at else None,
    }
    if detail:
        out["current"] = version_dict(current) if current is not None else None
        out["draft"] = version_dict(draft) if draft is not None else None
    return out


# ══════════════════════════════════════════════════════════════════════════
# Reads — the Settings → Reads list and one format (NFR-3: paged)
# ══════════════════════════════════════════════════════════════════════════
def formats_queryset(
    *, service: Any = None, status: Any = None, q: Any = None
) -> Any:
    """The tenant's formats, newest edit first, filtered. A QUERYSET — the API
    pages it with one COUNT and one LIMIT (NFR-3); nothing here caps (NFR-5)."""
    qs = ReadFormat.objects.filter(tenant_id=_tenant_id()).select_related(
        "service", "current_version"
    )
    service_code = _text(service, 40)
    if service_code:
        qs = qs.filter(service__code=service_code)
    status_text = _text(status, 20)
    if status_text in FORMAT_STATUSES:
        qs = qs.filter(status=status_text)
    term = _text(q, 120)
    if term:
        qs = qs.filter(name__icontains=term)
    return qs.order_by("-updated_at", "name", "id")


def list_page_rows(rows: list[ReadFormat]) -> list[dict[str, Any]]:
    """Serialise ONE page: use counts and drafts read once for the page."""
    ids = [row.id for row in rows]
    use = _use_counts(ids)
    drafts = {
        str(v.read_format_id): v
        for v in ReadFormatVersion.objects.filter(
            tenant_id=_tenant_id(), read_format_id__in=ids, state=VERSION_DRAFT
        )
    }
    return [format_dict(row, use=use[str(row.id)], draft=drafts.get(str(row.id))) for row in rows]


def get_format(format_id: Any) -> dict[str, Any]:
    fmt = _format_or_404(format_id)
    return format_dict(fmt, draft=_draft_of(fmt), detail=True)


def versions_queryset(format_id: Any) -> Any:
    fmt = _format_or_404(format_id)
    return (
        ReadFormatVersion.objects.filter(tenant_id=fmt.tenant_id, read_format=fmt)
        .select_related("published_by")
        .order_by("-version_no", "-created_at", "id")
    )


def get_version(version_id: Any, *, published_only: bool = False) -> dict[str, Any]:
    """One version with its questions. `published_only` is the handset's door:
    a phone is only ever sent a published version (it caches by this id)."""
    if not _is_uuid(version_id):
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    qs = ReadFormatVersion.objects.filter(tenant_id=_tenant_id(), pk=version_id).select_related(
        "read_format", "read_format__service", "published_by"
    )
    if published_only:
        qs = qs.filter(state=VERSION_PUBLISHED)
    version = qs.first()
    if version is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    out = version_dict(version)
    out["read_format"] = {
        "id": str(version.read_format_id),
        "name": version.read_format.name,
        "service": version.read_format.service.code,
    }
    return out


# ══════════════════════════════════════════════════════════════════════════
# Writes — a format and its draft (System Admin: Settings is A4 "Full" for
# System Admin and "View" for Executive)
# ══════════════════════════════════════════════════════════════════════════
def _service_or_refuse(raw: Any, fe: list[dict[str, Any]]) -> Any:
    code = _text(raw, 40)
    if not code:
        fe.append(_fe("service", errors.VAL_REQUIRED, "errors.val-001"))
        return None
    if code not in seams.enabled_service_codes():
        fe.append(_fe("service", errors.VAL_UNKNOWN_LOOKUP, "errors.val-005", value=code))
        return None
    service_id = seams.service_id_by_code(code)
    if service_id is None:  # pragma: no cover — an enabled code is in the catalog
        fe.append(_fe("service", errors.VAL_UNKNOWN_LOOKUP, "errors.val-005", value=code))
    return service_id


def _name_or_refuse(raw: Any, fe: list[dict[str, Any]], *, exclude: Any = None) -> str | None:
    name = _text(raw)
    if not name:
        fe.append(_fe("name", errors.VAL_REQUIRED, "errors.val-001"))
        return None
    if len(name) > _vocab()["label_max"]:
        fe.append(_fe("name", errors.VAL_RANGE, "errors.val-003", max=_vocab()["label_max"]))
        return None
    clash = ReadFormat.objects.filter(tenant_id=_tenant_id(), name__iexact=name)
    if exclude is not None:
        clash = clash.exclude(pk=exclude)
    if clash.exists():
        fe.append(_fe("name", errors.VAL_FORMAT, "metering.readFormats.name_taken", value=name))
        return None
    return name


def _unknown_fields(data: dict[str, Any], allowed: set[str]) -> None:
    _refuse(
        [_fe(f, errors.VAL_FORMAT, "settings.unknown_field") for f in sorted(set(data) - allowed)]
    )


def _payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    return payload


@require_role(SYSTEM_ADMIN)
def create_format(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST settings/read-formats` `{name, service, change_note?}` — a format
    in DRAFT with its first (empty) draft version. Nothing is pre-filled
    (*"we dont have to provide anything readymade"*)."""
    data = _payload(payload)
    _unknown_fields(data, {"name", "service", "change_note"})
    fe: list[dict[str, Any]] = []
    name = _name_or_refuse(data.get("name"), fe)
    service_id = _service_or_refuse(data.get("service"), fe)
    _refuse(fe)
    tenant_id = _tenant_id()
    try:
        with transaction.atomic():
            fmt = ReadFormat.objects.create(
                tenant_id=tenant_id,
                name=name,
                service_id=service_id,
                status=FORMAT_DRAFT,
                created_by_id=_actor_id(actor),
            )
            ReadFormatVersion.objects.create(
                tenant_id=tenant_id,
                read_format=fmt,
                state=VERSION_DRAFT,
                change_note=_text(data.get("change_note"), 500),
            )
    except IntegrityError:
        # Two clerks naming a format the same at once: the unique key answers.
        _refuse([_fe("name", errors.VAL_FORMAT, "metering.readFormats.name_taken", value=name)])
    _audit(actor, "read_format.created", "read_format", fmt.id, name=name)
    return get_format(fmt.id)


@require_role(SYSTEM_ADMIN)
def update_format(actor: Any, format_id: Any, payload: Any) -> dict[str, Any]:
    """`PATCH settings/read-formats/{id}` `{name?, service?, change_note?}`.

    `name` at any status but retired; `service` only while the format has
    never been published (a published version's answers were asked of that
    service's readings); `change_note` lands on the open draft."""
    data = _payload(payload)
    _unknown_fields(data, {"name", "service", "change_note"})
    fmt = _format_or_404(format_id)
    if fmt.status == FORMAT_RETIRED:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.retired"
        )
    fe: list[dict[str, Any]] = []
    fields: list[str] = []
    if "name" in data:
        name = _name_or_refuse(data.get("name"), fe, exclude=fmt.id)
        if name:
            fmt.name = name
            fields.append("name")
    if "service" in data:
        if fmt.current_version_id:
            fe.append(_fe("service", errors.VAL_FORMAT, "metering.readFormats.published_locked"))
        else:
            service_id = _service_or_refuse(data.get("service"), fe)
            if service_id:
                fmt.service_id = service_id
                fields.append("service")
    draft = _draft_of(fmt)
    if "change_note" in data:
        if draft is None:
            fe.append(_fe("change_note", errors.VAL_FORMAT, "metering.readFormats.published_locked"))
        else:
            draft.change_note = _text(data.get("change_note"), 500)
    _refuse(fe)
    with transaction.atomic():
        if fields:
            fmt.save(update_fields=[*fields, "updated_at"])
        if draft is not None and "change_note" in data:
            draft.save(update_fields=["change_note", "updated_at"])
    _audit(actor, "read_format.updated", "read_format", fmt.id, changed=sorted(data))
    return get_format(fmt.id)


# ── questions ───────────────────────────────────────────────────────────────
def _valid_value_for(q_type: str, options: Any, value: Any) -> bool:
    """Whether `value` is a lawful ANSWER to a question of this type — used for
    `show_if.answer` and `raise_work.on_answer`, which must be answers the
    question can actually receive."""
    if value is None:
        return False
    if q_type in _vocab()["select_types"]:
        return isinstance(value, str) and value in (options or [])
    if q_type == "boolean":
        return isinstance(value, bool)
    if q_type == "number":
        return _number(value) is not None
    if q_type == "date":
        return _date(value) is not None
    if q_type == PHOTO:
        return False
    return isinstance(value, str) and bool(value.strip())


def _validate_question(
    data: dict[str, Any],
    version: ReadFormatVersion,
    *,
    existing: ReadFormatQuestion | None = None,
) -> dict[str, Any]:
    """Validate a question create or edit and return the column values.

    Defined like a custom field (`tenancy.custom_fields.validate_definition`'s
    shape and limits, read through the seam) plus the three behaviours."""
    vocab = _vocab()
    allowed = {
        "label", "key", "help_text", "data_type", "options", "is_required",
        "asked_when", "show_if", "raise_work",
    }
    _unknown_fields(data, allowed)
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    merged = {
        "label": existing.label if existing else None,
        "help_text": existing.help_text if existing else None,
        "data_type": existing.data_type if existing else None,
        "options": existing.options if existing else None,
        "is_required": existing.is_required if existing else False,
        "asked_when": existing.asked_when if existing else ASKED_EVERY_READING,
        "show_if": existing.show_if if existing else None,
        "raise_work": existing.raise_work if existing else None,
        "key": existing.key if existing else None,
    }
    merged.update({k: v for k, v in data.items()})

    label = _text(merged["label"])
    if not label:
        fe.append(_fe("label", errors.VAL_REQUIRED, "errors.val-001"))
    elif len(label) > vocab["label_max"]:
        fe.append(_fe("label", errors.VAL_RANGE, "errors.val-003", max=vocab["label_max"]))
    out["label"] = label

    key = _text(merged["key"]) if merged.get("key") else (vocab["derive_key"](label or "") or None)
    if not key or not vocab["key_re"].match(key):
        fe.append(_fe("key", errors.VAL_FORMAT, "errors.val-002"))
    else:
        clash = ReadFormatQuestion.objects.filter(version=version, key=key)
        if existing is not None:
            clash = clash.exclude(pk=existing.pk)
        if clash.exists():
            fe.append(_fe("key", errors.VAL_FORMAT, "metering.readFormats.key_taken", key=key))
    out["key"] = key

    help_text = _text(merged["help_text"])
    if help_text and len(help_text) > vocab["help_text_max"]:
        fe.append(_fe("help_text", errors.VAL_RANGE, "errors.val-003", max=vocab["help_text_max"]))
    out["help_text"] = help_text

    data_type = _text(merged["data_type"])
    if data_type not in data_types():
        fe.append(
            _fe("data_type", errors.VAL_FORMAT, "settings.customFields.data_type_unknown",
                data_type=data_type or "")
        )
    out["data_type"] = data_type

    options = merged["options"]
    if data_type in vocab["select_types"]:
        if not isinstance(options, list) or not all(isinstance(o, str) and o.strip() for o in options):
            fe.append(_fe("options", errors.VAL_REQUIRED, "errors.val-001"))
            options = None
        else:
            options = [o.strip() for o in options]
            if (
                len(options) < vocab["options_min"]
                or len(options) > vocab["options_max"]
                or len(set(options)) != len(options)
                or any(len(o) > vocab["option_max"] for o in options)
            ):
                fe.append(_fe("options", errors.VAL_RANGE, "errors.val-003",
                              min=vocab["options_min"], max=vocab["options_max"]))
    elif options not in (None, []):
        fe.append(_fe("options", errors.VAL_FORMAT, "errors.val-002"))
        options = None
    else:
        options = None
    out["options"] = options

    if not isinstance(merged["is_required"], bool):
        fe.append(_fe("is_required", errors.VAL_FORMAT, "errors.val-002"))
    out["is_required"] = bool(merged["is_required"])

    asked_when = _text(merged["asked_when"]) or ASKED_EVERY_READING
    if asked_when not in ASKED_WHEN:
        fe.append(_fe("asked_when", errors.VAL_UNKNOWN_LOOKUP, "errors.val-005", value=asked_when))
    out["asked_when"] = asked_when

    # ── follow-up: `show_if` must name an EARLIER question of THIS version ──
    show_if = merged["show_if"]
    if show_if in (None, {}):
        out["show_if"] = None
    elif not isinstance(show_if, dict) or set(show_if) - {"question_key", "answer"}:
        fe.append(_fe("show_if", errors.VAL_FORMAT, "errors.val-002"))
    else:
        parent_key = _text(show_if.get("question_key"))
        my_seq = existing.seq if existing is not None else _next_seq(version)
        parent = (
            ReadFormatQuestion.objects.filter(version=version, key=parent_key).first()
            if parent_key
            else None
        )
        # Earlier = a LOWER seq; a question cannot follow itself. Earlier-only
        # makes a cycle impossible by construction (a chain only runs upward).
        if (
            parent is None
            or (existing is not None and parent.pk == existing.pk)
            or parent.seq >= my_seq
        ):
            fe.append(
                _fe("show_if", errors.VAL_FORMAT, "metering.readFormats.show_if_earlier",
                    question_key=parent_key or "")
            )
        elif not _valid_value_for(parent.data_type, parent.options, show_if.get("answer")):
            fe.append(_fe("show_if", errors.VAL_FORMAT, "errors.val-002"))
        out["show_if"] = {"question_key": parent_key, "answer": show_if.get("answer")}

    # ── raise a work order: a published Work template, on a lawful answer ──
    raise_work = merged["raise_work"]
    if raise_work in (None, {}):
        out["raise_work"] = None
    elif not isinstance(raise_work, dict) or set(raise_work) - {"on_answer", "template_id"}:
        fe.append(_fe("raise_work", errors.VAL_FORMAT, "errors.val-002"))
    else:
        template_id = _text(raise_work.get("template_id"))
        template = seams.work_job_template(template_id) if template_id and _is_uuid(template_id) else None
        if template is None or not template.get("published"):
            fe.append(
                _fe("raise_work", errors.VAL_UNKNOWN_LOOKUP,
                    "metering.readFormats.template_unpublished")
            )
        if not _valid_value_for(data_type or "", options, raise_work.get("on_answer")):
            fe.append(_fe("raise_work", errors.VAL_FORMAT, "errors.val-002"))
        out["raise_work"] = {"on_answer": raise_work.get("on_answer"), "template_id": template_id}
    _refuse(fe)
    return out


def _next_seq(version: ReadFormatVersion) -> int:
    top = ReadFormatQuestion.objects.filter(version=version).aggregate(m=Max("seq"))["m"]
    return (top or 0) + 10


@require_role(SYSTEM_ADMIN)
def add_question(actor: Any, format_id: Any, payload: Any) -> dict[str, Any]:
    """`POST settings/read-formats/{id}/questions` — a question at the END of
    the draft. Order is changed with `reorder_questions`."""
    fmt = _format_or_404(format_id)
    draft = _draft_or_refuse(fmt)
    values = _validate_question(_payload(payload), draft)
    try:
        with transaction.atomic():
            row = ReadFormatQuestion.objects.create(
                tenant_id=fmt.tenant_id, version=draft, seq=_next_seq(draft), **values
            )
    except IntegrityError:
        _refuse([_fe("key", errors.VAL_FORMAT, "metering.readFormats.key_taken", key=values["key"])])
    _audit(actor, "read_format.question_added", "read_format", fmt.id, key=row.key)
    return get_format(fmt.id)


def _question_or_404(draft: ReadFormatVersion, key: str) -> ReadFormatQuestion:
    row = ReadFormatQuestion.objects.filter(version=draft, key=str(key)).first()
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return row


@require_role(SYSTEM_ADMIN)
def update_question(actor: Any, format_id: Any, key: str, payload: Any) -> dict[str, Any]:
    """`PATCH settings/read-formats/{id}/questions/{key}` — on the DRAFT only.
    A key a later question's `show_if` names cannot be renamed out from under
    it; the follow-up is re-checked and the edit refused by name."""
    fmt = _format_or_404(format_id)
    draft = _draft_or_refuse(fmt)
    row = _question_or_404(draft, key)
    values = _validate_question(_payload(payload), draft, existing=row)
    if values["key"] != row.key and _dependants(draft, row.key):
        _refuse([_fe("key", errors.VAL_FORMAT, "metering.readFormats.question_in_use", key=row.key)])
    with transaction.atomic():
        for name, value in values.items():
            setattr(row, name, value)
        row.save()
    _audit(actor, "read_format.question_updated", "read_format", fmt.id, key=row.key)
    return get_format(fmt.id)


def _dependants(draft: ReadFormatVersion, key: str) -> list[str]:
    return [
        q.key
        for q in ReadFormatQuestion.objects.filter(version=draft).only("key", "show_if")
        if (q.show_if or {}).get("question_key") == key
    ]


@require_role(SYSTEM_ADMIN)
def delete_question(actor: Any, format_id: Any, key: str) -> dict[str, Any]:
    """`DELETE settings/read-formats/{id}/questions/{key}` — from the DRAFT. A
    question another one follows up on is refused, naming the follow-up: a
    silent cascade would delete a question the clerk did not choose."""
    fmt = _format_or_404(format_id)
    draft = _draft_or_refuse(fmt)
    row = _question_or_404(draft, key)
    dependants = _dependants(draft, row.key)
    if dependants:
        _refuse(
            [_fe("key", errors.VAL_FORMAT, "metering.readFormats.question_in_use",
                 key=row.key, followed_by=dependants)]
        )
    row.delete()
    _audit(actor, "read_format.question_deleted", "read_format", fmt.id, key=key)
    return get_format(fmt.id)


@require_role(SYSTEM_ADMIN)
def reorder_questions(actor: Any, format_id: Any, payload: Any) -> dict[str, Any]:
    """`POST settings/read-formats/{id}/questions/reorder` `{keys: [...]}` —
    every key of the draft, once, in the new order. A follow-up moved above
    the question it follows is refused (that would be a forward reference)."""
    fmt = _format_or_404(format_id)
    draft = _draft_or_refuse(fmt)
    data = _payload(payload)
    _unknown_fields(data, {"keys"})
    keys = data.get("keys")
    rows = {q.key: q for q in _questions(draft)}
    if not isinstance(keys, list) or sorted(map(str, keys)) != sorted(rows):
        _refuse([_fe("keys", errors.VAL_FORMAT, "errors.val-002")])
    position = {str(k): i for i, k in enumerate(keys)}
    fe = [
        _fe("keys", errors.VAL_FORMAT, "metering.readFormats.show_if_earlier",
            question_key=(q.show_if or {}).get("question_key"))
        for q in rows.values()
        if q.show_if and position.get(q.show_if.get("question_key"), 10**9) >= position[q.key]
    ]
    _refuse(fe)
    with transaction.atomic():
        for k, index in position.items():
            rows[k].seq = (index + 1) * 10
            rows[k].save(update_fields=["seq", "updated_at"])
    _audit(actor, "read_format.questions_reordered", "read_format", fmt.id, keys=list(position))
    return get_format(fmt.id)


# ── lifecycle ───────────────────────────────────────────────────────────────
@require_role(SYSTEM_ADMIN)
def publish(actor: Any, format_id: Any, payload: Any = None) -> dict[str, Any]:
    """`POST settings/read-formats/{id}/publish` `{change_note?}` — the draft
    becomes the next numbered version and the one readings are taken under
    from now on (BR-MET-1213). Nothing already answered is re-worded: every
    stored answer keeps the version it was asked under."""
    data = _payload(payload or {})
    _unknown_fields(data, {"change_note"})
    fmt = _format_or_404(format_id)
    draft = _draft_or_refuse(fmt)
    if not ReadFormatQuestion.objects.filter(version=draft).exists():
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.no_questions"
        )
    with transaction.atomic():
        # Row lock on the format: two publishes at once number once each.
        locked = ReadFormat.objects.select_for_update().get(pk=fmt.pk)
        top = (
            ReadFormatVersion.objects.filter(read_format=locked, state=VERSION_PUBLISHED).aggregate(
                m=Max("version_no")
            )["m"]
            or 0
        )
        draft.state = VERSION_PUBLISHED
        draft.version_no = top + 1
        draft.published_at = timezone.now()
        draft.published_by_id = _actor_id(actor)
        if "change_note" in data:
            draft.change_note = _text(data.get("change_note"), 500)
        draft.save()
        locked.current_version = draft
        locked.status = FORMAT_PUBLISHED
        locked.save(update_fields=["current_version", "status", "updated_at"])
    _audit(actor, "read_format.published", "read_format", fmt.id, version_no=draft.version_no)
    return get_format(fmt.id)


@require_role(SYSTEM_ADMIN)
def new_draft(actor: Any, format_id: Any) -> dict[str, Any]:
    """`POST settings/read-formats/{id}/new-draft` — *editing a published
    format creates a new draft version*: a copy of the current version's
    questions. Idempotent: with a draft already open, that draft is answered."""
    fmt = _format_or_404(format_id)
    if fmt.status == FORMAT_RETIRED:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.retired"
        )
    if _draft_of(fmt) is not None:
        return get_format(fmt.id)
    current = fmt.current_version
    try:
        with transaction.atomic():
            draft = ReadFormatVersion.objects.create(
                tenant_id=fmt.tenant_id, read_format=fmt, state=VERSION_DRAFT
            )
            if current is not None:
                ReadFormatQuestion.objects.bulk_create(
                    [
                        ReadFormatQuestion(
                            tenant_id=fmt.tenant_id,
                            version=draft,
                            seq=q.seq,
                            key=q.key,
                            label=q.label,
                            help_text=q.help_text,
                            data_type=q.data_type,
                            options=q.options,
                            is_required=q.is_required,
                            asked_when=q.asked_when,
                            show_if=q.show_if,
                            raise_work=q.raise_work,
                        )
                        for q in _questions(current)
                    ]
                )
    except IntegrityError:
        # A second press raced the first: the one-draft key answered.
        return get_format(fmt.id)
    _audit(actor, "read_format.draft_opened", "read_format", fmt.id)
    return get_format(fmt.id)


@require_role(SYSTEM_ADMIN)
def retire(actor: Any, format_id: Any) -> dict[str, Any]:
    """`POST settings/read-formats/{id}/retire` — withdrawn. Refused while any
    route, cycle or service default points at it, with the three counts:
    *"replace it later"* is moving those pointers first. A retired format's
    versions and every answer given under them are kept."""
    fmt = _format_or_404(format_id)
    if fmt.status == FORMAT_RETIRED:
        return get_format(fmt.id)
    if fmt.current_version_id is None:
        # Never published: nothing was ever asked under it, and a format is
        # never deleted (no delete door) — so there is nothing to retire.
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-MET-1213", message_key="metering.readFormats.not_published"
        )
    use = _use_counts([fmt.id])[str(fmt.id)]
    if any(use.values()):
        raise errors.BizError(
            errors.BIZ_STATE, br_ref=BR, message_key="metering.readFormats.in_use", params=use
        )
    with transaction.atomic():
        # An open draft dies with the format: nothing was ever asked under it.
        ReadFormatQuestion.objects.filter(
            version__read_format=fmt, version__state=VERSION_DRAFT
        ).delete()
        ReadFormatVersion.objects.filter(read_format=fmt, state=VERSION_DRAFT).delete()
        fmt.status = FORMAT_RETIRED
        fmt.retired_at = timezone.now()
        fmt.save(update_fields=["status", "retired_at", "updated_at"])
    _audit(actor, "read_format.retired", "read_format", fmt.id)
    return get_format(fmt.id)


# ══════════════════════════════════════════════════════════════════════════
# Pointers — route → cycle → service. Replacing = moving a pointer.
# ══════════════════════════════════════════════════════════════════════════
def _pointable(raw: Any, *, service_code: str | None) -> ReadFormat | None:
    """The format a pointer may name: PUBLISHED (BR-MET-1212), of this
    service when the target has one. None clears the pointer."""
    if raw in (None, ""):
        return None
    fmt = _format_or_404(raw)
    if fmt.status != FORMAT_PUBLISHED:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref=BR, message_key="metering.readFormats.not_published"
        )
    if service_code and fmt.service.code != service_code:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR,
            message_key="metering.readFormats.service_mismatch",
            params={"format_service": fmt.service.code, "service": service_code},
        )
    return fmt


def _pointer_value(data: dict[str, Any]) -> Any:
    _unknown_fields(data, {"read_format_id"})
    if "read_format_id" not in data:
        _refuse([_fe("read_format_id", errors.VAL_REQUIRED, "errors.val-001")])
    return data.get("read_format_id")


def defaults() -> dict[str, Any]:
    """`GET settings/read-formats/defaults` — one row per ENABLED service, its
    default format or none. Bounded by the eleven-service catalogue."""
    rows = {
        r.service.code: r
        for r in ReadFormatDefault.objects.filter(tenant_id=_tenant_id()).select_related(
            "service", "read_format"
        )
    }
    names = seams.service_names_by_code()
    out = []
    for code in seams.enabled_service_codes_ordered():
        row = rows.get(code)
        out.append(
            {
                "service": {"code": code, "name": names.get(code, code)},
                "read_format": (
                    {"id": str(row.read_format_id), "name": row.read_format.name}
                    if row is not None
                    else None
                ),
            }
        )
    return {"count": len(out), "results": out}


@require_role(SYSTEM_ADMIN)
def set_service_default(actor: Any, service_code: str, payload: Any) -> dict[str, Any]:
    """`PUT settings/read-formats/defaults/{service}` `{read_format_id | null}`."""
    raw = _pointer_value(_payload(payload))
    code = _text(service_code, 40)
    if code not in seams.enabled_service_codes():
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    fmt = _pointable(raw, service_code=code)
    tenant_id = _tenant_id()
    service_id = seams.service_id_by_code(code)
    with transaction.atomic():
        if fmt is None:
            ReadFormatDefault.objects.filter(tenant_id=tenant_id, service_id=service_id).delete()
        else:
            ReadFormatDefault.objects.update_or_create(
                tenant_id=tenant_id, service_id=service_id, defaults={"read_format": fmt}
            )
    _audit(actor, "read_format.default_set", "service", service_id, service=code,
           read_format=str(fmt.id) if fmt else None)
    return defaults()


def _cycle_or_404(cycle_id: Any) -> Any:
    row = (
        models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=cycle_id, deleted_at__isnull=True).first()
        if _is_uuid(cycle_id)
        else None
    )
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return row


def cycle_format(cycle_id: Any) -> dict[str, Any]:
    """`GET cycles/{id}/read-format` — the format the cycle itself names, or
    None (MQ-033 task 11: the cycle screen shows the pointer it edits). Not a
    resolution: a cycle has no service of its own, so what a reading uses is
    the ROUTE's answer (`route_resolution`)."""
    cycle = _cycle_or_404(cycle_id)
    fmt = (
        ReadFormat.objects.filter(tenant_id=cycle.tenant_id, pk=cycle.read_format_id).first()
        if cycle.read_format_id
        else None
    )
    return {"cycle_id": str(cycle.id), "read_format": _pointer_dict(fmt)}


@require_role(SYSTEM_ADMIN)
def set_cycle_format(actor: Any, cycle_id: Any, payload: Any) -> dict[str, Any]:
    """`PUT cycles/{id}/read-format` `{read_format_id | null}`. A cycle carries
    no service of its own, so any published format may be named; it applies
    to the cycle's routes OF THAT SERVICE (`resolve_read_format`)."""
    raw = _pointer_value(_payload(payload))
    cycle = _cycle_or_404(cycle_id)
    fmt = _pointable(raw, service_code=None)
    before = str(cycle.read_format_id) if cycle.read_format_id else None
    # `.update()`, not `.save()`: this lane writes ONE column of `cycles` and
    # nothing else (another lane is changing the cycle's Routes tab).
    models.Cycle.objects.filter(pk=cycle.pk).update(read_format=fmt, updated_at=timezone.now())
    _audit(actor, "read_format.cycle_set", "cycle", cycle.id, before=before,
           read_format=str(fmt.id) if fmt else None)
    return {"cycle_id": str(cycle.id), "read_format": _pointer_dict(fmt)}


@require_role(SYSTEM_ADMIN)
def set_route_formats(actor: Any, payload: Any) -> dict[str, Any]:
    """`PUT routes/read-format` `{route_ids: [...], read_format_id | null}` —
    one or many routes in one move. All or nothing: a route of another
    service, or an id this tenant does not hold, refuses the whole move."""
    data = _payload(payload)
    route_ids = data.get("route_ids")
    raw = _pointer_value({k: v for k, v in data.items() if k != "route_ids"})
    if not isinstance(route_ids, list) or not route_ids or not all(_is_uuid(r) for r in route_ids):
        _refuse([_fe("route_ids", errors.VAL_REQUIRED, "errors.val-001")])
    ids = sorted({str(r) for r in route_ids})
    routes = list(
        models.Route.objects.filter(tenant_id=_tenant_id(), pk__in=ids, deleted_at__isnull=True)
        .select_related("service")
    )
    if len(routes) != len(ids):
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    fmt = _pointable(raw, service_code=None)
    if fmt is not None:
        for route in routes:
            if route.service_id and route.service.code != fmt.service.code:
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref=BR,
                    message_key="metering.readFormats.service_mismatch",
                    params={"format_service": fmt.service.code, "service": route.service.code,
                            "route": route.code},
                )
    with transaction.atomic():
        # ONE column of `routes` (task 9 is changing `assigned_to` in parallel).
        models.Route.objects.filter(pk__in=ids).update(read_format=fmt, updated_at=timezone.now())
        for route in routes:
            _audit(actor, "read_format.route_set", "route", route.id,
                   before=str(route.read_format_id) if route.read_format_id else None,
                   read_format=str(fmt.id) if fmt else None)
    return {"route_ids": ids, "read_format": _pointer_dict(fmt), "updated": len(ids)}


def _pointer_dict(fmt: ReadFormat | None) -> dict[str, Any] | None:
    return None if fmt is None else {"id": str(fmt.id), "name": fmt.name}


# ══════════════════════════════════════════════════════════════════════════
# Resolution — THE one function (BR-MET-1212)
# ══════════════════════════════════════════════════════════════════════════
SOURCE_ROUTE = "route"
SOURCE_CYCLE = "cycle"
SOURCE_SERVICE = "service"


def resolve_with_source(route: Any, service_code: str | None = None) -> tuple[Any, str | None]:
    """`(published version, source)` for a reading on `route` of
    `service_code` (default: the route's own service), or `(None, None)`.

    *"route → cycle → service. A route can override its cycle, and a cycle
    its service."* Each level is used only when it names a PUBLISHED format
    of the reading's service; otherwise the next level is asked, and with
    none the reading is the plain reading it always was."""
    if route is None:
        return None, None
    service = service_code or (route.service.code if getattr(route, "service_id", None) else None)

    def usable(fmt_id: Any) -> Any:
        if not fmt_id:
            return None
        fmt = (
            ReadFormat.objects.filter(tenant_id=route.tenant_id, pk=fmt_id, status=FORMAT_PUBLISHED)
            .select_related("service", "current_version")
            .first()
        )
        if fmt is None or (service and fmt.service.code != service):
            return None
        return fmt.current_version

    version = usable(route.read_format_id)
    if version is not None:
        return version, SOURCE_ROUTE
    if route.cycle_id:
        cycle_format = (
            models.Cycle.objects.filter(pk=route.cycle_id).values_list("read_format_id", flat=True).first()
        )
        version = usable(cycle_format)
        if version is not None:
            return version, SOURCE_CYCLE
    if service:
        default = (
            ReadFormatDefault.objects.filter(tenant_id=route.tenant_id, service__code=service)
            .values_list("read_format_id", flat=True)
            .first()
        )
        version = usable(default)
        if version is not None:
            return version, SOURCE_SERVICE
    return None, None


def resolve_read_format(route: Any, service_code: str | None = None) -> Any:
    """THE resolution: route → cycle → service default → None. Returns the
    format's CURRENT published version (a `ReadFormatVersion`) or None."""
    return resolve_with_source(route, service_code)[0]


def route_resolution(route_id: Any) -> dict[str, Any]:
    """`GET routes/{id}/read-format` — what each of the route's services
    resolves to and from which level, for the Settings screens."""
    route = (
        models.Route.objects.filter(tenant_id=_tenant_id(), pk=route_id, deleted_at__isnull=True)
        .select_related("service")
        .first()
        if _is_uuid(route_id)
        else None
    )
    if route is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return {
        "route_id": str(route.id),
        "route_read_format_id": str(route.read_format_id) if route.read_format_id else None,
        "results": route_formats(route),
    }


def route_formats(route: Any, service_codes: list[str] | None = None) -> list[dict[str, Any]]:
    """One entry per service the route reads: `{service, source, read_format:
    {id, name, version_id, version_no} | None}`. What the handset caches by
    `version_id` (`field_routes`)."""
    from apps.metering import selectors

    codes = service_codes or selectors.route_service_codes(route.id) or (
        [route.service.code] if getattr(route, "service_id", None) else []
    )
    out = []
    for code in codes:
        version, source = resolve_with_source(route, code)
        out.append(
            {
                "service": code,
                "source": source,
                "read_format": (
                    {
                        "id": str(version.read_format_id),
                        "name": version.read_format.name,
                        "version_id": str(version.id),
                        "version_no": version.version_no,
                    }
                    if version is not None
                    else None
                ),
            }
        )
    return out


def versions_for_handset(version_ids: list[str]) -> list[dict[str, Any]]:
    """The published versions a route page names, each with its questions —
    deduplicated, so a route of one format carries it once."""
    out = []
    for version_id in dict.fromkeys(v for v in version_ids if v):
        out.append(get_version(version_id, published_only=True))
    return out


# ══════════════════════════════════════════════════════════════════════════
# Answers — on each reading item (BR-MET-1215 … 1217)
# ══════════════════════════════════════════════════════════════════════════
def _number(raw: Any) -> Decimal | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def _date(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _boolean(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
        return raw.strip().lower() == "true"
    return None


def _missing(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and not raw.strip()) or raw == []


def coerce_answer(question: ReadFormatQuestion, raw: Any, photo_id: Any = None) -> tuple[Any, str | None, Any, str | None]:
    """`(value, value_text, photo_id, issue)` — the answer as stored. `value`
    is what was SENT when the type does not fit (kept, flagged); `value_text`
    is the filterable form of a lawful answer."""
    kind = question.data_type
    if kind == PHOTO:
        candidate = photo_id if photo_id not in (None, "") else raw
        if _is_uuid(candidate):
            return str(candidate), str(candidate), str(candidate), None
        return raw, None, None, ISSUE_WRONG_TYPE
    if kind == "number":
        n = _number(raw)
        return (str(n), str(n.normalize()), None, None) if n is not None else (raw, None, None, ISSUE_WRONG_TYPE)
    if kind == "date":
        d = _date(raw)
        return (d.isoformat(), d.isoformat(), None, None) if d else (raw, None, None, ISSUE_WRONG_TYPE)
    if kind == "boolean":
        b = _boolean(raw)
        return (b, "true" if b else "false", None, None) if b is not None else (raw, None, None, ISSUE_WRONG_TYPE)
    if kind == "multi_select":
        if not isinstance(raw, list) or not all(isinstance(v, str) for v in raw):
            return raw, None, None, ISSUE_WRONG_TYPE
        if any(v not in (question.options or []) for v in raw):
            return raw, None, None, ISSUE_NOT_AN_OPTION
        # `|a|b|` so `answer[key]=a` matches one option of several.
        return raw, "|" + "|".join(raw) + "|", None, None
    if kind == "select":
        if not isinstance(raw, str):
            return raw, None, None, ISSUE_WRONG_TYPE
        if raw not in (question.options or []):
            return raw, None, None, ISSUE_NOT_AN_OPTION
        return raw, raw, None, None
    # text, and any custom-field type added later: kept as text.
    if isinstance(raw, (dict, list)):
        return raw, None, None, ISSUE_WRONG_TYPE
    text = str(raw)[:TEXT_ANSWER_MAX]
    return text, text, None, None


def answer_matches(question: ReadFormatQuestion | dict[str, Any], value: Any, expected: Any) -> bool:
    """Whether a lawful stored answer equals `expected` — `show_if.answer` or
    `raise_work.on_answer`. A list answer matches when it CONTAINS it."""
    kind = question["data_type"] if isinstance(question, dict) else question.data_type
    if value is None or expected is None:
        return False
    if kind == "multi_select":
        return isinstance(value, list) and expected in value
    if kind == "boolean":
        return _boolean(value) is not None and _boolean(value) == _boolean(expected)
    if kind == "number":
        a, b = _number(value), _number(expected)
        return a is not None and b is not None and a == b
    return str(value).strip().casefold() == str(expected).strip().casefold()


class AnswerContext:
    """What one sync request knows about each reading when its answers are
    judged: the reader's status, whether the ENGINE flagged it, its stop."""

    def __init__(self) -> None:
        self._versions: dict[str, ReadFormatVersion | None] = {}
        self._questions: dict[str, list[ReadFormatQuestion]] = {}
        #: (route, premises, day) → question keys answered at that stop in
        #: THIS request, for `once_per_stop`.
        self.stop_answers: dict[tuple[str, str, str], set[str]] = {}

    def version(self, version_id: Any) -> ReadFormatVersion | None:
        key = str(version_id or "")
        if key not in self._versions:
            self._versions[key] = (
                ReadFormatVersion.objects.filter(
                    tenant_id=_tenant_id(), pk=key, state=VERSION_PUBLISHED
                ).first()
                if _is_uuid(key)
                else None
            )
        return self._versions[key]

    def questions(self, version: ReadFormatVersion) -> list[ReadFormatQuestion]:
        key = str(version.id)
        if key not in self._questions:
            self._questions[key] = _questions(version)
        return self._questions[key]


def _stop_key(field_read: Any, tz: Any) -> tuple[str, str, str] | None:
    if not field_read.premises_id:
        return None
    when = field_read.device_captured_at or field_read.received_at or timezone.now()
    day = when.astimezone(tz).date().isoformat() if tz else when.date().isoformat()
    return (str(field_read.route_id or ""), str(field_read.premises_id), day)


def _parse_answers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:ANSWERS_PER_ITEM_MAX]:
        if isinstance(item, dict) and _text(item.get("question_key")):
            out.append(item)
    return out


def item_answers(item: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """`(version id, answers)` as the handset sent them on one reading item.
    Payload: `"read_format_version_id": "<uuid>"`, `"answers": [{"question_key",
    "value" | "photo_id"}]`."""
    return item.get("read_format_version_id"), _parse_answers(item.get("answers"))


def plan_stop_answers(ctx: AnswerContext, pending: list[tuple[Any, dict[str, Any]]], tz: Any) -> None:
    """Pass 1 over the request: which `once_per_stop` keys were answered at
    which stop, so a second reading at the same stop is not flagged missing."""
    for field_read, item in pending:
        stop = _stop_key(field_read, tz)
        if stop is None:
            continue
        _version_id, answers = item_answers(item)
        keys = {str(a.get("question_key")) for a in answers if not _missing(a.get("value")) or a.get("photo_id")}
        ctx.stop_answers.setdefault(stop, set()).update(keys)


def _answered_at_stop_before(field_read: Any, key: str, stop: tuple[str, str, str]) -> bool:
    """`once_per_stop`: an EARLIER request already answered it at this stop
    on this route on this day."""
    route_id, premises_id, day = stop
    return ReadAnswer.objects.filter(
        tenant_id=_tenant_id(),
        question_key=key,
        issue__isnull=True,
        field_read__premises_id=premises_id,
        field_read__route_id=route_id or None,
        field_read__device_captured_at__date=day,
    ).exclude(field_read_id=field_read.id).exists()


def record_answers(
    actor: Any,
    ctx: AnswerContext,
    field_read: Any,
    item: dict[str, Any],
    *,
    engine_flagged: bool,
    tz: Any = None,
) -> dict[str, Any] | None:
    """Judge and STORE one reading's answers against the version it names;
    raise any job its answers call for. Returns the receipt's `answers`
    block, or None when the item carried no format at all.

    ⚠ **NEVER DROPS, NEVER REFUSES** (BR-MET-1216, PO *"never cause a reading
    to be dropped (stored and flagged instead)"*): every answer sent is a row,
    a bad one with its `issue`; a missing required one is a row with
    `required_missing`; the reading itself was judged before this ran and
    nothing here can change that judgment. Called inside the item's own
    SAVEPOINT by `field_reads` (law 14)."""
    version_id, answers = item_answers(item)
    if not version_id and not answers:
        return None
    version = ctx.version(version_id) if version_id else None
    tenant_id = field_read.tenant_id
    rows: list[ReadAnswer] = []
    if version is None:
        for a in answers:
            rows.append(
                ReadAnswer(
                    tenant_id=tenant_id, field_read=field_read, version=None,
                    question_key=str(a["question_key"])[:120],
                    value=a.get("value") if a.get("value") is not None else a.get("photo_id"),
                    issue=ISSUE_VERSION_UNKNOWN,
                )
            )
        _store(rows)
        field_read.answers_need_review = True
        field_read.save(update_fields=["answers_need_review", "updated_at"])
        return _receipt_block(None, rows, [])

    field_read.read_format_version = version
    questions = ctx.questions(version)
    by_key = {q.key: q for q in questions}
    sent: dict[str, dict[str, Any]] = {}
    for a in answers:
        sent.setdefault(str(a["question_key"]), a)  # first answer per key wins
    stop = _stop_key(field_read, tz)
    reader_status = field_read.reader_status
    took_figure = reader_status in ("read", "read_with_problem")
    lawful: dict[str, Any] = {}

    for q in questions:  # in seq order, so a follow-up's parent is judged first
        a = sent.get(q.key)
        shown = True
        if q.show_if:
            parent = by_key.get(q.show_if.get("question_key"))
            shown = parent is not None and answer_matches(
                parent, lawful.get(parent.key), q.show_if.get("answer")
            )
        if q.asked_when == ASKED_EVERY_READING:
            asked = took_figure
        elif q.asked_when == ASKED_OUT_OF_RANGE:
            asked = took_figure and engine_flagged
        elif q.asked_when == ASKED_CANT_READ:
            asked = reader_status == "could_not_read"
        else:  # once per stop — offered at every reading of the stop
            asked = True
        if a is None or (_missing(a.get("value")) and not a.get("photo_id")):
            if q.is_required and shown and asked:
                if q.asked_when == ASKED_ONCE_PER_STOP and stop is not None and (
                    q.key in ctx.stop_answers.get(stop, set())
                    or _answered_at_stop_before(field_read, q.key, stop)
                ):
                    continue
                rows.append(
                    ReadAnswer(tenant_id=tenant_id, field_read=field_read, version=version,
                               question_key=q.key, value=None, issue=ISSUE_REQUIRED_MISSING)
                )
            continue
        value, value_text, photo_id, issue = coerce_answer(q, a.get("value"), a.get("photo_id"))
        if not shown:
            issue = ISSUE_NOT_SHOWN
        elif not asked:
            issue = ISSUE_NOT_ASKED
        if issue is None:
            lawful[q.key] = value
        rows.append(
            ReadAnswer(tenant_id=tenant_id, field_read=field_read, version=version,
                       question_key=q.key, value=value, value_text=value_text if issue is None else None,
                       photo_id=photo_id if issue is None else None, issue=issue)
        )
    for key, a in sent.items():
        if key not in by_key:
            rows.append(
                ReadAnswer(tenant_id=tenant_id, field_read=field_read, version=version,
                           question_key=key[:120],
                           value=a.get("value") if a.get("value") is not None else a.get("photo_id"),
                           issue=ISSUE_UNKNOWN_QUESTION)
            )
    _store(rows)
    field_read.answers_need_review = any(r.issue for r in rows)
    field_read.save(update_fields=["read_format_version", "answers_need_review", "updated_at"])
    raised = _raise_work(actor, field_read, version, by_key, rows)
    return _receipt_block(version, rows, raised)


def _store(rows: list[ReadAnswer]) -> None:
    if rows:
        ReadAnswer.objects.bulk_create(rows)


def _raise_work(
    actor: Any,
    field_read: Any,
    version: ReadFormatVersion,
    by_key: dict[str, ReadFormatQuestion],
    rows: list[ReadAnswer],
) -> list[dict[str, Any]]:
    """BR-MET-1217 — each LAWFUL answer that matches its question's
    `raise_work.on_answer` hands ONE job to Work, idempotent on reading +
    question (`read-answer:<reading key>:<question key>`). Each raise in its
    own SAVEPOINT (law 14): a raise Work refuses is recorded on the answer and
    loses nothing else."""
    from apps.metering.field_read_models import OUTCOME_POSTED, OUTCOME_RECORDED

    out: list[dict[str, Any]] = []
    if field_read.outcome not in (OUTCOME_POSTED, OUTCOME_RECORDED):
        return out
    for row in rows:
        q = by_key.get(row.question_key)
        if row.issue or q is None or not q.raise_work:
            continue
        if not answer_matches(q, row.value, q.raise_work.get("on_answer")):
            continue
        key = f"read-answer:{field_read.key}:{q.key}"
        detail = {
            "read_format": str(version.read_format_id),
            "read_format_version": str(version.id),
            "version_no": version.version_no,
            "question_key": q.key,
            "question": q.label,
            "answer": row.value,
            "field_read_key": field_read.key,
            "meter_read_id": str(field_read.meter_read_id) if field_read.meter_read_id else None,
        }
        try:
            with transaction.atomic():
                finding, _duplicate = seams.work_raise_for_read_answer(
                    actor,
                    key=key,
                    template_id=q.raise_work.get("template_id"),
                    route_id=field_read.route_id,
                    premises_id=field_read.premises_id,
                    asset_id=field_read.asset_id,
                    captor_id=field_read.reader_id,
                    captured_at=field_read.device_captured_at,
                    lat=field_read.lat,
                    lng=field_read.lng,
                    accuracy_m=field_read.accuracy_m,
                    detail=detail,
                )
        except Exception as exc:  # noqa: BLE001 — the answer and reading stay
            ReadAnswer.objects.filter(pk=row.pk).update(
                work_finding_key=key, work_raise_error=type(exc).__name__[:120]
            )
            out.append({"question_key": q.key, "work_order": None, "error": type(exc).__name__})
            continue
        order = finding.get("work_order") or None
        ReadAnswer.objects.filter(pk=row.pk).update(
            work_finding_key=key,
            work_order_id=(order or {}).get("id"),
            work_order_no=(order or {}).get("order_no"),
        )
        out.append(
            {"question_key": q.key, "finding_status": finding.get("status"), "work_order": order}
        )
    return out


def _receipt_block(
    version: ReadFormatVersion | None, rows: list[ReadAnswer], raised: list[dict[str, Any]]
) -> dict[str, Any]:
    issues = [{"question_key": r.question_key, "issue": r.issue} for r in rows if r.issue]
    return {
        "version_id": str(version.id) if version is not None else None,
        "stored": sum(1 for r in rows if r.issue != ISSUE_REQUIRED_MISSING),
        "needs_review": bool(issues),
        "issues": issues,
        "work": raised,
    }


# ══════════════════════════════════════════════════════════════════════════
# The office: answers on a reading, and the Reads list filter (BR-MET-1218)
# ══════════════════════════════════════════════════════════════════════════
def answers_for_meter_read(meter_read_id: Any) -> dict[str, Any] | None:
    """The answers given with the field reading that became this read, with
    each question's words AS THEY WERE in the stamped version. None when the
    read did not come from a field reading carrying a format."""
    field_read = (
        _field_read_model()
        .objects.filter(tenant_id=_tenant_id(), meter_read_id=meter_read_id)
        .select_related("read_format_version", "read_format_version__read_format")
        .order_by("received_at")
        .first()
    )
    if field_read is None:
        return None
    answers = list(
        ReadAnswer.objects.filter(tenant_id=field_read.tenant_id, field_read=field_read).order_by(
            "created_at", "question_key"
        )
    )
    if not answers and field_read.read_format_version_id is None:
        return None
    version = field_read.read_format_version
    questions = {q.key: q for q in _questions(version)} if version is not None else {}
    order = {key: i for i, key in enumerate(questions)}
    answers.sort(key=lambda r: (order.get(r.question_key, 10**6), r.question_key))
    return {
        "read_format": (
            {
                "id": str(version.read_format_id),
                "name": version.read_format.name,
                "version_id": str(version.id),
                "version_no": version.version_no,
            }
            if version is not None
            else None
        ),
        "needs_review": field_read.answers_need_review,
        "answers": [
            {
                "question_key": r.question_key,
                "label": questions[r.question_key].label if r.question_key in questions else None,
                "data_type": (
                    questions[r.question_key].data_type if r.question_key in questions else None
                ),
                "value": r.value,
                "photo_id": str(r.photo_id) if r.photo_id else None,
                "issue": r.issue,
                "work_order": (
                    {"id": str(r.work_order_id), "order_no": r.work_order_no}
                    if r.work_order_id
                    else None
                ),
            }
            for r in answers
        ],
    }


def _field_read_model() -> Any:
    from apps.metering.field_read_models import FieldRead

    return FieldRead


def answer_filters(query_params: Any) -> dict[str, str]:
    """`answer[<question_key>]=<value>` pairs from a reads-list URL. Unknown
    shapes are ignored, never an error (BR-SHL-011)."""
    out: dict[str, str] = {}
    for name in getattr(query_params, "keys", lambda: [])():
        if name.startswith("answer[") and name.endswith("]") and len(name) > 8:
            key = name[7:-1].strip()
            value = query_params.get(name)
            if key and value not in (None, ""):
                out[key] = str(value)
    return out


def meter_read_ids_answering(filters: dict[str, str]) -> Any:
    """A SUBQUERY of meter-read ids whose field reading answered every
    `key=value` given (AND). A lawful answer only: a flagged one is not what
    the question asked. Handed to the reads list as `id__in` (NFR-3: the
    database filters, nothing is listed)."""
    FieldRead = _field_read_model()
    qs = FieldRead.objects.filter(tenant_id=_tenant_id(), meter_read_id__isnull=False)
    for key, value in filters.items():
        matching = ReadAnswer.objects.filter(
            tenant_id=_tenant_id(), question_key=key, issue__isnull=True
        ).filter(
            Q(value_text=value)
            | Q(value_text__iexact=value)
            | Q(value_text__contains=f"|{value}|")
        )
        qs = qs.filter(id__in=matching.values("field_read_id"))
    return qs.values("meter_read_id")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-192-BRC10 (MQ-033 task 10 — read formats server; decision log 2026-10-24 ×3)
# generated: 2026-10-24 by lane MQ033-SERVER
# checklist: A✔ B✔ C✔ D✔ E=deferred(task 11 Settings screens · task 12 phone · task 13 Reads list columns + export) F✔ G✔ H=deferred(no 🔒 path in this file; metering/0080 and work/0050 are)
# gates: see the lane report
# exceptions: the seven judgments in the module docstring · export columns are task 13's
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
