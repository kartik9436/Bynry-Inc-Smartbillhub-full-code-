# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `assets` group, NEW 2026-09-03
#           Screens: shell chrome (the topbar popover, every authenticated screen)
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (assets are one of the nine groups;
#           ≤5; prefix-then-recency; by their B2 identifiers) · BR-SHL-006
#           (app.tenant_id + RLS FORCE; role-invisible groups omitted) ·
#           BR-AST-026 (an asset has THREE identifiers and the uuid is NEVER
#           displayed) · B14 rule 31
# Tests:    06-backend/tests/test_us_shl_003_search.py ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7)
# Impacts:  core.search registry (apps/assets/apps.py registers this) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The assets module's global-search source — a NEW group the signed rule never
contemplated, added by PO ruling 2026-09-03 (*"premises , unit assets , …"*).

⚠ **AN ASSET HAS THREE IDENTIFIERS AND EXACTLY ONE OF THEM MUST NEVER BE SHOWN
(BR-AST-026).** The model says so in its own words and this is the surface where
getting it wrong would be visible on every screen in the product:

  · `asset_no`   — OUR number, from the tenant series. What a person quotes.
  · `serial_no`  — the MANUFACTURER'S serial, off the device. Also quotable, and
                   the number a field tech reads aloud over the phone.
  · `id`         — the hidden uuid. Carried here for the deep link ONLY. It is
                   never the label and never the context line (B14 rule 31,
                   ratified as *"no Databse ID on screen - that is a rule"*).

Both quotable numbers are searched, and both are in the PREFIX band — unlike
every other group in this feature, where the identifier band holds one column.
That is deliberate: a serial is an identifier in the same sense `asset_no` is,
the ruling names both, and demoting a serial-prefix match below an `asset_no`
substring match would put the wrong meter first for the one person most likely
to be reading a serial off a device.

The model's own comment is worth repeating, because it is the trap next door:
`external_ref` is the LEGACY id from the utility's previous system and is a
THIRD thing again. It is not searched here — nobody quotes it at a counter — and
folding it in would make a column that holds either, which is the defect
`serial_no` exists to prevent.
"""

from typing import Any

from apps.assets import models
from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

# BOTH quotable numbers rank first — see the module docstring.
_ASSET_PREFIX_FIELDS = ("asset_no", "serial_no")
_ASSET_MATCH_FIELDS = ("asset_no", "serial_no")


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def search_assets(term: str, limit: int) -> list[dict[str, Any]]:
    """Assets by asset number or serial number.

    The context line names the asset TYPE ("Water meter") and, where the two
    differ, the serial — so a clerk who typed an `asset_no` still sees the
    serial they can check against the device, and one who typed a serial is not
    shown it twice (B14 rule 32's repetition clause).
    """
    qs = (
        models.Asset.objects.filter(tenant_id=_tenant_id())
        .select_related("type")
        .filter(core_search.matches_any(term, _ASSET_MATCH_FIELDS))
    )
    rows = list(core_search.prefix_then_recency(qs, term, _ASSET_PREFIX_FIELDS)[:limit])
    result: list[dict[str, Any]] = []
    for row in rows:
        parts = [row.type.name] if row.type_id and row.type is not None else []
        if row.serial_no and row.serial_no != row.asset_no:
            parts.append(row.serial_no)
        result.append(
            {
                "id": str(row.id),
                "label": row.asset_no,
                "context": " · ".join(parts) or None,
                "amount": None,
                "currency": None,
            }
        )
    return result


def register() -> None:
    """Register the assets group with the BE-08 kernel.

    Called from `AssetsConfig.ready()`. Default `visible_to` — every tenant role
    — because every read route in `apps/assets/api.py` is `AnyTenantRole` (only
    retire is `SystemAdminOnly`, and that is a write). BR-SHL-006's omission
    clause guards a future role, in the kernel.
    """
    core_search.register_search_source("assets", search_assets)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03 (BR-SHL-005 amended)
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in the same lane) F✔ G✔ H=deferred(PO)
# exceptions: `external_ref` (the legacy id) is NOT searched — reported, not
#         smuggled in: it is a third identifier with a different owner and
#         nobody quotes it at a counter
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
