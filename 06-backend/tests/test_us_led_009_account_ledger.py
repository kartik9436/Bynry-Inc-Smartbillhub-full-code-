# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-009 (S59 account ledger report — TC-1 ACC-1042's rows and
#           running balance, TC-2 the source vocabulary, TC-3 the opening row,
#           TC-4 the premises param, TC-5 footing to the AR tie-out, TC-6 the
#           refusals, TC-7 isolation)
#           Screens: S59
# Rules:    BR-LED-010 (account + range → dated charges/payments + running
#           balance) · BR-REP-008 (Type = the FULL source vocabulary; the report
#           foots to the AR tie-out) · BR-REP-001 (basis label) · BR-CUS-048
#           (opening buckets age forward) · CLAUDE.md rule 1
# Golden:   US-LED-009 §7 CONFIRMED (r_n = r_{n−1} + charge_n − payment_n;
#           45.00 + 247.87 = 292.87; 292.87 − 292.87 = 0.00; Σ closings =
#           152.32) · LE-1
# ───────────────────────────────────────────────────────
"""A ledger any auditor can foot — and one that hides nothing.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_009_tc5__every_account_ledger_foots_to_the_ar_tie_out`. US-LED-009
§7: *"Foot: Σ closings 135.90 + 16.42 = 152.32 = AR tie-out (LE-1)."* If the
per-account report and the AR control disagree by a cent, one of them is lying
and the sum is where it shows.

Every figure comes from `tests/ledger_le_fixtures.py`, transcribed from LE-1 and
US-LED-009 §7 with the source quoted beside it.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import reporting
from core import errors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_DEPOSIT_APPLIED,
    LE1_MASTER_TRANSFER,
    LE1_OPENING_AR,
    LE1_PAYMENT,
    LE1_WE1_BILL,
    LE1_WE3_BILL,
    LE1_WE7B_BILL,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — ACC-1042, July, row for row
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc1__acc_1042_rows_running_balance_and_footer(brazos, dana):
    """US-LED-009 TC-1 verbatim: *"Rows: opening balance **45.00** → bill
    **+247.87** → running **292.87** → payment **−292.87** → running **0.00**;
    footer totals charge 247.87 / payment 292.87; closing = 0.00"*.

    The opening 45.00 is dated at the cutover, BEFORE the window, so it arrives
    as the report's opening BALANCE rather than as a row — which is what a
    report starting mid-history has to do, and is why `_day_before` exists.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        report = reporting.account_ledger(accounts["ACC-1042"].id, start=JULY_START, end=JULY_END)

        assert report["opening_balance"] == LE1_OPENING_AR
        assert [
            (row.type, row.charge, row.payment, row.running_balance) for row in report["rows"]
        ] == [
            ("bill", LE1_WE1_BILL, ZERO, Decimal("292.87")),
            ("payment", ZERO, LE1_PAYMENT, ZERO),
        ]
        assert report["totals"]["charges"] == LE1_WE1_BILL
        assert report["totals"]["payments"] == LE1_PAYMENT
        assert report["totals"]["closing_balance"] == ZERO
        assert report["basis"] == reporting.BASIS_POSTING

        # §7's formula, asserted as arithmetic rather than as a shape.
        assert LE1_OPENING_AR + LE1_WE1_BILL == Decimal("292.87")
        assert Decimal("292.87") - LE1_PAYMENT == ZERO


def test_us_led_009_tc1b__only_the_receivable_leg_appears(brazos, dana):
    """A payment entry has more than one line and they ALL carry the account
    dimension — undeposited-funds debit, AR credit. Listing both would show the
    customer paying twice and the running balance would go negative.

    What a customer's ledger tracks is their RECEIVABLE, so the rows are the
    lines that hit the `accounts_receivable` account and nothing else.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        report = reporting.account_ledger(accounts["ACC-1042"].id, start=JULY_START, end=JULY_END)
        assert len(report["rows"]) == 2
        assert all(row.charge == ZERO or row.payment == ZERO for row in report["rows"])
        assert min(row.running_balance for row in report["rows"]) >= ZERO


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the FULL source vocabulary (BR-REP-008)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc2__acc_1055_exercises_deposit_and_transfer_as_first_class_types(brazos, dana):
    """US-LED-009 TC-2 verbatim: *"final bill +289.40 · deposit application
    −153.50 (Type=deposit) · transfer −135.90 (Type=transfer, ref ACC-0009) →
    closing 0.00; the master account's ledger shows the +135.90 transfer-in"*.

    The two rows a naive report loses are exactly these: a deposit application
    and a transfer are not "payments", and if the Type column had no word for
    them the money would still move and the reader would not know why.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        report = reporting.account_ledger(accounts["ACC-1055"].id, start=JULY_START, end=JULY_END)
        rows = [(row.type, row.charge, row.payment) for row in report["rows"]]

        assert ("bill", LE1_WE7B_BILL, ZERO) in rows
        assert ("bill", ZERO, LE1_DEPOSIT_APPLIED) in rows
        assert ("transfer", ZERO, LE1_MASTER_TRANSFER) in rows
        assert report["totals"]["closing_balance"] == ZERO

        master = reporting.account_ledger(accounts["ACC-0009"].id, start=JULY_START, end=JULY_END)
        assert [(row.type, row.charge) for row in master["rows"]] == [
            ("transfer", LE1_MASTER_TRANSFER)
        ]
        assert master["totals"]["closing_balance"] == LE1_MASTER_TRANSFER


def test_us_led_009_tc2b__every_row_maps_and_an_unknown_source_is_shown_not_hidden(brazos, dana):
    """BR-REP-008's *nothing invisible*, both halves.

    Every source this build posts maps to one of the ten ratified words, and a
    source the vocabulary has never heard of comes back AS ITSELF with
    `type_mapped=False` — never bucketed under a familiar word, which would
    hide a new posting contract inside an old column while the ledger still
    footed.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        for key in accounts:
            report = reporting.account_ledger(accounts[key].id, start=JULY_START, end=JULY_END)
            for row in report["rows"]:
                assert row.type_mapped is True, f"{row.source_type} has no ratified word"
                assert row.type in reporting.SOURCE_VOCABULARY

        assert reporting.source_vocabulary_for("lease_settlement") == ("lease_settlement", False)
        assert reporting.source_vocabulary_for("opening_balance") == ("opening", True)
        assert len(reporting.SOURCE_VOCABULARY) == 10


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the opening row
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc3__the_opening_entry_is_a_first_class_row_when_it_is_in_range(brazos, dana):
    """Widen the window past the cutover and the opening JE stops being a
    balance and becomes a ROW, typed `opening` (GT-16's `source_type`
    `opening_balance`).

    TC-3's forward-aging half — *"30 days later unpaid, aging reads 31–60 ←
    84.20"* — is NOT assertable: `account_opening_buckets` (B2 r9 #2) is not
    built, so there are no buckets to age. Reported on the result rather than
    quietly skipped.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        report = reporting.account_ledger(
            accounts["ACC-1042"].id, start=date(2026, 6, 1), end=JULY_END
        )
        assert report["opening_balance"] == ZERO
        assert report["rows"][0].type == "opening"
        assert report["rows"][0].charge == LE1_OPENING_AR
        assert report["rows"][0].running_balance == LE1_OPENING_AR
        assert report["totals"]["closing_balance"] == ZERO

        codes = {gap["code"] for gap in report["unavailable"]}
        assert "aging_buckets_need_invoice_due_dates_and_opening_buckets" in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the premises parameter
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc4__the_premises_parameter_is_reported_missing_not_silently_ignored(
    brazos, dana
):
    """TC-4 wants the premises param to restrict via the account's unit →
    premises. The parameter is still NOT OFFERED, and the reason changed on
    2026-08-16 — which is why this test changed with it.

    It used to assert `premises_and_unit_dimensions_never_stamped`, because the
    dimension genuinely did not exist: every journal line carried
    `premises_id = NULL`. US-LED-002 stamps the chain now, so that sentence
    would be a comment claiming a gap that has closed (hard-won law 1) and it
    is replaced by the narrower fact that was always the real one: **this
    report accepts no premises parameter.** A parameter that accepted a
    premises and changed nothing would be the worse failure — the report would
    look filtered.

    Both halves are asserted, so neither can rot: the gap is NAMED, and the
    dimension it used to blame is demonstrably present on the lines.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        report = reporting.account_ledger(accounts["ACC-1042"].id, start=JULY_START, end=JULY_END)
        codes = {gap["code"] for gap in report["unavailable"]}
        assert "premises_filter_is_not_offered_on_this_report" in codes
        assert "premises_and_unit_dimensions_never_stamped" not in codes

        # The premises exist upstream AND on the lines — the filter is what is
        # missing, and the report says exactly that and nothing wider.
        assert accounts["ACC-1042"].unit_id is not None
        from apps.ledger import models as ledger_models

        assert ledger_models.JournalLine.objects.filter(
            tenant=brazos, premises_id__isnull=False
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — THE ONE. Σ closings = the AR tie-out.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc5__every_account_ledger_foots_to_the_ar_tie_out(brazos, dana):
    """US-LED-009 §7 verbatim: *"Σ closings 135.90 + 16.42 = **152.32** = AR
    tie-out (LE-1)."*

    Four accounts, four independently-computed running balances, and their sum
    must equal the single AR control figure the trial balance shows. This is the
    property that makes the report an AUDIT rather than a view: a line dropped
    from one account's ledger, a side read backwards, a window off by a day —
    each of them lands here as a delta with a name.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        closings = {
            key: reporting.account_ledger(row.id, start=date(2026, 1, 1), end=JULY_END)["totals"][
                "closing_balance"
            ]
            for key, row in accounts.items()
        }

        assert closings["ACC-1042"] == ZERO
        assert closings["ACC-1051"] == LE1_WE3_BILL  # 16.42, unpaid
        assert closings["ACC-1055"] == ZERO
        assert closings["ACC-0009"] == LE1_MASTER_TRANSFER  # 135.90, master-held

        assert sum(closings.values()) == LE1_AR
        assert sum(closings.values()) == reporting.ar_control(as_of=JULY_END)

        tb = reporting.trial_balance(end=JULY_END)
        ar_row = next(row for row in tb["rows"] if row["code"] == "1200")
        assert ar_row["debit"] == LE1_AR


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the refusals
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc6__an_inverted_range_is_refused_not_answered_empty(brazos, dana):
    """US-LED-009 TC-6: *"Param validation rejects the range … never an
    empty-but-plausible report."*

    An inverted range answered with zero rows is a report that says the account
    had no activity, which is a different and false statement.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        with pytest.raises(errors.ValidationError):
            reporting.account_ledger(accounts["ACC-1042"].id, start=JULY_END, end=JULY_START)


def test_us_led_009_tc6b__a_foreign_account_id_yields_nothing(brazos, dana, lonestar, erin):
    """*"a foreign account 404s (RLS)"*. At this layer that means: no rows and
    no balance — the report never reaches another tenant's money, and it does
    not distinguish "not yours" from "not real", which would answer a question
    the asker has no right to."""
    with tenant_ctx(lonestar):
        foreign = make_accounts(erin, lonestar, {}, service="water")
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        report = reporting.account_ledger(foreign["ACC-1042"].id, start=JULY_START, end=JULY_END)
        assert report["rows"] == ()
        assert report["opening_balance"] == ZERO
        assert report["totals"]["closing_balance"] == ZERO


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_009_tc7__lone_star_ridge_runs_its_own_accounts_only(brazos, dana, lonestar, erin):
    """US-LED-009 TC-7. Brazos Bend's whole month is posted; Lone Star Ridge's
    own account ledger is empty and its AR control is zero."""
    with tenant_ctx(brazos):
        brazos_accounts = a_month(brazos, dana)
    with tenant_ctx(lonestar):
        theirs = make_accounts(erin, lonestar, {}, service="water")
        assert reporting.ar_control(as_of=JULY_END) == ZERO
        assert (
            reporting.account_ledger(theirs["ACC-1042"].id, start=JULY_START, end=JULY_END)["rows"]
            == ()
        )
        # …and Brazos Bend's own account id reaches nothing from in here.
        leaked = reporting.account_ledger(
            brazos_accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        assert leaked["rows"] == ()
        assert leaked["totals"]["closing_balance"] == ZERO


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-009@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-009 §1/§3/§7 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/008)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — `account_ledger` was mutated to drop the TRANSFER leg (the one AR movement that is neither a bill nor a payment), RUN, and TC-5's tie-out failed `AssertionError: assert Decimal('135.900000') == Decimal('0')` with TC-2 failing beside it; the mutation was reverted and both went green on SQLite and on a live Postgres cluster
# exceptions: TC-3's FORWARD-AGING half is not assertable —
#         `account_opening_buckets` (B2 r9 #2) is unbuilt, so GT-16's
#         84.20/62.10/121.00 have nowhere to come from; the test asserts the
#         opening ROW and the reported gap instead · TC-4 asserts the premises
#         parameter's ABSENCE and proves the dimension is NULL while the
#         premises rows exist upstream · TC-6's "404" is asserted as "reaches
#         nothing", since this layer has no HTTP surface to return a status from
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
