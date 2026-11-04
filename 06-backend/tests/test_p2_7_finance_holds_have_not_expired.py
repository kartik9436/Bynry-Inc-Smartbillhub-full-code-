# ── Trace ──────────────────────────────────────────────
# Change:  Finance blueprint `P2.7` (p015) — *"For every remaining hold, assert
#          the condition it names is still true. Write the test in the same
#          commit as the hold — a hold with no such test is a promise nobody is
#          keeping."* Outcome: *"The next rotting hold goes red instead of
#          shipping."*
# Defects: DEF-GOV-6531 (G103 owns this question and can only see `portal.` and
#          `settings.` holds — every Finance hold is outside its scope) ·
#          DEF-LED-6499 (the property-filter panel, which is what a rotted hold
#          looks like when nobody is watching) · DEF-2346 (the same shape, on
#          the same screen, three weeks earlier)
# Rules:   CLAUDE.md hard-won law 2, mirror clause — *"when you write a hold,
#          write the test that fires when the hold expires, in the same
#          commit"* · law 1 (a comment claiming a guarantee is not the
#          guarantee) · law 7 (a check must be able to fail, and must say what
#          it skipped) · BR-SHL-025 (a control this deployment cannot honour
#          renders disabled WITH its reason)
# ───────────────────────────────────────────────────────
"""EVERY REMAINING FINANCE REFUSAL, AND THE CONDITION IT NAMES — STILL TRUE?

WHY THIS FILE EXISTS RATHER THAN A GATE
---------------------------------------
`G103` already owns the question *"is this refusal still true"* and says so in
its own docstring: *"nobody owned the question … This gate owns it."* **It then
answers it for two key prefixes out of a dozen.** Its matchers are anchored to
``(?:portal|settings)\\.``, so every hold whose key begins `finance.` — the four
disabled downloads, the S74 reconciliation download, the expand panel — is
outside its scope, **and it prints no number beside what it skipped**. That is
hard-won law 7's fifth shape, and it is filed as `DEF-GOV-6531` rather than
worked around by widening one gate inside a commit about Finance copy.

**So this file covers Finance's holds directly, and it asserts the CONDITION
rather than the SENTENCE.** That distinction is the entire lesson of
`DEF-LED-6499`: the panel it replaced was covered by a test asserting its
sentence was PRESENT and pinning its exact English, and **neither assertion
could go red on the day the filter shipped**. The screen went on denying a
built feature for three weeks with every check green. A test that pins a
sentence holds the sentence in place, because correcting the code then looks
like breaking the suite.

**Each case below therefore fails the day the thing it waits for ARRIVES**, and
names the control that must be released in the same breath.

⚠ **THESE ARE FACTS ABOUT THE SERVER, WHICH IS WHY THEY ARE HERE AND NOT IN
`vitest`.** Whether the trial balance has a download is a question about
`apps/reports/exports.RESOURCES`, not about a React tree. A frontend test could
only assert that the screen still SAYS so, which is the failure mode above.
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]

# ⚠ **NO `django_db` MARK, DELIBERATELY.** Not one of these cases touches a
# table: they read a registered-resource tuple, a module attribute, the source
# tree and a register row. The first draft carried `pytestmark =
# pytest.mark.django_db` out of habit and spent its whole budget building a test
# database it never queried — a fixture that costs minutes and proves nothing is
# how a fast check becomes one nobody runs. These finish in under a second.


def test_the_export_service_is_running_so_no_screen_may_blame_it() -> None:
    """The premise `P2.5` rests on, pinned so it cannot silently stop being true.

    Four Finance sentences used to say the download *"needs the report export
    service, which is not running on this deployment"*. It IS running:
    `apps/tenancy/exports.py` is the kernel, and `apps/reports/exports.py`
    registers four report resources with it at startup. If that stops being so,
    the corrected copy becomes wrong in the OTHER direction and this fails.
    """
    from apps.reports import exports

    assert exports.RESOURCES, "no export resource is registered — P2.5's corrected copy now understates the gap"
    slugs = {resource.slug for resource in exports.RESOURCES}
    assert "ar-aging" in slugs, f"the ar_aging export resource is gone; registered: {sorted(slugs)}"


@pytest.mark.parametrize(
    ("report_key", "control"),
    [
        # `finance.gl.exportUnavailable` — "The trial balance has no download."
        ("trial_balance", "the Download control on Finance → General ledger → Balance"),
        # `finance.taxes.reportUnavailable` — "This report has no download yet."
        ("remittance", "the Download control on Finance → Taxes & Remittance"),
        # `reports.export.reason` — "These reports have no download yet."
        # ONE sentence, THREE screens (P2.10): S59, S60 and the customer statement.
        ("account_ledger", "ReportDownloads on S59 · S60 · the customer statement"),
        ("by_premises", "ReportDownloads on S59 · S60 · the customer statement"),
    ],
)
def test_a_report_with_no_download_still_has_no_download(report_key: str, control: str) -> None:
    """RELEASE THE CONTROL THE DAY THIS FAILS.

    Each of these reports is refused a download because it is not registered as
    an export RESOURCE — a missing registration, not a downed service. The day
    somebody registers one, this test names the control that is still greyed
    over it, which is the whole point of `P2.7`.
    """
    from apps.reports import exports

    slugs = {resource.slug for resource in exports.RESOURCES}
    key_as_slug = report_key.replace("_", "-")
    assert key_as_slug not in slugs, (
        f"`{report_key}` IS a registered export resource now — so its download works and "
        f"{control} is refusing over a gap that has closed. Release it (P2.7, BR-SHL-025)."
    )


def test_the_period_pack_is_still_not_built() -> None:
    """`finance.action.periodPackUnavailable` — "The period pack is not built."

    The old sentence said *"this deployment does not build yet"*, which framed a
    universal absence as a local one. Nothing named `period_pack` exists in the
    backend at all, and this is what pins that.
    """
    hits = [
        path
        for path in (REPO / "06-backend" / "apps").rglob("*.py")
        if "period_pack" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not hits, (
        "something now builds a period pack — the Revenue & AR action is refusing over a gap "
        f"that has closed. Release it. Found in: {[str(p.relative_to(REPO)) for p in hits]}"
    )


def test_oq_204_is_still_only_half_closed() -> None:
    """The S74 reconciliation download's reason, narrowed by `P2.5`.

    It used to blame *"WHERE this view lives has not been ruled"*, and where it
    lives was ruled on 2026-09-03 (`CR-060` C27). What remains open is the
    download CONTRACT, and `OQ-204` is `PARTIALLY CLOSED` over exactly that.

    ⚠ **THE STATUS COLUMN DECIDES, NEVER THE BODY** — CLAUDE.md's prime
    directive, after three lanes were misled in one evening by a closed
    question whose body still described the open world.
    """
    register = (REPO / "12-governance" / "01-open-questions.md").read_text(encoding="utf-8")
    row = next((line for line in register.splitlines() if line.startswith("| OQ-204 ")), None)
    assert row is not None, "OQ-204 has left the register — the S74 download's reason cites it"
    assert "PARTIALLY CLOSED" in row, (
        "OQ-204 is no longer PARTIALLY CLOSED. If it is CLOSED, the download pipeline has been "
        "chosen and `apps/ledger/cost_api.py`'s Download control must be built or its reason "
        "rewritten — it is currently disabled over this question (P2.7, BR-SHL-025)."
    )


def test_one_account_line_still_cannot_be_opened_to_its_entries() -> None:
    """`finance.gl.expandUnavailable` — the OTHER S56 absence, which is TRUE.

    `P2.4` deleted the property-filter panel and left this one standing on
    purpose: a refusal whose cause is false gets corrected, a refusal whose
    cause is true is left alone. This is what keeps "left alone" honest — the
    day `journal_entry_detail` is published, the panel is the thing to remove.
    """
    from apps.ledger import reporting

    assert not hasattr(reporting, "journal_entry_detail"), (
        "`apps.ledger.reporting.journal_entry_detail` exists now — the S56 'Open a line to its "
        "detail' panel is stating an absence that has closed. Remove it (P2.7, B14 rule 33)."
    )
