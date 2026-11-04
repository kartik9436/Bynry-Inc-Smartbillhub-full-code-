# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 group 6 — the finance-period family (T5-08 · T5-09 · T6-09),
#           which all want the same two facts: 2026-06 CLOSED with a recorded
#           export batch, 2026-07 the earliest OPEN period.
# Defect:   DEF-576 (2026-08-22) — the T7-14 cohort issued into OCTOBER 2026,
#           the month OQ-333's ruling moves the LE-1 book to, and seed_j19
#           refused: *"the fixture month October 2026 already holds 2 posted
#           entries … those entries are somebody else's book"*. The last test in
#           this file is the durable half of that fix.
# Rules:    BR-LED-017 (an OPEN period may never be exported) · BR-LED-018
#           (close is WARN + CONFIRM, never a silent close and never a lockout)
#           · BR-TEN-038 (an entry dated into a closed period auto-forwards) ·
#           BR-TEN-043 (every business moment is an argument, never a clock) ·
#           OQ-333 (the LE-1 book's month moves only where July is taken).
# Red-proof: shown RED before green; the failures are quoted in the commit
#           message and the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""One closed month, one open month — and the month nobody else may use.

The finance-period cohort has an ORDERING hazard no journey can see. LE-1's
book opens with a cutover entry dated **2026-06-30**, inside the very window
this cohort closes, and the posting service auto-forwards an entry whose date
lands in a closed period. So a stack that closed June before the book was
posted would push LE-1's opening entry into July and the finance-signed 598.69
footing would move — silently, because auto-forwarding is correct behaviour.
The builder refuses rather than allowing it, and the first case here is that
refusal.

The last case is DEF-576's guard, and it is about a different scarce resource:
a MONTH. In a shared fixture tenant, a cohort that issues a bill into a month
has claimed it, and OQ-333's ruling claims one for the LE-1 book. Building
every round-3 cohort must leave that month empty.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from tests import journey_cohort_fixtures as cohort
from tests import ledger_le_fixtures as le
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEEDER_PATH = (
    Path(__file__).resolve().parents[2] / "08-qa" / "01-e2e" / "stack" / "seed_journey_fixture.py"
)


def _seeder():
    spec = importlib.util.spec_from_file_location("seed_journey_fixture_finance", SEEDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _post_the_book(tenant, dana):
    """LE-1's book, posted where it is signed — July, on a clean test tenant."""
    world: dict = {}
    accounts = le.make_accounts(dana, tenant, world, service="electric")
    le.post_le1_month(tenant, accounts)
    return accounts


def test_round3_finance__closing_june_before_the_book_is_posted_is_REFUSED(brazos, dana):
    """The ordering guard, and it protects a finance-signed figure.

    Nothing in the seeder registry orders J19 before T5-08. If June were closed
    first, LE-1's 2026-06-30 opening entry would auto-forward into July
    (BR-TEN-038) and the signed 598.69 footing would move — with no error
    anywhere, because auto-forwarding is the correct behaviour for an ordinary
    entry. So the cohort refuses by name instead.
    """
    with tenant_ctx(brazos):
        with pytest.raises(cohort.CohortCannotSeed) as refusal:
            cohort.ensure_finance_period_cohort(brazos, dana)

    assert "LE-1 book is not posted" in str(refusal.value)
    assert "auto-forward" in str(refusal.value)


def test_round3_finance__june_closes_and_july_stays_open(brazos, dana):
    """T5-08's two facts, both asserted from the product's own state.

    July must be OPEN because T5-08's whole subject is being REFUSED an export
    of an open period (BR-LED-017). With July closed the refusal never happens
    and the journey passes over the wrong state entirely.
    """
    from apps.ledger import close as ledger_close

    with tenant_ctx(brazos):
        _post_the_book(brazos, dana)
        result = cohort.ensure_finance_period_cohort(brazos, dana)

        closed_start, closed_end = cohort.FINANCE_CLOSED_PERIOD
        open_start, open_end = cohort.FINANCE_OPEN_PERIOD
        assert ledger_close.is_period_closed(closed_start, closed_end)
        assert not ledger_close.is_period_closed(open_start, open_end)

    assert result["posted_in_open_period"] > 0
    assert result["close_reason"] == cohort.FINANCE_CLOSE_REASON


def test_round3_finance__the_export_batch_is_recorded_for_the_closed_window(brazos, dana):
    """*"period 2026-06 CLOSED with recorded batch EXP-2606-01"*.

    The BATCH is real and its NUMBER is not seeded — `export_batches.batch_no`
    comes from the tenant's `export_batch` series, and tenancy seeds no default
    format for it, so the recorded batch may carry NULL. A typed `EXP-2606-01`
    would be a number no series issued, which is the kind of plausible fiction
    a fixture must never write.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        _post_the_book(brazos, dana)
        result = cohort.ensure_finance_period_cohort(brazos, dana)
        batches = list(
            ledger_models.ExportBatch.objects.filter(
                tenant=brazos,
                period_start=cohort.FINANCE_CLOSED_PERIOD[0],
                period_end=cohort.FINANCE_CLOSED_PERIOD[1],
            )
        )

    assert len(batches) == 1, "one handover per covered window (BR-LED-004 / DB-12)"
    assert batches[0].target == cohort.FINANCE_EXPORT_TARGET
    assert result["batch_target"] == cohort.FINANCE_EXPORT_TARGET


def test_round3_finance__the_cohort_is_idempotent(brazos, dana):
    """A re-boot re-runs every seeder (CLAUDE.md rule 6).

    Closing an already-closed period raises in the real service — deliberately,
    because a second close would overwrite the first one's reason and its
    incomplete-item snapshot — so a cohort that did not check would turn every
    re-boot into a failure.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        _post_the_book(brazos, dana)
        first = cohort.ensure_finance_period_cohort(brazos, dana)
        second = cohort.ensure_finance_period_cohort(brazos, dana)
        batches = ledger_models.ExportBatch.objects.filter(tenant=brazos).count()
        closes = ledger_models.FiscalPeriodClose.objects.filter(tenant=brazos).count()

    assert batches == 1
    assert closes == 1
    assert first["closed_period"] == second["closed_period"]


def test_round3_no_cohort_may_issue_into_the_month_oq333_reserves(brazos, dana):
    """DEF-576's durable half — a MONTH is a resource in a shared tenant.

    OQ-333's ruling moves the LE-1 fixture book forward when July is taken, and
    `seed_j19` verifies its destination month is EMPTY before posting a line.
    T7-14 billed three consecutive cycles and its third landed exactly there;
    J19 then refused on every stack that seeded T7-14 first.

    The destination is read from the SEEDER's own `FIXTURE_MONTH_SHIFT`, never
    from a copy — if the shift is ever changed, this test follows it and the
    cohorts are re-checked against the new month rather than against a stale
    one.
    """
    from apps.ledger import models as ledger_models

    seeder = _seeder()
    destination_start = seeder._shift_month(le.JULY_START, seeder.FIXTURE_MONTH_SHIFT)
    destination_end = seeder._shift_month(le.JULY_END, seeder.FIXTURE_MONTH_SHIFT)

    with tenant_ctx(brazos):
        cohort.ensure_flat_cohort(brazos, dana)
        cohort.ensure_grace_pre_state(brazos, dana)
        cohort.ensure_guardrail_cohort(brazos, dana)
        cohort.ensure_we1_taxed_bill(brazos, dana)
        intruders = list(
            ledger_models.JournalEntry.objects.filter(
                tenant=brazos,
                status=ledger_models.JE_POSTED,
                entry_date__gte=destination_start,
                entry_date__lte=destination_end,
            ).values_list("posting_key", "entry_date")
        )

    assert destination_start == date(2026, 10, 1), (
        "the OQ-333 destination moved; re-read the fixture-month calendar at "
        "journey_cohort_fixtures.T714_CYCLE_MONTHS before changing this"
    )
    assert not intruders, (
        f"these entries occupy {destination_start:%B %Y}, the month OQ-333's ruling moves "
        f"the LE-1 book into: {intruders}. seed_j19 verifies that month is EMPTY and will "
        "refuse — DEF-576 exactly. A cohort that issues into a month has claimed it."
    )
