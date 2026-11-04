# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 (types) · US-WRK-008 (priorities + SLA) · US-WRK-009
#           (skills, safety kits, parts categories) · US-WRK-012 (the four
#           Settings cards stop saying "arrives with Work").  Screen: Work-018
# Rules:    BR-SHL-035 (a Reference-data card is DATA — the SAME management
#           view, never a new layout) · BR-TEN-031 (tenancy renders and routes;
#           the OWNING module validates and writes — this file is Work's half)
#           · BR-TEN-029 (used-by counts are LIVE) · BR-TEN-030 (a code freezes
#           once used) · BR-TEN-034 (a used row cannot be deleted) ·
#           BR-TEN-036 (a SEEDED row is deactivatable, never deletable) ·
#           BR-WRK-017 · BR-WRK-018 · B14 rule 33 (a refusal is five or six
#           words) · CLAUDE.md hard rule 1 (every read filtered by the tenant
#           in context) · hard rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_wrk_007_types.py ·
#           tests/test_us_wrk_008_priorities.py · tests/test_us_wrk_009_lookups.py
# Impacts:  apps/tenancy/services.LOOKUP_LISTS (five new codes) ·
#           apps/work/apps.py `ready()` (registers these) ·
#           07-frontend/src/features/tenancy/referenceDataConfig.ts (the cards)
# ───────────────────────────────────────────────────────
"""The five `/lookups/{list}` handlers Work owns — Settings → Reference data.

FIFTEEN HANDLERS WERE NOT WRITTEN, AND THAT WAS THE FIRST DECISION OF THIS WAVE
------------------------------------------------------------------------------
`07-endpoints.md` §2 counts **21** phase-1 reference-data endpoints — three per
simple lookup (`GET · POST /work/types`, `PATCH /work/types/{id}` and so on
five times over) — and then asks, in its own margin, whether `BR-SHL-035`'s
generic reference-data routes can serve the cards instead. **They can, and they
do.** `GET|POST /lookups/{list}`, `PATCH /lookups/{list}/{id}`,
`…/deactivate` and `DELETE` already exist, already carry the A4 role gate
(`SettingsReadAnyWriteSystemAdmin`), the ETag, the pagination, the audit row
and the ONE add/edit modal every other card in this product uses. Fifteen
handlers would have been fifteen copies of that, and the shipped screen would
have looked *different* from every other Reference-data card — which is the
one thing `BR-SHL-035` exists to prevent.

**So five of the six lists are served by the generic routes and this file is
what the framework calls.** Only `parts` has routes of its own
(`apps/work/api.py`), because the register carries five columns of its own —
part number, description, category, unit, unit cost — and the generic card
renders code, name and ONE detail. Endpoints: **21 → 4** (`GET · POST
/work/parts`, `GET · PATCH /work/parts/{id}`).

THE `_text` TWIN, AND WHY A UNIT IS THE SERVER'S JOB
----------------------------------------------------
The generic card draws exactly one detail column and its add/edit modal edits
it as one text box (`SettingsReferenceData.tsx`). Two of these lists have a
detail that is not a plain string — an SLA in HOURS and a kit's CONTENTS — so
each serializes a **twin**: the value (`sla_hours` as an integer, `items` as a
list) and its display/edit form (`sla_hours_text` = `"4 h"`, `items_text` =
`"Harness, Gas monitor, Tripod"`). The card names the `_text` key and the rest
of the product reads the value.

The unit is in the `_text` key rather than added by the screen for CLAUDE.md
hard rule 3's reason: *4* is not an answer to *"what is the SLA"*, *4 h* is —
and putting the "h" in the front end would put it in eleven catalogues and
three screens, where the first divergence is a silent one.

WHAT `used_by` HONESTLY COUNTS TODAY
------------------------------------
`BR-TEN-029` wants a LIVE count, and a wrong one is worse than none: the count
is what freezes a code (`BR-TEN-030`) and what locks a delete (`BR-TEN-034`).

  * **types** — live: `work_orders.type_id` (the column `metering/0045` adds),
    read through the seam, never through metering's model.
  * **priorities** — live: `work_order_types.default_priority_id`. The other
    reference (`work_orders.priority_id`) is wave G's column and joins the
    count in the commit that creates it.
  * **skills · safety kits** — **0 BY CONSTRUCTION, not by guess.** Nothing in
    the schema points at either table yet: `work_order_templates.skill` is free
    TEXT and NULL on all 24 seeded rows, and `skill_id` arrives with
    `US-WRK-013` (wave D). The same honest reading `HostedFlatLookupHandler.
    used_by` documents, and it changes the day the FK lands.
  * **parts categories** — live: `parts.category_id`, this module's own.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError
from django.db.models import Q

from apps.work import models
from apps.work.seams import metering_seam
from core import errors
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]]) -> None:
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            params=field_errors[0]["params"],
            field_errors=field_errors,
        )


class _BaseHandler:
    """The BR-TEN-031 duck-typed contract, in the shape `apps/assets/lookups.py`
    already established: search · count · get · serialize · used_by · create ·
    update · set_active · delete. Kept deliberately parallel to that file so
    the two read as one pattern rather than two."""

    model: Any = None
    list_code: str = ""
    #: The ONE extra key this card's detail column names, or "" for a flat list.
    detail_key: str = ""

    # ── reads ───────────────────────────────────────────────────────────
    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id())

    def search(self, q: str | None) -> Any:
        qs = self._qs().order_by("code", "id")  # IS-2 stable secondary sort
        if q and len(q.strip()) >= 2:  # IS-3 server-side, min 2 chars
            term = q.strip()
            qs = qs.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return qs

    def count(self) -> int:
        return self._qs().count()

    def get(self, entry_id: Any) -> Any:
        return self._qs().filter(pk=entry_id).first()

    def used_by(self, row: Any) -> int:
        return 0

    def detail(self, row: Any) -> dict[str, Any]:
        """This list's own keys, beyond code/name/active. `{}` for a flat one."""
        return {}

    def serialize(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
            **self.detail(row),
        }

    # ── validation ──────────────────────────────────────────────────────
    def _allowed_fields(self) -> set[str]:
        return {"code", "name"}

    def _validate_detail(
        self, payload: dict[str, Any], *, partial: bool, fe: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {}

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        out: dict[str, Any] = {}
        for field in sorted(set(payload) - self._allowed_fields()):
            fe.append(_field_error(field, errors.VAL_FORMAT, "work.lookups.unknown_field"))
        for field in ("code", "name"):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_field_error(field, errors.VAL_REQUIRED, "work.lookups.required"))
                elif len(value) > 60:
                    fe.append(
                        _field_error(field, errors.VAL_RANGE, "work.lookups.too_long", max=60)
                    )
                else:
                    out[field] = value
            elif not partial:
                fe.append(_field_error(field, errors.VAL_REQUIRED, "work.lookups.required"))
        out.update(self._validate_detail(payload, partial=partial, fe=fe))
        _refuse(fe)
        return out

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:  # BR-TEN-030, US-WRK-007 TC-3
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "work.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    # ── writes ──────────────────────────────────────────────────────────
    def _defaults_for_create(self) -> dict[str, Any]:
        return {}

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return self.model.objects.create(
            tenant_id=_tenant_id(),
            is_system=False,
            active=True,
            **{**self._defaults_for_create(), **cleaned},
        )

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def set_active(self, row: Any, active: bool) -> Any:
        row.active = active
        row.save(update_fields=["active", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        if row.is_system:
            # BR-TEN-036 — a seeded row is part of the vocabulary every tenant
            # shares. Deactivate it; never delete it. (US-WRK-007 TC-4's
            # sibling: a row that is USED is refused by tenancy's own
            # delete-lock, which reads `used_by` above.)
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="work.lookups.system_row_not_deletable",
                params={"code": row.code},
            )
        row.delete()

    # ── seeding (reached through apps.work.services.seed_reference_list) ──
    def seed(self, tenant_id: Any, entries: list[dict[str, Any]]) -> int:
        """Insert-missing only, `is_system=True` — the conservative reading of
        BR-TEN-012 every other seeder in this product uses: no touch-tracking
        column exists, so an existing row is NEVER overwritten."""
        created = 0
        for entry in entries:
            code = str(entry.get("code", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not code or not name:
                raise errors.SysError(
                    errors.SYS_INTERNAL,
                    message_key="signup.reference_fixture_invalid",
                    params={"reason": f"{self.list_code} entry missing code/name"},
                )
            if self.model.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
                continue
            self.model.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=name,
                is_system=True,
                active=True,
                **self._seed_extra(tenant_id, entry),
            )
            created += 1
        return created

    def _seed_extra(self, tenant_id: Any, entry: dict[str, Any]) -> dict[str, Any]:
        return {}


class WorkSkillLookupHandler(_BaseHandler):
    """`/lookups/work_skills` — what a job needs a person to be able to do."""

    model = models.WorkSkill
    list_code = "work_skills"


class PartCategoryLookupHandler(_BaseHandler):
    """`/lookups/work_parts_categories` — how the parts register groups itself.

    ⚠ **THE LIST CODE IS NOT THE TABLE NAME, AND THAT IS DELIBERATE.** The card
    has been on the Settings grid since 2026-08-16 as `work_parts_categories`,
    and its label, its sample copy and its eleven catalogue keys are all keyed
    on that string. Renaming the card to match `part_categories` would move
    twenty-two catalogue entries to rename a thing nobody sees, on a wave whose
    whole job is to make the card WORK. The table keeps the field map's name.
    """

    model = models.PartCategory
    list_code = "work_parts_categories"

    def used_by(self, row: Any) -> int:
        return models.Part.objects.filter(tenant_id=_tenant_id(), category=row).count()


class WorkHoldReasonLookupHandler(_BaseHandler):
    """`/lookups/work_hold_reasons` — why a job came off the run (`CR-168-BRC10`
    P0.4, judgment J1).

    A new reason takes the next free `rank`, the `work_priorities` posture.
    A reason in use is DEACTIVATED, never deleted: `work_orders.hold_reason_id`
    is PROTECT, and *used by* counts the jobs that name it.
    """

    model = models.WorkHoldReason
    list_code = "work_hold_reasons"

    def used_by(self, row: Any) -> int:
        from apps.work.seams import metering_seam

        return metering_seam.orders_held_for(row.id)

    def _defaults_for_create(self) -> dict[str, Any]:
        highest = self._qs().order_by("-rank").values_list("rank", flat=True).first()
        return {"rank": (highest or 0) + 1}

    def _seed_extra(self, tenant_id: Any, entry: dict[str, Any]) -> dict[str, Any]:
        return {"rank": int(entry.get("rank") or 0)}


class WorkSafetyKitLookupHandler(_BaseHandler):
    """`/lookups/work_safety_kits` — the kit a job's safety step asks for.

    `items_text` is the card's detail column and its edit box: one line,
    comma-separated. `items` is the list underneath, which is what the template
    builder's safety step reads (wave E).
    """

    model = models.WorkSafetyKit
    list_code = "work_safety_kits"
    detail_key = "items_text"

    def detail(self, row: Any) -> dict[str, Any]:
        items = list(row.items or [])
        return {"items": items, "items_text": ", ".join(items)}

    def _allowed_fields(self) -> set[str]:
        return {"code", "name", "items_text"}

    def _validate_detail(
        self, payload: dict[str, Any], *, partial: bool, fe: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if "items_text" not in payload:
            return {}
        raw = str(payload.get("items_text") or "")
        items = [part.strip() for part in raw.split(",") if part.strip()]
        if len(items) > 20:
            fe.append(
                _field_error("items_text", errors.VAL_RANGE, "work.lookups.too_many_items", max=20)
            )
            return {}
        return {"items": items}

    def _seed_extra(self, tenant_id: Any, entry: dict[str, Any]) -> dict[str, Any]:
        items = entry.get("items") or []
        return {"items": [str(item).strip() for item in items if str(item).strip()]}


class WorkPriorityLookupHandler(_BaseHandler):
    """`/lookups/work_priorities` — `BR-WRK-018`: a priority carries a PROMISE.

    The detail column is the SLA, with its unit: *Urgent · 4 h*. A new priority
    a tenant adds takes the next free `rank` (`max + 1`) and the neutral
    colour, because neither is a question the one-line add form can ask and
    both have an answer that cannot collide — `rank` is unique per tenant, so
    guessing "1" would refuse every second addition.
    """

    model = models.WorkPriority
    list_code = "work_priorities"
    detail_key = "sla_hours_text"

    def detail(self, row: Any) -> dict[str, Any]:
        return {
            "sla_hours": row.sla_hours,
            # hard rule 3 — the unit travels with the number.
            "sla_hours_text": f"{row.sla_hours} h",
            "rank": row.rank,
            "colour": row.colour,
            # CR-187-BRC10 (PO answer 9) — how an assignment at this priority
            # rings on the technician's phone. A fixed token; the card shows it
            # through `settings.reference.pushKind.<token>`.
            "push_kind": row.push_kind,
        }

    def used_by(self, row: Any) -> int:
        # LIVE. `work_orders.priority_id` is wave G's column and joins this
        # count in the commit that creates it (BR-TEN-029).
        return models.WorkOrderType.objects.filter(
            tenant_id=_tenant_id(), default_priority=row
        ).count()

    def _allowed_fields(self) -> set[str]:
        return {"code", "name", "sla_hours_text", "push_kind"}

    def _validate_detail(
        self, payload: dict[str, Any], *, partial: bool, fe: list[dict[str, Any]]
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if "push_kind" in payload:
            # CR-187-BRC10 (PO answer 9) — one of the three kinds an assignment
            # may ring with; anything else is refused by name, never coerced.
            kind = str(payload.get("push_kind") or "").strip().lower()
            if kind not in models.PRIORITY_PUSH_KINDS:
                fe.append(
                    _field_error(
                        "push_kind",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "work.priorities.push_kind_unknown",
                        allowed=", ".join(models.PRIORITY_PUSH_KINDS),
                    )
                )
            else:
                out["push_kind"] = kind
        if "sla_hours_text" not in payload:
            return out
        return {**out, **self._validate_sla(payload, fe)}

    def _validate_sla(self, payload: dict[str, Any], fe: list[dict[str, Any]]) -> dict[str, Any]:
        raw = str(payload.get("sla_hours_text") or "").strip().lower()
        for suffix in (" hours", " hour", " hrs", " hr", " h", "hours", "hour", "hrs", "hr", "h"):
            if raw.endswith(suffix):
                raw = raw[: -len(suffix)].strip()
                break
        if raw == "":
            fe.append(
                _field_error("sla_hours_text", errors.VAL_REQUIRED, "work.lookups.required")
            )
            return {}
        try:
            hours = int(raw)
        except ValueError:
            fe.append(
                _field_error("sla_hours_text", errors.VAL_FORMAT, "work.priorities.sla_not_hours")
            )
            return {}
        if hours < 0:  # US-WRK-008 TC-3
            fe.append(
                _field_error("sla_hours_text", errors.VAL_RANGE, "work.priorities.sla_negative")
            )
            return {}
        return {"sla_hours": hours}

    def _defaults_for_create(self) -> dict[str, Any]:
        highest = self._qs().order_by("-rank").values_list("rank", flat=True).first()
        return {"rank": (highest or 0) + 1, "colour": "neutral", "sla_hours": 0}

    def _seed_extra(self, tenant_id: Any, entry: dict[str, Any]) -> dict[str, Any]:
        kind = str(entry.get("push_kind") or "new_job")
        return {
            "rank": int(entry.get("rank") or 0),
            "sla_hours": int(entry.get("sla_hours") or 0),
            "colour": str(entry.get("colour") or "neutral"),
            "push_kind": kind if kind in models.PRIORITY_PUSH_KINDS else "new_job",
        }


class WorkOrderTypeLookupHandler(_BaseHandler):
    """`/lookups/work_order_types` — `BR-WRK-017`: types are a catalogue.

    The detail column is the **default priority**, by NAME. A clerk types what
    they can see on the priorities card beside it; the handler resolves it
    case-insensitively against this tenant's own priorities, by name first and
    then by code, and refuses anything else with the list of names it would
    have accepted. That is `AssetTypeLookupHandler.extra_choices`' shape with
    the choices read from a table instead of a constant — the choices here are
    the tenant's, not the platform's.

    ⚠ **`est_duration`, `customer_present` and `default_template` have no
    editor at this wave, and that is stated rather than hidden.** They are read
    by the New work order wizard, which is wave G's; `default_template` is NULL
    until wave D publishes a template to point at. The one-line add form on a
    Reference-data card can carry one detail, and inventing a second screen for
    three fields nothing reads yet would be the "built is not wired" failure
    from the other end.

    ⚠ **AND SINCE 2026-09-07 NONE OF THE THREE IS SEEDED EITHER, BECAUSE THE
    PRODUCT OWNER'S LIST STATES NAMES AND NOTHING ELSE.** The eight retired
    rows carried r10's own default priorities and durations; the nine types and
    forty-two sub-types that replace them carry no priority, no duration and no
    presence flag, because the PO supplied none and inventing *"a gas leak
    call-out is Urgent · 60 minutes"* would put a promise to a customer in a
    seed file. Every one is tenant-editable on this card; the observation is in
    the lane's report rather than resolved here.

    ── TWO LEVELS (`BR-WRK-058`, PO ruling 2026-09-07) ──────────────────────
    **A row with no parent IS a type. A row with a parent IS a sub-type.**
    `parent_code`, not `parent_id`, because this list is edited on a settings
    screen where a human types codes and `B14` rule 31 forbids a database id
    ever being a field's visible value — `AreaLookupHandler` made both choices
    first and this handler follows it rather than inventing a second posture.

    **DEPTH IS EXACTLY TWO AND IT IS ENFORCED HERE**, in the one place a parent
    is ever set, and not by a database trigger, which would be a second
    statement of the same rule and the one that drifts (hard-won law 1). Three
    refusals implement it: a parent that itself has a parent, a row pointed at
    itself, and a row that already HAS sub-types being given a parent — which
    is the third level arriving from the other direction and the one
    `_resolve_parent` cannot see.
    """

    model = models.WorkOrderType
    list_code = "work_order_types"
    detail_key = "default_priority"

    def _qs(self) -> Any:
        return self.model.objects.filter(tenant_id=_tenant_id()).select_related(
            "default_priority", "parent"
        )

    def detail(self, row: Any) -> dict[str, Any]:
        return {
            "default_priority": row.default_priority.name if row.default_priority_id else "",
            "customer_present": row.customer_present,
        }

    def serialize(self, row: Any) -> dict[str, Any]:
        """The flat keys, plus the four the hierarchical card reads.

        ⚠ **THE KEY NAMES ARE `is_sub_area` AND `sub_area_count` ON A LIST WITH
        NO AREAS IN IT, AND THAT IS THE CONTRACT RATHER THAN AN OVERSIGHT.**
        `SettingsReferenceData.tsx` states it in as many words since
        `DEF-TEN-4478`: these four are *"the SELF-PARENTED WIRE CONTRACT, not
        area vocabulary — every hierarchical handler publishes those four names
        whatever its own two levels are called, and the words a person reads
        come from the card's `hierarchical` block instead."* Publishing
        `sub_type_count` beside them would give one fact two names and hand one
        shared view N payload shapes to sniff. The NOUNS a clerk sees are the
        card's (`settings.reference.subTypeCount`, *"3 sub-types"*); the wire is
        one shape.
        """
        parent = row.parent if row.parent_id else None
        return {
            **super().serialize(row),
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "parent_code": parent.code if parent else None,
            "parent_name": parent.name if parent else None,
            # The card needs to know which rows are offerable as a PARENT, and a
            # client computing it from `parent_id is None` would be a second
            # implementation of BR-WRK-058's depth rule.
            "is_sub_area": row.parent_id is not None,
            # Always an integer, 0 included — the view hides a zero itself, and
            # a sub-type never shows a count because its own is always 0 and
            # drawing it would advertise a third level that does not exist.
            "sub_area_count": row.sub_types.count(),
        }

    def _resolve_parent(self, value: Any, *, own_pk: Any = None, tenant_id: Any = None) -> Any:
        """`BR-WRK-058`: resolve `parent_code` and enforce the two-level cap.

        `tenant_id` is passed by `seed` and by nothing else. `_qs()` scopes
        itself to the tenant IN CONTEXT, which is right for every screen call
        and is an assumption a seeder must not make: `seed` is handed its
        tenant as an argument and is the one caller that can be sure which one
        it means. (`AreaLookupHandler._resolve_parent`'s own reasoning, kept
        word for word so the two read as one pattern.)
        """
        if value in (None, ""):
            return None
        qs = self._qs() if tenant_id is None else self.model.objects.filter(tenant_id=tenant_id)
        parent = qs.filter(code__iexact=str(value).strip()).first()
        if parent is None:
            _refuse(
                [
                    _field_error(
                        "parent_code",
                        errors.VAL_UNKNOWN_LOOKUP,
                        "work.types.parent_unknown",
                        picked=str(value),
                    )
                ]
            )
        if own_pk is not None and str(parent.pk) == str(own_pk):
            _refuse([_field_error("parent_code", errors.VAL_FORMAT, "work.types.parent_self")])
        if parent.parent_id is not None:
            _refuse(
                [
                    _field_error(
                        "parent_code",
                        errors.VAL_FORMAT,
                        "work.types.parent_is_sub_type",
                        picked=parent.code,
                        picked_parent=parent.parent.code,
                    )
                ]
            )
        return parent

    def used_by(self, row: Any) -> int:
        # Through the seam, never through metering's model (BR-WRK-002/G78).
        return metering_seam.count_work_orders_of_type(row.pk)

    def _allowed_fields(self) -> set[str]:
        return {"code", "name", "default_priority"}

    def _validate_detail(
        self, payload: dict[str, Any], *, partial: bool, fe: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if "default_priority" not in payload:
            return {}
        wanted = str(payload.get("default_priority") or "").strip()
        if wanted == "":
            return {"default_priority": None}  # clearing is a real thing to do
        priorities = list(models.WorkPriority.objects.filter(tenant_id=_tenant_id()))
        match = next((p for p in priorities if p.name.lower() == wanted.lower()), None)
        if match is None:
            match = next((p for p in priorities if p.code.lower() == wanted.lower()), None)
        if match is None:
            fe.append(
                _field_error(
                    "default_priority",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "work.types.priority_unknown",
                    allowed=[p.name for p in priorities],
                )
            )
            return {}
        return {"default_priority": match}

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        # `parent_code` is handled by create/update below; hide it from the base
        # validator, which refuses every field it does not know by name.
        stripped = {k: v for k, v in payload.items() if k != "parent_code"}
        return super()._validate(stripped, partial=partial)

    def create(self, payload: dict[str, Any]) -> Any:
        row = super().create(payload)
        if "parent_code" in payload:
            row.parent = self._resolve_parent(payload["parent_code"], own_pk=row.pk)
            row.save(update_fields=["parent", "updated_at"])
        return row

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        row = super().update(row, payload)
        if "parent_code" in payload:
            new_parent = self._resolve_parent(payload["parent_code"], own_pk=row.pk)
            if new_parent is not None and row.sub_types.exists():
                # Giving a parent to a row that already HAS children would
                # create the third level from the other direction, and
                # `_resolve_parent` cannot see this one. Clearing a parent on
                # such a row is fine — it promotes it back to top level.
                _refuse(
                    [
                        _field_error(
                            "parent_code",
                            errors.VAL_FORMAT,
                            "work.types.has_sub_types",
                            count=row.sub_types.count(),
                        )
                    ]
                )
            row.parent = new_parent
            row.save(update_fields=["parent", "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        """A type with sub-types refuses deletion NAMING THEM, rather than
        letting the PROTECT FK surface as a 500. Same shape as `BR-TEN-034`'s
        used-row refusal: the person is told what is in the way."""
        children = row.sub_types.count()
        if children:
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-WRK-058",
                message_key="work.types.delete_blocked_sub_types",
                params={"code": row.code, "sub_types": children},
            )
        super().delete(row)

    def seed(self, tenant_id: Any, entries: list[dict[str, Any]]) -> int:
        """The nine types, the eighteen base sub-types, and the per-service
        sub-types for the services THIS TENANT SELLS (PO ruling 2026-09-07).

        ⚠ **THIS OVERRIDE EXISTS FOR TWO REASONS AND EITHER ONE ALONE WOULD
        REQUIRE IT.** The base `seed` reads `code` and `name` and nothing else,
        so a `parent_code` would be silently discarded and every sub-type would
        land TOP LEVEL with no error raised anywhere — which is precisely what
        happened to `areas` for a fortnight, and is why `AreaLookupHandler`
        carries the same override. And the base `seed` seeds every entry it is
        given, which would hand a water-only utility all twenty-four of the
        other services' sub-types the PO ruled it must not have.

        **THE SERVICE FILTER IS THE RULING, IN ONE LINE.** An entry with no
        `service` is for everybody — which since 2026-09-07 is the nine TYPES
        and nothing else — and an entry naming one is created only where
        `tenancy` says this tenant has that service ENABLED. *"a utility that
        picks water and gas gets the eighteen plus the four gas ones; a
        water-only utility gets exactly the eighteen and nothing else."* The
        tag is read HERE and stored NOWHERE — see the model docstring for why
        this list does not carry a `service` column.

        ⚠ **THE EIGHTEEN JOINED THE SCOPED SET ON 2026-09-07 AND NOT ONE LINE
        OF THIS METHOD MOVED.** They were unscoped, so every utility received
        them; the PO ruled *"gas onlyutility carry only gas meters"* and they
        became water's. The filter already read the tag — the tag simply
        arrived on eighteen more rows. That is what makes the counts a property
        of `models.SEED_TYPES` rather than of this function.

        ⚠ **THE ENABLEMENT ROWS DO NOT EXIST YET WHEN PROVISIONING RUNS THIS**
        (decision log 2026-09-07, *"the second reference pass"*).
        `provision_tenant` calls `_seed_reference_data` BEFORE
        `_enable_signup_services`, because the units a service points at are
        themselves seeded by the reference pass. So the first call here
        sees NO enabled service and seeds the twenty-seven common rows only;
        `apps.tenancy.services._seed_service_scoped_reference_data` runs
        immediately after enablement and this seeder — insert-missing, like
        every other — adds the service rows on the second pass.

        ⚠ **AND THAT TRAP GOT WORSE ON 2026-09-07, WHICH IS WORTH SAYING OUT
        LOUD.** While the eighteen were unscoped, a broken second pass left a
        tenant with nine types and eighteen sub-types — wrong, and plausible
        enough to ship. Now that every sub-type names a service it would leave
        a tenant with **nine types and NO SUB-TYPES AT ALL**. Louder, and just
        as invisible to every check in this repo, because nothing here reads a
        row count. So the counts are asserted end to end from
        `provision_tenant` in `test_cr070_work_order_type_levels.py`, never
        from this function.

        **TWO PASSES, AND THE ORDER IS THE WHOLE MECHANISM.** A child's parent
        must exist before the child can point at it, and the entry list has no
        guaranteed order. Pass 1 creates every parentless entry; pass 2 creates
        the children and resolves each `parent_code` through `_resolve_parent`,
        which is the SAME function the settings screen goes through — so the
        depth cap and both refusals are stated once and apply to a fixture
        exactly as they apply to a person.

        **INSERT-MISSING (`BR-TEN-012`).** A replay writes nothing, and a row
        that already exists is never re-parented: a utility that re-hung a
        sub-type under another type has made a decision, and a version bump
        re-delivering the list must not quietly undo it.
        """
        from django.db import transaction

        from apps.work.seams import tenancy_seam

        rows = [dict(entry) for entry in entries]
        wanted_services = {
            str(entry.get("service") or "").strip() for entry in rows if entry.get("service")
        }
        sells = tenancy_seam.enabled_service_codes() if wanted_services else set()
        created = 0
        for wants_parent in (False, True):
            for entry in rows:
                parent_code = str(entry.get("parent_code") or "").strip()
                if bool(parent_code) is not wants_parent:
                    continue
                service = str(entry.get("service") or "").strip()
                if service and service not in sells:
                    continue  # the ruling: only what this utility sells
                code = str(entry.get("code", "")).strip()
                name = str(entry.get("name", "")).strip()
                if not code or not name:
                    raise errors.SysError(
                        errors.SYS_INTERNAL,
                        message_key="signup.reference_fixture_invalid",
                        params={"reason": f"{self.list_code} entry missing code/name"},
                    )
                if self._already_seeded(tenant_id, code):
                    continue
                parent = (
                    self._resolve_parent(parent_code, tenant_id=tenant_id)
                    if parent_code
                    else None
                )
                # ⚠ **A SAVEPOINT, AND IT IS NOT THE TIDY OPTION — IT IS THE
                # ONLY ONE (CLAUDE.md hard-won law 14).** The `exists()` check
                # above is a read followed by a write, so a concurrent seeder or
                # a case-folding collation can still refuse the INSERT on
                # `uq_work_order_types_tenant_code_ci`. On PostgreSQL a failed
                # statement ABORTS THE WHOLE TRANSACTION: every later query
                # raises `InFailedSqlTransaction` and the twenty-six rows
                # already seeded are lost at COMMIT. A nested `atomic()` issues
                # a SAVEPOINT, so the refusal rolls back one row and the rest
                # survive. **The suite runs on in-memory SQLite, which has no
                # aborted-transaction state at all**, so the version without
                # this block passes every test on every machine and fails the
                # first time a real row is refused in production. Do not
                # "simplify" it away; `test_cr070_work_order_type_levels_pg.py`
                # proves it on real PostgreSQL.
                try:
                    with transaction.atomic():
                        self.model.objects.create(
                            tenant_id=tenant_id,
                            code=code,
                            name=name,
                            parent=parent,
                            is_system=True,
                            active=True,
                            **self._seed_extra(tenant_id, entry),
                        )
                except IntegrityError:
                    continue
                created += 1
        return created

    def _already_seeded(self, tenant_id: Any, code: str) -> bool:
        """`BR-TEN-012`'s insert-missing check, in a method of its own.

        ⚠ **IT IS A METHOD SO THAT THE SAVEPOINT ABOVE CAN BE PROVED.** The
        window this seeder has to survive is a READ-THEN-WRITE race — this
        check says no, another connection inserts the same code, and the
        INSERT is refused by `uq_work_order_types_tenant_code_ci`. That cannot
        be produced from a single test process, so
        `test_cr070_work_order_type_levels_pg.py` makes this method answer
        False and drives a real duplicate into real PostgreSQL, which is the
        same statement failing for the same reason. Without a name to patch,
        the only proof available would be *"read the code and agree"* — and
        hard-won law 14 exists because that proof was given and was wrong.
        """
        return self.model.objects.filter(tenant_id=tenant_id, code__iexact=code).exists()

    def _seed_extra(self, tenant_id: Any, entry: dict[str, Any]) -> dict[str, Any]:
        from datetime import timedelta

        priority = None
        wanted = str(entry.get("default_priority") or "").strip()
        if wanted:
            priority = models.WorkPriority.objects.filter(
                tenant_id=tenant_id, code__iexact=wanted
            ).first()
        minutes = entry.get("est_minutes")
        return {
            "default_priority": priority,
            "est_duration": None if minutes is None else timedelta(minutes=int(minutes)),
            "customer_present": bool(entry.get("customer_present")),
        }


#: The list code → handler map this module registers. One place, so
#: `apps.py`'s `ready()` and the seeder cannot disagree about what Work owns.
WORK_LOOKUP_HANDLERS: dict[str, type[_BaseHandler]] = {
    "work_order_types": WorkOrderTypeLookupHandler,
    "work_priorities": WorkPriorityLookupHandler,
    "work_skills": WorkSkillLookupHandler,
    "work_safety_kits": WorkSafetyKitLookupHandler,
    "work_parts_categories": PartCategoryLookupHandler,
    "work_hold_reasons": WorkHoldReasonLookupHandler,
}


def register() -> None:
    """Called from `WorkConfig.ready()`.

    tenancy's registry raises `KeyError` for a list code it does not declare.
    Logged and skipped rather than raised: a registry that has not landed a
    list must not break startup (the skip-until-wired law every other
    `register()` in this product follows).
    """
    import logging

    from apps.tenancy.services import register_lookup_handler

    logger = logging.getLogger("smartbillhub.work")
    for list_code, handler in WORK_LOOKUP_HANDLERS.items():
        try:
            register_lookup_handler(list_code, handler())
        except KeyError:  # pragma: no cover - defensive, per the docstring
            logger.warning("work: tenancy declares no reference list %r yet", list_code)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-007/008/009/012@81bb7e45 (EP-WRK-02) · 07-endpoints.md §2 · BR-SHL-035
# generated: 2026-09-04 by the CR-070 wave C build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path — the RLS migration is)
# gates: pytest tests/test_us_wrk_00{7,8,9}*.py · G32 (every message_key resolves) · G33 (five or six words) · G78
# exceptions: fifteen simple-lookup handlers NOT written — the generic BR-SHL-035 routes serve them (the docstring's first section; decision log 2026-09-04)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
