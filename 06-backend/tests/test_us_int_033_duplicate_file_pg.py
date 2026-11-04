# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-033 (EP-INT-09) TC-1 — the same bank file twice, on a real
#           PostgreSQL. **`CR-069` §12's phase-4 exit test.** Screens: S142
# Rules:    BR-INT-020 C (the content hash is computed BEFORE parse) ·
#           BR-INT-023 · BR-INT-039 (a finished run is append-only — a TRIGGER,
#           which SQLite does not have and never will) · CLAUDE.md hard rule 1
#           (RLS FORCE, proved under the non-superuser probe role) · hard rule
#           6 (idempotency by unique key) · hard-won law 14
# Tests:    this file. The SQLite half is
#           tests/test_us_int_033_duplicate_file.py
# Impacts:  apps/integrations/arrivals.py · services.py
# ───────────────────────────────────────────────────────
"""US-INT-033 on PostgreSQL — the phase-4 exit test, and the guarantees SQLite cannot express.

    10-scripts/proof-db.sh clone int_i
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_int_i \\
        pytest tests/test_us_int_033_duplicate_file_pg.py

⚠ WHY THIS FILE EXISTS, AND IT IS HARD-WON LAW 14 WORD FOR WORD.
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`.
The SERVICE refuses a duplicate on every vendor and the SQLite suite proves
that much. It proves NOTHING about:

  * the **append-only trigger** on a finished run — the shape a migration, a
    psql session or a well-meaning data fix takes. SQLite carries no trigger,
    so a hand-written `UPDATE integration_run SET input_hash = NULL` succeeds
    there and would launder a duplicate into a fresh file.
  * **RLS `FORCE`** — that one utility's bank file is invisible to another.
    SQLite has no row-level security at all, so the isolation half of this
    guarantee is *structurally incapable of being tested* on the default suite.

Every case SKIPS rather than passing vacuously when the vendor is not
PostgreSQL, so a green run of the default suite never claims either.
"""

from __future__ import annotations

import hashlib

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import arrivals, models
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

BANK = "bank_lockbox_file"
LOCKBOX = "import_lockbox"

TUESDAY = b"6,121000248,0000123456,260901,0610,USD,2/\n16,175,0000004250,,A-10432/\n"
WEDNESDAY_RECUT = b"6,121000248,0000123456,260901,0611,USD,2/\n16,175,0000004250,,A-10432/\n"


def _bank_connection(tenant, label="Chase lockbox"):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=BANK,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config={"source": "upload"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — THE PHASE-4 EXIT TEST, on real PostgreSQL, with its control case.
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_tc1_exit_test_the_byte_identical_file_is_refused_naming_the_first(brazos):
    """Tuesday's file, Wednesday's identical upload, and a different file.

    THREE STEPS, AND THE THIRD IS WHAT MAKES THE SECOND MEAN ANYTHING:
      1. Tuesday's file arrives and is ACCEPTED.
      2. The byte-identical file arrives and is REFUSED, naming the first by
         day and time, with `input_hash` equal on both rows.
      3. A file one byte different arrives and is ACCEPTED — because *nothing
         was written* also describes an endpoint that is simply broken, and
         without this step the two are indistinguishable.
    """
    with live_tenant_context(brazos.id):
        connection_row = _bank_connection(brazos)

        first = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=TUESDAY
        )
        assert first.accepted is True
        assert first.run.input_hash == hashlib.sha256(TUESDAY).hexdigest()

        second = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=TUESDAY
        )
        assert second.accepted is False, "the same bytes twice must be refused"
        assert second.run.input_hash == first.run.input_hash
        assert second.duplicate_of is not None
        assert second.duplicate_of.id == first.run.id
        assert "refused duplicate" in (second.run.summary or "")
        assert first.run.started_at.strftime("%A") in (second.run.summary or "")
        assert second.run.outcome == models.OUTCOME_SKIPPED
        #: nothing was parsed and nothing was handed on
        assert second.run.attempted == 0
        assert second.run.succeeded == 0

        #: THE CONTROL — a genuinely different file is still taken
        different = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=WEDNESDAY_RECUT
        )
        assert different.accepted is True, (
            "a one-byte difference is a NEW file; without this the refusal above "
            "is indistinguishable from an endpoint that refuses everything"
        )
        assert different.run.input_hash != first.run.input_hash

        #: three arrivals, three rows — the refused one is RECORDED, not lost
        rows = models.IntegrationRun.objects.filter(
            tenant_id=brazos.id, connection_id=connection_row.id
        )
        assert rows.count() == 3


@requires_postgres
@pytest.mark.django_db
def test_the_hash_was_computed_before_parsing_asserted_by_ordering(brazos):
    """The refused run spent NO parse work — it has a hash and nothing else.

    On the refused arrival the digest is present, the counts are all zero and
    no item was recorded. A run that had parsed the file before discovering it
    was a duplicate would have something to show for it.
    """
    with live_tenant_context(brazos.id):
        connection_row = _bank_connection(brazos)
        arrivals.record_arrival(connection=connection_row, operation=LOCKBOX, body=TUESDAY)
        second = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=TUESDAY
        )

        assert second.run.input_hash, "the hash exists on the refused run too"
        assert second.run.attempted == 0
        assert second.run.succeeded == 0
        assert second.run.failed == 0
        assert second.run.items in ([], None), "no per-item work was done"


# ═══════════════════════════════════════════════════════════════════════════
# The append-only trigger — the guarantee SQLite has no way to carry.
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_a_hand_written_update_cannot_launder_a_duplicate(brazos):
    """`UPDATE integration_run SET input_hash = NULL` on a finished run → refused.

    ⚠ THIS IS THE ATTACK THE TRIGGER EXISTS FOR AND SQLITE CANNOT SEE IT. The
    service will not blank the column, and a data fix run in psql does not go
    through the service. If the row were mutable, clearing one hash would make
    a bank file we have already applied look new — and it would be applied
    twice, which is the exact failure hard rule 6 names.
    """
    with live_tenant_context(brazos.id):
        connection_row = _bank_connection(brazos)
        first = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=TUESDAY
        )
        #: close it the way the processing half would
        arrivals.close_arrival(
            first, attempted=40, succeeded=38, failed=2, skipped=0, summary="handed on"
        )

        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        "UPDATE integration_run SET input_hash = NULL WHERE id = %s",
                        [str(first.run.id)],
                    )

    #: and the refusal still stands afterwards
    with live_tenant_context(brazos.id):
        again = arrivals.record_arrival(
            connection=connection_row, operation=LOCKBOX, body=TUESDAY
        )
        assert again.accepted is False


# ═══════════════════════════════════════════════════════════════════════════
# Hard rule 1 — one utility's bank file is invisible to another.
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_another_utilitys_arrival_is_invisible_under_the_probe_role(brazos, lonestar, rls):
    """Under a NON-SUPERUSER role, RLS FORCE hides the other tenant's run rows.

    ⚠ THE PROBE ROLE IS THE POINT. `smartbillhub` is a superuser on this
    deployment and a superuser BYPASSES every policy — a check run as that role
    would report isolation it never tested (law 7's *incapable of failing*).
    `rls` refuses to run rather than skip if the role it is handed can bypass.
    """
    with live_tenant_context(brazos.id):
        ours = _bank_connection(brazos)
        mine = arrivals.record_arrival(connection=ours, operation=LOCKBOX, body=TUESDAY)
    with live_tenant_context(lonestar.id):
        theirs = _bank_connection(lonestar, label="Lone Star lockbox")
        yours = arrivals.record_arrival(connection=theirs, operation=LOCKBOX, body=TUESDAY)

    #: identical bytes, identical digest, two unrelated files
    assert mine.run.input_hash == yours.run.input_hash
    assert yours.accepted is True, "another utility's file is not our duplicate"

    #: and neither tenant can SEE the other's row
    assert_rls_scoped(
        rls,
        "integration_run",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(mine.run.id)},
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-033 (EP-INT-09) + BR-INT-020 C + BR-INT-023 + BR-INT-039 +
#         BR-INT-054 as amended 2026-09-06 (CR-069 §20.4 wave I)
# generated: 2026-09-06 by the CR-069 wave I build lane
# gates: DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
#        DATABASE_URL=… pytest tests/test_us_int_033_duplicate_file_pg.py
# exceptions: skips entirely on SQLite, by design — see the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
