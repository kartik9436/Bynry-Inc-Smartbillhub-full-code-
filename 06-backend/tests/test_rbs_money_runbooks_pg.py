# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-022 · US-RBS-026 (EP-RBS-05) — CR-075 wave P: the two money
#           runbooks, on the vendor that will run them.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE is on; no cross-tenant queryset) · hard
#           rule 4 (a payment row is append-only) · hard-won law 14 (the suite
#           is in-memory SQLite and production is PostgreSQL) · hard-won law 7
#           (a check that cannot fail is the defect) · BR-RBS-002 · BR-RBS-003
#           (dry and live are ONE code path) · BR-RBS-018 · BR-RBS-027
# Tests:    this file
# Impacts:  apps/runbooks/definitions/cash_application.py ·
#           apps/runbooks/definitions/bank_reconciliation.py ·
#           apps/runbooks/seams/payments_seam.py ·
#           apps/runbooks/seams/integrations_seam.py
# ───────────────────────────────────────────────────────
"""The two money runbooks on real PostgreSQL, through the REAL seams.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_rbs_money_runbooks_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE.** The sibling suites
replace the seams with fixed answers, so they prove the runbooks' REASONING and
nothing about the reads. **These cases replace nothing**: the connection check
asks `integrations` for real, the batch read asks `payments` for real, and the
tenant boundary is the database's own row-level security rather than a filter in
Python. Every case carries `requires_postgres` and SKIPS on the default suite
rather than passing vacuously — `G5` once ran the isolation suite on SQLite and
called 192 skips a pass.

⚠ **WHAT EACH CASE WOULD PROVE ON SQLITE: NOTHING, AND FOR TWO DIFFERENT
REASONS.** The isolation case would pass with no policies in force at all,
because SQLite has none. The dry-promise case counts rows in tables whose
triggers and constraints only exist on PostgreSQL. The difference is the point.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.runbooks import models, services
from apps.runbooks.definitions import bank_reconciliation as br
from apps.runbooks.definitions import cash_application as ca
from apps.runbooks.engine import executor
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

pytestmark = [pytest.mark.django_db, requires_postgres]

#: One cheque per line, in the column names `lockbox.REMITTANCE_COLUMN_ALIASES`
#: accepts. The header is NAMED and never positional: a file whose columns
#: cannot be named is refused rather than half-understood (`BR-PAY-023`).
REMITTANCE = (
    "account_ref,payer_name,amount,paid_on,reference\n"
    "{account},Alvarez M,182.40,2026-09-05,88213\n"
    ",Nobody At All,60.00,2026-09-05,88240\n"
    "NOT-A-REAL-ACCOUNT,Okonkwo D,1204.05,2026-09-05,88199\n"
)


def _runbook(tenant, definition):
    """The runbook row, written the way the product writes it.

    `cap` is typed rather than defaulted: `OQ-RBS-1731` CLOSED on 2026-09-06 at
    **100**, and `runbooks.cap` still has NO column default — wave `L4` carries
    that change, and a fixture that pre-empted it would hide the gap.
    """
    return models.Runbook.objects.create(
        tenant=tenant,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
        template_key=definition.key,
        timezone="America/Chicago",
        gate_mode="approve_each_run",
        cap=100,
    )


def _an_account(tenant, *, account_no="A-11488"):
    """One account for the file's first cheque to name.

    ⚠ **THE `brazos` FIXTURE PROVISIONS A TENANT AND SEEDS NO ACCOUNTS**, which
    the first version of this file assumed it did — three cases died on
    `'NoneType' object has no attribute 'account_no'`. The account is built here
    the way `test_br_cus_107` builds one, through `customers`' own models, so a
    reader can see exactly how thin the fixture is.
    """
    from apps.customers import models as customers_models
    from apps.metering import models as metering_models

    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="1408 Elm St", city="Katy", state="TX"
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, label="Unit A"
    )
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        account_no=account_no,
        status=customers_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customers_models.AccountType.objects.get(code="residential"),
    )


def _stage_a_file(actor, tenant) -> str:
    """A remittance file, staged and validated through `payments`' OWN path.

    ⚠ **NOT INSERTED.** A fixture that wrote `PaymentImportRow` rows directly
    would let this file pass over a broken matcher — and the matcher is exactly
    what runbook 10 reads. `stage_import` parses the bytes and `validate_batch`
    walks the ladder, so the match states these cases assert on are the
    product's own.
    """
    from apps.payments import payment_import

    account = _an_account(tenant)
    payload = REMITTANCE.format(account=account.account_no).encode("utf-8")
    staged = payment_import.stage_import(
        actor, file_name="lockbox-2026-09-05.csv", payload=payload, source_kind="lockbox"
    )
    payment_import.validate_batch(actor, batch_id=staged.batch_id)
    return staged.batch_id


# ── the stop, on the vendor that will run it ──────────────────────────────


def test_no_connection_and_no_file_stops_the_run_through_the_real_seams(brazos, dana):
    """PO ruling 2026-09-06 — *"that is a valid case and state for us"*.

    ⚠ **NOTHING IS MOCKED HERE.** `integrations_seam.live_connections` really
    asks `apps.integrations.selectors.grid` for this tenant's connections and
    really gets none; `payments_seam.import_batch` really asks `payments` for a
    batch that is not there. **This is the screen a real utility meets first**,
    and it is a designed answer rather than a crash.
    """
    with live_tenant_context(brazos.id):
        runbook = _runbook(brazos, ca.RUNBOOK)
        run = services.open_run(runbook, ca.RUNBOOK)
        result = executor.execute(
            ca.RUNBOOK, tenant_id=brazos.id, run_id=run.pk, params={"batch": None}
        )
        closed = services.close_run(run, result, status=models.RUN_STATUS_STOPPED)

    assert closed.status == models.RUN_STATUS_STOPPED
    stop = result.set_results[ca.STEP_SOURCE]["stop"]
    assert stop["headline"] == "Nothing to work on."
    assert "No payment connection is set up." in stop["detail"]
    blocks = {block["block"]: block["payload"] for block in closed.report}
    assert [cell["state"] for cell in blocks["chain"]["cells"]] == ["bad"] + ["notReached"] * 6
    assert "kpis" not in blocks


def test_bank_reconciliation_stops_the_same_way(brazos, dana):
    """The sibling, and the reason both are in one file: they are one shape."""
    with live_tenant_context(brazos.id):
        runbook = _runbook(brazos, br.RUNBOOK)
        run = services.open_run(runbook, br.RUNBOOK)
        result = executor.execute(
            br.RUNBOOK, tenant_id=brazos.id, run_id=run.pk, params={"statement": None}
        )
        closed = services.close_run(run, result, status=models.RUN_STATUS_STOPPED)

    assert closed.status == models.RUN_STATUS_STOPPED
    stop = result.set_results[br.STEP_SOURCE]["stop"]
    assert stop["headline"] == "Nothing to reconcile."
    blocks = {block["block"]: block["payload"] for block in closed.report}
    assert [cell["state"] for cell in blocks["chain"]["cells"]] == ["bad"] + ["notReached"] * 5


# ── the money path, through the real matcher ──────────────────────────────


def test_a_real_uploaded_file_is_matched_planned_and_nothing_is_applied(brazos, dana):
    """The whole deliverable, end to end, with nothing replaced.

    A three-row lockbox file: one row naming a real account, one naming nothing
    at all, one naming an account this utility does not hold. `payments`' own
    ladder decides all three and runbook 10 reports them.

    ⚠ **AND THE ASSERTION THAT MATTERS IS THE LAST ONE: NOTHING IS APPLIED.**
    Every run of a money-bearing action needs a second person (`BR-RBS-018`,
    CONFIRMED 2026-09-06 with no threshold), and no writer is bound to
    `apply_payment` until wave `L2`.
    """
    with live_tenant_context(brazos.id):
        batch_id = _stage_a_file(dana, brazos)
        runbook = _runbook(brazos, ca.RUNBOOK)
        run = services.open_run(runbook, ca.RUNBOOK)
        result = executor.execute(
            ca.RUNBOOK,
            tenant_id=brazos.id,
            run_id=run.pk,
            params={
                "batch": batch_id,
                # ⚠ **THE THRESHOLD IS RAISED SO THE HAPPY PATH CAN HAPPEN, AND
                # SAYING SO IS THE POINT.** This tenant's account has no open
                # bills, so a $182.40 cheque against it IS an overpayment and
                # the runbook correctly refuses to plan it — which would leave a
                # fixture in which NOTHING is ever planned, where a broken plan
                # looks exactly like a working one (hard-won law 7 at the
                # fixture layer). `overpayment_over` is the card's own
                # parameter, and the case below leaves it at its default and
                # asserts the refusal instead.
                "overpayment_over": "5000.0000",
            },
        )
        closed = services.close_run(run, result)

    assert len(result.subjects) == 3
    outcomes = [record.outcome for record in result.records]
    assert outcomes.count(ca.OUTCOME_PLANNED) == 1
    assert outcomes.count(ca.OUTCOME_NEEDS_A_PERSON) == 2
    assert all(
        record.reason == "Waiting for a second person to approve this run."
        for record in result.records
        if record.outcome == ca.OUTCOME_PLANNED
    )
    blocks = {block["block"]: block["payload"] for block in closed.report}
    assert blocks["breakdown"]["rows"][0]["cells"]["source"]["text"] == "Lockbox"
    assert blocks["breakdown"]["rows"][0]["cells"]["landed"]["text"] == "3"
    assert blocks["records"]["total"] == 2


def test_the_run_writes_nothing_outside_the_seven_runbooks_tables(brazos, dana):
    """The dry promise, counted rather than asserted (`BR-RBS-003`).

    ⚠ **THIS IS THE ONE CASE THAT WOULD CATCH A BOUND WRITER ARRIVING BY
    ACCIDENT.** `G115` proves no foreign ORM write is WRITTEN in this module;
    this proves none HAPPENS when the module runs, which is a different claim
    and the one a utility cares about. `payments` and `allocations` are counted
    because they are what `apply_payment` would touch.
    """
    with live_tenant_context(brazos.id):
        batch_id = _stage_a_file(dana, brazos)
        before = _counts()
        runbook = _runbook(brazos, ca.RUNBOOK)
        run = services.open_run(runbook, ca.RUNBOOK)
        result = executor.execute(
            ca.RUNBOOK,
            tenant_id=brazos.id,
            run_id=run.pk,
            params={"batch": batch_id, "overpayment_over": "5000.0000"},
        )
        services.close_run(run, result)
        after = _counts()

    assert after == before, f"the run wrote outside its own tables: {before} → {after}"


def test_an_overpayment_is_refused_at_the_declared_threshold(brazos, dana):
    """The other half of the case above, and the reason it may raise the knob.

    Left at its default of **$50.00**, the same cheque against an account with
    nothing open is an OVERPAYMENT and the runbook refuses to plan it — *"over-
    and short-payments flagged, never guessed"* (`RB-110`). Two cases over one
    file, differing only in the parameter, is what makes the raised threshold in
    the sibling case a knob rather than a way of hiding a refusal.
    """
    with live_tenant_context(brazos.id):
        batch_id = _stage_a_file(dana, brazos)
        runbook = _runbook(brazos, ca.RUNBOOK)
        run = services.open_run(runbook, ca.RUNBOOK)
        result = executor.execute(
            ca.RUNBOOK, tenant_id=brazos.id, run_id=run.pk, params={"batch": batch_id}
        )

    outcomes = [record.outcome for record in result.records]
    assert outcomes == [ca.OUTCOME_NEEDS_A_PERSON] * 3
    over = [r for r in result.records if "more than this account owes" in r.reason]
    assert len(over) == 1, [r.reason for r in result.records]
    # Hard rule 2's display half: TWO decimals and a CHAR(3) code in a sentence
    # a clerk reads, never the stored six-place value.
    assert "182.40 USD" in over[0].reason, over[0].reason


#: The tables an Action could reach if a writer were bound. Named rather than
#: derived, because the question is *did the ports fire*, not *did anything at
#: all move* — the second would count Django's own bookkeeping as a breach.
WATCHED = (
    "payments",
    "allocations",
    "payment_import_rows",
    "payment_import_batches",
    "bank_lines",
    "deposit_batches",
    "journal_lines",
)


def _counts() -> dict[str, int]:
    """Row counts for the watched tables — **asking the catalogue first.**

    ⚠⚠ **THE FIRST VERSION OF THIS FUNCTION WAS HARD-WON LAW 14, IN THE FILE
    WRITTEN TO PROVE HARD-WON LAW 14.** It did `try: SELECT count(*) FROM
    <table> except Exception: continue`, so a table this build does not have
    raised — and on PostgreSQL **one failed statement aborts the whole
    transaction**. Every later count, the test's own writes and its teardown
    then died with `InFailedSqlTransaction`, and TWO unrelated cases failed with
    an error that named none of this. On SQLite it would have passed.

    The fix is not a savepoint — it is not to fail at all. One query to
    `information_schema` says which of the watched tables exist, and nothing
    after it can raise.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            [list(WATCHED)],
        )
        present = [row[0] for row in cursor.fetchall()]
        counts: dict[str, int] = {}
        for table in present:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — from the catalogue
            counts[table] = cursor.fetchone()[0]
    return counts


# ── the tenant boundary, enforced by the database ─────────────────────────


def test_another_tenants_file_is_invisible_and_the_run_stops(brazos, dana, lonestar, erin):
    """Hard rule 1, proved where the guarantee actually lives.

    Lone Star Ridge starts cash application with **Brazos Bend's batch id**. RLS
    is `FORCE`d, so the read returns nothing; the seam turns that into an
    absence rather than a traceback, and the run STOPS with the ordinary
    *nothing to work on* sentence.

    ⚠ **THE STOP IS THE PROOF AND ALSO THE HAZARD, SO BOTH ARE ASSERTED.** A
    runbook that reported *"no file"* for a file it was merely not allowed to
    see is correct — the two must be indistinguishable (`G4`) — but it means a
    test could pass because the id was mistyped. So the same id is read back
    successfully in Brazos Bend's own context in the same case: the batch
    exists, and only the tenant boundary hides it.
    """
    with live_tenant_context(brazos.id):
        batch_id = _stage_a_file(dana, brazos)

    with live_tenant_context(lonestar.id):
        runbook = _runbook(lonestar, ca.RUNBOOK)
        run = services.open_run(runbook, ca.RUNBOOK)
        intruder = executor.execute(
            ca.RUNBOOK, tenant_id=lonestar.id, run_id=run.pk, params={"batch": batch_id}
        )

    assert intruder.subjects == ()
    assert intruder.set_results[ca.STEP_SOURCE]["stop"]["headline"] == "Nothing to work on."
    assert intruder.set_results[ca.STEP_SOURCE]["checked"]["file_uploaded"] is False

    # The other half: the very same id IS readable by its owner, so the empty
    # answer above is the boundary and not a bad id.
    with live_tenant_context(brazos.id):
        owner = executor.execute(
            ca.RUNBOOK, tenant_id=brazos.id, run_id=None, params={"batch": batch_id}
        )
    assert len(owner.subjects) == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-022 · US-RBS-026 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
