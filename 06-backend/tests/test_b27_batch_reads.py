# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B27
#           (changes row 55)
# Defects:  DEF-BIL-8491 (the read-time stamp) · DEF-BIL-8490 (partition range)
# Findings: 04-docs/05-modules/07-billing/19-check-cost-measured.md
# PG proof: 10-scripts/bbr_check_cost.py race / profile / measure
# ───────────────────────────────────────────────────────
"""B27 — each Check batch of 500 reads its data once, and answers exactly what
the per-account reads answered.

Four things are held here, each written to go red on the defect it guards:

  * the batch answer EQUALS the per-account answer on a mixed seed (ready,
    no plan, a disputed read, a missing read, a payment after the cut-off) —
    every finding, every status, every gathered bill;
  * DEF-BIL-8491 — a payment recorded while a batch runs is flagged stale by
    the sweep (the saved result is stamped with the batch's READ time);
  * the memo never answers across tenants and never outlives its batch
    (hard rule 1);
  * DEF-BIL-8490 — the partition-key range selects exactly the rows the
    `__date` lookup selected, at both day boundaries.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pytest

from apps.billing import (
    batch_seams,
    check_engine,
    check_models,
    check_staleness,
    check_store,
    runs,
)
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from core import batch_reads
from core.dbfields import uuid7
from core import tenancy as core_tenancy

from tests.test_bbr_check_categories import a_payment_after_the_cutoff
from tests.test_bbr_check_engine import BILL_DATE, three_accounts
from tests.test_bbr_check_store import a_run, saved_status
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

DUE = date(2026, 7, 22)


def _summary(checked):
    """Everything an account's Check answer carries that a clerk or a bill can
    see — minus a support reference, which is random by design."""
    return (
        checked.account_no,
        checked.check_status(),
        sorted(
            (f.code, f.severity or "", f.service_code or "", f.step or "", repr(f.params))
            for f in checked.findings
        ),
        repr(checked.data),
        checked.plan_id,
        checked.covered_unit_ids,
        checked.quiet,
        checked.unmeasured,
    )


def _prepare(cycle, *, batched, monkeypatch):
    out = {}
    with monkeypatch.context() as patch:
        if not batched:
            # The per-account pass: no memo is ever active and no batch read runs.
            patch.setattr(batch_reads, "active", lambda: None)
            patch.setattr(check_engine, "_load_batch", lambda ctx, accounts: None)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            service_date=BILL_DATE,
            payment_window=(BILL_DATE, DUE),
            on_account=lambda checked: out.__setitem__(checked.account_no, _summary(checked)),
        )
    return out, prepared


def a_mixed_cycle(tenant, actor):
    """Ready accounts, a payment after the cut-off, an account with no plan and
    a disputed read, and one whose meter was never read."""
    cycle, _plan, accounts = three_accounts(tenant, actor)
    a_payment_after_the_cutoff(tenant, accounts["A-00106"])
    premises = make_premises(actor, address_line="105 Bluestem Ln")
    unit = make_unit(actor, premises["id"], label="Unit 105", services=["electric"])
    asset = a_meter(actor, asset_no="M-9105", unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    commit_read(
        actor,
        asset["id"],
        day="2026-06-28",
        value="500",
        prior_value="400",
        consumption="100.000000",
        unit="kWh",
    )
    metering_models.MeterRead.objects.filter(tenant=tenant, asset_id=asset["id"]).update(
        disputed_at=datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc),
        dispute_reason="customer says the meter is wrong",
    )
    an_account(tenant, unit["id"], "A-00105")
    unread = make_unit(actor, premises["id"], label="Unit 107", services=["electric"])
    a_meter(actor, asset_no="M-9107", unit_id=unread["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unread["id"]).update(
        cycle=cycle
    )
    an_account(tenant, unread["id"], "A-00107")
    return cycle


# ══════════════════════════════════════════════════════════════════════════
# The batch answer IS the per-account answer
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_b27__a_batch_answers_exactly_what_each_account_answered_alone(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle = a_mixed_cycle(brazos, dana)
        alone, prepared_alone = _prepare(cycle, batched=False, monkeypatch=monkeypatch)
        together, prepared_together = _prepare(cycle, batched=True, monkeypatch=monkeypatch)
        loaders = dict(batch_seams.LAST)
        counts = batch_reads.last_counts()

    assert sorted(alone) == ["A-00101", "A-00102", "A-00105", "A-00106", "A-00107"]
    # The seed is mixed: not every account comes back the same way.
    assert len({row[1] for row in alone.values()}) >= 2
    assert "paid_after_cutoff" in {f[0] for f in alone["A-00106"][2]}
    assert together == alone
    assert [repr(d) for d in prepared_together.ready] == [repr(d) for d in prepared_alone.ready]
    assert [p.reason for p in prepared_together.blocked] == [
        p.reason for p in prepared_alone.blocked
    ]
    # Every owning module's batch read ran, and primed what it read.
    assert set(loaders.values()) == {"ok"}, loaders
    assert counts["primed"], counts


# BULK-CHG-55
def test_b27__the_batch_reads_each_repeated_question_once(brazos, dana, monkeypatch):
    """The identical-for-everyone reads (a tax row, a rate tier, a charge code)
    are asked once per batch, not once per account."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with tenant_ctx(brazos):
        cycle = a_mixed_cycle(brazos, dana)
        with CaptureQueriesContext(connection) as alone:
            _prepare(cycle, batched=False, monkeypatch=monkeypatch)
        with CaptureQueriesContext(connection) as together:
            _prepare(cycle, batched=True, monkeypatch=monkeypatch)

    assert len(together.captured_queries) < len(alone.captured_queries) / 2, (
        len(together.captured_queries),
        len(alone.captured_queries),
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8491 · a payment recorded mid-batch is flagged stale
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-55
def test_8491__a_payment_recorded_while_the_batch_runs_is_flagged_stale(brazos, dana):
    """`bbr_check_cost.py race`, in the suite: the batch reads payments once,
    before its first account; a $120.00 payment posted after the cut-off lands
    on A-00106 the moment A-00101 is saved. A-00106's saved result cannot know
    it — and the sweep MUST, because the result is stamped with the batch's
    read time, which is before the payment."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        late = accounts["A-00106"]
        fired = []

        def on_progress(done, _account_no):
            if done == 1 and not fired:
                time.sleep(0.01)
                fired.append(a_payment_after_the_cutoff(brazos, late))

        check_store.check_run(run, on_progress=on_progress)
        saved = saved_status(run, late)[1]
        row = check_models.BillRunAccountCheck.objects.get(bill_run=run, account_id=late.id)
        stale = check_staleness.stale_categories(run)
        check_staleness.sweep(run)
        after = saved_status(run, late)[1]

    assert fired, "the payment was never recorded"
    assert "paid_after_cutoff" not in saved  # the batch read before it existed
    assert row.checked_at < fired[0].updated_at  # stamped with the READ time
    assert stale == {str(late.id): frozenset({check_staleness.PAYMENT_CHANGE})}
    assert "paid_after_cutoff" in after


def test_8491__every_result_of_a_batch_carries_the_batch_read_time(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        stamps = set(
            check_models.BillRunAccountCheck.objects.filter(bill_run=run).values_list(
                "checked_at", flat=True
            )
        )
    assert len(stamps) == 1  # one batch, one read time


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 1 · the memo is one tenant's and one batch's
# ══════════════════════════════════════════════════════════════════════════
def test_b27__the_memo_answers_nothing_for_another_tenant_and_dies_with_the_batch(brazos, lonestar):
    calls = []

    @batch_reads.memoised
    def read(key):
        calls.append((core_tenancy.current_tenant_id(), key))
        return len(calls)

    with tenant_ctx(brazos):
        with batch_reads.batch() as opened:
            assert read("a") == 1
            assert read("a") == 1  # served
            with tenant_ctx(lonestar):
                assert batch_reads.active() is None
                assert read("a") == 2  # asked again, under the other tenant
            with core_tenancy.tenant_context(str(brazos.id)):
                assert read("a") == 1
        assert opened.served
        assert batch_reads.active() is None
        assert read("a") == 3  # the batch is gone: asked again
    assert [c[1] for c in calls] == ["a", "a", "a"]


def test_b27__a_uuid_and_its_string_are_one_question_and_errors_are_not_kept(brazos):
    import uuid

    calls = []

    @batch_reads.memoised
    def read(key, *, on=None):
        calls.append(key)
        if key == "boom":
            raise ValueError("no")
        return [key]

    one = uuid.uuid4()
    with tenant_ctx(brazos):
        with batch_reads.batch():
            read(one)
            read(str(one), on=None)
            assert batch_reads.prime(read, ["primed"], "x")
            assert read("x") == ["primed"]
            for _ in range(2):
                with pytest.raises(ValueError):
                    read("boom")
    assert calls == [one, "boom", "boom"]


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8490 · the range on the partition key is the same days
# ══════════════════════════════════════════════════════════════════════════
def test_8490__the_read_at_range_selects_exactly_the_date_lookup_rows(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="9 Edge Ct")
        unit = make_unit(dana, premises["id"], label="Edge", services=["electric"])
        asset = a_meter(dana, asset_no="M-EDGE", unit_id=unit["id"])
        commit_read(dana, asset["id"], day="2026-06-15", value="100", unit="kWh")
        base = metering_selectors._read_heads().filter(asset_id=asset["id"])
        # Copies of that read at the very edges of the days — INSERTED, because
        # a committed read's value may not be updated (BR-MET-053's trigger).
        template = base.get()
        for edge in (
            datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
            datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
            datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
        ):
            template.id = uuid7()
            template.read_at = edge
            template.save(force_insert=True)
        old = set(
            base.filter(
                read_at__date__gte=date(2026, 6, 1), read_at__date__lte=date(2026, 6, 30)
            ).values_list("id", flat=True)
        )
        new = set(
            base.filter(
                read_at__gte=metering_selectors._day_start(date(2026, 6, 1)),
                read_at__lt=metering_selectors._day_after(date(2026, 6, 30)),
            ).values_list("id", flat=True)
        )
    assert len(old) == 3  # Jun 1 00:00, Jun 15, Jun 30 23:59:59 — not May 31, not Jul 1
    assert new == old
