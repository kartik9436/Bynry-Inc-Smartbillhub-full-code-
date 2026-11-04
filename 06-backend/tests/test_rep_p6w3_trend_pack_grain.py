# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 `P6.11` wave 3 · `DEF-REP-6937` — R43 Trend Pack was
#           served by the `journal_lines` dataset query and answered ONE ROW
#           PER JOURNAL LINE under its own title.
# Rules:    `BR-REP-002` (every card opens a READ MODEL) · `BR-REP-024` (a
#           figure that cannot be produced is named, never guessed) ·
#           CLAUDE.md hard-won law 7 (*looking at the wrong thing* — a key
#           MISSING from a hand-kept map is indistinguishable from a
#           deliberately absent one)
# ───────────────────────────────────────────────────────
"""R43 IS NOT THE `journal_lines` DATASET'S TO SERVE, AND R42's NEIGHBOUR PROVES IT.

The two sit side by side in Finance › Performance, on one dataset, with the
same by-period shape. R42 was refused by name and R43 was not, so a clerk who
opened *Trend Pack* got thirty-six rows of `posted_on / account_code / debit /
credit`. Every gate passed over it: the rows were real, the footer footed, and
nothing anywhere asked whether the REPORT and the GRAIN agreed.

⚠ **THE CASE IS WRITTEN AGAINST THE REFUSAL AND NOT AGAINST THE MAP.** Asserting
`"trend_pack" in JOURNAL_LINES_DEFINITIONS_NOT_SERVED` would pass on a map entry
that nothing reads — which is the defect's own shape one layer up. It calls
`definition_refusal`, the function the catalogue and the viewer both call, and
`runner.run`, the one path a clerk's request actually takes.
"""

import pytest

from apps.reports import queries, runner

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The columns the `journal_lines` dataset serves. If R43 ever renders THESE,
#: it is serving ledger lines under a trend pack's title again.
LEDGER_LINE_COLUMNS = ("posted_on", "account_code", "debit", "credit")


def test_the_dataset_itself_refuses_r43_by_name_and_says_what_it_draws(brazos):
    """The DATASET QUERY, called directly — which is the layer that was wrong.

    ⚠ **IT IS CALLED DIRECTLY AND NOT THROUGH `definition_refusal`, AND THAT IS
    THE WHOLE DESIGN OF THIS CASE.** `definition_refusal` and
    `runner.queries_for` both check `VIEWERS` first, so once R43 has its own
    read model they answer *not refused* — correctly. A case written against
    them would have gone quiet the moment the report was built, which is the
    exact moment this guard stops being decorative: the refusal is the thing
    standing between a clerk and ledger lines if the viewer is ever unwired.
    """
    with tenant_ctx(brazos), pytest.raises(queries.DatasetCannotServe) as raised:
        queries.journal_lines_dataset({}, key="trend_pack")
    reason = raised.value.reason
    # The sentence must name the grain R43 draws and the grain this dataset
    # has, or a reader cannot tell a deliberate absence from a forgotten key.
    assert "FISCAL PERIOD" in reason
    assert "journal LINE" in reason


def test_r42_and_r43_are_refused_by_the_dataset_the_same_way(brazos):
    """The neighbour that was right, asserted beside the one that was wrong.

    They are the same section, the same dataset and the same by-period shape,
    so a change that refuses one and not the other is `DEF-REP-6937` recurring.
    """
    for key in ("operational_dashboard", "trend_pack"):
        with tenant_ctx(brazos), pytest.raises(queries.DatasetCannotServe):
            queries.journal_lines_dataset({}, key=key)


def test_the_viewer_wins_over_the_refusal_and_the_card_is_available(brazos):
    """`BR-REP-039`'s arrangement, one report along.

    A per-KEY viewer is checked FIRST, so the refusal above is bypassed rather
    than deleted — and the catalogue must agree with the viewer about whether
    the card can be produced, which is what `definition_refusal` answers.
    """
    assert queries.VIEWERS.get("trend_pack") is not None
    assert queries.definition_refusal("trend_pack", "journal_lines") is None
    # R42 has no viewer, so its refusal still reaches the catalogue.
    assert queries.definition_refusal("operational_dashboard", "journal_lines") is not None


def test_r43_never_carries_the_ledger_line_columns(brazos):
    """`DEF-REP-6937` itself, at the layer a clerk's request reaches.

    This is the case that survives everything: whatever answers `trend_pack` —
    a read model today, a refusal if one is ever restored — it is not the
    journal-line grain wearing this report's title.
    """
    try:
        with tenant_ctx(brazos):
            answer = runner.run("trend_pack")
    except queries.DatasetCannotServe:
        return  # refused — lawful, and not the wrong report
    served = tuple(answer.columns)
    assert not set(LEDGER_LINE_COLUMNS) <= set(served), (
        f"trend_pack served {served}, which is the journal_lines dataset's column set. "
        "DEF-REP-6937 has recurred."
    )
    assert served[0] == "period"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 3 (DEF-REP-6937; 05-prototype/09 Reports Build Brief.pdf p059 read as an image per B14 rule 42)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-W3
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — against the shipped `queries.py` all four cases failed: the dataset did NOT raise for `trend_pack`, `definition_refusal` answered None because nothing refused and nothing served, and `runner.run("trend_pack")` returned the journal_lines column set. Verbatim: `4 failed, 10 warnings in 497.76s`.
# exceptions: (1) the first two cases call the DATASET QUERY directly rather than `definition_refusal`, because the per-key viewer legitimately silences the latter and a case written against it would stop protecting anything the day R43 was built · (2) the last case is satisfied by a refusal as well as by a correct answer — it is the guard that outlives either
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
