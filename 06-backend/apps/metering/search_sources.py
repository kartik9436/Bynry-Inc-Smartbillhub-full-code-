# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (global search) — the `premises` and `units` groups
#           Screens: shell chrome (the topbar popover, every authenticated screen)
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (nine groups; ≤5 each;
#           prefix-then-recency; by their B2 identifiers — and the SIGNED field
#           list for this module is `premises.name`, `premises.address_line`,
#           `units.label`) · BR-SHL-006 (app.tenant_id + RLS FORCE; role-invisible
#           groups omitted) · B14 rule 31 (no database id is ever visible)
# Tests:    06-backend/tests/test_us_shl_003_search.py ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7)
# Impacts:  core.search registry (apps/metering/apps.py registers these two) ·
#           GET /search (apps/tenancy/search_api.py)
# ───────────────────────────────────────────────────────
"""The metering module's global-search sources: premises and units.

⚠ **THIS IS THE ONE MODULE WHERE AN ADDRESS IS A SEARCH FIELD, AND THAT IS
SIGNED RATHER THAN A LANE'S CHOICE.** BR-SHL-005's field list names
`premises.address_line` outright, and US-SHL-003/TC-2 searches *"Cedar"* and
expects *Cedar Ridge Apartments*. So premises admit a match on the name and the
street as well as the premises number. **No other group in this feature matches
free text** — the amendment of 2026-09-03 repeats *"by their B2 identifiers"* as
a thing not to relax, and the decision log records why the line was drawn here
and not around every entity.

The RANK still puts the identifier first: `premise_no` and `unit_no` are the
prefix band, so a person typing a premises number gets it above a street that
happens to contain the same characters.

Soft deletes are excluded. `premises` and `units` both carry `deleted_at`, and a
deleted premises answering a search would let a clerk deep-link into a record the
list screens will not show them.
"""

from typing import Any

from apps.metering import models
from apps.metering import selectors as metering_selectors
from core import errors
from core import search as core_search
from core import tenancy as core_tenancy

# The identifier band (BR-SHL-005's "prefix-match-first").
_PREMISES_PREFIX_FIELDS = ("premise_no",)
# The admission sets are metering's SHARED staff-search lists since
# `CR-200-BRC10` (PO 2026-10-29, 3 A): `selectors.PREMISES_WORD_FIELDS` (+ a unit
# inside the premises) and `selectors.UNIT_WORD_FIELDS`, matched WORD BY WORD.
# They widen BR-SHL-005's signed list (number, name, street; unit label) by the
# town and ZIP, and a unit now answers to its building's street — "12 Oak"
# returned 12 Oak St and never Apt 2B inside it (`DEF-MET-10679`).

_UNIT_PREFIX_FIELDS = ("unit_no",)


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-SHL-006")
    return tenant_id


def _premises_label(row: Any) -> str:
    """What the popover shows large.

    The premises NUMBER when the tenant issues them, and the premises NAME when
    it does not — `premise_no` is nullable and a great many utilities never fill
    it. **The fallback is a name, never the uuid** (B14 rule 31): where neither
    exists the row would be unidentifiable to a human, so the street stands in.
    """
    return row.premise_no or row.name or row.address_line


def search_premises(term: str, limit: int) -> list[dict[str, Any]]:
    """Premises by number, name or street (BR-SHL-005's signed field list)."""
    qs = models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True).filter(
        metering_selectors.premises_word_match(term)
    )
    # Ranked on the FIRST word (decision log 2026-10-29, `CR-200-BRC10` lane A).
    rank = core_search.rank_word(term)
    rows = list(core_search.prefix_then_recency(qs, rank, _PREMISES_PREFIX_FIELDS)[:limit])
    return [
        {
            "id": str(row.id),
            "label": _premises_label(row),
            # The street tells a clerk they have the right building. It is
            # dropped when it IS the label, because saying it twice is B14 rule
            # 32's repetition clause on a two-line row.
            "context": row.address_line if row.address_line != _premises_label(row) else None,
            "amount": None,
            "currency": None,
        }
        for row in rows
    ]


def search_units(term: str, limit: int) -> list[dict[str, Any]]:
    """Units by number or label ("Unit A", "200"), or by their building's
    street, town, ZIP, number or name — word by word ("12 Oak 2B").

    The context line is the premises the unit is in — a bare *"Unit A"* is
    ambiguous across an estate and useless on its own. `select_related` so the
    five rows cost one query rather than six.
    """
    qs = (
        models.Unit.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .select_related("premises")
        .filter(metering_selectors.unit_word_match(term))
    )
    rank = core_search.rank_word(term)
    rows = list(core_search.prefix_then_recency(qs, rank, _UNIT_PREFIX_FIELDS)[:limit])
    return [
        {
            "id": str(row.id),
            "label": row.unit_no or row.label,
            "context": _premises_label(row.premises) if row.premises_id else None,
            "amount": None,
            "currency": None,
        }
        for row in rows
    ]


def register() -> None:
    """Register the two metering groups with the BE-08 kernel.

    Called from `MeteringConfig.ready()`. Default `visible_to` — every tenant
    role — because `GET /premises` and `GET /units` are `AnyTenantRole` today
    (A4: Premises is Admin Full · Clerk Full · Executive View, and a search is a
    read). BR-SHL-006's omission clause guards a future role, in the kernel.
    """
    core_search.register_search_source("premises", search_premises)
    core_search.register_search_source("units", search_units)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03 (BR-SHL-005 amended)
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(the popover is wired in the same lane) F✔ G✔ H=deferred(PO)
# exceptions: premises is the ONLY group that admits free text (name + street),
#         and it is signed rather than chosen — BR-SHL-005's own field list
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
