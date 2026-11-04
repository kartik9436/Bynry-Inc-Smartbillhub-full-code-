# ── Trace ──────────────────────────────────────────────
# Change:  CR-089 wave F · `F3` (the four tiles belong to the PAGE) and `F6`
#          (`PUJ-44`/`PUJ-45` — a unit has an edit screen, and the plan is
#          applied or changed from that same form).
# Rules:   BR-MET-007 / BR-CUS-014 (a unit's default plan) · BR-MET-040 (the
#          plan lock) · BR-MET-042 (a plan edit on an OCCUPIED unit is an
#          error-correction OVERRIDE the server WARNS about) · BR-RAT-030 (an
#          unpublished plan is not assignable) · BR-CUS-013 (the dated,
#          append-only assignment history) · BR-MET-046 (a unit never moves
#          premises) · BR-AST-004 (the asset category that splits the tile) ·
#          DEF-075 (a null count is *could not ask*, never 0) ·
#          DEF-127 / DEF-138 (a null balance is never 0.00) ·
#          CLAUDE.md law 7 (proved RED on the real fault, in this harness).
# ───────────────────────────────────────────────────────
"""What `GET /units/{id}` now serves, and what a PATCH carrying a plan does.

**THE DEFECT THIS FILE EXISTS TO PIN IS A SILENT DROP ON A MONEY PATH.**
`services._validate_unit` has carried `"plan"` in its `ignored` set since S16,
so that the CREATE payload could be handed to it whole. On a PATCH nothing then
read it: `PATCH /units/{id}` with a plan block answered **200**, changed the
label, left the plan exactly where it was, and said nothing about it. A form
that offered a plan picker and posted through that endpoint would have looked
like it worked, on every screen, for every clerk, forever — `DEF-836`'s
silent-drop shape, on the field that decides what a unit is billed.

⚠ **AND THE OTHER HALF IS THAT THE PLAN GOES THROUGH `_apply_unit_plan` AND NOT
THROUGH A SECOND WRITER.** That function owns `BR-MET-040`'s lock guard,
`BR-RAT-030`'s unpublished refusal, `BR-MET-042`'s occupied-unit warning and
`BR-CUS-013`'s history row. The test asserting the HISTORY ROW is the one that
would notice a re-implementation: a second writer that set `units.rate_plan_id`
directly would satisfy every other assertion here and leave the unit's plan
history with a hole in it, which shows up months later inside a bill.
"""

from datetime import date

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _unit_with_plan(dana, brazos):
    premises = make_premises(dana, address_line="1408 Elm Street")
    unit = make_unit(dana, premises["id"], label="Apt 101")
    plan = make_plan(brazos, name="Residential Standard", code="RES-STD")
    return unit, plan


# ═══════════════════════════════════════════════════════════════════════════
# F6 — the plan rides the PATCH
# ═══════════════════════════════════════════════════════════════════════════


def test_patch_applies_the_nested_plan_block(dana, brazos):
    """The whole of `PUJ-45`: one write carries the fields AND the plan."""
    with tenant_ctx(brazos):
        unit, plan = _unit_with_plan(dana, brazos)
        assert unit["rate_plan_id"] is None

        answer = services.update_unit(
            dana,
            unit["id"],
            {
                "label": "2B",
                "square_feet": "820",
                "plan": {"tariff_id": str(plan.id), "effective_from": "2026-06-01"},
            },
        )

        assert answer["label"] == "2B"
        assert answer["square_feet"] == 820
        # The plan moved, and the row says so.
        assert answer["rate_plan_id"] == str(plan.id)
        assert answer["plan_effective_from"] == "2026-06-01"
        # The server's own `plan_assignment` block is forwarded so the form can
        # show `BR-MET-042`'s warning without deciding anything itself.
        assert "plan_assignment" in answer


def test_patch_without_a_plan_block_carries_no_plan_key_at_all(dana, brazos):
    """*I did not ask* and *I asked and nothing came back* are different states.

    Collapsing them is how a screen comes to report an override warning it never
    received — so the key is ABSENT rather than `None` when no plan was sent.
    """
    with tenant_ctx(brazos):
        unit, _plan = _unit_with_plan(dana, brazos)
        answer = services.update_unit(dana, unit["id"], {"label": "2C"})
        assert "plan_assignment" not in answer
        assert answer["rate_plan_id"] is None


def test_the_plan_change_writes_the_BR_CUS_013_history_row(dana, brazos):
    """⚠ **THE ASSERTION THAT CATCHES A SECOND WRITER.**

    A re-implementation that set `units.rate_plan_id` directly would pass every
    other test in this file and leave `unit_plan_assignments` empty — and a hole
    in that table is not visible until a mid-cycle plan change has to be priced,
    months later, inside a bill.
    """
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        unit, plan = _unit_with_plan(dana, brazos)
        services.update_unit(
            dana,
            unit["id"],
            {"label": "2B", "plan": {"tariff_id": str(plan.id), "effective_from": "2026-06-01"}},
        )
        rows = list(
            rating_models.UnitPlanAssignment.objects.filter(
                tenant_id=brazos.id, unit_id=unit["id"]
            )
        )
        assert len(rows) == 1
        assert str(rows[0].rate_plan_id) == str(plan.id)
        assert rows[0].assigned_from == date(2026, 6, 1)
        # ⚠ `change_plan` — an EXISTING value of the column's own documented
        # vocabulary (`new_connection|move_in|change_plan|bulk_update|import`),
        # never a sixth word minted for this form. A word nobody ruled in a
        # signed history table is a word every later reader has to guess at.
        assert rows[0].source == "change_plan"


def test_an_unknown_plan_is_refused_and_the_label_change_goes_back_with_it(dana, brazos):
    """One transaction. `BR-RAT-030` refuses; the rename must not survive it.

    Two calls behind one Save button would leave the clerk with a RENAMED unit,
    an error message about a plan, and no way to tell which half landed.
    """
    from core import errors

    with tenant_ctx(brazos):
        unit, _plan = _unit_with_plan(dana, brazos)
        with pytest.raises(errors.ValidationError):
            services.update_unit(
                dana,
                unit["id"],
                {
                    "label": "RENAMED",
                    "plan": {"tariff_id": "00000000-0000-4000-8000-000000000000"},
                },
            )
        after = models.Unit.objects.get(pk=unit["id"])
        assert after.label == "Apt 101"
        assert after.rate_plan_id is None


def test_the_premises_is_still_refused_by_name_on_a_patch_that_carries_a_plan(dana, brazos):
    """`BR-MET-046` is not weakened by the new block."""
    from core import errors

    with tenant_ctx(brazos):
        unit, plan = _unit_with_plan(dana, brazos)
        other = make_premises(dana, address_line="9 Elsewhere Rd")
        with pytest.raises(errors.BizError):
            services.update_unit(
                dana,
                unit["id"],
                {"premises_id": other["id"], "plan": {"tariff_id": str(plan.id)}},
            )


# ═══════════════════════════════════════════════════════════════════════════
# F3 — the three tile figures ride the payload the page already asks for
# ═══════════════════════════════════════════════════════════════════════════


def test_unit_page_dict_carries_the_three_tile_figures(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1408 Elm Street")
        unit = make_unit(dana, premises["id"], label="Apt 101")
        row = selectors.unit_page_dict(models.Unit.objects.get(pk=unit["id"]))
        assert set(row["assets"]) == {"total", "bills", "behind"}
        assert row["open_work"]["count"] == 0
        # `owed` is `None` for a unit with no OCCUPYING account — absent from
        # the map, never `0.00` (`DEF-138`).
        assert row["owed"] is None


def test_the_units_list_row_is_untouched_by_the_tile_figures(dana, brazos):
    """⚠ **THE COST CHECK, AND IT IS THE POINT OF `unit_page_dict` EXISTING.**

    `CR-089` §5 flags the tiles as *"the one ruling in this CR whose cost grows
    with tenant size"*. The three figures are served by the DETAIL endpoint and
    by nothing else, so a 133-row units list, the create's answer, the audit
    `before`/`after` payloads and every internal caller pay nothing at all. A
    lane that later moved them into `unit_list_dict` for tidiness would put a
    ledger read and a work-order count into every row of the busiest list on
    this screen — `DEF-2723`'s shape, which was six per-row reads and a 562 ms
    page nobody had measured.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1408 Elm Street")
        unit = make_unit(dana, premises["id"], label="Apt 101")
        row = selectors.unit_list_dict(models.Unit.objects.get(pk=unit["id"]))
        assert "assets" not in row
        assert "open_work" not in row


def test_the_asset_tile_splits_on_the_servers_own_category(dana, brazos):
    """`BR-AST-004`'s category, never a guess from the type code.

    A row whose category did not arrive is counted in the TOTAL and in neither
    half: forcing an unknown into *behind the meter* would say *we own it and
    never read it* about a meter.
    """
    tile = selectors._asset_tile(
        [
            {"asset_no": "E-1", "tab": "meters"},
            {"asset_no": "SM-1", "tab": "sub_meters"},
            {"asset_no": "CART-1", "tab": "behind_the_meter"},
            {"asset_no": "MYSTERY", "tab": None},
        ]
    )
    assert tile == {"total": 4, "bills": 2, "behind": 1}


def test_assets_on_unit_publishes_the_category_it_splits_on(dana, brazos):
    """The seam the tile reads. Without `tab` on the row the split is a guess."""
    from apps.assets import selectors as asset_selectors

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1408 Elm Street")
        unit = make_unit(dana, premises["id"], label="Apt 101")
        # ⚠ `install_date` is REQUIRED for an asset that lands ON a unit —
        # `assets.services` refuses `assets.install_date_required` otherwise.
        # The shared helper's default is a spare left in INVENTORY, which needs
        # none; this is the fitted case and it has to say when it was fitted.
        asset = make_asset(  # noqa: F405 — shared fixture
            dana,
            asset_no="M-CR89F",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        rows = asset_selectors.assets_on_unit(unit["id"])
        assert rows, "the fixture asset should be assigned to the unit"
        # The field the tile splits on. Without it the split is a guess from a
        # type code, which breaks the first time a tenant adds a type of their
        # own (`BR-TEN-036` says they may).
        assert all("tab" in row for row in rows)
        assert {row["tab"] for row in rows} <= {"meters", "sub_meters", "behind_the_meter"}
        assert asset is not None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave F · F3 · F6 (`PUJ-44`, `PUJ-45`)
# generated: 2026-09-09 by the CR-089 wave F build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# exceptions: E3 the OPEN-WORK count is asserted as 0 rather than as a positive
#   number — no fixture in this suite raises a work order on a unit, and a test
#   that built one would be asserting the work module's own create path rather
#   than this seam. The non-zero case is proved in the browser walkthrough on
#   `SCW-U-307`, which carries a planned order, and the figure is quoted there
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
