# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (S16 bulk create — premises CSV · unit pattern generator ·
#           units CSV with asset columns)   Screens: S16
# Rules:    BR-MET-004 (staged: every row validated before anything is written) ·
#           BR-MET-005 (pattern total = floors × units/floor, ≤3,000 per run) ·
#           BR-MET-031 ({seq}/{floor} token grammar, BOTH paths) · BR-MET-038
#           (10 MB · 10,000-row cap · skip-errors ON · "N created · N failed"
#           ALWAYS shown) · BR-MET-039 (asset columns reference OR create
#           inline, BR-AST-028) · BR-MET-002 (label unique per premise) ·
#           BR-MET-003 (services ⊆ tenant-enabled) · BR-MET-048 (batch audit)
# Tests:    06-backend/tests/test_us_met_004_bulk.py
# Impacts:  apps/metering/services.py (stage_import / commit_import) ·
#           apps.assets (inline asset creation + inventory reference seam)
# ───────────────────────────────────────────────────────
"""Staged bulk creation for premises & units (US-MET-004).

Staging is IN-MEMORY: US-MET-004 §5 states the validation-preview counts are
"computed over staged rows (no persistence in v1)", and no premises/unit
staging table exists in B2 (unlike assets, which has `asset_import_batches`).
So `stage()` returns the fully-validated row set and `commit()` re-validates
the same input before writing — the reviewed set and the written set are
computed by the SAME code path, which is what BR-MET-004 actually requires.
The divergence from 11b §2.5's id-bearing 3-step contract is reported, not
resolved here.

Nothing in this module writes a row itself: commits call the metering service
functions (sole writer, LAW 0) and the assets seam (BR-AST-028 one registry).
"""

import csv
import io
import re
from typing import Any

from apps.metering import models, seams
from core import errors

CSV_ROW_CAP = 10_000  # BR-MET-038 (same discipline as assets, BR-AST-034)
CSV_BYTE_CAP = 10 * 1024 * 1024  # US-MET-004 §5: ≤10 MB UTF-8
PATTERN_UNIT_CAP = 3_000  # BR-MET-005/038

KINDS = ("premises_csv", "units_csv", "units_pattern")

# Column mapping is auto-detected BY HEADER and remappable (US-MET-004 §5).
# target → the header aliases the auto-detector accepts (lower-cased, trimmed).
PREMISES_COLUMNS: dict[str, tuple[str, ...]] = {
    "address_line": ("address", "address_line", "street address", "street"),
    "city": ("city",),
    "state": ("state",),
    "postal_code": ("zip", "postal_code", "postcode", "zip code"),
    "premises_type": ("type", "property type", "premises_type"),
    "unit_count": ("units", "unit_count", "number of units"),
    "owner_manager": ("owner", "owner/manager", "owner_manager", "manager"),
    "services": ("services", "services available"),
    "route": ("route",),
    "external_ref": ("external ref", "external_ref", "gis ref"),
}
UNIT_COLUMNS: dict[str, tuple[str, ...]] = {
    "premise_ref": ("premise_id", "premise", "premise no", "premise_no"),
    "label": ("unit_label", "unit", "label"),
    "unit_type": ("type", "unit_type"),
    "floor_label": ("floor", "floor_label"),
    "square_feet": ("sq ft", "sqft", "square_feet"),
    "services": ("services",),
    "asset_no": ("asset #", "asset_no", "asset", "meter #", "meter_no"),
    "asset_serial": ("serial", "asset_serial", "serial #"),
    "asset_type": ("asset type", "asset_type"),
    "occupant": ("occupant",),
}
REQUIRED_TARGETS = {
    "premises_csv": ("address_line",),
    "units_csv": ("premise_ref", "label"),
}

# BR-MET-031 token grammar; the optional `:00` pad reuses the RATIFIED
# BR-TEN-035 zero-pad convention (Eng disposition — reported).
_TOKEN_RE = re.compile(r"\{(seq|floor)(?::(0+))?\}")
_ANY_TOKEN_RE = re.compile(r"\{([^{}]*)\}")


def _refuse(code: str, message_key: str, **params: Any) -> None:
    raise errors.ValidationError(code, message_key=message_key, params=params)


def _cap(message_key: str, **params: Any) -> None:
    """BR-MET-038 caps refuse as BIZ-CAP (11b G11 → 422)."""
    raise errors.BizError(
        errors.BIZ_CAP, br_ref="BR-MET-038", message_key=message_key, params=params
    )


# ── parsing + column mapping ────────────────────────────────────────────────
def _parse_csv(payload: dict[str, Any], columns: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    content = payload.get("content")
    if content is None:
        _refuse(errors.VAL_REQUIRED, "metering.import.file_required")
    text = str(content)
    if len(text.encode("utf-8")) > CSV_BYTE_CAP:
        _cap("metering.import.file_too_large", max_bytes=CSV_BYTE_CAP)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        _refuse(errors.VAL_FORMAT, "metering.import.header_required")
    detected = _auto_map(list(reader.fieldnames), columns)
    for target, source in (payload.get("mapping") or {}).items():
        if target not in columns:
            _refuse(errors.VAL_FORMAT, "metering.import.unknown_mapping_target", target=target)
        detected[target] = source
    rows = []
    for raw in reader:
        rows.append(raw)
        if len(rows) > CSV_ROW_CAP:  # BR-MET-038: rejected AT UPLOAD, nothing staged
            _cap("metering.import.row_cap_exceeded", max_rows=CSV_ROW_CAP)
    return {"mapping": detected, "raw_rows": rows, "headers": list(reader.fieldnames)}


def _auto_map(headers: list[str], columns: dict[str, tuple[str, ...]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    lowered = {str(h).strip().lower(): h for h in headers}
    for target, aliases in columns.items():
        for alias in aliases:
            if alias in lowered:
                mapping[target] = lowered[alias]
                break
    return mapping


def _value(raw: dict[str, Any], mapping: dict[str, str], target: str) -> str | None:
    source = mapping.get(target)
    if source is None:
        return None
    value = raw.get(source)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,|]", value) if part.strip()]


# ── staging ─────────────────────────────────────────────────────────────────
def stage(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind") or "").strip()
    if kind not in KINDS:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "metering.import.kind_unknown", allowed=list(KINDS))
    if kind == "units_pattern":
        return _stage_pattern(payload)
    columns = PREMISES_COLUMNS if kind == "premises_csv" else UNIT_COLUMNS
    parsed = _parse_csv(payload, columns)
    missing = [t for t in REQUIRED_TARGETS[kind] if t not in parsed["mapping"]]
    if missing:
        _refuse(errors.VAL_REQUIRED, "metering.import.required_column_unmapped", targets=missing)
    staged = _stage_premises_rows(parsed) if kind == "premises_csv" else _stage_unit_rows(parsed)
    return {
        "kind": kind,
        "filename": payload.get("filename"),
        "mapping": parsed["mapping"],
        "rows": staged,
        "preview": _counts(staged),
    }


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The S16 preview line: Rows / Valid / Warnings / Errors + DUPE callout."""
    duplicates = [r for r in rows if any(w.get("code") == "duplicate" for w in r["warnings"])]
    return {
        "rows": len(rows),
        "valid": sum(1 for r in rows if not r["errors"]),
        "warnings": sum(1 for r in rows if r["warnings"]),
        "errors": sum(1 for r in rows if r["errors"]),
        "duplicates": len(duplicates),
    }


def _blank_row(row_no: int, raw: dict[str, Any]) -> dict[str, Any]:
    return {"row_no": row_no, "raw": raw, "data": {}, "errors": [], "warnings": []}


def _stage_premises_rows(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.metering import services

    services.ensure_reference_catalogs()  # BR-MET-034: the seeded type list
    mapping = parsed["mapping"]
    enabled = seams.enabled_service_codes()
    types = {
        t.code.lower(): t
        for t in models.PremisesType.objects.filter(tenant_id=_tenant(), active=True)
    }
    type_names = {t.name.lower(): t for t in types.values()}
    seen_addresses: set[str] = set()
    staged: list[dict[str, Any]] = []
    for index, raw in enumerate(parsed["raw_rows"], start=1):
        row = _blank_row(index, raw)
        address = _value(raw, mapping, "address_line")
        if not address:
            row["errors"].append({"column": "address_line", "code": "required"})
        else:
            row["data"]["address_line"] = address
            key = address.lower()
            existing = models.Premises.objects.filter(
                tenant_id=_tenant(), address_line__iexact=address
            ).exists()
            if existing or key in seen_addresses:
                # BR-MET-004 DUPE callout: skipped unless the user opts to merge.
                row["warnings"].append({"column": "address_line", "code": "duplicate"})
            seen_addresses.add(key)
        for target in ("city", "state", "postal_code", "owner_manager", "external_ref"):
            value = _value(raw, mapping, target)
            if value:
                row["data"][target] = value
        type_value = _value(raw, mapping, "premises_type")
        if type_value:
            found = types.get(type_value.lower()) or type_names.get(type_value.lower())
            if found is None:
                row["errors"].append(
                    {"column": "premises_type", "code": "unknown_type", "value": type_value}
                )
            else:
                row["data"]["premises_type"] = found.code
        services = _split_list(_value(raw, mapping, "services"))
        unknown = [s for s in services if s not in enabled]
        if unknown:
            row["errors"].append(
                {"column": "services", "code": "service_not_enabled", "value": unknown}
            )
        elif services:
            row["data"]["services_available"] = services
        unit_count = _value(raw, mapping, "unit_count")
        if unit_count:
            try:
                row["data"]["unit_count"] = int(unit_count)
            except ValueError:
                row["errors"].append({"column": "unit_count", "code": "not_an_integer"})
        staged.append(row)
    return staged


def _stage_unit_rows(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = parsed["mapping"]
    enabled = seams.enabled_service_codes()
    seen_labels: set[tuple[str, str]] = set()
    staged: list[dict[str, Any]] = []
    for index, raw in enumerate(parsed["raw_rows"], start=1):
        row = _blank_row(index, raw)
        premise_ref = _value(raw, mapping, "premise_ref")
        premises = _find_premises(premise_ref) if premise_ref else None
        if premises is None:
            # BR-MET-034/BR-AST-034 discipline: premises must EXIST first;
            # a cross-tenant id simply does not resolve (US-MET-004 TC-8).
            row["errors"].append(
                {"column": "premise_ref", "code": "premise_must_exist", "value": premise_ref}
            )
        else:
            row["data"]["premises_id"] = str(premises.id)
        label = _value(raw, mapping, "label")
        if not label:
            row["errors"].append({"column": "label", "code": "required"})
        else:
            row["data"]["label"] = label
            if premises is not None:
                key = (str(premises.id), label.lower())
                clash = models.Unit.objects.filter(
                    tenant_id=_tenant(), premises=premises, label__iexact=label
                ).exists()
                if clash or key in seen_labels:
                    row["errors"].append({"column": "label", "code": "duplicate_label"})
                seen_labels.add(key)
        for target in ("unit_type", "floor_label"):
            value = _value(raw, mapping, target)
            if value:
                row["data"][target] = value
        sqft = _value(raw, mapping, "square_feet")
        if sqft:
            try:
                row["data"]["square_feet"] = int(sqft)
            except ValueError:
                row["errors"].append({"column": "square_feet", "code": "not_an_integer"})
        services = _split_list(_value(raw, mapping, "services"))
        unknown = [s for s in services if s not in enabled]
        if unknown:
            row["errors"].append(
                {"column": "services", "code": "service_not_enabled", "value": unknown}
            )
        elif services:
            row["data"]["services"] = services
        _stage_asset_columns(raw, mapping, row)
        staged.append(row)
    return staged


def _stage_asset_columns(raw: dict[str, Any], mapping: dict[str, str], row: dict[str, Any]) -> None:
    """BR-MET-039 / BR-AST-028: an asset # REFERENCES existing inventory; a
    serial + type CREATES a new asset inline. One registry, never duplicates."""
    asset_no = _value(raw, mapping, "asset_no")
    serial = _value(raw, mapping, "asset_serial")
    asset_type = _value(raw, mapping, "asset_type")
    if not (asset_no or serial or asset_type):
        return
    probe = seams.resolve("assets", "stage_probe")
    if asset_no:
        problem = probe(asset_no=asset_no) if probe is not None else None
        if problem:
            row["errors"].append({"column": "asset_no", "code": problem, "value": asset_no})
        else:
            row["data"]["asset_ref"] = {"mode": "reference", "asset_no": asset_no}
        return
    if not (serial and asset_type):
        row["errors"].append({"column": "asset_serial", "code": "serial_and_type_required"})
        return
    problem = probe(asset_type=asset_type) if probe is not None else None
    if problem:
        row["errors"].append({"column": "asset_type", "code": problem, "value": asset_type})
        return
    row["data"]["asset_ref"] = {"mode": "create", "serial_no": serial, "type": asset_type}


def _find_premises(ref: str) -> models.Premises | None:
    qs = models.Premises.objects.filter(tenant_id=_tenant())
    row = qs.filter(premise_no__iexact=ref).first()
    if row is not None:
        return row
    if _is_uuid(ref):
        return qs.filter(pk=ref).first()
    return None


def _is_uuid(value: Any) -> bool:
    from uuid import UUID

    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _tenant() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


# ── pattern generator (BR-MET-005/031/038) ──────────────────────────────────
def _stage_pattern(payload: dict[str, Any]) -> dict[str, Any]:
    spec = dict(payload.get("pattern") or {})
    premises = _find_premises(str(spec.get("premises_id") or ""))
    if premises is None:
        _refuse(errors.VAL_UNKNOWN_LOOKUP, "metering.import.premise_must_exist")
    try:
        floors = int(spec.get("floors", 1))
        per_floor = int(spec.get("units_per_floor", 0))
    except (TypeError, ValueError):
        floors, per_floor = 0, 0
        _refuse(errors.VAL_FORMAT, "metering.import.pattern_counts_not_integers")
    if floors < 1 or per_floor < 1:
        _refuse(errors.VAL_RANGE, "metering.import.pattern_counts_range")
    total = floors * per_floor
    if total > PATTERN_UNIT_CAP:  # US-MET-004 TC-5: blocked, nothing generated
        _cap("metering.import.pattern_cap_exceeded", total=total, max_units=PATTERN_UNIT_CAP)
    label_pattern = str(spec.get("label_pattern") or "")
    _validate_tokens(label_pattern, "label_pattern")
    unit_no_pattern = spec.get("unit_no_pattern")
    if unit_no_pattern:
        _validate_tokens(str(unit_no_pattern), "unit_no_pattern")
    enabled = seams.enabled_service_codes()
    # ── `DEF-MET-6796` · `BR-MET-119` AS AMENDED 2026-09-25 ────────────────
    # ⚠ **`None` MEANS *NOBODY WAS ASKED* AND IT MUST STAY `None` ALL THE WAY
    # TO THE CREATE.** This line read `spec.get("services") or []`, and the row
    # below set `"services": services` unconditionally — so **every unit this
    # wizard has ever generated arrived at `create_unit` carrying an explicit
    # empty list**, which under the amended rule is a clerk unticking
    # everything. The service-layer default would then be overruled by a key
    # the clerk never sent, on the one door that makes units in bulk.
    #
    # It is the `or []` trap the rule's own test names, one layer up from the
    # create: `data.get("services") or []` cannot tell an ABSENT key from a
    # deliberate `[]`, and here the absent one is the common case.
    raw_services = spec.get("services")
    services = (
        None
        if raw_services is None
        else [s for s in raw_services if s in enabled]
    )
    # ── `CR-176-BRC10` · a unit's services come ONLY from its building ─────
    # PO 2026-10-09, rule (3): *"a unit takes services only from its building,
    # all ticked to start, refused on save otherwise"*. `create_unit` already
    # refuses one at the press (`_refuse_service_not_at_premises`, per row);
    # this says it at Continue, once, naming every code, so the review is never
    # a review of a run the press will refuse row by row.
    if raw_services is not None:
        _refuse_services_not_at_building(premises, raw_services)
    # ── `CR-176-BRC10` · a common area is ONE unit (rule 5, changed) ──────
    # *"a common area is a choice made at the start; it is one unit of the
    # chosen kind, billed to the owner, with no count"*. The screen sends one;
    # a door that sent three laundries would make three shared spaces billed to
    # the owner under one name, so the count is refused here rather than
    # trusted.
    if spec.get("is_common_area") is True and total != 1:
        _refuse(errors.VAL_RANGE, "metering.import.common_area_one_unit", total=total)
    # ── CR-089 wave E (`E5`/`PUJ-25`) · BR-MET-007 ─────────────────────────
    # ⚠ **THE CONTRACT WAS ALREADY THERE AND ONLY THE PANEL WAS MISSING.**
    # `services.create_unit` has accepted a nested `plan` block since S16 was
    # written (`_apply_unit_plan`, `source="new_connection"`); the wizard simply
    # never drew it, so every unit generated here landed with no plan and
    # `BR-MET-100`'s *unplanned* filter was the only thing that noticed. The
    # block is carried through the staged row UNVALIDATED on purpose: the
    # create's own `_apply_unit_plan` is the one place a plan id is resolved and
    # refused (`BR-RAT-030` — an unpublished plan is as unknown as a made-up
    # one), and a second check here would be a second definition of which plans
    # a unit may be put on.
    plan = spec.get("plan") if isinstance(spec.get("plan"), dict) else None
    # ── CR-089 U2 · TWO MORE FIELDS THE FRAME DRAWS AND THE GENERATOR DROPPED ─
    # `create_unit` has accepted `floor_label` and `is_common_area` since
    # `_validate_unit` was written; `_stage_pattern` simply never put them in
    # the row, so the add-units wizard could not offer either and every unit it
    # made had an empty floor. Both are carried the same way the `plan` block
    # above is — into `row["data"]`, where `_commit_row` hands the whole dict to
    # the ONE create — so neither gets a second definition here.
    #
    # ⚠ `is_common_area` IS COERCED TO A STRICT BOOLEAN AT THE CREATE and not
    # here: `BR-MET-101`'s validator refuses a non-boolean by name, and a
    # truthiness test in this file would let the string `"false"` flag a unit
    # somebody lives in as shared space and bill it to the owner.
    floor_label = str(spec.get("floor_label") or "").strip()
    common_area = spec.get("is_common_area")
    # ── 2026-09-19 · A THIRD FIELD THE FORM DRAWS AND THE GENERATOR DROPPED ──
    # `Floor area` is on the add-units wizard from today (PO: *"Unit add form ->
    # square feet field present on edit form but not present on add form
    # why?"*), and this is the identical shape as `floor_label` above: the
    # column exists, `_validate_unit` has parsed and range-checked it since it
    # was written, the units CSV importer maps it as `Floor area (sq ft)` — and
    # `_stage_pattern` simply never put it in the row, so the one path a clerk
    # would actually use could not set it.
    #
    # ⚠ **IT IS NOT COERCED HERE, ON PURPOSE — THE SAME ARGUMENT AS
    # `is_common_area` ABOVE.** `_validate_unit` is the ONE place a floor area
    # is parsed and refused (`metering.unit.square_feet_range` for a negative,
    # `VAL_RANGE` for a non-integer), and a second `int()` in this file would be
    # a second definition of what a valid area is — which is how a row that the
    # create would have refused gets staged as valid and shown on a review.
    #
    # ⚠ **`is not None` RATHER THAN TRUTHINESS, AND THAT IS NOT A STYLE
    # CHOICE.** A `0` is falsy and is a legitimate figure a clerk may type; the
    # `floor_label` line above can use truthiness because `""` genuinely means
    # *not recorded* for a string, and this cannot.
    square_feet = spec.get("square_feet")
    # ── `CR-161-BRC10` W3 · `DEF-MET-9227` / `DEF-MET-9173` — THE TENANT'S
    # OWN FIELDS, TYPED ONCE ON *Add units* AND CARRIED ONTO EVERY UNIT ────
    # Validated HERE, once, with the screen this wizard is (`UNIT_ADD`), so a
    # wrong option or a blank required field is refused at the review rather
    # than failing every generated row at the press. The create validates again
    # with the same screen — the one validator, called twice, never copied.
    unit_custom, point_custom = _pattern_custom_data(spec, premises, services, enabled)

    seen: set[str] = set()
    staged: list[dict[str, Any]] = []
    row_no = 0
    floor_start = int(spec.get("floor_start", 1))
    seq_start = int(spec.get("seq_start", 1))
    # ── `CR-176-BRC10` rule (1) · A TAKEN LABEL IS REFUSED, NAMING IT AND THE
    # NEXT FREE START ───────────────────────────────────────────────────────
    # PO 2026-10-09: *"numbering starts at the first number from which the
    # WHOLE run is free; a taken number is refused naming the taken labels and
    # offering the next free one"* (worked: Unit 1, 2, 3 and 5 on file; three
    # units from 1 → *"Unit 1, Unit 2, Unit 3 are taken. Use 6"*). This used to
    # mark each clashing ROW `duplicate_label` and leave the screen to count
    # them; the clerk was told *how many* clashed and never *which*, nor where
    # to start instead. The taken set is read ONCE (it was one `exists()` per
    # generated row) with `_check_unit_label_unique`'s own scope — every unit at
    # the address, a removed one included, because that is what the create
    # refuses.
    taken = existing_unit_labels(premises)
    clashing = [
        label
        for label in run_labels(
            label_pattern, floors=floors, per_floor=per_floor,
            floor_start=floor_start, seq_start=seq_start,
        )
        if label.lower() in taken
    ]
    if clashing:
        next_free = next_free_seq_start(
            premises, label_pattern=label_pattern, floors=floors,
            per_floor=per_floor, floor_start=floor_start, taken=taken,
        )
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=(
                "metering.import.pattern_labels_taken"
                if next_free is not None
                else "metering.import.pattern_labels_taken_no_seq"
            ),
            params={
                "labels": ", ".join(clashing),
                "count": len(clashing),
                "next_free": next_free,
                "taken": clashing,
            },
            field_errors=[
                {
                    "field": "seq_start",
                    "code": errors.VAL_FORMAT,
                    "message_key": "metering.import.pattern_labels_taken",
                    "params": {"labels": ", ".join(clashing), "count": len(clashing),
                               "next_free": next_free},
                }
            ],
        )
    for floor in range(floor_start, floor_start + floors):
        for seq in range(seq_start, seq_start + per_floor):
            row_no += 1
            label = _render_tokens(label_pattern, floor=floor, seq=seq)
            row = _blank_row(row_no, {"floor": floor, "seq": seq})
            row["data"] = {
                "premises_id": str(premises.id),
                "label": label,
                "unit_type": spec.get("unit_type"),
            }
            # Absent rather than empty — see the block above. `[]` is a clerk's
            # answer and is carried; a missing key lets the address answer.
            if services is not None:
                row["data"]["services"] = services
            if floor_label:
                row["data"]["floor_label"] = floor_label
            if common_area is not None:
                row["data"]["is_common_area"] = common_area
            if square_feet is not None:
                row["data"]["square_feet"] = square_feet
            if unit_no_pattern:
                row["data"]["unit_no"] = _render_tokens(str(unit_no_pattern), floor=floor, seq=seq)
            if plan:
                row["data"]["plan"] = dict(plan)
            if unit_custom:
                row["data"]["custom_data"] = dict(unit_custom)
            if point_custom:
                row["data"]["service_point_custom_data"] = {
                    code: dict(answers) for code, answers in point_custom.items()
                }
            # A label already on file was refused above, by name. What is left
            # is a pattern that repeats ITSELF (no `{seq}`, or `{floor}` alone
            # over one floor), which stays a row error as it always was.
            if label.lower() in seen:
                row["errors"].append({"column": "label", "code": "duplicate_label"})
            seen.add(label.lower())
            staged.append(row)
    return {
        "kind": "units_pattern",
        "filename": None,
        "mapping": {},
        "rows": staged,
        "preview": {**_counts(staged), "total": total},
    }


#: The custom-field slot the Add units wizard is (`custom_fields.SLOTS`).
ADD_UNITS_SCREEN = "UNIT_ADD"


def _pattern_custom_data(
    spec: dict[str, Any], premises: Any, services: list[str] | None, enabled: Any
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """The unit's answers and each service point's, validated for `UNIT_ADD`.

    The service list is the one the CREATE will use — the clerk's ticks when
    sent, otherwise the address's offer narrowed to what the utility sells
    (`_services_for_a_new_unit`'s default) — so a required service-point field
    binds on exactly the points that will exist. Only non-empty answers are
    returned, so a tenant with no fields stages rows of the shape it always did.
    """
    from apps.metering import services as metering_services

    unit_answers = seams.validate_custom_data(
        "units", spec.get("custom_data"), screen=ADD_UNITS_SCREEN
    )
    codes = (
        list(services)
        if services is not None
        else [code for code in (premises.services_available or []) if code in enabled]
    )
    point_answers = metering_services._service_point_custom_data(
        {"service_point_custom_data": spec.get("service_point_custom_data")},
        codes,
        ADD_UNITS_SCREEN,
    )
    return unit_answers, {code: answers for code, answers in point_answers.items() if answers}


def _validate_tokens(pattern: str, field: str) -> None:
    if not pattern.strip():
        _refuse(errors.VAL_REQUIRED, "metering.import.pattern_required", field=field)
    for token in _ANY_TOKEN_RE.findall(pattern):
        if not re.fullmatch(r"(seq|floor)(:0+)?", token):
            # BR-MET-031: the CONFIRMED grammar is {seq}/{floor} only.
            _refuse(
                errors.VAL_FORMAT,
                "metering.import.pattern_token_unknown",
                field=field,
                token="{" + token + "}",
            )


def _render_tokens(pattern: str, *, floor: int, seq: int) -> str:
    def fill(match: re.Match) -> str:
        name, pad = match.group(1), match.group(2)
        value = floor if name == "floor" else seq
        return str(value).zfill(len(pad)) if pad else str(value)

    return _TOKEN_RE.sub(fill, pattern)


# ── `CR-176-BRC10` rule (1) · THE FIRST START FROM WHICH THE WHOLE RUN IS FREE ─
def existing_unit_labels(premises: Any) -> set[str]:
    """Every label already used at this address, lower-cased.

    The SAME scope as `services._check_unit_label_unique` — every unit at the
    address, a removed one included — because this set decides which starts the
    screen may offer, and offering a start the create then refuses is the bug
    this exists to close (`DEF-MET-10035`: *"Start numbering at defaults to 1
    when Unit 1 is taken"*)."""
    return {
        str(label).lower()
        for label in models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises=premises
        ).values_list("label", flat=True)
        if label
    }


def run_labels(
    pattern: str, *, floors: int, per_floor: int, floor_start: int, seq_start: int
) -> list[str]:
    """The labels a run makes, in the order `_stage_pattern` makes them."""
    return [
        _render_tokens(pattern, floor=floor, seq=seq)
        for floor in range(floor_start, floor_start + floors)
        for seq in range(seq_start, seq_start + per_floor)
    ]


def next_free_seq_start(
    premises: Any,
    *,
    label_pattern: str,
    floors: int = 1,
    per_floor: int = 1,
    floor_start: int = 1,
    taken: set[str] | None = None,
) -> int | None:
    """**The first `seq_start` from which EVERY label the run makes is free.**

    PO 2026-10-09, worked: *"123 Main Street holds Unit 1, 2, 3 and 5; three
    units from 1 → Unit 1, Unit 2, Unit 3 are taken. Use 6"*. Not 4: three
    units from 4 would make Unit 4, Unit 5, Unit 6 and hit Unit 5, and a
    *"Use N"* that lands on another refusal is a button that lies.

    ⚠ **IT JUMPS PAST EACH CLASH RATHER THAN STEPPING BY ONE.** A clash at seq
    `s` rules out every start up to `s`, so the next candidate is `s + 1`. That
    makes the walk proportional to the labels on file plus the run, never to
    their product — no limit on either is assumed or imposed (`NFR-5`).

    `None` when the pattern has no `{seq}`: every start makes the same labels,
    so no number can be offered and the refusal says only what is taken.
    """
    if "{seq" not in label_pattern or floors < 1 or per_floor < 1:
        return None
    used = taken if taken is not None else existing_unit_labels(premises)
    start = 1
    while True:
        clash_at = None
        for floor in range(floor_start, floor_start + floors):
            for seq in range(start, start + per_floor):
                if _render_tokens(label_pattern, floor=floor, seq=seq).lower() in used:
                    clash_at = seq if clash_at is None else max(clash_at, seq)
        if clash_at is None:
            return start
        start = clash_at + 1


def _refuse_services_not_at_building(premises: Any, asked: Any) -> None:
    """`CR-176-BRC10` rule (3) — every service asked for must be one the
    building offers. Names them all, and the building, in the sentence
    `create_unit` already uses for one (`metering.service_not_at_premises`), so
    the two doors say the same thing."""
    from apps.metering import services as metering_services

    offered = list(premises.services_available or [])
    stray = [str(code) for code in (asked or []) if code not in offered]
    if not stray:
        return
    offered_text = ", ".join(str(code) for code in offered) or "nothing"
    params = {
        "service": ", ".join(stray),
        "premises": metering_services._premises_ref(premises),
        "offered": offered_text,
    }
    raise errors.ValidationError(
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="metering.service_not_at_premises",
        params=params,
        field_errors=[
            {
                "field": "services",
                "code": errors.VAL_UNKNOWN_LOOKUP,
                "message_key": "metering.service_not_at_premises",
                "params": params,
            }
        ],
    )


# ── commit (BR-MET-004/038 — result summary ALWAYS returned) ────────────────
def commit(actor: Any, payload: dict[str, Any], staged: dict[str, Any]) -> dict[str, Any]:
    from apps.metering import services

    options = dict(payload.get("options") or {})
    skip_errors = bool(options.get("skip_errors", True))  # BR-MET-038 default ON
    merge_duplicates = bool(options.get("merge_duplicates", False))
    rows = staged["rows"]
    error_rows = [r for r in rows if r["errors"]]
    if error_rows and not skip_errors:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-004",
            message_key="metering.import.errors_must_be_fixed",
            params={"errors": len(error_rows)},
        )

    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in rows:
        if row["errors"]:
            failed.append({"row_no": row["row_no"], "reasons": row["errors"]})
            continue
        is_duplicate = any(w.get("code") == "duplicate" for w in row["warnings"])
        if is_duplicate and not merge_duplicates:
            failed.append({"row_no": row["row_no"], "reasons": row["warnings"]})
            continue
        try:
            created.append(_commit_row(actor, staged["kind"], row, options, services))
        except (errors.ApiError, errors.NotFoundError) as exc:
            failed.append(
                {
                    "row_no": row["row_no"],
                    "reasons": [{"code": getattr(exc, "message_key", "refused")}],
                }
            )
    action = "premises.bulk_created" if staged["kind"] == "premises_csv" else "units.bulk_created"
    services._audit(  # BR-MET-048: one batch row (file, counts, actor)
        actor,
        action,
        "premises" if staged["kind"] == "premises_csv" else "unit",
        None,
        after={
            "file": staged.get("filename"),
            "kind": staged["kind"],
            "created": len(created),
            "failed": len(failed),
        },
    )
    return {
        "kind": staged["kind"],
        "preview": staged["preview"],
        # BR-MET-038: the summary is rendered after EVERY create, with reasons.
        "summary": {"created": len(created), "failed": len(failed)},
        "created": created,
        "errors": failed,
    }


def _commit_row(
    actor: Any, kind: str, row: dict[str, Any], options: dict[str, Any], services: Any
) -> dict[str, Any]:
    """`__wrapped__` calls the UNGUARDED service body deliberately: the actor's
    role was already checked once at the batch entry point (`commit_import` is
    @require_role'd), and re-running the guard per row would turn one refusal
    into N identical ones. Every row still goes through the SAME validation and
    audit path as a single create — nothing bypasses the rules, only the
    repeated role check."""
    data = dict(row["data"])
    if kind == "premises_csv":
        unit_count = data.pop("unit_count", None)
        data.pop("route", None)
        payload = dict(data)
        if unit_count == 1 and options.get("auto_create_unit"):
            payload["auto_create_unit"] = True
            payload["unit"] = {"label": "Unit A"}
        return services.create_premises.__wrapped__(actor, payload)
    asset_ref = data.pop("asset_ref", None)
    # `CR-161-BRC10` W3 — the generator is the Add units wizard's door, so its
    # rows are created as `UNIT_ADD`; a units CSV is an import and names none.
    result = services.create_unit.__wrapped__(
        actor,
        data,
        custom_fields_screen=ADD_UNITS_SCREEN if kind == "units_pattern" else None,
    )
    if asset_ref:
        # ⚠ **THE UNIT'S OWN POINTS, NOT THE REQUEST'S (`DEF-MET-6796`).** This
        # read `data.get("services") or []`, which is `[]` for every row that
        # INHERITS its services from the address — so the meter on such a row
        # would be attached with no service point at all. What the unit ended
        # up holding is a fact only the create knows, and it is the fact a
        # meter has to be fitted into (`BR-MET-119`: the unit's services are
        # the set of slots a meter can go in).
        from apps.metering import selectors as metering_selectors

        held = [
            point["service"]
            for point in metering_selectors.service_points_for(result["id"])
            if point["service"]
        ]
        result["asset"] = _link_asset(actor, result["id"], held, asset_ref)
    return result


def _link_asset(
    actor: Any, unit_id: str, service_codes: list[str], asset_ref: dict[str, Any]
) -> dict[str, Any] | None:
    """BR-MET-039/BR-AST-028: reference existing OR create inline — both land
    in the one assets registry, through the assets service (never here)."""
    from apps.metering import services

    service = service_codes[0] if service_codes else None
    service_point_id = str(services.ensure_service_point(unit_id, service)) if service else None
    if asset_ref["mode"] == "reference":
        return seams.attach_existing_asset(
            actor=actor,
            asset_no=asset_ref["asset_no"],
            unit_id=unit_id,
            service_point_id=service_point_id,
            install_date=None,
        )
    return seams.create_asset_for_unit(
        actor=actor,
        unit_id=unit_id,
        service_point_id=service_point_id,
        payload={
            "type": asset_ref["type"],
            "serial_no": asset_ref["serial_no"],
            "unit": seams.service_default_uom(service) if service else None,
        },
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@d76f5b4 (story+rules snapshot hash — EP-MET-01 bulk-create story)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — called by services.stage_import/commit_import) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: staging is NOT persisted (US-MET-004 §5 "no persistence in v1"; no B2 premises/unit staging table) — E2 vs 11b §2.5's id-bearing 3-step contract, reported · the `{seq:00}` zero-pad reuses the RATIFIED BR-TEN-035 pad convention so US-MET-004 TC-2's "Apt 101…Apt 620" is renderable; BR-MET-031's confirmed grammar names only {seq}/{floor} — Eng disposition, reported
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
