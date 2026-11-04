# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10147 — G3 (PO 2026-10-14): a correction case takes its
#           number at Send from the tenant's Correction case series.
# Rules:    BR-TEN-035 (`SELECT … FOR UPDATE` on the series row; a number is
#           never reused) · hard-won law 14 (a row lock means nothing on SQLite)
# ───────────────────────────────────────────────────────
"""Two clerks press Send on two different customers at the same moment.

**What must happen:** both cases open, and they hold DIFFERENT numbers —
CC-2026-001 and CC-2026-002, in whichever order the lock hands them out. The
guard is `tenancy.services.allocate_series_number`'s row lock on the tenant's
`correction_case` series, taken inside each Send's own transaction
(`correction_items._open_case`); the partial unique index
`(tenant, case_no) WHERE case_no IS NOT NULL` is the backstop.

**POSTGRESQL ONLY, AND A REAL RACE.** Two threads, two connections, each running
the product's own `correction_items.open_at_send`, released together by a
barrier. On SQLite this is skipped and the first case states the vendor, so a
skip cannot read as a pass (law 7).

RED FIRST, with the row lock taken out of `allocate_series_number` (and a
one-second pause so the two Sends overlap), verbatim:

    PROOF two concurrent Sends: [{'case_no': 'CC-2026-001'}, {'error':
    'IntegrityError: duplicate key value violates unique constraint
    "uq_correction_cases_no" … (tenant_id, case_no)=(…, CC-2026-001) already exists.'}]

— both Sends drew 001; the backstop index refused the second, which is a Send
lost, not a number shared. With the lock: CC-2026-001 and CC-2026-002.

    cd 06-backend && CELERY_BROKER_URL=memory:// JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest -q tests/test_def_bil_10147_correction_case_numbers_pg.py \\
      --ds=config.settings.pgtest --create-db
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection, connections, transaction

from apps.billing import correction_items
from apps.billing.correction_models import CorrectionCase

from tests.isolation_helpers import requires_postgres  # noqa: F401
from tests.test_cr180_fix_a_bill_revamp import (  # noqa: F401 — the autouse template pin
    AS_OF,
    _one_customer,
    _preview,
    _the_rebill_template,
)
from tests.test_def_bil_10091_bulk_fix_jobs import ITEMS, _three_bills
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

_TRANSACTIONAL = pytest.mark.django_db(transaction=True, serialized_rollback=True)


@requires_postgres
@pytest.mark.django_db
def test_this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


@requires_postgres
@_TRANSACTIONAL
def test_two_sends_pressed_together_never_share_a_number(brazos, dana):
    # The fixture issues bills through the number kernel, whose row lock needs a
    # transaction; a transactional test runs in autocommit, so it is given one.
    with transaction.atomic():
        world = _three_bills(brazos, dana)
    sends = []
    for one in (world.first, world.second):
        scope = _one_customer(one)
        preview = _preview(brazos, dana, scope, ITEMS)
        assert preview.status_code == 200, preview.data
        sends.append((scope, preview.data["preview_hash"]))

    barrier = threading.Barrier(2)
    outcomes: list[dict] = []

    def send(scope, preview_hash) -> None:
        try:
            with tenant_ctx(brazos):
                barrier.wait(timeout=30)
                case = correction_items.open_at_send(
                    scope, ITEMS, as_of=AS_OF, preview_hash=preview_hash, actor=dana
                )
                outcomes.append({"case_no": case.case_no})
        except Exception as exc:  # reported, never swallowed
            outcomes.append({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            connections.close_all()

    threads = [threading.Thread(target=send, args=args) for args in sends]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
    assert not any(thread.is_alive() for thread in threads), "a Send never finished"
    print(f"\nPROOF two concurrent Sends: {outcomes}")
    assert [o for o in outcomes if "error" in o] == []
    assert sorted(o["case_no"] for o in outcomes) == ["CC-2026-001", "CC-2026-002"]
    with tenant_ctx(brazos):
        assert sorted(CorrectionCase.objects.values_list("case_no", flat=True)) == [
            "CC-2026-001",
            "CC-2026-002",
        ]
