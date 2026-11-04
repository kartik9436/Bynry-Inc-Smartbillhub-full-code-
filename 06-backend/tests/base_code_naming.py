# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9832 — PO ruling 2026-10-06, verbatim: *"You will take the
#          code from plan -> rate schedule -> base charges - in that case if it
#          is provided then you will take it if it is not provided then you
#          will take it zeo ; but you cannot take W-COM because it is availabel
#          in charge coede"*.
# ───────────────────────────────────────────────────────
"""One helper for the fixtures that mint a base charge code: NAME it on the
rate schedules of its service, the way step 1 of the rate-schedule wizard does
(and the way activation does when exactly one code could serve).

Until 2026-10-06 a fixture could create an `is_base` code and leave every
schedule naming none, because the live path took the code from the charge-code
list by class (the pool). The PO retired the pool: an unnamed schedule bills a
`$0.00` base with a warning. So a fixture whose subject is a PRICED base names
its code — the figure it asserts is unchanged, reached by the ruled chain.

Call it AFTER the schedule versions exist; it names every version of every
schedule of the code's service on the tenant, so call it once per code and only
where one code per service is meant.
"""

from __future__ import annotations

from typing import Any


def name_base_code(tenant: Any, charge: Any) -> Any:
    """Point every rate schedule version of `charge`'s service at `charge`."""
    from apps.rating import models as rating_models

    rating_models.TariffVersion.objects.filter(
        tenant=tenant, tariff__service_id=charge.service_id
    ).update(base_charge_code_id=charge.id)
    return charge
