# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-039 (Sign off) · J73 S2 (Sign off opens in < 2 s at 40,000)
# Defect:   DEF-BIL-8696 (Sign off's summary: 250–396 s at 40,008 bills)
# Ruling:   OQ-843 re-ruled 2026-09-30, option C — saved, and rebuilt the
#           moment what it was built from changes
# Rules:    CLAUDE.md hard-won laws 7 and 14 (proved red, on PostgreSQL)
# ───────────────────────────────────────────────────────
"""Sign off's saved summary is served only while nothing it was built from has
been written since — and a write of each kind it reads makes it rebuild.

`signoff.sign_off_summary` serves the copy saved on the run while
`signoff.inputs_key` is unchanged. These cases write ONE thing of each kind the
summary reads — a decision, a draft's total changed in place (a queryset
`.update()` that never touches `updated_at`), a payment, a migrated opening
bucket, a discarded draft, a Check row — and assert that the next read is a fresh
build, equal to `build_sign_off_summary` and showing the change.

POSTGRESQL ONLY: the key is PostgreSQL's row versions (`core.row_versions`);
elsewhere nothing is saved and every read builds.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.billing import signoff

from tests.isolation_helpers import requires_postgres
from tests.test_d8696_signoff_batched import _pay, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc


def _saved(run):
    return (
        billing_models.BillRun.objects.filter(pk=run.pk)
        .values_list("sign_off_snapshot", "sign_off_snapshot_key")
        .first()
    )


def _no_build(monkeypatch):
    """A read that BUILDS fails the case: it must be served saved."""

    def refuse(_run):
        raise AssertionError("built, where the saved summary should have been served")

    monkeypatch.setattr(signoff, "build_sign_off_summary", refuse)


@requires_postgres
def test_d8696_this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


@requires_postgres
def test_d8696_the_saved_summary_is_served_while_nothing_has_changed(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, _drafts = _world(brazos, dana)
        assert signoff.refresh_sign_off_snapshot(run) is True
        saved, key = _saved(run)
        assert key == signoff.inputs_key(run)
        assert saved == signoff.build_sign_off_summary(run)
        assert Decimal(saved["payments_and_balances"]["amount_due"]) == Decimal("688.42")
        _no_build(monkeypatch)
        assert signoff.sign_off_summary(run) == saved
        assert signoff.sign_off_summary(run) == saved


def _changes(brazos, run, drafts):
    """Each a write of one kind the summary reads, and what it moves."""
    from apps.billing import decisions, check_models
    from apps.customers import models as customer_models

    def decision():
        decisions.record_decision(
            bill_run=run, account_id=drafts["A-08601"].account_id,
            case="plan_instalment_due", choice=decisions.CHOICE_SKIP,
        )

    def draft_total():
        billing_models.Invoice.objects.filter(pk=drafts["A-08604"].pk).update(total=Decimal("55.00"))

    def payment():
        _pay(brazos, drafts["A-08603"].account, "45.00", datetime(2026, 9, 20, 12, 0, tzinfo=UTC))

    def opening():
        # The buckets are append-only: a migration that arrives adds a row.
        customer_models.AccountOpeningBucket.objects.create(
            tenant=brazos, account=drafts["A-08604"].account, as_of=date(2026, 8, 31),
            bucket=customer_models.AccountOpeningBucket.BUCKET_CURRENT, amount=Decimal("12.00"),
            currency="USD",
        )

    def draft_discarded():
        # Calculate replaces an account's draft by deleting it (BR-BIL-023); a
        # draft cannot be voided without a document (BR-BIL-030's trigger).
        billing_models.InvoiceLine.objects.filter(invoice_id=drafts["A-08604"].pk).delete()
        billing_models.Invoice.objects.filter(pk=drafts["A-08604"].pk).delete()

    def check_row():
        check_models.BillRunAccountCheck.objects.create(
            tenant=brazos, bill_run=run, account_id=drafts["A-08604"].account_id,
            account_no="A-08604", status="ready",
        )

    return {
        "decision": decision,
        "draft_total": draft_total,
        "payment": payment,
        "opening": opening,
        "draft_discarded": draft_discarded,
        "check_row": check_row,
    }


@requires_postgres
@pytest.mark.parametrize(
    "kind", ["decision", "draft_total", "payment", "opening", "draft_discarded", "check_row"]
)
def test_d8696_a_write_it_reads_makes_the_next_read_build_afresh(brazos, dana, kind):
    with tenant_ctx(brazos):
        run, drafts = _world(brazos, dana)
        assert signoff.refresh_sign_off_snapshot(run) is True
        before, before_key = _saved(run)
        _changes(brazos, run, drafts)[kind]()
        assert signoff.inputs_key(run) != before_key, f"a {kind} did not move the key"
        served = signoff.sign_off_summary(run)
        fresh = signoff.build_sign_off_summary(run)
        after, after_key = _saved(run)
    print(f"\nPROOF {kind}: amount due {before['run_summary']['amount_due']} -> "
          f"{served['run_summary']['amount_due']}")
    assert served == fresh
    assert after == fresh and after_key != before_key
    if kind != "check_row":
        assert served != before, f"a {kind} changed nothing Sign off shows"


@requires_postgres
def test_d8696_calculate_saves_the_summary_at_its_end(brazos, dana, monkeypatch):
    """`runs.calculate_run` ends by saving Sign off's summary, so Sign off opens
    on it rather than building it in the clerk's request."""
    from apps.billing import runs

    saved_for: list = []
    monkeypatch.setattr(signoff, "refresh_sign_off_snapshot", lambda run: saved_for.append(run.pk))
    with tenant_ctx(brazos):
        run, _drafts = _world(brazos, dana)
        prepared = runs.prepare_run(
            cycle_id=run.cycle_id, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
            service_date=date(2026, 10, 1),
        )
        runs.calculate_run(prepared, bill_run=run)
    assert saved_for == [run.pk]
