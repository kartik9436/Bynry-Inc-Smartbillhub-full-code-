# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-1114 — a master account is raised only on a premises with two
#           or more homes (PO ruling 2026-10-02: *"single family hime, single
#           unit, we should not do master account"*).
# ───────────────────────────────────────────────────────
"""One shared step for fixtures that raise a master account.

Fixtures written before 2026-10-02 opened a master account on an address with
one home (or none, or only a common area), because the rules then allowed it.
Each such case is ABOUT something else — where the account hangs, who pays a
vacant unit, how a customer is matched — so rather than rewrite them, the
fixture tops the building up to two homes immediately before the master is
raised and the case goes on testing what it was written for.

The single-home case itself is tested, by name, in
`tests/test_br_cus_1114_master_only_multi_unit.py`.
"""

from __future__ import annotations

from typing import Any

#: Mirrors `customers.services.MASTER_ACCOUNT_MIN_UNITS`.
MIN_HOMES = 2


def top_up_homes(actor: Any, premises_id: Any, *, to: int = MIN_HOMES) -> list[Any]:
    """Add vacant homes (`Home 1`, `Home 2` …) until the premises holds `to`
    live, non-common-area units. Returns what it added (often nothing)."""
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services

    live = metering_models.Unit.objects.filter(
        premises_id=premises_id, deleted_at__isnull=True, is_common_area=False
    ).count()
    added = []
    n = 0
    while live < to:
        n += 1
        label = f"Home {n}"
        if metering_models.Unit.objects.filter(premises_id=premises_id, label=label).exists():
            continue
        added.append(
            metering_services.create_unit(
                actor, {"premises_id": str(premises_id), "label": label, "unit_type": "residential"}
            )
        )
        live += 1
    return added
