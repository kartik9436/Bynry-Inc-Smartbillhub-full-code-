# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (the move-out flow this fixture finally exercises) ·
#           US-TEN-019 (the sample set the block belongs to)
#           Screens: S17 (Accounts, where a `Closed` row is now visible) ·
#           S21 (the account) · S20 (the wizard whose service this drives)
# Change:   DEF-CUS-4628 — no seeded tenant had ever held an account in the
#           TERMINAL state.
# Rules:    BR-CUS-030 (a move-out writes `closed_at`, the terminal status and
#           every open `service_agreements.ended_on`) · BR-CUS-055 (billing and
#           occupancy key off the behaviour CLASS) · BR-CUS-056 (the outgoing
#           account pays the move day) · BR-BIL-004 (a move-out may not be
#           dated behind an issued bill) · BR-CUS-082 (a debt surviving closure
#           is still owed) · BR-TEN-056/060/063 (the sample set, its named
#           blocks, its idempotency) · CLAUDE.md hard rule 4 (nothing issued is
#           edited)
# Tests:    this file
# Impacts:  apps/customers/sample_data.seed_sample_move_out ·
#           apps/tenancy/sample_data.SAMPLE_MODULES (the position IS the fix) ·
#           core/sample_fixture.move_out_on
# ───────────────────────────────────────────────────────
"""DEF-CUS-4628 — the demo's terminal state is REACHED, not merely seeded.

WHAT WENT WRONG, IN THE NUMBERS THAT FOUND IT
----------------------------------------------
On a freshly planted `brazosbend`, 2026-09-07:

    69 Active · 1 Marked disconnect · 1 Pending activation · 1 Vacation hold
    select count(*) from accounts where closed_at is not null   →   0
    select count(*) from move_records where kind = 'move_out'   →   0

Six account statuses are seeded and `Closed` — the TERMINAL one, the state the
whole move-out flow exists to arrive at — had never once been assigned. The
product was not broken: `services.move_out` writes every column BR-CUS-030
names. **Nothing had ever called it on the demo estate.**

WHY EVERY EXISTING CHECK MISSED IT, AND WHAT THIS FILE ASSERTS INSTEAD
----------------------------------------------------------------------
Every check on the status list asks whether the six ROWS EXIST
(`test_reference_data_completeness`), never whether a row is ever ASSIGNED. The
seed count is compared against SEATS, not against STATES. So the assertions
here are about a state being **reached**, which is a question nothing in this
repository had asked of any lookup value.

⚠ **AND THE FIXTURE'S OWN DATE WAS ONE THE PRODUCT REFUSES**, which is the
half that could only be found by calling the door. `account_plan()` carried
`moved_out_on = 2026-07-15` and never read it back; measured against the real
estate that date raises

    BIZ-STATE customers.account.move_out_behind_issued_bill
    (BR-BIL-004, issued_through 2026-07-31)

because this estate bills WHOLE MONTHS and that account's July bill is issued
through the 31st. `fixture.move_out_on()` now derives the day from the last
BILLED period, so the guard is satisfied by construction rather than by a
literal somebody has to remember to move — and `test_the_date_is_the_last_day_
the_fixture_billed` below is what goes red if a literal comes back.

NON-VACUOUS (DEF-466 / DEF-828's shape)
----------------------------------------
Every assertion here comes with the thing that stops it passing over an empty
or half-planted estate: the terminal count is asserted as EXACTLY ONE rather
than "at least one", so a fixture that closed the whole estate fails just as
loudly as one that closes nothing; the closed account is required to still hold
its two ISSUED bills, so a block that reached the terminal state by deleting
history fails; and the block's POSITION is asserted, because a correct row in
the wrong place writes the same account row and silently costs that account
both of its bills.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.customers import models as customers_models
from apps.customers import moves, sample_data as customers_sample_data
from apps.customers import services as customers_services
from apps.tenancy import sample_data as tenancy_sample_data
from core import sample_fixture as fixture
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# The cheap half — the block exists, is published, and is in the right place
# ══════════════════════════════════════════════════════════════════════════
MOVE_OUT_BLOCK = "customers:seed_sample_move_out"


def test_the_seam_the_orchestrator_resolves_is_implemented():
    """DEF-153's assertion, for this block. A `SampleModule` row whose module
    publishes no such callable is a NAMED not-loaded line and `run_summary()`
    then answers `succeeded = False` — the block and its seam land in ONE
    commit or the branch is merge-blocked in between."""
    assert callable(getattr(customers_services, "seed_sample_move_out", None)), (
        "apps.customers.services.seed_sample_move_out is not implemented, so the "
        f"{MOVE_OUT_BLOCK} block would report itself not-loaded on every plant"
    )


def test_the_block_runs_after_the_money_and_before_the_payment_plan():
    """**THE POSITION IS THE FIX, not the row.** A closed account's behaviour
    class is not in `OCCUPYING_BEHAVIOR_CLASSES`, so it leaves
    `accounts_in_cycle` and no bill run can see it. Move this block above
    either billing block and it writes exactly the same account row while
    costing that account BOTH of its bills, its collections and the August
    reading story the fixture tells about it — which is the failure a test that
    merely counted closed accounts would pass straight over."""
    keys = [spec.key for spec in tenancy_sample_data.SAMPLE_MODULES]
    assert MOVE_OUT_BLOCK in keys, f"{MOVE_OUT_BLOCK} is not in SAMPLE_MODULES"
    assert keys.index("billing:seed_sample_second_cycle") < keys.index(MOVE_OUT_BLOCK), (
        "the move-out block runs BEFORE the second cycle is billed, so the account it "
        "closes is billed neither month"
    )
    assert keys.index("payments:seed_sample_cycle_collections") < keys.index(MOVE_OUT_BLOCK), (
        "the move-out block runs BEFORE the collections, so the tenancy ends before it "
        "was ever paid against"
    )
    assert keys.index(MOVE_OUT_BLOCK) < keys.index("customers:seed_sample_payment_plans")


def test_the_date_is_the_last_day_the_fixture_billed():
    """`BR-BIL-004` — a move-out may not be dated behind an issued bill, and
    `BR-CUS-056` — the outgoing account pays the move day. Both are satisfied
    by ONE date: the last day of the last BILLED period, which makes that
    period's bill the tenancy's final bill with nothing to prorate and nothing
    to reissue (hard rule 4).

    Asserted as a DERIVATION rather than as `2026-07-31`, because the literal
    is precisely what went wrong: the fixture carried `2026-07-15` for weeks and
    nothing could tell, since nothing read the field."""
    billed_ends = [period["end"] for period in fixture.PERIODS if period["billed"]]
    assert fixture.move_out_on() == max(billed_ends)
    unbilled_starts = [period["start"] for period in fixture.PERIODS if not period["billed"]]
    assert all(fixture.move_out_on() < start for start in unbilled_starts), (
        "the tenancy must end before the unbilled cycle the Product Owner runs, or the "
        "demo's third run has one fewer account for a reason nobody can see"
    )
    plan = {row["unit_index"]: row for row in fixture.account_plan()}
    assert plan[fixture.CASE_MOVED_OUT]["moved_out_on"] == fixture.move_out_on(), (
        "account_plan()'s move-out date has stopped agreeing with move_out_on() — which "
        "is DEF-CUS-4628 exactly: a fixture field nothing reads back"
    )


# ══════════════════════════════════════════════════════════════════════════
# The half that needs a real estate — the state is REACHED
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **ONE PLANT, NOT FIVE.** A full `seed_sample_data` is minutes of work on a
# shared machine, and `test_cr040_seeded_books_tie_out.py` plants six times in
# one file. Every fact below is asserted against a single estate, each with its
# own sentence, so a failure is still legible without paying for the plant once
# per question.


def _real_admin(tenant):
    """An actor whose id resolves to a real user row — `move_out` is
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` on the SERVICE, and a
    namespace with a random uuid gets past neither."""
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def test_the_seeded_estate_ends_with_exactly_one_closed_account():
    """DEF-CUS-4628, asserted end to end on the estate the Product Owner gets.

    Nothing here is hand-written: the tenant is provisioned and planted through
    the same orchestrator the Sample data panel presses, so what this file
    reads is what a person opening the demo reads."""
    from apps.billing import models as billing_models

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        actor = _real_admin(tenant)
        tenancy_sample_data.seed_sample_data(actor)

    with tenant_ctx(tenant):
        # ── 1 · EXACTLY ONE, in both directions ─────────────────────────────
        # "At least one" would pass over a fixture that closed the whole
        # estate, and the Product Owner's standing principle for this demo is
        # that *a demo where everything is finished leaves nothing to
        # evaluate* — it is why the third billing cycle is left unrun.
        terminal = list(
            customers_models.Account.objects.filter(
                tenant_id=tenant.id,
                status__behavior_class=customers_services.CLASS_TERMINAL,
            ).select_related("status", "unit")
        )
        assert (
            len(terminal) == 1
        ), f"the seeded estate holds {len(terminal)} terminal accounts, not 1: " + ", ".join(
            f"{row.account_no} ({row.status.code})" for row in terminal
        )
        account = terminal[0]
        assert account.closed_at == fixture.move_out_on()
        assert account.status.code == "closed"
        assert account.is_sample is True

        # ── 2 · ON THE SEAT THE FIXTURE DECLARES ────────────────────────────
        # A block that closed some other unit would satisfy every count above
        # and would put the demo's move-out on a customer with no story.
        plan = {row["unit_index"]: row for row in fixture.account_plan()}
        assert account.unit.unit_no == plan[fixture.CASE_MOVED_OUT]["unit_no"]

        # ── 3 · BR-CUS-030's OTHER WRITE ────────────────────────────────────
        # `service_agreements.ended_on` is not on hard rule 4's list — B2
        # declares the column as *"NULL = still in force"* — so writing it is
        # the documented close of an agreement, never an edit of history.
        agreements = list(
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=tenant.id, account_id=account.id
            )
        )
        assert agreements, "the closed account holds no service agreements at all"
        assert all(
            row.ended_on == fixture.move_out_on() for row in agreements
        ), "an agreement on a closed account is still open: " + ", ".join(
            str(row.ended_on) for row in agreements
        )

        # ── 4 · NOTHING ISSUED WAS TOUCHED (CLAUDE.md hard rule 4) ──────────
        # Asserted PRESENT and ISSUED because that is how this fixture could
        # have reached a terminal state dishonestly: a block that deleted or
        # un-issued the history would satisfy every status assertion above.
        issued = list(
            billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, account_id=account.id, status="issued"
            ).order_by("period_start")
        )
        billed_periods = [period for period in fixture.PERIODS if period["billed"]]
        assert len(issued) == len(billed_periods), (
            f"the closed account holds {len(issued)} issued bills and the fixture billed "
            f"{len(billed_periods)} cycles — closing an account must not touch anything "
            "already issued"
        )
        assert max(row.period_end for row in issued) == account.closed_at, (
            "the last issued period no longer ends on the move day, so BR-CUS-056's "
            "'the outgoing account pays the move day' has stopped being true"
        )

        # ── 5 · THE MVO- SERIES ISSUED ITS FIRST NUMBER ─────────────────────
        # `_seed_cr039_move_records` skips any account whose `closed_at` is
        # NULL, so this series had never issued a number on any seeded tenant —
        # the demo held one move record and it was a move-IN. `move_out` writes
        # the record itself, inside its own transaction.
        records = list(
            moves.MoveRecord.objects.filter(tenant_id=tenant.id, kind=moves.KIND_MOVE_OUT)
        )
        assert len(records) == 1, f"expected one seeded move-out record, found {len(records)}"
        assert records[0].effective_on == fixture.move_out_on()
        assert records[0].is_sample is True
        assert str(records[0].move_no or "").startswith(
            "MVO-"
        ), f"the seeded move-out record carries {records[0].move_no!r}, not an MVO- number"

        # ── 6 · IDEMPOTENT (BR-TEN-063 · CLAUDE.md rule 6) ──────────────────
        # The counts are RE-READ after the replay rather than the return value
        # being trusted, so a block that closed a SECOND account and answered 0
        # would still fail here.
        assert customers_sample_data.seed_sample_move_out(actor) == 0
        assert (
            customers_models.Account.objects.filter(
                tenant_id=tenant.id,
                status__behavior_class=customers_services.CLASS_TERMINAL,
            ).count(),
            moves.MoveRecord.objects.filter(tenant_id=tenant.id, kind=moves.KIND_MOVE_OUT).count(),
        ) == (1, 1)
