# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 Phase 2 · P2.8 + P2.16 — "retire three screens into
#          definitions rendered by 2·1".  Screens: S59 · S60 · the customer
#          statement (no A1 id).
# Rules:   CLAUDE.md hard-won law 2, THE MIRROR — *"nothing asks whether a
#          REFUSAL is still true"* — and its prescription: **WHEN YOU WRITE A
#          HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD EXPIRES, IN THE SAME
#          COMMIT.** · hard-won law 1 (a comment claiming a guarantee is not
#          the guarantee) · BR-CUS-054 as amended by CR-060 C16 (sum within a
#          customer, NEVER across) · 12-governance/22-product-maintenance-
#          process.md (*"a live screen redrawn end to end is MAINTENANCE"*).
# ───────────────────────────────────────────────────────
"""**THE THREE REPORT PAGES ARE NOT RETIRED, AND THIS IS THE CLOCK ON THAT.**

`P2.8` and `P2.16` ask for three live screens — `/reports/account-ledger`,
`/reports/by-premises` and `/reports/customer-statement` — to become definitions
rendered by screen 2·1. **They cannot be, today, and the blocker is measured
here rather than asserted in a paragraph.**

WHAT WAS MEASURED, BY RUNNING IT (lane REP-P2-RETIRE, 2026-09-27, against real
PostgreSQL 16 on the seeded `brazosbend` tenant)
════════════════════════════════════════════════════════════════════════════
    >>> runner.run("account_ledger", …)
    DatasetNotExecutable: report 'account_ledger' reads dataset
    'journal_lines', which has no query yet

    >>> runner.run("statement", …)
    DatasetCannotServe: statement: Statement draws a running balance —
    opening, charges, credits, closing — over accounts, invoices AND payments
    … The invoices dataset produces charges only, so serving it here would
    show every bill and no payment and still print a closing balance.

**AND THE TASK ROWS NAME THREE DEFINITIONS THAT DO NOT EXIST.** `P2.8`'s
outcome column reads *"three definitions added"* and `P2.16`'s reads *"two
definitions gained"* — the two disagree, and **both are wrong in the same
direction**: `report_definitions` already holds the targets and there are
**TWO**, not three and not five. The brief's own drawing says so in terms
(p069, read as an image per B14 rule 42): *"They collapse into two definitions
with a `Subject` parameter."*

      /reports/account-ledger      →  `account_ledger`  (R25, journal_lines)  subject=account
      /reports/by-premises         →  `statement`       (R24, invoices)       subject=premises
      /reports/customer-statement  →  `statement`       (R24, invoices)       subject=customer

There is **no `by_premises` key and no `customer_statement` key** in
`report_definitions`, so *"redirect to `/reports/{key}`"* has no key to point at
for two of the three addresses. p073 says this about by-premises in its own
words: *"it is also the row my own register left dangling: it said by-premises
'becomes a definition' and never named which one. **It is this.**"*

WHY THIS FILE IS A HOLD AND NOT A FIX
══════════════════════════════════════
Retiring a page whose replacement cannot answer would leave a clerk an address
that opens onto a refusal — hard-won law 2's mirror, which on 2026-09-05 left
the customer portal with two working doors out of eight. So the three pages
STAY, and every case below fires the day its blocker lifts and names the page
that is then owed.

⚠ **THE `_VIEWERS` MERGE IS A TRAP AND IS ASSERTED, NOT DESCRIBED.**
`apps/reports/api._VIEWERS` lists the two ledger-owned keys FIRST and then
splats `**{key: runner.run… for key in queries.VIEWERS}` over them. So the day
somebody adds `account_ledger` to `queries.VIEWERS` to make it a definition,
the splat **silently overrides `_account_ledger`** and the live S59 page — still
mounted, still linked from Finance — starts receiving a payload it cannot
render. Nothing in the dict says so. `test_…the_merge_would_override_the_live_
route` is what says so.
"""
from __future__ import annotations

import pytest

from apps.reports import api as reports_api
from apps.reports import queries as reports_queries
from apps.reports import runner as reports_runner
from apps.reports.models import ReportDefinition

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


#: The three live addresses, the definition key each would retire INTO, and the
#: page component a lane must delete on the day it can.
RETIREMENTS = (
    (
        "/reports/account-ledger",
        "account_ledger",
        "account",
        "07-frontend/src/features/reports/AccountLedgerReportPage.tsx",
    ),
    (
        "/reports/by-premises",
        "statement",
        "premises",
        "07-frontend/src/features/reports/ByPremisesReportPage.tsx",
    ),
    (
        "/reports/customer-statement",
        "statement",
        "customer",
        "07-frontend/src/features/reports/CustomerStatementPage.tsx",
    ),
)

#: The window every case below runs over. Any window does: the refusals are
#: raised before a row is read, which is itself part of the finding — the
#: blocker is structural, not a property of this tenant's data.
WINDOW = {"from": "2026-07-01", "to": "2026-08-31"}


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 1 — the two definitions exist and NEITHER can be executed
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_8_p2_16__the_retirement_targets_are_two_definitions_not_three(brazos):
    """The brief says three definitions; the table holds two and the drawing
    agrees with the table.

    This is not pedantry about a count. A lane building to the wording would
    MINT `by_premises` and `customer_statement` as new keys — and that is three
    implementations of one question at three grains, which is exactly the
    duplication p069 says took 95 requirements down to 46.
    """
    with tenant_ctx(brazos):
        keys = set(ReportDefinition.objects.values_list("key", flat=True))
        assert "account_ledger" in keys
        assert "statement" in keys
        # The two the task wording would have had somebody create.
        assert "by_premises" not in keys, (
            "a `by_premises` definition now exists. P2.8's wording asked for one "
            "and p069 says by-premises is `statement` at subject=premises, not a "
            "key of its own — check this was a ruling and not the wording."
        )
        assert "customer_statement" not in keys, (
            "a `customer_statement` definition now exists — see the note above; "
            "p069 makes it `statement` at subject=customer."
        )
        # Both already declare all four subjects, which is what makes them the
        # targets: the Subject parameter (P2.14) has somewhere to land.
        for key in ("account_ledger", "statement"):
            definition = reports_runner.resolve(key)
            assert definition.filters.get("subjects") == [
                "account",
                "customer",
                "premises",
                "unit",
            ], f"{key} no longer declares the four subjects p069 draws"


# ⚠ **THE CLOCK FIRED FOR `statement` ON 2026-09-27 AND THIS FILE MOVED WITH
# IT — `BR-REP-038`, lane REP-P2-LAST.** The PO ruled the statement onto the
# LEDGER (*"it should be like bank statement … Build it on the ledger — the
# account's running record, which holds both sides"*), `reports/0007` moved R24
# to `journal_lines`, and `apps/reports/statement.py` serves it. So the row
# below holds ONE key, not two, and `statement` gets the opposite case.
#
# **WHAT IT DOES NOT MEAN.** `CustomerStatementPage.tsx` is still owed nothing:
# it is *"one person, their accounts, each balance, and a total across them"* —
# the CUSTOMER grain, with the `held_with` guard — and R24 serves the ACCOUNT
# grain. The `customer` subject still refuses, so retiring that page would put
# a refusal at a live address. `test_p2_8_p2_16__the_three_addresses_are_still_
# served_by_their_own_routes` below is what keeps that honest.
@pytest.mark.parametrize(
    ("key", "expected"),
    (("account_ledger", reports_runner.DatasetNotExecutable),),
)
def test_p2_8_p2_16__the_ledger_target_cannot_be_executed_so_its_pages_stay(
    brazos, key, expected
):
    """**THE CLOCK.** The day either of these serves rows, the page it replaces
    is owed a deletion and this case goes red naming it.

    They fail for two DIFFERENT reasons and the difference decides who does the
    work next, which is why they are not collapsed into one assertion:

      * `account_ledger` → `DatasetNotExecutable`. `journal_lines` has no entry
        in `queries.DATASET_QUERIES` at all. Its four live reports (trial
        balance, journal export, tax remittance, close pack) were turned on with
        per-KEY viewers, not with a dataset query. **This waits for a dataset
        lane.**
      * `statement` → `DatasetCannotServe`. `invoices` HAS a query and declines
        this definition BY NAME, correctly: a statement needs payments as well
        as bills, and serving it from invoices would print a closing balance
        over charges only. **This waits for a ruling about which dataset a
        statement belongs on** — which is not the same work at all.
    """
    owed = [row for row in RETIREMENTS if row[1] == key]
    with tenant_ctx(brazos), pytest.raises(expected) as raised:
        reports_runner.run(key, dict(WINDOW))
    # The refusal NAMES what is missing rather than being a bare
    # NotImplementedError — `DatasetNotExecutable`'s own docstring's reason.
    assert key in str(raised.value)
    # The message a future lane reads on the day this goes green instead.
    assert owed, f"{key} retires no page — RETIREMENTS is out of date"


def test_br_rep_038__the_statement_serves_rows_and_no_longer_refuses(brazos):
    """The other half of the clock: `statement` SERVES, and says which basis.

    ⚠ **IT ASSERTS A SERVED PAYLOAD AND NOT MERELY *no exception*.** A viewer
    that answered an empty report would satisfy `pytest.raises` going away and
    would be the same defect wearing a pass — so this asks for the four things
    `BR-REP-038` names a statement by: the posting basis, the opening balance,
    both movement figures and the closing balance.
    """
    with tenant_ctx(brazos):
        payload = reports_runner.run("statement", dict(WINDOW)).payload
    assert payload["basis"] == "posting", (
        "the statement is struck on the ledger's BOOK date. `0003` seeded it at "
        "the event basis; `0007` moves both the dataset and the basis, and the "
        "journal_lines dataset refuses regulatory_filing over the same mismatch."
    )
    for figure in ("opening_balance", "charges", "payments", "closing_balance"):
        assert figure in payload["totals"], (
            f"a statement without {figure!r} is not a running record. "
            "BR-REP-038: an opening balance, every charge and every payment in "
            "date order, and a closing balance."
        )
    assert [tile["key"] for tile in payload["kpis"]] == [
        "opening_balance",
        "charges",
        "payments",
        "closing_balance",
    ]


def test_p2_8_p2_16__the_three_addresses_are_still_served_by_their_own_routes(brazos):
    """Every one of the three answers TODAY, from a route of its own, and that
    is the state this file is protecting.

    `/reports/account-ledger` and `/reports/by-premises` are
    `apps.reports.api._VIEWERS`' two hand-written entries;
    `/reports/customer-statement` is `apps.customers.api`'s own route and is
    not in the reports dispatcher at all — which is itself worth pinning,
    because a lane retiring "the three report pages" would look for three
    entries in one dict and find two.
    """
    assert reports_api._VIEWERS[reports_api.KEY_ACCOUNT_LEDGER] is reports_api._account_ledger
    assert reports_api._VIEWERS[reports_api.KEY_BY_PREMISES] is reports_api._by_premises
    assert "customer_statement" not in reports_api._VIEWERS
    assert "customer-statement" not in reports_api._VIEWERS


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 2 — the merge that would break S59 without a word
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_8__adding_account_ledger_to_queries_viewers_would_override_the_live_route(brazos):
    """**THE TRAP, ASSERTED RATHER THAN DESCRIBED** (hard-won law 1).

    `_VIEWERS` is `{two hand-written keys, **{every key in queries.VIEWERS}}`.
    A splat wins. So `queries.VIEWERS["account_ledger"] = …` — the obvious first
    move for anyone making the account ledger a definition — replaces
    `_account_ledger` with `runner.run`, and S59, still mounted and still linked
    from Finance, receives `{columns, kpis, rows, window}` where it expects a
    running balance and a footer. **`tsc` passes. Every gate passes. The screen
    renders nothing.**

    This case does not forbid the move. It makes the move IMPOSSIBLE TO MAKE
    QUIETLY: whoever adds the key must delete the page and this case in the same
    commit.
    """
    assert "account_ledger" not in reports_queries.VIEWERS, (
        "`account_ledger` is in queries.VIEWERS, so apps/reports/api._VIEWERS' "
        "dict merge has just overridden `_account_ledger` and the LIVE S59 page "
        "at /reports/account-ledger is receiving the viewer payload instead of "
        "its own. Delete AccountLedgerReportPage.tsx, its route in App.tsx and "
        "its links from Finance in the same commit — or take the key back out."
    )
    assert "by_premises" not in reports_queries.VIEWERS, (
        "same trap, one route along — see the message above for S60 and "
        "ByPremisesReportPage.tsx."
    )
    # Proof the override is real and not a reading of the source: the splat is
    # LAST, so a key present in both resolves to the runner.
    merged = {
        reports_api.KEY_ACCOUNT_LEDGER: reports_api._account_ledger,
        **{key: "the runner" for key in (*reports_queries.VIEWERS, "account_ledger")},
    }
    assert merged[reports_api.KEY_ACCOUNT_LEDGER] == "the runner"


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 3 — the payload shapes, measured side by side
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_8_p2_16__the_viewer_payload_and_the_bespoke_payloads_are_different_shapes(brazos):
    """**WHAT A DEFINITION MUST PRODUCE TO REPLACE THESE PAGES**, pinned so the
    next lane does not have to boot the product to find out.

    A report screen 2·1 can render carries `columns`, `rows`, `kpis`, `window`
    and `totals` — measured off `trial_balance`, which is a live one. The three
    bespoke payloads carry none of those four names. That difference is the
    whole reason `P2.8` and `P2.16` are BACKEND tasks and not the front-end ones
    the brief files them as.
    """
    with tenant_ctx(brazos):
        served = reports_runner.run("trial_balance", dict(WINDOW))
    viewer_shape = {"columns", "rows", "kpis", "window"}
    assert viewer_shape <= set(served.payload), (
        "screen 2·1's payload contract has changed — re-measure it before "
        "trusting the shape delta recorded in this file's docstring"
    )


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 4 — P2.24 has nothing to drill into
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("key", ("ar_aging", "billing_register", "trial_balance"))
#: `area` and `service` are declared by all three datasets below.
#: `route_cycle` is NOT declared by `journal_lines` and is refused by name
#: there — the dimension model working correctly, and not this hold's
#: subject. Asserting it would have made this case fail for the right
#: reason under the wrong heading.
@pytest.mark.parametrize("grouping", ("area", "area,service"))
def test_p2_24__group_by_is_accepted_and_echoed_and_changes_not_one_row(brazos, key, grouping):
    """**`P2.24` IS *DRILL DOWN IN PLACE*, AND THERE IS NO GROUP ROW TO OPEN.**

    `P2.17` landed the grouping on 2026-09-27 (`b7f0be982`). `group_by` is
    bound, checked against the dataset's declared dimensions, checked for
    additivity, and written back into the payload — **and no dataset query
    reads it.** Measured across four servable reports and three groupings:
    **12 of 12 return rows and totals BYTE-IDENTICAL to the ungrouped run**,
    with no group row, no subtotal row and no `groups` key anywhere.

    ⚠ **EVERY CHECK THAT ASKS *WAS THE GROUPING ACCEPTED* PASSES ON THIS**, and
    the payload's own `group_by: ["area"]` reads exactly like a control that
    worked. Hard-won law 7's second shape, and `DEF-REP-6855`. A control must be
    asserted by its EFFECT, never by its echo — which is the one comparison an
    echo cannot fake, and is why this case compares against the ungrouped run
    rather than asserting a shape.

    **THE CLOCK:** the day a dataset query honours `group_by`, this goes red and
    `P2.24` — expand a group row to the level beneath it without a page load —
    becomes buildable. Until then a drill-down control would be a live screen
    behind a dead control, which is law 2's mirror and cost the portal six of
    its eight front doors.
    """
    import json

    with tenant_ctx(brazos):
        plain = reports_runner.run(key, dict(WINDOW))
        grouped = reports_runner.run(key, {**WINDOW, "group_by": grouping})

    # The parameter IS accepted and echoed — half of why this went unnoticed.
    assert grouped.payload.get("group_by") == grouping.split(",")
    # And it changes nothing. When this flips, P2.24 is owed.
    assert json.dumps(plain.rows, default=str) == json.dumps(grouped.rows, default=str), (
        f"`group_by={grouping}` now changes {key}'s rows. P2.17's grouping has "
        "started reaching SQL, so CR-142-BRC07 P2.24 (drill down in place — a "
        "group row opens the level beneath it without a page load) is now "
        "buildable and DEF-REP-6855 can be closed. Delete this case with it."
    )
    assert "groups" not in grouped.payload


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 §4 P2.8 · P2.16 · P2.15 · P2.24 (05-prototype/09 Reports Build Brief.pdf p010-p013 · p069-p073, read as RENDERED IMAGES per B14 rule 42)
# screens: S59 · S60 · RPT-03 (the three this file HOLDS) · 2·1 (the viewer they would retire into)
# generated: 2026-09-27 by lane REP-P2-RETIRE
# gates: RED PROVED FIRST, THROUGH pytest, five breakers — (1) `queries.VIEWERS["account_ledger"] = …` turned THREE cases red including the identity of `_VIEWERS[KEY_ACCOUNT_LEDGER]`, which is the override proved rather than described · (2) a `DATASET_QUERIES["journal_lines"]` entry turned the account-ledger clock red · (3) popping `statement` from `INVOICES_DEFINITIONS_NOT_SERVED` turned the statement clock red · (4) a stubbed `runner.run` payload turned the shape guard red · (5) minting a `by_premises` definition row fired the two-definitions guard, asserted with `pytest.raises(AssertionError, match="by_premises")`.
# exceptions: (1) NOTHING IS RETIRED and nothing is fixed — this file is a HOLD, and every assertion is of the state a lane must not break while the blocker stands · (2) the P2.24 cases group by `area` and `service` and deliberately NOT by `route_cycle`, which `journal_lines` does not declare and refuses by name — the dimension model working correctly, and a case failing for the right reason under the wrong heading is worse than no case · (3) `payments_by_method` is left out of the P2.24 parametrize: DEF-REP-6854 records it does not page at all (70.477s over 40,066 payments, past the 60s worker timeout), so it is a different lane's finding and not this hold's subject · (4) figures quoted in this file's docstrings were RUN on real PostgreSQL 16 against the seeded `brazosbend` tenant, never taken from the brief
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
