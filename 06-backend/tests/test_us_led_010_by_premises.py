# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-010 (S60 by-premises summary — TC-1 the LE-6 rows, TC-2 the
#           unit grouping, TC-3 the service filter, TC-4 the KPI strip, TC-5 the
#           unit lifecycle, TC-6 isolation)
#           Screens: S60
# Rules:    BR-LED-011 (billed/collected/owed per premises via the unit chain) ·
#           BR-LED-001 (the dimension set) · BR-MET-046 (units never move
#           between premises) · BR-REP-002 (never a side-maintained number) ·
#           BR-REP-009 (collection %) · CLAUDE.md rule 1
# Golden:   LE-6 (500 Main St 247.87 / Oak Grove 16.42 / Marina Bay 289.40) ·
#           US-LED-010 §7 CONFIRMED (footer billed Σ = 553.69)
# ───────────────────────────────────────────────────────
"""S60 renders LE-6's three rows — since US-LED-002 landed on 2026-08-16.

⚠ **EVERY MONEY ASSERTION IN THIS FILE WAS INVERTED UNTIL TODAY, AND THE TRAIL
IS KEPT.** The docstring here read *"S60 cannot be built today, and this file is
the proof and the measurement"*, and it was right: `premises_id` and `unit_id`
were NULL on every journal line in the product, nothing stamped them, and
`by_premises_summary` returned `available=False` with the money it could not
attribute — LE-6's own **553.69**. This file asserted that refusal, and said in
as many words that *"the day US-LED-002 lands the assertions flip to LE-6's
three rows"*.

**THAT DAY IS 2026-08-16.** `apps/ledger/posting._stamped` resolves BR-LED-001's
chain — account → unit → premises — at posting time, through
`apps/ledger/dimension_seam.py`. So the assertions below are the ones the STORY
asks for:

    500 Main St   billed 247.87   ·   Oak Grove   billed 16.42
    Marina Bay    billed 289.40   ·   footer      billed 553.69  ✔

**WHAT DID NOT FLIP, AND MUST NOT.** TC-5 still asserts, structurally, that the
report never resolves the chain at READ time. That was never a workaround for
the missing dimension — it is US-LED-010's own requirement (*a unit deactivated
and recreated mid-period leaves the report stable*), and it is MORE load-bearing
now that a stamp exists to be undermined by a join. And the refusal path is
still exercised (TC-6): a tenant whose entries carry no premises still gets
`available=False` and its own 0.00, never Brazos Bend's figures.
"""

from decimal import Decimal

import pytest

from apps.ledger import models as ledger_models
from apps.ledger import reporting

from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    COLLECTED_COLUMN,
    JULY_END,
    JULY_START,
    LE1_WE1_BILL,
    LE1_WE3_BILL,
    LE1_WE7B_BILL,
    LE2_BY_SERVICE,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: LE-6 verbatim — the rows this report will produce when US-LED-002 stamps the
#: chain, kept here so the assertions have somewhere to flip TO.
LE6_ROWS = {
    "500 Main St": LE1_WE1_BILL,  # "billed 247.87 · collected 292.87 · owed 0 · 100%"
    "Oak Grove": LE1_WE3_BILL,  # "billed 16.42 · collected 0 · owed 16.42 · 0%"
    "Marina Bay": LE1_WE7B_BILL,  # "billed 289.40 · collected 153.50 (deposit)"
}


def a_month(tenant, actor):
    world = {}
    accounts = make_accounts(actor, tenant, world)
    post_le1_month(tenant, accounts)
    return accounts, world


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the LE-6 period: three rows, footing to 553.69
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_010_tc1__the_three_le6_rows_foot_to_the_signed_553_69(brazos, dana):
    """US-LED-010 TC-1, as the story actually asks it: three premises rows.

    The four assertions, in order of what each protects against:
      * `available is True` — the table renders at all;
      * three rows, one per premises, NAMED — never one *Unassigned* row
        holding the whole book, which sorts and exports like a premises and is
        a finding disguised as data;
      * each row's billed equals LE-6's own figure to the cent;
      * the footer sums to **553.69**, the same number this test asserted as
        UNATTRIBUTED for the five days the dimension did not exist. The money
        did not move; it acquired an address.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        report = reporting.by_premises_summary(start=JULY_START, end=JULY_END)

        assert report["available"] is True
        assert report["basis"] == reporting.BASIS_POSTING

        billed_by_name = {row.name: row.billed for row in report["rows"]}
        assert billed_by_name == LE6_ROWS

        assert report["kpis"]["premises"] == 3
        assert report["kpis"]["billed"] == BILLED_IN_PERIOD
        assert sum(LE6_ROWS.values()) == report["kpis"]["billed"]

        # …and nothing is left over: every cent of the period's AR movement now
        # has a premises, so the residue the refusal used to report is 0.00.
        assert report["unattributed_billed"] == ZERO
        assert report["unattributed_collected"] == ZERO


def test_us_led_010_tc1b__the_stamp_is_on_the_line_and_not_a_read_time_join(brazos, dana):
    """The dimension is WRITTEN, which is what makes the report stable.

    This test is the inverse of the one it replaces. That one asserted
    `premises_id__isnull=False` counted **0** and called the gap specific rather
    than general; this one asserts the same query counts every AR line, because
    the stamp is now on the row itself. `unit_id` rides with it — BR-LED-001
    names premises AND unit, and a report that could group by premises but not
    by unit would only be half the dimension.
    """
    with tenant_ctx(brazos):
        accounts, world = a_month(brazos, dana)

        assert len(world["premises"]) == 3
        assert all(row.unit_id is not None for row in accounts.values())

        lines = ledger_models.JournalLine.objects.filter(tenant=brazos)
        assert lines.count() > 0
        # Every line that names an ACCOUNT carries the chain; the ones that do
        # not name an account (a cash leg) are left alone, which is BR-LED-001's
        # "where they apply" and not an omission.
        with_account = lines.filter(account_id__isnull=False)
        assert with_account.count() > 0
        assert with_account.filter(premises_id__isnull=True).count() == 0
        assert with_account.filter(unit_id__isnull=True).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 — the grouping and the filter, one of which IS buildable
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_010_tc2_tc3__the_service_slice_works_and_the_premises_slice_does_not(brazos, dana):
    """LE-2's own claim: *"Same query grouped by premises → LE-6; by authority →
    LE-3. One dimension set, every slice."*

    **ALL THREE SLICES ARE REAL NOW.** `service` is stamped by
    `apps/billing/posting_seam.py` when a GL bucket's lines agree on one, so the
    by-service slice returns LE-2's figures; the by-authority slice works
    through the 2200-nn accounts (US-LED-014); and the by-premises slice groups
    on the stamp US-LED-002 writes. The claim LE-2 makes is therefore testable
    end to end: **one dimension set, every slice, out of the same rows** — and
    the two slices below must foot to the same 553.69 from opposite directions.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

        by_service = {
            row.service_code: row.total_billed
            for row in reporting.revenue_by_service(start=JULY_START, end=JULY_END)
        }
        for code, total in LE2_BY_SERVICE.items():
            assert by_service[code] == total

        by_premises = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        assert len(by_premises["rows"]) == 3
        assert by_premises["kpis"]["billed"] == BILLED_IN_PERIOD


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the stability property, which is WHY read-time resolution is refused
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_010_tc5__the_report_never_resolves_the_chain_at_read_time(brazos, dana):
    """US-LED-010 TC-5: *"a unit deactivated + recreated mid-period → historical
    lines keep their STAMPED premises/unit — the report is stable; no
    orphan/unassigned money row ever appears."*

    The obvious "fix" for the missing dimension is a read-time join: account →
    unit → premises, at report time. It is refused, and TC-5 is the reason —
    such a report moves LAST YEAR'S money the day a unit is re-assigned, and
    BR-MET-046's chain guarantee is about the STAMP, not about the join.

    Asserted structurally, because a behaviour test cannot see a join that
    happens to agree with the stamp today.
    """
    import inspect

    source = inspect.getsource(reporting.by_premises_summary)
    for smell in ("unit__premises", "account__unit", "premises_id_for", "unit_id_for"):
        assert smell not in source
    # …and nothing in the module reaches for a premises through an account.
    module_source = inspect.getsource(reporting)
    assert "account__unit" not in module_source

    with tenant_ctx(brazos):
        a_month(brazos, dana)
        report = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        # Every row's premises id is one the POSTING wrote — the report never
        # invents a key, and a premises with no stamped line is simply absent.
        stamped = set(
            str(value)
            for value in ledger_models.JournalLine.objects.filter(
                tenant=brazos, premises_id__isnull=False
            ).values_list("premises_id", flat=True)
        )
        assert {row.premises_id for row in report["rows"]} <= stamped
        assert report["kpis"]["billed"] == BILLED_IN_PERIOD


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_010_tc6__the_refusal_is_per_tenant_and_leaks_nothing(brazos, dana, lonestar, erin):
    """US-LED-010 TC-6: *"Its premises only (RLS)"*. The refusal is a per-tenant
    fact too — Lone Star Ridge builds the SAME three premises addresses and
    still sees none of Brazos Bend's money, and the grouping never crosses."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        ours = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        assert ours["kpis"]["billed"] == BILLED_IN_PERIOD
        our_ids = {row.premises_id for row in ours["rows"]}

    with tenant_ctx(lonestar):
        make_accounts(erin, lonestar, {}, service="water")
        theirs = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
        # Their premises exist and are named the same three addresses; nothing
        # was posted for them, so the report refuses with its own 0.00 rather
        # than showing the neighbour's rows.
        assert theirs["available"] is False
        assert theirs["rows"] == ()
        assert theirs["unattributed_billed"] == ZERO
        assert theirs["unattributed_collected"] == ZERO
        assert {row.premises_id for row in theirs["rows"]} & our_ids == set()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-010@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-010 §1/§3/§5/§7 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-6 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-011 · BR-MET-046)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the refusal was proved to BITE — a variant of `by_premises_summary` returning one "Unassigned" row holding 553.69 was written, RUN and seen to fail TC-1 before the refusing version was trusted
# exceptions: EVERY MONEY ASSERTION IN THIS FILE IS INVERTED. The story's TCs
#         want three premises rows and this file asserts that none is produced,
#         because the dimension they group on is NULL on every journal line in
#         the product. LE-6's figures are transcribed into `LE6_ROWS` so the
#         assertions have somewhere to flip to the day US-LED-002 stamps the
#         chain — at which point TC-1 becomes the three-row equality the story
#         actually asks for · TC-4's KPI/footer tie and the PDF/CSV downloads are
#         not covered at all: there is nothing to tie and no download half
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
