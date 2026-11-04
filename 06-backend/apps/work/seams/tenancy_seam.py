# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — the tenancy seam: which services the
#           utility sells, its areas and certification types, and a number
#           series row.
# Rules:    BR-WRK-002 (read-only) · BR-MET-003 (a service must be one the
#           tenant sells) · BR-TEN-035 (numbering is tenancy's) · hard rule 1
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-6 · TC-7)
# Impacts:  apps/work/selectors.py · wave C (the four reference cards)
# ───────────────────────────────────────────────────────
"""work → tenancy: the platform reads Work needs. READ ONLY.

Areas and certification types are tenancy's tables today (`tenancy/models.py`
`Area`, `CertificationType`) and stay so; Work reads them to place a job and to
watch a certification (Work-023) and writes neither. The `WO-` series is
allocated by metering's `create_work_order` through tenancy's own numbering —
this file only READS a series row for a screen.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def enabled_service_codes() -> set[str]:
    """Which services this tenant sells — tenancy's own selector, one query."""
    if _tenant_id() is None:
        return set()
    from apps.tenancy import selectors as tenancy_selectors

    return set(tenancy_selectors.enabled_service_codes())


def areas() -> list[dict[str, Any]]:
    """The tenant's areas, for placing a job (Work-007's Area filter, wave G)."""
    from apps.tenancy import models as tenancy_models

    rows = tenancy_models.Area.objects.filter(tenant_id=_tenant_id()).order_by("code")
    return [{"id": str(row.id), "code": row.code, "name": row.name} for row in rows]


def validate_custom_answers(
    entity: str, submitted: Any, *, screen: str | None, existing: Any = None
) -> dict[str, Any]:
    """CR-161-BRC10 W4 — tenancy's ONE custom-field validator, called by name.

    A READ (the tenant's definitions) plus pure validation; it writes nothing,
    so it sits in this read-only seam. `screen` is the slot the door's form is
    (`WORK_EDIT` for Work-021), so a required field binds only where it is
    typed in; `existing` makes it an edit and returns the merged blob.
    """
    from apps.tenancy import services as tenancy_services

    return tenancy_services.validate_custom_data_for(
        entity, submitted, screen=screen, existing=existing
    )


def certification_types() -> list[dict[str, Any]]:
    """The tenant's certification types (Work-023's watch, wave F)."""
    from apps.tenancy import models as tenancy_models

    rows = tenancy_models.CertificationType.objects.filter(tenant_id=_tenant_id()).order_by("code")
    return [{"id": str(row.id), "code": row.code, "name": row.name} for row in rows]


def number_series_row(series: str) -> dict[str, Any] | None:
    """One number series row (`work_order` · `WO-{0000}` · next), for a screen."""
    from apps.tenancy import models as tenancy_models

    row = tenancy_models.NumberSeries.objects.filter(tenant_id=_tenant_id(), series=series).first()
    if row is None:
        return None
    return {"series": row.series, "format": row.format, "next_number": row.next_number}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01)
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_005_module.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def tenant_timezone() -> Any:
    """The tenant's own zone (`ZoneInfo`), by tenancy's own read — so a calendar
    day a clerk picked (*due 05-Sep*) is anchored in THEIR day, not the server's
    (`DEF-CUS-6363`: `05-Sep` saved as `04-Sep` when read as midnight UTC)."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_timezone()


def tenant_slug() -> str | None:
    """The tenant-in-context's URL segment (`brazosbend`) — so a server answer
    can carry a SAME-ORIGIN API path (`/api/brazosbend/…`) a browser may draw an
    image from (`DEF-WRK-9594`: the page policy refuses a storage host). READ."""
    from apps.tenancy import models as tenancy_models

    row = tenancy_models.Tenant.objects.filter(pk=_tenant_id()).only("subdomain").first()
    return row.subdomain if row is not None else None



def utility_masthead() -> dict[str, Any]:
    """`{name, support_phone}` — the utility's own name (trading name first) and
    the number a printed work order carries. READ ONLY, tenancy's published
    `company_profile` (`CR-168-BRC10` P6.3, lane SRV-5)."""
    from apps.tenancy import selectors as tenancy_selectors

    try:
        profile = tenancy_selectors.company_profile()
    except Exception:  # noqa: BLE001 — a page prints without a masthead
        return {"name": None, "support_phone": None}
    return {
        "name": profile.get("dba_name") or profile.get("legal_name"),
        "support_phone": profile.get("support_phone"),
    }


def holidays_between(start: Any, end: Any) -> dict[Any, str]:
    """`{date: label}` for the utility's holidays from `start` to `end`
    inclusive (`tenancy.HolidayCalendar`, BR-TEN-039) — the phone's week greys
    them (`CR-193-BRC10`, MQ-040 step 1). READ ONLY."""
    from apps.tenancy import models as tenancy_models

    rows = tenancy_models.HolidayCalendar.objects.filter(
        tenant_id=_tenant_id(), holiday_date__gte=start, holiday_date__lte=end
    ).values_list("holiday_date", "label")
    return {day: label for day, label in rows}
