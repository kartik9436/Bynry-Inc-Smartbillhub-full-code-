# ── Trace ──────────────────────────────────────────────
# Story:    the Reads→Work door — `from_flows`' SIXTH caller (PO 2026-09-14).
# Rules:    BR-WRK-024 + `ck_work_orders_source` (the vocabulary is closed and
#           the DATABASE is what closes it; `metering/0056` adds the sixteenth
#           token) · BR-WRK-055 (a failed raise never fails the flow) ·
#           CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; the suite runs on SQLite, which does not, so
#           the broken version passes everything)
# Tests:    this file — the TWO cases the ordinary suite cannot fail
# ───────────────────────────────────────────────────────
"""**THE TWO CASES `tests/test_reads_field_work.py` STRUCTURALLY CANNOT FAIL.**

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        DATABASE_URL="postgres://…" pytest tests/test_reads_field_work_pg.py

`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`
(hard-won law 14 names this file as the reason it is a law). Two guarantees of
this door are invisible there:

**1 · THE CONSTRAINT IS REAL, AND IT KNOWS ABOUT THE SIXTEENTH TOKEN.**
`ck_work_orders_source` lives in the DATABASE. `metering/0049` builds it from a
LIVE import of `connections.WORK_ORDER_SOURCES`, so appending a token changes
what that migration *would* create while every database that has already run it
keeps the old vocabulary. `metering/0056` drops and rebuilds it for exactly that
reason, and the failure it prevents is the one `0052` records: **Python accepts
the raise and PostgreSQL refuses the INSERT**, inside the transaction, naming a
constraint rather than a cause. The case below asserts BOTH directions —
`meter_read` is accepted, an invented token is refused BY NAME — because a check
that only proves the happy half would go green on a database where the migration
never ran.

**2 · A FAILED RAISE ON ONE METER DOES NOT COST THE NEXT ONE ITS VISIT.**
`raise_meter_read_field_work` loops meters and catches per meter, which is
`BR-WRK-055` (*the flow completes whether or not the visit could be booked*) —
and on PostgreSQL a caught database error is **not enough**: once any statement
errors, the transaction is aborted and every later query raises
`InFailedSqlTransaction`. What saves it is `raise_for`'s own `transaction.
atomic()`, which is the OUTERMOST block on this path because `ATOMIC_REQUESTS`
is set nowhere in `config/settings` — so a refusal rolls that meter back and the
next iteration opens a fresh transaction. **On SQLite the broken version passes,
because SQLite has no aborted-transaction state at all.**

⚠ **AND THE SECOND CASE RE-READS THE ROW FROM THE DATABASE RATHER THAN
BELIEVING THE RETURN VALUE**, for `test_us_wrk_039_from_flows_pg.py`'s reason:
a lost write and a saved one produce the SAME answer, so only the row can tell
them apart.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work import from_flows
from apps.work.seams import metering_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="hard-won law 14 and a database CHECK: neither can fail on SQLite, so "
    "proving them there proves nothing",
)


def _published_template(actor, name: str) -> dict:
    header = w6.create_work_order_template(
        actor, {"name": name, "service": "electric", "sequence": 0}
    )
    w6.publish_work_order_template(actor, header["id"])
    return header


def _meter_on_a_unit(actor, tenant, asset_no: str, address: str):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    service = tenancy_models.Service.objects.get(code="electric")
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name="Residential Standard",
        defaults={"code": "residential-standard", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name="Residential Standard — electric", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    return make_asset(
        actor,
        asset_no=asset_no,
        service="electric",
        unit="kWh",
        unit_id=str(unit["id"]),
        install_date="2024-01-15",
    )


@POSTGRES_ONLY
@pytest.mark.django_db
def test_the_database_itself_accepts_meter_read_and_refuses_an_invented_token(dana, brazos):
    """`metering/0056` — the CHECK and the Python tuple agree about sixteen.

    ⚠ **THE REFUSAL HALF IS THE LOAD-BEARING ONE.** Asserting only that
    `meter_read` is accepted would pass on a database whose `source` column has
    no CHECK at all — which is precisely the state a lane produces by appending
    to `WORK_ORDER_SOURCES` and writing no migration. So this asserts that an
    invented token is refused, BY THE CONSTRAINT'S OWN NAME, on the same
    connection and in the same breath.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        meter = _meter_on_a_unit(dana, brazos, "MTR-0463", "22 Cypress Row")
        template = _published_template(dana, "Re-read the meter")

        # 1 · the sixteenth token is ACCEPTED by the deployed database.
        result = from_flows.raise_for(
            from_flows.FLOW_METER_READ, meter["id"], [template["id"]], dana
        )
        order = work_tables.WorkOrder.objects.get(pk=result["raised"][0]["id"])
        assert order.source == "meter_read"

        # 2 · … and a token the tuple does not hold is REFUSED, by this
        #     constraint, on this connection. The savepoint is so the aborted
        #     transaction does not take the assertions after it down with it —
        #     which is hard-won law 14 showing up inside its own test file.
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():
                work_tables.WorkOrder.objects.filter(pk=order.pk).update(source="reading_needs_a_visit")
        assert "ck_work_orders_source" in str(caught.value), (
            "the database accepted a source the vocabulary does not hold — "
            "`ck_work_orders_source` is missing or stale, and `metering/0056` is "
            "what puts the sixteenth token into it"
        )


@POSTGRES_ONLY
@pytest.mark.django_db
def test_one_meters_database_failure_does_not_cost_the_next_meter_its_visit(
    dana, brazos, monkeypatch
):
    """`BR-WRK-055` + hard-won law 14, on the loop the endpoint actually runs.

    The first meter's raise dies of a REAL database error — a statement
    PostgreSQL refuses, which is what puts the connection into the aborted state
    SQLite does not have. A Python `RuntimeError` would prove only that the
    `except` exists and would leave the connection perfectly healthy.

    **The sabotage that makes this go red is deleting `raise_for`'s own
    `transaction.atomic()`**, which is the thing confining the poisoned
    statement. Shown red that way before it was trusted green, on this database.

    ⚠ **IT RUNS INSIDE AN OUTER TRANSACTION (`django_db`, not
    `transaction=True`), AND THAT IS THE HARDER CASE RATHER THAN A CONVENIENCE —
    said plainly, because the opposite would be easy to assume.** In production
    there is no outer transaction on this path (`ATOMIC_REQUESTS` is unset), so
    each statement commits on its own and an aborted one ends there; law 14
    cannot bite. It bites the moment ANY caller wraps this loop — a management
    command, a bulk door, a lane tidying the view into `@transaction.atomic` —
    and that is the version asserted here. A case that could only fail in a
    shape the product does not currently have would be a case that never fails.
    """
    with tenant_ctx(brazos):
        bad = _meter_on_a_unit(dana, brazos, "MTR-0463", "22 Cypress Row")
        good = _meter_on_a_unit(dana, brazos, "MTR-0471", "1408 Elm")
        template = _published_template(dana, "Re-read the meter")

        real_raise = metering_seam.raise_work_order
        seen: list[str] = []

        def _fail_the_first_meter(actor, payload):
            seen.append(str(payload.get("asset_id")))
            if len(seen) == 1:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 / 0")
            return real_raise(actor, payload)

        monkeypatch.setattr(metering_seam, "raise_work_order", _fail_the_first_meter)

        # The loop `raise_meter_read_field_work` runs, in the same order and with
        # the same catch. Kept here rather than driven through the HTTP view so
        # the case names the GUARANTEE and not a permission class.
        raised: list[dict] = []
        not_raised: list[str] = []
        for asset_id in (bad["id"], good["id"]):
            try:
                result = from_flows.raise_for(
                    from_flows.FLOW_METER_READ, asset_id, [template["id"]], dana
                )
            except Exception:  # noqa: BLE001 — exactly what the endpoint does
                not_raised.append(asset_id)
            else:
                raised.extend(result["raised"])

        assert not_raised == [bad["id"]]
        assert len(raised) == 1

        # ⚠ **RE-READ FROM THE DATABASE.** A raise that was lost at COMMIT and one
        # that was saved return the SAME answer, so only the row can tell them
        # apart — which is the whole reason this case exists.
        order = work_tables.WorkOrder.objects.get(pk=raised[0]["id"])
        assert order.source == "meter_read"
        assert order.source_ref == "MTR-0471"
        assert str(order.asset_id) == str(good["id"])
        # And the meter that failed left NOTHING behind: a half-written visit is
        # worse than none, because a crew would be dispatched to it.
        assert not work_tables.WorkOrder.objects.filter(asset_id=bad["id"]).exists()


# ── Lifecycle ─────────────────────────────────────────────
# packet: the Reads→Work door (decision log 2026-09-14) · hard-won law 14
# generated: 2026-09-14 by the Meter Reads field-visit lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: NOT in the ordinary suite — it skips on SQLite by construction. Run it
#   with `DJANGO_SETTINGS_MODULE=config.settings.local` against real PostgreSQL.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
