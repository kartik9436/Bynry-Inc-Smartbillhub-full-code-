# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-577 (the `unit` number series stands BEHIND the units that
#           already exist, so the next "Add unit" fails with a duplicate key) —
#           and the same fault on `premises`, reached through the CR-023 import
# Rules:    BR-TEN-035 (a number is NEVER reused; gaps are fine; next-number
#           moves are FORWARD-ONLY) · BR-TEN-043 (the issue date is an explicit
#           input, never the wall clock) · BR-MET-001 (premises/unit numbering)
# Decision: 12-governance/02-decision-log.md — DEF-577 catch-up ruling
#           Screens: S16 (Add premise / Add unit) · WFL-01 stage 4 (load)
# ───────────────────────────────────────────────────────
"""THE INVARIANT: a series must never hand out a number that already exists.

Two paths write a premises/unit number WITHOUT allocating it from the tenant's
series — a caller-supplied `unit_no` (the BR-TEN-063 sample plant does exactly
this, 48 units of it) and the CR-023 import load stage, which writes the
CUSTOMER'S OWN numbers straight from their CSV. Both leave the counter standing
behind data that already exists, and the first ordinary "Add unit" afterwards
walks the counter into a row that is already there.

PROVED RED FIRST (hard-won law 7). Against the code as it stood on 2026-08-22,
`test_add_unit_after_a_caller_supplied_number_does_not_collide` reported:

    E   django.db.utils.IntegrityError: duplicate key value violates unique
        constraint "uq_units_tenant_unit_no"
        DETAIL:  Key (tenant_id, unit_no)=(..., U-00101) already exists.

which is the customer-facing 500 the defect row measured on the demo database
(there at `U-00102`, with units up to `U-00420` already on file). The premises
case reported the same failure against `uq_premises_tenant_no`.
"""

import pytest

from apps.metering import models
from apps.tenancy import models as tenancy_models
from core import numbering as core_numbering

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _series(tenant, series):
    return tenancy_models.NumberSeries.objects.get(tenant=tenant, series=series)


def _open_at(tenant, series, position):
    """Put the counter at a known place. FORWARD only, like every real edit —
    the fixtures open both series at 101 and the provisioned sample plant has
    already drawn on `premises`, so a test that assumed 101 would be measuring
    the fixture rather than the fix.
    """
    row = _series(tenant, series)
    assert position >= row.next_number, "test setup may only move a counter forward"
    tenancy_models.NumberSeries.objects.filter(pk=row.pk).update(next_number=position)
    return position


# ═══════════════════════════════════════════════════════════════════════════
# THE REPRODUCTION — units
# ═══════════════════════════════════════════════════════════════════════════


def test_add_unit_after_a_caller_supplied_number_does_not_collide(brazos, dana):
    """DEF-577, in its shipped shape: the sample plant names its own unit
    numbers, so the series never advances past them.

    The test fixtures open both series at 101, so `U-00101` is the number the
    series would hand out next. Writing it under its own name first is what a
    seeded or imported tenant looks like.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _open_at(brazos, "unit", 500)
        make_unit(dana, premises["id"], label="Unit A", unit_no="U-00500")

        result = make_unit(dana, premises["id"], label="Unit B")

        assert result["unit_no"] == "U-00501"
        assert models.Unit.objects.filter(unit_no="U-00501").count() == 1
        # forward-only, and past everything that exists (BR-TEN-035)
        assert _series(brazos, "unit").next_number == 502


def test_the_catch_up_clears_a_whole_block_in_one_move(brazos, dana):
    """The demo database's real shape: 300-odd numbers already on file and a
    counter far behind them. The repair is ONE forward move, not one per
    collision — an operator does not click through 300 failures."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _open_at(brazos, "unit", 500)
        for n in range(500, 540):
            make_unit(dana, premises["id"], label=f"Unit {n}", unit_no=f"U-{n:05d}")
        assert (
            _series(brazos, "unit").next_number == 500
        ), "a caller-supplied number must not consume one from the series"

        result = make_unit(dana, premises["id"], label="Unit Z")

        assert result["unit_no"] == "U-00540"
        assert _series(brazos, "unit").next_number == 541


def test_a_number_in_the_customers_own_format_is_left_alone(brazos, dana):
    """`SCW-U-001` cannot be rendered by `U-{00000}` at any counter value, so
    it can never collide and must not drag the counter anywhere.

    This is the sample plant's own numbering (BR-TEN-063 writes 48 of them).
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _open_at(brazos, "unit", 500)
        make_unit(dana, premises["id"], label="Unit A", unit_no="SCW-U-901")

        result = make_unit(dana, premises["id"], label="Unit B")

        assert result["unit_no"] == "U-00500"
        assert _series(brazos, "unit").next_number == 501


# ═══════════════════════════════════════════════════════════════════════════
# THE SAME FAULT ON PREMISES
# ═══════════════════════════════════════════════════════════════════════════


def test_add_premise_after_an_imported_premise_number_does_not_collide(brazos, dana):
    """`create_premises` always allocates, so only a path that WRITES a
    premise_no can put the counter behind — which is what the CR-023 import
    does. Written here the way the load stage writes it: straight to the model.
    """
    with tenant_ctx(brazos):
        _open_at(brazos, "premises", 500)
        models.Premises.objects.create(
            tenant_id=brazos.id,
            premise_no="P-00500",
            address_line="9 Imported Row",
            city="Katy",
            premises_type=models.PremisesType.objects.filter(code="single_family").first(),
            status="active",
        )

        result = make_premises(dana, address_line="10 Fresh St")

        assert result["premise_no"] == "P-00501"
        assert models.Premises.objects.filter(premise_no="P-00501").count() == 1
        assert _series(brazos, "premises").next_number == 502


# ═══════════════════════════════════════════════════════════════════════════
# THE KERNEL PARSER — the thing that decides what "already exists" means
# ═══════════════════════════════════════════════════════════════════════════


def test_sequence_of_reads_back_exactly_what_render_wrote():
    from datetime import date

    day = date(2026, 8, 22)
    for fmt in ("U-{00000}", "{00000}", "P-{YYYY}-{0000}", "AC-{YY}{MM}-{000}"):
        for seq in (1, 7, 420, 99999, 1234567):
            rendered = core_numbering.render(fmt, seq, day)
            assert core_numbering.sequence_of(fmt, rendered, day) == seq, fmt


def test_sequence_of_refuses_anything_this_format_could_not_have_written():
    from datetime import date

    day = date(2026, 8, 22)
    assert core_numbering.sequence_of("U-{00000}", "SCW-U-001", day) is None
    assert core_numbering.sequence_of("U-{00000}", "U-00420X", day) is None
    assert core_numbering.sequence_of("U-{00000}", "", day) is None
    assert core_numbering.sequence_of("U-{00000}", None, day) is None
    # a DIFFERENT issue date renders different literals, so it is a different
    # number and cannot collide with today's (BR-TEN-043)
    assert core_numbering.sequence_of("P-{YYYY}-{0000}", "P-2025-0007", day) is None
    assert core_numbering.sequence_of("P-{YYYY}-{0000}", "P-2026-0007", day) == 7
