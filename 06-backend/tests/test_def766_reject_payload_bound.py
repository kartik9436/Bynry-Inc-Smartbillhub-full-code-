# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (the CR-023 import runner)
# Defect:   DEF-766 — *"THE SCREEN POLLS A 4.28 MB PAYLOAD EVERY TWO SECONDS ON
#           A RUN WITH MANY REJECTS — rejects() IS UNBOUNDED"*, measured by lane
#           IMPORTPERF on the PO's own all-reject run (9,881 rejects).
# Rules:    BR-MET-090 (the run's record is what it DID) · B14 rule 16 (the
#           reject table on screen is paginated) · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""THE FIXTURE THAT CAN SEE AN UNBOUNDED PAYLOAD.

**Why DEF-766 survived every gate and every test: EVERY TEST ASSERTED REJECT
CONTENT AND NONE ASSERTED PAYLOAD SIZE**, and no reject fixture in this repo
exceeded 20 rows — under the 50-row window, so a bounded server and an unbounded
one are INDISTINGUISHABLE on all of them. `test_cr023_import_stages.py` asserts
`len(result["rejects"]) == 3` and would pass over a server that shipped four
megabytes on the next file. A fixture that cannot tell the two apart is the
whole reason this reached a live screen.

So this file builds two runs that differ ONLY in how many rows reject — 60 and
600 — and asserts the thing that was actually wrong:

    THE SIZE OF A RUN PAYLOAD DOES NOT GROW WITH THE NUMBER OF REJECTS.

That is deterministic on any machine: no clock, no row-per-second figure, no CI
flake. The unbounded shape fails it by an order of magnitude and cannot be made
to pass by tuning a threshold.

MEASURED HERE (the numbers this file prints, dev container, live Postgres 16):

    600 rejects, UNBOUNDED (the shipped shape, rebuilt in `_unbounded_rejects`)
        payload  259,171 bytes
    600 rejects, BOUNDED (this fix, default 50-row window)
        payload   23,272 bytes  —  11.1x smaller, and FLAT in the reject count

⚠ **THE TWO THINGS A BOUND MUST NOT COST**, both asserted below:
  * **the TOTAL** — an operator reads *"600 rejected"*, never *"50"*, so
    `rejects_window.total` is a COUNT in the database and not `len(rejects)`;
  * **the `Fix here` path** — the inline editor edits a reject's `raw` source
    cells, so every reject in the window still carries them. A window whose
    rows arrive stripped is the DEF-762 bug again in a new place: an editor
    that opens on a row whose data was never sent.
"""

import json

import pytest

from apps.metering import import_runs, models

from tests.test_cr023_import_stages import ALL_ON, HEADERS, MAPPING, _csv, _row
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _all_reject_csv(rows: int) -> str:
    """`rows` premises rows, EVERY ONE of which rejects.

    A blank `ADDR1` is `PRM.ADDRESS_REQUIRED`, tier 1 — the same structural
    refusal the PO's own run hit on every row. Each row keeps its own
    `PREMISE_ID`, so stage 2's exact-duplicate drop takes none of them and
    stage 3 sees all `rows`.
    """
    return _csv([_row(index, ADDR1="") for index in range(1, rows + 1)], HEADERS)


def _validated(actor, rows: int) -> dict:
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": f"all_rejects_{rows}.csv",
            "content": _all_reject_csv(rows),
            "session_ref": "sess_def766",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
    return import_runs.validate(actor, run["id"])


def _bytes(payload: dict) -> int:
    """What the wire carries — the payload as JSON, in bytes."""
    return len(json.dumps(payload, default=str).encode("utf-8"))


def _unbounded_rejects(run_id) -> list[dict]:
    """`rejects()` AS IT SHIPPED — no limit, no offset, every row's full `raw`.

    Kept here rather than in the module so the comparison this file makes is
    against the real defect and NOT against something the fix can quietly
    redefine. If a future change makes the served payload look like this again,
    the ratio assertion below goes red on it.
    """
    run = models.ImportRun.objects.get(pk=run_id)
    return [
        {
            "row_no": row.row_no,
            "source_key": row.source_key,
            "problem": row.problem,
            "fix_hint": row.fix_hint,
            "outcome": row.outcome,
            "raw": row.raw or {},
        }
        for row in models.ImportRunRow.objects.filter(
            tenant_id=run.tenant_id, run=run, outcome="rejected"
        ).order_by("row_no")
    ]


# ═══════════════════════════════════════════════════════════════════════════
# THE ASSERTION THE OLD FIXTURES COULD NOT MAKE
# ═══════════════════════════════════════════════════════════════════════════


def test_def766__a_run_payload_does_not_grow_with_the_number_of_rejects(brazos, marcus):
    """60 rejects and 600 rejects answer payloads of the SAME SIZE.

    The screen polls `GET /imports/{id}` every two seconds while a stage is in a
    worker (`IMPORT_POLL_INTERVAL_MS = 2000`), so payload size is not a detail of
    one request — it is a rate. Ten times the rejects must not be ten times the
    poll.
    """
    with tenant_ctx(brazos):
        small = _validated(marcus, 60)
        large = _validated(marcus, 600)

    assert small["counts"]["errors"] == 60
    assert large["counts"]["errors"] == 600
    small_bytes, large_bytes = _bytes(small), _bytes(large)
    growth = large_bytes / small_bytes
    print(f"\nDEF-766  60 rejects: {small_bytes:,} B   600 rejects: {large_bytes:,} B "
          f"({growth:.2f}x)")
    assert growth < 1.10, (
        f"a run payload grew {growth:.1f}x when the rejects grew 10x — "
        f"{small_bytes:,} B for 60 rejects, {large_bytes:,} B for 600. That is "
        "DEF-766: the reject list is riding along unbounded, polled every 2s."
    )


def test_def766__the_bounded_payload_is_an_order_of_magnitude_smaller(brazos, marcus):
    """The same run, served both ways, on one set of rows.

    ⚠ Not a timing assertion (`test_cr036e_import_performance.py`'s rule): both
    figures are byte counts of the same data structure, so the comparison is the
    same on a busy box as on an idle one.
    """
    with tenant_ctx(brazos):
        served = _validated(marcus, 600)
        unbounded = dict(served)
        unbounded["rejects"] = _unbounded_rejects(served["id"])

    served_bytes, unbounded_bytes = _bytes(served), _bytes(unbounded)
    print(f"\nDEF-766  bounded: {served_bytes:,} B   unbounded: {unbounded_bytes:,} B "
          f"({unbounded_bytes / served_bytes:.1f}x)")
    assert unbounded_bytes > served_bytes * 5, (
        "the fixture cannot see the defect it was written for: the unbounded "
        f"payload ({unbounded_bytes:,} B) is not materially bigger than the "
        f"bounded one ({served_bytes:,} B). Grow the fixture, do not weaken this."
    )
    assert served_bytes < 60_000, f"a polled run payload of {served_bytes:,} bytes"


def test_def766__the_window_is_fifty_and_the_TOTAL_is_still_the_true_count(brazos, marcus):
    """*"an operator must still see that 9,881 rows were rejected, not 50"*."""
    with tenant_ctx(brazos):
        served = _validated(marcus, 600)

    assert import_runs.REJECT_WINDOW_DEFAULT == 50
    assert len(served["rejects"]) == 50
    assert served["rejects_window"] == {"total": 600, "offset": 0, "limit": 50}
    # The count is the DATABASE's, not the window's length — the one arithmetic
    # error that would make the fix cost the operator the figure that matters.
    assert served["counts"]["errors"] == served["rejects_window"]["total"]


def test_def766__every_reject_in_the_window_still_carries_its_raw_cells(brazos, marcus):
    """The `Fix here` path. `RejectList` draws the control only when the row
    carries `raw`, and `RejectFixEditor` edits exactly those cells — so a window
    that dropped them would silently retire the inline fix on every run."""
    with tenant_ctx(brazos):
        served = _validated(marcus, 600)

    for reject in served["rejects"]:
        assert reject["raw"], "a reject with no raw cells cannot be fixed inline"
        assert set(reject["raw"]) >= set(HEADERS), reject["raw"]
        assert reject["problem"] and reject["fix_hint"]


def test_def766__the_pager_reaches_the_rejects_that_are_not_on_page_one(brazos, marcus):
    """Bounding the payload must not put row 600 out of reach — the operator
    asks for the next page and the server answers it. This is what a WINDOW buys
    over a truncated list, and the reason this fix is a page rather than a cap.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, 600)["id"]
        first = import_runs.read_run(run_id, reject_offset=0, reject_limit=50)
        second = import_runs.read_run(run_id, reject_offset=50, reject_limit=50)
        last = import_runs.read_run(run_id, reject_offset=550, reject_limit=50)

    rows_of = lambda answer: [reject["row_no"] for reject in answer["rejects"]]  # noqa: E731
    assert len(rows_of(first)) == len(rows_of(second)) == len(rows_of(last)) == 50
    assert set(rows_of(first)) & set(rows_of(second)) == set()
    assert rows_of(first) + rows_of(second) == sorted(rows_of(first) + rows_of(second))
    assert max(rows_of(last)) == 600
    # Every window states the same total — a footer that read "50" on page one
    # and "600" on page two would be a footer arguing with itself.
    for answer in (first, second, last):
        assert answer["rejects_window"]["total"] == 600


def test_def766__the_window_is_clamped_and_a_garbled_one_takes_the_default(brazos, marcus):
    """No client can ask for the 4.28 MB back, and a bad parameter never blanks
    a stage the operator is watching — this surface is POLLED, so a refusal
    mid-poll costs more than a fallback."""
    assert import_runs.reject_window(0, 10_000) == (0, import_runs.REJECT_WINDOW_MAX)
    assert import_runs.reject_window(-5, -1) == (0, 0)
    assert import_runs.reject_window("banana", "50") == (0, 50)
    assert import_runs.reject_window(None, None) == (0, import_runs.REJECT_WINDOW_DEFAULT)

    with tenant_ctx(brazos):
        run_id = _validated(marcus, 600)["id"]
        huge = import_runs.read_run(run_id, reject_offset=0, reject_limit=10_000)
        garbled = import_runs.read_run(run_id, reject_offset="x", reject_limit="y")

    assert huge["rejects_window"]["limit"] == import_runs.REJECT_WINDOW_MAX
    assert len(huge["rejects"]) == 600  # all of them, because 600 < the ceiling
    assert garbled["rejects_window"] == {"total": 600, "offset": 0, "limit": 50}


def test_def766__the_poll_route_itself_forwards_the_window(brazos, marcus):
    """Built is not wired (hard-won law 2). The bound lives in `import_runs`,
    and `GET /imports/{id}` is the surface that is polled — so the route must
    read `?reject_offset=` / `?reject_limit=` or the page control on screen
    reaches nothing."""
    from apps.metering import api as metering_api

    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        run_id = _validated(marcus, 600)["id"]

    default = api_call(
        metering_api.import_run_detail, "get",
        user=marcus.user, role="billing_clerk", tenant=brazos, run_id=run_id,
    )
    assert default.status_code == 200
    assert len(default.data["rejects"]) == 50
    assert default.data["rejects_window"]["total"] == 600

    paged = api_call(
        metering_api.import_run_detail, "get",
        user=marcus.user, role="billing_clerk", tenant=brazos, run_id=run_id,
        query={"reject_offset": "550", "reject_limit": "50"},
    )
    assert paged.status_code == 200
    assert [r["row_no"] for r in paged.data["rejects"]][-1] == 600
    assert paged.data["rejects_window"] == {"total": 600, "offset": 550, "limit": 50}
