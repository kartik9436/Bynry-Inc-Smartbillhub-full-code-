# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (BR-AST-031 lifecycle stages / BR-AST-004 types are
#           Reference data, tenant-renamable and extensible) · US-TEN-009 (the
#           S8 card grid — "Meter types 5", TC-1) · US-TEN-010 (per-list add /
#           edit) · US-TEN-011 (deactivate / delete lock)   Screens: S8, S49
# Rules:    BR-AST-031 (every stage maps to a behavior class so filters and
#           billing logic stay sound regardless of tenant labels; seeded rows
#           is_system — deactivatable, never deletable) · BR-AST-004/009/042
#           (type set + tab partition) · BR-AST-043 (meter_types + read_methods
#           are two separate seeded, tenant-extensible lists) · BR-AST-044
#           (assets reference meter_types — the used-by count, and with it the
#           code-immutable and delete-lock rules, go LIVE for that card) ·
#           BR-TEN-029/030/031/034/036 (used-by live, code immutable once used,
#           owner validates, delete audit-lock)
# Tests:    06-backend/tests/test_us_ast_001_003_registry.py
# Impacts:  apps.tenancy /lookups/{list} endpoints (asset_types · asset_statuses
#           · meter_types; read_methods once tenancy declares the list)
# ───────────────────────────────────────────────────────
"""The /lookups handlers this module owns (BR-TEN-031 duck-typed contract:
search · count · get · serialize · used_by · create · update · set_active ·
delete). Content validation lives HERE — the owning module's law.

A seeded (is_system) row may be deactivated but never deleted (BR-TEN-036),
and a behavior class is REQUIRED on every stage: transitions and list filters
key off the class, so a stage without one would silently break BR-AST-020.
"""

import logging
from typing import Any

from django.db.models import Q

from apps.assets import models, services
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.assets")

BEHAVIOR_CLASSES = (
    services.STAGE_AVAILABLE,
    services.STAGE_IN_SERVICE,
    services.STAGE_OUT_OF_SERVICE,
    services.STAGE_TERMINAL,
)
CATEGORIES = (services.TAB_METERS, services.TAB_SUB_METERS, services.TAB_BTM)


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
    model: Any = None
    extra_field: str = ""
    extra_choices: tuple[str, ...] = ()

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

    def serialize(self, row: Any) -> dict[str, Any]:
        payload = {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
        }
        if self.extra_field:  # BR-AST-043 lists are flat — code + name only
            payload[self.extra_field] = getattr(row, self.extra_field)
        return payload

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        out: dict[str, Any] = {}
        allowed = {"code", "name"} | ({self.extra_field} if self.extra_field else set())
        for field in sorted(set(payload) - allowed):
            fe.append(_field_error(field, errors.VAL_FORMAT, "assets.lookups.unknown_field"))
        for field in ("code", "name"):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_field_error(field, errors.VAL_REQUIRED, "assets.lookups.required"))
                elif len(value) > 60:
                    fe.append(
                        _field_error(field, errors.VAL_RANGE, "assets.lookups.too_long", max=60)
                    )
                else:
                    out[field] = value
            elif not partial:
                fe.append(_field_error(field, errors.VAL_REQUIRED, "assets.lookups.required"))
        if self.extra_field and (self.extra_field in payload or not partial):
            value = str(payload.get(self.extra_field) or "").strip()
            if value not in self.extra_choices:
                # BR-AST-031: a stage with no behavior class (or a type with no
                # tab) would silently break transitions/filters — refuse.
                fe.append(
                    _field_error(
                        self.extra_field,
                        errors.VAL_UNKNOWN_LOOKUP,
                        "assets.lookups.bad_choice",
                        allowed=list(self.extra_choices),
                    )
                )
            else:
                out[self.extra_field] = value
        _refuse(fe)
        return out

    def _check_duplicate(self, code: str, exclude_pk: Any = None) -> None:
        qs = self._qs().filter(code__iexact=code)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        existing = qs.first()
        if existing is not None:  # BR-TEN-030: case-insensitive duplicate
            _refuse(
                [
                    _field_error(
                        "code",
                        errors.VAL_FORMAT,
                        "assets.lookups.duplicate_code",
                        existing=existing.code,
                    )
                ]
            )

    def create(self, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=False)
        self._check_duplicate(cleaned["code"])
        return self.model.objects.create(tenant_id=_tenant_id(), is_system=False, **cleaned)

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
            # BR-TEN-036 / BR-AST-031: seeded rows are deactivatable, NEVER
            # deletable — even at used_by = 0.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-AST-031",
                message_key="assets.lookups.system_row_not_deletable",
                params={"code": row.code},
            )
        row.delete()


class AssetTypeLookupHandler(_BaseHandler):
    """/lookups/asset_types — BR-AST-004/009/042 type set, tenant-extensible.
    `category` keys the S49 tab partition, so every type carries one."""

    model = models.AssetType
    extra_field = "category"
    extra_choices = CATEGORIES

    def used_by(self, row: Any) -> int:
        return models.Asset.objects.filter(tenant_id=_tenant_id(), type=row).count()


class AssetStageLookupHandler(_BaseHandler):
    """/lookups/asset_statuses — the BR-AST-031 lifecycle-stage list."""

    model = models.AssetLifecycleStage
    extra_field = "behavior_class"
    extra_choices = BEHAVIOR_CLASSES

    def used_by(self, row: Any) -> int:
        return (
            models.Asset.objects.filter(tenant_id=_tenant_id(), status=row).count()
            + models.AssetMaintenance.objects.filter(
                tenant_id=_tenant_id(), resulting_status=row
            ).count()
        )


class MeterTypeLookupHandler(_BaseHandler):
    """/lookups/meter_types — BR-AST-043: what the meter IS (seeded AMI · AMR ·
    walk-by · sub-meter · master, US-TEN-009 TC-1), tenant-extensible. A flat
    named set: the rule gives this list no tab key and no behavior class."""

    model = models.MeterType

    def used_by(self, row: Any) -> int:
        """BR-AST-044: LIVE as of the PO's 2026-08-09 ruling. This count was
        honestly 0 while no column referenced the catalog; `assets.meter_type`
        is now a PROTECTed FK (migration 0004), so the count is real and the
        two BR-TEN rules it feeds are live for meter types too — the code is
        immutable once used (BR-TEN-030, checked by tenancy's
        update_lookup_entry against this number) and a referenced row cannot be
        deleted (BR-TEN-034, plus PROTECT enforcing the same law in the DB).
        `assets.type` is still the SEPARATE asset_types FK and is deliberately
        NOT counted here — BR-AST-044 makes the two classifications
        independent."""
        return models.Asset.objects.filter(tenant_id=_tenant_id(), meter_type=row).count()


class ReadMethodLookupHandler(_BaseHandler):
    """/lookups/read_methods — BR-AST-043: how the read is COLLECTED (seeded
    AMI · AMR · walk-by · Manual · Mobile · Drive-by · Self-read · Field visit,
    the last three added 2026-08-27 by BR-MET-142), tenant-extensible. `assets.
    read_method` is a PROTECTed FK here, so used_by is a live asset count and
    the BR-TEN-034 delete-lock is also enforced by the database."""

    model = models.ReadMethod

    def used_by(self, row: Any) -> int:
        return models.Asset.objects.filter(tenant_id=_tenant_id(), read_method=row).count()


def register() -> None:
    """Called from AppConfig.ready(). tenancy's registry raises KeyError for a
    list code it does not declare — logged and skipped so a registry that has
    not landed a list cannot break startup (skip-until-wired).

    `read_methods` IS in tenancy's LOOKUP_LISTS (the one-line fix this
    docstring used to report as missing landed with the tenancy-side lanes;
    verified 2026-08-22 by the CR-028 debt sweep, D7 — all four codes resolve
    and the S8 card renders). The defensive KeyError path stays: it is the
    skip-until-wired law for any FUTURE list, not a claim about these four."""
    from apps.tenancy import services as tenancy_services

    for list_code, handler in (
        ("asset_types", AssetTypeLookupHandler()),
        ("asset_statuses", AssetStageLookupHandler()),
        ("meter_types", MeterTypeLookupHandler()),
        ("read_methods", ReadMethodLookupHandler()),
    ):
        try:
            tenancy_services.register_lookup_handler(list_code, handler)
        except KeyError:  # pragma: no cover - registry declares both today
            logger.warning(
                "tenancy LOOKUP_LISTS has no %r entry — handler not registered", list_code
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@9d8d058 (story+rules snapshot hash — EP-AST-01 registry story)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-043 reference-data gap lane — meter_types + read_methods) · AMENDED 2026-08-09 by story-coder (BR-AST-044 both-classifications lane)
# checklist: A✔ B✔ C✔ D=deferred(served through tenancy's /lookups endpoints) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ migrate-from-empty✔ makemigrations --check✔ · suite `pytest tests -m "not golden and not isolation"` 587 passed / 8 skipped (580 baseline green + the 7 new BR-AST-043 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (13 baseline + 1 new) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0003 data path exercised on a scratch file-backed sqlite DB seeded at 0002 (ami→AMI, 'AMR'→amr case-insensitively, 'na'→NULL+logged, NULL→NULL; reverse restores the codes and drops both tables) · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [BR-AST-044 lane 2026-08-09] ruff✔(E4/E7/E9/F) black✔ migrate✔ makemigrations --check✔ (hand-written 0004 matches the model state) · suite `pytest tests -m "not golden and not isolation"` 593 passed / 8 skipped (587 baseline green + 6 new BR-AST-044 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (unchanged) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy STILL NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: tenancy's LOOKUP_LISTS carries no `premises_types` or `meter_types` table-backed entry — premises types are served by metering's own endpoint and meter types have NO table at all (B2 r4 keeps read_method as a plain value); both reported, neither invented · BR-AST-043 gap lane 2026-08-09: MeterTypeLookupHandler + ReadMethodLookupHandler registered; _BaseHandler now tolerates a list with NO extra field (both new lists are flat: code + name) · meter_types.used_by is honestly 0 — nothing in the schema references that list yet; counting assets.read_method there would fake a relationship BR-AST-043 does not make · `read_methods` is NOT in tenancy's LOOKUP_LISTS (out of territory), so its handler logs the skip-until-wired warning and its S8 card cannot render until one line lands there — REPORTED · BR-AST-044 lane 2026-08-09: meter_types.used_by is LIVE — it counts assets referencing the row, so "code immutable once used" (BR-TEN-030) and "a referenced row cannot be deleted" (BR-TEN-034, plus PROTECT in the DB) now bite for meter types exactly as they do for read methods; the honest 0 it returned while nothing referenced the catalog is gone. `assets.type` is deliberately NOT counted here — BR-AST-044 keeps the two classifications independent
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
