"""DEF-CUS-10093 — isolate the final-bill DRAFT from suites that test the CLOSE.

PO ruling 2026-10-13, option B: Complete drafts the final bill before the close,
and a move-out whose bill cannot be drafted does not complete. Most move-out
suites were written before that ruling on fixtures that were never billable (no
cycle, no plan, no reads), because their subject is the close itself — the
unit freeing, the reads, the field visit, the settlement, the move-in chain.
Under the ruling each of those move-outs is now refused, correctly.

Rather than make sixty-nine fixtures billable, those suites answer billing's
draft as `nothing_to_bill` — the honest outcome for an account with no billable
days, which leaves every warning they assert exactly as it was. The draft
itself, its refusal and its money are tested where they belong:
`tests/test_def_cus_10093_move_out_drafts_the_final_bill.py`.

Use: `pytestmark = [..., pytest.mark.usefixtures("move_out_draft_isolated")]`
after `from tests.move_out_draft_isolation import move_out_draft_isolated`.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def move_out_draft_isolated(monkeypatch):
    from apps.customers import seams

    def nothing_to_bill(actor, *, account_id, moved_out_on):
        day = getattr(moved_out_on, "isoformat", lambda: str(moved_out_on))()
        return {"outcome": "nothing_to_bill", "period_start": day, "period_end": day}

    monkeypatch.setattr(seams, "draft_move_out_final_bill", nothing_to_bill)


def on_a_billing_cycle(tenant, unit_id, *, code="MO-CYC", first_run="2026-06-01", due_days=21):
    """DEF-CUS-10127 — make a move-out fixture BILLABLE instead of isolating it.

    The other way round from `move_out_draft_isolated`: the real draft runs and
    the refusal stays exactly as strong as the product makes it. A unit on no
    billing cycle is refused by billing by name (`billing.oneTime.err.
    noBillingCycle`), which is correct, so a suite that moves an account out
    must put its unit on a cycle the product can place on a calendar — a ruled
    `frequency` and a `first_run_date` (`period_engine.billing_period` answers
    `None` without either) and the `due_days` BR-BIL-024 reads. The cycle is
    stamped on every service point of the unit, which is where metering keys a
    bill's scope (`tests/test_us_bil_001_prepare.a_billed_unit`).
    """
    from datetime import date

    from apps.metering import models as metering_models

    start = date.fromisoformat(first_run)
    cycle = metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        frequency="monthly",
        start_day=start.day,
        days_to_complete=30,
        first_run_date=start,
        due_days=due_days,
    )
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
    return cycle


def billable_unit(
    actor, tenant, unit_id, *, services, uoms=None, plan_name="DEF-CUS-10127 priced"
):
    """DEF-CUS-10127 — a cycle (above) AND prices: the unit's plan becomes a
    PUBLISHED plan with a version in force from 1 January 2026 for every one of
    `services` (`tests/test_us_bil_001_prepare.a_priced_plan`, the shared
    builder — never a second one). Billing then drafts the final bill for real,
    so the move-out under test completes through the same door a clerk uses.

    ⚠ **PRICES ARE NOT ENOUGH ON THEIR OWN, AND THE CALLER MUST ALSO READ A
    METER.** Billing counts a service in service only where an asset sits on
    its point (PO, `gather._unconnected_plan_services`), and a meter with no
    committed read on the move day is a missing read the draft refuses
    (`missing_read_undecided_at_calculate`). Both refusals are the product
    being right, so each caller commits its own read rather than this helper
    hiding them. `uoms` restates a service's billed unit where the builder's
    `kWh` is wrong for it (water in `kgal`) — hard rule 3, never assumed."""
    from apps.metering import services as metering_services
    from apps.rating import models as rating_models

    from tests.test_us_bil_001_prepare import a_priced_plan

    on_a_billing_cycle(tenant, unit_id)
    plan = a_priced_plan(tenant, name=plan_name, services=tuple(services))
    for service_code, uom in (uoms or {}).items():
        rating_models.TariffVersion.objects.filter(
            tenant=tenant,
            tariff__service__code=service_code,
            tariff__planrateschedule__rate_plan=plan,
        ).update(uom=uom)
    metering_services.assign_unit_plan(
        actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    return plan
