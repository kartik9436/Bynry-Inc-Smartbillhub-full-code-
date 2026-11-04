# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — the switch and the five · US-CWP-070 —
#           the portal-only branding fields. Screens: CWP-069 · CWP-070
# Rules:    CR-068 R8 · hard-won law 3 · blueprint B2 (only the strapline, the
#           chips, the hours and the emergency number are editable here — the
#           shared four are REFUSED, US-CWP-070 TC-2) · US-CWP-070 TC-5 (a
#           service the tenant does not sell is refused) · B14 rule 32 (the
#           strapline is one sentence — a length cap) · B14 rule 33 (every
#           refusal sentence is five or six words, in all eleven catalogues) ·
#           CLAUDE.md hard rule 7 (every action that changes what a customer
#           can do writes audit_log) · A4 settings_lookups (System Admin Full)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py ·
#           test_us_cwp_070_branding.py
# Impacts:  apps/portal/models.PortalSettings (the ONLY table this file
#           writes — G81 asserts it) · audit_log (`portal_settings.update`)
# ───────────────────────────────────────────────────────
"""The BACK OFFICE's write to the portal's own settings row.

⚠ THIS IS A STAFF WRITE, NOT ONE OF THE PORTAL'S FOUR (BR-CWP-001). A signed-in
System Admin changes what the utility's customers may do; the portal surface
itself cannot reach this module (it is mounted only under `backoffice_api`).
`write_points.py` names this file in `STAFF_WRITE_MODULES` so G81 allows the
write here and nowhere else outside `services.py`.

The row is created on the first save — a read never writes — and every save
writes one audit row with the before/after of exactly the fields that moved.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.portal import models, selectors
from apps.portal.seams import tenancy_seam
from core import audit, errors
from core.permissions import SYSTEM_ADMIN, require_role

_SETTINGS_FIELDS: frozenset[str] = frozenset({"is_live", *models.SWITCH_FIELDS})
#: CR-190-BRC10 — the one NUMBER this door takes (Settings → Customer portal).
AGREEMENT_LINK_DAYS = "agreement_link_valid_days"
#: DEF-BIL-10531 — the bill email link's life, the second number (same rules).
BILL_LINK_DAYS = "bill_link_valid_days"
#: Each number this door takes → its (min, max) and the refusal's key.
_DAY_FIELDS: dict[str, tuple[int, int, str]] = {
    AGREEMENT_LINK_DAYS: (
        models.AGREEMENT_LINK_DAYS_MIN,
        models.AGREEMENT_LINK_DAYS_MAX,
        "portal.settings.agreement_days_range",
    ),
    BILL_LINK_DAYS: (
        models.BILL_LINK_DAYS_MIN,
        models.BILL_LINK_DAYS_MAX,
        # The same generic sentence ("Use 1 to 90 days.") — one key, not two.
        "portal.settings.agreement_days_range",
    ),
}
_BRANDING_FIELDS: frozenset[str] = frozenset(models.BRANDING_FIELDS)
_TEXT_FIELDS: frozenset[str] = frozenset({"strapline", "office_hours_text", "emergency_phone"})


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]], message_key: str) -> None:
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key=message_key, field_errors=field_errors
        )


def _row_for_update(tenant_id: Any) -> models.PortalSettings:
    row, _created = models.PortalSettings.objects.get_or_create(tenant_id=tenant_id)
    return row


def _audit(actor: Any, tenant_id: Any, before: dict[str, Any], after: dict[str, Any]) -> None:
    if before == after:
        return
    audit.write_row(
        action="portal_settings.update",
        entity_type="portal_settings",
        entity_id=tenant_id,
        actor_user_id=getattr(actor, "id", None),
        before=before,
        after=after,
    )


@require_role(SYSTEM_ADMIN)
def save_settings(actor: Any, tenant_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
    """PUT /settings/portal — the on/off and the five switches (CWP-069).

    Any subset of the six may be sent; each must be a boolean; any other key is
    refused by name, so a client cannot smuggle a branding field, a logo or an
    address through this door.
    """
    field_errors: list[dict[str, Any]] = []
    for key, value in changes.items():
        if key in _DAY_FIELDS:
            # CR-190-BRC10 / DEF-BIL-10531 — a whole number of days within bounds.
            low, high, message_key = _DAY_FIELDS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                field_errors.append(
                    _field_error(key, errors.VAL_RANGE, message_key, min=low, max=high)
                )
        elif key not in _SETTINGS_FIELDS:
            field_errors.append(
                _field_error(key, errors.VAL_FORMAT, "portal.settings.unknown_field")
            )
        elif not isinstance(value, bool):
            field_errors.append(
                _field_error(key, errors.VAL_FORMAT, "portal.settings.switch_not_boolean")
            )
    _refuse(field_errors, "portal.settings.refused")

    with transaction.atomic():
        row = _row_for_update(tenant_id)
        before = {key: getattr(row, key) for key in changes}
        for key, value in changes.items():
            setattr(row, key, value)
        row.save(update_fields=[*changes, "updated_at"])
        after = {key: getattr(row, key) for key in changes}
        _audit(actor, tenant_id, before, after)
    return selectors.settings_view(tenant_id)


def _validate_branding(tenant_id: Any, changes: dict[str, Any]) -> list[dict[str, Any]]:
    field_errors: list[dict[str, Any]] = []
    for key, value in changes.items():
        if key not in _BRANDING_FIELDS:
            # US-CWP-070 TC-2: the logo, the names and the colours are edited
            # ONCE, in Company → Profile. Refused by name, not silently dropped.
            field_errors.append(
                _field_error(key, errors.VAL_FORMAT, "portal.branding.shared_field_refused")
            )
        elif key in _TEXT_FIELDS:
            if value is not None and not isinstance(value, str):
                field_errors.append(
                    _field_error(key, errors.VAL_FORMAT, "portal.branding.field_not_text")
                )
            elif key == "strapline" and value and len(value.strip()) > models.STRAPLINE_MAX_CHARS:
                field_errors.append(
                    _field_error(
                        key,
                        errors.VAL_RANGE,
                        "portal.branding.strapline_too_long",
                        max=models.STRAPLINE_MAX_CHARS,
                    )
                )
        elif key in ("quick_service_categories", "request_errands"):
            # US-CWP-015 — a list of `{code, label, hint, needs_bill_number}`.
            # US-CWP-060 — a list of `{code, label, hint, screen}`.
            # Refused BY SHAPE rather than trusted: one of these lists is served
            # to an anonymous visitor and the other decides where a card LINKS,
            # and a malformed row would reach a screen either way.
            if not isinstance(value, list) or not all(
                isinstance(one, dict) and str(one.get("code") or "").strip() for one in value
            ):
                field_errors.append(
                    _field_error(key, errors.VAL_FORMAT, "portal.branding.categories_not_list")
                )
            elif len({str(one["code"]) for one in value}) != len(value):
                field_errors.append(
                    _field_error(key, errors.VAL_FORMAT, "portal.branding.categories_repeat")
                )
            elif key == "request_errands" and not all(
                one.get("screen") in (None, "", *selectors.ERRAND_ROUTE) for one in value
            ):
                # ⚠ **A CARD MAY NAME ONLY A SCREEN THIS PRODUCT SERVES.** An
                # unknown `CWP-###` would render as a card with no destination
                # and no held reason — a control that neither works nor says
                # why, which is the shape `BR-CWP-056` exists to forbid. `None`
                # is the lawful way to say *this errand has no screen yet*.
                field_errors.append(
                    _field_error(key, errors.VAL_UNKNOWN_LOOKUP, "portal.branding.errand_screen_unknown")
                )
        elif key == "front_page_service_ids":
            if not isinstance(value, list) or not all(tenancy_seam.is_uuid(one) for one in value):
                field_errors.append(
                    _field_error(key, errors.VAL_FORMAT, "portal.branding.services_not_list")
                )
            else:
                # US-CWP-070 TC-5: the list is the tenant's OWN services.
                foreign = tenancy_seam.service_ids_are_the_tenants_own(
                    tenant_id, [str(one) for one in value]
                )
                if foreign:
                    field_errors.append(
                        _field_error(
                            key, errors.VAL_UNKNOWN_LOOKUP, "portal.branding.service_not_sold"
                        )
                    )
    return field_errors


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@require_role(SYSTEM_ADMIN)
def save_branding(actor: Any, tenant_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
    """PUT /settings/portal/branding — the portal-only fields (CWP-070).

    ⚠ **FIVE SINCE 2026-09-04, AND THE FIFTH HAS NO CONTROL ON THE SCREEN YET.**
    `quick_service_categories` (US-CWP-015) is saved through this door because a
    second door for one list would be a second set of rules; the editor for it
    lands with the wave that owns `CWP-069`'s content section. Stated here as an
    absence rather than left to be discovered (`12-governance/02-decision-log.md`
    2026-09-04, and the surface-debt sentence).

    *Reset to defaults* (US-CWP-070 TC-8) is this call with every portal-only
    field cleared; the shared four cannot be touched from here, so a reset
    cannot reach them either.
    """
    _refuse(_validate_branding(tenant_id, changes), "portal.branding.refused")

    with transaction.atomic():
        row = _row_for_update(tenant_id)
        before = {key: getattr(row, key) for key in changes}
        for key, value in changes.items():
            if key == "front_page_service_ids":
                setattr(row, key, [str(one) for one in value])
            elif key == "quick_service_categories":
                setattr(
                    row,
                    key,
                    [
                        {
                            "code": str(one["code"]).strip(),
                            "label": _clean_text(one.get("label")),
                            "hint": _clean_text(one.get("hint")),
                            "needs_bill_number": bool(one.get("needs_bill_number")),
                        }
                        for one in value
                    ],
                )
            elif key == "request_errands":
                # US-CWP-060 — the same normalising as the list above, on this
                # list's OWN four fields. `screen` is stored as `None` rather
                # than `""` so `request_errands` has one falsy answer to test.
                setattr(
                    row,
                    key,
                    [
                        {
                            "code": str(one["code"]).strip(),
                            "label": _clean_text(one.get("label")),
                            "hint": _clean_text(one.get("hint")),
                            "screen": _clean_text(one.get("screen")),
                        }
                        for one in value
                    ],
                )
            else:
                setattr(row, key, _clean_text(value))
        row.save(update_fields=[*changes, "updated_at"])
        after = {key: getattr(row, key) for key in changes}
        _audit(actor, tenant_id, before, after)
    return selectors.settings_view(tenant_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-069@87b94265 · US-CWP-070@87b94265 (EP-CWP-12 stories + BR-CWP snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D✔(backoffice_api.py) E✔(SettingsCustomerPortalTab.tsx) F✔ G✔ H=n/a(staff write to the portal's own row; no 🔒 path)
# gates: pytest tests/test_us_cwp_069_settings.py tests/test_us_cwp_070_branding.py · G32/G33 (every message_key here is in all eleven catalogues, five or six words) · G81 (the only write outside services.py)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
