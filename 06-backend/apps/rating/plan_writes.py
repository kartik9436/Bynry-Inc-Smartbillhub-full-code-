"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — the plan WRITES of the plans redesign,
`CR-167-BRC10` §7.3 (round 2 task 3). Part of the rating write path
(`services.py` remains the sole writer of every row; this module translates the
contract's body and calls it). Row in `12-governance/09-human-review-ledger.md`
(2026-10-03, CR-167-BRC10 r2 t3).

── THE CONTRACT'S BODY ─────────────────────────────────────────────────────
`POST /plans`, `PATCH /plans/{id}`, `POST /plans/{id}/versions`,
`POST /plans/{id}/corrections` take the WHOLE plan as the five steps lay it out::

    details      {name, code, description, customer_classes, intended_for, notes}
    services     [{service, schedule, surcharged}]
    outside_city_percent
    charge_codes [{charge, late_fee?}]       (the late fee is a row like any other)
    taxes        [{tax} | {jurisdiction}]
    deposits     [{charge}]                  (refundable codes, by class — ruling 9)
    discounts    [{discount, offered_from, offered_until}]
    budget_billing, minimum_bill_amount, effective_from, effective_to, publish, reason

and every refusal names the box by its path in THAT body (`charge_codes[2].charge`,
`details.name`) — ruling 6, *"An empty row is refused by name"*.

── THE THREE EDIT VERBS (`BR-RAT-1016`, ruling 1) ───────────────────────────
* **Name and details** — `PATCH` on a live plan: only `details`; the SAME
  version; an Audit line (`BR-RAT-1067`). Anything else is refused by name
  (`rating.plans.field_needs_new_version`).
* **Change from a date** — `POST …/versions`: a NEW dated version
  (`BR-RAT-1066`): *Save new version* (`publish:false`) or *Publish new version*;
  publishing ENDS the version in force the day before. A start before the
  utility's today, or on/before the start of the version it replaces, is refused
  (J4: issued bills are never re-priced — hard rule 4).
* **Fix a mistake** — `POST …/corrections` with `version` and `reason`: the same
  number and the same dates (`services.correct_plan_version`).

⚠ **THE 8-STEP FORM STILL POSTS THE OLD BODY** until task 8 retires it, so a
body with no `details` key is handed to `services` unchanged (`api.py`).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db import IntegrityError, connection, transaction
from django.db.models import Q

from apps.rating import charge_prices, models, plan_versioning, seams, selectors, services
from apps.rating import discounts as discount_models
from core import errors

#: The contract body's top-level keys (`CR-167-BRC10` §7.3).
BODY_KEYS = (
    "details",
    "services",
    "outside_city_percent",
    "charge_codes",
    "taxes",
    "deposits",
    "discounts",
    "budget_billing",
    "minimum_bill_amount",
    "effective_from",
    "effective_to",
    "publish",
    "reason",
    "version",
)
DETAIL_KEYS = ("name", "code", "description", "customer_classes", "intended_for", "notes")
INTENDED_FOR_KEYS = ("cap_proof", "min_demand_25kw", "owner_occupied")

#: Old body path → contract body path, for a refusal raised by `services`.
_PATHS = (
    ("charge_rules[", "charge_codes["),
    ("tax_rules[", "taxes["),
    ("account_type_ids", "details.customer_classes"),
    ("eligibility", "details.notes"),
    ("late_fee_charge", "charge_codes"),
    ("name", "details.name"),
    ("code", "details.code"),
    ("description", "details.description"),
)


def is_contract_body(payload: Any) -> bool:
    return isinstance(payload, dict) and "details" in payload


def _fe(field: str, key: str, code: str = errors.VAL_FORMAT, **params: Any) -> dict[str, Any]:
    return services._field_error(field, code, key, **params)


def _refuse(fe: list[dict[str, Any]]) -> None:
    services._refuse(fe)


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _rename(exc: errors.ValidationError) -> errors.ValidationError:
    """Rewrite the field paths of a `services` refusal into the contract body's."""
    for entry in getattr(exc, "field_errors", None) or []:
        field = str(entry.get("field") or "")
        for old, new in _PATHS:
            if field == old or field.startswith(old):
                entry["field"] = new + field[len(old):]
                break
    return exc


def _charge_by_ref(reference: Any) -> Any:
    lookup = models.Charge.objects.filter(deleted_at__isnull=True)
    try:
        return lookup.filter(pk=UUID(str(reference))).first()
    except (ValueError, AttributeError, TypeError):
        return lookup.filter(code=str(reference)).first()


def translate(payload: dict[str, Any], plan: Any = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The contract body → the body `services._validate_plan` reads, plus every
    refusal that can only be named in the contract's own paths.

    Facts with no box on the new form are CARRIED from the version being
    written over (`CR-167` §5.2 S5: `base_charge`, `gl_account_id`, a charge
    rule's `amount_override`/`recurrence`/`taxable`), so a save never clears a
    figure nobody could see (`DEF-422`)."""
    fe: list[dict[str, Any]] = []
    services._reject_unknown(payload, BODY_KEYS, fe)
    legacy: dict[str, Any] = {}
    existing_services: dict[str, Any] = {}
    existing_rules: dict[Any, Any] = {}
    if plan is not None:
        existing_services = {
            row.service.code: row
            for row in models.PlanService.objects.filter(rate_plan=plan).select_related("service")
        }
        existing_rules = {
            row.charge_id: row for row in models.PlanChargeRule.objects.filter(rate_plan=plan, role="charge")
        }

    details = payload.get("details") or {}
    if not isinstance(details, dict):
        fe.append(_fe("details", "rating.plans.rule_not_object"))
        details = {}
    services._reject_unknown(details, DETAIL_KEYS, fe, prefix="details.")
    for key in ("name", "code", "description"):
        if key in details:
            legacy[key] = details[key]
    if "customer_classes" in details:
        raw = details["customer_classes"] or []
        if not isinstance(raw, list):
            fe.append(_fe("details.customer_classes", "rating.plans.classes_not_a_list"))
            raw = []
        legacy["account_type_ids"] = [
            item.get("value") if isinstance(item, dict) else item
            for item in raw
            if not _empty(item.get("value") if isinstance(item, dict) else item)
        ]
    if "intended_for" in details or "notes" in details:
        blob = dict((plan.eligibility or {}) if plan is not None else {})
        ticks = details.get("intended_for") or {}
        for key in INTENDED_FOR_KEYS:
            if key in ticks:
                if ticks[key]:
                    blob[key] = True
                else:
                    blob.pop(key, None)
        if "notes" in details:
            notes = []
            for index, note in enumerate(details.get("notes") or []):
                note = note if isinstance(note, dict) else {}
                parts = [note.get("attribute"), note.get("operator"), note.get("value")]
                if all(_empty(part) for part in parts):
                    fe.append(_fe(f"details.notes[{index}]", "rating.plans.row_empty", errors.VAL_REQUIRED, table="notes", row=index + 1))
                    continue
                notes.append({"attribute": note.get("attribute"), "operator": note.get("operator"), "value": note.get("value")})
            blob["rules"] = notes
        legacy["eligibility"] = blob

    if "services" in payload:
        rows = []
        seen: set[str] = set()
        for index, item in enumerate(payload.get("services") or []):
            item = item if isinstance(item, dict) else {}
            code = item.get("service")
            if _empty(code):
                fe.append(_fe(f"services[{index}].service", "rating.plans.row_empty", errors.VAL_REQUIRED, table="services", row=index + 1))
                continue
            if code in seen:
                fe.append(_fe(f"services[{index}].service", "rating.plans.service_listed_twice", service=code))
                continue
            seen.add(code)
            schedule = item.get("schedule")
            if not _empty(schedule):
                try:
                    tariff = models.Tariff.objects.filter(pk=UUID(str(schedule))).select_related("service").first()
                except (ValueError, TypeError, AttributeError):
                    tariff = None
                if tariff is not None and tariff.service.code != code:
                    fe.append(_fe(f"services[{index}].schedule", "rating.plans.schedule_wrong_service", service=code))
                    continue
            kept = existing_services.get(code)
            rows.append(
                {
                    "service": code,
                    "tariff": None if _empty(schedule) else str(schedule),
                    "outside_city_exempt": not bool(item.get("surcharged", True)),
                    "base_charge": None if kept is None or kept.base_charge is None else str(kept.base_charge),
                    "gl_account_id": None if kept is None or kept.gl_account_id is None else str(kept.gl_account_id),
                    "currency": kept.currency if kept is not None else None,
                }
            )
        legacy["services"] = rows

    if "outside_city_percent" in payload:
        legacy["outside_city_percent"] = payload["outside_city_percent"]

    if "charge_codes" in payload:
        rules = []
        late = None
        seen_codes: set[Any] = set()
        candidates: list[Any] = []
        for index, item in enumerate(payload.get("charge_codes") or []):
            item = item if isinstance(item, dict) else {"charge": item}
            reference = item.get("charge")
            field = f"charge_codes[{index}].charge"
            if _empty(reference):
                fe.append(_fe(field, "rating.plans.row_empty", errors.VAL_REQUIRED, table="charge_codes", row=index + 1))
                continue
            charge = _charge_by_ref(reference)
            if charge is None:
                fe.append(_fe(field, "rating.plans.unknown_charge", errors.VAL_UNKNOWN_LOOKUP))
                continue
            if charge.id in seen_codes:
                fe.append(_fe(field, "rating.plans.charge_listed_twice", item=charge.code))
                continue
            seen_codes.add(charge.id)
            if charge.is_base:
                fe.append(_fe(field, "rating.plans.base_code_on_charges", item=charge.code))
                continue
            if item.get("late_fee"):
                late = charge
                continue
            if charge.charge_type == "penalty" and _is_late_fee_shaped(charge):
                candidates.append(charge)
                continue
            kept = existing_rules.get(charge.id)
            rules.append(
                {
                    "charge": str(charge.id),
                    "amount_override": None if kept is None or kept.amount_override is None else str(kept.amount_override),
                    "recurrence": kept.recurrence if kept is not None else "event",
                    "taxable": kept.taxable if kept is not None else False,
                }
            )
        # `BR-RAT-1011` / `DEF-RAT-9328` (§7.6) — the late fee is a row of the
        # ONE Charges list: the row flagged `late_fee`, else the penalty code
        # among the rows that charges a percentage (the seeded `LATE` first
        # when several do). No such row — `[]` included — means the plan
        # charges no late fee ($0.00, the PO's ruled case). Nothing is added.
        if late is None and candidates:
            seeded = [one for one in candidates if one.code == services.SEEDED_LATE_FEE_CODE]
            late = (seeded or candidates)[0]
        for other in candidates:
            if late is None or other.id != late.id:
                rules.append({"charge": str(other.id), "amount_override": None, "recurrence": "event", "taxable": False})
        legacy["charge_rules"] = rules
        legacy["late_fee_charge"] = None if late is None else str(late.id)
    elif plan is None:
        # A new plan whose body names no Charges list charges no late fee —
        # never the silent `LATE` default (`DEF-RAT-9328`, §7.6).
        legacy["late_fee_charge"] = None

    if "taxes" in payload:
        rules = []
        seen_tax: set[str] = set()
        for index, item in enumerate(payload.get("taxes") or []):
            item = item if isinstance(item, dict) else {"tax": item}
            key = "tax" if not _empty(item.get("tax")) else ("jurisdiction" if not _empty(item.get("jurisdiction")) else None)
            if key is None:
                fe.append(_fe(f"taxes[{index}].tax", "rating.plans.row_empty", errors.VAL_REQUIRED, table="taxes", row=index + 1))
                continue
            marker = f"{key}:{item[key]}"
            if marker in seen_tax:
                fe.append(_fe(f"taxes[{index}].{key}", "rating.plans.tax_listed_twice"))
                continue
            seen_tax.add(marker)
            rules.append({key: item[key]})
        legacy["tax_rules"] = rules

    if "deposits" in payload:
        legacy["deposits"] = [
            (item.get("charge") if isinstance(item, dict) else item) for item in (payload.get("deposits") or [])
        ]

    if "discounts" in payload:
        rows = []
        seen_d: set[str] = set()
        for index, item in enumerate(payload.get("discounts") or []):
            item = item if isinstance(item, dict) else {"discount": item}
            reference = item.get("discount")
            if _empty(reference):
                fe.append(_fe(f"discounts[{index}].discount", "rating.plans.row_empty", errors.VAL_REQUIRED, table="discounts", row=index + 1))
                continue
            if str(reference) in seen_d:
                fe.append(_fe(f"discounts[{index}].discount", "rating.plans.discount_listed_twice"))
                continue
            seen_d.add(str(reference))
            start, end = item.get("offered_from"), item.get("offered_until")
            if not _empty(start) and not _empty(end) and str(end) < str(start):
                fe.append(_fe(f"discounts[{index}].offered_until", "rating.plans.offer_window_backwards"))
                continue
            rows.append({"discount": reference, "available_from": start or None, "available_to": end or None})
        legacy["discounts"] = rows

    for key in ("budget_billing", "minimum_bill_amount", "effective_from", "effective_to"):
        if key in payload:
            legacy[key] = payload[key]
    return legacy, fe


def _is_late_fee_shaped(charge: Any) -> bool:
    """A penalty that charges a PERCENTAGE (on the code or in dated terms rows)
    — the shape of a late fee, as against a flat NSF or tamper fee."""
    if charge.percent is not None:
        return True
    return bool(charge_prices.rows_in_force([charge.id], None, terms=True).get(charge.id))


def _plan_dict(plan_id: Any, as_of: date | None = None) -> dict[str, Any]:
    from apps.rating import plan_reads

    body = selectors.plan_detail(plan_id)
    body.update(plan_reads.plan_sections(plan_id, as_of))
    return body


# ── POST /plans ──────────────────────────────────────────────────────────────


def create(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """*Save as draft* (`publish:false`) or *Publish plan* — one transaction, so
    a refused publish leaves no half-saved draft behind (ruling 10)."""
    legacy, fe = translate(payload)
    _refuse(fe)
    with transaction.atomic():
        try:
            created = services.create_plan(actor, legacy)
        except errors.ValidationError as exc:
            raise _rename(exc) from None
        if payload.get("publish"):
            services.publish_plan(actor, created["id"])
    return _plan_dict(created["id"])


# ── PATCH /plans/{id} ────────────────────────────────────────────────────────


def patch(actor: Any, plan_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """A draft: anything. A live plan: ONLY `details` (`BR-RAT-1067`); every
    other key is refused BY NAME — a price changes from a date or by a
    correction."""
    plan = selectors.plan_or_404(plan_id)
    if plan.status != services.PLAN_DRAFT:
        priced = [key for key in payload if key not in ("details", "reason")]
        if priced:
            raise services._needs_new_version(priced[0])
    legacy, fe = translate(payload, plan)
    _refuse(fe)
    legacy.pop("reason", None)
    try:
        services.update_plan(actor, plan_id, legacy)
    except errors.ValidationError as exc:
        raise _rename(exc) from None
    return _plan_dict(plan_id)


# ── POST /plans/{id}/versions · …/versions/{n}/publish ─────────────────────


def _refusal(field: str, key: str, **params: Any) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=key,
        params={**params, "br_ref": "BR-RAT-1066"},
        field_errors=[_fe(field, key, **params)],
    )


def _parse_day(value: Any) -> date | None:
    if _empty(value):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _copy_bindings(plan: Any, source_id: Any, target_id: Any) -> None:
    for model in (
        models.PlanService,
        models.PlanRateSchedule,
        models.PlanChargeRule,
        models.PlanTaxRule,
        discount_models.PlanDiscountRule,
    ):
        for row in model.all_versions.filter(rate_plan=plan, plan_version_id=source_id):
            row.pk = None
            row.id = None
            row.plan_version_id = target_id
            row._state.adding = True
            row.save()


def _check_start(plan: Any, start: date | None, *, exclude: Any = None) -> Any:
    """J4 and the window rules; answers the version the new one takes over from."""
    if start is None:
        raise _refusal("effective_from", "rating.plans.version_start_required")
    today = seams.tenant_today()
    if start < today:
        raise _refusal("effective_from", "rating.plans.version_start_in_past", today=today.isoformat())
    current = plan_versioning.version_on(plan.pk, start)
    if current is not None and current.pk != exclude:
        current_start = current.effective_from or plan.effective_from
        if current_start is not None and start <= current_start:
            raise _refusal(
                "effective_from",
                "rating.plans.version_start_not_after_current",
                start=current_start.isoformat(),
            )
    later = (
        models.PlanVersion.objects.filter(
            rate_plan=plan,
            status=plan_versioning.VERSION_PUBLISHED,
            superseded_by__isnull=True,
            effective_from__gte=start,
        )
        .exclude(pk=exclude)
        .exists()
    )
    if later:
        raise _refusal("effective_from", "rating.plans.versions_overlap")
    return current


def new_version(actor: Any, plan_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """*Change from a date* — `BR-RAT-1066`. Draft (`publish:false`, *Save new
    version*) or published (*Publish new version*). Worked: v1 09/01/2026 – no
    end; a v2 from 01/01/2027 ends v1 on 12/31/2026; 12/31/2026 prices by v1 and
    01/01/2027 by v2."""
    reason = str(payload.get("reason") or "").strip()
    fe: list[dict[str, Any]] = []
    if not reason:
        fe.append(_fe("reason", "rating.reason_required", errors.VAL_REQUIRED))
    start = _parse_day(payload.get("effective_from"))
    end = _parse_day(payload.get("effective_to"))
    if start is None:
        fe.append(_fe("effective_from", "rating.plans.version_start_required", errors.VAL_REQUIRED))
    if start is not None and end is not None and end < start:
        fe.append(_fe("effective_to", "rating.plans.window_inverted", errors.VAL_RANGE))
    content = {key: value for key, value in payload.items() if key not in ("effective_from", "effective_to", "reason", "publish")}
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        if plan.status != services.PLAN_PUBLISHED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1066",
                message_key="rating.plans.version_of_draft",
                params={"name": plan.name},
            )
        if models.PlanVersion.objects.filter(rate_plan=plan, status=plan_versioning.VERSION_DRAFT).exists():
            fe.append(_fe("effective_from", "rating.plans.one_draft_version"))
        legacy, more = translate(content, plan)
        fe += more
        _refuse(fe)
        current = _check_start(plan, start)
        # `DEF-RAT-10029` — History's `before`, read before anything below writes.
        with plan_versioning.pricing_day(start):
            before = services._plan_snapshot(plan.id)
        try:
            cleaned = services._validate_plan(legacy, partial=True, plan=plan)
        except errors.ValidationError as exc:
            raise _rename(exc) from None
        source = current or models.PlanVersion.objects.get(pk=plan_versioning.ensure_head(plan))
        number = (
            max(models.PlanVersion.objects.filter(rate_plan=plan, corrects__isnull=True).values_list("version_no", flat=True) or [0])
            + 1
        )
        terms = {name: getattr(source, name) for name in plan_versioning.TERM_FIELDS}
        for field in ("minimum_bill_amount", "outside_city_factor", "budget_billing", "late_fee_charge"):
            if field in cleaned:
                column = "late_fee_charge_id" if field == "late_fee_charge" else field
                terms[column] = getattr(cleaned[field], "pk", cleaned[field])
        version = models.PlanVersion.objects.create(
            tenant_id=plan.tenant_id,
            rate_plan=plan,
            version_no=number,
            change_reason=reason,
            submitted_by_id=services._actor_user_id(actor),
            snapshot={},
            status=plan_versioning.VERSION_DRAFT,
            effective_from=start,
            effective_to=end,
            **terms,
        )
        _copy_bindings(plan, source.pk, version.pk)
        services._apply_plan_children(plan, cleaned, actor, version=version)
        for field in ("code", "name", "description", "account_type_ids", "eligibility"):
            if field in cleaned:
                setattr(plan, field, cleaned[field])
        plan.save()
        services._audit(
            actor,
            "plan.version_saved",
            "rate_plan",
            plan.id,
            after={"version_no": number, "effective_from": start.isoformat(), "reason": reason},
        )
        if payload.get("publish"):
            _publish(actor, plan, version, before=before)
    return _plan_dict(plan_id)


def _lock_now() -> None:
    """Check the DEFERRED overlap lock NOW, inside a savepoint (law 14), so a
    collision is refused by name instead of failing at COMMIT."""
    if connection.vendor != "postgresql":
        return
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ex_plan_versions_no_overlap IMMEDIATE")
                cursor.execute("SET CONSTRAINTS ex_plan_versions_no_overlap DEFERRED")
    except IntegrityError:
        raise _refusal("effective_from", "rating.plans.versions_overlap") from None


def _publish(actor: Any, plan: Any, version: Any, before: Any = None) -> None:
    start = version.effective_from
    # `DEF-RAT-10029` — the plan as it read on `start` BEFORE this version, for
    # the History row's `before`. Taken first, while the version is still a
    # draft (a draft prices nothing, so the read sees the one it replaces) and
    # before the version in force is ended. The row used to store
    # `before=None`, so History listed every fact of the plan as changed
    # (*"… and 89 more"*) under a reason that named one of them.
    # `new_version` passes the plan as it read BEFORE its own writes, because
    # the plan-level facts it changes (name, customer classes) are not
    # versioned and would already read as the new values here.
    if before is None:
        with plan_versioning.pricing_day(start):
            before = services._plan_snapshot(plan.id)
    current = _check_start(plan, start, exclude=version.pk)
    if current is not None and current.effective_from is not None:
        if current.effective_to is None or current.effective_to >= start:
            models.PlanVersion.objects.filter(pk=current.pk).update(effective_to=start - timedelta(days=1))
    elif current is not None and current.effective_from is None:
        # A dateless head (`DEF-438`) is given the plan's own start before it
        # ends, so its window is a real one.
        models.PlanVersion.objects.filter(pk=current.pk).update(
            effective_from=plan.effective_from, effective_to=start - timedelta(days=1)
        )
    with plan_versioning.pricing_day(start):
        models.PlanVersion.objects.filter(pk=version.pk).update(status=plan_versioning.VERSION_PUBLISHED)
    # The newest start is the HEAD; the plan's term columns mirror it, its
    # counter reads its number, and the plan's overall window ends where it does.
    version.refresh_from_db()
    models.RatePlan.objects.filter(pk=plan.pk).update(
        head_version_id=version.pk,
        version=version.version_no,
        effective_to=version.effective_to,
        minimum_bill_amount=version.minimum_bill_amount,
        outside_city_factor=version.outside_city_factor,
        budget_billing=version.budget_billing,
        late_fee_charge_id=version.late_fee_charge_id,
    )
    _lock_now()
    # `DEF-RAT-10029` — the History row's `after` is read once the plan's term
    # columns mirror THIS version (above).
    with plan_versioning.pricing_day(start):
        after = services._plan_snapshot(plan.id)
    # `DEF-RAT-10031`, PO 2026-10-09 option (b), verbatim: *"yes - old changes
    # are not required (b) Fix it going forward only - this is okay"*. The
    # version's stored copy is the SAME read, taken after the mirror, so v2 with
    # a $12.00 minimum stores $12.00 (it stored the $10.00 it replaced: the read
    # was taken before the mirror). `TERMS_RECORDED_KEY` marks a copy written
    # this way; copies already on disk are NOT rewritten, and the Versions table
    # says so beside them (`plan_reads.version_terms_recorded`).
    models.PlanVersion.objects.filter(pk=version.pk).update(
        snapshot={**after, plan_versioning.TERMS_RECORDED_KEY: True}
    )
    models.RateChangeLog.objects.create(
        tenant_id=plan.tenant_id,
        entity_type="plan",
        entity_id=plan.id,
        before=before,
        after=after,
        reason=version.change_reason or "",
        actor_id=services._actor_user_id(actor),
    )
    services._audit(
        actor,
        "plan.version_published",
        "rate_plan",
        plan.id,
        after={
            "version_no": version.version_no,
            "effective_from": start.isoformat(),
            "effective_to": version.effective_to.isoformat() if version.effective_to else None,
            "reason": version.change_reason,
        },
    )


def publish_version(actor: Any, plan_id: Any, version_no: Any) -> dict[str, Any]:
    with transaction.atomic():
        plan = selectors.plan_or_404(plan_id)
        # `DEF-RAT-9510`: a DRAFT plan's own v1 is a draft version row too, and
        # this door would have tried to publish it with the plan left a draft
        # (on the tip it failed the version-window lock instead). A draft plan
        # is published as a whole, by *Publish plan* (`POST /plans/{id}/publish`)
        # — refused by the key `new_version` already uses for the same mistake.
        if plan.status != services.PLAN_PUBLISHED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1066",
                message_key="rating.plans.version_of_draft",
                params={"name": plan.name},
            )
        version = models.PlanVersion.objects.filter(
            rate_plan=plan, version_no=version_no, status=plan_versioning.VERSION_DRAFT
        ).first()
        if version is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-RAT-1066",
                message_key="rating.plans.no_version_to_publish",
                params={"name": plan.name, "version": version_no},
            )
        _publish(actor, plan, version)
    return _plan_dict(plan_id)


# ── POST /plans/{id}/duplicate (`DEF-RAT-9352`, image 25) ───────────────────

#: The binding tables a duplicate copies from the version in force, in the
#: order `_copy_bindings` writes them.
_DUPLICATED_BINDINGS = (
    models.PlanService,
    models.PlanRateSchedule,
    models.PlanChargeRule,
    models.PlanTaxRule,
    discount_models.PlanDiscountRule,
)


def duplicate(actor: Any, plan_id: Any, payload: Any) -> dict[str, Any]:
    """*Duplicate* on the details page's More ▾ (image 25) — a NEW DRAFT plan
    that offers what the source offers TODAY, under a new name and code.

    ── WHAT IS COPIED, AND FROM WHERE (our judgment, decision log 2026-10-03
    *"CR-167 FOLLOW-UP · DUPLICATE A PLAN …"*) ─────────────────────────────────
    The source's version IN FORCE on the utility's today (`version_on`) — not
    the head, which may be a version that starts next year, and not a draft new
    version nobody has published. From it: the services, their rate schedules,
    the charge codes (late fee and deposits included — they are charge-code
    rows), the taxes, the discounts still offered (a binding whose offer has
    already ended is history, not an offer), and the four terms (minimum bill,
    outside-city surcharge, budget billing, the late-fee code). From the plan:
    description, customer classes, sub-class and the notes. The legacy
    per-class deposit amounts and penalty rule travel too, so the copy prices a
    deposit exactly as the source does.

    ── WHAT IS NEVER COPIED ─────────────────────────────────────────────────
    **Units** (a unit is moved to a plan on purpose, never by a copy),
    **history** (versions, audit, corrections — the copy is v1 of a new plan),
    and **dates** (a new plan's window is chosen when it is published; the
    source's would put the copy's v1 over a past the copy never priced).

    ── WHY A DRAFT ──────────────────────────────────────────────────────────
    Nothing is billable until a human publishes it (`BR-RAT-030`), so every
    guard that stands between a plan and being in force still stands between
    the copy and being in force. The source is read and not one of its rows is
    written — the same posture `services.duplicate_rate_schedule` records.

    `name` and `code` are REQUIRED and must be free; the refusals are
    `create_plan`'s own (`rating.plans.duplicate_name` / `duplicate_code`) on
    the fields `name` and `code`.
    """
    body = payload if isinstance(payload, dict) else {}
    fe: list[dict[str, Any]] = []
    for key in body:
        if key not in ("name", "code"):
            fe.append(_fe(key, "rating.unknown_field", errors.VAL_FORMAT))
    for key in ("name", "code"):
        if _empty(body.get(key)):
            fe.append(_fe(key, "rating.required", errors.VAL_REQUIRED))
    _refuse(fe)
    with transaction.atomic():
        source = selectors.plan_or_404(plan_id)
        today = seams.tenant_today()
        # `DEF-RAT-9516` — a plan that has not started yet is copied from the
        # version it will START with (never the newest, which `version_on`'s
        # head fallback would give): the plan READS' own rule.
        from apps.rating import plan_reads

        version = plan_versioning.version_on(source.pk, plan_reads._read_day(source.pk, today))
        terms: Any = version if version is not None else source
        legacy: dict[str, Any] = {
            "name": str(body["name"]).strip(),
            "code": str(body["code"]).strip(),
            "description": source.description,
            "account_type_ids": [str(one) for one in (source.account_type_ids or [])],
            "eligibility": source.eligibility or {},
            "budget_billing": bool(terms.budget_billing),
            "late_fee_charge": str(terms.late_fee_charge_id) if terms.late_fee_charge_id else None,
        }
        if source.account_subtype_id:
            legacy["account_subtype_id"] = str(source.account_subtype_id)
        if terms.minimum_bill_amount is not None:
            legacy["minimum_bill_amount"] = str(terms.minimum_bill_amount)
        if terms.outside_city_factor is not None:
            legacy["outside_city_factor"] = str(terms.outside_city_factor)
        created = services.create_plan(actor, legacy)
        copy = models.RatePlan.objects.get(pk=created["id"])
        head = plan_versioning.ensure_head(copy)
        if version is not None:
            for model in _DUPLICATED_BINDINGS:
                rows = model.all_versions.filter(rate_plan=source, plan_version_id=version.pk)
                if model is discount_models.PlanDiscountRule:
                    rows = rows.filter(Q(available_to__isnull=True) | Q(available_to__gte=today))
                for row in rows:
                    row.pk = None
                    row.id = None
                    row.rate_plan_id = copy.pk
                    row.plan_version_id = head
                    row._state.adding = True
                    row.save()
        for model in (models.PlanDepositRule, models.PlanPenaltyRule):
            for row in model.objects.filter(rate_plan=source):
                row.pk = None
                row.id = None
                row.rate_plan_id = copy.pk
                row._state.adding = True
                row.save()
        services._audit(
            actor,
            "plan.duplicated",
            "rate_plan",
            copy.pk,
            after={
                "duplicated_from": {"code": source.code, "name": source.name},
                "version_no": version.version_no if version is not None else None,
            },
        )
    return _plan_dict(copy.pk)


# ── POST /plans/{id}/corrections ─────────────────────────────────────────────


def correct(actor: Any, plan_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """*Fix a mistake* with the contract body — same number, same dates."""
    plan = selectors.plan_or_404(plan_id)
    content = {key: value for key, value in payload.items() if key not in ("version", "reason")}
    legacy, fe = translate(content, plan)
    _refuse(fe)
    for key in ("effective_from", "effective_to"):
        legacy.pop(key, None)
    legacy["reason"] = payload.get("reason")
    if "version" in payload:
        legacy["version"] = payload["version"]
    try:
        result = services.correct_plan_version(actor, plan_id, legacy)
    except errors.ValidationError as exc:
        raise _rename(exc) from None
    body = _plan_dict(plan_id)
    body["issued_bills_unchanged"] = result.get("issued_bills_unchanged", True)
    return body
