# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.22 (THE MONEY TASK — a footer that
#           cannot lawfully sum shows an em-dash and the reason, on screen AND
#           in the CSV, never a number).  Screens: 2·1 footer.
# Rules:    CLAUDE.md hard rule 2 (money 4 dp stored, DISPLAY 2, never a
#           float) · hard rule 3 (a quantity carries its unit — gallons plus
#           kilowatt-hours is not a number) · B14 rule 33 (a FACT is six words)
#           · brief §7.2.2 p85 read as an image (B14 rule 42)
# Tests:    this file
# Impacts:  apps/reports/additivity.py · apps/reports/queries.py ·
#           apps/reports/exports.py · apps/tenancy/exports.py (the footer row)
# ───────────────────────────────────────────────────────
"""THE THREE TOTALS THAT ARE WRONG TODAY, WRITTEN AS TESTS BEFORE THE FIX.

Brief §7.2.2, read as an image from p85 — *"ADDITIVITY — THE TWO TRAPS THAT
PRODUCE WRONG MONEY"* — names three things a clerk can ask for today and get a
confident number for:

  1. **A balance summed across time.** *"AR balance · deposits held · accounts
     active … sums across accounts, never across time. Group AR Ageing by
     month, total the column, and the number means nothing. **Nothing stops you
     today.**"*
  2. **A DSO averaged across routes.** *"DSO · collection rate · % share ·
     average days overdue must be recomputed from their components, never
     averaged. The average of four route DSOs is **not** the utility's DSO."*
  3. **Two units added together.** *"gallons plus kilowatt-hours is not a
     number — hard rule 3 already forbids it, and this is the same rule stated
     as metadata."*

⚠ **WHAT `P0.16` ALREADY DID, AND WHY IT IS NOT THIS.** `assert_summable`
RAISES, and `runner.validate` calls it when a definition is SAVED. That stops a
stored definition from being built wrong. It does nothing at all about the
number a clerk is looking at right now, because a footer is computed at render
time over whatever the query returned — and `queries.py` builds `totals` as a
plain `{name: "1234.56"}` map with nothing between it and the screen.

So this file asserts the RENDER-time half, and it asserts it in **both
directions** — that the refusal appears when the total is unlawful, and that it
is **GONE** when it is lawful. A refusal that stays on screen after the clerk
regroups is the defect that shipped this week in another module.

⚠ **AND IT ASSERTS THE FILE, NOT ONLY THE SCREEN.** The CSV is what a clerk
sends an auditor. A test that checks only the screen leaves the file wrong.
"""

import csv
import io

import pytest

from apps.reports import additivity, datasets


# ═══════════════════════════════════════════════════════════════════════════
# The three cases, as the brief names them
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_22__case_one_a_balance_summed_across_time_is_refused():
    """AR Ageing grouped by month, totalling the balance column.

    This is the outcome row on p13: *"AR Ageing grouped by month refuses its
    balance total and says why."*
    """
    refusal = additivity.refusal_for("payments", "total", ("time",))
    assert refusal is not None, "a balance summed across time must be refused"
    assert refusal.measure == "total"
    assert refusal.reason_code == additivity.REASON_NOT_ACROSS_TIME
    # The em-dash IS the value. Never a number.
    assert refusal.as_dict()["value"] is None
    assert refusal.as_dict()["display"] == additivity.EM_DASH


def test_p2_22__case_two_a_dso_averaged_across_routes_is_refused():
    """*"The average of four route DSOs is not the utility's DSO."*"""
    refusal = additivity.refusal_for("payments", "dso_days", ("route_cycle",))
    assert refusal is not None
    assert refusal.reason_code == additivity.REASON_RECOMPUTE_NEVER_AVERAGE
    # Non-additive means NO direction is safe — including no grouping at all,
    # which is the case a footer hits when it totals a flat listing.
    assert additivity.refusal_for("payments", "dso_days", ()) is not None


def test_p2_22__case_three_two_units_added_together_is_refused():
    """Gallons plus kilowatt-hours is not a number (hard rule 3)."""
    refusal = additivity.refusal_for("meter_reads", "consumption", ("service",))
    assert refusal is not None
    assert refusal.reason_code == additivity.REASON_ONE_SERVICE_ONLY


# ═══════════════════════════════════════════════════════════════════════════
# The other direction — the half a refusal-only test cannot see
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_22__a_lawful_total_is_not_touched_and_carries_no_refusal():
    """Refusing an unlawful total must not change a lawful one.

    Law 7's *"ask what would make this check pass wrongly"*: a module that
    refused everything would satisfy all three cases above and be useless.
    """
    assert additivity.refusal_for("invoices", "amount", ("time", "service")) is None
    assert additivity.refusal_for("journal_lines", "debit", ("time",)) is None
    # A balance across ACCOUNTS is exactly what a balance is FOR.
    assert additivity.refusal_for("payments", "total", ("consumer_class",)) is None
    # An attribute is never totalled, so there is nothing to refuse.
    assert additivity.refusal_for("payments", "account_no", ("time",)) is None


def test_p2_22__the_refusal_disappears_when_the_grouping_changes():
    """⚠ **THE DEFECT THAT SHIPPED THIS WEEK, ASSERTED AGAINST.** A refusal
    that stays on screen after the clerk fixes the grouping is a live screen
    behind a dead control (hard-won law 2's mirror). One footer, two groupings,
    asserted in both directions."""
    by_month = additivity.footer("payments", {"total": "48221.1400"}, ("time",))
    assert by_month["total"]["refused"] is True
    assert by_month["total"]["value"] is None

    by_class = additivity.footer("payments", {"total": "48221.1400"}, ("consumer_class",))
    assert by_class["total"] == "48221.1400", "the lawful total is untouched, not re-wrapped"
    assert "refused" not in str(by_class["total"])


def test_p2_22__the_footer_refuses_only_the_measure_that_cannot_sum():
    """A footer is a ROW, and one unlawful column must not poison the rest."""
    served = additivity.footer(
        "payments",
        {"total": "48221.1400", "payments": 412, "dso_days": "31.500000"},
        ("time",),
    )
    assert served["total"]["refused"] is True          # semi-additive across time
    assert served["dso_days"]["refused"] is True       # non-additive anywhere
    assert served["payments"] == 412                   # fully additive — a number


# ═══════════════════════════════════════════════════════════════════════════
# No number reaches the reader — on screen OR in the file
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_22__no_digit_of_the_refused_figure_survives_into_the_wire():
    """*"never a number"* asserted as the absence of the digits themselves.

    Asserting `value is None` is not enough: a first draft carried the figure
    on in a `detail` field for the tooltip, which is a number on the wire and
    one CSS rule away from being a number on screen.
    """
    served = additivity.footer("payments", {"total": "48221.1400"}, ("time",))
    assert "48221" not in repr(served["total"])
    assert not any(ch.isdigit() for ch in repr(served["total"]["display"]))


def test_p2_22__the_csv_footer_row_carries_the_em_dash_and_the_reason():
    """⚠ **THE FILE IS WHAT A CLERK SENDS AN AUDITOR.**

    A test that only checks the screen leaves the file wrong, so this one
    writes the row the exporter appends and reads it back with `csv`.
    """
    row = additivity.csv_footer_row(
        columns=("account_no", "current", "total"),
        totals=additivity.footer("payments", {"total": "48221.1400"}, ("time",)),
        label="Total",
    )
    handle = io.StringIO()
    csv.writer(handle).writerow(row)
    back = next(csv.reader(io.StringIO(handle.getvalue())))
    assert back[0] == "Total"
    assert additivity.EM_DASH in back[2]
    # The reason travels WITH the em-dash, in the same cell — a separate
    # metadata row would break IS-9's one-header-then-data contract further
    # than one footer row already does.
    assert len(back[2]) > 1, "the em-dash arrives with its reason, never alone"
    assert "48221" not in "".join(back)


def test_p2_22__the_csv_footer_is_absent_entirely_when_every_total_is_lawful():
    """Both directions again, in the file. A file that always carried a footer
    would be a file whose footer says nothing."""
    assert additivity.csv_footer_row(
        columns=("account_no", "total"),
        totals={"total": "48221.1400"},
        label="Total",
    ) == ["Total", "48221.1400"]


# ═══════════════════════════════════════════════════════════════════════════
# The reason is a FACT, and B14 rule 33 caps a fact at six words
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("code", sorted(additivity.REASON_SENTENCES))
def test_p2_22__every_reason_is_six_words_or_fewer(code):
    """B14 rule 33: a FACT is ≤ 6 words, and RATIONALE is zero words on screen.

    *"Balances do not sum across time"* is a fact about this number. *"Because
    a balance is a stock rather than a flow…"* is rationale and belongs in this
    module's docstring, where it is.
    """
    sentence = additivity.REASON_SENTENCES[code]
    assert len(sentence.split()) <= 6, f"{code}: {sentence!r} is more than six words"


def test_p2_22__every_additivity_the_model_declares_has_a_reason():
    """A refusal with no sentence renders as a bare em-dash, which is the one
    thing p85 forbids — *"an em-dash **and its reason**"*.

    This is the blind-spot check law 7 asks for: it counts what the model
    declares against what this module can explain, so a fifth additivity added
    to `datasets.py` cannot ship a silent footer.
    """
    explicable = set(additivity.REASON_SENTENCES)
    for dataset in datasets.DATASETS:
        for meas in dataset.measures:
            refusal = additivity.refusal_for(dataset.code, meas.name, tuple(
                dim.name for dim in dataset.dimensions
            ))
            if refusal is not None:
                assert refusal.reason_code in explicable, (
                    f"{dataset.code}.{meas.name} refuses with {refusal.reason_code!r}, "
                    "which has no sentence — that renders as a bare em-dash"
                )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.22 (05-prototype/09 Reports Build Brief.pdf p13, p84, p85 read as images per B14 rule 42)
# screens: 2·1 footer
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
