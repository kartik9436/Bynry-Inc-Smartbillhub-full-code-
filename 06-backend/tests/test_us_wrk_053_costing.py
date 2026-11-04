"""US-WRK-053 — the report's arithmetic, `BR-WRK-051`.

⚠ **THESE ARE THE TESTS THE RULE ASKS FOR BY NAME.** `BR-WRK-051` is PROPOSED
and says *"one test pins the figure and pins that 4-decimal hours would give
`42.03`"*. TC-1 and TC-2 are that pair, and they are deliberately pure
arithmetic — no fixture, no tenant, no migration — so they fail for arithmetic
reasons only. A worked figure guarded by a test that needs a database is a
worked figure that goes quiet the first time the database is awkward.
"""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from apps.work import costing

FIELD_TECH = Decimal("48.5000")
OVERTIME = Decimal("72.7500")


def _wo_4822():
    """`WO-4822` — a meter exchange, on site 15:15–16:07, one meter, one seal."""
    return (
        costing.LabourInput(minutes=52, role_label="Field technician", rate=FIELD_TECH),
        [
            costing.PartInput("MTR-E1P", Decimal("1"), "each", Decimal("96.0000")),
            costing.PartInput("SEAL-01", Decimal("1"), "each", Decimal("0.2200")),
        ],
    )


def test_tc1_the_worked_figure_is_138_42():
    """TC-1 — three lines, and the total a reader reaches by adding them.

    *Labour · Field technician · 0.87 h · 48.5000 · 42.20* · *Part · MTR-E1P ·
    1 · 96.0000 · 96.00* · *Part · SEAL-01 · 1 · 0.2200 · 0.22*; stored amounts
    `42.1950 · 96.0000 · 0.2200`; total `138.42`.
    """
    labour, parts = _wo_4822()
    lines, total = costing.compute(labour, parts)

    assert [line.kind for line in lines] == ["labour", "part", "part"]
    # the HOURS the report prints, and the same value that was multiplied
    assert lines[0].qty == Decimal("0.87")
    assert lines[0].unit == "h"
    assert lines[0].rate == FIELD_TECH
    # stored to FOUR (hard rule 2), shown to TWO
    assert lines[0].amount == Decimal("42.1950")
    assert lines[0].display_amount == Decimal("42.20")
    assert [line.amount for line in lines[1:]] == [Decimal("96.0000"), Decimal("0.2200")]
    assert [line.display_amount for line in lines[1:]] == [Decimal("96.00"), Decimal("0.22")]

    assert total == Decimal("138.42")
    # and it is the sum of what is PRINTED — the rule, stated as arithmetic
    assert total == sum(line.display_amount for line in lines)


def test_tc2_four_decimal_hours_would_give_42_03_and_that_is_why_two():
    """TC-2 — the counter-case. The rounding point is part of the rule.

    At four-decimal hours `0.8667 × 48.5 = 42.03`, seventeen cents from the
    `42.20` that ships. This test exists so that "improving the precision"
    fails loudly instead of quietly moving every labour line in the product.
    """
    four_dp_hours = (Decimal(52) / Decimal(60)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    assert four_dp_hours == Decimal("0.8667")
    would_be = (four_dp_hours * FIELD_TECH).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert would_be == Decimal("42.03")

    labour, _ = _wo_4822()
    lines, _ = costing.compute(labour, [])
    assert lines[0].display_amount == Decimal("42.20")
    assert lines[0].display_amount != would_be
    assert costing.HOURS_PLACES == Decimal("0.01")


def test_tc3_there_is_no_tax_line_anywhere_in_the_costing_path():
    """TC-3 — `BR-WRK-052`, PO 2026-09-03: *"Dont add Tax on work order"*.

    The wireframe totals `149.84` with `8.65` and `2.77` of tax on it. Nothing
    here produces a tax line, no cost-line kind can hold one, and the module's
    only mentions of the word are the paragraphs explaining why there is none.
    """
    labour, parts = _wo_4822()
    lines, total = costing.compute(labour, parts)
    assert all(line.kind in ("labour", "overtime", "part") for line in lines)
    assert not any("tax" in line.kind.lower() for line in lines)
    assert not any("tax" in line.description.lower() for line in lines)
    assert total == Decimal("138.42")
    # the figure that is NOT computed, pinned so nobody reconstructs it
    assert total != Decimal("149.84")

    source = Path(costing.__file__).read_text()
    body = source.split('"""', 2)[2]  # past the module docstring's explanation
    for forbidden in ("KIND_TAX", "tax_rate", "tax_amount", "add_tax"):
        assert forbidden not in body, forbidden


def test_tc9_overtime_is_two_lines_at_two_prices():
    """TC-9 — nine hours on an eight-hour threshold: `388.00 + 72.75 = 460.75`.

    Two lines and not one blended rate, because that is what a reader must be
    able to check and because overtime is a price a manager may want to see.
    """
    lines, total = costing.compute(
        costing.LabourInput(
            minutes=9 * 60,
            role_label="Field technician",
            rate=FIELD_TECH,
            overtime_rate=OVERTIME,
            overtime_after_hours=Decimal("8"),
        ),
        [],
    )
    assert [line.kind for line in lines] == ["labour", "overtime"]
    assert (lines[0].qty, lines[0].display_amount) == (Decimal("8.00"), Decimal("388.00"))
    assert (lines[1].qty, lines[1].display_amount) == (Decimal("1.00"), Decimal("72.75"))
    assert total == Decimal("460.75")


def test_us_wrk_051_tc5_a_contractor_has_one_rate_and_no_overtime():
    """`BR-WRK-020` — *"an agency invoices its own overtime… the dash is the
    honest value."* Nine hours for a contractor is ONE line, not two."""
    lines, total = costing.compute(
        costing.LabourInput(minutes=9 * 60, role_label="Contractor", rate=Decimal("95.0000")),
        [],
    )
    assert len(lines) == 1
    assert lines[0].kind == "labour"
    assert total == Decimal("855.00")


def test_a_part_planned_and_not_used_produces_no_cost_line():
    """`US-WRK-050` TC-2 — *0 of 1 · not used* is a real outcome kept on the
    SCREEN. It is not a cost line of `$0.00`, which would print as *free*."""
    lines, total = costing.compute(
        None, [costing.PartInput("GSKT-STD", Decimal("0"), "each", Decimal("1.5000"))]
    )
    assert lines == []
    assert total == Decimal("0.00")


def test_an_order_with_no_rate_snapshot_yields_no_labour_line_not_a_zero_one():
    """A report reading *Labour · 0.87 h · $0.00* states the work was free.
    Not stating it is the better answer, so the line is absent."""

    class _Order:
        labour_rate_snapshot = None
        labour_role = "field_technician"
        minutes_on_site = 52
        materials = None

    lines, total = costing.work_order_cost_lines(_Order())
    assert lines == []
    assert total == Decimal("0.00")


def test_the_total_is_the_sum_of_rounded_lines_not_a_rounded_sum():
    """The rule, on a case where the two DIFFER — `WO-4822`'s own figures agree
    by luck (`138.4150` rounds to `138.42` either way), which is exactly why
    this needs its own case. Three lines of `0.005` each: rounded first they
    are `0.01 × 3 = 0.03`; summed first they are `0.015 → 0.02`."""
    parts = [costing.PartInput(f"P{i}", Decimal("1"), "each", Decimal("0.0050")) for i in range(3)]
    lines, total = costing.compute(None, parts)
    assert [line.amount for line in lines] == [Decimal("0.0050")] * 3
    assert [line.display_amount for line in lines] == [Decimal("0.01")] * 3
    assert total == Decimal("0.03")
    rounded_sum = sum(line.amount for line in lines).quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert rounded_sum == Decimal("0.02")
    assert total != rounded_sum


def test_us_wrk_054_tc4_posting_is_a_ruling_not_a_stub():
    """`OQ-WRK-1491` CLOSED 2026-09-04 to option (a). The refusal names the
    RULING and not a question id, because a stub invites a later lane to
    unblock a question the Product Owner has already answered
    (`DEF-WRK-4030`)."""
    import pytest

    with pytest.raises(NotImplementedError) as excinfo:
        costing.post_field_cost_to_ledger(object())
    message = str(excinfo.value)
    assert "posted nowhere" in message
    assert "payroll already posts the hour" in message
    assert "OQ-" not in message, "a ruled absence must not cite a closed question"
