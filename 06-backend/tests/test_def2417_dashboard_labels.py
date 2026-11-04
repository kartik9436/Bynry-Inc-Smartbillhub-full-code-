# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2417 (2026-09-01) — every KPI tile on the landing screen printed
#          its machine id as its label. The PO read AR-OUTSTANDING and
#          UNBILLED-READS on the first screen after every sign-in.
# Rules:   B14 rule 31 (nothing internal is ever visible to a utility user) ·
#          TD-16/B8 (the server sends a stable key, the UI renders language) ·
#          BR-REP-031 (activity) · BR-REP-032 (to do) · BR-TEN-015 (S62's
#          checklist)
# Screens: S7
# ───────────────────────────────────────────────────────
"""EVERY TOKEN THIS MODULE CAN EMIT MUST HAVE COPY IN THE CATALOGUE.

WHY THIS TEST LIVES ON THE BACKEND, WHICH IS THE WHOLE POINT
------------------------------------------------------------
The split TD-16/B8 draws is right and is not in question: reports SENDS a
stable token (`ar-outstanding`, `read_batch.imported`, `company_profile`) and
the frontend RENDERS language for it. Renaming a token to suit a screen would
break the contract, and DEF-2417's own prevention column says so in as many
words.

**What nothing owned was the OTHER end of that sentence.** A token with no copy
rendered ITSELF, so the five KPI tiles printed their ids at a billing clerk for
as long as the screen existed — because the five catalogue entries had been
written `dashboard.kpi.arOutstanding` while this module has always emitted
`ar-outstanding`.

**Not one check in the repo could see it, and the two nearest both said PASS:**

  * `G27` resolves LITERAL `t("some.key")` calls. Every label on that screen is
    a key BUILT from the server's token, and its own docstring explains why it
    will not follow one: a computed key "cannot be resolved without running the
    app".
  * `G18` compares catalogue to code in both directions, and treats a static
    stem — `dashboard.kpi.` — as covering every leaf beneath it. So the five
    camelCase keys were never reported DEAD and the five kebab ids were never
    reported MISSING. Two gates, green, disagreeing with each other.
  * `vitest` renders the component and asserts on text the test supplies.
  * `tsc` and `eslint`: a string is a string.

So the question has to be asked where the tokens are DEFINED. This file reads
the constants this module emits from and the app's own `en.json`, and fails the
moment a new tile, a new operator action class or a new checklist step arrives
without a label. The eleven-catalogue half is
`07-frontend/src/features/reports/dashboard.test.tsx`, which asks the same
lists in every language.

**RED PROVED FIRST — four of the six cases here, run against the pre-fix
catalogue read straight out of `git show HEAD:…`:**

    RED  test_every_kpi_tile_id_has_a_label
         the KPI tile 'ar-outstanding' has no label:
         dashboard.kpi.ar-outstanding is in no catalogue
    RED  test_every_onboarding_step_has_a_label
         the onboarding step 'company_profile' has no label:
         dashboard.todo.onboarding.company_profile is in no catalogue
    RED  test_every_operator_activity_class_has_a_label
         the activity class 'account' has no label:
         dashboard.activity.class.account is in no catalogue
    RED  test_the_unnamed_fallbacks_exist
         dashboard.kpi.unnamed is in no catalogue
    RED  test_no_kpi_label_is_still_written_in_the_spelling_the_server_never_sends
         dashboard.kpi.arOutstanding is back.

⚠ **THE SIXTH WAS ALREADY GREEN AND IS RECORDED AS SUCH.**
`test_every_todo_code_an_owner_can_emit_has_both_labels` passed before this
lane touched anything: the six operational to-do codes have had copy since
CR-012, and only the ONBOARDING half of that panel was missing. Saying so is
the point — a case added alongside four that go red reads as though it went red
too, and the next lane would take its green as proof of this lane's work rather
than of the 2026-08-19 work that earned it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.reports import dashboard, dashboard_regions
from apps.tenancy import selectors as tenancy_selectors

CATALOGUE = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"


@pytest.fixture(scope="module")
def copy() -> dict[str, str]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


def test_every_kpi_tile_id_has_a_label(copy: dict[str, str]) -> None:
    """`KPI_ORDER` is the contract. A tile added here with no label is the defect."""
    ids = [tile_id for tile_id, *_ in dashboard.KPI_ORDER]
    assert ids, "KPI_ORDER is empty — this test would pass by having nothing to ask"
    for tile_id in ids:
        key = f"dashboard.kpi.{tile_id}"
        assert key in copy, f"the KPI tile {tile_id!r} has no label: {key} is in no catalogue"


def test_every_operator_activity_class_has_a_label(copy: dict[str, str]) -> None:
    """The feed shows the CLASS — the part of the audit action before its first dot."""
    classes = sorted({prefix.rstrip(".") for prefix in dashboard_regions.OPERATOR_ACTIONS})
    assert classes
    for klass in classes:
        key = f"dashboard.activity.class.{klass}"
        assert key in copy, f"the activity class {klass!r} has no label: {key} is in no catalogue"


def test_every_todo_code_an_owner_can_emit_has_both_labels(copy: dict[str, str]) -> None:
    """Derived by RUNNING `todo_rows`, not by transcribing its `add()` calls.

    A row is emitted with a count or without one and the two read differently
    (PO 2026-08-19 d.3 — a countless row shows NO number), so both keys are
    required for every code an owner can produce.
    """
    rows = dashboard_regions.todo_rows(
        billing_exceptions=3,
        onboarding=(),
        rate_approvals=2,
        disconnect_eligible=1,
        finance_close={"period": "2026-08"},
        number_format=None,
    )
    codes = [row["code"] for row in rows]
    assert codes, "no owner produced a row — this test would ask nothing"
    for code in codes:
        for key in (f"dashboard.todo.item.{code}", f"dashboard.todo.itemNoCount.{code}"):
            assert key in copy, f"the to-do code {code!r} has no label: {key} is in no catalogue"


def test_every_onboarding_step_has_a_label(copy: dict[str, str]) -> None:
    """S62's checklist feeds the To-do panel for every brand-new tenant, so these
    six are the FIRST rows a new utility ever reads (BR-REP-032, BR-TEN-015)."""
    codes = [code for code, _kind in tenancy_selectors.CHECKLIST_ITEMS]
    assert codes
    for code in codes:
        key = f"dashboard.todo.onboarding.{code}"
        assert key in copy, f"the onboarding step {code!r} has no label: {key} is in no catalogue"


def test_the_unnamed_fallbacks_exist(copy: dict[str, str]) -> None:
    """What a token with NO copy renders instead of itself.

    A missing fallback would print its own dotted key, which is B14 rule 31
    broken one level up from where it was broken before.
    """
    for key in (
        "dashboard.kpi.unnamed",
        "dashboard.activity.unnamed",
        "dashboard.todo.unnamed",
    ):
        assert key in copy, f"{key} is in no catalogue"


def test_no_kpi_label_is_still_written_in_the_spelling_the_server_never_sends(
    copy: dict[str, str],
) -> None:
    """The five orphans that caused this, named so they cannot come back.

    They were real, translated eleven times, and unreachable: nothing in `src/`
    read them and no gate could say so. Their VALUES were not thrown away — they
    are the values now keyed on the ids this module emits.
    """
    for orphan in (
        "dashboard.kpi.arOutstanding",
        "dashboard.kpi.unbilledReads",
        "dashboard.kpi.failedPayments",
        "dashboard.kpi.periodRevenue",
        "dashboard.kpi.activeConnections",
    ):
        assert orphan not in copy, (
            f"{orphan} is back. The server sends kebab-case ids; a camelCase "
            "label is a key nothing can reach."
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2417 (12-governance/10-defect-log.csv) · B14 rule 31
#         (04-docs/02-decisions/14-ui-conventions.md) · US-REP-019
# screens: S7
# generated: 2026-09-01 by the customer-facing-copy lane
# gates: RED PROVED FIRST — every assertion above failed on the pre-fix
#        catalogue and the failures are quoted in this file's docstring.
# exceptions: (1) this test reads `07-frontend/src/i18n/locales/en.json` from a
#     backend test, which four other tests in this directory already do
#     (test_cr005_numbering_set08, test_cr054_w1_reading_sheet,
#     test_cr056_w6_minimum_identity, test_br_bil_870_resolution_switch). It is
#     the only place the two ends of the token contract are both in scope, and
#     the eleven-language half stays in the frontend suite where the catalogues
#     are loaded properly · (2) it asks whether a KEY EXISTS, not whether the
#     sentence is right — no check can do the latter, which is why the PO
#     reading a screen is still how DEF-2417 was found
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
