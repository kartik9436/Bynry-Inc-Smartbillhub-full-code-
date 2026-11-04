# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (Send) — clerk check F4, second half
# Checks:   04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md F4
#           (*"two Sends cannot both issue"*)
# Defect:   DEF-BIL-8512 (the second half had guards and no proof on PostgreSQL)
# Rules:    CLAUDE.md hard rules 4 (an issued bill is never issued again) and 6
#           (idempotency) · hard-won law 14 (a row lock means nothing on SQLite)
# ───────────────────────────────────────────────────────
"""Two clerks press Send on the same signed-off run at the same moment.

**What must happen, and it is the whole of F4's second half:** every bill is
issued ONCE — one `issued` status, one journal entry, one invoice number — and
the Send that lost the race files nothing as *not sent*. The guard is the row
lock `issue.issue_invoice` takes on each draft (`select_for_update`, then the
status check on the LOCKED row), and `release.record_send_breaks`, which skips a
"break" whose bill is no longer a draft.

**POSTGRESQL ONLY, AND A REAL RACE.** SQLite has no row locks — `select_for_update`
is a no-op there — so on the default suite this would prove nothing; it is
skipped there, and the first case states the vendor so a skip cannot read as a
pass (law 7). Two threads, two connections, each running the product's own
`release.release_run`, released together by a barrier.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest
from django.db import connection, connections

from apps.billing import models as billing_models
from apps.billing import release

from tests.isolation_helpers import requires_postgres  # noqa: F401
from tests.test_def_bil_5352_run_status_machine import a_releasable_run, authorise
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

#: `serialized_rollback=True` for the reason `test_invoice_cloud_make_payment_pg`
#: gives: a transactional case tears down by FLUSHING the platform seed.
_TRANSACTIONAL = pytest.mark.django_db(transaction=True, serialized_rollback=True)

SENT_AT = datetime(2026, 10, 1, 9, 45, tzinfo=UTC)


@requires_postgres
@pytest.mark.django_db
def test_f4_this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


# BULK-CHG-40
@requires_postgres
@_TRANSACTIONAL
def test_f4_two_sends_pressed_together_issue_every_bill_once(brazos, dana):
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=4, key="2026-06|f4-race")
        row = authorise(run, dana)
        drafts = list(billing_models.Invoice.objects.filter(bill_run=run).values_list("pk", flat=True))

    barrier = threading.Barrier(2)
    outcomes: list[dict] = []

    def send() -> None:
        try:
            with tenant_ctx(brazos):
                fresh_run = billing_models.BillRun.objects.get(pk=run.pk)
                fresh_row = billing_models.BillRunRelease.objects.get(pk=row.pk)
                barrier.wait(timeout=30)
                done = release.release_run(
                    bill_run=fresh_run,
                    release_row=fresh_row,
                    released_at=SENT_AT,
                    issued_at=SENT_AT,
                    template_id=TEMPLATE_ID,
                    template_version=TEMPLATE_VERSION,
                    actor=dana.user,
                )
                outcomes.append(
                    {"issued": list(done.issued.issued), "broken": len(done.issued.broken)}
                )
        except Exception as exc:  # reported, never swallowed
            outcomes.append({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            connections.close_all()

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not any(thread.is_alive() for thread in threads), "a Send never finished"

    with tenant_ctx(brazos):
        statuses = list(
            billing_models.Invoice.objects.filter(pk__in=drafts).values_list("status", flat=True)
        )
        from apps.ledger import models as ledger_models

        entries = {
            str(pk): ledger_models.JournalEntry.objects.filter(
                source_type="invoice", source_id=pk
            ).count()
            for pk in drafts
        }
        send_breaks = billing_models.BillRunBreak.objects.filter(
            bill_run=run, stage=billing_models.BREAK_STAGE_SEND
        ).count()
    issued_by_either = [one for outcome in outcomes for one in outcome.get("issued", [])]
    # A Send that arrives after the other has finished is REFUSED at the gate
    # (the release is stamped) — the other lawful ending of the race.
    refused = [o["error"] for o in outcomes if "error" in o]
    assert all("no authorised release" in text for text in refused), refused
    print(f"\nPROOF F4 two Sends: outcomes={outcomes} entries={entries} send_breaks={send_breaks}")
    # Each bill went ONCE, whichever Send issued it.
    assert sorted(issued_by_either) == sorted(str(pk) for pk in drafts)
    assert set(statuses) == {billing_models.INVOICE_ISSUED}
    assert set(entries.values()) == {1}, entries
    # And the Send that met them already issued filed nothing as "not sent".
    assert send_breaks == 0
