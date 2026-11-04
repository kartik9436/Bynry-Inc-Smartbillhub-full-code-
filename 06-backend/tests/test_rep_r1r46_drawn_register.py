# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 · lane REP-REGISTER — the 46 drawings on p49-p73 of
#           `05-prototype/09 Reports Build Brief.pdf`, read AS IMAGES (B14
#           rule 42) and transcribed into `10-scripts/rep_r1r46_drawn.py`.
# Rules:    CLAUDE.md hard rule 3 (a quantity carries its unit; gallons plus
#           kilowatt-hours is not a number) · B14 rule 37 (a drawn figure is
#           an illustration) · BR-REP-021 (five reports are on the generic
#           viewer BECAUSE their column sets are unratified)
# Impacts:  04-docs/05-modules/12-reports/02-business-rules.md SS R1-R46 ·
#           10-scripts/rep_r1r46_drawn.py · apps/reports/queries.py
# ───────────────────────────────────────────────────────
"""TWO GUARDS THE 46 DRAWINGS NEEDED AND DID NOT HAVE.

The drawings carry 52 rule-bearing warnings and they lived in a PDF, which is
the one place no check in this repo can read. Transcribing them buys nothing
on its own — a transcription rots the moment the seed moves, and a rotted
transcription is worse than a PDF because it looks current.

**GUARD ONE keeps the transcription honest.** It compares the drawn record
against the SEED, in both directions, so a lane that adds, removes or renames
a definition cannot leave the register describing a product that no longer
exists. ⚠ **BOTH DIRECTIONS IS THE WHOLE POINT** — a one-way check passes
happily while a drawing describes a definition nobody seeded.

**GUARD TWO is hard rule 3 on the one built query that could break it.**
`R17 Revenue Analysis` is drawn with a USAGE column showing `3,884,100 gal`
for water, an EM-DASH for sewer, and a BLANK where a cross-service total
would go. Its warning, verbatim: *"Gallons and kilowatt-hours cannot be
added, so a cross-service usage total is refused rather than computed. Money
adds; quantities do not."* `revenue_by_service_rate` is one of only FOUR
queries built today, so this is one of the few places the rule can be
enforced against running code rather than against a definition row.
⚠ **AND IT PASSES TODAY FOR A REASON THAT IS ITSELF A DEFECT** (`DEF-REP-6828`):
the built query serves no usage column at all, so there is no quantity to
total wrongly. That does not weaken the guard — it is precisely the day the
usage column lands that somebody will reach for a `usage` total, and this
test is what will be red when they do.

WHAT FALSE PASS EACH IS WRITTEN AGAINST
────────────────────────────────────────
GUARD ONE would pass wrongly if it read the drawn table for BOTH sides of the
comparison, which is the shape of a check that cannot fail — so the seed is
parsed from `0003_seed_catalogue.py` by the helper in the script, and the
assertion is over the SYMMETRIC DIFFERENCE rather than over two counts. Two
counts can agree while naming different reports.

GUARD TWO would pass wrongly if it asserted on `columns` instead of `totals`.
A report may legitimately SHOW a per-row usage quantity — the drawing does,
one row per service, each with its own unit — and the rule bites only on the
FOOTER. Asserting the absence of a usage column would forbid the drawing, and
asserting the whole payload holds no `usage` string would go green only while
the column is missing and red the day it is built correctly.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]


def _drawn_module():
    spec = importlib.util.spec_from_file_location(
        "rep_r1r46_drawn", REPO / "10-scripts/rep_r1r46_drawn.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_drawn_register_names_every_seeded_definition_and_no_others():
    """One drawn record per seeded definition, both directions.

    ⚠ R24 and R25 are ONE definition each drawn at FOUR subjects, so the drawn
    side carries `R24a`..`R24d` and the seed carries `R24`. The suffix is
    stripped for the comparison and the four are asserted separately, because
    a lane dropping one subject would otherwise be invisible.
    """
    drawn = _drawn_module()
    seeded = set(drawn.definitions(REPO))
    recorded = {re.sub(r"[a-d]$", "", register) for register, _page, _cols in drawn.DRAWN}

    assert seeded - recorded == set(), (
        "a seeded definition has no drawn record — the register in "
        "04-docs/05-modules/12-reports/02-business-rules.md is now describing a "
        f"product that has moved under it: {sorted(seeded - recorded)}"
    )
    assert recorded - seeded == set(), (
        "a drawing names a definition nobody seeded — either the seed lost a "
        f"row or the transcription invented one: {sorted(recorded - seeded)}"
    )
    assert len(seeded) == 46, f"the brief answers 46 questions; the seed holds {len(seeded)}"

    for definition, subjects in (("R24", "abcd"), ("R25", "abcd")):
        for subject in subjects:
            assert any(
                register == f"{definition}{subject}" for register, _page, _cols in drawn.DRAWN
            ), f"{definition}{subject} is one of the four subjects and has no drawn record"


def test_a_cross_service_usage_total_is_refused_rather_than_computed(monkeypatch):
    """Hard rule 3 in R17's footer: money adds, quantities do not.

    Two services with DIFFERENT units are handed to the report and the totals
    it publishes are asserted to carry every MONEY figure and no quantity.
    """
    from apps.reports import queries

    # ⚠ The tenant clock is stubbed and NOT the thing under test. `_checked_window`
    # resolves the tenant's own today (BR-TEN-043) and would raise
    # AUTH_TENANT_UNRESOLVABLE outside a request; the window it produces is an
    # argument to a seam this test replaces. The BODY that builds `totals` —
    # the only thing this guard is about — runs for real.
    monkeypatch.setattr(queries, "_checked_window", lambda _params: (date(2026, 9, 1), date(2026, 9, 30)))

    rows = [
        SimpleNamespace(
            service_id=1, service_code="WTR", service_name="Water",
            tariff_id=10, tariff_name="RES-W-2026", accounts=984,
            usage_revenue=Decimal("61204.1000"), base=Decimal("18402.0000"),
            tax=Decimal("4880.0000"), total=Decimal("84486.1000"),
        ),
        SimpleNamespace(
            service_id=2, service_code="ELE", service_name="Electric",
            tariff_id=11, tariff_name="RES-E-2026", accounts=61,
            usage_revenue=Decimal("6000.0000"), base=Decimal("2500.0000"),
            tax=Decimal("410.0000"), total=Decimal("8910.0000"),
        ),
    ]
    monkeypatch.setattr(
        queries.seams,
        "revenue_by_service_and_rate",
        lambda **_: {
            "currency": "USD",
            "basis": "posting",
            "rows": rows,
            "totals": {
                "accounts": 1045,
                "usage_revenue": Decimal("67204.1000"),
                "base": Decimal("20902.0000"),
                "tax": Decimal("5290.0000"),
                "total": Decimal("93396.1000"),
            },
            "problems": [],
        },
    )

    report = queries.revenue_by_service_rate({"from": "2026-09-01", "to": "2026-09-30"})
    totals = report["totals"]

    # The MONEY footer is present and complete — the rule forbids one kind of
    # total, not totalling.
    for money in ("usage_revenue", "base", "tax", "total"):
        assert money in totals, f"{money} is money and money adds"

    quantity_keys = [
        key for key in totals
        if key == "usage" or key.endswith("_usage") or key.endswith("_quantity")
    ]
    assert quantity_keys == [], (
        "R17's footer publishes a cross-service quantity total "
        f"({quantity_keys}) — 3,884,100 gal plus 1,102,400 kWh is not a number. "
        "CLAUDE.md hard rule 3, and the drawing's own warning: 'a cross-service "
        "usage total is refused rather than computed'. A per-SERVICE usage "
        "figure with its own unit is lawful and belongs on the row."
    )
