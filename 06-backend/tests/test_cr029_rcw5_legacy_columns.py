# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W5 task W5-T2:
#           the deprecated cycle columns are DROPPED, and the transitional
#           day-of-month fallback in the dashboard countdown goes with them.
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §6/§7
# Rules:    D2 (*"Yes"* — one schedule generation) · D8② (*"Next cycle date"*) ·
#           D9 (bill day + due days STAY as cycle defaults) · BR-MET-016 (a
#           second unchanged read inside the cycle window is a duplicate) ·
#           BR-MET-077 · CLAUDE.md rule 4 (nothing already issued moves) ·
#           CLAUDE.md 🔒 (migration ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
"""W5-T2 — five of the six deprecated columns go, and the sixth is NAMED.

**WHAT W1 LEFT AND WHAT THIS PICKS UP.** metering 0019 marked six columns
DEPRECATED with a Postgres column comment, listed them in
`LEGACY_DEPRECATED_COLUMNS`, and left a test asserting **no `RemoveField`
exists** — W1 protecting W5's work from a lane that felt like tidying up. That
test is UPDATED here rather than deleted: the tuple is still the record of what
was deprecated, and what changes is which of them the migrations have now taken.

**FIVE GO:**

    window_start · window_end   the read window is DERIVED (B17 §2)
    read_day_from · read_day_to superseded by start_day + days_to_complete
    due_day                     the due fact billing reads is `due_days`

**AND ONE STAYED, WITH ITS REASON WRITTEN DOWN RATHER THAN ITS DROP FORCED —
UNTIL THE RULING ARRIVED.** `cycles.bill_date` was read by
`apps/billing/issue.py::_due_terms_for` as the fallback bill date for a run where
the clerk typed none, and **there was no ruled answer for what replaced it.** D9
kept `bill_day` — a DAY-OF-MONTH — as the surviving default, and turning a
day-of-month into the bill DATE of a particular run means choosing a month, which
nothing stated. The three candidate readings were not equivalent (up to a month
apart, and the due date they produce starts the late-fee clock, BR-BIL-001), so
W5 refused to pick one at a call site and reported OQ-344.

⚠ **THE PO RULED IT ON 2026-08-23 AND THE SIXTH COLUMN WENT TOO (RC-W6, metering
0023).** Verbatim: *"I'd say B - these are defualt - user can override"* — **the
bill day, in the month AFTER the period ends**. Worked: bill day 5, due days 21,
period 1–31 Aug → bills 5 Sep, due 26 Sep. So this file now asserts SIX dropped
columns and none kept; the cases below are amended rather than deleted, because
the claim they defend — *a column goes only after its readers move, and the
payload keeps the keys whose fact survives* — is exactly what OQ-344 made true
for the sixth as well.

**THE TRANSITIONAL DASHBOARD FALLBACK GOES WITH THE COLUMNS.** RC-W2 left
`_candidate` falling back to `read_day_to` for a cycle with no `first_run_date`,
and said so out loud: *"while the deprecated day-of-month columns still exist
(RC-W5 drops them) a cycle that cannot say when it next comes round falls back to
them … When they go, a cycle with no first run publishes nothing and is
skipped."* That is what happens now, and the countdown still renders — asserted
below on a cycle that CAN say, because that is the case the line exists for.
"""

from datetime import date

import pytest

from apps.metering import models, schedule, selectors as metering_selectors
from apps.reports import dashboard_regions

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The five taken by W5-T2. Named as data so the assertions below cannot
#: disagree with the prose above.
DROPPED = ("window_start", "window_end", "read_day_from", "read_day_to", "due_day")

#: The sixth, taken by RC-W6 in metering 0023 once OQ-344 ruled what replaced it.
#: Kept as its own name rather than folded into `DROPPED`, because the two
#: migrations are separate facts and each is asserted against its own file.
DROPPED_ONCE_RULED = "bill_date"

#: ⚠ **THE PAYLOAD AND THE TABLE DO NOT LOSE THE SAME NAMES, AND THAT IS THE
#: POINT OF D2.** `window_start` / `window_end` are dropped COLUMNS and surviving
#: KEYS: `cycle_dict` derives the pair from `start_day` + `days_to_complete` for
#: every cycle, and the bill-run picker, S27 and the cycles export keep reading
#: exactly those two names — which is why nothing downstream had to change. What
#: leaves the payload is the three whose FACT has no replacement to serve.
DROPPED_FROM_THE_PAYLOAD = ("read_day_from", "read_day_to", "due_day")


# ═══════════════════════════════════════════════════════════════════════════
# THE COLUMNS ARE GONE FROM THE DATABASE, NOT ONLY FROM THE MODEL
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t2__the_five_columns_are_gone_from_the_cycles_table(brazos):
    """Read out of `information_schema`, not off the model. A model field
    removed while the column survives is a migration that did not run, and it
    looks identical from Python."""
    from django.db import connection

    with connection.cursor() as cursor:
        # Django's own introspection rather than `information_schema`, so this
        # assertion is about the TABLE on whichever backend the suite runs on.
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, "cycles")
        }
    still_there = sorted(name for name in DROPPED if name in columns)
    assert still_there == [], f"deprecated columns still on the table: {still_there}"
    # ⚠ This asserted `bill_date in columns` — *"kept deliberately"* — until
    # OQ-344 ruled its replacement on 2026-08-23. Inverted rather than deleted:
    # the sixth column is gone and nothing may put it back without a ruling.
    assert (
        DROPPED_ONCE_RULED not in columns
    ), "bill_date went with metering 0023 once OQ-344 ruled the fallback"
    # The surviving generation, asserted positively so a later "cleanup" that
    # took the wrong five fails here.
    for kept in ("start_day", "days_to_complete", "frequency", "bill_day", "due_days"):
        assert kept in columns, f"{kept} is the RULED generation and must stay"


def test_w5_t2__the_model_no_longer_declares_them(brazos):
    fields = {field.name for field in models.Cycle._meta.get_fields()}
    assert not (set(DROPPED) & fields), f"model still declares {sorted(set(DROPPED) & fields)}"


def test_w5_t2__the_served_payload_no_longer_carries_the_dropped_keys(brazos, dana):
    """A key served as a permanent null is dead payload (hard-won law 2), and a
    screen reading it renders an em-dash forever."""
    with tenant_ctx(brazos):
        row = models.Cycle.objects.create(
            tenant_id=brazos.id,
            code="CY-W5T2",
            name="W5-T2",
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            first_run_date=date(2026, 9, 1),
            bill_day=5,
            due_days=20,
            status="active",
        )
        served = metering_selectors.cycle_dict(row)
    for name in DROPPED_FROM_THE_PAYLOAD:
        assert name not in served, f"cycle_dict still serves the dropped key {name!r}"
    # And the ruled generation IS served, with the window DERIVED under the two
    # contracted names their consumers have always read.
    assert served["start_day"] == 1
    assert served["days_to_complete"] == 3
    assert served["read_window_source"] == "derived"
    assert served["window_start"] is not None and served["window_end"] is not None
    assert served["bill_day"] == 5 and served["due_days"] == 20


# ═══════════════════════════════════════════════════════════════════════════
# W2's TRANSITIONAL FALLBACK GOES — AND THE COUNTDOWN STILL RENDERS
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t2__the_countdown_still_renders_for_a_cycle_that_can_say_when_it_closes():
    """D8② — *"② which date 'closes in 4 days' counts to - Next cycle date"*.

    Worked, and it is the sentence the requirement draws: a cycle whose next
    date is **1 Sep**, read on **28 Aug**, is *"closes in 4 days"*.
    """
    cycles = [
        {
            "code": "CY-001",
            "name": "Residential monthly",
            "lifecycle_status": "active",
            "accounts": 48,
            "next_cycle_date": "2026-09-01",
        }
    ]
    data = dashboard_regions.cycle_status_data(cycles, as_of=date(2026, 8, 28))
    assert data["state"] == dashboard_regions.CYCLE_STATE_CLOSES_IN
    assert data["days"] == 4
    assert data["cycle_code"] == "CY-001"


def test_w5_t2__a_cycle_that_cannot_say_is_skipped_rather_than_guessed_at():
    """The fallback's replacement, stated as a test. RC-W2 kept the day-of-month
    branch so a tenant with six cycles would not read *"no cycle configured"*;
    with the columns gone, such a cycle publishes nothing and is SKIPPED — which
    is D8①'s posture (*"dont build it"*) applied to a date rather than a state.
    """
    cycles = [
        {"code": "CY-OLD", "lifecycle_status": "active", "accounts": 9, "next_cycle_date": None}
    ]
    data = dashboard_regions.cycle_status_data(cycles, as_of=date(2026, 8, 28))
    assert data["state"] == dashboard_regions.CYCLE_STATE_NONE
    assert data["cycle_code"] is None


def test_w5_t2__the_dashboard_asks_no_cycle_for_a_day_of_month(brazos):
    """The fallback is gone from the CODE, not merely unreachable.

    ⚠ Deliberately NOT a grep over the module: the historical note explaining
    why `CYCLE_CLOSE_FIELD` held `"read_day_to"` and why the PO's D8② replaced
    it must STAY (hard-won law 9 — the repo is where the reasoning lives), so a
    grep for the string would fail on the explanation rather than on the code.
    This drives the function instead: a cycle carrying the day-of-month keys and
    NOTHING else must be skipped, where before it was counted down to.
    """
    legacy_shaped = [
        {
            "code": "CY-LEGACY",
            "lifecycle_status": "active",
            "accounts": 12,
            "next_cycle_date": None,
            # What the old fallback read. Present here on purpose: if either is
            # still consulted this cycle is NAMED instead of skipped.
            "read_day_to": 3,
            "bill_day": 5,
        }
    ]
    data = dashboard_regions.cycle_status_data(legacy_shaped, as_of=date(2026, 8, 28))
    assert data["state"] == dashboard_regions.CYCLE_STATE_NONE
    assert data["cycle_code"] is None


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-016 — THE DUPLICATE CLAUSE KEEPS ITS WINDOW, DERIVED
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t2__the_cycle_window_a_read_is_checked_against_is_derived(brazos):
    """⚠ **AND IT NOW FIRES FOR EVERY CYCLE, WHERE IT USED TO FIRE FOR ALMOST
    NONE.** BR-MET-016's second clause — a second read for one meter+channel
    inside the cycle window with an UNCHANGED value is a duplicate — scoped
    itself with `cycle.window_start`/`window_end`. Those are null on every cycle
    the wizard has created since CR-029 landed, so the clause was silently dead
    for all of them and alive only for CR-006-era rows. Derived from
    `start_day` + `days_to_complete` in the READ's own month, it applies to
    every cycle, which is what the rule always said.

    This is `derive_read_window`'s documented purpose — *"placed in `anchor`'s
    month … a RENDERING choice for a month already picked"* — and NOT the
    generate-occurrences path OQ-339 blocks: the month is not being chosen here,
    it arrives with the read.
    """
    with tenant_ctx(brazos):
        cycle = models.Cycle.objects.create(
            tenant_id=brazos.id,
            code="CY-W5T2B",
            frequency="Monthly",
            start_day=1,
            days_to_complete=5,
            status="active",
        )
        window = schedule.derive_read_window(
            cycle.start_day, cycle.days_to_complete, date(2026, 8, 20)
        )
    assert window == (date(2026, 8, 1), date(2026, 8, 5))


# ═══════════════════════════════════════════════════════════════════════════
# 🔒 THE MIGRATION ITSELF
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t2__the_drop_migration_takes_five_and_names_the_sixth():
    from importlib import import_module

    migration = import_module("apps.metering.migrations.0021_cr029_drop_legacy_cycle_columns")
    removed = {
        operation.name
        for operation in migration.Migration.operations
        if type(operation).__name__ == "RemoveField"
    }
    assert removed == set(DROPPED)
    assert DROPPED_ONCE_RULED not in removed
    doc = migration.__doc__ or ""
    assert DROPPED_ONCE_RULED in doc, "the migration must name the column it did NOT take"
    assert "open question" in doc, "and say that its replacement is unruled, not merely deferred"


def test_w6__the_sixth_column_went_in_its_own_migration_once_the_ruling_arrived(brazos):
    """0021 named the column it did not take; 0023 is the one that took it.

    Asserted against the migration files themselves so the two facts cannot
    drift: the RC-W5 migration must still explain the deferral (a reader meeting
    it should learn why it waited), and the RC-W6 migration must quote the
    ruling that ended it.
    """
    from importlib import import_module

    migration = import_module("apps.metering.migrations.0023_cr029_drop_cycle_bill_date")
    removed = {
        operation.name
        for operation in migration.Migration.operations
        if type(operation).__name__ == "RemoveField"
    }
    assert removed == {DROPPED_ONCE_RULED}
    doc = migration.__doc__ or ""
    assert "OQ-344" in doc
    assert "these are defualt - user can override" in doc, "the PO's own words, verbatim"


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 §6/§7 RC-W5 T2 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W5 lane
# checklist: A✔ B✔(the wizard's Schedule step moved with the columns) C✔ D✔ E✔ F✔ G✔ H=PENDING(🔒 migration 0021 — HUMAN-REVIEW-PENDING, ledger row OWED and REPORTED)
# gates: makemigrations --check clean · metering + reports + billing suites green
# exceptions: (1) ~~`cycles.bill_date` is NOT dropped~~ **CLOSED 2026-08-23 — OQ-344 RULED** (*"I'd say B - these are defualt - user can override"*): the fallback is the bill DAY in the month after the period ends, and RC-W6's metering 0023 took the sixth column. This file's assertion is INVERTED, not deleted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
