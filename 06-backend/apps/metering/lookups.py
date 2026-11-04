# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 card grid) · US-TEN-010 (per-list add / edit) ·
#           US-TEN-011 (deactivate / delete lock) · US-MET-001 (BR-MET-034
#           premises types are Reference data)   Screens: S8, S16
# Change:   CR-010 item 2 (PO 2026-08-17: *"why no screen"*) — DEF-236
# Rules:    BR-MET-034 (seeded + tenant-extensible) · BR-TEN-029/030/031/034/036
#           (used-by live, code immutable once used, owner validates, seeded
#           rows never deletable)
# Tests:    06-backend/tests/test_def_236_premises_types_card.py
# Impacts:  apps.tenancy /lookups/premises_types endpoint · the S8 card ·
#           reference_data_report() (the list leaves the `uncounted` state)
# ───────────────────────────────────────────────────────
"""The /lookups handlers for `premises_types` (DEF-236's fix) and, since
CR-010 A-4 (PO 2026-08-17: *"this is correct"*, 2026-08-18 build), for
`unit_types` — the second half of r10 SET-04's "Premise & unit types" card
pair (BR-MET-084).

THE GAP THIS CLOSES, BECAUSE IT IS THE WHOLE REASON THE FILE EXISTS. From
2026-08-10 this list was seeded into every tenant (5 rows, BR-MET-034), the
S16 premises wizard REQUIRED one of its rows, and no screen anywhere could
show, add, rename or deactivate one — the only reference list in the product
with rows and no door. The DEF-026 lane that seeded it reported the missing
handler accurately, in a docstring, and in no register; nothing came back to
it for seven days (hard-won law 1: a comment is a note, never a plan). A
utility whose vocabulary needs "Farm" or "Church" simply could not have it.

The handler is the BR-TEN-031 duck-typed contract (search · count · get ·
serialize · used_by · create · update · set_active · delete), the same shape
apps/assets/lookups.py and apps/customers/lookups.py already register, served
through tenancy's existing `/lookups/{list}` routes — no new endpoint, no new
screen frame, one card entry in the frontend config.

`used_by` counts premises referencing the row, so BR-TEN-030 (code frozen once
used) and BR-TEN-034 (a referenced row is not deletable) are live from day
one — the FK is PROTECT, so the database enforces the same law.
"""

import logging
from typing import Any

from django.db.models import Q

from apps.metering import models
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.metering")


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


class PremisesTypeLookupHandler:
    """/lookups/premises_types — BR-MET-034's flat code + name list, plus
    `CR-162-BRC10`'s *Account type* — master or regular — per row."""

    model = models.PremisesType
    #: `CR-162-BRC10` — the premises-type list carries the ACCOUNT TYPE every
    #: account-creation door reads. Its sibling `UnitTypeLookupHandler` does not.
    account_kind_field = True

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
        return {
            "id": str(row.pk),
            "code": row.code,
            "name": row.name,
            "active": row.active,
            "is_system": row.is_system,
            "used_by": self.used_by(row),
            **({"account_kind": row.account_kind} if self.account_kind_field else {}),
        }

    def used_by(self, row: Any) -> int:
        """LIVE: `premises.premises_type` is a PROTECTed FK to this table, so
        the count is real and BR-TEN-030/034 bite from the first premises."""
        return models.Premises.objects.filter(tenant_id=_tenant_id(), premises_type=row).count()

    def _validate(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        fe: list[dict[str, Any]] = []
        out: dict[str, Any] = {}
        known = {"code", "name"} | ({"account_kind"} if self.account_kind_field else set())
        for field in sorted(set(payload) - known):
            fe.append(_field_error(field, errors.VAL_FORMAT, "metering.lookups.unknown_field"))
        if self.account_kind_field:
            # `CR-162-BRC10` (PO 2026-10-02): a type a utility ADDS must name
            # the account type its premises take — required, NO default
            # (hard-won law 3: the unsafe answer is never the one you get by
            # leaving a box empty). On an edit it may be left out, but never
            # blanked: a row once answered stays answered.
            if "account_kind" in payload:
                answer = str(payload["account_kind"] or "").strip().lower()
                if answer in ("master", "regular"):
                    out["account_kind"] = answer
                else:
                    fe.append(
                        _field_error(
                            "account_kind",
                            errors.VAL_REQUIRED,
                            "metering.lookups.account_kind_required",
                        )
                    )
            elif not partial:
                fe.append(
                    _field_error(
                        "account_kind",
                        errors.VAL_REQUIRED,
                        "metering.lookups.account_kind_required",
                    )
                )
        for field in ("code", "name"):
            if field in payload:
                value = str(payload[field] or "").strip()
                if not value:
                    fe.append(_field_error(field, errors.VAL_REQUIRED, "metering.lookups.required"))
                elif len(value) > 60:
                    fe.append(
                        _field_error(field, errors.VAL_RANGE, "metering.lookups.too_long", max=60)
                    )
                else:
                    out[field] = value
            elif not partial:
                fe.append(_field_error(field, errors.VAL_REQUIRED, "metering.lookups.required"))
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
                        "metering.lookups.duplicate_code",
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
            # BR-TEN-036: seeded rows are deactivatable, NEVER deletable —
            # even at used_by = 0. The five BR-MET-034 rows are all is_system.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-036",
                message_key="metering.lookups.system_row_not_deletable",
                params={"code": row.code},
            )
        row.delete()


class UnitTypeLookupHandler(PremisesTypeLookupHandler):
    """/lookups/unit_types — BR-MET-084 (CR-010 A-4), premises types' sibling
    on the same S8 PREMISES group (r10 SET-04's one "Premise & unit types"
    surface = the group's two cards, recorded in the decision log 2026-08-18).

    Same flat code+name contract, with the ONE structural difference stated
    loud: `units.unit_type` is a TEXT code, not an FK, so there is no PROTECT
    for BR-TEN-030/034 to lean on — this handler enforces both itself:
      · `used_by` counts units carrying the row's code (case-insensitive);
      · a USED row's CODE is frozen (renaming it would strand every unit
        holding the old spelling — the drift an FK id makes impossible);
      · a USED row is not deletable; a SEEDED row never is (BR-TEN-036).
    """

    model = models.UnitType
    account_kind_field = False

    def used_by(self, row: Any) -> int:
        """LIVE over `units.unit_type` — deleted units excluded, the same
        liveness premises types get from their FK."""
        return models.Unit.objects.filter(
            tenant_id=_tenant_id(), unit_type__iexact=row.code, deleted_at__isnull=True
        ).count()

    def update(self, row: Any, payload: dict[str, Any]) -> Any:
        cleaned = self._validate(payload, partial=True)
        if "code" in cleaned and cleaned["code"].lower() != row.code.lower():
            if self.used_by(row) > 0:
                # BR-TEN-030: code frozen once used. TEXT column — a rename
                # here would orphan every unit holding the old code.
                raise errors.BizError(
                    errors.BIZ_LOCKED,
                    br_ref="BR-TEN-030",
                    message_key="metering.lookups.code_frozen_in_use",
                    params={"code": row.code, "used_by": self.used_by(row)},
                )
            self._check_duplicate(cleaned["code"], exclude_pk=row.pk)
        for field, value in cleaned.items():
            setattr(row, field, value)
        row.save(update_fields=[*cleaned.keys(), "updated_at"])
        return row

    def delete(self, row: Any) -> None:
        used = self.used_by(row)
        if used > 0:
            # BR-TEN-034: referenced → deactivate, never delete. Enforced
            # HERE because no FK will refuse it for us.
            raise errors.BizError(
                errors.BIZ_LOCKED,
                br_ref="BR-TEN-034",
                message_key="metering.lookups.row_in_use_not_deletable",
                params={"code": row.code, "used_by": used},
            )
        super().delete(row)


def register() -> None:
    """Called from AppConfig.ready(). tenancy's registry raises KeyError for a
    list code it does not declare — logged and skipped so a registry that has
    not landed the list cannot break startup (skip-until-wired). `premises_
    types` HAS been declared since DEF-026 (2026-08-10); the missing half was
    this call. `unit_types` joins it with CR-010 A-4 (2026-08-18)."""
    from apps.tenancy import services as tenancy_services

    for list_code, handler in (
        ("premises_types", PremisesTypeLookupHandler()),
        ("unit_types", UnitTypeLookupHandler()),
    ):
        try:
            tenancy_services.register_lookup_handler(list_code, handler)
        except KeyError:  # pragma: no cover — the registry declares both today
            logger.warning(
                "tenancy LOOKUP_LISTS has no %r entry — handler not registered", list_code
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 item 2 / DEF-236 (PO 2026-08-17: "why no screen")
# generated: 2026-08-17 by the CR-010 seeding lane
# checklist: A✔ B✔ C✔ D=deferred(served through tenancy's /lookups endpoints — the established shape) E✔(one card entry in referenceDataConfig.ts) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see tests/test_def_236_premises_types_card.py + the frontend card pin
# exceptions: none — the list this handler serves was already seeded, already declared and already routed; this file is the missing quarter of DEF-026's fix
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
