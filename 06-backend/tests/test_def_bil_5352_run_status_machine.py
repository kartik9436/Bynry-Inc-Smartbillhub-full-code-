# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5352 — a bill run's status never advances. A run that had
#          issued 1,251 bills still read `draft`, and the three words the
#          blueprint draws (Issued · Corrected · Abandoned) existed nowhere.
# Rule:    BR-BIL-1045 (the five-word vocabulary and its transitions, decided
#          2026-09-15 from blueprint p146 — B14 rule 41, the drawing is the
#          agreement; law 13, a judgment recorded is the deliverable)
# Also:    BR-TEN-043 (event time is an argument, never a clock) ·
#          BR-MET-132 (a run CONSUMES a cycle period) · BR-LED-006 (the
#          month-end close's *"every run finished"* item) · CLAUDE.md hard
#          rule 4 (an issued bill is immutable — nothing here moves one)
# ───────────────────────────────────────────────────────
"""The run status machine, and the two dead vocabularies it replaces.

**WHAT WAS WRONG, MEASURED.** `bill_runs.status` had two writers and both wrote
at CREATION — `runs.create_run` wrote `"draft"`, `corrections` wrote `"issuing"`
for a rebill run — and nothing ever advanced either. On the demo tenant on
2026-09-15 that was 2 rows `draft`, 1 `issuing`, and one of those drafts had
issued 1,251 bills. Nothing could see it, because the column was stored and
served correctly; it took a screen drawing the word to reveal that every
finished run in the product's history read *Draft*.

**THE PART NOBODY WAS LOOKING FOR, AND IT IS WHY SECTION 4 BELOW EXISTS.** Two
selector constants already named a vocabulary in prose and **no writer had ever
written a word of it**:

  * `SETTLED_RUN_STATUSES = {"completed", "cancelled"}` — `unissued_run_count`
    EXCLUDES this set, so every run in every window counted as unfinished, on
    every tenant, for ever. The ledger's month-end *"every run finished"* item
    could never go green.
  * `RUN_STATUSES_THAT_CONSUME_A_PERIOD = {"completed"}` — matched no row, so
    `BR-MET-132`'s chase-days chip never dropped a period a bill run had billed.

Both were correct-looking, both were commented at length, and both were dead.
**A constant is a claim about what some writer writes, and nothing re-checks
it** — so the cases in section 4 compare the two sets against the words the
writer actually writes, which is a check that goes red the day they drift again.

**HOW EACH CASE WAS PROVED RED.** Every one was run against the code as it stood
before `record_run_outcome` existed; the failures are quoted in the lane's
conformance record. The shortest of them is the whole defect:
`AssertionError: assert 'draft' == 'issued'`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.billing import models as billing_models
from apps.billing import release
from apps.billing import runs as billing_runs
from apps.billing import selectors as billing_selectors

from tests.test_us_bil_005_issue import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    electric_gl_accounts,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — every moment here is NAMED. Nothing reads a clock, and gate G6
#: forbids one in this app at all.
CONFIRMED_AT = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)
RELEASED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)

ALL_FIVE = release.Confirmations(
    compliance=True, email_mandate=True, sms_mandate=True, autopay_mandate=True, final=True
)


# ── the world, in the shape a run actually happens ──────────────────────────
def a_releasable_run(tenant, dana, *, accounts=2, key="2026-06|cycle-1"):
    """A bill run carrying `accounts` priced drafts that `issue_run` can issue."""
    electric_gl_accounts()  # the seeded chart splits 4100/4105
    run = a_run(tenant, key=key)
    for index in range(accounts):
        account = an_account(dana, tenant, account_no=f"A-5200{index}")
        a_priced_draft(tenant, account, run, invoice_no=f"BL-2607-00020{index}")
    return run


def authorise(run, dana):
    """Phase 4 — the release gate, all five confirmations recorded."""
    return release.authorise_release(
        bill_run=run,
        summary=release.summary_for(run),
        confirmations=ALL_FIVE,
        confirmed_by=dana.user,
        confirmed_at=CONFIRMED_AT,
    )


def release_the_run(run, row, dana):
    """Phase 5 — the point a bill run finishes, and the one place the status
    word is written for a cycle run."""
    return release.release_run(
        bill_run=run,
        release_row=row,
        released_at=RELEASED_AT,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana.user,
    )


def reread(run):
    """The row as the database holds it — never the in-memory instance.

    A test that asserts on the object the service handed back can pass over a
    service that assigned the attribute and never saved it, which is precisely
    the false pass this file exists to prevent.
    """
    return billing_models.BillRun.objects.get(pk=run.pk)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT ITSELF — a finished run must not read Draft
# ═══════════════════════════════════════════════════════════════════════════
def test_5352_1__a_run_that_issued_its_bills_reads_issued(brazos, dana):
    """RED before `record_run_outcome`: `assert 'draft' == 'issued'`.

    The blueprint's own row: `BR-2609-0051` · 1,251 bills · **Issued**.
    """
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=2)
        assert run.status == billing_runs.RUN_STATUS_DRAFT  # where every run starts
        release_the_run(run, authorise(run, dana), dana)
        after = reread(run)

    assert after.status == billing_runs.RUN_STATUS_ISSUED
    assert after.status == "issued"  # the literal, so a rename of the constant shows


def test_5352_1__the_word_is_written_to_the_database_and_not_just_returned(brazos, dana):
    """The status the read serves is the STORED one, so the row a clerk opens
    tomorrow says what today's run did."""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|stored")
        release_the_run(run, authorise(run, dana), dana)
        served = [
            row
            for row in billing_selectors.bill_runs_list()
            if row["id"] == str(run.pk)
        ]

    assert served and served[0]["status"] == "issued"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · ABANDONED — drawn at zero, and it must not un-terminate
# ═══════════════════════════════════════════════════════════════════════════
def test_5352_2__a_run_that_issued_nothing_and_has_nothing_left_is_abandoned(brazos, dana):
    """The blueprint's note: *"BR-2607-0030 issued nothing and is still a row.
    A run that vanished would leave a clerk unable to explain a gap in the
    numbering to an auditor."*

    Nothing went out and nothing is waiting to go out.
    """
    assert billing_runs.run_status_from_evidence(issued=0, drafts=0) == "abandoned"


def test_5352_2__a_run_with_drafts_left_is_issuing_and_never_abandoned(brazos, dana):
    """⚠ **THE OBVIOUS READING OF *"issued nothing"* IS A TRAP AND THIS IS THE
    CASE THAT HOLDS THE DOOR SHUT.**

    Reading it as *the issue pass ended with no bills* would mark a run whose
    accounts all broke as Abandoned — and then a clerk clears the break list,
    issues again, and a TERMINAL word flips back to Issued. A terminal word that
    un-terminates is worse than no word at all: a clerk who watched a run leave
    Abandoned would rightly stop trusting the column.
    """
    assert billing_runs.run_status_from_evidence(issued=0, drafts=18) == "issuing"


def test_5352_2__an_issued_run_is_issued_whatever_else_it_holds(brazos, dana):
    """Money that has left the building outranks everything. A run that issued
    499 and broke on one is ISSUED, not issuing — BR-BIL-055 says a break never
    blocks a release, and the word has to agree with the rule."""
    assert billing_runs.run_status_from_evidence(issued=499, drafts=1) == "issued"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · CORRECTED — the word the correction workflow sets, and it never regresses
# ═══════════════════════════════════════════════════════════════════════════
def test_5352_3__a_correction_marks_the_run_it_restated(brazos, dana):
    """Blueprint p146: *"Run 08-B reads Corrected because §06 screen 26.5
    restated its 412 water bills … this is the only screen where a clerk can see
    that a whole run was redone."*"""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|corrected")
        release_the_run(run, authorise(run, dana), dana)
        assert reread(run).status == "issued"
        billing_runs.mark_run_corrected(reread(run))
        after = reread(run)

    assert after.status == billing_runs.RUN_STATUS_CORRECTED


def test_5352_3__corrected_never_goes_back_to_issued(brazos, dana):
    """⚠ **THE ONE TRANSITION THAT WOULD TELL A CLERK SOMETHING FALSE.** A run
    reading Corrected and then reading Issued again says the restatement was
    undone, and hard rule 4 is that nothing undoes an issued bill.

    So `record_run_outcome` is a no-op on a corrected run — proved here by
    calling it on one that has every reason to read `issued`.
    """
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|noregress")
        release_the_run(run, authorise(run, dana), dana)
        billing_runs.mark_run_corrected(reread(run))
        # Every piece of evidence now says `issued`. The word must not move.
        billing_runs.record_run_outcome(reread(run))
        after = reread(run)

    assert after.status == billing_runs.RUN_STATUS_CORRECTED


def test_5352_3__a_draft_run_is_not_jumped_forward_to_corrected(brazos, dana):
    """There is nothing to restate on a run that never issued, so the caller is
    not made to care and the word is left where it is."""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|nodraftjump")
        billing_runs.mark_run_corrected(run)
        after = reread(run)

    assert after.status == billing_runs.RUN_STATUS_DRAFT


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE TWO DEAD VOCABULARIES — the check that goes red when they drift again
# ═══════════════════════════════════════════════════════════════════════════
def test_5352_4__every_settled_word_is_a_word_this_module_actually_writes():
    """⚠ **THIS IS THE CASE THAT WOULD HAVE CAUGHT THE ORIGINAL BUG, AND IT IS
    THE ONLY SHAPE THAT COULD HAVE.**

    `SETTLED_RUN_STATUSES` was `{"completed", "cancelled"}` — two words no writer
    in this product has ever written — and every check in the repository passed
    over it, because a frozenset of strings is valid whatever is in it. Nothing
    compared the CONSUMER's vocabulary against the WRITER's.

    A future lane adding a sixth word to `RUN_STATUSES` without deciding whether
    it settles a run now has to come here and say so.
    """
    assert billing_selectors.SETTLED_RUN_STATUSES <= set(billing_runs.RUN_STATUSES)
    assert billing_selectors.RUN_STATUSES_THAT_CONSUME_A_PERIOD <= set(billing_runs.RUN_STATUSES)


def test_5352_4__the_in_flight_words_are_exactly_the_ones_not_settled():
    """`draft` and `issuing` are in flight; the other three are terminal. Stated
    as a partition rather than as two lists, so the two cannot drift apart."""
    in_flight = set(billing_runs.RUN_STATUSES) - billing_selectors.SETTLED_RUN_STATUSES
    assert in_flight == {"draft", "issuing"}


def test_5352_4__a_finished_run_stops_counting_as_unfinished(brazos, dana):
    """`BR-LED-006` — the month-end close's *"every run finished"* item.

    ⚠ **IT COULD NEVER GO GREEN ON ANY TENANT**: `unissued_run_count` excludes
    `SETTLED_RUN_STATUSES`, which named two words nothing wrote, so every run in
    every window counted as unfinished for ever. The 2026-09-07 row that
    published this seam measured the symptom — three runs reading
    `draft · issuing · draft` — and read it as the seam being unpublished.
    """
    from datetime import date

    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|close")
        window = (date(2026, 6, 1), date(2026, 6, 30))
        before = billing_selectors.unissued_run_count(*window)
        release_the_run(run, authorise(run, dana), dana)
        after = billing_selectors.unissued_run_count(*window)

    assert before == 1, "a draft run is unfinished, which was always right"
    assert after == 0, "and an issued one is finished, which was never reachable"


def test_5352_4__an_issued_run_consumes_its_cycle_period(brazos, dana):
    """`BR-MET-132` — *"Keep counting until the run consumes the period"*. The
    chase-days chip dropped a period only for a status nothing wrote, so it
    counted unread meters for periods that had already gone out on a bill."""
    from datetime import date

    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|consume")
        before = billing_selectors.period_consumed_by_run(
            run.cycle_id, date(2026, 6, 1), date(2026, 6, 30)
        )
        release_the_run(run, authorise(run, dana), dana)
        after = billing_selectors.period_consumed_by_run(
            run.cycle_id, date(2026, 6, 1), date(2026, 6, 30)
        )

    assert before is False
    assert after is True


# ═══════════════════════════════════════════════════════════════════════════
# 4b · THE BACK-FILL — because the writer fixes no run already in the database
# ═══════════════════════════════════════════════════════════════════════════
def _backfill_module():
    """`billing/0029`, imported by path — a migration module is not a package
    member and cannot be imported by name."""
    import importlib.util
    import pathlib as _pathlib

    path = (
        _pathlib.Path(__file__).resolve().parents[1]
        / "apps/billing/migrations/0029_br_bil_1045_backfill_run_status.py"
    )
    spec = importlib.util.spec_from_file_location("billing_0029", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_5352_4b__the_backfill_gives_a_run_that_already_issued_the_word_issued(brazos, dana):
    """⚠ **THE WRITER ALONE WOULD HAVE LEFT THE DEFECT ON SCREEN.** Measured on
    the demo tenant with `release_run` advancing correctly and before this
    migration ran: `RUN-0002` had issued **39 bills worth $15,453.63** and still
    read `draft`, because it was released long before the writer existed. Those
    are exactly the rows screen 27 is for.
    """
    from django.apps import apps as django_apps

    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=2, key="2026-06|backfill")
        release_the_run(run, authorise(run, dana), dana)
        # Put it back the way history left it: released, with bills out, reading
        # the word its creator wrote.
        billing_models.BillRun.objects.filter(pk=run.pk).update(
            status=billing_runs.RUN_STATUS_DRAFT
        )
        assert reread(run).status == "draft"

        _backfill_module().backfill(django_apps, None)
        after = reread(run)

    assert after.status == billing_runs.RUN_STATUS_ISSUED


def test_5352_4b__the_backfill_never_calls_an_unfinished_run_abandoned(brazos, dana):
    """⚠ **THE FIRST DRAFT OF THE MIGRATION WOULD HAVE STAMPED *Abandoned* ON
    EVERY RUN IN FLIGHT, AND THIS IS THE CASE THAT HOLDS IT SHUT.**

    `BR-BIL-1045` defines `abandoned` as *the run ENDED having issued nothing*,
    and "ended" is an EVENT. A stored row cannot tell a run that ended with
    nothing from a run a clerk created this morning: both are `draft` with no
    bills out. Stamping the second one Abandoned is worse than the defect being
    fixed, because Draft is at least TRUE of a new run.
    """
    from django.apps import apps as django_apps

    with tenant_ctx(brazos):
        fresh = a_run(brazos, key="2026-06|inflight")  # drafts, nothing issued
        empty = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=fresh.cycle,
            period_start=fresh.period_start,
            period_end=fresh.period_end,
            idempotency_key="2026-06|nothing-at-all",
        )
        _backfill_module().backfill(django_apps, None)
        after_fresh = reread(fresh)
        after_empty = reread(empty)

    assert after_fresh.status == "draft"
    assert after_empty.status == "draft"


def test_5352_4b__the_backfill_leaves_a_deliberate_word_alone(brazos, dana):
    """A `corrected` run stays corrected and a rebill run created `issuing` with
    nothing out stays `issuing`. This pass rewrites only the two words a CREATOR
    wrote, and only on the evidence of a locked bill."""
    from django.apps import apps as django_apps

    with tenant_ctx(brazos):
        corrected = a_releasable_run(brazos, dana, accounts=1, key="2026-06|bf-corrected")
        release_the_run(corrected, authorise(corrected, dana), dana)
        billing_runs.mark_run_corrected(reread(corrected))
        rebill = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=corrected.cycle,
            period_start=corrected.period_start,
            period_end=corrected.period_end,
            idempotency_key="2026-06|bf-rebill",
            status=billing_runs.RUN_STATUS_ISSUING,
            bill_type="rebill",
        )
        _backfill_module().backfill(django_apps, None)
        assert reread(corrected).status == billing_runs.RUN_STATUS_CORRECTED
        assert reread(rebill).status == billing_runs.RUN_STATUS_ISSUING


def test_5352_4b__the_reverse_does_not_destroy_a_word_the_forward_pass_never_wrote(
    brazos, dana
):
    """⚠ **THE REVERSE GOT THIS WRONG FIRST AND WOULD HAVE DONE DAMAGE THE
    FORWARD PASS COULD NOT.** A rebill run is CREATED `issuing`; a reverse that
    sent every `issuing` row back to `draft` would erase a word a writer had put
    there before the migration existed."""
    from django.apps import apps as django_apps

    with tenant_ctx(brazos):
        rebill = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_run(brazos, key="2026-06|rev-parent").cycle,
            period_start=CONFIRMED_AT.date(),
            period_end=CONFIRMED_AT.date(),
            idempotency_key="2026-06|rev-rebill",
            status=billing_runs.RUN_STATUS_ISSUING,
            bill_type="rebill",
        )
        _backfill_module().unbackfill(django_apps, None)
        assert reread(rebill).status == billing_runs.RUN_STATUS_ISSUING


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE WRITER'S OWN MANNERS — idempotent, narrow, and it writes no money
# ═══════════════════════════════════════════════════════════════════════════
def test_5352_5__recording_the_outcome_twice_writes_once(brazos, dana):
    """CLAUDE.md rule 6's posture applied to a status: a resumed release, a
    replayed job and a double-click all reach this, and none of them may do
    anything the first call did not."""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|twice")
        release_the_run(run, authorise(run, dana), dana)
        first = reread(run)
        billing_runs.record_run_outcome(reread(run))
        second = reread(run)

    assert first.status == second.status == "issued"
    assert first.updated_at == second.updated_at, "the second call re-saved the row"


def test_5352_5__the_writer_touches_no_other_column(brazos, dana):
    """`update_fields` is exactly `status` and `updated_at`. A status writer that
    saved the whole row would carry any stale attribute the caller happened to
    be holding — which on `bill_runs` includes the idempotency key BR-BIL-005
    depends on."""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|narrow")
        before = reread(run)
        stale = reread(run)
        stale.idempotency_key = "tampered"  # never saved — the writer must ignore it
        stale.label = "tampered"
        billing_runs.record_run_outcome(stale)
        after = reread(run)

    assert after.idempotency_key == before.idempotency_key
    assert after.label == before.label


def test_5352_5__no_issued_bill_moves_when_the_status_does(brazos, dana):
    """Hard rule 4. The status machine writes one column of `bill_runs` and
    nothing on `invoices`, and this asserts it against the bills rather than by
    reading the code."""
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=2, key="2026-06|immutable")
        release_the_run(run, authorise(run, dana), dana)
        bills = {
            str(row["id"]): (row["status"], row["total"], row["issued_at"])
            for row in billing_models.Invoice.objects.filter(
                tenant=brazos, bill_run=run
            ).values("id", "status", "total", "issued_at")
        }
        billing_runs.record_run_outcome(reread(run))
        billing_runs.mark_run_corrected(reread(run))
        after = {
            str(row["id"]): (row["status"], row["total"], row["issued_at"])
            for row in billing_models.Invoice.objects.filter(
                tenant=brazos, bill_run=run
            ).values("id", "status", "total", "issued_at")
        }

    assert bills and bills == after
