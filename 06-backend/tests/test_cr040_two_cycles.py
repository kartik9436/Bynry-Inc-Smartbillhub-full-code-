# ── Trace ──────────────────────────────────────────────
# Story:    CR-040 wave C (two billing cycles, and the money between them)
#           Screens: S8 (Sample data panel), S31 (Bill run)
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 (the sample set reaches money) ·
#           BR-TEN-061 (removal order) · BR-TEN-063 (atomic per module,
#           idempotent) · BR-BIL-005 (a run is keyed on cycle + period, so a
#           replay issues nothing) · BR-BIL-058 (the release gate's five facts)
#           · CLAUDE.md hard rule 4 (an issued invoice is append-only)
# Tests:    this file
# Impacts:  apps/billing/sample_data (two seams) · apps/tenancy/sample_data
#           (the block order) · core/sample_fixture (PERIODS)
# ───────────────────────────────────────────────────────
"""CR-040 wave C — TWO cycles issued, on a real seeded tenant, end to end.

WHY THIS FILE EXISTS SEPARATELY FROM THE DECLARATION TESTS
-----------------------------------------------------------
`test_us_ten_019_sample_records.py` asserts what the fixture DECLARES: which
periods are marked billed, which seam owns which period, and that the payments
block sits between the two billing blocks in `SAMPLE_MODULES`. All of that can
be true while the second cycle issues nothing — the declaration is a tuple, and
a tuple cannot bill.

DEF-166 is the reason that distinction is written down rather than assumed. Its
whole shape was a count read off rows that included DRAFTS, so a run that issued
**zero** bills reported 95 and the panel printed OK. A second billing block is a
new opportunity for exactly that: it runs late, against an estate five blocks
have already changed, and if it quietly issued nothing the only visible
difference would be a number nobody counts.

So this file runs the real orchestrator on a real provisioned tenant and asks
the database how many bills ISSUED, per period.

RED-FIRST RECORD (hard-won law 7): the two tests below were run against the tree
before the seam split landed and failed on the missing block —
`("billing", "seed_sample_second_cycle")` is not in `SAMPLE_MODULES` — and the
issued-count assertion failed with July at 0.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.billing import models as billing_models
from apps.billing import sample_data as billing_sample
from apps.tenancy import sample_data
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _real_admin(tenant):
    """An actor whose id resolves to a real user row.

    BR-BIL-058's fifth fact is WHO authorised the run, and `authorise_release`
    refuses a null `confirmed_by` — correctly, since a bill run authorised by
    nobody is not authorised. The shared `admin_actor()` helper is a namespace
    with a random uuid, which several blocks get away with and this one cannot.
    """
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def _issued_by_period() -> dict[str, int]:
    """Bills that ISSUED, per fixture period — counted off the rows.

    `status="issued"` is not decoration: DEF-166's count was read off the rows
    too, and included drafts. Reading the database is what stops a count
    drifting from what the database holds; reading only the ISSUED rows is what
    stops it hiding a failure.
    """
    out: dict[str, int] = {}
    for period in fixture.PERIODS:
        out[period["key"]] = billing_models.Invoice.objects.filter(
            bill_run__period_start=period["start"],
            bill_run__period_end=period["end"],
            status="issued",
        ).count()
    return out


def test_cr040_c11__two_cycles_issue_and_the_third_is_left_unbilled():
    """The PO's own sentence, proved on rows: *"complete 2 billing cycle and
    create data for 3rd billing cycle"*."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
        issued = _issued_by_period()
        runs_issued = billing_models.BillRun.objects.count()

    assert issued["june"] > 0, "cycle one issued nothing"
    assert issued["july"] > 0, "cycle two issued nothing — the block ran and billed no one"
    # Two cycles, not one billing twice: each period is its own run.
    assert runs_issued >= 2

    # THE INVARIANT THAT SURVIVED THREE RULINGS: the last period is the PO's own.
    assert issued[fixture.PERIODS[-1]["key"]] == 0, (
        "August must stay unbilled — a demo that arrives with everything done "
        "leaves nothing to evaluate"
    )


def test_cr040_c11__the_second_cycle_is_written_after_the_money_is():
    """The ORDER, proved by its consequence rather than by reading a tuple.

    ⚠ **THIS IS THE ASSERTION THE WHOLE WAVE IS FOR.** Both orderings write the
    same rows; only one of them produces a second cycle billed against an estate
    with a financial past. The tuple order is asserted in
    `test_us_ten_019_sample_records.py`; this asserts that the money genuinely
    existed in the database BEFORE the second cycle's bills did.

    ⚠ **THE FIRST VERSION OF THIS TEST COMPARED THE WRONG CLOCKS, AND IT IS
    RECORDED RATHER THAN QUIETLY FIXED.** It read `Payment.received_at` against
    `Invoice.issued_at` — the BUSINESS dates the fixture states. Those are
    back-dated declarations: the seeded payments are dated on the fixture's busy
    day, **8 August**, and July's bills are dated **2 August**, so on business
    dates the money looks later than the bills no matter which block ran first.
    The test failed against a tree where the ordering was correct.

    The clock that answers this question is `created_at` (`auto_now_add`) —
    **when the seeder actually wrote the row**. That is the only field that
    records the block order, because it is the only one the fixture does not
    get to choose.
    """
    from apps.payments import models as payment_models

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))

        july = next(p for p in fixture.PERIODS if p["key"] == "july")
        second_run = billing_models.BillRun.objects.filter(
            period_start=july["start"], period_end=july["end"]
        ).first()
        assert second_run is not None, "the second cycle created no run at all"

        written_at = (
            billing_models.Invoice.objects.filter(bill_run=second_run, status="issued")
            .order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        assert written_at is not None

        total_payments = payment_models.Payment.objects.count()
        paid_before = payment_models.Payment.objects.filter(
            created_at__lt=written_at
        ).count()

    # Non-vacuous by construction (DEF-466's shape): a fixture that seeded no
    # payments at all would satisfy "none were written after" trivially.
    assert total_payments > 0, "no payments seeded — this test would pass vacuously"
    assert paid_before > 0, (
        "the second cycle's bills were written before any payment was — the "
        "payments block did not run between the two billing blocks, which is the "
        "one thing this wave was asked for"
    )


def test_cr040_c11__a_replay_bills_nothing_twice():
    """BR-BIL-005 + BR-TEN-063 on the NEW seam as well as the old one.

    Idempotency is the reason a second billing block is safe to add: the run is
    keyed on (cycle, period), so a repeated load finds the existing run and
    issues nothing. Asserted on the second cycle specifically, because the first
    one has had that guarantee since it was written and the second one is new.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        admin = _real_admin(tenant)
        sample_data.seed_sample_data(admin)
        first = _issued_by_period()
        second_pass = billing_sample.seed_sample_second_cycle(admin)
        after = _issued_by_period()

    assert second_pass == 0, "a replay of cycle two issued bills"
    assert first == after, "a replay changed the issued counts"
