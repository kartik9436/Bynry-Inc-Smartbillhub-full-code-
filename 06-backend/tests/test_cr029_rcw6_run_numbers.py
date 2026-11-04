# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W6: **OQ-342**,
#           *"DOES A BILL RUN GET A NUMBER — AND IF SO, IN WHAT GRAMMAR?"*
#           Screens: SET-07D (Runs tab) · S31
# Ruling:   OQ-342, CLOSED 2026-08-23, PO verbatim: *"A: a real series
#           (RUN-0001, like RT-001)"*.
# Rules:    BR-TEN-035 (the numbering grammar and its allocation law — in
#           transaction, forward-only, gaps ok, NEVER reused, issued numbers
#           never renumbered) · BR-TEN-043 (the issue date is an argument,
#           never the wall clock) · BR-BIL-005 (a run is unique on tenant ·
#           cycle · period — the number is NOT part of that key) · CLAUDE.md
#           rule 4 (financial immutability) · rule 7 (every money action is
#           audited) · hard-won law 2 (built is not wired)
# ───────────────────────────────────────────────────────
"""RC-W6 — a bill run gets a real number, and previewing one does not burn it.

**WHAT WAS TRUE UNTIL 2026-08-23.** The PO's own SET-07D screenshot draws a Run
column reading `RUN-0814` and the product could not produce it: `bill_runs` had
no number column and `core.numbering.SERIES_CATALOG` carried no bill-run series.
RC-W4b served `run_no: null` and a test HELD it null, so no later lane could
quietly derive one from `created_at`, from a per-cycle ordinal or from the
uuid's first eight characters — each of those would have minted a naming grammar
by call site, and a number a customer or an auditor may quote is exactly the
thing a screen must not invent.

**THE PO RULED READING (A): a real series.** So a run is numbered from the same
machinery that issues `RT-001` and `CY-001`, and this file defends the four
properties that make such a number trustworthy:

1. **IT IS ALLOCATED AT CREATION**, inside the run's own transaction, so the row
   and its number are one atomic fact — the shape `create_route` was forced into
   by DEF-234 and for the same reason.
2. **IT IS FORWARD-ONLY AND NEVER REUSED** (BR-TEN-035). Two runs get two
   numbers; a rolled-back run leaves a gap and the gap is not refilled.
3. **PREVIEWING DOES NOT BURN ONE.** This repo learned that by defect: the route
   and cycle wizards preview through `core.numbering.preview`, which renders and
   allocates NOTHING, so opening a wizard and cancelling does not leave a hole a
   utility has to explain. Every READ of a run — the list, the detail — must
   likewise leave the counter exactly where it found it.
4. **EXISTING RUNS ARE NOT RETRO-NUMBERED.** The ruling says so in as many
   words, and CLAUDE.md rule 4 says why: a number that appeared on a bill
   already sent is a different question, and nobody has asked it.
"""

from datetime import date

import pytest
from django.db import transaction

from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.billing import selectors as billing_selectors
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from core import numbering as core_numbering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)


def _cycle(tenant, code="CY-RUNNO"):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        bill_day=5,
        due_days=21,
        first_run_date=date(2026, 8, 1),
    )


def _series(tenant):
    return tenancy_models.NumberSeries.objects.get(tenant=tenant, series=core_numbering.BILL_RUN)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE SERIES EXISTS, IN THE GRAMMAR THE PO NAMED
# ═══════════════════════════════════════════════════════════════════════════
def test_oq342__a_bill_run_series_exists_and_its_default_renders_RUN_0001():
    """PO verbatim: *"A: a real series (RUN-0001, like RT-001)"*. The literal
    string in the ruling is the assertion: a counter of 1 renders `RUN-0001`."""
    assert core_numbering.BILL_RUN in core_numbering.KNOWN_SERIES
    group, options = core_numbering.SERIES_CATALOG[core_numbering.BILL_RUN]
    assert group == core_numbering.GROUP_BILLING
    assert options[0] == "RUN-{0000}"
    assert core_numbering.preview("RUN-{0000}", 1, date(2026, 8, 23)) == "RUN-0001"
    # …and RT-001 is the shape the PO compared it to, unchanged.
    assert core_numbering.SERIES_CATALOG[core_numbering.ROUTE][1][0] == "RT-{000}"


def test_oq342__provisioning_seeds_the_new_series_for_a_tenant(brazos):
    """Built is not wired (hard-won law 2). A series in the catalogue that
    provisioning does not seed is the gap BR-LED-021 (i) found on `JE-`: every
    manual journal entry shipped unnumbered because `SERIES_DEFAULTS` held five
    keys where the kernel knew nine. `SERIES_DEFAULTS` is derived from the
    catalogue now, so this passes by construction — and is asserted anyway,
    because a guarantee that is not asserted is a comment."""
    assert _series(brazos).format == "RUN-{0000}"
    assert _series(brazos).next_number == 1


def test_oq342__no_two_series_are_seeded_with_the_same_prefix(brazos):
    """⚠ **THE COLLISION THE RULING CREATED, AND HOW IT WAS RESOLVED.**
    `import_run` already defaulted to `RUN-{0000}` — it numbers a READ IMPORT
    batch, which is a different thing — so honouring the PO's `RUN-0001` for
    bill runs would have greeted every new tenant with a duplicate-prefix
    warning on a screen nobody had touched.

    The ruling wins over the older default: the BILL RUN takes `RUN-`, and
    `import_run` opens on `IMP-{YY}{MM}{DD}-{00}`, which was already the second
    ready-made option on its own list. `RUN-{0000}` stays OFFERED there, so a
    tenant who wants it can still choose it — CR-005 makes duplicates a warning
    and never a block.

    ⚠ **NOTHING ALREADY ISSUED MOVES** (BR-TEN-035: issued numbers are never
    renumbered). A tenant provisioned before today keeps the `import_run` format
    in ITS OWN ROW — `_seed_number_series` is `get_or_create` — so existing
    import-run numbers and the counter behind them are untouched.
    """
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        rows = tenancy_selectors.number_series_overview()
    assert [row["series"] for row in rows if row["duplicate_prefix"]] == []
    assert core_numbering.SERIES_CATALOG[core_numbering.IMPORT_RUN][1][0] == "IMP-{YY}{MM}{DD}-{00}"
    assert "RUN-{0000}" in core_numbering.SERIES_CATALOG[core_numbering.IMPORT_RUN][1]


# ═══════════════════════════════════════════════════════════════════════════
# 2 · ALLOCATED AT CREATION, FORWARD-ONLY
# ═══════════════════════════════════════════════════════════════════════════
def test_oq342__creating_a_run_allocates_its_number(brazos, dana):
    """The run and its number are one atomic fact. `RUN-0001` is the PO's own
    string and the first run of a fresh tenant is exactly that."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
    assert run.run_no == "RUN-0001"


def test_oq342__the_series_is_forward_only_and_two_runs_never_share_a_number(brazos, dana):
    """BR-TEN-035: forward-only, gaps acceptable, **never reused**. Two runs of
    two periods take 0001 and 0002 and the counter stands at 3."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        first = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
        second = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            run_by=dana,
            actor=dana,
        )
        standing = _series(brazos).next_number
    assert [first.run_no, second.run_no] == ["RUN-0001", "RUN-0002"]
    assert standing == 3


def test_oq342__a_duplicate_run_is_refused_and_the_number_is_not_consumed(brazos, dana):
    """BR-BIL-005 keys a run on (tenant · cycle · period) and **the number is
    not part of that key** — adding it would let one cycle-period be billed
    twice by taking a new number.

    ⚠ **THE ALLOCATION SITS INSIDE THE SAME `atomic()` AS THE INSERT**, so a
    refused duplicate rolls its number back with the row it would have numbered.
    A successful allocation followed by a refused create is exactly how
    `create_route` used to burn one (DEF-234's neighbourhood), and a utility
    reconciling a sequence has to explain every hole in it.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
        before = _series(brazos).next_number
        with pytest.raises(billing_runs.DuplicateRun):
            with transaction.atomic():
                billing_runs.create_run(
                    cycle_id=cycle.id,
                    period_start=PERIOD_START,
                    period_end=PERIOD_END,
                    run_by=dana,
                    actor=dana,
                )
        after = _series(brazos).next_number
    assert (before, after) == (2, 2), "a refused run must not consume a number"


def test_oq342__the_number_is_in_the_audit_trail(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — every money action writes `audit_log`, and the number
    a customer may quote belongs in the trail beside the dates that decide what
    they are charged.

    Asserted through the BE-03 capture sink rather than by querying `audit_log`
    (the posture `test_oq122_run_bill_date` records): the trail table is
    partitioned and this is a claim about the PAYLOAD, not about the store.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        audit_rows.clear()
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
    created = [row for row in audit_rows if row["action"] == "bill_run.created"]
    assert [row["after"]["run_no"] for row in created] == ["RUN-0001"]
    assert run.run_no == "RUN-0001"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · A PREVIEW NEVER BURNS ONE — the defect this repo already paid for
# ═══════════════════════════════════════════════════════════════════════════
def test_oq342__reading_the_runs_list_leaves_the_counter_exactly_where_it_was(brazos, dana):
    """*"previewing a number must not burn one"*, taken to its read surfaces.

    `next_route_code` renders through `core.numbering.preview`, which allocates
    NOTHING — *"opening the wizard and cancelling does not burn a number"*. A
    LIST is the same promise made a hundred times a day: a clerk refreshing
    SET-07D's Runs tab must not walk the series forward.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
        before = _series(brazos).next_number
        for _ in range(3):
            billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
        after = _series(brazos).next_number
    assert before == after == 2


def test_oq342__the_runs_list_serves_the_allocated_number(brazos, dana):
    """⚠ **THIS TEST HELD `run_no` NULL UNTIL 2026-08-23 AND NOW ASSERTS THE
    NUMBER.** RC-W4b's own words: *"inventing `RUN-0814` would mint a naming
    grammar by call site"* — so it was served null and a test pinned it there
    until the PO ruled. The PO ruled reading (A), so the pin is INVERTED rather
    than deleted: what stopped a lane guessing now stops a lane dropping it.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=dana,
            actor=dana,
        )
        rows = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))
    assert rows[0]["run_no"] == "RUN-0001"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · WHAT IS NOT DONE, ASSERTED SO IT STAYS NOT DONE
# ═══════════════════════════════════════════════════════════════════════════
def test_oq342__runs_that_predate_the_column_are_not_retro_numbered(brazos, dana):
    """The ruling, verbatim: *"Existing runs have no number and are not
    retro-numbered unless the PO asks — a number that appears on a bill already
    sent is a different question."*

    A run written straight to the table (which is what every run on a live host
    is, relative to this migration) keeps `run_no = NULL`, the list serves the
    null honestly, and the series does not move because of it.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        legacy = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            status="draft",
            idempotency_key="legacy-unnumbered",
        )
        rows = {str(row["id"]): row for row in billing_selectors.bill_runs_list()}
        standing = _series(brazos).next_number
    assert legacy.run_no is None
    assert rows[str(legacy.pk)]["run_no"] is None
    assert standing == 1, "an unnumbered legacy row does not walk the series"


def test_oq342__a_number_is_unique_per_tenant_and_null_is_not(brazos, dana):
    """The uniqueness is PARTIAL — `WHERE run_no IS NOT NULL` — which is the
    only shape that can hold both halves of the ruling at once: numbers are
    unique, and every historical run keeps a null. `import_runs` (metering 0014)
    took the identical shape for the identical reason."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        first = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            status="draft",
            idempotency_key="null-1",
        )
        second = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            status="draft",
            idempotency_key="null-2",
        )
    assert first.run_no is None and second.run_no is None  # two nulls coexist
    constraint = next(
        c
        for c in billing_models.BillRun._meta.constraints
        if getattr(c, "name", "") == "uq_bill_runs_tenant_run_no"
    )
    assert constraint.condition is not None
