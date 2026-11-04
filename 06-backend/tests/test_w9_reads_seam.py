# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 Amendment 2 · W9 task 2 — the READ seam customers named as
#           missing: `apps.metering.selectors.reads_for_unit` published,
#           `apps.customers.seams.reads_for_unit` resolving it by name, and the
#           READ side of `apps/customers/move_reads.py` wired through it.
# Story:    US-CUS-005 (move-out) · US-CUS-004 (move-in). ⚠ NO STORY OWNS the
#           two worklist tabs (hard-won law 8 — `move_reads.py` filed it;
#           still OWED, not re-filed here).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 3 (a quantity
#           NEVER travels without its explicit unit) · BR-MET-016/053 (a
#           consumer sees committed lineage HEADS only — a corrected read is
#           represented by its correction) · BR-MET-024 (correction = NEW row)
#           · B1/B8 (customers never touches metering's ORM — the seam is the
#           one door) · BR-CUS-030 (`closed_at` IS the move-out date) ·
#           BR-CUS-022 (no start date → nothing to measure against) · DEF-127
#           (an absence is never spelled like a zero; an unwired seam REPORTS)
#           · DEF-075 (None means "cannot answer", never "nothing there") ·
#           DEF-324 (no per-meter query fan-out)
# Design:   B18 §5.5.2 (READS `taken`/`due`) · §5.6.2 (FINAL READ
#           `taken`/`due`/`estimated`) · §5.6.1 (`FINAL READS DUE` tile) ·
#           `move_reads.py` §4 rows 2–3 (the absence this seam closes)
# Tests:    this file. RED-first proof for the customers half is quoted in §2's
#           docstrings verbatim (hard-won law 7).
# Impacts:  apps/metering/selectors.py (reads_for_unit + read_is_estimated) ·
#           apps/customers/seams.py (the late-bound resolver; B2 §2 interface
#           row OWED — flagged for central write-back, 04-docs is not this
#           lane's to edit) · apps/customers/move_reads.py (reads/final_read
#           cells + FINAL READS DUE)
# ───────────────────────────────────────────────────────
"""CR-038 W9 task 2 — the unit-reads seam, both sides of the boundary.

§1 proves the METERING selector: newest committed head per meter/register,
quantity WITH its unit, `on` as-of capping, superseded rows invisible, the unit
and tenant boundaries, the estimation marker, and ONE reads query however many
meters the unit holds.

§2 proves the CUSTOMERS consumers: the seam resolves by name, the FINAL READS
DUE tile becomes a REAL count, the two cells serve `taken`/`due` with the
missing meters NAMED, and everything that must stay a stated absence stays one
— the unresolved-seam deployment, the meterless unit, the move-in with no date
to measure against, and (⚠ since task 4 landed, 2026-08-26) the FLAGLESS close
(`final_read_state_not_recorded`). `estimated` itself SERVES now, off
`accounts.final_read_state` — the amended case below carries the red-first
proof of the retire verbatim.
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import models as customers_models
from apps.customers import move_reads
from apps.customers import seams as customers_seams
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    lonestar,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The W5 worklist suite's clock, reused so the two files read one calendar.
TODAY = date(2026, 8, 25)


# ════════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658), except
# committed history, which `commit_read` writes directly for the same reason
# its own docstring states: the rows are the PAST a case starts from.
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    """A published plan so an ACTIVE account can exist (BR-MET-040)."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="W9 Reads", defaults={"code": "w9-reads", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"W9 Reads — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _metered_unit(admin, tenant, *, label="Unit A", meters=(("M-9101", "electric", "kWh"),)):
    """One unit holding real meters, through the real services.

    `make_unit(services=[...])` mints the service points; `a_meter` attaches
    each meter through `assets.create_asset` — the same chain
    `tests/test_w5_unit_reads.py` uses, so the seam is proven over the product's
    own wiring and not a hand-linked shortcut.
    """
    services = sorted({service for _no, service, _uom in meters}) or ["electric"]
    premises = make_premises(admin, services_available=services)
    unit = make_unit(admin, premises["id"], label=label, services=services)
    metering_services.assign_unit_plan(admin, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    made = [
        a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
        for asset_no, service, uom in meters
    ]
    return unit, made


def _account_on(clerk, unit_id, *, name, status="active", opened_at="2026-07-01"):
    """One account through `services.create_account` — the one door."""
    payload = {
        "unit_id": str(unit_id),
        "account_type": "residential",
        "status": status,
        "contact": {"full_name": name},
        # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
        # customer identifies nobody, and this fixture's own name went in above.
        # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
        "customer": identity_fixtures.customer_block(name, account_type="residential"),
    }
    if opened_at is not None:
        payload["opened_at"] = opened_at
    return customers_services.create_account(clerk, payload)


def _moved_out_on(clerk, unit_id, *, name, on):
    """A real `services.move_out` — the signed BR-CUS-030 path, never a status
    UPDATE. `closed_at` IS the move-out date; there is no second column."""
    account = _account_on(clerk, unit_id, name=name)
    customers_services.move_out(clerk, account["id"], {"moved_out_on": on})
    return customers_models.Account.objects.get(id=account["id"])


def _row_for(payload, account_no):
    return next(row for row in payload["rows"] if row["account_no"] == account_no)


def _register(answer, asset_no, channel="total"):
    meter = next(m for m in answer["meters"] if m["asset_no"] == asset_no)
    return next(r for r in meter["registers"] if r["channel"] == channel)


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE METERING SELECTOR — `apps.metering.selectors.reads_for_unit`
# ════════════════════════════════════════════════════════════════════════════
def test_w9_met__the_newest_committed_head_is_served_per_meter_with_its_unit(brazos, dana):
    """The Brazos Bend figure (EP-MET-03): M-7001 42,180 → 42,864 =
    684.000000 kWh — served as the ELECTRIC meter's head with its explicit unit
    (hard rule 3), while the WATER meter's head keeps ITS unit. Two units are
    two quantities; nothing here mixes or converts them (OQ-004's posture)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(
            dana, brazos, meters=(("M-7001", "electric", "kWh"), ("M-7002", "water", "kgal"))
        )
        commit_read(dana, _asset_id(unit, "M-7001"), day="2026-06-30", value="42180")
        newest = commit_read(
            dana,
            _asset_id(unit, "M-7001"),
            day="2026-07-31",
            value="42864",
            prior_value="42180",
            consumption="684.000000",
        )
        commit_read(
            dana,
            _asset_id(unit, "M-7002"),
            day="2026-07-15",
            value="1210",
            consumption="8.400000",
            unit="kgal",
        )

        answer = metering_selectors.reads_for_unit(unit["id"])

    assert answer["unit_id"] == str(unit["id"])
    assert answer["as_of"] is None  # no cap was asked for, none is claimed
    assert {m["asset_no"] for m in answer["meters"]} == {"M-7001", "M-7002"}

    electric = _register(answer, "M-7001")
    assert electric["read_id"] == str(newest.id)  # the NEWEST head, not the June row
    assert electric["consumption"] == "684.000000"
    assert electric["unit"] == "kWh"  # hard rule 3 — never separated
    assert electric["read_at"] == "2026-07-31"
    assert electric["source"] == "import"
    assert electric["lifecycle"] == "committed"
    assert electric["estimated"] is False

    water = _register(answer, "M-7002")
    assert (water["consumption"], water["unit"]) == ("8.400000", "kgal")

    by_no = {m["asset_no"]: m for m in answer["meters"]}
    assert by_no["M-7001"]["latest_read_at"] == "2026-07-31"
    assert by_no["M-7002"]["latest_read_at"] == "2026-07-15"


def test_w9_met__on_caps_the_answer_at_the_stated_date(brazos, dana):
    """`on` is AS-OF, not a filter convenience: the head at/limited to that
    date, so a consumer can ask what was known on the day (BR-TEN-043 — the
    event date is an argument, never a wall clock)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        july = commit_read(dana, _asset_id(unit, "M-9101"), day="2026-07-15", value="42500")
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")

        capped = metering_selectors.reads_for_unit(unit["id"], on=date(2026, 7, 31))

    assert capped["as_of"] == "2026-07-31"
    head = _register(capped, "M-9101")
    assert head["read_id"] == str(july.id)
    assert head["read_at"] == "2026-07-15"  # the August row is AFTER the date


def test_w9_met__a_superseded_row_is_never_the_head(brazos, dana, marcus):
    """BR-MET-016/053 — the correction is the answer. The supersede travels
    through the REAL `services.supersede_read` (DEF-658), and the closed row
    disappears from the seam entirely: `superseded_by_id__isnull` is the head
    set, the same `_read_heads()` every other consumer reads."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-07-15", value="42500")
        wrong = commit_read(
            dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900", prior_value="42500"
        )
        fixed = metering_services.supersede_read(
            marcus, str(wrong.id), {"value": "42876", "reason": "keying error"}
        )

        answer = metering_selectors.reads_for_unit(unit["id"])

    served = {r["read_id"] for m in answer["meters"] for r in m["registers"]}
    assert fixed["id"] in served
    assert str(wrong.id) not in served  # the closed row is INVISIBLE, not demoted
    assert _register(answer, "M-9101")["read_at"] == "2026-08-10"


def test_w9_met__two_registers_on_one_meter_are_two_entries(brazos, dana):
    """B2 r8's key is (asset, read_at, CHANNEL): a net meter's export register
    is its own measurement and is served beside `total`, never summed with it
    (rule 3 — two quantities; combining them is rating's question, OQ-001)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")
        commit_read(
            dana,
            _asset_id(unit, "M-9101"),
            day="2026-08-12",
            value="310",
            channel="export",
            consumption="310.000000",
        )

        answer = metering_selectors.reads_for_unit(unit["id"])

    meter = next(m for m in answer["meters"] if m["asset_no"] == "M-9101")
    assert {r["channel"] for r in meter["registers"]} == {"total", "export"}
    # The per-meter summary is the MAX across registers — one derivation, here.
    assert meter["latest_read_at"] == "2026-08-12"


def test_w9_met__the_unit_boundary_holds(brazos, dana):
    """Unit B's meter and its reads never appear in unit A's answer — the seam
    answers for THE unit asked about, not for the premises or the tenant."""
    with tenant_ctx(brazos):
        seed_config()
        unit_a, _ = _metered_unit(dana, brazos, label="Unit A")
        unit_b, _ = _metered_unit(
            dana, brazos, label="Unit B", meters=(("M-9201", "electric", "kWh"),)
        )
        commit_read(dana, _asset_id(unit_b, "M-9201"), day="2026-08-10", value="500")

        answer = metering_selectors.reads_for_unit(unit_a["id"])

    assert {m["asset_no"] for m in answer["meters"]} == {"M-9101"}
    assert all(m["registers"] == [] for m in answer["meters"])


def test_w9_met__tenant_isolation_a_foreign_unit_answers_empty(brazos, dana, lonestar):
    """Hard rule 1. Under the OTHER tenant's context the same unit id resolves
    to no meters and no reads — `assets_on_unit` and `_read_heads()` are both
    tenant-filtered, so a cross-tenant probe learns nothing, not even a
    meter number."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")

    with tenant_ctx(lonestar):
        answer = metering_selectors.reads_for_unit(unit["id"])

    assert answer["meters"] == []


def test_w9_met__the_estimation_marker_travels_as_a_flag(brazos, dana):
    """US-MET-014 — an estimate is a committed read AND says it is one. The
    derivation is `read_is_estimated` (status/disposition), the SAME one
    `billing_reads_for_unit` applies, extracted so the two can never drift
    (hard-won law 5)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(
            dana, brazos, meters=(("M-9101", "electric", "kWh"), ("M-9102", "electric", "kWh"))
        )
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")
        commit_read(
            dana,
            _asset_id(unit, "M-9102"),
            day="2026-08-10",
            value=None,
            consumption="120.000000",
            estimated=True,
        )

        answer = metering_selectors.reads_for_unit(unit["id"])

    assert _register(answer, "M-9101")["estimated"] is False
    assert _register(answer, "M-9102")["estimated"] is True
    # …and an estimate still carries its quantity WITH its unit (rule 3).
    assert _register(answer, "M-9102")["consumption"] == "120.000000"
    assert _register(answer, "M-9102")["unit"] == "kWh"


def test_w9_met__one_reads_query_however_many_meters(brazos, dana):
    """DEF-324's discipline: the heads come back in ONE `meter_reads` query for
    the whole unit — never a query per meter. The assets side of the answer is
    the published `assets_on_unit` seam and is not re-counted here; the
    assertion is about the table THIS selector reads."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(
            dana,
            brazos,
            meters=(
                ("M-9101", "electric", "kWh"),
                ("M-9102", "electric", "kWh"),
                ("M-9103", "water", "kgal"),
            ),
        )
        for asset_no, day in (
            ("M-9101", "2026-08-01"),
            ("M-9102", "2026-08-02"),
            ("M-9103", "2026-08-03"),
        ):
            unit_of_measure = "kgal" if asset_no == "M-9103" else "kWh"
            commit_read(dana, _asset_id(unit, asset_no), day=day, value="100", unit=unit_of_measure)

        with CaptureQueriesContext(connection) as captured:
            answer = metering_selectors.reads_for_unit(unit["id"])

    assert len(answer["meters"]) == 3
    reads_queries = [q for q in captured.captured_queries if "meter_reads" in q["sql"]]
    assert len(reads_queries) == 1, [q["sql"] for q in reads_queries]


def _asset_id(unit, asset_no):
    """The fixture's meter id, read back through the published assets seam so
    the test never touches the assets ORM either."""
    from apps.metering import seams as metering_seams

    for row in metering_seams.assets_on_unit(unit["id"]):
        if row["asset_no"] == asset_no:
            return row["id"]
    raise AssertionError(f"{asset_no} is not on {unit['id']}")


# ════════════════════════════════════════════════════════════════════════════
# 2 · THE CUSTOMERS CONSUMERS — the seam, the two cells, the tile
# ════════════════════════════════════════════════════════════════════════════
def test_w9_cus__the_seam_resolves_the_metering_selector_by_name(brazos, dana):
    """B1/B8 — customers asks, it never joins. `customers_seams.reads_for_unit`
    late-binds `apps.metering.selectors.reads_for_unit` (the KIND named
    explicitly — DEF-035's two-words-wrong lesson) and hands back the owning
    module's own answer."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")

        answer = customers_seams.reads_for_unit(unit["id"])
        capped = customers_seams.reads_for_unit(unit["id"], on=date(2026, 7, 31))

    assert answer is not None and {m["asset_no"] for m in answer["meters"]} == {"M-9101"}
    assert answer["meters"][0]["latest_read_at"] == "2026-08-10"
    assert capped["as_of"] == "2026-07-31"
    assert capped["meters"][0]["registers"] == []  # nothing was known by July 31


def test_w9_cus__final_reads_due_becomes_the_real_count(brazos, dana, marcus):
    """⛔ **THE RED-FIRST CASE THIS LANE EXISTS FOR** (hard-won law 7).

    One move-out whose unit holds TWO meters — the electric one read ON the
    closing date, the water one last read before it — is DUE a final read. A
    second move-out, fully read on its closing date, is not. The tile serves
    **1**, a real count, where it served `None` with *"no read seam"*.

    **RED PROVED FIRST against the stated-absence behaviour** — this test was
    run 2026-08-26 on the tree with the seam PUBLISHED (both halves green) and
    `move_reads` still unwired, and failed on exactly the absence it replaces,
    verbatim:

        >       assert kpis["final_reads_due"] == 1
        E       assert None == 1
        tests/test_w9_reads_seam.py:433: AssertionError
        FAILED tests/test_w9_reads_seam.py::test_w9_cus__final_reads_due_becomes_the_real_count

    `due` here is the wired definition, exactly: a committed read exists
    at/after the move-out date for every meter on the unit → taken; any meter
    without one → due. (`closed_at` IS the move-out date — BR-CUS-030.)
    """
    with tenant_ctx(brazos):
        seed_config()
        half_read_unit, _ = _metered_unit(
            dana, brazos, meters=(("M-7001", "electric", "kWh"), ("M-7002", "water", "kgal"))
        )
        commit_read(dana, _asset_id(half_read_unit, "M-7001"), day="2026-08-20", value="43566")
        commit_read(
            dana,
            _asset_id(half_read_unit, "M-7002"),
            day="2026-07-31",
            value="1210",
            unit="kgal",
        )
        due = _moved_out_on(marcus, half_read_unit["id"], name="Fitzgerald, Sean", on="2026-08-20")

        fully_read_unit, _ = _metered_unit(
            dana, brazos, label="Unit B", meters=(("M-9201", "electric", "kWh"),)
        )
        commit_read(dana, _asset_id(fully_read_unit, "M-9201"), day="2026-08-21", value="9000")
        settled = _moved_out_on(
            marcus, fully_read_unit["id"], name="Delgado, Pilar", on="2026-08-21"
        )

        kpis = move_reads.move_out_kpis(as_of=TODAY)

    assert kpis["final_reads_due"] == 1
    # Served ⇒ no absence rides beside the figure. (`None`, not a dict.)
    assert kpis["final_reads_due_unavailable"] is None
    # The count means what it says, and says what it means — the
    # `open_means` precedent, applied to the new tile.
    assert kpis["final_reads_due_means"] == "closed_move_outs_with_a_meter_unread_since_close"
    assert due.account_no != settled.account_no  # the fixture really is two jobs


def test_w9_cus__the_final_read_cell_serves_taken_and_due_and_names_the_missing_meter(
    brazos, dana, marcus
):
    """B18 §5.6.2's FINAL READ cell, wired: `due` while any meter lacks a
    committed read at/after `closed_at`, with the unread meter NAMED — a clerk
    acts on a meter number, not on a boolean — and `taken` the moment the last
    one is read."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(
            dana, brazos, meters=(("M-7001", "electric", "kWh"), ("M-7002", "water", "kgal"))
        )
        commit_read(dana, _asset_id(unit, "M-7001"), day="2026-08-20", value="43566")
        gone = _moved_out_on(marcus, unit["id"], name="Fitzgerald, Sean", on="2026-08-20")

        before = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]
        commit_read(dana, _asset_id(unit, "M-7002"), day="2026-08-20", value="1219", unit="kgal")
        after = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]

    assert before["state"] == "due"
    assert before["measured_against"] == "2026-08-20"
    assert (before["meters_total"], before["meters_read"]) == (2, 1)
    assert before["missing"] == ["M-7002"]

    assert after["state"] == "taken"
    assert after["missing"] == []
    assert (after["meters_total"], after["meters_read"]) == (2, 2)


def test_w9_cus__estimated_serves_off_the_settlements_own_stored_flag(brazos, dana, marcus):
    """✅ **`estimated` SERVES NOW — off `accounts.final_read_state`, W9 task 4.**

    ⚠ AMENDED 2026-08-26 (the same lane, task 4): until this commit the case
    was `test_w9_cus__estimated_stays_a_stated_absence_with_the_narrowed_reason`
    and pinned `state == "taken"` + the `estimated_state_has_no_settlement_flag`
    absence — TC-MVO-7's truth while `move_out_settlement` had no how-obtained
    store. **That pinned case IS the red-first proof of the retire** (hard-won
    law 7): run unchanged against the task-4 code it failed
    `AssertionError: assert 'estimated' == 'taken'` — the flag derivation had
    gone live end to end before a single assertion here was touched.

    The new truth: the covering head IS an estimate, so `services.move_out`
    derives `final_read_state == "estimated"` at close (ONE seam sweep, shared
    with the BR-CUS-031 handoff), stores it beside `closed_at`, and the FINAL
    READ cell says B18 §5.6.2's amber third word off THAT flag — never off
    live history, which still derives `taken` (a committed estimate is a
    committed read). No absence rides a flagged close."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(
            dana,
            _asset_id(unit, "M-9101"),
            day="2026-08-20",
            value=None,
            consumption="120.000000",
            estimated=True,
        )
        gone = _moved_out_on(marcus, unit["id"], name="Ngata, Rewi", on="2026-08-20")

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]

    assert gone.final_read_state == "estimated"  # derived at close, stored
    assert cell["state"] == "estimated"  # B18's amber third state, live
    assert cell["unavailable"] is None  # a flagged close carries no absence
    # The derived counts still serve beside the flag — the estimate covers.
    assert (cell["meters_total"], cell["meters_read"]) == (1, 1)


def test_w9_cus__a_flagless_close_states_final_read_state_not_recorded(brazos, dana, marcus):
    """⛔ **A CLOSE THE COLUMN NEVER SAW IS NOT GUESSED ABOUT (task 4's residue).**

    A pre-column close carries `final_read_state` NULL. The cell still serves
    the LIVE derived `taken`/`due` — history is readable — and
    `final_read_state_not_recorded` rides beside it: whether THE SETTLEMENT
    consumed an estimate was never recorded for this row, and the cell will
    not invent the answer (DEF-127's posture, pointed at the amber word)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-20", value="43566")
        gone = _moved_out_on(marcus, unit["id"], name="Okafor, Ada", on="2026-08-20")
        # The pre-column shape: a close that predates migration 0026.
        customers_models.Account.objects.filter(id=gone.id).update(final_read_state=None)

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]

    assert cell["state"] == "taken"  # live history still derives
    assert cell["unavailable"]["code"] == "final_read_state_not_recorded"
    assert "NULL" in cell["unavailable"]["detail"]


def test_w9_cus__an_unresolved_seam_is_still_the_stated_absence(brazos, dana, marcus, monkeypatch):
    """DEF-075/DEF-127 — a deployment where metering publishes no selector goes
    back to REPORTING, under the SAME code the tabs already speak
    (`unit_reads_not_readable_from_customers`), never to a guess and never to a
    zero. The `_ledger_says(available=False)` posture, applied to reads."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-20", value="43566")
        gone = _moved_out_on(marcus, unit["id"], name="Fitzgerald, Sean", on="2026-08-20")

        monkeypatch.setattr(move_reads.seams, "reads_for_unit", lambda *_a, **_k: None)

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]
        kpis = move_reads.move_out_kpis(as_of=TODAY)

    assert cell["state"] is None
    assert cell["unavailable"]["code"] == "unit_reads_not_readable_from_customers"
    # The sentence now names the RESOLUTION failing, not a seam that is missing.
    assert "apps.metering.selectors.reads_for_unit" in str(cell["unavailable"]["wanted_reads"])
    assert kpis["final_reads_due"] is None  # ⛔ not 0 — DEF-127
    assert kpis["final_reads_due_unavailable"]["code"] == "unit_reads_not_readable_from_customers"


def test_w9_cus__a_meterless_unit_is_an_exception_not_a_verdict(brazos, marcus):
    """A unit with nothing to read gets NO `taken`/`due`: `taken` over zero
    meters is vacuously true and reads as "the reads are in"; `due` sends a
    clerk to a meter that does not exist. The cell states the configuration
    fact (`billing`'s READ_ABSENT_NO_METER posture), and the tile EXCLUDES the
    account while serving the exclusion count beside the figure — so the `0` a
    meterless fixture produces is a different sentence from "every meter has
    been read"."""
    with tenant_ctx(brazos):
        # The W5 worklist suite's own shape: a real unit, a plan, a service
        # point — and NO meter.
        premises = make_premises(marcus, services_available=["electric"])
        unit = make_unit(marcus, premises["id"], label="Unit A")
        metering_services.assign_unit_plan(marcus, unit["id"], {"tariff_id": str(_plan(brazos).id)})
        metering_services.ensure_service_point(unit["id"], "electric")
        gone = _moved_out_on(marcus, unit["id"], name="Sandoval, Rita", on="2026-08-20")

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["final_read"]
        kpis = move_reads.move_out_kpis(as_of=TODAY)

    assert cell["state"] is None
    assert cell["unavailable"]["code"] == "unit_has_no_meters"
    assert kpis["final_reads_due"] == 0
    assert kpis["final_reads_due_unavailable"] is None
    # …and the zero is qualified: one move-out could not be measured AT ALL.
    assert kpis["final_reads_due_meterless"] == 1


def test_w9_cus__the_move_in_reads_cell_measures_against_the_start_date(brazos, dana, marcus):
    """B18 §5.5.2's READS cell (`taken`/`due` — TWO states on this tab): due
    until every meter has a committed read at/after the move-in date, taken
    after. No remaining absence rides on a served move-in cell — `estimated`
    is a FINAL READ state, not a READS one."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        booked = _account_on(
            marcus,
            unit["id"],
            name="Kwan, Michael",
            status="pending_activation",
            opened_at="2026-08-20",
        )

        before = _row_for(move_reads.move_ins_list(as_of=TODAY), booked["account_no"])["reads"]
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-20", value="42900")
        after = _row_for(move_reads.move_ins_list(as_of=TODAY), booked["account_no"])["reads"]

    assert before["state"] == "due"
    assert before["missing"] == ["M-9101"]
    assert after["state"] == "taken"
    assert after["measured_against"] == "2026-08-20"
    assert after["unavailable"] is None


def test_w9_cus__a_move_in_with_no_date_has_nothing_to_measure_against(brazos, dana, marcus):
    """BR-CUS-022's `waiting` row cannot take a `taken`/`due`: the state is
    measured AGAINST the move-in date and there is none — the same missing fact
    that blocks activation blocks this cell, and the absence says so instead of
    silently measuring against today (BR-TEN-043)."""
    with tenant_ctx(brazos):
        seed_config()
        unit, _made = _metered_unit(dana, brazos)
        commit_read(dana, _asset_id(unit, "M-9101"), day="2026-08-10", value="42900")
        waiting = _account_on(
            marcus,
            unit["id"],
            name="Alvarez, Rosa",
            status="pending_activation",
            opened_at=None,
        )

        cell = _row_for(move_reads.move_ins_list(as_of=TODAY), waiting["account_no"])["reads"]

    assert cell["state"] is None
    assert cell["unavailable"]["code"] == "reads_state_needs_a_service_start_date"
