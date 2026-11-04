# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (the CR-023 import runner) · US-MET-007 (reads import)
# Defect:   DEF-MET-5756 — imports and exports cannot carry 60–80,000 rows: the
#           10 MB byte cap refuses five of the seven targets before the 100,000
#           row cap is reached, the reads import caps at 50,000 rows, the list
#           export caps at 50,000, and the default async bar is a
#           transform-shaped figure being spent on loads.
# Change:   PO 2026-09-18 — the product was designed for 3,000 accounts and the
#           assumption is now 40,000–80,000; 60–80,000 row uploads must work.
#           PO, verbatim: *"what if we test with option a first instead increase
#           worker ram to start with test whether is it okay for 80k - if it
#           does not work we can later go for option b"*.
# Rules:    NFR-5 (no hard caps anywhere) · BR-MET-038 (the upload caps) ·
#           BR-SHL-016/029 + BR-AUD-014 (the export cap) · CLAUDE.md law 3
#           (defaults fail closed) · law 7 (prove a guard RED)
# ───────────────────────────────────────────────────────
"""**THE CAPS, AND THE ARITHMETIC THAT HAS TO HOLD BETWEEN THEM.**

Everything here is a statement about CONSTANTS, deliberately. None of it times
anything: a case that fails when a shared box is busy teaches lanes to re-run it
until it passes, which is the posture `test_cr036e_import_performance.py` already
records and `test_def2487_accounts_async_bar.py` repeats. The measurements live
in `12-governance/02-decision-log.md` with their figures; these cases hold the
measured numbers as constants and refuse a cap that contradicts them.

WHAT WAS MEASURED, 2026-09-18, on live PostgreSQL 16 in this dev container, at
80,000 rows unless stated. Full table in the decision log.

    target row width, shipped template (`sample_csv`), bytes per row:
        premises 353 · units 208 · accounts 199 · assets_meters 133 ·
        assets_submeters 132 · assets_devices 126 · parts 53 · reads 54.5

    so at 80,000 rows:  premises 26.9 MB · units 15.9 MB · accounts 15.2 MB ·
    assets_meters 10.2 MB · assets_submeters 10.1 MB — **five of seven targets
    over the 10 MB byte cap before a single row is staged.**

THE THREE THINGS PROVED HERE
----------------------------
1. **The byte cap can never refuse before the row cap.** Two caps that disagree
   is the whole defect: `CSV_ROW_CAP` was raised to 100,000 by the PO in August
   (CR-026) and `CSV_BYTE_CAP` stayed at the 10 MB `US-MET-004` §5 wrote when a
   file was 3,000 rows, so the refusal an operator actually met named a byte
   limit while the product's stated limit was a row count.
2. **Every (target, stage) async bar divides into the web-worker timeout**, not
   just the accounts load that `DEF-2487` measured. That defect's guard asserts
   the ONE pair it measured, so the default of 5,000 — justified on a premises
   load at 2.03 ms/row — went on being inherited by **six other targets' loads
   that nobody has ever timed**. Accounts is what that inheritance costs when it
   is wrong: 94 ms/row, so 5,000 rows would be **470 seconds inside a request
   gunicorn kills at 60**. The fix is not a number, it is that an UNMEASURED
   load now takes the worst measured cost rather than the best.
3. **The reads import and the list export reach the same ceiling as the runner.**
   Data that can go in and not come back out is worse than data that cannot go in.

RED EVIDENCE (law 7) — each case was run against the pre-change constants first,
through `pytest`, which is the harness that will run it.
"""

from __future__ import annotations

import pytest

from apps.metering import import_runs, read_import
from apps.tenancy import exports

# ── the measurements these cases hold ───────────────────────────────────────

#: Widest shipped template row, bytes — `premises`, 31 columns, measured with
#: `import_runs.sample_csv` under a real tenant. ⚠ **THE TEMPLATE IS THE
#: NARROWEST REALISTIC FILE, NOT THE WIDEST**: a customer's own export carries
#: longer addresses and owner names than our sample values, which is why the
#: allowance below is a multiple of this rather than this.
WIDEST_TEMPLATE_BYTES_PER_ROW = 353

#: Measured wall clock per row per stage, milliseconds, on live PostgreSQL.
#: A pair absent here is UNMEASURED and takes `_worst_measured` below.
MEASURED_MS_PER_ROW: dict[tuple[str, str], float] = {
    # DEF-2487, 2026-08-30 — 1,048 accounts, 45 queries and 121–127 ms each;
    # transform and validate 0.2s each on the same file.
    (import_runs.TARGET_ACCOUNTS, "load"): 94.0,
    (import_runs.TARGET_ACCOUNTS, "transform"): 0.19,
    (import_runs.TARGET_ACCOUNTS, "validate"): 0.19,
    # CR-026, 2026-08-22 — 101.5s for 50,000 premises rows in one transaction.
    # ⚠ **NOT RE-MEASURED UNCONTENDED.** DEF-MET-5756 re-ran this load on a box
    # carrying seven other suites against the same PostgreSQL and got a far
    # larger figure; a contended number is not a per-row cost and is deliberately
    # NOT recorded here. What that run did establish, because a query count does
    # not care how busy the box is, is that this load issues **4.45 queries per
    # row** — so its wall time is round trips, and it moves with the database.
    # The premises load bar is set conservatively against that uncertainty.
    (import_runs.TARGET_PREMISES, "load"): 2.03,
    # DEF-MET-5756, 2026-09-18 — 80,000 rows, allocation tracer OFF.
    (import_runs.TARGET_PREMISES, "transform"): 0.60,
    (import_runs.TARGET_PREMISES, "validate"): 0.79,
    # DEF-AST-8103, 2026-09-30 — 1,000 meters inserted in 20.09s (the worse of
    # insert and update), PostgreSQL 16, `10-scripts/def_ast_8103_upload_cost.py`.
    (import_runs.TARGET_ASSETS_METERS, "load"): 20.1,
}

#: How much of the request a stage may spend. Three times' margin, the same
#: figure `test_def2487_accounts_async_bar.REQUIRED_MARGIN` holds and CR-026
#: chose before it; quoted rather than imported so that file stays the owner.
REQUIRED_MARGIN = 3.0

STAGES = ("transform", "validate", "load")


def _worst_measured(stage: str) -> float:
    """What an UNMEASURED (target, stage) is assumed to cost: the worst figure
    any target has recorded for that stage.

    ⚠ **THIS IS THE FAIL-CLOSED HALF AND IT IS THE POINT OF THE CASE
    (hard-won law 3).** DEF-2487 happened because accounts inherited a bar
    measured on premises; assuming the BEST measured cost for a target nobody
    has timed would repeat it exactly. Assuming the WORST costs an operator a
    poll and cannot cost them a killed worker.
    """
    return max(ms for (_target, key), ms in MEASURED_MS_PER_ROW.items() if key == stage)


def _ms_per_row(target: str, stage: str) -> tuple[float, bool]:
    """`(ms per row, was it measured for this target)`."""
    if (target, stage) in MEASURED_MS_PER_ROW:
        return MEASURED_MS_PER_ROW[(target, stage)], True
    return _worst_measured(stage), False


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE TWO CAPS MUST NOT DISAGREE
# ══════════════════════════════════════════════════════════════════════════
def test_the_byte_cap_cannot_refuse_a_file_the_row_cap_accepts():
    """⛔ **THE DEFECT, STATED AS ARITHMETIC.**

    `CSV_ROW_CAP` is the product's stated limit — the PO named 100,000 out loud
    (CR-026, *"the sizes of CSV file scan be 50,000 or 100,000 units or premises
    at a time"*) and every refusal sentence about size counts ROWS. A byte cap
    that fires first makes that sentence a lie: the operator is told about
    megabytes when what they were promised was rows.

    RED before the change, with `CSV_BYTE_CAP` at 10 MB::

        AssertionError: CSV_BYTE_CAP is 10,485,760 B but 100,000 rows of the
        widest target need at least 35,300,000 B — the byte cap refuses a file
        the row cap accepts, so the two caps disagree and the smaller one wins
        while the larger one is the one we tell operators about.
        assert 10485760 >= 35300000
    """
    needed = import_runs.CSV_ROW_CAP * WIDEST_TEMPLATE_BYTES_PER_ROW
    assert import_runs.CSV_BYTE_CAP >= needed, (
        f"CSV_BYTE_CAP is {import_runs.CSV_BYTE_CAP:,} B but "
        f"{import_runs.CSV_ROW_CAP:,} rows of the widest target "
        f"({WIDEST_TEMPLATE_BYTES_PER_ROW} B/row, measured) need at least "
        f"{needed:,} B — the byte cap refuses a file the row cap accepts, so "
        "the two caps disagree and the smaller one wins while the larger one "
        "is the one we tell operators about."
    )


def test_every_target_fits_eighty_thousand_rows_under_the_byte_cap():
    """The Product Owner's own number, held as a case rather than as a comment.

    RED before the change on FIVE of the seven targets — premises 28,240,000 B,
    units 16,640,000, accounts 15,920,000, assets_meters 10,640,000,
    assets_submeters 10,560,000, every one of them against a 10,485,760 B cap.
    """
    widths = {  # bytes per row, measured from `sample_csv` under a real tenant
        "premises": 353, "units": 208, "accounts": 199, "assets_meters": 133,
        "assets_submeters": 132, "assets_devices": 126, "parts": 53,
    }
    assert set(widths) == set(import_runs.TARGETS), (
        "a target arrived or left without its measured row width — re-measure "
        "with tests/test_zz_scale_measure.py before moving this table"
    )
    too_big = {
        target: width * 80_000
        for target, width in widths.items()
        if width * 80_000 > import_runs.CSV_BYTE_CAP
    }
    assert not too_big, (
        f"80,000 rows is refused for {sorted(too_big)} — "
        + ", ".join(f"{t} needs {b:,} B" for t, b in sorted(too_big.items()))
        + f" against a cap of {import_runs.CSV_BYTE_CAP:,} B"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · EVERY BAR, NOT JUST THE ONE DEF-2487 MEASURED
# ══════════════════════════════════════════════════════════════════════════
def test_every_target_and_stage_bar_divides_into_the_web_worker_timeout():
    """⛔ **THE GUARD `test_def2487_accounts_async_bar` ASKS OF ONE PAIR AND THIS
    ASKS OF ALL TWENTY-ONE.**

    That file's own case reads `async_row_bar(TARGET_ACCOUNTS, "load")` and
    nothing else, so the default of 5,000 went on being applied to six other
    targets' loads with nobody comparing it to a measured cost. It is the same
    defect DEF-2487 is named for — a bar measured on one target inherited by
    another — surviving inside the fix for it, because the fix asserted the
    exception and never the rule.

    RED before the change, verbatim::

        AssertionError: 5 (target, stage) bars spend more than a third of the
        60s the web worker allows (allowed 20.0s):
          units/load: 5,000 rows x 94.0 ms = 470.0s (worst-measured stand-in)
          assets_meters/load: 5,000 rows x 94.0 ms = 470.0s (worst-measured stand-in)
          assets_submeters/load: 5,000 rows x 94.0 ms = 470.0s (worst-measured stand-in)
          assets_devices/load: 5,000 rows x 94.0 ms = 470.0s (worst-measured stand-in)
          parts/load: 5,000 rows x 94.0 ms = 470.0s (worst-measured stand-in)

    ⚠ **READ WHAT THOSE FIVE LINES SAY.** Not one of those loads has ever been
    timed. The figure beside each is ACCOUNTS' cost, stood in for them by
    `_worst_measured` — which is the whole argument: the old bar assumed they
    were premises-shaped, this one assumes they are accounts-shaped, and until
    somebody measures them the second assumption is the one that cannot kill a
    worker. If a target here is really cheap, time it and give it a row in
    `ASYNC_ROW_BAR_BY_TARGET`; that is a decision somebody makes, which is
    exactly what DEF-2487 asked for.
    """
    allowed = import_runs.WEB_WORKER_TIMEOUT_SECONDS / REQUIRED_MARGIN
    over = []
    for target in import_runs.TARGETS:
        for stage in STAGES:
            bar = import_runs.async_row_bar(target, stage)
            ms, measured = _ms_per_row(target, stage)
            worst = bar * ms / 1000
            if worst > allowed:
                over.append(
                    f"{target}/{stage}: {bar:,} rows x {ms} ms = {worst:.1f}s "
                    f"({'measured' if measured else 'worst-measured stand-in'})"
                )
    assert not over, (
        f"{len(over)} (target, stage) bars spend more than a third of the "
        f"{import_runs.WEB_WORKER_TIMEOUT_SECONDS}s the web worker allows "
        f"(allowed {allowed:.1f}s):\n  " + "\n  ".join(over)
    )


def test_no_stage_of_any_target_runs_inline_at_sixty_thousand_rows():
    """The Product Owner's ask, stated as a property of the bars.

    Green before the change too — 60,000 is over every bar there has ever been —
    and it is here so that it CANNOT be undone by a later lane raising a bar to
    buy back a poll. A bar above 60,000 would put an 80,000-row load inside a
    60-second request, which is the failure this whole defect is about.
    """
    inline = [
        f"{target}/{stage} (bar {import_runs.async_row_bar(target, stage):,})"
        for target in import_runs.TARGETS
        for stage in STAGES
        if import_runs.async_row_bar(target, stage) >= 60_000
    ]
    assert not inline, (
        "these stages would run INSIDE a web request at 60,000 rows: "
        + ", ".join(inline)
    )


def test_the_load_stage_never_inherits_the_transform_bar():
    """⛔ **THE SHAPE, NOT THE NUMBER.** Every load measured in this repo costs
    one to two orders of magnitude more per row than its own transform, so a
    single constant for all three stages is guaranteed to be wrong for one of
    them. This refuses the arrangement rather than any particular figure.
    """
    assert "load" in import_runs.ASYNC_ROW_BAR_BY_STAGE, (
        "the load stage has no bar of its own — it is back on ASYNC_ROW_BAR, "
        "which is a transform-shaped figure (5,000 rows) being spent on the "
        "one stage that writes"
    )
    for target in import_runs.TARGETS:
        load = import_runs.async_row_bar(target, "load")
        for cheap in ("transform", "validate"):
            assert load <= import_runs.async_row_bar(target, cheap), (
                f"{target}: the load bar ({load:,}) is above its {cheap} bar "
                f"({import_runs.async_row_bar(target, cheap):,}), so the "
                "expensive stage is allowed to run inline for longer than the "
                "cheap one"
            )


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHAT GOES IN MUST COME OUT
# ══════════════════════════════════════════════════════════════════════════
def test_the_reads_import_reaches_the_same_row_ceiling_as_the_runner():
    """A reads file is the NARROWEST of the eight (54.5 B/row measured), so its
    10 MB byte cap was never what stopped it — `CSV_ROW_CAP = 50,000` was, and
    50,000 is below the Product Owner's 60–80,000 by itself.

    RED before the change::

        AssertionError: the reads import stops at 50,000 rows while the one
        runner carries 100,000 — a meter file is refused at a size a premises
        file is accepted at, for no reason anyone has written down.
        assert 50000 >= 100000
    """
    assert read_import.CSV_ROW_CAP >= import_runs.CSV_ROW_CAP, (
        f"the reads import stops at {read_import.CSV_ROW_CAP:,} rows while the "
        f"one runner carries {import_runs.CSV_ROW_CAP:,} — a meter file is "
        "refused at a size a premises file is accepted at, for no reason "
        "anyone has written down"
    )
    needed = read_import.CSV_ROW_CAP * 60  # 54.5 B/row measured, rounded up
    assert read_import.CSV_BYTE_CAP >= needed, (
        f"reads CSV_BYTE_CAP is {read_import.CSV_BYTE_CAP:,} B against "
        f"{needed:,} B for {read_import.CSV_ROW_CAP:,} rows at the measured "
        "54.5 B/row"
    )


def test_the_list_export_carries_what_the_import_can_load():
    """⛔ **DATA THAT GOES IN AND WILL NOT COME OUT.** A tenant may import
    100,000 premises and then be refused the CSV of them at 50,000 — and unlike
    the import caps this one has no memory argument behind it: `write_csv`
    streams from `selection_iter`, which is `.iterator(chunk_size=500)` on a
    QuerySet, so the file is written row by row and never materialised.

    ⚠ **THE COMPARISON IS GONE BECAUSE ONE SIDE OF IT IS (`P2.4`,
    `CR-142-BRC07`).** This case compared two caps and demanded the export's be
    the larger; raising it to 100,000 on 2026-09-18 (`DEF-MET-5756`) was the
    right fix for that day and the wrong SHAPE, because 100,000 was still short
    of Killeen's ~685,000 bill rows a year. **The export cap is deleted**, so
    the question this case asks — *can a tenant put data in that they cannot
    get back out?* — is now answered structurally rather than arithmetically:
    there is no number on the way out at all.

    The import caps stay and are another rule's (`CSV_ROW_CAP`, `CSV_BYTE_CAP`):
    they bound what ARRIVES in one file, which is a real memory argument, and
    the cases above measure them.
    """
    assert not hasattr(exports, "EXPORT_ROW_CAP"), (
        f"`EXPORT_ROW_CAP` is back at {getattr(exports, 'EXPORT_ROW_CAP', None)}. "
        f"An import may load {import_runs.CSV_ROW_CAP:,} rows in ONE file and a "
        "tenant may hold hundreds of thousands; NFR-5 forbids a ceiling on the "
        "way out — see P2.4."
    )


def test_the_export_streams_rather_than_building_a_list():
    """The cap above is only safe to raise BECAUSE of this, so it is asserted
    rather than assumed (hard-won law 1 — a comment claiming a guarantee is not
    the guarantee).

    ⚠ **IT IS TRUE OF A QuerySet AND NOT OF EVERY SELECTION.** `selection_iter`
    iterates an already-materialised list as it is, and the derived-filter lists
    (units, assets, routes, cycles and the four rating lists) hand it one. Those
    hold their rows in memory whatever this cap says, which is `NFR-3`'s problem
    and not this defect's — recorded here so the next lane raising this cap
    knows which half of the registry it is safe for.
    """
    import inspect

    source = inspect.getsource(exports.selection_iter)
    assert ".iterator(" in source, (
        "exports.selection_iter no longer streams a QuerySet — the export row "
        "cap was raised on the strength of it doing so"
    )
