# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-039 (EP-WRK-05) — the five flows raise their jobs.
# Rules:    BR-WRK-055 (a flow completes whether or not the visit could be
#           raised) · CLAUDE.md hard-won law 14 (a failed statement poisons the
#           whole PostgreSQL transaction; the suite runs on SQLite, which does
#           not, so the broken version passes everything)
# Tests:    this file — the ONE case the ordinary suite cannot fail
# ───────────────────────────────────────────────────────
"""**THE LAW-14 CASE — and the first draft of it PROVED NOTHING.**

`services._raise_flow_work` catches a failure from the raise and lets the flow
complete. On PostgreSQL a caught database error is not enough: once any
statement errors, the transaction is aborted and every later query raises
`InFailedSqlTransaction`, so the flow's own writes are lost at COMMIT while the
`except` runs and the function returns a cheerful answer. `config/settings/
test.py` hardcodes in-memory SQLite, which has no such state, so a broken
version passes the entire ordinary suite green on every machine.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        DATABASE_URL="postgres://…" pytest tests/test_us_wrk_039_from_flows_pg.py

⚠ **WHAT IS ACTUALLY UNDER TEST, AFTER THE FIRST VERSION WAS SHOWN TO BE
WORTHLESS.** The first draft asserted *"the savepoint in `raise_for` is what
saves the account"*, and it was proved RED by deleting that savepoint — **and it
still passed.** The savepoint is not what saves it: **every one of the five
doors raises AFTER its own transaction has committed**, so there is no open
transaction for a failed statement to poison. A case whose sabotage does not
bite is worse than no case, because it is trusted (`DEF-182`).

**So the guarantee this file asserts is the real one, and it is held by TWO
independent mechanisms:**

  1. **THE ORDERING** — the raise is outside the flow's `atomic()` block, in all
     five doors. This is the load-bearing half.
  2. **THE SAVEPOINT** — `raise_for` wraps its own reads and writes in a nested
     `atomic()`, so a lane that later moves a call inside a transaction while
     tidying does not silently lose a flow.

**The sabotage that DOES bite is breaking both**, which is exactly what a
careless tidy-up looks like: move the raise inside the caller's transaction and
"simplify away" the nested atomic. The case below was proved red that way and
green again, on a real PostgreSQL.

⚠ **THE FAILURE IS INDUCED AS A REAL DATABASE ERROR, NOT AS A `RuntimeError`.**
`test_us_wrk_039_from_flows.py` TC-2 raises a Python exception, which proves the
CATCH exists; it cannot prove anything about transaction state, because a Python
exception leaves the connection perfectly healthy.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work.seams import metering_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="hard-won law 14: SQLite has no aborted-transaction state, so this case "
    "cannot fail there and proving it there proves nothing",
)


def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


@POSTGRES_ONLY
@pytest.mark.django_db(transaction=True)
def test_a_database_error_in_the_raise_still_closes_the_account_on_postgresql(
    dana, brazos, monkeypatch
):
    """A move-out whose field job dies of a DATABASE error still closes.

    The failed statement below is one PostgreSQL refuses, so the connection
    enters the aborted state that SQLite does not have. The move-out must still
    be committed — and the check is a RE-READ from the database, not the answer
    the function returned, because a lost flow and a saved one produce the same
    answer. That is the point: `work_orders_not_raised` is reported either way,
    and only the row can tell you which happened.

    **A false record of a customer's departure is worse than a refusal**, which
    is what makes this a law and not a tip.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="221 Oak Ave")
        unit = make_unit(dana, premises["id"])
        metering_services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(_plan(brazos).id)})
        for code in ("electric", "water"):
            metering_services.ensure_service_point(unit["id"], code)
        account = customers_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-01-05",
                "contact": {"full_name": "Sarah Miller"},
                "customer": {
                    "display_name": "Sarah Miller",
                    "kind": "person",
                    "identity": {"phone": "+1 (281) 555-0155"},
                },
            },
        )
        header = w6.create_work_order_template(
            dana, {"name": "Final read & deactivate", "service": "electric", "sequence": 0}
        )
        w6.publish_work_order_template(dana, header["id"])

        def _database_error(*_args, **_kwargs):
            # A statement PostgreSQL refuses. Everything after it in the SAME
            # transaction raises `InFailedSqlTransaction`. The move-out has
            # already committed by the time this runs — that ordering is the
            # guarantee — and `raise_for`'s nested atomic() is the second line
            # of defence for a lane that later moves the call.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 / 0")

        monkeypatch.setattr(metering_seam, "raise_work_order", _database_error)

        result = customers_services.move_out(
            dana,
            account["id"],
            {"moved_out_on": "2026-03-28", "field_visit": {"template_ids": [header["id"]]}},
        )

        # 1 · the flow reported that the job was not raised …
        assert [row["code"] for row in result["warnings"]].count("work_orders_not_raised") == 1
        assert result["work_orders"] == []

        # 2 · … and the move-out is REALLY committed, READ BACK FROM THE
        #     DATABASE rather than taken from the answer the function returned.
        #     That re-read is the whole case: a lost flow and a saved one return
        #     the SAME answer, warnings included, and only the row can tell them
        #     apart.
        from apps.customers import models as customers_models

        row = customers_models.Account.objects.get(pk=account["id"])
        assert row.closed_at is not None, (
            "the account was lost at COMMIT — the raise is inside the flow's transaction "
            "and nothing confines it (hard-won law 14)"
        )
        assert str(row.closed_at)[:10] == "2026-03-28"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-039 (EP-WRK-05) · CLAUDE.md hard-won law 14
# generated: 2026-09-05 by the CR-070 wave P build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_wrk_039_from_flows_pg.py (PostgreSQL only)
# exceptions: SKIPs on SQLite by design — a case that cannot fail on the harness
#   it runs in is worse than no case, so it says so instead of passing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
