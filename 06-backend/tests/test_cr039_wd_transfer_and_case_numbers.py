# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave D tasks 15 and 16 — *"a series and number for transfer"*
#           and *"the same for disconnect"*, against the CR's own trace finding
#           5: *"Transfer and disconnect have tables and no number"*, whose
#           consequence is *"A clerk cannot quote a reference; nothing on a bill
#           can point at the job that caused a change"*.
# Rules:    BR-TEN-035 (a number is allocated INSIDE the issuing transaction;
#           gaps are fine and a number is never reused) · BR-TEN-043 (the issue
#           date is an INPUT, never the wall clock) · CR-005 (the catalogue's
#           own rules — asserted here only where this change touches them)
# Questions: OQ-426 (the transfer series' seeded format — OPEN) · OQ-427 (the
#           disconnect case series' — OPEN, and r10 answers it a third way)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.2 · §5.7.6 ·
#           §5.7.7 · §5.8.2 · §5.8.6 · §5.8.7 — **all six read for a number and
#           none of them draws one**, which is what OQ-426/OQ-427 record.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-039 W-D 15/16 — the number a clerk quotes, and the absence where it isn't.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE PROVES, AND WHY THAT IS THE UNUSUAL PART
════════════════════════════════════════════════════════════════════════════
Most numbering tests assert a rendered string. **This one cannot, and that is
the finding rather than a gap in the test.** A series' seeded default is
DERIVED FROM THE PROTOTYPE and never invented — `core/numbering.py` says so of
`CONNECTION` in its own words — and B18 draws no number for a transfer or a
disconnect case. So no series was minted, `OQ-426` and `OQ-427` hold the
question, and what is buildable today is the machinery either answer needs:

  1. the column exists and holds a number when one is issued;
  2. the allocation happens INSIDE the creating transaction (BR-TEN-035), so a
     record never exists unnumbered and a rolled-back create leaves a GAP
     rather than a number two records could share;
  3. with no series, the absence is REPORTED with its reason and its open
     question — never faked, never a bare dash, never `"TRF-00000"`.

⚠ **CASE 1 IS PROVED BY SEEDING A SERIES ROW DIRECTLY IN THE TEST, AND THAT IS
NOT THE LANE PICKING A PREFIX.** `PROBE_FORMAT` below is deliberately a shape
NO catalogue could ever seed — it is a probe, chosen so that a reader cannot
mistake it for a proposal and so that a pass cannot come from a real default
happening to match. `tests/test_cr005_numbering_reaches_records.py` uses the
same device for the same reason.

════════════════════════════════════════════════════════════════════════════
RED-FIRST (r11 step 2d / hard-won law 7) — every case below was broken first
════════════════════════════════════════════════════════════════════════════
Each mutation was applied, run, its failure captured verbatim, and reverted.

  1. `transfers.Transfer.transfer_no` declared on the model with migration
     0028's `RunPython` removed — i.e. the state without the column →
        E       AssertionError: model fields with no column: {'transfer_no'}
        E       assert {'transfer_no'} == set()
        FAILED tests/test_w7_transfers.py::test_tc_trf_12_the_model_and_the_live_table_agree_column_for_column
     (that guard is `test_w7_transfers.py`'s and is named here because it is
     the one that covers the UNMANAGED half — `makemigrations --check` never
     compares an unmanaged model's fields and is silent about `transfer_no`.)

  2. migration 0028 removed entirely → `makemigrations --check --dry-run`:
        Migrations for 'customers':
          apps/customers/migrations/0028_disconnectcase_case_no_and_more.py
            + Add field case_no to disconnectcase
            + Create constraint uq_disconnect_cases_tenant_case_no_ci on model disconnectcase

  3. `_allocate_transfer_no` returning `("TRF-00000", None)` on a missing series
     instead of reporting — the exact "invent a prefix" mistake this lane
     refused →
        E       AssertionError: a number was invented where no series exists: 'TRF-00000'
        FAILED tests/test_cr039_wd_transfer_and_case_numbers.py::test_a_transfer_with_no_series_reports_the_absence_and_never_invents_a_number

  4. `_allocate_case_no` swallowing the absence as `None` with NO reason served
     — the dash-that-means-two-things defect →
        E       AssertionError: an absent case number served no reason at all
        FAILED tests/test_cr039_wd_transfer_and_case_numbers.py::test_a_disconnect_case_with_no_series_reports_the_absence_and_never_invents_a_number

  5. `open_case` allocating the number OUTSIDE its `atomic()` (the call hoisted
     above the `with`) →
        E       AssertionError: the counter moved although the case was never written: 700 → 701
        E       assert 701 == 700
        FAILED tests/test_cr039_wd_transfer_and_case_numbers.py::test_a_case_that_fails_to_write_leaves_the_counter_where_it_was

     ⚠ **AND THE FIRST VERSION OF THAT TEST PASSED ON THIS MUTATION.** It
     wrapped the call in an `atomic()` of its own and raised after it returned,
     so both worlds rolled back to the same savepoint and the counter came back
     either way. Only breaking the guard revealed that the guard could not see
     the break — DEF-182's lesson, one file over: a check whose output cannot
     distinguish pass from fail is worse than none, because it is trusted. The
     shipped shape fails the WRITE while the ALLOCATION stands; see
     `_make_the_insert_fail`, whose docstring records this in full.

  6. `case_reference_absence` collapsing both arms onto
     `CASE_NUMBER_UNAVAILABLE` — S90's two absences merged into one →
        E       AssertionError: assert 'numbering_series_missing' == 'no_case_opened'
        FAILED tests/test_cr039_wd_transfer_and_case_numbers.py::test_the_two_reasons_a_disconnect_reference_can_be_empty_are_not_the_same_reason

     ⚠ **AND THE FIRST VERSION OF *THAT* TEST PASSED ON THIS ONE TOO** — it
     compared the two CONSTANTS, which says nothing about which one the row
     builder picks, and the branch was inline in `list_row` where no test could
     reach it. That is why `case_reference_absence` is a named three-line
     function: the extraction is what made the guard capable of failing.

  7. `RecordNumberCell` rendering `—` instead of the server's reason (the
     bare-dash defect the cell exists to prevent) → all three screen cases:
        AssertionError: expected '<div data-embedded="" data-screen="S8…' to contain 'A number series for transfers has not…'
        AssertionError: expected '<div data-embedded="" data-screen="S9…' to contain 'A number series for disconnections ha…'
        AssertionError: expected '<div data-embedded="" data-screen="S9…' to contain 'No disconnection case has been opened'
        Tests  3 failed | 35 passed | 5 todo (43)

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DELIBERATELY DOES NOT ASSERT
════════════════════════════════════════════════════════════════════════════
**No prefix.** Not `TRF-`, not `DSC-`, not `WO-`. Asserting one here would be
DEF-615 reproduced exactly — a test and a catalogue each picking independently,
disagreeing from the day they land, and the disagreement invisible until
somebody runs that one test. The prefix belongs in
`tests/test_def615_series_defaults.py::EXPECTED_PREFIX` on the day OQ-426 and
OQ-427 close, beside the catalogue row that makes it true.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_reads, disconnects, transfer_reads, transfers
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import numbering as core_numbering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    marcus,
    tenant_ctx,
)
from tests.test_w7_disconnects import _account, _owes
from tests.test_w7_transfers import _mover

pytestmark = pytest.mark.django_db

#: ⚠ **A PROBE, NOT A PROPOSAL.** No catalogue would ever seed this: the literal
#: is nonsense on a screen and belongs to no entity. That is the point — a
#: reader cannot mistake it for OQ-426/OQ-427's answer, and a pass cannot come
#: from a real seeded default happening to match. Same device, same reason, as
#: `test_cr005_numbering_reaches_records.PROBES`.
PROBE_FORMAT = "ZZPROBE-{YY}-{0000}"

TODAY = date(2026, 8, 25)


def _seed_series(series: str, *, next_number: int = 1) -> None:
    """Put this tenant's row for `series` onto the probe format.

    ⚠ **`update_or_create`, NOT `create`, SINCE 2026-08-27 — and the reason is
    the whole shape of this file changing under it.** When it was written
    neither series was catalogued, so provisioning made no row and a plain
    `create` was correct. `transfer` joined `SERIES_CATALOG` when the PO closed
    `OQ-426`, so `_seed_number_series` now writes a `transfer` row into every
    tenant at provisioning and a `create` here raises on the (tenant, series)
    unique index.

    ⚠ **AMENDED AGAIN LATER THE SAME DAY.** This paragraph continued *"`disconnect
    _case` is still uncatalogued (`OQ-427`) and still has no row, so the SAME
    helper must serve both"* — and `OQ-427` closed hours later on *"it needs its
    own series"*, so BOTH series are now provisioned into every tenant and
    `create` would raise for both. `update_or_create` was the right call for a
    reason that has since evaporated and is still the right call; the reasoning
    is kept rather than deleted, because a helper whose comment describes a
    state the repo has left is exactly what hard-won law 1 is about.

    The FORMAT is still validated through the product's own
    `core.numbering.validate_format`, which is the half that could be wrong.
    """
    core_numbering.validate_format(PROBE_FORMAT)
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant_id=_current_tenant_id(),
        series=series,
        defaults={"format": PROBE_FORMAT, "next_number": next_number},
    )


def _forget_series(series: str) -> None:
    """Remove this tenant's row for `series` — a tenant provisioned BEFORE the
    catalogue row landed, which is a real state and not a contrivance.

    `_seed_number_series` is `get_or_create` per series, so a host already
    running when `OQ-426` closed keeps no `transfer` row until somebody runs
    `manage.py seed_demo --tenant <subdomain>`. Until they do, the allocator
    takes the missing-series branch — which is the branch the absence contract
    below is about, and the only way to reach it once provisioning seeds the row.
    """
    tenancy_models.NumberSeries.objects.filter(
        tenant_id=_current_tenant_id(), series=series
    ).delete()


def _current_tenant_id():
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


@pytest.fixture(autouse=True)
def series_sink():
    """The REAL sink the real callers use — `AppConfig.ready` registers it.

    Pointing this at a stub would make the file prove its own fixture instead of
    the product, which is `test_cr005_numbering_reaches_records`'s own note and
    is worth repeating one module over.
    """
    core_numbering.set_series_sink(tenancy_services.allocate_series_number)
    yield
    core_numbering.set_series_sink(tenancy_services.allocate_series_number)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE ABSENCE — what every tenant sees today, and what it must never be
# ═══════════════════════════════════════════════════════════════════════════
def test_both_the_transfer_and_the_disconnect_series_are_catalogued():
    """⚠ **THIS TEST USED TO PASS BY FINDING NOTHING. BOTH HALVES HAVE NOW FIRED,
    ON THE SAME DAY, AND IT IS RENAMED BECAUSE ITS OLD NAME BECAME A FALSE
    CLAIM.** It was `test_the_transfer_series_is_catalogued_and_the_disconnect_is
    _still_not`; a test name is read far more often than a test body, and a name
    asserting an open question that has closed is exactly the stale-comment
    hazard hard-won law 1 is about.

    Its predecessor asserted that NEITHER series was catalogued, and said in its
    own failure message what to do when one arrived. `OQ-426` closed on
    2026-08-27 — PO verbatim, *"Transfer TRF-26-0001 recommend it is one job
    spanning two accounts, and neither account number names it - follow same
    logic that we are following for other numbers we have did in settings"* —
    so it went RED exactly as designed, and this is the shape it named:

        AssertionError: a `transfer` number series has appeared in
        SERIES_CATALOG. If OQ-426 was answered, this test is now the wrong
        shape — delete it and add the prefix to
        tests/test_def615_series_defaults.EXPECTED_PREFIX, the size in
        test_cr005_numbering_set08, and the `wired` set + both counts in
        test_cr005_numbering_reaches_records.

    All four of those places moved in the same commit as the catalogue row.

    ⛔ **THE DISCONNECT HALF WAS DELIBERATELY LEFT INVERTED AND HAS NOW FIRED
    TOO.** It said `OQ-427` was *"explicitly still OPEN"*, because the transfer
    ruling's own reason — *"one job spanning two accounts, and neither account
    number names it"* — is precisely what does NOT carry to a disconnect, which
    belongs to ONE account whose number already names it and which r10 draws as
    a WORK ORDER (`WO-4833`). **That was right, and the answer to it was to ASK,
    which is what happened.** PO verbatim, in full: *"it needs its own series"*.
    Its RED, verbatim, on the commit that added the catalogue row:

        AssertionError: a `disconnect_case` number series has appeared in
        SERIES_CATALOG — OQ-427 is STILL OPEN and the transfer ruling does not
        cover it. If it was answered, add the prefix to
        tests/test_def615_series_defaults.EXPECTED_PREFIX, the size in
        test_cr005_numbering_set08, and the `wired` set + both counts in
        test_cr005_numbering_reaches_records.

    All four moved in that commit, and so did the fifth the transfer half
    discovered — the S8 label, `tests/test_cr005_numbering_set08
    ::test_def880_every_catalogued_series_has_a_label_on_the_settings_screen`.

    ⚠ **WHAT THE RULING DID NOT SAY IS THE PREFIX.** `DSC-` is the BUILD's
    delegated choice (decision log 2026-08-27), which is why it is pinned in
    `EXPECTED_PREFIX` rather than asserted as a ratified figure here.
    """
    catalogued = set(core_numbering.KNOWN_SERIES)
    assert transfers.TRANSFER_SERIES in catalogued, (
        "the `transfer` series has left SERIES_CATALOG. OQ-426 is CLOSED and its "
        "ruling names the rendered string TRF-26-0001; removing the row un-numbers "
        "every future transfer."
    )
    assert disconnects.DISCONNECT_CASE_SERIES in catalogued, (
        "the `disconnect_case` series has left SERIES_CATALOG. OQ-427 is CLOSED — PO "
        'verbatim, *"it needs its own series"* — and removing the row un-numbers '
        "every future disconnect case AND every case the post-closure restart reopens."
    )
    # The lane's own claim about what it did and did NOT change, made checkable
    # rather than asserted in a commit message. 25 → 26 → 27: one row each time.
    # ⚠ **29 SINCE THE SAME AFTERNOON** — `move_in` and `move_out` joined for
    # CR-039 wave D task 18, whose own suite is
    # `tests/test_cr039_wd_move_records.py`. Their formats are the BUILD's, not
    # a PO ruling; this count is here only so a fifth row cannot arrive
    # unnoticed. RED first, verbatim: `AssertionError: assert 29 == 27`.
    # ⚠ **31 SINCE 2026-09-22, AND THIS LINE SAID 29 UNTIL 2026-10-02 — RED
    # FOR FOUR WEEKS, UNREAD.** Two rows arrived and each moved
    # `test_cr005_numbering_set08`'s count in its own commit but not this one:
    # `interruption_report` (`RP-`, CR-068 wave B, `b83059cf5`, 2026-09-04 —
    # 30) and `settlement` (`STL-`, PO 2026-09-22 *"(a) STL-26-0001"*,
    # `11cd8aefa` — 31). Neither touches the transfer or disconnect rows this
    # case is about. Re-measured, not incremented: `assert 31 == 29`.
    assert len(catalogued) == 31
    # ⛔ AND THE WORK ORDER IS STILL NOT WIRED TO EITHER. The ruling's whole
    # content is that a case is its OWN document rather than r10's `WO-4833`,
    # so a lane that later pointed `_allocate_case_no` at `work_order` would be
    # undoing the ruling rather than tidying the catalogue.
    assert core_numbering.WORK_ORDER != disconnects.DISCONNECT_CASE_SERIES


def test_the_first_transfer_on_a_new_tenant_is_trf_26_0001():
    """⚠ **THE RATIFIED FIGURE, PINNED SO DRIFT GOES RED.**

    The PO named a rendered STRING rather than a format — *"Transfer
    TRF-26-0001"* — and this is the assertion that the product produces exactly
    that string. It is the figure the human-review ledger row states in plain
    English: *"the first transfer on a new tenant is numbered TRF-26-0001"*.

    Deterministic on purpose: the issue date is a literal rather than
    `tenant_today()`, so this test says the same thing in 2027 as it does today.
    The end-to-end half — that a real `start_transfer` on a real tenant renders
    the tenant's own seeded default — is the case two blocks down.
    """
    default = tenancy_services.SERIES_DEFAULTS[core_numbering.TRANSFER]
    assert default == "TRF-{YY}-{0000}"
    assert core_numbering.render(default, 1, date(2026, 8, 27)) == "TRF-26-0001"


def test_the_first_disconnect_case_on_a_new_tenant_is_dsc_26_0001():
    """⚠ **THE BUILD'S FIGURE, PINNED SO DRIFT GOES RED — AND IT IS NOT THE SAME
    KIND OF FIGURE AS THE ONE ABOVE.**

    `OQ-427` closed on one sentence — PO verbatim, in full: *"it needs its own
    series"* — which settles that a disconnect case is its OWN document rather
    than r10's `WO-4833` work order, and says nothing about the prefix. The
    format is therefore the BUILD's DELEGATED choice, recorded as the build's in
    `12-governance/02-decision-log.md` under *"a disconnect gets its own
    series"*, and `DSC-26-0001` is the string that choice renders on day one.

    It is pinned for the same reason the ratified one is: a later lane changing
    `DSC-` to `DC-` would silently renumber every disconnect notice a customer
    is holding, and BR-TEN-035 forbids renumbering what has been issued.

    Deterministic on purpose — the issue date is a literal, so this says the
    same thing in 2027.
    """
    default = tenancy_services.SERIES_DEFAULTS[core_numbering.DISCONNECT_CASE]
    assert default == "DSC-{YY}-{0000}"
    assert core_numbering.render(default, 1, date(2026, 8, 27)) == "DSC-26-0001"
    # ⚠ `DSP-` is the dispatch batch and is ONE CHARACTER AWAY. That is ACCEPTED,
    # not solved (OQ-427 raised it; the decision log names it). What must stay
    # true is that they are DIFFERENT — CR-005's duplicate-prefix warning
    # compares the literals, and a tenant provisioned today must not be greeted
    # by one on a screen nobody has touched.
    assert core_numbering.literal_prefix(default) == "DSC-"
    assert (
        core_numbering.literal_prefix(
            tenancy_services.SERIES_DEFAULTS[core_numbering.DISPATCH_BATCH]
        )
        == "DSP-"
    )


def test_a_transfer_with_no_series_reports_the_absence_and_never_invents_a_number(brazos, marcus):
    """⚠ **NO LONGER "every tenant today" — it is every tenant that has not been
    RE-SEEDED since `OQ-426` closed, and that is why this guard survives.**

    `_seed_number_series` is `get_or_create` per series, so the `transfer` row
    reaches a host that was already running only when somebody runs
    `manage.py seed_demo --tenant <subdomain>`. Until then the allocator takes
    the missing-series branch, and the three things below must all still be true
    at once — the third being the one a later lane will be tempted to "fix": the
    number is NULL, a REASON is served beside it, and the reason names the open
    question so a reader can find out why.

    The row is DELETED rather than never created, because provisioning now makes
    one; deleting it is the only way to reach this branch, and it reproduces the
    real state rather than a contrived one.
    """
    with tenant_ctx(brazos):
        _forget_series(transfers.TRANSFER_SERIES)
        _customer, account, _unit = _mover(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

    assert (
        started["transfer_no"] is None
    ), f"a number was invented where no series exists: {started['transfer_no']!r}"
    absence = started["transfer_no_unavailable"]
    assert absence is not None, "an absent transfer number served no reason at all"
    assert absence["code"] == transfers.NUMBERING_SERIES_MISSING
    assert absence["series"] == transfers.TRANSFER_SERIES
    assert absence["open_question"] == "OQ-426"
    # A sentence a billing clerk can act on, and the id is NOT in it (DEF-332).
    assert "number series for transfers has not been set up" in absence["detail"]
    assert "OQ-426" not in absence["detail"]


def test_a_disconnect_case_with_no_series_reports_the_absence_and_never_invents_a_number(
    brazos, marcus, monkeypatch
):
    """The same for `disconnect_cases` (`OQ-427`).

    ⚠ **AMENDED 2026-08-27 — THIS TEST WENT RED WHEN `OQ-427` CLOSED, AND ITS
    RED IS THE PROOF THAT THE SERIES REACHES A REAL CASE.** Verbatim:

        AssertionError: a number was invented where no series exists:
        'DSC-26-0001'
        assert 'DSC-26-0001' is None

    Nothing was invented — provisioning now seeds a `disconnect_case` row, so
    the tenant HAS a series and the branch this case is about is no longer the
    default one. It is reached the same way the transfer's twin above reaches
    it: by DELETING the row, which reproduces a host that was already running
    when the ruling landed and has not been re-seeded with
    `manage.py seed_demo --tenant <subdomain>`. That is a real state, and the
    three things below must all still hold in it — the number is NULL, a REASON
    is served beside it, and the reason names the open question.

    ⚠ **`absence["open_question"]` STILL READS `OQ-427` AND THAT IS DELIBERATE.**
    The question is CLOSED, and this branch is precisely the state of a tenant
    for whom its answer has not arrived yet; pointing the reader at the question
    that explains why the column is empty is more useful than pointing them at
    nothing. Changing it is a product copy decision, not a test edit.
    """
    with tenant_ctx(brazos):
        _forget_series(disconnects.DISCONNECT_CASE_SERIES)
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        payload = disconnects.open_case(marcus, account["id"], as_of=TODAY)

    assert (
        payload["case_no"] is None
    ), f"a number was invented where no series exists: {payload['case_no']!r}"
    absence = payload["case_no_unavailable"]
    assert absence is not None, "an absent case number served no reason at all"
    assert absence["code"] == disconnects.NUMBERING_SERIES_MISSING
    assert absence["series"] == disconnects.DISCONNECT_CASE_SERIES
    assert absence["open_question"] == "OQ-427"
    assert "number series for disconnections has not been set up" in absence["detail"]
    assert "OQ-427" not in absence["detail"]


def test_the_two_reasons_a_disconnect_reference_can_be_empty_are_not_the_same_reason(
    brazos, marcus, monkeypatch
):
    """⚠ **DEF-127's SHAPE, ONE COLUMN OVER, AND IT WOULD HAVE BEEN INVISIBLE.**

    S90 lists two kinds of row with no reference: a real case that is unnumbered
    (`OQ-427`), and §5.8.6's HELD rows, which are on the tab because a PROTECTION
    is in force and **never entered the ladder at all**. Once rendered, one dash
    looks exactly like the other — and they say opposite things. One says *"your
    numbering is not set up"*, the other *"nothing has been opened here"*. A
    clerk who reads the first on a protection row goes looking for a settings
    problem that does not exist.

    ⚠ **THE FIRST VERSION OF THIS TEST READ THE TWO CONSTANTS AND PASSED WHEN
    THE BRANCH WAS BROKEN.** Collapsing both arms of the decision onto
    `CASE_NUMBER_UNAVAILABLE` — the exact defect — left it green, because two
    constants that differ from each other say nothing about which one the row
    builder picks. The branch is now `disconnect_reads.case_reference_absence`,
    a named function precisely so a test can reach it, and this calls it. Same
    lesson as `_make_the_insert_fail` below, found the same way: by breaking the
    thing and watching the guard not notice (DEF-182).

    ⚠ **AMENDED 2026-08-27 — IT WENT RED WHEN `OQ-427` CLOSED, AND THE FIX IS TO
    KEEP ARM (a) REACHABLE RATHER THAN TO DROP IT.** With a `disconnect_case`
    series now seeded into every tenant, `open_case` numbers the case and arm
    (a) — a REAL case with no number — stopped existing on a fresh tenant. It
    still exists on every host provisioned before the ruling, which is exactly
    the population this branch protects, so the series row is deleted first.
    Deleting arm (a) instead would have removed the only guard on a distinction
    a clerk acts on.
    """
    with tenant_ctx(brazos):
        _forget_series(disconnects.DISCONNECT_CASE_SERIES)
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        real_case = disconnects.open_case_for(account["id"])

        # (a) a real case, unnumbered — OQ-427
        unnumbered = disconnect_reads.case_reference_absence(real_case)
        # (b) §5.8.6's HELD rows: on the tab for a protection, no case ever opened
        no_case = disconnect_reads.case_reference_absence(None)
        # (c) and once a number exists, no absence at all
        real_case.case_no = "ZZPROBE-26-0001"
        numbered = disconnect_reads.case_reference_absence(real_case)

    assert unnumbered["code"] == disconnects.NUMBERING_SERIES_MISSING
    assert unnumbered["open_question"] == "OQ-427"
    assert no_case["code"] == "no_case_opened"
    assert no_case["code"] != unnumbered["code"], (
        "the two absences share a code, so a screen cannot tell an unnumbered case "
        "from an account that never had one"
    )
    assert "No disconnection case has been opened" in no_case["detail"]
    # An absence must not describe a settings gap on a row where nothing was
    # opened — the sentence itself, not just the code.
    assert "number series" not in no_case["detail"]
    assert numbered is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE MACHINERY — it works the moment a series exists
# ═══════════════════════════════════════════════════════════════════════════
def test_a_transfer_is_numbered_from_the_series_the_moment_one_exists(brazos, marcus):
    """⚠ **THIS WAS A PROMISE ABOUT THE FUTURE AND IS NOW A FACT ABOUT TODAY,
    AND IT IS KEPT BECAUSE ITS SECOND JOB OUTLIVED ITS FIRST.**

    Written as *"the day OQ-426 closes, THIS is what happens — with no code
    change"*, and that day was 2026-08-27: the catalogue row landed and this
    case passed without a line of `transfers.py` moving, which is exactly what
    the wave D lane's refusal was for.

    Its remaining job is the one the seeded default cannot do: the format here
    is a TENANT-EDITED one (`PROBE_FORMAT`, written through the same row S8
    writes), so this proves the allocator reads the tenant's own row rather than
    `SERIES_DEFAULTS` — BR-TEN-035's editable half. The seeded-default end of it
    is `test_a_new_tenants_first_transfer_renders_its_own_seeded_default` below.
    """
    with tenant_ctx(brazos):
        _seed_series(transfers.TRANSFER_SERIES, next_number=1)
        _customer, account, _unit = _mover(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        stored = transfers.Transfer.objects.get(id=started["id"])
        # ⚠ INSIDE the tenant context: `tenant_today()` reads the tenant's own
        # timezone (BR-TEN-043 — the event's date is an input, and which day it
        # is depends on whose day it is). Outside, it raises AUTH-003.
        expected = core_numbering.render(PROBE_FORMAT, 1, transfers.seams.tenant_today())

    assert started["transfer_no"] is not None
    assert (
        started["transfer_no_unavailable"] is None
    ), "a numbered transfer still served an absence — the screen would draw both"
    # The number is the SERIES', not a string this test built: re-derived through
    # the same `render` the allocator used, from the probe format and counter 1.
    assert started["transfer_no"] == expected
    # And it is ON THE ROW, not merely in the response.
    assert stored.transfer_no == started["transfer_no"]


def test_a_new_tenants_first_transfer_renders_its_own_seeded_default(brazos, marcus):
    """END TO END, WITH NOTHING SEEDED BY THE TEST — the case `OQ-426` closes.

    A provisioned tenant already holds a `transfer` row at `TRF-{YY}-{0000}`
    (`_seed_number_series` derives it from `SERIES_CATALOG`), so this starts a
    transfer and reads what comes back. The expected value is RE-DERIVED through
    the product's own `render` from the tenant's stored format rather than typed
    as a literal — a literal here would be DEF-615 again, a test and a catalogue
    each picking one. The literal `TRF-26-0001` is asserted exactly once, in
    `test_the_first_transfer_on_a_new_tenant_is_trf_26_0001` above.
    """
    with tenant_ctx(brazos):
        _customer, account, _unit = _mover(marcus, brazos)
        row = tenancy_models.NumberSeries.objects.get(
            tenant_id=_current_tenant_id(), series=transfers.TRANSFER_SERIES
        )
        assert row.format == tenancy_services.SERIES_DEFAULTS[core_numbering.TRANSFER]
        counter = row.next_number
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        expected = core_numbering.render(row.format, counter, transfers.seams.tenant_today())

    assert started["transfer_no"] == expected
    assert started["transfer_no_unavailable"] is None
    assert started["transfer_no"].startswith("TRF-")


def test_a_disconnect_case_is_numbered_from_the_series_the_moment_one_exists(
    brazos, marcus, monkeypatch
):
    """The same, for `OQ-427`."""
    with tenant_ctx(brazos):
        _seed_series(disconnects.DISCONNECT_CASE_SERIES, next_number=1)
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        payload = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        stored = disconnects.open_case_for(account["id"])
        expected = core_numbering.render(PROBE_FORMAT, 1, disconnects.seams.tenant_today())

    assert payload["case_no"] is not None
    assert payload["case_no_unavailable"] is None
    assert payload["case_no"] == expected
    assert stored.case_no == payload["case_no"]


def test_a_new_tenants_first_disconnect_case_renders_its_own_seeded_default(
    brazos, marcus, monkeypatch
):
    """END TO END, WITH NOTHING SEEDED BY THE TEST — the case `OQ-427` closes.

    The twin of `test_a_new_tenants_first_transfer_renders_its_own_seeded_default`
    and written for the same reason: the test above it seeds a PROBE format, so
    it proves the WIRING and says nothing about what a real tenant gets. A
    provisioned tenant now holds a `disconnect_case` row at `DSC-{YY}-{0000}`
    because `_seed_number_series` derives every row from `SERIES_CATALOG`.

    The expected value is RE-DERIVED through the product's own `render` from the
    tenant's stored format rather than typed as a literal — a literal here would
    be DEF-615 again, a test and a catalogue each picking one. `DSC-26-0001` is
    asserted exactly once, in
    `test_the_first_disconnect_case_on_a_new_tenant_is_dsc_26_0001` above.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        row = tenancy_models.NumberSeries.objects.get(
            tenant_id=_current_tenant_id(), series=disconnects.DISCONNECT_CASE_SERIES
        )
        assert row.format == tenancy_services.SERIES_DEFAULTS[core_numbering.DISCONNECT_CASE]
        counter = row.next_number
        payload = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        expected = core_numbering.render(row.format, counter, disconnects.seams.tenant_today())

    assert payload["case_no"] == expected
    assert payload["case_no_unavailable"] is None
    assert payload["case_no"].startswith("DSC-")


def test_two_transfers_get_two_different_numbers_and_the_counter_moves_forward(brazos, marcus):
    """BR-TEN-035: forward-only, never reused.

    Kept separate from the case above because that one allocates exactly once,
    which would pass identically if the allocator returned a constant.
    """
    with tenant_ctx(brazos):
        _seed_series(transfers.TRANSFER_SERIES, next_number=1)
        _c1, first_account, _u1 = _mover(marcus, brazos, label="18 Marten Row")
        _c2, second_account, _u2 = _mover(
            marcus, brazos, label="3 Kestrel Close", name="Haddad, Nour"
        )
        first = transfers.start_transfer(marcus, {"from_account_id": str(first_account.id)})
        second = transfers.start_transfer(marcus, {"from_account_id": str(second_account.id)})

    assert first["transfer_no"] != second["transfer_no"]
    assert first["transfer_no"].endswith("-0001")
    assert second["transfer_no"].endswith("-0002")


# ═══════════════════════════════════════════════════════════════════════════
# 3 · IN THE TRANSACTION — the rule that makes the number trustworthy
# ═══════════════════════════════════════════════════════════════════════════
def _counter(series: str) -> int:
    return tenancy_models.NumberSeries.objects.get(
        tenant_id=_current_tenant_id(), series=series
    ).next_number


class Boom(RuntimeError):
    """The INSERT itself failing — a unique-index clash, a constraint, a
    connection dropping between two statements."""


def _make_the_insert_fail(monkeypatch, model) -> None:
    """Make `model.objects.create(...)` raise, and nothing before it.

    ⚠ **THIS IS THE ONLY SHAPE THAT CAN TELL THE TWO WORLDS APART, AND THE FIRST
    VERSION OF THESE TWO TESTS COULD NOT.** That version wrapped the call in an
    `atomic()` of its own and raised AFTER it returned. Both worlds pass it: the
    outer block rolls back to ITS savepoint and takes the counter with it
    whether the allocation happened inside the writer's transaction or outside
    it. It was written, run against the mutation, and **passed** — a check whose
    output cannot distinguish pass from fail is worse than no check, because it
    is trusted (DEF-182's lesson, one file over).

    What separates them is the WRITE failing while the ALLOCATION stands. With
    the allocation inside the writer's `atomic()`, the two unwind together. With
    it outside, the counter has moved in the enclosing transaction and survives
    the writer's rollback — a number issued to a record that does not exist.
    """

    def boom(*_args, **_kwargs):
        raise Boom("the row could not be written")

    monkeypatch.setattr(model.objects, "create", boom)


def test_a_transfer_that_fails_to_write_leaves_the_counter_where_it_was(
    brazos, marcus, monkeypatch
):
    """BR-TEN-035 allocates INSIDE the issuing transaction, and this is what that
    buys.

    A `start_transfer` whose INSERT fails must leave **no number issued and no
    counter advanced**. Otherwise the tenant's next transfer is `…-0701` with no
    `…-0700` anywhere — which BR-TEN-035 tolerates as a gap in general, and which
    here would be a gap caused by nothing at all, on a counter two concurrent
    starts could also have read together.
    """
    with tenant_ctx(brazos):
        _seed_series(transfers.TRANSFER_SERIES, next_number=700)
        _customer, account, _unit = _mover(marcus, brazos)
        before = _counter(transfers.TRANSFER_SERIES)

        _make_the_insert_fail(monkeypatch, transfers.Transfer)
        with pytest.raises(Boom):
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        after = _counter(transfers.TRANSFER_SERIES)
        rows = transfers.Transfer.objects.filter(from_account_id=account.id).count()

    assert rows == 0, "the transfer survived a rolled-back transaction"
    assert (
        after == before
    ), f"the counter moved although the transfer was never written: {before} → {after}"


def test_a_case_that_fails_to_write_leaves_the_counter_where_it_was(brazos, marcus, monkeypatch):
    """The same for `open_case`, whose `atomic()` was ADDED by this lane.

    Before task 16 that create was a bare autocommit statement. Adding an
    allocation beside it without a transaction would have burnt a number on
    every failed insert, which is precisely what this asserts cannot happen.
    """
    with tenant_ctx(brazos):
        _seed_series(disconnects.DISCONNECT_CASE_SERIES, next_number=700)
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        before = _counter(disconnects.DISCONNECT_CASE_SERIES)

        _make_the_insert_fail(monkeypatch, disconnects.DisconnectCase)
        with pytest.raises(Boom):
            disconnects.open_case(marcus, account["id"], as_of=TODAY)

        after = _counter(disconnects.DISCONNECT_CASE_SERIES)
        rows = disconnects.DisconnectCase.objects.filter(account_id=account["id"]).count()

    assert rows == 0, "the case survived a rolled-back transaction"
    assert (
        after == before
    ), f"the counter moved although the case was never written: {before} → {after}"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE SCREENS CAN SEE IT (r11 step 2b's backing half)
# ═══════════════════════════════════════════════════════════════════════════
def test_both_worklists_publish_a_reference_column_ahead_of_the_drawn_eight():
    """A number a clerk cannot SEE is not a number.

    B18 §5.7.2 and §5.8.2 each draw eight columns and neither draws a reference;
    CR-039 finding 5 is that a clerk cannot quote one. The ninth column leads on
    both lists and both writers publish it as DATA, so the screen and the
    payload cannot disagree about which cells exist — the same reason
    `transfers.STEPS` is a tuple rather than a docstring.

    ⚠ **FIVE PLACES PIN THESE TWO LISTS BY HAND AND ALL FIVE HAD TO MOVE FOR
    ONE COLUMN** — `transfer_reads.COLUMNS`, `disconnect_reads.COLUMNS`, the two
    `columns[]` configs in `TransfersTab.tsx` / `DisconnectsTab.tsx`, and
    `tests/test_w7_worklists.py`'s two literal assertions, which went RED and
    were the only thing that said so. DEF-807's lesson on a different list:
    **when you touch one, ask what else asserts the same fact.** This case is
    the sixth and is deliberately the cheap one — it reads the tuples rather
    than restating them, so it can never be the place that goes stale.
    """
    assert transfer_reads.COLUMNS[0] == "reference"
    assert disconnect_reads.COLUMNS[0] == "reference"
    # The design's own eight, unchanged and in order, after it.
    assert transfer_reads.COLUMNS[1:] == (
        "from_account",
        "customer",
        "from_to",
        "out_date",
        "in_date",
        "step",
        "money",
        "state",
    )
    assert disconnect_reads.COLUMNS[1:] == (
        "account",
        "customer",
        "address",
        "owed",
        "tier",
        "cut_date",
        "last_notice",
        "state",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave D tasks 15/16 (12-governance/11-change-requests.md) ·
#         OQ-426 · OQ-427 · B18 §5.7 · §5.8 · BR-TEN-035 · BR-TEN-043.
#         ⚠ G1 wants `US-XXX-###@<hex>` and no story owns a CR wave task —
#         DEF-810 records that the packet grammar has no form for CR-driven
#         work and that 277 files are in this position.
# generated: 2026-08-27 by the CR-039 wave D tasks 15/16 lane
# checklist: A✔ B✔ C✔ D=n/a(no new route) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case above proved RED first with its failure quoted in the module
#         docstring (hard-won law 7) · ruff ✔ · black --check ✔
# exceptions: **NO PREFIX IS ASSERTED ANYWHERE IN THIS FILE**, deliberately —
#         see the docstring's closing section. `PROBE_FORMAT` is a shape no
#         catalogue could seed, for exactly that reason.
#         `test_no_transfer_or_disconnect_series_is_in_the_catalogue_and_that_is
#         _deliberate` is DESIGNED to go red when OQ-426/OQ-427 close, and its
#         message is the checklist of the four other places that must move.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
