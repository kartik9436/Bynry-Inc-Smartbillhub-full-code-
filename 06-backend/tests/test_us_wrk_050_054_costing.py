# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-050 (parts against a job, and NO stock) · US-WRK-051 (labour
#           rates, per role, dated) · US-WRK-052 (tax on a work order — NOTHING
#           IS BUILT) · US-WRK-054 (the performance tab, and no Finance arrow)
# Rules:    BR-WRK-019 · BR-WRK-020 · BR-WRK-049 · BR-WRK-052 · BR-WRK-053 ·
#           BR-WRK-004 · CLAUDE.md hard rule 2 (4 stored, 2 displayed) ·
#           hard rule 5 (only the ledger posting service writes journal lines)
# Tests:    this file — every TC named in its own test name.
#           US-WRK-053's arithmetic is test_us_wrk_053_costing.py.
# ───────────────────────────────────────────────────────
"""US-WRK-050 · 051 · 052 · 054, by TC.

⚠ **THE RLS HALVES OF `US-WRK-050` TC-6 AND `US-WRK-051` TC-7 ARE NOT HERE AND
CANNOT BE.** `config/settings/test.py` hardcodes in-memory SQLite, **which has
no row-level security at all**, so an RLS assertion in this file would pass by
vacuum (CLAUDE.md hard-won law 14, one rule along). The isolation cases below
are the APPLICATION-layer proof — the selector filters by the tenant in context
and one utility's rows are absent from the other's list. The DATABASE-layer
proof is `tests/test_us_wrk_053_costing_pg.py`, on real PostgreSQL 16 under a
non-superuser probe role.

⚠ **AND THE TENANT-ISOLATION GATE IS NOT THAT PROOF EITHER** (`DEF-GOV-4024`,
2026-09-05): it runs the isolation suite without pointing it at PostgreSQL, so
it inherits SQLite — 46 of 238 proofs run, 192 skip, exit 0. A green gate there
is evidence of nothing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[2]


def _part(tenant, part_no="MTR-W58", cost="92.4000"):
    return work_models.Part.objects.create(
        tenant=tenant, part_no=part_no, name=f"{part_no} part",
        unit_of_measure="each", unit_cost=Decimal(cost),
    )


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-051 — a labour rate is per ROLE, dated, and a closed job keeps it
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_051_tc1_a_rate_is_stored_at_four_and_shown_at_four_on_this_screen(brazos, dana):
    """TC-1 — `48.5000` stored; `Work-030` shows `48.5000`; the report `48.50`.

    This is the ONE screen that shows four decimals, because the stored value
    is what is being edited (hard rule 2's display half yields to that).
    """
    with tenant_ctx(brazos):
        row = work_services.create_labour_rate(dana, {
            "role": "field_technician", "role_label": "Field technician",
            "hourly": "48.5000", "overtime_hourly": "72.7500",
            "overtime_after_hours": "8", "effective_from": "2026-01-01",
        })
    assert row["hourly"] == "48.5000"
    assert row["overtime_hourly"] == "72.7500"
    assert row["current"] is True
    stored = work_models.LabourRate.objects.get(id=row["id"])
    assert stored.hourly == Decimal("48.5000")


def test_us_wrk_051_tc3_a_change_is_a_new_row_and_the_old_one_is_never_updated(brazos, dana):
    """TC-3 — the rate moves to `50.0000` on 1 April.

    The old row keeps `48.5000` EXACTLY and gains `superseded_on`; it is never
    edited. `WO-4822`, closed 15 March, must still price at `48.5000` — and so
    must the 184 exchanges that closed before it.
    """
    with tenant_ctx(brazos):
        first = work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "48.5000",
            "effective_from": "2026-01-01",
        })
        second = work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "50.0000",
            "effective_from": "2026-04-01",
        })
        rows = work_selectors.labour_rates_page()["rows"]

    old = work_models.LabourRate.objects.get(id=first["id"])
    assert old.hourly == Decimal("48.5000"), "the old rate was EDITED, not superseded"
    assert old.superseded_on == dt.date(2026, 4, 1)
    assert second["hourly"] == "50.0000" and second["current"] is True
    assert [r["current"] for r in rows] == [True, False]
    assert work_models.LabourRate.objects.filter(role="field_technician").count() == 2


def test_us_wrk_051_tc3b_only_one_row_per_role_is_ever_current(brazos, dana):
    """The partial unique index, not the service layer's intention.

    Two supervisors saving a new Field technician rate in the same second get
    one winner and one refusal — rather than two current rates and a report
    whose figure depends on row order.
    """
    from django.db import IntegrityError

    with tenant_ctx(brazos):
        work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "48.5000", "effective_from": "2026-01-01",
        })
        with pytest.raises(IntegrityError):
            work_models.LabourRate.objects.create(
                tenant=brazos, role="field_technician",
                hourly=Decimal("60.0000"), effective_from=dt.date(2026, 2, 1),
            )


def test_us_wrk_051_tc4_a_rate_with_five_decimals_is_refused_not_rounded(brazos, dana):
    """TC-4 — `48.50004` is REFUSED. A price quietly changed by the thing that
    stored it is a defect nobody finds for a year."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            work_services.create_labour_rate(dana, {
                "role": "field_technician", "hourly": "48.50004",
                "effective_from": "2026-01-01",
            })


def test_us_wrk_051_tc5_a_contractor_carries_one_rate_and_a_dash(brazos, dana):
    """TC-5 — overtime reads a DASH; `overtime_hourly` NULL, threshold NULL.

    `BR-WRK-020`: *"an agency invoices its own overtime… The dash is the honest
    value."* NULL, never `0.0000`, which would read as free overtime.
    """
    with tenant_ctx(brazos):
        row = work_services.create_labour_rate(dana, {
            "role": "contractor:apex", "role_label": "Apex Utility Svc",
            "hourly": "95.0000", "effective_from": "2026-01-01",
        })
    assert row["overtime_hourly"] is None
    assert row["overtime_after_hours"] is None
    assert row["hourly"] == "95.0000"


def test_us_wrk_051_tc6_a_rate_is_per_role_and_a_technician_id_is_refused(brazos, dana):
    """`WM-45` — *"a per-person rate is a salary, it belongs in payroll"*.

    The body cannot carry a person, and an unknown field is REFUSED rather
    than ignored, so it cannot arrive from the other side either.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            work_services.create_labour_rate(dana, {
                "role": "field_technician", "hourly": "48.5000",
                "effective_from": "2026-01-01", "technician_id": "someone",
            })
    assert not hasattr(work_models.LabourRate, "technician")


def test_us_wrk_051_tc7_one_utility_never_sees_anothers_rates(brazos, lonestar, dana, erin):
    """TC-7 — application-layer isolation. The database half is the `_pg` file."""
    with tenant_ctx(brazos):
        work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "48.5000", "effective_from": "2026-01-01",
        })
    with tenant_ctx(lonestar):
        work_services.create_labour_rate(erin, {
            "role": "field_technician", "hourly": "51.0000", "effective_from": "2026-01-01",
        })
        rows = work_selectors.labour_rates_page()["rows"]
    assert [r["hourly"] for r in rows] == ["51.0000"]


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-050 — parts against a job, and NO stock anywhere
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_050_tc1_an_issue_is_a_negative_row_naming_who_and_when(brazos, dana):
    """TC-1 — *−1 · D. Ortiz · (ref WO-4822)*, and nothing counts down."""
    with tenant_ctx(brazos):
        part = _part(brazos, "MTR-W58")
        row = work_services.create_part_issue(dana, {
            "part_id": str(part.id), "qty": "-1",
            "purpose": "Exchanges on Route 2", "order_ref": "WO-4822",
            "at": "2026-08-16T08:10:00Z",
        })
    assert row["qty"] == "-1.0000"
    assert row["direction"] == "issue"
    assert row["order_ref"] == "WO-4822"
    assert row["at"].startswith("2026-08-16T08:10")


def test_us_wrk_050_tc4_the_answer_carries_no_stock_key_and_no_running_balance(brazos, dana):
    """TC-4 · **negative** — no `on_hand`; Movements has no running balance.

    `OQ-WRK-1490` closed 2026-09-04 to option (a). A running balance IS an
    on-hand figure with extra steps.
    """
    with tenant_ctx(brazos):
        part = _part(brazos, "MTR-W58")
        work_services.create_part_issue(dana, {"part_id": str(part.id), "qty": "-2"})
        page = work_selectors.part_issues_page()
    body = repr(page)
    for forbidden in ("on_hand", "reorder_at", "location", "balance", "running"):
        assert forbidden not in body, forbidden
    for forbidden in ("on_hand", "reorder_at", "location"):
        assert not hasattr(work_models.PartIssue, forbidden)
        assert not hasattr(work_models.Part, forbidden)


def test_us_wrk_050_tc5_stock_position_is_a_ruling_not_a_stub(brazos):
    """TC-5 · **absence** — the banner is not rendered and the function raises
    THE RULING, not a question id (`DEF-WRK-4030`)."""
    with pytest.raises(NotImplementedError) as excinfo:
        work_services.stock_position("any")
    message = str(excinfo.value)
    assert "no stock at all" in message
    assert "OQ-" not in message, "a ruled absence must not cite a closed question"


def test_us_wrk_050_tc5b_an_issue_body_refuses_a_stock_field_by_name(brazos, dana):
    """A lane adding `on_hand` to a request body gets a refusal naming it,
    rather than having it silently dropped."""
    with tenant_ctx(brazos):
        part = _part(brazos)
        with pytest.raises(errors.ValidationError):
            work_services.create_part_issue(dana, {
                "part_id": str(part.id), "qty": "-1", "on_hand": "184",
            })


def test_us_wrk_050_tc6_one_utility_never_sees_anothers_issue_log(brazos, lonestar, dana, erin):
    """TC-6 — application-layer isolation."""
    with tenant_ctx(brazos):
        work_services.create_part_issue(dana, {
            "part_id": str(_part(brazos, "MTR-W58").id), "qty": "-2"})
    with tenant_ctx(lonestar):
        work_services.create_part_issue(erin, {
            "part_id": str(_part(lonestar, "LSR-01").id), "qty": "-5"})
        rows = work_selectors.part_issues_page()["rows"]
    assert [r["part_no"] for r in rows] == ["LSR-01"]


def test_us_wrk_050_tc7_a_return_is_a_new_positive_row_never_a_deletion(brazos, dana):
    """TC-7 — `+4 · R. Patel · return · Unused on job`.

    Deleting the issue would make the log say the parts were never taken,
    which is not what happened.
    """
    with tenant_ctx(brazos):
        part = _part(brazos, "GSKT-STD")
        work_services.create_part_issue(dana, {"part_id": str(part.id), "qty": "-4"})
        ret = work_services.create_part_issue(dana, {
            "part_id": str(part.id), "qty": "4", "purpose": "Unused on job"})
        rows = work_selectors.part_issues_page()["rows"]
    assert ret["direction"] == "return"
    assert len(rows) == 2, "the issue was replaced instead of a return being added"
    assert {r["direction"] for r in rows} == {"issue", "return"}


def test_a_movement_of_nothing_is_refused(brazos, dana):
    """A zero quantity is a mis-keyed row and means nothing in a log."""
    with tenant_ctx(brazos):
        part = _part(brazos)
        with pytest.raises(errors.ValidationError):
            work_services.create_part_issue(dana, {"part_id": str(part.id), "qty": "0"})


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-052 — tax on a work order: NOTHING IS BUILT, and this proves it
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_052_tc1_nothing_is_built_and_the_absence_is_the_test():
    """TC-1 · **negative** — PO 2026-09-03: *"Dont add Tax on work order - for
    now"*. No flag, no frequency, no `Work-031`, no tax line.

    B4 §Tax ❄️ FROZEN stands: *tax base = usage + base charge only*. Re-opening
    this is a finance re-sign through HUMAN-GUIDE §6, never a lane's edit.
    """
    rating_models = (REPO / "06-backend/apps/rating/models.py").read_text()
    assert "base_includes_field_work" not in rating_models
    assert "per_work_order" not in rating_models

    # the cost-line kinds are exactly three, and a fourth cannot be added quietly
    assert work_models.WorkOrderCostLine.KINDS == ("labour", "overtime", "part")
    assert not hasattr(work_models.WorkOrderCostLine, "KIND_TAX")

    for path in ("06-backend/apps/work/costing.py", "06-backend/apps/work/selectors.py"):
        body = (REPO / path).read_text()
        for forbidden in ("base_includes_field_work", "per_work_order", "KIND_TAX"):
            assert forbidden not in body, f"{forbidden} in {path}"


def test_us_wrk_052_the_figure_that_is_not_computed_is_recorded_as_not_computed():
    """`138.42 × 0.0625 = 8.65`, `× 0.02 = 2.77`, `149.84`. None of it is built,
    and the report totals `138.42` — pinned so nobody reconstructs the
    wireframe's figure from the drawing."""
    from apps.work import costing

    lines, total = costing.compute(
        costing.LabourInput(minutes=52, role_label="Field technician", rate=Decimal("48.5000")),
        [costing.PartInput("MTR-E1P", Decimal("1"), "each", Decimal("96.0000")),
         costing.PartInput("SEAL-01", Decimal("1"), "each", Decimal("0.2200"))],
    )
    assert total == Decimal("138.42")
    assert total != Decimal("149.84")
    assert len(lines) == 3, "a fourth line appeared — a tax row?"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-054 — the performance tab, and no way from it into Finance
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_054_tc3_nothing_on_the_page_carries_the_total_into_finance(brazos):
    """TC-3 · **negative** — grep for *Finance*, *Cost & Margin*, *O&M*, `5300`.

    r10 says the total *"feeds the O&M / labour line in Finance → Cost &
    Margin"*. That arrow is not built (`BR-WRK-004`; `CR-028` D3 is the same
    sentence removed for asset maintenance). Payroll already posts the hour.
    """
    with tenant_ctx(brazos):
        payload = repr(work_selectors.performance())
    for forbidden in ("Finance", "Cost & Margin", "O&M", "5300", "6020", "journal"):
        assert forbidden not in payload, forbidden


def test_us_wrk_054_tc4_posting_is_a_ruling_and_nothing_calls_it():
    """TC-4 · **absence** — `post_field_cost_to_ledger()` raises the RULING,
    and no line of `apps/work/**` calls it (hard rule 5: only the ledger
    posting service writes journal lines)."""
    from apps.work import costing

    with pytest.raises(NotImplementedError):
        costing.post_field_cost_to_ledger(object())

    calls = []
    for path in (REPO / "06-backend/apps/work").rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if "post_field_cost_to_ledger(" in line and "def " not in line:
                calls.append(f"{path.name}:{number}")
    assert calls == [], f"something calls the posting: {calls}"


def test_us_wrk_054_tc6_a_utility_with_no_completed_work_sees_zeros_drawn_as_zeros(brazos):
    """TC-6 — *"zeros drawn as zeros"*. A new utility should see that it has no
    completed work, not an empty page."""
    with tenant_ctx(brazos):
        result = work_selectors.performance()
    # `totals`/`rows` since 2026-10-04 (P5.6, lane SRV-4): the table is paged
    # in SQL and `total` is now the count of its rows, the list envelope's.
    assert result["totals"]["volume"] == 0
    assert result["totals"]["total_cost"] == "0.00"
    assert result["tiles"]["sla_met_pct"] == "0.0"
    assert result["tiles"]["first_time_fix_pct"] == "0.0"
    assert result["rows"] == []


def test_us_wrk_054_tc5_first_time_fix_is_the_share_with_no_follow_up(brazos, dana):
    """TC-5 — the share of completed orders that nothing was re-done for.

    ⚠ **THIS TEST WAS WRITTEN AS A HOLD-EXPIRY ALARM AND THE HOLD EXPIRED THE
    SAME AFTERNOON.** `follows_order_id` is wave `I`'s column (`US-WRK-034`)
    and had not landed when this wave started, so the tile read a DASH rather
    than the `100%` that counting every order as a first-time fix would have
    produced — wrong in the flattering direction, on a figure a manager acts
    on. `I` landed `metering/0052` mid-build, the alarm fired by name, and this
    is TC-5 finished (hard-won law 2: write the test that fires when the hold
    expires, in the same commit as the hold).

    Three completed jobs, one of them re-done: two first-time fixes out of
    three is `66.7%`.
    """
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        # ⚠ EVERY ORDER NEEDS AN ANCHOR — `ck_work_orders_has_anchor`
        # (`BR-WRK-006`): at least one of connection, premises, account or
        # asset. An anchorless fixture row is refused by the database, which is
        # the constraint doing its job and is why these are hung on a premises.
        premises = make_premises(dana, address_line="221 Oak Ave", services_available=["electric"])
        made = []
        for name in ("first", "second", "third"):
            made.append(work_tables.WorkOrder.objects.create(
                tenant=brazos, type="Meter exchange", state=work_tables.WO_COMPLETED,
                completed_at=dt.datetime(2026, 3, 15, 16, 7, tzinfo=dt.timezone.utc),
                premises_id=premises["id"], order_no=name,
            ))
        # the third job exists BECAUSE the first one failed — so the FIRST is
        # the one that was not fixed first time. The pointer is on the
        # follow-up and the target is the re-done job.
        made[2].follows_order = made[0]
        made[2].save(update_fields=["follows_order"])
        result = work_selectors.performance()

    assert result["totals"]["volume"] == 3
    assert result["tiles"]["first_time_fix_pct"] == "66.7"


def test_us_wrk_054_tc2_an_undated_order_is_measured_against_the_default_target(brazos, dana):
    """TC-2 — the share of completed orders finished on or before their promise.

    ⚠ **SUPERSEDED 2026-10-04 BY PO ANSWER (1)** (*"(b), so every job has a
    promise to measure against"*, judgment J7; lane SRV-4, `CR-168-BRC10`
    P5.9). This case was *"an order with no promise is out of the denominator"*
    and asserted `50.0%` for two promised jobs (one kept, one missed) and one
    undated. Since the ruling an undated job IS promised — its raise plus the
    DEFAULT target's hours (the tenant's Normal priority, 72 h) — so the third
    job, raised at 08:00 and done at 16:07 the same day, is KEPT: `66.7%`.
    A job is left out only when there is no default either (no Normal
    priority and none chosen), which `test_cr168_srv4_promise.py` covers.
    """
    from apps.work import connection_models as work_tables

    due = dt.datetime(2026, 3, 15, 17, 0, tzinfo=dt.timezone.utc)
    raised = dt.datetime(2026, 3, 15, 8, 0, tzinfo=dt.timezone.utc)
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        premises = make_premises(dana, address_line="14 Elm St", services_available=["water"])
        for order_no, completed, promise in (
            ("kept", dt.datetime(2026, 3, 15, 16, 7, tzinfo=dt.timezone.utc), due),
            ("missed", dt.datetime(2026, 3, 15, 18, 0, tzinfo=dt.timezone.utc), due),
            ("undated", dt.datetime(2026, 3, 15, 16, 7, tzinfo=dt.timezone.utc), None),
        ):
            row = work_tables.WorkOrder.objects.create(
                tenant=brazos, type="Meter exchange", order_no=order_no,
                state=work_tables.WO_COMPLETED, premises_id=premises["id"],
                completed_at=completed, due_at=promise,
            )
            work_tables.WorkOrder.objects.filter(pk=row.pk).update(created_at=raised)
        result = work_selectors.performance()

    assert result["totals"]["volume"] == 3
    assert result["tiles"]["sla_measured"] == 3
    assert result["tiles"]["sla_met_pct"] == "66.7"


def test_us_wrk_054_the_percentage_is_one_decimal_as_drawn():
    """`Work-027` draws `94.2%`. One decimal, half-up."""
    assert work_selectors._pct(942, 1000) == "94.2"
    assert work_selectors._pct(88, 100) == "88.0"
    assert work_selectors._pct(0, 0) == "0.0"
