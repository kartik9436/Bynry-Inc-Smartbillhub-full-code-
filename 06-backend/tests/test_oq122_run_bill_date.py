# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (S31 step 1 — the run's scope, and the *"Bill date
#           (shows on statement)"* field it has always asked for) ·
#           US-BIL-002 (S31.2 — what the run then prices at)
#           Screens: S31 · S31.2
# Rules:    BR-BIL-070 (the bill date a clerk types is STORED and USED — PO
#           ruling 2026-08-11, OQ-122 option A, *"A Store what they type and
#           use it"*) · BR-RAT-007 (a bill prices on the tariff version in
#           force at the SERVICE date) · BR-BIL-024 (due date = bill date + the
#           cycle's due-days) · BR-BIL-005 (a run is idempotent on tenant +
#           cycle + period — and NOT on the bill date) · BR-BIL-050 (a run is
#           resumable from S30 at any point, so the date cannot live in the
#           browser) · BR-TEN-043 (event time is an ARGUMENT — a typed date is
#           one, a clock never is) · CLAUDE.md rule 7 (every money action is
#           audited)
# Tests:    this file
# Impacts:  apps/billing/models.BillRun.bill_date ·
#           apps/billing/migrations/0011_bill_run_bill_date.py ·
#           apps/billing/runs.effective_bill_date · apps/billing/selectors ·
#           apps/billing/api.bill_runs
# ───────────────────────────────────────────────────────
"""The clerk's typed bill date reaches the run — PO ruling 2026-08-11 (OQ-122).

Verbatim: *"A Store what they type and use it"*.

S31 step 1 has asked for a bill date since the wizard shipped and `runCreateBody`
has POSTed it since the wizard shipped. `bill_runs` had no column for it, so the
server accepted the field and dropped it, every bill priced at the CYCLE's date,
and nothing on screen said so. This file asserts the whole of what the ruling
changes and, where it matters, the outcome it reverses.

THE CONSEQUENCE THAT REACHES PAST THE ONE FIELD is asserted rather than
described: **a tariff version dated between the cycle's date and the typed date
prices differently.** The decision log states it in words; here it bites. Cycle
dated 1 Aug, clerk types 3 Aug, a rate rise effective 2 Aug — the run now
reaches the 2-Aug price, where before the ruling it reached the January one.

WHAT THIS FILE CANNOT YET ASSERT, AND WHY IT IS SAID RATHER THAN QUIETLY
OMITTED (hard-won law 1)
------------------------------------------------------------------------
**BR-BIL-024's due date.** The ruling makes the due date derive from the typed
bill date too. That derivation lives in `apps/billing/issue._due_terms_for`,
which reads `cycle__bill_date`, and `apps/billing/issue.py` is owned by another
lane in this session — so the PRICING half of the ruling ships here and the DUE
DATE half does not. A run with a typed bill date currently prices at the typed
date and derives its due date from the cycle's. That is a REPORTED gap with a
named one-line fix, not a silence.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.billing import selectors as billing_selectors
from apps.rating import models as rating_models
from core import errors

from tests.test_us_bil_001_003_run_api import (  # noqa: F401 — fixtures + helpers
    PERIOD_END,
    PERIOD_START,
    a_run_world,
    an_actor_user,
    created_run,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

# The PO's own worked case, to the day.
CYCLE_BILL_DATE = date(2026, 8, 1)  # "cycle 08-A dated 1 Aug"
#: ⚠ **WHAT THE CYCLE'S FALLBACK RESOLVES TO SINCE OQ-344 (2026-08-23).** The
#: cycle no longer STORES a bill date — `cycles.bill_date` is dropped (metering
#: 0023) — and the fallback is derived from its bill DAY: *"the bill day, in the
#: month after the period ends"* (PO verbatim: *"I'd say B - these are defualt -
#: user can override"*). These runs cover 1–30 June, so the cycle's day of 1
#: lands on **1 July**. The PO's OQ-122 case is untouched by that: it is about
#: PRECEDENCE — the clerk's 3 Aug beating whatever the cycle would have said —
#: and both dates still sit before the 2 Aug rate rise, so the old price still
#: applies to the untyped run exactly as it did.
CYCLE_DEFAULT_DATE = date(2026, 7, 1)
CLERK_TYPES = date(2026, 8, 3)  # "clerk types 3 Aug"
RATE_RISE = date(2026, 8, 2)  # a tariff version BETWEEN the two

OLD_PRICE = Decimal("0.120000")  # in force since 1 Jan 2026
NEW_PRICE = Decimal("0.150000")  # in force from 2 Aug 2026


def a_rate_rise(tenant, plan, *, effective_from=RATE_RISE, unit_price=NEW_PRICE):
    """A second ACTIVATED tariff version on the plan's schedule.

    Built the way rating really stores a flat rate — one 0→∞ tier (BR-RAT-032) —
    so `pricing_inputs` resolves it exactly as it does in production. This is
    the fixture that makes BR-RAT-007's pricing pivot observable: with two
    versions in the history, the SERVICE date decides which price the run sees.
    """
    from apps.rating import selectors as rating_selectors

    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="flat",
            base_charge=Decimal("18.500000"),
            uom="kWh",
            currency="USD",
            effective_from=effective_from,
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=unit_price,
        )


def priced_at(run):
    """(the run's service date, the unit price its only account resolved)."""
    prepared = billing_selectors.prepared_for(run)
    assert prepared.ready, "fixture: the run must have one ready account"
    tariffs = prepared.ready[0].tariffs
    assert len(tariffs) == 1, "fixture: one electric tariff"
    return prepared.service_date, tariffs[0].unit_price


# ══════════════════════════════════════════════════════════════════════════
# The resolution rule itself — pure, no database
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_001_tc7__the_typed_date_wins_and_the_cycle_is_the_fallback():
    """BR-BIL-070 — *"Store what they type and use it"*, as three cases.

    A typed date wins. No typed date means nobody expressed a preference and
    the cycle's date is used, which is what every run did before the ruling.
    Neither is `None` — this function never invents a third date and never
    reaches for a clock (BR-TEN-043 / gate G6); the caller refuses.
    """
    # ⚠ **THE SIGNATURE CHANGED WITH OQ-344 (2026-08-23)** — it took the
    # cycle's stored `bill_date` and now takes the cycle's bill DAY plus the
    # run's period end, because that column is gone (metering 0023) and the
    # fallback is DERIVED: *"the bill day, in the month after the period ends"*.
    # The PRECEDENCE this case exists for is untouched: the clerk's date wins
    # whenever there is one.
    period_end = date(2026, 6, 30)
    assert (
        billing_runs.effective_bill_date(CLERK_TYPES, CYCLE_BILL_DATE.day, period_end)
        == CLERK_TYPES
    )
    assert billing_runs.effective_bill_date(None, CYCLE_BILL_DATE.day, period_end) == date(
        2026, 7, CYCLE_BILL_DATE.day
    )
    assert billing_runs.effective_bill_date(CLERK_TYPES, None, period_end) == CLERK_TYPES
    assert billing_runs.effective_bill_date(None, None, period_end) is None


# ══════════════════════════════════════════════════════════════════════════
# The column exists and the endpoint fills it — hard-won law 2
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_001_tc7__the_endpoint_stores_the_date_the_wizard_posts(brazos, dana):
    """`runCreateBody` sends `bill_date`; the server must keep it.

    The whole defect OQ-122 recorded was a field submitted and discarded. This
    asserts the round trip through the REAL endpoint, not through `create_run`,
    because "the service can store it" and "the route passes it on" are two
    different claims and only the second is what a clerk experiences.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        actor_user = an_actor_user(brazos)
    response = created_run(brazos, actor_user, cycle, bill_date=CLERK_TYPES.isoformat())
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])

    assert run.bill_date == CLERK_TYPES
    # And it is NOT the cycle's — the two differ on purpose in this fixture.
    assert run.bill_date != CYCLE_BILL_DATE


def test_us_bil_001_tc7__an_omitted_bill_date_records_that_nobody_typed_one(brazos, dana):
    """Absent, null and "" are ONE answer, and it is not an error.

    NULL means *nobody typed a bill date on this run* — a real fact, not a
    missing value — and the cycle's date is then used. An empty string arrives
    from a date input a clerk cleared, and refusing it would refuse a run over a
    field the ruling makes optional.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        actor_user = an_actor_user(brazos)

    for value, label in ((None, "null"), ("", "empty string")):
        with tenant_ctx(brazos):
            billing_models.BillRun.objects.all().delete()
        response = created_run(brazos, actor_user, cycle, bill_date=value)
        assert response.status_code == 201, f"{label} must be accepted, not refused"
        with tenant_ctx(brazos):
            run = billing_models.BillRun.objects.get(pk=response.data["id"])
            assert run.bill_date is None, label
            # …and the run still bills, on the cycle's DEFAULT (OQ-344).
            assert billing_selectors.prepared_for(run).service_date == CYCLE_DEFAULT_DATE


def test_us_bil_001_tc7__a_malformed_bill_date_is_refused_by_name(brazos, dana):
    """A date that is PRESENT is parsed strictly (BR-TEN-020).

    A bill date decides which tariff version prices the run, so a value parsed
    by guessing at a format would price two identical runs differently in two
    regions. Optional is not lenient — and the refusal leaves no row.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        actor_user = an_actor_user(brazos)
    refused = created_run(brazos, actor_user, cycle, bill_date="03/08/2026")
    with tenant_ctx(brazos):
        rows = billing_models.BillRun.objects.count()

    assert refused.status_code == 422
    # ⚠ AMENDED 2026-09-30 (BR-BIL-1050): every Scope refusal comes back at
    # once, so the envelope's code is the summary's and the format refusal is
    # the FIELD error — on the bill-date field, still VAL-002.
    bill = [e for e in refused.data["field_errors"] if e["field"] == "bill_date"]
    assert [(e["reason"], e["code"]) for e in bill] == [("bill_date_invalid", errors.VAL_FORMAT)]
    assert rows == 0


# ══════════════════════════════════════════════════════════════════════════
# The consequence the PO was shown — the run PRICES at the typed date
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_002_tc7__a_tariff_version_between_the_two_dates_prices_differently(brazos, dana):
    """The decision log's consequence (b), as an assertion.

    Cycle dated **1 Aug** · clerk types **3 Aug** · a rate rise effective
    **2 Aug**. BR-RAT-007 prices on the SERVICE date, so:

      * typed 3 Aug   → service date 3 Aug → the 2-Aug version → **0.150000**
      * nothing typed → service date 1 Aug → the January version → **0.120000**

    Both are asserted, so the test states the behaviour the ruling REPLACED as
    well as the one it introduced. This is the case that makes the ruling worth
    more than one stored field: the same run, the same cycle, two prices.
    """
    with tenant_ctx(brazos):
        cycle, plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        a_rate_rise(brazos, plan)

        typed = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=CLERK_TYPES,
        )
        service_date, unit_price = priced_at(typed)
        assert service_date == CLERK_TYPES
        # ⚠ SUPERSEDED 2026-09-30 — BR-BIL-1055 (PO: *"this si correct"* to *"The
        # period end: $3.25"*): the typed date is still the run's DOCUMENT date,
        # and the rate VERSION is the one in force at the PERIOD END (30 Jun),
        # which is the January version. The pricing half of this case is
        # replaced by US-BIL-038 TC-2 (`tests/test_bbr_check_engine.py::
        # test_b16__…`). Until 2026-09-30 this asserted NEW_PRICE.
        assert unit_price == OLD_PRICE, (
            "the run must price against the tariff version in force at the "
            "period end (30 Jun), not the date the clerk typed (3 Aug)"
        )

        # The pre-ruling behaviour, kept visible: with no typed date the same
        # run falls back to the CYCLE's default — 1 July since OQ-344 — and
        # reaches the OLD price, because both it and the cycle's old stored
        # 1 Aug sit before the 2 Aug rate rise.
        billing_models.BillRun.objects.all().delete()
        untyped = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        service_date, unit_price = priced_at(untyped)
        assert service_date == CYCLE_DEFAULT_DATE
        assert unit_price == OLD_PRICE


def test_us_bil_002_tc7__neither_date_still_refuses_rather_than_guessing(brazos, dana):
    """No typed date and no cycle date REFUSES — it never reaches for a clock.

    BR-RAT-007 prices on the service date, so a guessed one silently selects a
    different tariff version. BR-TEN-043 and gate G6 both ban a clock in this
    path, and the refusal names BR-BIL-024 so a clerk is told which rule stopped
    them.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=None)
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

        with pytest.raises(errors.BizError) as refusal:
            billing_selectors.prepared_for(run)
        assert refusal.value.br_ref == "BR-BIL-024"

        # …and a TYPED date is enough on its own: the cycle never gains one and
        # the run prices anyway. A typed date is an argument, which is exactly
        # what the event-time law asks for.
        typed = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            bill_date=CLERK_TYPES,
        )
        assert billing_selectors.prepared_for(typed).service_date == CLERK_TYPES


# ══════════════════════════════════════════════════════════════════════════
# What the stored date must NOT do
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_001_tc7__the_bill_date_is_not_part_of_the_idempotency_key(brazos, dana):
    """BR-BIL-005 keys on tenant + cycle + period, and gains no fourth term.

    If the bill date joined the key, one cycle-period could be billed twice by
    retyping one field — which is the double-billing BR-BIL-005 exists to
    prevent. So a second run over the same cycle and period is refused however
    different its bill date.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        first = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=CLERK_TYPES,
        )

        with pytest.raises(billing_runs.DuplicateRun):
            billing_runs.create_run(
                cycle_id=cycle.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                bill_date=date(2026, 8, 9),  # a different typed date
            )
        assert billing_models.BillRun.objects.count() == 1
        assert billing_models.BillRun.objects.get().pk == first.pk


def test_us_bil_001_tc7__the_typed_date_reaches_the_audit_trail(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — the date decides prices and due dates, so it is logged.

    `bill_run.created` carries it, and carries `null` when nobody typed one,
    because "the clerk chose 3 Aug" and "the clerk chose nothing" are different
    facts a dispute months later turns on.

    Asserted through the BE-03 capture sink rather than by querying `audit_log`:
    the trail table is partitioned and this is a claim about the PAYLOAD, not
    about the store.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        audit_rows.clear()
        billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=CLERK_TYPES,
        )
        billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
        )

    created = [row for row in audit_rows if row["action"] == "bill_run.created"]
    assert len(created) == 2
    assert created[0]["after"]["bill_date"] == CLERK_TYPES.isoformat()
    assert created[1]["after"]["bill_date"] is None


def test_us_bil_001_tc7__a_resumed_run_still_finds_the_date(brazos, dana):
    """BR-BIL-050 — a run is resumable from S30 *"at any point"*.

    Which is why the date could never have lived in the browser: a clerk who
    comes back tomorrow must find the same bill date, and re-reading the row
    from scratch must give the same service date. Asserted by discarding the
    in-memory row entirely and reading it back by id.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=CYCLE_BILL_DATE)
        run_id = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=CLERK_TYPES,
        ).pk

        reopened = billing_selectors.run_or_404(str(run_id))
        assert reopened.bill_date == CLERK_TYPES
        assert billing_selectors.prepared_for(reopened).service_date == CLERK_TYPES


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (this file's own sources, in order:
#         12-governance/02-decision-log.md 2026-08-11 row "THE BILL DATE A CLERK
#         TYPES IS STORED AND USED (OQ-122 CLOSED, option A)" ·
#         12-governance/01-open-questions.md OQ-122 (CLOSED) ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-070 +
#         BR-BIL-024 · 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md §5)
# generated: 2026-08-11 by Eng-Lead (OQ-122 typed-bill-date lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S31 step 1 already ships the field and `runCreateBody` already POSTs it; nothing in 07-frontend changes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · RED-PROVED before being trusted green — the measured
#         failures are quoted verbatim in apps/billing/runs.py's trailer and in
#         12-governance/09-human-review-ledger.md
# exceptions: (1) THE DUE-DATE HALF OF THE RULING IS NOT ASSERTED HERE because
#         it is not built: BR-BIL-024's derivation lives in
#         `apps/billing/issue._due_terms_for`, which reads `cycle__bill_date`,
#         and apps/billing/issue.py belongs to another lane in this session. A
#         run with a typed bill date PRICES at the typed date and derives its
#         due date from the cycle's — REPORTED, with the one-line fix named,
#         rather than asserted as though it worked (hard-won law 1) ·
#         (2) the fixtures are imported from tests/test_us_bil_001_003_run_api.py
#         rather than rebuilt: a second copy of "a cycle, a plan, a metered unit,
#         an account" is a second thing to keep true · (3) no isolation marker —
#         the new column changes no RLS policy (a policy is per table) and
#         `bill_runs` cross-tenant behaviour is already covered by that file's
#         tc6 cases
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
