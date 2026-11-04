# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-013 (header columns and one relaxed key) · US-WRK-014 (the
#           seven child collections as ROWS) · US-WRK-015 (the write service
#           the seeder says is OWED) · US-WRK-018 (versions, and what v2
#           means).  Screens: Work-013, Work-022
# Rules:    BR-WRK-008 (copy, never link) · BR-WRK-009 (rows, not a blob) ·
#           BR-WRK-010 (more than one template per service) · BR-WRK-011
#           (Publish is the ONE write) · BR-WRK-012 (versioned; delete refused
#           while referenced; deactivate instead; PATCH never toggles active)
#           · BR-WRK-015 (a reading's unit is a column) · BR-TEN-035 (the
#           `ST-{0000}` series) · BR-WRK-002 (the header goes through the
#           seam) · CLAUDE.md hard rule 1 (tenant scope) · 3 (a quantity
#           carries its unit) · 7 (every write writes audit_log)
# Tests:    06-backend/tests/test_us_wrk_013_018_templates.py (29 cases, every
#           TC in its own test name) · 06-backend/tests/test_us_wrk_rls_pg.py
#           (all FOURTEEN Work tables' policies, on real PostgreSQL)
# Impacts:  apps/work/api.py (nine routes) · apps/work/selectors.py (the
#           reads) · apps/metering/connections.py (the header writer) ·
#           apps/work/seams/metering_seam.py (the doors)
# ───────────────────────────────────────────────────────
"""The template bundle's write side — **one service, seven collections, ONE
write that reaches an order.**

WHAT THIS FILE IS FOR, IN ONE SENTENCE
--------------------------------------
`apps/metering/sample_data.py` has recorded a debt in its own words since
2026-08-25 — *"a `create_work_order_template` service is OWED"* — and wrote its
24 starter rows straight through the model because nothing existed to write
them through. This is that service, plus the six collections a template needs
to be worth authoring.

THE BOUNDARY, AND WHY IT RUNS THROUGH THE MIDDLE OF ONE TEMPLATE
----------------------------------------------------------------
A template is TWO things in this tree today:

  * its **header row** — `work_order_templates`, which is METERING's table
    (`03-field-map.md` §4, PENDING the blueprint's §16, a section this repo has
    never been able to read); and
  * its **bundle** — `wot_details`, `wot_safety`, `wot_tasks`, `wot_materials`,
    `wot_readings`, `wot_help`, `wot_asset_types` and
    `work_order_template_versions`, which are WORK's, created by `work/0003`.

So this file writes the second half directly and the first half through
`apps/work/seams/metering_seam.py`, which calls metering's own service by name.
That is the door `BR-WRK-002` sanctions and `G78` enforces, and it is the same
shape `raise_work_order` already uses. **The day the table moves, the seam
changes and nothing here does.**

⚠ **PUBLISH IS THE ONE WRITE, AND IT IS ALSO THE ONE PLACE THE TWO HALVES MEET**
(`BR-WRK-011`). `publish` opens one transaction, asks metering to set the
version and allocate `ST-{0000}`, and writes the `work_order_template_versions`
row itself. Neither module writes the other's table; both commit or neither
does.

⚠ **PUBLISHING TWICE IN A SECOND MAKES ONE VERSION.** Not by a lock and not by
an idempotency key: by asking whether anything has CHANGED. `_bundle_touched_at`
is the newest `updated_at` across the header and all seven collections; if it
is not newer than the current version's `published_at`, publish returns the
version that already exists and writes nothing. A second version identical to
the first is not a version — it is a number a supervisor now has to explain on
`Work-022`.

⚠ **WHAT IS NOT HERE.** No order is touched. `BR-WRK-008` — *copy, never link*
— means an order took its own copies when it was raised, so editing or
publishing a template changes nothing already raised, and there is nothing in
this file that could. The copies themselves are `EP-WRK-06`'s (wave H).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.work import models
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

#: The seven collections, and the model behind each. `details` is the odd one
#: out — it is ONE row per template rather than a list — so it is named here
#: and handled by its own branch rather than pretended into the same shape.
COLLECTIONS: dict[str, Any] = {
    "safety": models.WorkOrderTemplateSafety,
    "tasks": models.WorkOrderTemplateTask,
    "materials": models.WorkOrderTemplateMaterial,
    "readings": models.WorkOrderTemplateReading,
    "help": models.WorkOrderTemplateHelp,
    "asset-types": models.WorkOrderTemplateAssetType,
}

#: The one-row collection, kept out of `COLLECTIONS` on purpose (see above).
DETAILS = "details"

#: Every name `PUT /work/templates/{id}/{collection}` answers to.
COLLECTION_NAMES: tuple[str, ...] = (DETAILS, *COLLECTIONS)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _audit(actor: Any, action: str, entity_id: Any, **rows: Any) -> None:
    """CLAUDE.md hard rule 7 — every write writes `audit_log`."""
    core_audit.write_row(
        action=action,
        entity_type="work_order_template",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        **rows,
    )


def _header_or_404(template_id: Any) -> dict[str, Any]:
    """The header through the seam, or a 404 identical to an absent row."""
    row = metering_seam.template(template_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _refuse(code: str, message_key: str, *, br_ref: str | None = None, **params: Any) -> None:
    """One refusal shape, so every sentence a clerk reads comes from a
    catalogue key rather than from a string built at the call site.

    ⚠ **THE SECOND PARAMETER IS NAMED `message_key` ON PURPOSE.** `G32` reads
    every module with `ast` and follows a local helper only when one of its
    positional arguments is called exactly that (its own docstring records
    `DEF-643`: 341 keys reach a user through helpers, and 60 of them resolved
    to nothing while the gate reported PASS over all of them). Calling this
    parameter `key` would hide every refusal in this file from the one gate
    that checks them — a guard defeated by a variable name.

    ⚠ **AND EVERY KEY PASSED IN IS ONE THAT ALREADY RESOLVES.** The wave D lane
    could not write to `07-frontend/src/i18n/locales/*.json`, and a key that
    resolves to nothing renders as its own raw dotted name on a clerk's screen
    (`DEF-322`). So these reuse existing sentences that are TRUE of these
    refusals. The looser ones are filed for the commit that lands the
    purpose-written `work.template.*` keys.
    """
    if code in errors.BIZ_CODES:
        raise errors.BizError(
            code, br_ref=br_ref or "BR-WRK-009", message_key=message_key, params=params or None
        )
    raise errors.ValidationError(
        code, message_key=message_key, params=params or None, br_ref=br_ref
    )


# ── the collections ─────────────────────────────────────────────────────────


def _int(value: Any, field: str, *, minimum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        _refuse(errors.VAL_FORMAT, "settings.param_not_integer", field=field)
    if minimum is not None and number < minimum:
        _refuse(errors.VAL_RANGE, "settings.param_not_integer", field=field)
    return number


def _decimal(value: Any, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        _refuse(errors.VAL_FORMAT, "settings.param_not_integer", field=field)
    return None


def _text(row: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = str(row.get(key) or "").strip()
    if required and not value:
        _refuse(errors.VAL_REQUIRED, "work.lookups.required", field=key)
    return value


def _safety_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    return {
        "seq": seq,
        "text": _text(row, "text"),
        "is_mandatory": bool(row.get("is_mandatory", True)),
    }


def _task_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    # ⚠ `est_minutes = 0` with `is_mandatory = true` IS LAWFUL and
    # `US-WRK-014` TC-4 guards it: a mandatory zero-minute check is a real
    # thing, and a validator that read *no estimate* as *invalid* would refuse
    # it. The floor is 0, not 1.
    return {
        "seq": seq,
        "title": _text(row, "title"),
        "est_minutes": _int(row.get("est_minutes", 0), "est_minutes", minimum=0),
        "photo_required": bool(row.get("photo_required", False)),
        "is_mandatory": bool(row.get("is_mandatory", False)),
        # PO answer (3) of 2026-10-04: *"(a) Add an instruction text box to each
        # task, shown on the technician's phone."* Optional; blank is NULL so
        # *no instruction* is one value, not two.
        "instruction": str(row.get("instruction") or "").strip() or None,
        # CR-187-BRC10 T-35 · R18 — freshness is DATA on the step, like the
        # photo rule. See `_money_fresh_minutes`.
        "money_fresh_minutes": _money_fresh_minutes(row),
        # R111 — the tenant's own charge code this step asks about (FF-61's
        # fee). Blank is NULL: *no charge question* is one value, not two.
        "money_charge_code": str(row.get("money_charge_code") or "").strip() or None,
    }


def _money_fresh_minutes(row: dict[str, Any]) -> int | None:
    """`money_fresh_minutes` from a task row — NULL, or a bar of 1 minute or more.

    `needs_fresh_money: true` with no bar takes R17's five minutes
    (`money.MONEY_FRESH_DEFAULT_MINUTES`); a bar given alone implies the check;
    neither is NULL — the step reads no money. A bar of 0 is refused: *no older
    than zero minutes* is a figure nobody can ever hold, and it would turn every
    proceed on the step into *unverified*.
    """
    from apps.work import money

    minutes = row.get("money_fresh_minutes")
    if minutes not in (None, ""):
        return _int(minutes, "money_fresh_minutes", minimum=1)
    if row.get("needs_fresh_money"):
        return money.MONEY_FRESH_DEFAULT_MINUTES
    return None


def _material_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    part_id = row.get("part_id")
    part = models.Part.objects.filter(tenant_id=_tenant_id(), pk=part_id).first() if part_id else None
    if part is None:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "assets.lookups.bad_choice", field="part_id")
    qty = _decimal(row.get("planned_qty", 1), "planned_qty")
    if qty is None or qty <= 0:
        _refuse(errors.VAL_RANGE, "assets.must_be_positive", field="planned_qty")
    return {
        "part": part,
        "planned_qty": qty,
        # hard rule 3 — the unit travels with the quantity, taken from the part
        # rather than typed again, so a template and its register cannot
        # disagree about what "2" means.
        "unit_of_measure": str(row.get("unit_of_measure") or part.unit_of_measure),
    }


def _reading_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    # ⚠ **THE UNIT IS A COLUMN AND IT IS REQUIRED** — `BR-WRK-015` and hard
    # rule 3. `US-WRK-014` TC-3 refuses *Final read (kWh)* with no unit by
    # name: a unit hidden inside a prompt cannot be validated, converted or
    # compared, and the reading posts to `meter_reads` on approval.
    #
    # ⚠ **EXCEPT FOR A READING THAT IS WORDS** (`CR-168-BRC10` P1.33, judgment
    # J8). `kind: "text"` — a seal number, a serial, *W-5000-N* — has no unit and
    # no range because it is not a quantity, and it can NEVER post as a meter
    # read (hard rule 3: a meter read is a number with its unit). Asking for
    # both is refused by name rather than silently cleared, and the database
    # refuses it too (`ck_wot_readings_text_never_posts`, `work/0028`).
    kind = str(row.get("kind") or models.READING_KIND_NUMBER).strip()
    if kind not in models.READING_KINDS:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "assets.lookups.bad_choice", field="kind")
    posts = bool(row.get("posts_as_meter_read", False))
    if kind == models.READING_KIND_TEXT:
        if posts:
            _refuse(
                errors.VAL_RANGE, "work.template.text_reading_cannot_post",
                field="posts_as_meter_read",
            )
        return {
            "seq": seq,
            "prompt": _text(row, "prompt"),
            "unit_of_measure": "",
            "min_value": None,
            "max_value": None,
            "required": bool(row.get("required", True)),
            "photo_required": bool(row.get("photo_required", False)),
            "posts_as_meter_read": False,
            "kind": kind,
        }
    unit = _text(row, "unit_of_measure")
    low = _decimal(row.get("min"), "min")
    high = _decimal(row.get("max"), "max")
    if low is not None and high is not None and low > high:
        _refuse(errors.VAL_RANGE, "ledger.report.range_inverted", field="min")
    return {
        "seq": seq,
        "prompt": _text(row, "prompt"),
        "unit_of_measure": unit,
        "min_value": low,
        "max_value": high,
        "required": bool(row.get("required", True)),
        "photo_required": bool(row.get("photo_required", False)),
        "posts_as_meter_read": posts,
        "kind": kind,
    }


def _help_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    kind = _text(row, "kind")
    if kind not in models.HELP_KINDS:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "assets.lookups.bad_choice", field="kind")
    ref = (str(row.get("ref")).strip() or None) if row.get("ref") else None
    if kind == models.HELP_KIND_LINK:
        # Ruling 6 (24 Sep) — a video or web LINK. The address travels as `link`
        # (or `ref`) and is stored in `ref`. ⚠ `https` ONLY: the phone opens it
        # in a browser, and a `javascript:` or plain-http address on a job a
        # technician taps is not a help page (P3.25).
        ref = str(row.get("link") or ref or "").strip() or None
        if not ref:
            _refuse(errors.VAL_REQUIRED, "work.lookups.required", field="link")
        from urllib.parse import urlparse

        parsed = urlparse(ref)
        if parsed.scheme != "https" or not parsed.netloc:
            _refuse(errors.VAL_FORMAT, "work.template.help_link_https", field="link")
    return {
        "seq": seq,
        "kind": kind,
        "label": _text(row, "label"),
        "ref": ref,
    }


def _asset_type_row(row: dict[str, Any], seq: int) -> dict[str, Any]:
    asset_type_id = row.get("asset_type_id")
    if not asset_type_id:
        _refuse(errors.VAL_REQUIRED, "work.lookups.required", field="asset_type_id")
    return {"asset_type_id": asset_type_id}


_ROW_BUILDERS = {
    "safety": _safety_row,
    "tasks": _task_row,
    "materials": _material_row,
    "readings": _reading_row,
    "help": _help_row,
    "asset-types": _asset_type_row,
}


def replace_collection(
    actor: Any, template_id: Any, collection: str, rows: Any
) -> dict[str, Any]:
    """**ONE ROUTE, SEVEN COLLECTIONS** — `PUT /work/templates/{id}/{name}`.

    Replace-in-full rather than row-by-row CRUD, and that is the whole reason
    the drag handle on `Work-015` can work: reordering six tasks is one call
    with the new order in it, not six PATCHes with a moment in between where
    two rows claim `seq = 3` and the unique key refuses.

    Seven near-identical routes would be seven places to forget the tenant
    scope, the audit row or the sequence rewrite. There is one.

    ⚠ **NOTHING HERE REACHES AN ORDER.** This is draft content until Publish
    (`BR-WRK-011`), whatever the template's current version is.
    """
    if collection not in COLLECTION_NAMES:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            "assets.lookups.bad_choice",
            field="collection",
            collection=collection,
        )
    header = _header_or_404(template_id)
    tenant_id = _tenant_id()
    if collection == DETAILS:
        return _replace_details(actor, header, rows)
    model = COLLECTIONS[collection]
    builder = _ROW_BUILDERS[collection]
    incoming = list(rows or [])
    if not isinstance(incoming, list):
        _refuse(errors.VAL_FORMAT, "metering.payload_not_object", field=collection)
    prepared = [
        builder(row if isinstance(row, dict) else {}, seq)
        for seq, row in enumerate(incoming, start=1)
    ]
    with transaction.atomic():
        # ⚠ DELETE-THEN-INSERT INSIDE ONE TRANSACTION, never an update-in-place
        # merge. `seq` is uniquely constrained per template, so a merge would
        # have to compute a collision-free order of moves; a replace has no
        # intermediate state to collide in. On PostgreSQL the unique index is
        # checked per statement, so the deletes land before any insert.
        model.objects.filter(tenant_id=tenant_id, template_id=header["id"]).delete()
        model.objects.bulk_create(
            [model(tenant_id=tenant_id, template_id=header["id"], **row) for row in prepared]
        )
        _touch_header(header["id"])
        _audit(
            actor,
            f"work_order_template.{collection.replace('-', '_')}_replaced",
            header["id"],
            after={"collection": collection, "rows": len(prepared)},
        )
        # FB-031 — help changed: the open, not-started jobs get it too.
        refreshed = refresh_open_job_help(actor, header["id"]) if collection == "help" else 0
    out: dict[str, Any] = {"collection": collection, "count": len(prepared)}
    if collection == "help":
        out["jobs_refreshed"] = refreshed
    return out


def _replace_details(actor: Any, header: dict[str, Any], rows: Any) -> dict[str, Any]:
    """`wot_details` — one row per template. A dict, not a list.

    SEVEN booleans since wave E: the four of step 1 (*what the technician sees
    on the job*) and the three of step 7 (*what they have to bring back*). The
    step-7 three arrived with `work/0005`; see the model's own docstring for
    why they live here rather than on a table of their own.

    ⚠ **EVERY DEFAULT IS `True`, INCLUDING THE THREE NEW ONES** (hard-won law
    3: the unsafe option is the one you type). A template that says nothing
    about signatures asks for one, records why it was refused and leaves a
    card.
    """
    data = rows if isinstance(rows, dict) else {}
    fields = {
        "show_account_summary": bool(data.get("show_account_summary", True)),
        "show_asset_card": bool(data.get("show_asset_card", True)),
        "show_access_notes": bool(data.get("show_access_notes", True)),
        "show_appointment": bool(data.get("show_appointment", True)),
        # FB-023 F4 — the fifth tick; absent resets to shown like the four.
        "show_balance_payments": bool(data.get("show_balance_payments", True)),
        "signature_required": bool(data.get("signature_required", True)),
        "refusal_reason_required": bool(data.get("refusal_reason_required", True)),
        "door_hanger_on_no_answer": bool(data.get("door_hanger_on_no_answer", True)),
    }
    # ── DEF-WRK-10652 (PO 2026-10-29, rulings 3B and 4A) ────────────────────
    # ⚠ **AN ABSENT KEY IS *UNCHANGED*, NEVER *RESET*.** The seven ticks above
    # reset to their default when a save leaves them out; these two are KEPT,
    # because a caller written before they existed (the seeder, an older
    # screen) would otherwise wipe a utility's preparation text and switch its
    # disconnect templates back ON — the money-check fields' bug, an editor
    # dropping what it did not send. Present-and-blank clears the text.
    current = models.WorkOrderTemplateDetail.objects.filter(
        tenant_id=_tenant_id(), template_id=header["id"]
    ).first()
    if "prep_instructions" in data:
        fields["prep_instructions"] = _prep_text(data.get("prep_instructions"))
    elif current is not None:
        fields["prep_instructions"] = current.prep_instructions
    if "send_customer_visit_messages" in data:
        flag = data.get("send_customer_visit_messages")
        if not isinstance(flag, bool):
            _refuse(errors.VAL_FORMAT, "work.template.visit_messages_not_boolean",
                    field="send_customer_visit_messages")
        fields["send_customer_visit_messages"] = flag
    elif current is not None:
        fields["send_customer_visit_messages"] = current.send_customer_visit_messages
    # FB-028 (PO 2026-10-31) — the Reconnect limit. Absent is UNCHANGED, like
    # the two above: a caller written before it existed must not wipe it.
    if "reconnect_limit" in data:
        fields["reconnect_limit"] = _reconnect_limit(data.get("reconnect_limit"))
    elif current is not None:
        fields["reconnect_limit"] = current.reconnect_limit
    with transaction.atomic():
        models.WorkOrderTemplateDetail.objects.update_or_create(
            tenant_id=_tenant_id(), template_id=header["id"], defaults=fields
        )
        _touch_header(header["id"])
        _audit(
            actor,
            "work_order_template.details_replaced",
            header["id"],
            after={k: (str(v) if k == "reconnect_limit" and v is not None else v) for k, v in fields.items()},
        )
    return {"collection": DETAILS, "count": 1}


def _reconnect_limit(value: Any) -> Any:
    """FB-028 — the template's Reconnect limit: a money amount, stored to 4
    places (hard rule 2), never negative; blank is NULL (no limit). Decimal,
    never float: `"25"`, `"25.00"` and `25` all store `25.0000`."""
    from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, (bool, float)):
        _refuse(errors.VAL_FORMAT, "work.template.reconnect_limit_not_money", field="reconnect_limit")
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        _refuse(errors.VAL_FORMAT, "work.template.reconnect_limit_not_money", field="reconnect_limit")
    if not amount.is_finite() or amount < 0:
        _refuse(errors.VAL_RANGE, "work.template.reconnect_limit_not_money", field="reconnect_limit")
    return amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


#: The longest preparation text a template may carry — it rides an email and
#: (in its own paragraph) a text message, so it is a sentence or two.
PREP_MAX_CHARS = 300


def _prep_text(value: Any) -> str | None:
    """`prep_instructions` — trimmed; blank is NULL (*use the utility's
    default*), so *no text* is one value, not two."""
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > PREP_MAX_CHARS:
        _refuse(errors.VAL_RANGE, "work.template.prep_too_long",
                field="prep_instructions", max=PREP_MAX_CHARS)
    return text


def _touch_header(template_id: Any) -> None:
    """Move the header's `updated_at`, so `publish` can tell a real second
    version from a double click.

    ⚠ **AND IT IS NOT REDUNDANT WITH THE CHILD ROWS' OWN `auto_now`.** A
    collection can be EMPTIED — three tasks replaced by none — and then there
    is no child row left to carry a timestamp, so a bundle that genuinely
    changed would look untouched and `publish` would refuse to make v2. The
    header is the one row that is always there.

    It goes through metering's own door and writes NO audit row of its own:
    the meaningful entry is the collection replace's, which names the
    collection and the row count. A second row saying *"the header's timestamp
    moved"* would be noise in the trail a supervisor reads.
    """
    metering_seam.touch_template(template_id)


def _bundle_touched_at(template_id: Any, header: dict[str, Any]) -> Any:
    """The newest `updated_at` across the header and all eight Work tables."""
    newest = header.get("updated_at")
    for model in (*COLLECTIONS.values(), models.WorkOrderTemplateDetail):
        row = (
            model.objects.filter(tenant_id=_tenant_id(), template_id=template_id)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        if row is not None and (newest is None or row > newest):
            newest = row
    return newest


# ── the header, through the door ────────────────────────────────────────────


def _minutes_to_duration(payload: Any) -> Any:
    """Accept `est_duration_minutes` on the wire and hand metering a duration.

    ⚠ **THE READ SIDE HAS PUBLISHED MINUTES SINCE WAVE D AND THE WRITE SIDE
    TOOK AN INTERVAL, WHICH IS TWO VOCABULARIES FOR ONE FACT.**
    `selectors._template_list_row` answers `est_duration_minutes` because
    `Work-013`'s EST. column reads *45 min*; `work_order_templates.
    est_duration` is a `DurationField` because an interval carries its own unit
    (hard rule 3). A screen that read minutes and had to post an ISO duration
    would be doing a conversion in a browser, which is where conversions go
    wrong. So the conversion happens once, here, in Work's own service.

    `est_duration` itself is still accepted untouched, for a caller that has
    one — the seeder does.
    """
    data = dict(payload or {}) if isinstance(payload, dict) else payload
    if not isinstance(data, dict) or "est_duration_minutes" not in data:
        return payload
    minutes = data.pop("est_duration_minutes")
    if minutes is None:
        data["est_duration"] = None
        return data
    data["est_duration"] = timedelta(minutes=_int(minutes, "est_duration_minutes", minimum=0))
    return data


def create_draft(actor: Any, payload: Any) -> dict[str, Any]:
    """A new template, as a DRAFT — version 0, no number (`BR-WRK-011`)."""
    return metering_seam.create_template(actor, _minutes_to_duration(payload))


def update_header(actor: Any, template_id: Any, payload: Any) -> dict[str, Any]:
    """Header edits. `active` is NOT settable here — `DEF-WRK-3579`."""
    return metering_seam.update_template(actor, template_id, _minutes_to_duration(payload))


def _refuse_empty_help(template_id: Any) -> None:
    """FB-031 (`DEF-FLD-10805`, decision log 2026-10-31) — a template is not
    published with an EMPTY help row: a document row with nothing in it, or a
    phone row with no number. The "Meter exchange" starter pack adds both
    (`packs`), and a job raised from it showed a technician an SOP that never
    downloads. Drafts may hold them — the pack's labels are the prefill.

    ⚠ A document row naming a TYPED label (*STD-EL-004*, written before uploads
    existed) is not refused here: it is listed on the phone as *No file
    attached.* and the builder marks it *No file*. Refusing it would stop every
    template carrying one — the sample data's among them — from being
    republished until a file is found for it (coordinator judgment, decision
    log 2026-10-31 FB-031)."""
    for row in models.WorkOrderTemplateHelp.objects.filter(
        tenant_id=_tenant_id(), template_id=template_id
    ).order_by("seq"):
        ref = (row.ref or "").strip()
        if row.kind == models.HELP_KIND_DOCUMENT and not ref:
            _refuse(errors.VAL_REQUIRED, "work.template.help_needs_file", field="help", label=row.label)
        if row.kind == "phone" and not any(ch.isdigit() for ch in ref):
            _refuse(errors.VAL_REQUIRED, "work.template.help_needs_number", field="help", label=row.label)


def refresh_open_job_help(actor: Any, template_id: Any) -> int:
    """FB-031 — a template's help, changed, reaches the jobs raised from it
    that are OPEN and NOT STARTED (planned; queued, scheduled or on the way —
    nobody on site yet), so a file attached this afternoon is on tomorrow's
    job. Answers how many jobs.

    ⚠ **A NARROWING OF `BR-WRK-008`'s *copy, never link*, FOR HELP ONLY.** A
    started job keeps the help it was given — the record of what the
    technician had in hand — and nothing else a job copied moves. Each job's
    `updated_at` is touched through the seam's one write door, so the change
    feed sends the job again and the phone re-fetches its bundle."""
    from apps.work import connection_models as work_tables

    tenant_id = _tenant_id()
    rows = list(
        models.WorkOrderTemplateHelp.objects.filter(tenant_id=tenant_id, template_id=template_id)
        .order_by("seq")
    )
    orders = list(
        work_tables.WorkOrder.objects.filter(
            tenant_id=tenant_id,
            template_id=template_id,
            state=work_tables.WO_PLANNED,
            dispatch_state__in=(
                work_tables.DISPATCH_QUEUED,
                work_tables.DISPATCH_SCHEDULED,
                work_tables.DISPATCH_EN_ROUTE,
            ),
        )
    )
    if not orders:
        return 0
    with transaction.atomic():
        for order in orders:
            models.WorkOrderHelp.objects.filter(tenant_id=tenant_id, work_order_id=order.id).delete()
            models.WorkOrderHelp.objects.bulk_create(
                [
                    models.WorkOrderHelp(
                        tenant_id=tenant_id,
                        work_order_id=order.id,
                        seq=row.seq,
                        kind=row.kind,
                        label=row.label,
                        ref=row.ref,
                    )
                    for row in rows
                ]
            )
            metering_seam.save_order_fields(order, [])
        _audit(
            actor,
            "work_order_template.help_refreshed_on_jobs",
            template_id,
            after={"orders": [str(o.id) for o in orders], "rows": len(rows)},
        )
    return len(orders)


def publish(actor: Any, template_id: Any, *, change_note: Any = None) -> dict[str, Any]:
    """**THE ONE WRITE** (`BR-WRK-011`).

    Two halves in one transaction: metering sets the version and allocates
    `ST-{0000}` the first time; this writes the `work_order_template_versions`
    row. Neither module writes the other's table.

    ⚠ **A SECOND PUBLISH WITH NOTHING CHANGED RETURNS THE VERSION THAT ALREADY
    EXISTS.** The demo presses Publish twice within a second and expects one
    version. This is not an idempotency key — it is the honest question: has
    anything in this bundle changed since the last publish? If not, there is
    nothing to version, and a v2 identical to v1 is a number a supervisor has
    to explain on `Work-022`.
    """
    header = _header_or_404(template_id)
    _refuse_empty_help(header["id"])
    current = (
        models.WorkOrderTemplateVersion.objects.filter(
            tenant_id=_tenant_id(), template_id=header["id"]
        )
        .order_by("-version")
        .first()
    )
    if current is not None:
        touched = _bundle_touched_at(header["id"], header)
        if touched is None or touched <= current.published_at:
            return {
                **header,
                "version": current.version,
                "published_at": current.published_at.isoformat(),
                "created": False,
            }
    with transaction.atomic():
        published = metering_seam.publish_template(actor, header["id"])
        row = models.WorkOrderTemplateVersion.objects.create(
            tenant_id=_tenant_id(),
            template_id=header["id"],
            version=published["version"],
            published_at=timezone.now(),
            published_by=getattr(actor, "id", None),
            change_note=(str(change_note).strip() or None) if change_note else None,
        )
    return {
        **metering_seam.template(header["id"]),
        "version": row.version,
        "published_at": row.published_at.isoformat(),
        "created": True,
    }


def duplicate(actor: Any, template_id: Any) -> dict[str, Any]:
    """`US-WRK-015` TC-7 — a new DRAFT carrying every child row, name suffixed.

    The copy is version 0 with no `template_no`: it has never been published,
    so it has issued no number and produced no order. Nothing about the
    original moves.
    """
    header = _header_or_404(template_id)
    tenant_id = _tenant_id()
    payload = {
        "name": _unique_copy_name(header),
        "service": header["service"]["code"] if header.get("service") else None,
        "scope": header["scope"],
        # ⚠ `sequence` is NOT copied. A duplicate is a new job the utility is
        # authoring, not a second row in the connection sequence — copying it
        # would make New Connect step 6 propose two of the same thing
        # (`BR-WRK-016`, `DEF-WRK-3573`).
        "type_id": (header["job_type"] or {}).get("id"),
        "skill_id": (header["skill"] or {}).get("id"),
        "safety_kit_id": (header["safety_kit"] or {}).get("id"),
        "crew_size": header["crew_size"],
        "est_duration": header["est_duration"],
        "is_gate": False,
        "no_gate_reason": header["no_gate_reason"],
    }
    with transaction.atomic():
        copy = metering_seam.create_template(actor, payload)
        for model in (*COLLECTIONS.values(), models.WorkOrderTemplateDetail):
            rows = list(model.objects.filter(tenant_id=tenant_id, template_id=header["id"]))
            clones = []
            for row in rows:
                row.pk = None
                row.id = None
                row.template_id = copy["id"]
                clones.append(row)
            if clones:
                model.objects.bulk_create(clones)
        _audit(
            actor,
            "work_order_template.duplicated",
            copy["id"],
            before={"template_no": header["template_no"], "name": header["name"]},
            after={"name": copy["name"], "version": 0},
        )
    return metering_seam.template(copy["id"])


def _unique_copy_name(header: dict[str, Any]) -> str:
    """*(copy)*, then *(copy 2)* — because `BR-WRK-010`'s key would otherwise
    refuse the second duplicate of the same template with a constraint error
    where the person expected a row."""
    base = f"{header['name']} (copy)"
    existing = set(
        metering_seam.templates_queryset()
        .filter(service_id=(header["service"] or {}).get("id"))
        .values_list("name", flat=True)
    )
    if base not in existing:
        return base
    n = 2
    while f"{header['name']} (copy {n})" in existing:
        n += 1
    return f"{header['name']} (copy {n})"


def deactivate(actor: Any, template_id: Any) -> dict[str, Any]:
    """`BR-WRK-012` — stop new orders, leave every raised order readable."""
    return metering_seam.set_template_active(actor, template_id, False)


def reactivate(actor: Any, template_id: Any) -> dict[str, Any]:
    """The mirror route `DEF-WRK-3579` asks for. `PATCH` never toggles
    `active`; these two named routes are the only writers of it."""
    return metering_seam.set_template_active(actor, template_id, True)


def delete(actor: Any, template_id: Any) -> dict[str, Any]:
    """`BR-WRK-012` — refused while ANY version is referenced, naming the
    count. The bundle goes with the header (CASCADE); the refusal is what
    stops that ever happening under a live order."""
    _header_or_404(template_id)
    return metering_seam.delete_template(actor, template_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-013/014/015/018@ce221fc9 (EP-WRK-03) · 10-execution-plan.md wave D tasks D1–D2 · 03-field-map.md §2.2, §3
# generated: 2026-09-05 by the CR-070 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(work/0004_rls_force_bundle is the 🔒 path; the review-ledger row is D5)
# gates: G78 (no ORM write on a foreign model; the header goes through metering_seam) · pytest tests/test_us_wrk_01{3,4,5,8}*.py · tests/test_us_wrk_rls_pg.py on PostgreSQL
# exceptions: E1 `uq(tenant, service, name, version)` carries `service`, which BR-WRK-010 (PROPOSED) does not — the four-column key is the only one the 24 CONFIRMED starters admit (Meter set ×4, Inspection ×3, Service connection ×2); judgment recorded in the decision log 2026-09-05 · E3 the eight-step builder (US-WRK-016) is wave E's and no control for it is rendered here (law 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
