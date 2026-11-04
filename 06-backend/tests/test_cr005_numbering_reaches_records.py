# ── Trace ──────────────────────────────────────────────
# Change:  CR-005 (SET-08 Numbering) — the CLOSING LOOP, asked for by the PO on
#          2026-08-17: *"will it work whnen we create new account, device etc -
#          will it assign new number based on this selection or settings?"* and
#          then, when the first answer covered only two: *"not just both - all
#          number thata re set - i think there are 14 or more"*.
# Story:   US-TEN-012 (EP-TEN-08) · Screens: S8 / r10 SET-08
# Rules:   BR-TEN-035 (format grammar; future-only; forward-only counters) ·
#          BR-TEN-043 (the issue date is an INPUT, never the wall clock)
# ───────────────────────────────────────────────────────
"""Does a format an admin picks on the Settings screen actually reach a record?

**THE QUESTION IS "BUILT IS NOT WIRED" (hard-won law 2) AIMED AT CR-005**, and it
is the right question to aim there: CR-005 shipped a screen that writes twenty-two
`number_series` rows, and a screen that writes rows nothing reads would look
identical from the outside. Its own tests proved the SCREEN and the ALLOCATOR;
neither proved that picking `CUST-{YYYY}-{000000}` is what a new account is
actually called.

**Twenty-two, not two.** The first cut of this file checked `account` and
`asset`, and the PO corrected it — *"all number thata re set"*. A sweep is also
the only shape that survives the next series being added, which is exactly how
`SERIES_DEFAULTS` came to hold five entries while `KNOWN_SERIES` held nine and
every manual journal entry went unnumbered (BR-LED-021 (i)).

**What this file proves and what it deliberately does not.** It proves the loop
from *format saved* → *number rendered*, for every series, through the real sink
the real callers use. It does **not** prove that every series has a caller — that
is a different fact, it is not true today, and `test_which_series_have_a_live_consumer`
below records it honestly rather than leaving it implied.
"""

from datetime import date

import pytest
from django.db import transaction

from apps.tenancy import services as tenancy_services
from core import numbering as cn

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import admin_actor, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

ISSUE_DATE = date(2026, 8, 17)

#: A format per series, deliberately DISTINCT from every seeded default, so a
#: pass cannot come from the seed happening to match. Each exercises the token
#: grammar rather than being decorative: a year, a short year+month, a full
#: date and a bare counter.
PROBES = (
    ("{YYYY}-{00000}", "2026-00042", 42),
    ("ZZ-{YY}{MM}-{0000}", "ZZ-2608-0042", 42),
    ("Q{YY}{MM}{DD}-{000}", "Q260817-042", 42),
    ("{0000000}", "0000042", 42),
)


@pytest.fixture(autouse=True)
def series_sink():
    """The REAL sink the real callers use — not a stub.

    `core.numbering` is deliberately ignorant of tenancy; `AppConfig.ready`
    registers `allocate_series_number` as its sink. Pointing this at anything
    else would make the file prove its own fixture instead of the product.
    """
    cn.set_series_sink(tenancy_services.allocate_series_number)
    yield
    cn.set_series_sink(tenancy_services.allocate_series_number)


@pytest.mark.parametrize("fmt,expected,counter", PROBES, ids=[p[0] for p in PROBES])
def test_every_series_issues_the_format_an_admin_saved(
    fmt, expected, counter, growth_plan, identity_seam
):
    """EVERY catalogued series, each on each format shape. The PO's question.

    ⚠ This said *"All twenty-two series"* until 2026-08-27 and the loop has
    never read a literal — it sweeps `cn.KNOWN_SERIES`, which is **26** today.
    The number is dropped rather than corrected: it has been wrong four times
    (23 at OQ-342, 24 at CR-030 W0, 25 at CR-032, 26 at OQ-426) and the count
    is not what this case is about.

    `save_number_series` is what `PUT /settings/number-series` calls, and
    `cn.next_number` is what `create_account`, `create_asset`, the bill run, the
    payment recorder and the journal poster call. So this is the product's own
    two ends, with nothing in between paraphrased.
    """
    tenant, _ = provisioned_tenant()
    issued = {}
    with tenant_ctx(tenant):
        for series in sorted(cn.KNOWN_SERIES):
            tenancy_services.save_number_series(
                admin_actor(), series, format_string=fmt, next_number=counter
            )
        for series in sorted(cn.KNOWN_SERIES):
            with transaction.atomic():
                issued[series] = cn.next_number(series, ISSUE_DATE)

    # Counted from the CATALOGUE rather than typed: a literal restates the
    # catalogue instead of checking it, and it went red the day OQ-342 added the
    # twenty-third series (`bill_run`) for a reason that was not a defect.
    assert len(issued) == len(cn.KNOWN_SERIES), "the sweep must cover every series, not a subset"
    wrong = {s: got for s, got in issued.items() if got != expected}
    assert wrong == {}, (
        f"these series ignored the saved format {fmt!r} and issued something else: {wrong}"
    )


def test_the_counter_advances_per_series_and_does_not_share_a_pool(
    growth_plan, identity_seam
):
    """One independent counter per catalogued series — 26 of each today.

    ⚠ *"Twenty-two series, twenty-two independent counters"* until 2026-08-27;
    the body has always swept `cn.KNOWN_SERIES` and the literal was prose.

    Kept separate from the sweep above because that one allocates each series
    exactly once — which would pass identically if every series drew from ONE
    shared counter and simply happened to start in the same place. This is the
    assertion that tells those two worlds apart.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for series in sorted(cn.KNOWN_SERIES):
            tenancy_services.save_number_series(
                admin_actor(), series, format_string="{000000}", next_number=500
            )
        firsts, seconds = {}, {}
        for series in sorted(cn.KNOWN_SERIES):
            with transaction.atomic():
                firsts[series] = cn.next_number(series, ISSUE_DATE)
        for series in sorted(cn.KNOWN_SERIES):
            with transaction.atomic():
                seconds[series] = cn.next_number(series, ISSUE_DATE)

    assert set(firsts.values()) == {"000500"}, "every series starts where it was set"
    assert set(seconds.values()) == {"000501"}, (
        "each series has its OWN counter — a shared pool would run 500, 501, 502…"
    )


def test_which_series_have_a_live_consumer(growth_plan, identity_seam):
    """⚠ THE HONEST HALF. A format that reaches no caller reaches no record.

    The two cases above prove the loop WORKS for every series in the catalogue
    (twenty-two at CR-005; twenty-three since OQ-342 added the bill run;
    twenty-four since CR-030 W0 added `customer`; twenty-five since CR-032's
    `connection`; twenty-six since OQ-426 added `transfer` on 2026-08-27;
    twenty-seven since OQ-427 added `disconnect_case` later the same day;
    **twenty-nine since CR-039 wave D task 18 added `move_in` and `move_out`**).
    ⚠ Those loops read `KNOWN_SERIES` rather than a literal, which is why they
    kept working while this list of names did not — the prose is the part that
    goes stale, and it is corrected here rather than left as a count that has
    been wrong twice. They say
    nothing about whether anything CALLS it, and those are different facts — the
    exact gap hard-won law 2 is about. This case pins today's answer so the next
    lane inherits a measurement rather than an impression, and so that wiring a
    series later turns this RED and forces the list to be updated.

    Measured by grepping `next_number(` across `06-backend/apps` on 2026-08-17.
    """
    wired = {
        cn.ACCOUNT,  # apps/customers/services.py:1162 — _allocate_account_no
        cn.ASSET,  # apps/assets/services.py:466
        cn.BILL,  # apps/billing/stages/assemble_document.py:270
        cn.PAYMENT,  # apps/payments/services.py:727 + reversal.py:813
        cn.JOURNAL_ENTRY,  # apps/ledger/manual_je.py:300
        cn.EXPORT_BATCH,  # apps/ledger/exports.py:543
        # OQ-342 (PO 2026-08-23, *"A: a real series (RUN-0001, like RT-001)"*) —
        # wired the day the series was added: `apps/billing/runs.py`
        # `_allocate_run_no`, called from `create_run` inside its own atomic().
        cn.BILL_RUN,
        # CR-030 W0 — wired the day the series was added:
        # `apps/customers/services.py` `_allocate_customer_no`, called INSIDE
        # `models.Customer.objects.create(...)` in `link_customer`, so a
        # customer never exists unnumbered even for the width of a transaction.
        cn.CUSTOMER,
        # ── RE-MEASURED 2026-08-26 (DEF-807). The EIGHT below were wired between
        # 2026-08-17 and 2026-08-26 and none of them was moved into this set, so
        # this test sat RED and the list it exists to keep honest went stale —
        # the precise failure it was written to prevent, happening to it.
        cn.PREMISES,  # apps/metering/services.py:629 — _allocate_unused_number
        cn.UNIT,  # apps/metering/services.py:906 — same helper
        cn.ROUTE,  # apps/metering/services.py:2034 (preview at :1976)
        cn.CYCLE,  # apps/metering/services.py:3524 (preview at :1983)
        cn.IMPORT_RUN,  # apps/metering/import_runs.py:1432
        cn.READ_BATCH,  # apps/metering/services.py:4706 — the staged read batch
        cn.CONNECTION,  # apps/metering/connections.py:1407 — CR-032's CON- series
        cn.SERVICE_REQUEST,  # apps/customers/service_request_service.py:234
        # ── OQ-426 (PO ruling 2026-08-27) — WIRED THE DAY THE SERIES WAS
        # ADDED, and this is the unusual case: the CALLER shipped FIRST.
        # `apps/customers/transfers.py` `_allocate_transfer_no` has been called
        # from inside `start_transfer`'s own `atomic()` since CR-039 wave D
        # task 15, reporting `numbering_series_missing` because the catalogue
        # had no row. The row exists now, so the same call site allocates
        # `TRF-26-0001` with no code change — which is precisely what that
        # lane's refusal was for.
        cn.TRANSFER,  # apps/customers/transfers.py — _allocate_transfer_no
        # ── OQ-427 (PO ruling 2026-08-27, verbatim and in full: *"it needs its
        # own series"*) — THE SAME UNUSUAL CASE, from the same wave D lane and
        # for the same reason. `apps/customers/disconnects.py`
        # `_allocate_case_no` has been called from inside `open_case`'s own
        # `atomic()` AND from the post-closure collections restart since task
        # 16 shipped its column; both reported `numbering_series_missing`
        # because the catalogue had no row. It has one now, so the two existing
        # call sites allocate `DSC-26-0001` onwards with no code change.
        # ⚠ TWO call sites, one series — the restart reopens a case after a
        # closure and a reopened case is a NEW document, so it draws a NEW
        # number rather than reusing the closed one (BR-TEN-035: never reused).
        cn.DISCONNECT_CASE,  # apps/customers/disconnects.py — _allocate_case_no
        # ── CR-039 wave D task 18 — THE THIRD AND FOURTH IN ONE DAY, and the
        # first two that arrived WITH their caller rather than ahead of it.
        # `apps/customers/moves.record_move` allocates by name inside the
        # transaction `services.move_in` / `services.move_out` already open, so
        # these two series were wired by the same commit that catalogued them.
        # ⚠ Their formats are the BUILD's choice, not a PO ruling — see
        # `test_def615_series_defaults.EXPECTED_PREFIX` for the caveat.
        cn.MOVE_IN,  # apps/customers/services.move_in — moves.record_move
        cn.MOVE_OUT,  # apps/customers/services.move_out — moves.record_move
    }
    unwired = set(cn.KNOWN_SERIES) - wired

    # Every name in `wired` must really exist — a typo here would quietly shrink
    # the claim rather than fail it.
    assert wired <= set(cn.KNOWN_SERIES)

    # The count is asserted, not the membership, so ADDING a consumer is what
    # breaks this test — and the failure message says what to do about it.
    assert len(wired) == 20, (
        "the set of series with a live caller changed. If a series was just "
        "wired, move it into `wired` and say so in the CR record; if one lost "
        "its caller, that is a defect."
    )
    # ⚠ 20 wired and STILL 9 unwired — FOUR TIMES IN ONE DAY, and every one of
    # them for the same reason. `transfer`, then `disconnect_case`, then
    # `move_in` and `move_out` each arrived carrying their own caller: the wave
    # D lane shipped the allocation and refused the format, so the catalogue
    # grew 25 → 26 → 27 → 29 and the wired set grew with it every time. **The
    # honest half of this test has not moved at all today**, which is what that
    # refusal was for. RED first, verbatim, each time the rows landed before
    # the names above them: `AssertionError: assert 10 == 9` (twice) and
    # `AssertionError: assert 11 == 9`.
    # ⚠ **11, AND TWO OF THE THREE MOVES SINCE 29 WERE NOT THIS LANE'S.**
    # `interruption_report` joined the catalogue with CR-068 wave B and this
    # count was never moved, so this assertion was RED before the `P0.13` lane
    # touched anything — `30 known − 20 wired = 10`, asserted as 9. The
    # `settlement` series (`P0.13`, PO 2026-09-22 *"(a) STL-26-0001"*) makes it
    # 11, and it is DELIBERATELY unwired: there is no settlement table and no
    # endpoint in phase 0, so nothing may call `next_number("settlement")` yet.
    # Re-measured rather than incremented, which is the discipline the paragraph
    # above records failing three times already.
    assert len(unwired) == 11
    # Named rather than counted, because "11 unwired" is a number and
    # "a work order gets no number" is a fact somebody can act on.
    #
    # ⚠ `premises`, `unit` and `read_batch` USED TO BE NAMED HERE and all three
    # are wired now — which is why this loop is re-measured rather than trimmed.
    # The four that remain are the ones a reader should be able to act on: three
    # BILLING documents that a utility issues to a customer, and the work order.
    for series in ("work_order", "adjustment", "credit_memo", "write_off"):
        assert series in unwired, f"{series} is expected to have no caller yet"


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-08-17, CR-005 closing-loop lane, at the PO's direct question
# gates: 4 parametrized + 2 = 6 cases, all green against the real series sink
# exceptions: this file allocates real numbers on a provisioned test tenant and
#             asserts nothing about ISSUED records — creating an account or an
#             asset end to end needs the customers/assets fixtures and belongs in
#             those modules' suites; the loop under test is the numbering one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
