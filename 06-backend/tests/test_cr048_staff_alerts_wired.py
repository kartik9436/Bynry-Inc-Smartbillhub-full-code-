# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (the bill run's phase 5) × US-PAY-021 (the statement
#           import) × US-NOT-018 (ONE message per bulk action)
#           CR-048 wave B follow-up — B4's two entry points get their callers
#           Screens: S31 step 6 · S38 step 2 · shell-chrome (the bell) · S8
# Rules:    BR-NOT-020 (one message per bulk action, whatever the item count) ·
#           BR-NOT-021 (the ruled staff audience) · BR-NOT-019 (in-app is the
#           one channel that delivers) · BR-NOT-017 (the rule the queue reads) ·
#           BR-BIL-055 (a break never blocks the release) · BR-PAY-019 (what
#           auto-match may and may not decide) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           hard-won law 2 (built is not wired — this file IS the wiring proof)
# ───────────────────────────────────────────────────────
"""CR-048 wave B, the half that was missing: **the two staff alerts have callers.**

The wave-B lane said it plainly in its own report — *"Neither named entry point
has a caller yet … So 'visibly working from day one' is half true."* This file
is the other half. A clerk releases a bill run and a message appears in their
bell; a clerk imports a bank statement and a message appears in their bell.

FOUR THINGS EACH CALL SITE HAS TO PROVE, and each has its own case:

**1 · ONE message per run, however many records it touched.** A run over N
accounts is ONE row reading *"N processed · M failed"*. That is a ruling
(BR-NOT-020) and not an optimisation, so it is asserted as a COUNT — a shape
assertion passes on a hundred rows that all look right.

**2 · The run is never lost to a notification problem.** ⚠ **AND CATCHING THE
EXCEPTION IS NOT ENOUGH ON POSTGRESQL.** A statement that errors inside a
Postgres transaction aborts the whole transaction, so a caught exception still
loses the work at COMMIT. Both seams give the call its OWN savepoint, and the
`@requires_postgres` cases below drive a REAL database error (`SELECT 1/0`)
through the summary path and then read the run back in a new transaction. On
SQLite those cases skip, which is exactly why they are marked.

**3 · A utility that switched the alert off gets no row**, and the run still
completes normally — CR-048's headline on the one channel where a person can
watch it happen.

**4 · The message lands in the bell.** Queued is not delivered. Every headline
case runs a real dispatch cycle and asserts the unread count goes 0 → 1.

NOTHING HERE SENDS ANYTHING TO ANYBODY OUTSIDE THIS BUILDING: every dispatch
restricts itself to `in_app`, the platform's own adapter.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.billing import release
from apps.billing import run_alert_seam as billing_alert_seam
from apps.notifications import bulk_summary, dispatcher, in_app
from apps.notifications import models as notification_models
from apps.notifications import rule_catalog, rule_service, seed_templates
from apps.payments import bankrec_models as bankrec
from apps.payments import reconciliation
from apps.payments import run_alert_seam as payments_alert_seam

from tests.isolation_helpers import requires_postgres
from tests.test_us_bil_005_issue import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_unpublished_ledger,
    electric_gl_accounts,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import a_bank_account, a_statement
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — every moment in this file is NAMED. Nothing reads a clock.
CONFIRMED_AT = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)
RELEASED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)
STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)

ALL_FIVE = release.Confirmations(
    compliance=True, email_mandate=True, sms_mandate=True, autopay_mandate=True, final=True
)

#: How many accounts the bill run bills, and how many lines the statement
#: carries. Both are >1 on purpose: at 1, "one message per run" and "one message
#: per record" are the same number and the case proves nothing.
RUN_ACCOUNTS = 3
STATEMENT_LINES = 4


# ── fixtures, in the shape each run actually happens ────────────────────────
def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=RELEASED_AT.date())


def _staff_rows(tenant):
    """Every bulk-summary queue row of a tenant. The COUNT is the assertion."""
    return notification_models.OutboundMessage.objects.filter(
        tenant=tenant, source_type="bulk_action"
    )


def _codes(problems):
    return {problem.get("code") for problem in problems}


def _details(problems):
    return " ".join(problem.get("detail", "") for problem in problems)


def a_releasable_run(tenant, dana, *, accounts=RUN_ACCOUNTS, key="2026-06|cycle-1"):
    """A bill run carrying `accounts` priced drafts that `issue_run` can issue."""
    electric_gl_accounts()  # the seeded chart splits 4100/4105
    run = a_run(tenant, key=key)
    for index in range(accounts):
        account = an_account(dana, tenant, account_no=f"A-5100{index}")
        a_priced_draft(tenant, account, run, invoice_no=f"BL-2607-00010{index}")
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
    """Phase 5 — the point a bill run finishes, and the first of the two call
    sites this file exists to prove."""
    return release.release_run(
        bill_run=run,
        release_row=row,
        released_at=RELEASED_AT,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana.user,
    )


def a_finished_bill_run(tenant, dana, *, accounts=RUN_ACCOUNTS):
    """Phases 4 and 5 for real, end to end."""
    run = a_releasable_run(tenant, dana, accounts=accounts)
    return release_the_run(run, authorise(run, dana), dana)


def import_a_statement(tenant, dana, *, lines=STATEMENT_LINES):
    """S38 steps 1–2 for real — the second call site.

    No deposit batches exist, so every line comes back unmatched. That is not a
    contrivance: it is exactly the state `reconciliation_exceptions` was named
    for, and it is what a clerk needs told.
    """
    account = a_bank_account(tenant)
    return reconciliation.import_bank_statement(
        actor=dana.user,
        bank_account_id=account.pk,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 11),
        file_name="chase-aug.csv",
        payload=a_statement(
            [
                ("2026-08-11", f"CREDIT {index}", str(Decimal("10.00") + index))
                for index in range(lines)
            ]
        ),
        imported_at=STATEMENT_AT,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE BILL RUN — `release.release_run`, the moment phase 5 finishes
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_wire__a_bill_run_puts_exactly_one_row_in_the_bell(brazos, dana):
    """**THE HEADLINE CASE, and the whole point of the task.**

    Empty bell → a real three-account bill run through `release.release_run` →
    ONE queue row → one dispatch cycle → the bell holds exactly one message
    reading *"3 processed · 0 failed"*. Nothing in that sentence is stubbed.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        assert in_app.unread_count(actor=dana.user) == 0
        assert _staff_rows(brazos).count() == 0

        outcome = a_finished_bill_run(brazos, dana)

        assert outcome.issued.issued_count == RUN_ACCOUNTS, (
            "the run itself must be unaffected by the alert — "
            f"{outcome.issued.issued_count} issued, broken={outcome.issued.broken}"
        )
        queued = _staff_rows(brazos).count()
        assert queued == 1, (
            f"a bill run over {RUN_ACCOUNTS} accounts queued {queued} staff "
            "messages. BR-NOT-020 allows exactly one, whatever the run touched — "
            "a clerk who receives one per account switches the event off, and "
            "the failure they needed to see is the one they never get."
        )
        assert billing_alert_seam.RUN_SUMMARY_QUEUED in _codes(outcome.staff_alert)
        assert in_app.unread_count(actor=dana.user) == 0, (
            "a queued message is not a delivered one — the bell stays empty "
            "until a dispatch cycle runs."
        )

        dispatcher.dispatch_cycle(
            now=RELEASED_AT, channels=(notification_models.CHANNEL_IN_APP,), actor=dana.user
        )
        assert in_app.unread_count(actor=dana.user) == 1
        items = in_app.inbox(actor=dana.user)
        assert len(items) == 1
        body = items[0].body
        assert f"{RUN_ACCOUNTS} processed · 0 failed" in body, (
            "the summary must state how many records the run touched and how "
            f"many failed, in that order. Body was: {body!r}"
        )
        assert bulk_summary.OPERATION_BILLING_RUN in body


def test_cr048_wire__broken_bills_are_counted_as_failures_not_hidden(brazos, dana, monkeypatch):
    """BR-NOT-020's other half — *"where the operation had failures it must say
    HOW MANY"* — reaching the bell from a REAL break.

    A bill that cannot issue does not block the release (BR-BIL-055); it must
    also not vanish from the summary, because a run reporting *"3 processed · 0
    failed"* over a run in which nothing issued is the failure BR-NOT-020 exists
    to prevent, in the opposite direction.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        run = a_releasable_run(brazos, dana)
        row = authorise(run, dana)
        an_unpublished_ledger(monkeypatch)  # the GL stamp cannot resolve

        outcome = release_the_run(run, row, dana)

        assert outcome.issued.issued_count == 0
        assert len(outcome.issued.broken) == RUN_ACCOUNTS
        assert _staff_rows(brazos).count() == 1

        dispatcher.dispatch_cycle(
            now=RELEASED_AT, channels=(notification_models.CHANNEL_IN_APP,), actor=dana.user
        )
        body = in_app.inbox(actor=dana.user)[0].body
        assert f"{RUN_ACCOUNTS} processed · {RUN_ACCOUNTS} failed" in body, (
            "a broken bill is a record the run TOUCHED and a record that FAILED; "
            f"it must appear in both figures. Body was: {body!r}"
        )


def test_cr048_wire__switching_the_billing_alert_off_leaves_no_row(brazos, dana):
    """CR-048's headline: the settings screen now governs a real delivery.

    And the run still completes normally — a switched-off notification is a
    utility's choice, never a fault the bill run reports as one.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        rule_service.update_rule(
            event_key=bulk_summary.EVENT_BILLING_RUN, actor=dana, enabled=False
        )

        outcome = a_finished_bill_run(brazos, dana)

        assert outcome.issued.issued_count == RUN_ACCOUNTS
        assert _staff_rows(brazos).count() == 0, (
            "the utility switched this notification off and a message was "
            "queued anyway — the defect CR-048 exists to fix."
        )
        assert billing_alert_seam.RUN_SUMMARY_SUPPRESSED in _codes(outcome.staff_alert), (
            "a suppressed message must SAY it was suppressed. A rule obeyed so "
            "quietly that the run report cannot mention it is the settings "
            "screen lying in the other direction."
        )
        assert "Settings" in _details(outcome.staff_alert)

        dispatcher.dispatch_cycle(
            now=RELEASED_AT, channels=(notification_models.CHANNEL_IN_APP,), actor=dana.user
        )
        assert in_app.unread_count(actor=dana.user) == 0


def test_cr048_wire__a_bill_run_survives_a_broken_summary(brazos, dana, monkeypatch):
    """A run that has issued its bills must not fail because a summary could not
    be queued. The plain-Python half of the guarantee; the Postgres half is the
    next case and it is the one that matters."""

    def explode(**_kwargs):
        raise RuntimeError("the summary path is broken (test)")

    monkeypatch.setattr(bulk_summary, "queue_billing_run_summary", explode)
    with tenant_ctx(brazos):
        _seeded(dana)
        outcome = a_finished_bill_run(brazos, dana)

        assert outcome.issued.issued_count == RUN_ACCOUNTS
        stored = billing_models.BillRunRelease.objects.get(pk=outcome.release_id)
        assert stored.released_at == RELEASED_AT
        assert billing_alert_seam.RUN_SUMMARY_ERROR in _codes(outcome.staff_alert)
        assert "the summary path is broken" in _details(outcome.staff_alert)


@requires_postgres
def test_cr048_wire__a_database_error_in_the_summary_cannot_lose_the_bill_run(
    brazos, dana, monkeypatch
):
    """⚠ **THIS CASE ONLY MEANS ANYTHING ON POSTGRESQL, and that is the finding.**

    A statement that errors inside a Postgres transaction ABORTS the whole
    transaction: the `except` catches the exception, the issued bills are
    already doomed, and the COMMIT fails afterwards with *"current transaction
    is aborted"*. SQLite has no such state, so a `try/except` alone passes there
    and loses five hundred issued bills here.

    So the seam wraps the call in its OWN savepoint. This drives a REAL database
    error through the summary path and then reads the bills back in a NEW
    transaction — which is the only way to prove the savepoint is doing the work
    rather than the `except`.
    """

    def bad_sql(**_kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")

    monkeypatch.setattr(bulk_summary, "queue_billing_run_summary", bad_sql)
    with tenant_ctx(brazos):
        _seeded(dana)
        outcome = a_finished_bill_run(brazos, dana)

    with tenant_ctx(brazos):
        # A NEW transaction. The point is that the release COMMITTED.
        issued = billing_models.Invoice.objects.filter(status=billing_models.INVOICE_ISSUED).count()
        assert issued == RUN_ACCOUNTS, (
            f"{issued} of {RUN_ACCOUNTS} bills survived a failed notification. "
            "Without the savepoint the aborted transaction takes the whole "
            "release with it at COMMIT."
        )
        stored = billing_models.BillRunRelease.objects.get(pk=outcome.release_id)
        assert stored.released_at == RELEASED_AT
    assert billing_alert_seam.RUN_SUMMARY_ERROR in _codes(outcome.staff_alert)


def test_cr048_wire__a_replayed_release_never_says_it_twice(brazos, dana):
    """CLAUDE.md rule 6 — the summary is keyed on the RUN's own id, so a resumed
    or retried release finds its own message and writes nothing. The DATABASE
    does the refusing, which is the only guarantee that survives a retry that
    never called the function twice at all."""
    with tenant_ctx(brazos):
        _seeded(dana)
        outcome = a_finished_bill_run(brazos, dana)
        assert _staff_rows(brazos).count() == 1

        again = bulk_summary.queue_billing_run_summary(
            run_id=outcome.bill_run_id,
            total_count=RUN_ACCOUNTS,
            failed_count=0,
            finished_at=RELEASED_AT,
            actor=dana.user,
        )
        assert again.created is False
        assert _staff_rows(brazos).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE RECONCILIATION RUN — `reconciliation.import_bank_statement`
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_wire__a_statement_import_puts_exactly_one_row_in_the_bell(brazos, dana):
    """The second call site, end to end. Four bank lines, none of them ours,
    ONE message in the bell naming all four."""
    with tenant_ctx(brazos):
        _seeded(dana)
        assert in_app.unread_count(actor=dana.user) == 0

        result = import_a_statement(brazos, dana)

        assert result.line_count == STATEMENT_LINES
        queued = _staff_rows(brazos).count()
        assert queued == 1, (
            f"{STATEMENT_LINES} bank lines queued {queued} staff messages; "
            "BR-NOT-020 allows one."
        )
        assert payments_alert_seam.RUN_SUMMARY_QUEUED in _codes(result.staff_alert)

        dispatcher.dispatch_cycle(
            now=STATEMENT_AT, channels=(notification_models.CHANNEL_IN_APP,), actor=dana.user
        )
        assert in_app.unread_count(actor=dana.user) == 1
        body = in_app.inbox(actor=dana.user)[0].body
        assert f"{STATEMENT_LINES} processed · {STATEMENT_LINES} failed" in body, (
            "every line this run could not match is an exception a clerk must "
            f"work, `not_in_our_system` included. Body was: {body!r}"
        )
        assert bulk_summary.OPERATION_RECONCILIATION in body


def test_cr048_wire__switching_the_reconciliation_alert_off_leaves_no_row(brazos, dana):
    """The same switch, the same effect, on the second event — and the import
    still lands every bank line it read."""
    with tenant_ctx(brazos):
        _seeded(dana)
        rule_service.update_rule(
            event_key=bulk_summary.EVENT_RECONCILIATION, actor=dana, enabled=False
        )

        result = import_a_statement(brazos, dana)

        assert bankrec.BankLine.objects.filter(tenant=brazos).count() == STATEMENT_LINES
        assert _staff_rows(brazos).count() == 0
        assert payments_alert_seam.RUN_SUMMARY_SUPPRESSED in _codes(result.staff_alert)

        dispatcher.dispatch_cycle(
            now=STATEMENT_AT, channels=(notification_models.CHANNEL_IN_APP,), actor=dana.user
        )
        assert in_app.unread_count(actor=dana.user) == 0


def test_cr048_wire__a_statement_import_survives_a_broken_summary(brazos, dana, monkeypatch):
    """The bank lines are the work; the summary only describes it."""

    def explode(**_kwargs):
        raise RuntimeError("the summary path is broken (test)")

    monkeypatch.setattr(bulk_summary, "queue_reconciliation_summary", explode)
    with tenant_ctx(brazos):
        _seeded(dana)
        result = import_a_statement(brazos, dana)

        assert bankrec.BankLine.objects.filter(tenant=brazos).count() == STATEMENT_LINES
        assert payments_alert_seam.RUN_SUMMARY_ERROR in _codes(result.staff_alert)
        assert "the summary path is broken" in _details(result.staff_alert)


@requires_postgres
def test_cr048_wire__a_database_error_in_the_summary_cannot_lose_the_import(
    brazos, dana, monkeypatch
):
    """The Postgres half for the second call site — same mechanism, same proof:
    a real `SELECT 1/0` inside the summary path, and the bank lines read back in
    a NEW transaction afterwards."""

    def bad_sql(**_kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")

    monkeypatch.setattr(bulk_summary, "queue_reconciliation_summary", bad_sql)
    with tenant_ctx(brazos):
        _seeded(dana)
        result = import_a_statement(brazos, dana)

    with tenant_ctx(brazos):
        landed = bankrec.BankLine.objects.filter(tenant=brazos).count()
        assert landed == STATEMENT_LINES, (
            f"{landed} of {STATEMENT_LINES} bank lines survived a failed "
            "notification. Without the savepoint the aborted transaction takes "
            "the whole import with it at COMMIT."
        )
        assert (
            bankrec.BankStatementImport.objects.filter(pk=result.statement_import_id).count() == 1
        )
    assert payments_alert_seam.RUN_SUMMARY_ERROR in _codes(result.staff_alert)


def test_cr048_wire__a_replayed_statement_summary_never_says_it_twice(brazos, dana):
    """Rule 6 on the second event: the summary is keyed on the statement
    import's own id."""
    with tenant_ctx(brazos):
        _seeded(dana)
        result = import_a_statement(brazos, dana)
        assert _staff_rows(brazos).count() == 1

        again = bulk_summary.queue_reconciliation_summary(
            run_id=result.statement_import_id,
            total_count=STATEMENT_LINES,
            failed_count=STATEMENT_LINES,
            finished_at=STATEMENT_AT,
            actor=dana.user,
        )
        assert again.created is False
        assert _staff_rows(brazos).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# 3 · BOTH SEAMS OBEY B1/B2 §2 — NEITHER MODULE IMPORTS NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "seam", (billing_alert_seam, payments_alert_seam), ids=("billing", "payments")
)
def test_cr048_wire__the_seam_resolves_notifications_by_name(seam):
    """B1/B2 §2 — a cross-module call is resolved BY NAME at call time, never by
    an import statement. Asserted on the SOURCE, because an import hidden inside
    a function still binds the two modules and still reads as absent to a grep
    of the file's import block."""
    source = inspect.getsource(seam)
    assert "from apps.notifications" not in source
    assert "import apps.notifications" not in source
    assert seam.STAFF_ALERT_MODULE == "notifications"
    assert callable(seam.entry_point())


def test_cr048_wire__both_seams_name_the_catalogue_s_event_and_not_the_cr_s():
    """⚠ The CR's own task list calls the first event `billing_run_finished`,
    which is not a row on SET-12. Both seams call a NAMED entry point, so the
    key is a symbol they resolve rather than a string they type — and the entry
    points' own keys are re-checked here at the cheapest possible moment,
    because a mistyped key refuses at the END of a thousand-account run."""
    assert bulk_summary.EVENT_BILLING_RUN in rule_catalog.EVENT_KEYS
    assert bulk_summary.EVENT_RECONCILIATION in rule_catalog.EVENT_KEYS
    assert "billing_run_finished" not in rule_catalog.EVENT_KEYS
    assert billing_alert_seam.STAFF_ALERT_WRITE == "queue_billing_run_summary"
    assert payments_alert_seam.STAFF_ALERT_WRITE == "queue_reconciliation_summary"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B follow-up (12-governance/11-change-requests.md → CR-048 · apps/notifications/bulk_summary.py the two named entry points · apps/billing/release.py release_run · apps/payments/reconciliation.py import_bank_statement)
# generated: 2026-08-30 by story-coder (CR-048 wave B wiring lane)
# checklist: A✔ B=deferred(no frontend half — the bell that READS these messages is AppShell.tsx and shipped with CR-009) C✔ D=deferred(no new HTTP surface — both call sites are reached through the release endpoint and the bank-statement import endpoint that already exist) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr048_staff_alerts_wired.py — RED PROVED FIRST against an unwired release_run / import_bank_statement and quoted in the lane report; the two Postgres cases were re-run with the savepoint removed and failed with "current transaction is aborted"
# exceptions: (1) THE RECONCILIATION RUN'S FAILURE COUNT IS `exceptions + not_in_our_system` — both are lines this run could not match and both are a clerk's to work; counting only `exceptions` would report a statement of pure unknown credits as a clean run. (2) The bill run's counts come from `IssuedRun` and never from a second count taken here (US-BIL-005's rule against two versions of "how many bills went out"). (3) The bell is asserted with `in_app.unread_count`, the very read the shell's bell calls — not by counting queue rows, which is what "queued" already proves.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
