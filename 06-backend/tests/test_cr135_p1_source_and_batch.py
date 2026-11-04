# ── Trace ──────────────────────────────────────────────
# Change:   `CR-135-BRC07` `P1.9` — the payments list carries the blueprint's
#           §03 screen 2·1 SOURCE and BATCH columns. `DEF-PAY-6212` (origin was
#           stored and served to nobody) · `DEF-PAY-6213` (the run that made a
#           payment was linked and read by nobody) · `DEF-PAY-6216` (the list
#           read's comment said nothing writes `deposit_batch_id`).
# Story:    US-PAY-004   Screens: S33 · S21's Payments tab
# Rules:    B1 / B2 §2 (a cross-module read goes through a published callable) ·
#           CLAUDE.md hard rule 1 (tenant scoping — set `app.tenant_id` before
#           counting anything) · B14 rule 31 (no database id is the visible
#           value of a field) · `NFR-3` (a paged list costs one page) ·
#           hard-won law 2 (built is not wired)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Hard-won law 2, at the layer between two columns and a screen.

WHAT WAS TRUE BEFORE THIS LANE
==============================
**Both facts were in the database and neither reached a list row.**

  * `payments/0030` landed `origin` with `ck_payments_origin` on 2026-09-22.
    `import_writer.create_payment_from_import` sets it to `import` on every
    imported row and `record_payment` sets it on every other path. **The list
    read did not carry it**, so the blueprint's Source column could not be
    drawn at all (`DEF-PAY-6212`).
  * `import_run_rows.created_record_id` — *"what it made, for rollback"* — has
    named the payment each imported row created since the eighth import target
    landed, and every row carries `run_id`. **`DEF-PAY-6213` was reported as
    "not servable at all", which was false**: it was a READ that was missing,
    not a link that did not exist.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (law 7)
===============================================================
Each case below was first run against the tree as it stood at `5ce210ee6`:

  * `test_a_payment_row_carries_its_source` — `KeyError: 'origin'`.
  * `test_a_payment_row_carries_the_batch_it_belongs_to` — `KeyError:
    'batch_ref'`.
  * `test_metering_publishes_the_run_that_created_a_record` —
    `AttributeError: module 'apps.metering.import_runs' has no attribute
    'created_record_runs'`.
  * `test_the_source_filter_narrows_the_list` — the filter name was not in
    `PAYMENT_FILTERS`, so `parse_list_params` dropped it and the "filtered"
    queryset returned BOTH payments. ⚠ **That is the false pass worth naming:
    an undeclared filter does not raise, it is ignored** (BR-SHL-011), so a
    case asserting only that the request succeeds would have passed over it.
    The assertion is therefore on the COUNT and on WHICH row came back.
  * `test_the_batch_lookup_is_taken_once_for_a_page` — the per-row lookup was
    the only shape there was, so the query count rose with the row count.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.metering import import_runs
from apps.metering import models as metering_models
from apps.payments import bankrec_models, metering_seam, models, selectors
from apps.tenancy import models as tenancy_models
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def _a_payment(brazos, account, *, origin: str | None, amount="100.0000"):
    """A payment row written directly.

    ⚠ **DIRECTLY, AND ON PURPOSE.** The subject here is the READ. Going through
    `record_payment` would drag allocation, the ledger and the audit trail into
    a case about which keys a list row carries, and a failure anywhere in that
    chain would read as a failure of this one.
    """
    return models.Payment.objects.create(
        tenant_id=brazos.id,
        account_id=account.pk,
        amount=Decimal(amount),
        currency="USD",
        status=models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        origin=origin,
        origin_is_derived=False,
    )


def _a_payments_run(brazos, dana, *, run_no: str) -> metering_models.ImportRun:
    return metering_models.ImportRun.objects.create(
        tenant_id=brazos.id,
        target=import_runs.TARGET_PAYMENTS,
        status="loaded",
        run_no=run_no,
        source_kind="file",
    )


def _a_run_row(brazos, run, *, row_no: int, created_record_id):
    return metering_models.ImportRunRow.objects.create(
        tenant_id=brazos.id,
        run=run,
        row_no=row_no,
        raw={},
        mapped={},
        outcome="loaded",
        created_record_id=created_record_id,
    )


def _a_deposit_batch(brazos, *, code: str):
    """One banked batch. `method` is required and its VALUE is irrelevant here
    — the subject is the CODE the list reads off the batch."""
    method, _ = tenancy_models.PaymentMethod.objects.get_or_create(
        tenant_id=brazos.id, code="check", defaults={"name": "Check"}
    )
    return bankrec_models.DepositBatch.objects.create(
        tenant_id=brazos.id,
        code=code,
        method=method,
        deposited_on=POSTED_AT.date(),
        status=bankrec_models.BATCH_IN_TRANSIT,
    )


# ══ DEF-PAY-6212 — THE SOURCE COLUMN ════════════════════════════════════════


def test_a_payment_row_carries_its_source(brazos, dana):
    """The stored word travels; the LABEL is the screen's (B14 rule 31)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1001")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["origin"] == "import"


def test_a_source_that_was_never_observed_is_served_null(brazos, dana):
    """⚠ **NOT GUESSED INTO ONE OF THE THREE.** A row written before
    `payments/0029` has no observed origin, and *"this was keyed at a counter"*
    is a different statement from *"nobody recorded where this came from"*."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1002")
        payment = _a_payment(brazos, account, origin=None)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["origin"] is None


def test_the_source_filter_narrows_the_list(brazos, dana):
    """§03 2·1 ② — and the false pass this case is shaped around.

    ⚠ **AN UNDECLARED FILTER IS IGNORED, NOT REFUSED** (BR-SHL-011: a list URL
    never 4xxs over its params). So asserting that the request succeeds proves
    nothing at all — the assertion has to be on the COUNT and on WHICH row came
    back, or the case passes just as happily with `origin` missing from
    `PAYMENT_FILTERS` entirely.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1003")
        imported = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_ENTRY)

        params = selectors.list_params({"f.origin": "import"})
        assert "origin" in params.filters, "the filter was dropped as undeclared"

        rows = list(selectors.payment_list_queryset(params))

        assert [str(one.pk) for one in rows] == [str(imported.pk)]


def test_an_origin_no_payment_holds_matches_nothing_and_does_not_raise(brazos, dana):
    """A word outside the CHECK cannot be stored, so it can only ever match
    nothing — and a list URL never errors over its params."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1004")
        _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_ENTRY)

        params = selectors.list_params({"f.origin": "lockbox"})

        assert list(selectors.payment_list_queryset(params)) == []


# ══ DEF-PAY-6213 — THE RUN THAT MADE IT ═════════════════════════════════════


def test_metering_publishes_the_run_that_created_a_record(brazos, dana):
    """The published read itself, asked for the payments target by name."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1005")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        run = _a_payments_run(brazos, dana, run_no="IMP-2609-0007")
        _a_run_row(brazos, run, row_no=1, created_record_id=payment.pk)

        answer = import_runs.created_record_runs(
            import_runs.TARGET_PAYMENTS, [str(payment.pk)]
        )

        assert answer[str(payment.pk)]["run_no"] == "IMP-2609-0007"
        assert answer[str(payment.pk)]["run_id"] == str(run.pk)


def test_a_run_of_another_target_does_not_answer_for_a_payment(brazos, dana):
    """⚠ **`target` IS NOT DECORATION.** `created_record_id` is a bare uuid
    column shared by every target, so a read that did not ask for one would be
    a statement about whatever happened to match."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1006")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        premises_run = metering_models.ImportRun.objects.create(
            tenant_id=brazos.id,
            target="premises",
            status="loaded",
            run_no="IMP-2609-0008",
            source_kind="file",
        )
        _a_run_row(brazos, premises_run, row_no=1, created_record_id=payment.pk)

        answer = import_runs.created_record_runs(
            import_runs.TARGET_PAYMENTS, [str(payment.pk)]
        )

        assert answer == {}


def _a_bare_tenant(subdomain: str):
    """A tenant ROW and nothing else — no services, no series, no sample data.

    ⚠ **NOT THE `lonestar` ISOLATION FIXTURE, AND THE REASON IS MEASURED.**
    `lonestar` provisions a whole second utility; with it, this file went from
    23 seconds to over 900 and was killed by its own timeout. The subject here
    is ONE `WHERE tenant_id = …` on a metering read, and a bare row exercises
    that filter exactly as a provisioned utility would — the filter cannot tell
    the two apart. A fixture heavier than its question is how a suite stops
    being run at all.
    """
    return tenancy_models.Tenant.objects.create(name=subdomain, subdomain=subdomain)


def test_another_tenants_run_does_not_answer_for_our_payment(brazos, dana):
    """⚠ **HARD RULE 1, ON A READ THAT CROSSES A MODULE BOUNDARY.**

    This case exists because of law 7's second habit — *ask what would make this
    check pass wrongly*. Every other case in this file asks one tenant about its
    own rows, so **all of them pass just as happily with the tenant filter
    deleted**, and `created_record_runs` is a brand-new published read that
    another module calls. On PostgreSQL RLS is the second guarantee; on the
    SQLite tier the suite runs on there are no policies at all, so the app-level
    filter is the ONLY thing standing here and it is the thing asserted.

    **RED PROOF:** with `tenant_id=_tenant_id()` removed from
    `import_runs.created_record_runs`, this reports
    `AssertionError: another tenant's run answered for our payment`.
    """
    lonestar = _a_bare_tenant("lonestarridge-isolation")

    with tenant_ctx(lonestar):
        their_run = metering_models.ImportRun.objects.create(
            tenant_id=lonestar.id,
            target=import_runs.TARGET_PAYMENTS,
            status="loaded",
            run_no="IMP-2609-9999",
            source_kind="file",
        )

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1013")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)

    # Their row claims OUR payment — the shape a shared `created_record_id`
    # column makes possible, and exactly what the tenant filter must refuse.
    with tenant_ctx(lonestar):
        metering_models.ImportRunRow.objects.create(
            tenant_id=lonestar.id,
            run=their_run,
            row_no=1,
            raw={},
            mapped={},
            outcome="loaded",
            created_record_id=payment.pk,
        )

    with tenant_ctx(brazos):
        answer = import_runs.created_record_runs(
            import_runs.TARGET_PAYMENTS, [str(payment.pk)]
        )
        assert answer == {}, "another tenant's run answered for our payment"

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))
        assert row["batch_ref"] is None


def test_the_seam_answers_the_same_thing(brazos, dana):
    """Payments asks through its own seam and never through metering's ORM."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1007")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        run = _a_payments_run(brazos, dana, run_no="IMP-2609-0009")
        _a_run_row(brazos, run, row_no=1, created_record_id=payment.pk)

        answer = metering_seam.runs_that_created([payment.pk])

        assert answer[str(payment.pk)]["run_no"] == "IMP-2609-0009"


def test_a_payment_row_carries_the_batch_it_belongs_to(brazos, dana):
    """An imported payment reads as its RUN's number."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1008")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        run = _a_payments_run(brazos, dana, run_no="IMP-2609-0010")
        _a_run_row(brazos, run, row_no=1, created_record_id=payment.pk)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["batch_ref"] == "IMP-2609-0010"
        assert row["batch_kind"] == selectors.BATCH_KIND_IMPORT


def test_a_payment_in_no_batch_says_so_rather_than_naming_one(brazos, dana):
    """⚠ **THE DRAWING'S OWN GAP NOTE ⑦.** A card taken and not yet settled
    belongs to no batch, because there is no settlement run in the product."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1009")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_WEBHOOK)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["batch_ref"] is None
        assert row["batch_kind"] is None


# ══ DEF-PAY-6216 — THE DEPOSIT BATCH, AS A CODE AND NEVER AS A UUID ═════════


def test_a_banked_payment_reads_as_its_deposit_code(brazos, dana):
    """`reconciliation.cut_deposit_batches` has stamped `deposit_batch_id`
    since bank rec shipped; the list read's comment said nothing wrote it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1010")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_ENTRY)
        batch = _a_deposit_batch(brazos, code="DEP-260922-0001")
        models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=batch.pk)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["batch_ref"] == "DEP-260922-0001"
        assert row["batch_kind"] == selectors.BATCH_KIND_DEPOSIT
        # B14 rule 31: the id is not what a clerk reads. ⛔ AMENDED 2026-10-19
        # (record links, PO ruling): it read *"and it is not served"* and
        # asserted the uuid appeared nowhere in the row. The code now OPENS the
        # batch, and the batch page's address is its id — so the id travels in
        # exactly ONE key, `batch_id`, an address ingredient the screen never
        # prints (`PaymentsPage` batch cell, `recordLinksJobB.dom.test.tsx`).
        assert row["deposit_batch_id"] is None
        assert row["batch_id"] == str(batch.pk)
        assert str(batch.pk) not in str({k: v for k, v in row.items() if k != "batch_id"})


def test_a_banked_import_reads_as_its_deposit_and_not_as_its_run(brazos, dana):
    """⚠ **THE LATER, MORE SPECIFIC FACT WINS.** An imported cheque that has
    since been banked is in both populations, and the deposit is the one a
    bookkeeper is holding a bank statement against."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1011")
        payment = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        run = _a_payments_run(brazos, dana, run_no="IMP-2609-0011")
        _a_run_row(brazos, run, row_no=1, created_record_id=payment.pk)
        batch = _a_deposit_batch(brazos, code="DEP-260922-0002")
        models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=batch.pk)

        row = selectors.payment_row(models.Payment.objects.get(pk=payment.pk))

        assert row["batch_ref"] == "DEP-260922-0002"
        assert row["batch_kind"] == selectors.BATCH_KIND_DEPOSIT


# ══ NFR-3 — A PAGE COSTS A PAGE ═════════════════════════════════════════════


def test_the_batch_lookup_is_taken_once_for_a_page(brazos, dana, django_assert_num_queries):
    """⚠ **THE WHOLE POINT OF `payment_rows`.** `payment_row` looks a single
    row's batch up when nothing is passed, which is correct and is two queries;
    a 50-row page doing that is 100 queries on a list that pages in SQL
    precisely so that one page costs one page.

    Asserted as *the same count for two rows as for one*, rather than against a
    fixed number: a fixed number would go red the next time an unrelated
    `select_related` moved, and would then be edited rather than read.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AC-1012")
        run = _a_payments_run(brazos, dana, run_no="IMP-2609-0012")
        first = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        _a_run_row(brazos, run, row_no=1, created_record_id=first.pk)

        one = _count_queries(lambda: selectors.payment_batch_labels([first]))

        second = _a_payment(brazos, account, origin=models.PAYMENT_ORIGIN_IMPORT)
        _a_run_row(brazos, run, row_no=2, created_record_id=second.pk)

        two = _count_queries(lambda: selectors.payment_batch_labels([first, second]))

        assert two == one, f"the lookup grew with the page: {one} → {two}"


def _count_queries(fn) -> int:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        fn()
    return len(captured)


def test_an_empty_page_asks_nothing_at_all():
    """A list with no rows must not reach across the module boundary."""
    assert selectors.payment_batch_labels([]) == {}
    assert metering_seam.runs_that_created([]) == {}
    assert import_runs.created_record_runs(import_runs.TARGET_PAYMENTS, []) == {}


def test_the_seam_names_its_neighbour_so_the_boundary_is_greppable():
    """B2 §2 — resolved by NAME, so nothing binds the two modules at import."""
    assert metering_seam.METERING_MODULE == "apps.metering.import_runs"
    assert metering_seam.CREATED_RECORD_RUNS_READ == "created_record_runs"
    assert metering_seam.PAYMENTS_TARGET == import_runs.TARGET_PAYMENTS


def test_a_metering_that_publishes_nothing_answers_no_runs(monkeypatch):
    """⚠ **AND IT DOES NOT REFUSE, WHICH IS THE `_customer_name` POSTURE
    DELIBERATELY NOT TAKEN.** A name that cannot be read and a customer with no
    contact are different statements about a customer; a payment with no run
    and a run that cannot be looked up are the same statement on screen —
    *no batch* — and the batch id is not a fact the money depends on.
    """
    monkeypatch.setattr(metering_seam, "_read", lambda: None)

    assert metering_seam.runs_that_created([uuid.uuid4()]) == {}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-135-BRC07 `P1.9` · `DEF-PAY-6212` · `DEF-PAY-6213` · `DEF-PAY-6216`
#         · payments blueprint §03 screen 2·1
# generated: 2026-09-23 by lane ONEPATH
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: the SCREEN half of these columns is asserted in
#             `07-frontend/src/features/payments/bulkActions.test.tsx`, where
#             the cells live; no gate in this repo reads rendered output, so
#             neither file is a substitute for looking at the screen (law 6).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
