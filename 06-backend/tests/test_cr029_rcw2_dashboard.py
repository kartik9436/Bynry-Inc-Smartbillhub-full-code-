# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 task W2-T3.
#           Screens: S7 (the landing screen's cycle line and period filter)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7
# Rules:    D8① — *"what makes a cycle 'completed - dont build it"* ·
#           D8② — *"which date 'closes in 4 days' counts to - Next cycle
#           date"* · BR-REP-027 (the cycle line is SET-07's facts) ·
#           BR-REP-035 (the period vocabulary) · BR-REP-028 (a region fails
#           alone) · BR-TEN-043 (no clock) · OQ-221 (the derivation D8②
#           replaces) · OQ-268 (the "completed" judgment D8① withdraws)
# ───────────────────────────────────────────────────────
"""RC-W2-T3 — the countdown counts to the next cycle date, and one claim goes.

TWO RULINGS, AND ONE OF THEM IS A DELETION
------------------------------------------
**D8② — the countdown.** The line *"Cycle 08-A closes in 4 days"* used to count
to `cycles.read_day_to`, a field chosen by DERIVING it from the requirement's
own four states (OQ-221 carries that derivation and says in as many words that
it is not a stated rule). The PO has now stated it: **the next cycle date**. So
the target is the cycle's next occurrence — what the period engine derives —
and neither the read-window end nor the bill day.

**D8① — the claim that is REMOVED.** Asked *"what makes a cycle completed"*,
the PO ruled *"dont build it"*. The dashboard was claiming exactly that: the
period filter offered a **"Last completed cycle"** window built on a lane
judgment (a cycle is complete when its bill date has passed — OQ-268, raised
2026-08-19 and never ruled). **Removing the claim is the deliverable.** The
filter keeps its rolling and accounting windows; nothing invents a second
definition of "completed" to put in its place.

⚠ **THIS SUPERSEDES PART OF CR-015**, whose ruling offered *"last cycle or last
30 days"* and whose lane chose the first as the default. The default is now the
rolling thirty days, and the reason is stated on the payload rather than left as
a missing option. The CR-015 cases that pinned the completed-cycle window are
rewritten in their own file, not deleted quietly.
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.reports import dashboard
from apps.reports import dashboard_period as period_vocab
from apps.reports import dashboard_regions as regions

from tests.ledger_le_fixtures import JULY_END, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def fiscal_calendar(tenant):
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.update_or_create(
        tenant_id=tenant.id,
        defaults={
            "fy_start_month": 10,
            "fy_start_day": 1,
            "close_cadence": "monthly",
            "close_day": "3rd business day",
            "number_format": "1,234.56",
        },
    )


def a_july(tenant, dana):
    fiscal_calendar(tenant)
    accounts = make_accounts(dana, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def summary(tenant, **kwargs):
    kwargs.setdefault("as_of", JULY_END)
    with tenant_ctx(tenant):
        return dashboard.dashboard_summary(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# D8② · THE COUNTDOWN COUNTS TO THE NEXT CYCLE DATE
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t3__the_countdown_target_is_the_next_cycle_date():
    """A cycle whose next date is 1 Sep, read on 28 Aug, closes in **4 days**.

    The figure is the PO's own sentence made true: *"Cycle 08-A closes in 4
    days"*. Under the superseded reading the same cycle counted to its
    `read_day_to` and said something different.
    """
    data = regions.cycle_status_data(
        [
            {
                "code": "08-A",
                "name": "Residential monthly",
                "accounts": 842,
                "lifecycle_status": "active",
                "next_cycle_date": "2026-09-01",
                # The superseded fields are still on the payload and must NOT
                # be what the countdown reads.
                "read_day_to": 25,
                "bill_day": 5,
            }
        ],
        as_of=date(2026, 8, 28),
    )
    assert data["state"] == regions.CYCLE_STATE_CLOSES_IN
    assert data["days"] == 4
    assert data["close_date"] == "2026-09-01"


def test_w2_t3__on_the_day_itself_the_cycle_closes_today():
    data = regions.cycle_status_data(
        [
            {
                "code": "08-A",
                "accounts": 10,
                "lifecycle_status": "active",
                "next_cycle_date": "2026-09-01",
            }
        ],
        as_of=date(2026, 9, 1),
    )
    assert data["state"] == regions.CYCLE_STATE_TODAY
    assert data["days"] == 0


def test_w2_t3__the_next_closing_cycle_is_still_the_one_named():
    """CR-012's DSH-01 requirement is untouched: *"the next-closing active cycle
    from SET-07 (tie broken by account count)"*. Only the DATE moved."""
    data = regions.cycle_status_data(
        [
            {
                "code": "08-B",
                "accounts": 405,
                "lifecycle_status": "active",
                "next_cycle_date": "2026-09-12",
            },
            {
                "code": "08-A",
                "accounts": 842,
                "lifecycle_status": "active",
                "next_cycle_date": "2026-09-01",
            },
        ],
        as_of=date(2026, 8, 28),
    )
    assert data["cycle_code"] == "08-A"
    assert data["accounts"] == 842


def test_w2_t3__a_cycle_that_cannot_say_when_it_next_comes_round_is_skipped():
    """A cycle whose next date is unruled (OQ-339) publishes none, and is passed
    over for one that can answer — rather than being counted down to a date the
    product chose for it."""
    data = regions.cycle_status_data(
        [
            {"code": "31st", "accounts": 900, "lifecycle_status": "active"},
            {
                "code": "08-A",
                "accounts": 10,
                "lifecycle_status": "active",
                "next_cycle_date": "2026-09-01",
            },
        ],
        as_of=date(2026, 8, 28),
    )
    assert data["cycle_code"] == "08-A"


def test_w2_t3__a_tenant_with_no_scheduled_cycle_says_so_without_guessing():
    data = regions.cycle_status_data([], as_of=date(2026, 8, 28))
    assert data["state"] == regions.CYCLE_STATE_NONE
    assert data["days"] is None


def test_w2_t3__the_superseded_close_field_constant_is_gone():
    """OQ-221's derivation was *"the one constant that moves if the PO meant
    another date"*. The PO named a date that is not a day-of-month at all, so
    the constant does not move — it goes."""
    assert not hasattr(regions, "CYCLE_CLOSE_FIELD")


def test_w2_t3__the_line_reads_the_cycle_date_end_to_end(brazos, dana):
    """Wired, not merely built (hard-won law 2): the date comes off the cycle
    payload the metering seam already publishes, so the landing screen counts
    down to a real configured cycle."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        metering_models.Cycle.objects.create(
            tenant_id=brazos.id,
            code="CY-001",
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            first_run_date=date(2026, 8, 1),
            status="active",
        )
    payload = summary(brazos, as_of=date(2026, 8, 28))
    data = payload["regions"]["cycle_status"]["data"]
    assert data["cycle_code"] == "CY-001"
    assert data["close_date"] == "2026-09-01"
    assert data["days"] == 4


# ═══════════════════════════════════════════════════════════════════════════
# D8① · "CYCLE COMPLETED" IS NOT BUILT — THE CLAIM IS REMOVED
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t3__no_completed_cycle_definition_exists_anywhere_in_the_vocabulary():
    """*"dont build it"*. The function that defined completeness is gone, not
    renamed, not left unreferenced — a definition nobody calls is still a
    definition the next lane will call."""
    assert not hasattr(period_vocab, "last_completed_cycle")
    assert period_vocab.OPTION_LAST_CYCLE not in period_vocab.OPTION_ORDER


def test_w2_t3__the_filter_never_offers_a_completed_cycle_window(brazos, dana):
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        metering_models.Cycle.objects.create(
            tenant_id=brazos.id,
            code="07-A",
            # W5-T2: `window_start`/`window_end` are dropped columns; the cycle
            # states its schedule the ruled way. ⚠ `bill_date` — the sixth and
            # last legacy column, which said "billed" and is what made this row
            # "completed" under the rule D8① told us not to build — went too
            # (RC-W6, metering 0023 / OQ-344). The DAY is what survives.
            start_day=1,
            days_to_complete=8,
            frequency="Monthly",
            bill_day=8,
            status="active",
        )
    payload = summary(brazos, as_of=date(2026, 7, 31))
    ids = [option["id"] for option in payload["period_filter"]["options"]]
    assert "last_cycle" not in ids
    assert payload["period_filter"]["default"] == "last_30_days"
    assert payload["period_filter"]["selected"] == "last_30_days"


def test_w2_t3__the_removal_is_stated_on_the_payload_rather_than_silent(brazos, dana):
    """An absence is STATED (hard-won law 1), and it is stated for EVERY tenant.

    The old gap said *"this tenant has no completed cycle yet"* — a fact about
    data. This one is a fact about the product, so a utility with six healthy
    cycles sees it too and the sentence is true for that reader as well.

    ⚠ The screen does not print `detail`: `financeShared.gapSentence` renders
    `finance.gap.<code>` from the catalogue and falls back to a generic
    sentence, so `detail` is prose for the next AGENT and carries its
    provenance (the shape every gap in `dashboard.py` already uses). The
    CATALOGUE entry for this code is owed by the frontend lane and is reported.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        metering_models.Cycle.objects.create(
            tenant_id=brazos.id,
            code="07-A",
            start_day=1,
            days_to_complete=8,
            frequency="Monthly",
            bill_day=8,
            status="active",
        )
    payload = summary(brazos, as_of=date(2026, 7, 31))
    entries = [row for row in payload["unavailable"] if "cycle" in row["code"]]
    assert [row["code"] for row in entries] == ["billing_cycle_window_is_not_offered"]
    assert entries[0]["br_ref"]


def test_w2_t3__a_stale_bookmark_for_the_cycle_window_still_opens_the_page(brazos, dana):
    """BR-SHL-011 — `?f.period=last_cycle` was a shareable link yesterday. It
    falls back to the default rather than refusing."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 7, 31), period="last_cycle")
    assert payload["period_filter"]["selected"] == "last_30_days"
    assert payload["period"]["start"] is not None
