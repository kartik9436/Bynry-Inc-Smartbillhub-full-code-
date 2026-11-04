# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (S36 Revenue & AR — TC-1 the LE-1 month's strip, TC-2 the
#           LE-2 revenue-by-service slice, TC-3 the aging panel, TC-4 the basis
#           labels, TC-5 the cache/invoice divergence, TC-6 isolation)
#           Screens: S36
# Rules:    BR-LED-016 (the strip is dimension-derived) · BR-LED-007 (tie-out) ·
#           BR-REP-001 (every figure labels its basis) · BR-REP-002 (never a
#           side-maintained number) · BR-REP-009 (collection %) · BR-REP-011
#           (DSO) · BR-REP-014 (BILL-purpose payments only) · CLAUDE.md rule 1
# Golden:   LE-1 (598.69 = 598.69) · LE-2 (revenue by service) · LE-6 (the KPI
#           strip's collected column 446.37) · US-LED-007 §7 CONFIRMED
# ───────────────────────────────────────────────────────
"""S36's numbers come out of the books or they do not exist.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_007_tc5__a_cache_or_invoice_kpi_diverges_and_the_strip_still_reads_the_ledger`.
It plants two lies — an `accounts.balance` cache 1,000.00 out and an issued
invoice whose total no journal entry ever carried — and asserts that every KPI
still reports the posted figure. US-LED-007 TC-5 in one sentence: *"the strip
reads dimensions; the divergence surfaces as a US-LED-004 drift red flag — no
silent cache number ever renders."*

EVERY EXPECTED FIGURE IS COPIED FROM LE-1 / LE-2 / LE-6 / US-LED-007 §7 through
`tests/ledger_le_fixtures.py`, where each one is quoted beside the line it came
from. Nothing here recomputes an expectation — a test that did would agree with
a broken implementation.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import reporting

from tests.isolation_helpers import live_tenant_context  # noqa: F401 — parity with the suite
from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    COLLECTED_COLUMN,
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_CASH_REALISED,
    LE1_CASH_UNDEPOSITED,
    LE1_DEPOSIT_APPLIED,
    LE1_FOOTING,
    LE1_PAYMENT,
    LE1_REVENUE,
    LE2_BY_SERVICE,
    WE1_REVENUE,
    make_accounts,
    post_le1_month,
    reconcile_the_payment,
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
# TC-1 — the strip, and every figure of it footing to the trial balance
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc1__the_le1_strip_foots_to_the_trial_balance(brazos, dana):
    """US-LED-007 TC-1 + §7: billed **553.69**, still owed **152.32**, and the
    period's trial balance **598.69 = 598.69**, all out of `journal_lines`.

    The collected COLUMN is LE-6's own KPI-strip figure — *"collected 446.37
    (292.87 + 153.50)"* — the payment plus the applied deposit, which BR-REP-009
    counts (*"applied deposits count as collected"*).
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)
        kpis = strip["kpis"]

        assert kpis["billed"] == BILLED_IN_PERIOD, "billed must be Σ AR debits from bills"
        assert kpis["collected"] == COLLECTED_COLUMN
        assert kpis["collected_from_cash"] == LE1_PAYMENT
        assert kpis["collected_from_applied_deposits"] == LE1_DEPOSIT_APPLIED
        assert kpis["still_owed"] == LE1_AR

        # …and the same books, presented as the trial balance, foot to LE-1.
        tb = reporting.trial_balance(start=None, end=JULY_END)
        assert tb["balanced"] is True
        assert tb["total_debit"] == LE1_FOOTING
        assert tb["total_credit"] == LE1_FOOTING
        assert tb["difference"] == ZERO

        # The AR row of that trial balance IS the Still-owed KPI. One
        # derivation; a screen and a KPI cannot disagree (BR-REP-002).
        ar_row = next(row for row in tb["rows"] if row["code"] == "1200")
        assert ar_row["debit"] == kpis["still_owed"] == LE1_AR
        # …and its GROSS sides are still visible, which is the only way to see
        # that the master transfer wrote two rows rather than none.
        assert ar_row["gross_debit"] - ar_row["gross_credit"] == LE1_AR
        assert ar_row["gross_debit"] > ar_row["debit"]


def test_us_led_007_tc1b__accounts_owing_sums_back_to_the_ar_control(brazos, dana):
    """The strip's *"184 accounts"* counterpart, and it ties.

    Two accounts owe at the end of LE-1's month — Oak Grove's unpaid **16.42**
    and the master account's transferred-in **135.90** — and LE-1's own tie-out
    line says exactly that: *"ending AR 152.32 = master-held transfer 135.90 +
    unpaid WE-3 16.42"*.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)
        assert strip["kpis"]["accounts_owing"] == 2
        assert reporting.ar_control(as_of=JULY_END) == LE1_AR
        assert Decimal("135.90") + Decimal("16.42") == LE1_AR


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the LE-2 revenue-by-service slice
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc2__revenue_by_service_is_the_le2_slice(brazos, dana):
    """LE-2 verbatim over WE-1's own day: *"Electric 100.60 (usage 88.60 + base
    12.00) · Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar capacity 40.00 ·
    Late fee 5.00 = 226.90 ✔"*.

    The electric and water rows also prove the usage/base split resolves from
    the TENANT's pointer (4100/4105, 4110/4115) rather than from a line "kind"
    the journal does not carry.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        rows = reporting.revenue_by_service(start=date(2026, 7, 15), end=date(2026, 7, 15))
        by_code = {row.service_code: row for row in rows}

        for code, total in LE2_BY_SERVICE.items():
            assert by_code[code].total_billed == total, f"{code} is not LE-2's figure"
        assert by_code["electric"].usage == Decimal("88.60")
        assert by_code["electric"].base_and_fees == Decimal("12.00")
        assert by_code["water"].usage == Decimal("39.50")
        assert by_code["water"].base_and_fees == Decimal("8.00")

        # The late fee has NO service and its row is KEPT, labelled None. If it
        # were dropped the table would foot to 221.90 and quietly under-report
        # the bill by 5.00 — the silent shortfall BR-REP-002 exists to prevent.
        assert by_code[None].total_billed == Decimal("5.00")
        assert sum(row.total_billed for row in rows) == WE1_REVENUE


def test_us_led_007_tc2b__the_months_service_rows_foot_to_the_revenue_control(brazos, dana):
    """Every revenue row of the month sums to LE-1's **506.31**, unattributed
    money included.

    That is the property that makes the panel trustworthy: a service breakdown
    whose rows do not sum to the revenue control is a breakdown of something
    else.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        rows = reporting.revenue_by_service(start=JULY_START, end=JULY_END)
        assert sum(row.total_billed for row in rows) == LE1_REVENUE

        tb = reporting.trial_balance(start=JULY_START, end=JULY_END)
        revenue_control = sum(
            (row["credit"] - row["debit"] for row in tb["rows"] if row["type"] == "revenue"),
            ZERO,
        )
        assert revenue_control == LE1_REVENUE


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the aging panel, and the honest shape of a gap
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc3__aging_is_unavailable_and_names_why_never_four_zeros(brazos, dana):
    """TC-3 wants buckets summing to Still owed. A journal line carries no DUE
    DATE, so they cannot be summed out of the books — and the panel says so.

    The failure this asserts against is four confident zeros in a *Who owes you*
    table under a Total owed of 152.32: a clerk reads it as "nothing is
    overdue".
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)

        assert strip["aging"] is None
        codes = {gap["code"] for gap in strip["unavailable"]}
        assert "aging_buckets_need_invoice_due_dates_and_opening_buckets" in codes
        # The TOTAL the buckets must sum to is derivable and IS reported, so a
        # screen renders the total and the reason, never a fabricated split.
        assert strip["kpis"]["still_owed"] == LE1_AR


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — basis labels, and the percentage that is not invented
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc4__every_group_labels_its_basis(brazos, dana):
    """BR-REP-001: *"no unlabeled money number anywhere"*. The label travels ON
    the data, not in a caption a screen can forget to render."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)

        assert strip["basis"] == reporting.BASIS_POSTING
        assert strip["adjustments"]["basis"] == reporting.BASIS_POSTING
        assert reporting.trial_balance(end=JULY_END)["basis"] == reporting.BASIS_POSTING
        # Cash is the one CLEARING-basis group, and it says so.
        assert strip["cash"]["basis"] == reporting.BASIS_CLEARING


def test_us_led_007_tc4b__collection_pct_is_none_rather_than_the_wrong_ratio(brazos, dana):
    """BR-REP-009's percentage needs *cash applied to bills IN PERIOD* — which
    the books do not record (a payment entry credits AR in one lump).

    US-LED-007 §7 works it to **401.37 ÷ 553.69 = 72.49%**. The number this
    module COULD compute from what it holds is 446.37 ÷ 553.69 = **80.62%** — a
    different ratio wearing the ruled one's name, and 8 points more flattering.
    So the KPI is None with the reason attached, and this test pins that the
    plausible answer is never returned.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)

        assert strip["kpis"]["collection_pct"] is None
        codes = {gap["code"] for gap in strip["unavailable"]}
        assert "which_bill_a_payment_met_is_not_in_the_books" in codes

        wrong = (strip["kpis"]["collected"] / strip["kpis"]["billed"] * 100).quantize(
            Decimal("0.01")
        )
        assert wrong == Decimal("80.62")
        assert wrong != Decimal("72.49"), "the ruled figure and the derivable one differ"


def test_us_led_007_tc4c__written_off_is_its_own_kpi_and_never_inside_collected(brazos, dana):
    """BR-REP-009: *"write-offs excluded, shown separately"*.

    Nothing posts a write-off in this build, so the honest figure is **0.00** —
    a number, reported, distinct from the aging panel's `None`. "Nobody has
    written anything off" and "this cannot be known" are different answers and
    the strip gives each its own shape.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END, ytd_start=date(2026, 1, 1))
        assert strip["kpis"]["written_off_ytd"] == ZERO
        assert strip["kpis"]["collected"] == COLLECTED_COLUMN

        # …and the panel's LATE-FEE row is None rather than a number matched on
        # a mutable account NAME. 4200 Late-fee revenue carries no designation
        # (the PO ruled eleven and reserved nothing, OQ-110), a fee carries no
        # service dimension, and `apps/ledger/chart.py` forbids reading the
        # number — so the honest answer is the named gap. WE-1 posted a real
        # 5.00 late fee in this month, so a name-matching implementation would
        # have looked right here and gone silent the day a tenant renamed 4200.
        panel = strip["adjustments"]
        assert panel["late_fees_applied"] is None
        assert panel["credits_issued"] == ZERO
        assert {gap["code"] for gap in panel["unavailable"]} >= {
            "late_fee_revenue_has_no_designation"
        }


def test_us_led_007_tc4d__realised_cash_excludes_money_a_clerk_merely_keyed(brazos, dana):
    """PO ruling 2026-08-11 (OQ-143): *"until bank record and reconcilaition
    confirm it it is not realised."*

    LE-1's month, unbanked: **150.00** realised (the deposit, per the signed
    contract row) and **292.87** sitting in undeposited funds. The two are
    returned separately and never added — a cash-basis report that summed them
    would tell this utility it has 442.87 in the bank when 292.87 is in a
    drawer.

    Then the bank confirms, and the SAME function moves the money: realised
    442.87, undeposited 0.00, with no figure invented in between.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        cash = reporting.cash_position(end=JULY_END)
        assert cash["realised"] == LE1_CASH_REALISED
        assert cash["undeposited"] == LE1_CASH_UNDEPOSITED
        assert cash["realised"] != Decimal("442.87")

        reconcile_the_payment(brazos, accounts)
        after = reporting.cash_position(end=JULY_END)
        assert after["realised"] == Decimal("442.87")
        assert after["undeposited"] == ZERO
        # The books did not change size — money moved between two asset
        # accounts, so the trial balance still foots to LE-1's total.
        assert reporting.trial_balance(end=JULY_END)["total_debit"] == LE1_FOOTING


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — THE ONE. A cache and an invoice both lie; the strip does not.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc5__a_cache_or_invoice_kpi_diverges_and_the_strip_still_reads_the_ledger(
    brazos, dana
):
    """US-LED-007 TC-5: *"KPI computed from the `accounts.balance` cache diverges
    from dimension-derived AR … the strip reads dimensions; no silent cache
    number ever renders."*

    Two divergences are planted, because the two ways a parallel number gets
    into a finance screen are a CACHE and a REGISTER:

      1. `accounts.balance` is set to 1,000.00 on every account — a cache
         2,847.68 away from the ledger's 152.32.
      2. an **issued** invoice for 999.99 exists that no journal entry ever
         carried — a bill that reached a customer and not the books, which is
         precisely the state `apps/billing/posting_seam.py` was written to
         prevent and which a report must survive.

    Both are ignored. `billed` stays **553.69** and `still_owed` stays
    **152.32**, because every figure is a sum over `journal_lines` and this
    module has no code path that reads either table.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)

        customer_models.Account.objects.filter(
            tenant=brazos, id__in=[row.id for row in accounts.values()]
        ).update(balance=Decimal("1000.00"))
        cached_total = sum(
            customer_models.Account.objects.filter(tenant=brazos).values_list("balance", flat=True)
        )

        from apps.billing import models as billing_models

        billing_models.Invoice.objects.create(
            tenant=brazos,
            account=accounts["ACC-1042"],
            service_date=date(2026, 7, 18),
            period_start=JULY_START,
            period_end=JULY_END,
            status="issued",
            subtotal=Decimal("999.99"),
            total=Decimal("999.99"),
        )
        register_total = sum(
            billing_models.Invoice.objects.filter(tenant=brazos, status="issued").values_list(
                "total", flat=True
            )
        )

        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)

        # The two parallel numbers disagree with the books, loudly.
        assert cached_total != strip["kpis"]["still_owed"]
        assert cached_total - strip["kpis"]["still_owed"] == Decimal("3847.68")
        assert register_total == Decimal("999.99")
        assert register_total != strip["kpis"]["billed"]

        # …and the strip reports the LEDGER, unmoved by either.
        assert strip["kpis"]["still_owed"] == LE1_AR
        assert strip["kpis"]["billed"] == BILLED_IN_PERIOD
        assert reporting.trial_balance(end=JULY_END)["total_debit"] == LE1_FOOTING


def test_us_led_007_tc5b__the_module_reads_no_register_at_all(brazos, dana):
    """The structural half of TC-5, asserted on the SOURCE rather than on a
    behaviour — because a behaviour test passes for a module that reads a
    register and happens to agree with it today.

    `apps/ledger/reporting.py` may not import billing, payments or customers.
    Cross-module reads go through published service functions (B1) and there is
    no report figure that needs one; if a future figure does, the seam is
    resolved BY NAME the way `apps/billing/posting_seam.py` does, and this test
    is where that decision becomes visible.
    """
    import inspect

    source = inspect.getsource(reporting)
    for forbidden in ("apps.billing", "apps.payments", "apps.customers", "accounts.balance"):
        assert f"import {forbidden}" not in source
        assert f"from {forbidden}" not in source
    assert "Invoice" not in source.split('"""')[-1]


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_007_tc6__lone_star_ridge_sees_only_its_own_books(brazos, dana, lonestar, erin):
    """US-LED-007 TC-6: *"Its dimensions only (RLS); Brazos Bend figures never
    leak into any panel."*

    Brazos Bend posts the whole LE-1 month; Lone Star Ridge posts nothing. Its
    strip is zeros and its trial balance is empty — not Brazos Bend's numbers,
    and not an error.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        assert reporting.revenue_and_ar(start=JULY_START, end=JULY_END)["kpis"]["billed"] == (
            BILLED_IN_PERIOD
        )

    with tenant_ctx(lonestar):
        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)
        assert strip["kpis"]["billed"] == ZERO
        assert strip["kpis"]["still_owed"] == ZERO
        assert reporting.trial_balance(end=JULY_END)["rows"] == ()
        assert reporting.revenue_by_service(start=JULY_START, end=JULY_END) == ()
        assert reporting.cash_position(end=JULY_END)["realised"] == ZERO


def test_us_led_007_tc6b__no_tenant_context_is_refused_not_defaulted(brazos, dana):
    """CLAUDE.md rule 1 applies to READS. A report that ran with no tenant
    context would sum two utilities' books into one trial balance on the SQLite
    developer database, where RLS is not there to stop it."""
    from core import errors

    with tenant_ctx(brazos):
        a_month(brazos, dana)
    with pytest.raises(errors.AuthError):
        reporting.revenue_and_ar(start=JULY_START, end=JULY_END)
    with pytest.raises(errors.AuthError):
        reporting.trial_balance(end=JULY_END)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-007 §1/§3/§7 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1/LE-2/LE-6 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002/009/011/014 · 12-governance/02-decision-log.md 2026-08-11 OQ-143)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: TC-5 was PROVED RED FIRST — `revenue_and_ar` was mutated to read Σ accounts.balance for `still_owed`, the run failed on this file, and the verbatim failure is quoted in the lane report and the human-review row
# exceptions: TC-3's bucket assertion is inverted — the epic wants four buckets
#         summing to Still owed and the books hold no due date, so the test
#         asserts the REFUSAL and the total instead; when US-CUS-022 lands the
#         assertion flips to the four figures · TC-4's collection-% case asserts
#         the ruled 72.49% is NOT produced rather than that it IS, for the same
#         reason · the isolation case is marked `isolation` so the release-gate
#         suite runs it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
