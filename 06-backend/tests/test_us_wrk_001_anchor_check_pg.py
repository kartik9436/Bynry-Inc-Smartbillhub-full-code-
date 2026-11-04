# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-001 (EP-WRK-01) TC-6 — the CHECK is asserted on real
#           PostgreSQL 16, around the ORM, with the constraint's own name read
#           back out of the refusal.
# Rules:    BR-WRK-006 (at least one anchor, refused by the DATABASE) ·
#           CLAUDE.md hard-won law 14 (the suite runs on SQLite; a proof about
#           the real database runs on the real database) · hard rule 1 (the
#           INSERT runs under the tenant's context)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""US-WRK-001 TC-6 — `ck_work_orders_has_anchor`, on PostgreSQL.

Run it with a real database:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_us_wrk_001_anchor_check_pg.py

`test_us_wrk_001_anchors.py` proves the same constraint through the ORM on the
suite's SQLite. This file INSERTs with a cursor — the shape a migration, a
backfill or a bulk loader would use — so nothing Django adds between the call
and the table can be what refused it, and asserts the constraint's NAME in
PostgreSQL's own message.

⚠ **BOTH INSERTS NAME `dispatch_state` EXPLICITLY, AND THAT IS NOT TIDINESS —
IT IS THE REPAIR FOR `DEF-WRK-4033` (2026-09-05).** Wave G's `metering/0050`
added `dispatch_state` NOT NULL, and a raw-cursor INSERT gets **no Django model
default**: the row was refused by the NOT NULL constraint before it could ever
reach `ck_work_orders_has_anchor`, so the negative test above went red asserting
a constraint name against the message *"null value in column dispatch_state
… violates not-null constraint"*.

**The failure was invisible for a day and the reason generalises: this file is
PostgreSQL-only, so the ordinary suite SKIPS it** — and `DEF-GOV-4024` (filed
the same day) shows the tenant-isolation gate running that suite on SQLite and
reporting PASS with 192 of 238 proofs skipped. A test that only runs on the real
database is exactly the test a wave adding a NOT NULL column will not see go
red. **The lesson for a lane adding a NOT NULL column: grep for raw
`INSERT INTO <table>` before you add it**, because the ORM's default protects
every caller except the ones that bypass the ORM — which is precisely the set
this kind of file is written to cover.
"""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


@requires_postgres
def test_us_wrk_001_tc6_the_check_refuses_an_unanchored_row_on_postgresql(dana, brazos):
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO work_orders
                            (id, tenant_id, order_no, type, scope, state, mode, is_gate,
                             is_sample, dispatch_state, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, false, false, 'queued',
                                now(), now())
                        """,
                        [
                            str(uuid.uuid4()),
                            str(brazos.id),
                            "WO-0",
                            "floating",
                            "per_premise",
                            "planned",
                            "our_crew",
                        ],
                    )
    message = str(refused.value)
    assert "ck_work_orders_has_anchor" in message, message
    assert "check constraint" in message.lower(), message


@requires_postgres
def test_us_wrk_001_tc6_the_same_insert_with_a_premises_is_accepted(dana, brazos):
    """The negative above proves the CHECK; this proves it is the CHECK and not
    something else refusing the row — the identical INSERT with one anchor lands."""
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_premises

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="77 Cedar Ct")
        assert metering_models.Premises.objects.filter(pk=premises["id"]).exists()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO work_orders
                        (id, tenant_id, order_no, type, scope, state, mode, is_gate,
                         is_sample, dispatch_state, premises_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, false, false, 'queued', %s,
                            now(), now())
                    """,
                    [
                        str(uuid.uuid4()),
                        str(brazos.id),
                        "WO-1",
                        "Leak investigation",
                        "per_premise",
                        "planned",
                        "our_crew",
                        premises["id"],
                    ],
                )
                cursor.execute(
                    "SELECT count(*) FROM work_orders WHERE order_no = %s AND connection_id IS NULL",
                    ["WO-1"],
                )
                assert cursor.fetchone()[0] == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-001@87b94265 (EP-WRK-01 §3 TC-6) · BR-WRK-006 · metering/0044
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: run on PostgreSQL 16 (sbh_cr070a) by the lane; CI's "PostgreSQL-only proofs (law 14)" step picks up every tests/test_*_pg.py
# exceptions: skips on SQLite by design (law 14) — the skip reason names why
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
