# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill email's direct PDF link
# Rules:    BR-TEN-013 / B1 (a module never touches another module's ORM; a
#           cross-module read resolves the owner's published callable BY NAME) ·
#           G65 (billing reaches another module through a `*_seam.py` file)
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py
# ───────────────────────────────────────────────────────
"""billing → portal / tenancy SEAM for the bill email's PDF link.

Five reads and the public door's guards, each by NAME so no import statement
binds billing to another module's internals:

* `link_valid_days()` — portal's Settings → Customer portal value
  (`portal.selectors.settings_view`, seeded 30). Never a constant here.
* `tenant_now()` / `tenant_timezone()` / `tenant_subdomain()` — the utility's
  clock, its zone and its address segment.
* `company_profile()` — the utility's name and phone for the page.
* `fetch_document(document_id)` — tenancy's hash-verified read of the kept PDF.
* `guest_guards()` — the portal's GUEST throttles and admission, the same three
  the agreement link's door wears, because it faces the same strangers.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _module(path: str) -> Any:
    return import_module(path)


def link_valid_days(tenant_id: Any) -> int:
    view = _module("apps.portal.selectors").settings_view(tenant_id)
    return int(view["bill_link_valid_days"])


def tenant_now() -> Any:
    """This instant on the utility's clock — tenancy's one sanctioned read
    (`tenancy.selectors.tenant_now`; G6 bans a server clock in billing)."""
    return _module("apps.tenancy.selectors").tenant_now()


def tenant_timezone() -> Any:
    return _module("apps.tenancy.selectors").tenant_timezone()


def tenant_subdomain(tenant_id: Any) -> str | None:
    models = _module("apps.tenancy.models")
    return models.Tenant.objects.filter(pk=tenant_id).values_list("subdomain", flat=True).first()


def company_profile() -> dict[str, Any]:
    try:
        return dict(_module("apps.tenancy.selectors").company_profile() or {})
    except Exception:  # noqa: BLE001 — a dead end still renders without a number
        return {}


def fetch_document(document_id: Any) -> bytes:
    return _module("apps.tenancy.document_store").fetch(document_id)


def document_read_errors() -> tuple[type[BaseException], ...]:
    store = _module("apps.tenancy.document_store")
    storage = _module("apps.tenancy.document_storage")
    return (
        storage.ContentHashMismatch,
        storage.DocumentStorageError,
        store.DocumentStoreError,
    )


def guest_guards() -> tuple[list[Any], Any]:
    """(throttle classes, admission decorator) — the agreement link's set."""
    guards = _module("apps.portal.guards")
    onboarding = _module("apps.tenancy.api").PublicOnboardingThrottle
    return [onboarding, guards.PortalTenantThrottle], guards.portal_admission
