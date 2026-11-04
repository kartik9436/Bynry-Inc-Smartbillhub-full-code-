# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-028 · US-INT-031 · US-INT-035 (CR-069 wave K) — the walk
#           collects; what it collected MEANS something to somebody else.
#           CR-069 §11: one seam file per module integrations hands to.
# Rules:    BR-INT-054 as amended 2026-09-06 (integrations builds the
#           connection, holds the keys and owns the lifecycle; business logic,
#           scheduling and processing are Runbooks') · CR-069 §20.4 wave K
#           (*"MOVES: the readings projection"*) · BR-INT-049 (a measurement
#           without its declared unit is refused by name — in the PROJECTION,
#           which is on the far side of this door) · CLAUDE.md hard rule 3
# Tests:    06-backend/tests/test_us_int_028_token_walk.py
#           (`test_the_runbooks_seam_projects_nothing_today`)
# Impacts:  apps/integrations/runners/fetch.py (the walk calls this once per
#           page and does nothing with the answer, because there is none)
# ───────────────────────────────────────────────────────
"""integrations → Runbooks: the door the collected pages leave through, and it is shut.

WHY THIS FILE EXISTS AT ALL
---------------------------
`CR-069` §20.4 splits wave K in as many words. Integrations **keeps** token
exchange in memory, the fetch plan and paging, submit–poll–collect, and the
safety parameters — *"how you talk to THIS provider"*. It **moves** the
readings projection: *"turning what was collected into our measurement frame is
ETL"*, and `BR-INT-054` puts ETL in Runbooks.

So the walk in `runners/fetch.py` asks the head-end for window 61, page 2, gets
back 4,912 records, counts them, checkpoints, and calls `project_readings`
below. **Nothing happens.** That is not an oversight and it is not a stub: the
question of who owns the projection is RULED, not open, and the answer is
Runbooks (`CR-069` §20.4, the same distinction `runners/serve.partner_fields()`
records for the outbound direction). A lane finding this should leave it alone.

⚠ **THE FUNCTION RETURNS AN EMPTY TUPLE AND A TEST ASSERTS THAT IT DOES.** That
is the only way a boundary written in prose survives contact with the next lane:
the day Runbooks plugs its projection in here, the suite goes RED and names this
paragraph, so the door cannot open silently and nobody can mistake the absence
for something nobody got round to.

WHAT A LATER LANE WILL PUT HERE, AND WHAT IT MUST NOT
------------------------------------------------------
When the Runbooks module lands, this file resolves ITS published callable by
name at CALL TIME — the idiom every other seam in this directory uses — so a
neighbour that has not published one yet answers `None` and the caller says so
honestly rather than inventing an answer (`DEF-075`'s rule). It will hand over
what integrations legitimately holds: the connection, the operation, the window
and page, and the records exactly as they arrived.

It must **not** grow the projection itself. Three things belong on the far side
of this door and none of them may creep back:

  * **the measurement frame** — `BR-INT-049` and CLAUDE.md hard rule 3: a
    numeric arriving without its declared unit is refused BY NAME rather than
    written. `US-INT-035` TC-5 is that case, and it travels with the projection;
    the REQUEST half of the same rule stays here, as the manifest's
    `unit_of_measure` safety parameter, which is why the two look alike and are
    not the same test.
  * **reconciling by natural key** — *1,240 read · 6 revised*, and a reading
    already billed never moves. That is wave L, which `CR-069` §20.4 moves whole.
  * **which meter is which account** — `OQ-INT-1485` closed on 2026-09-04 with
    *we are master*; applying that rule is a record update and is Runbooks'.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def project_readings(
    *,
    connection_id: Any,
    operation: str,
    window_start: Any = None,
    window_end: Any = None,
    records: Sequence[Mapping[str, Any]] = (),
) -> tuple[()]:
    """What a collected page MEANS — Runbooks', not ours.

    Returns `()` and that is the finished answer for this module.

    ⚠ This is a **deliberate absence and not a stub** (the `OQ-1396`
    distinction, and the same wording `runners/serve.partner_fields()` uses):
    it raises nothing, blocks nothing and names no open question, because
    nothing is unruled. The arguments are named — rather than the function
    taking none — so that the day Runbooks arrives the CALL SITE does not have
    to change, only this body.
    """
    return ()


def projects_nothing() -> bool:
    """True while the door is shut. Read by the test that keeps it honest.

    ⚠ It exists because the alternative assertion is weaker than it looks: a
    test that only checked `project_readings(...) == ()` would still pass if a
    later lane made the function write rows and return an empty tuple anyway.
    This is the claim the boundary actually makes — *this module projects
    nothing* — stated once so it can be asserted once.
    """
    return True


__all__ = ["project_readings", "projects_nothing"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-028 · 031 · 035 (EP-INT-07/08/09) + BR-INT-054 as amended 2026-09-06 verbatim
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a(no screen — a seam) C✔ D✔(runners/fetch.py calls it once per page) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_028_token_walk.py
# exceptions: `project_readings()` returns () by BR-INT-054 — a deliberate absence owned by Runbooks, not a stub
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# CR-112 · the GIS pull hands its snapshot to runbook 20, BY NAME
# ═══════════════════════════════════════════════════════════════════════════

#: The runbook `gis_parcels.run` hands off to. ⚠ **ONE KEY, NAMED, AND NOT AN
#: EVENT** — see `hand_off_gis_batch` for why that distinction is the whole
#: design decision here.
GIS_RUNBOOK_KEY = "gis_reconciliation"


def hand_off_gis_batch(batch: object, *, start: object = None) -> dict[str, object]:
    """The City's landed snapshot → runbook 20, without emitting `batch.landed`.

    ── 2026-09-17 · `BR-INT-074` ───────────────────────────────────────────────
    ⚠ **THE RUNBOOK EXISTS AND NOTHING FIRED IT, AND THE MISSING PIECE WAS NOT
    THE EVENT.** `apps/runbooks/definitions/gis_reconciliation.py` has been
    written since `CR-075` wave Q′. Its card's trigger row reads ⚡
    `batch.landed`; its own docstring records that **a person starts it**,
    because `batch.landed` is emitted by nothing. Verified again on 2026-09-17
    by grep across `06-backend/`: the string appears in `runbooks/models.py` as
    a constant, in `runbooks/migrations/0001_initial.py` as a choice, and
    otherwise **only in docstrings saying it is not emitted**.

    What was actually missing is that **nothing ever LANDED a batch from the
    City's layer**. The runbook reads one through
    `metering_seam.staged_import_batch("premises", …)` and, with none, stops at
    step 1 with *"Nothing has landed yet"* — true, and useless. `gis_parcels.run`
    is what lands it; this is the hand-off.

    ⚠ **AND IT IS DELIBERATELY NOT THE GENERAL EVENT.** `batch.landed` is named
    by **SEVEN** runbooks — `gis_reconciliation`, `bank_reconciliation`,
    `returned_payments`, `leak_alert`, `cash_application`, `read_validation` and
    `payments/runbook_reads`. Emitting it from a GIS pull would start six
    unrelated runbooks on a wave scoped to addresses, which is a blast radius
    nobody asked for and which `CR-069` wave O owns. Every one of those seven
    declares **manual and schedule** instead and says so, so none of them is
    broken today.

    **So this names one runbook.** The day wave O lands, this function is what a
    lane greps for, and `tests/test_cr112_gis_parcels.py` is the test that goes
    red and says the general event may now replace it — hard-won law 2's rule
    that a hold must carry the test that fires when the hold expires.

    ⚠ **AMENDED 2026-10-07 (`DEF-INT-9850`).** `batch` is a DESCRIPTION of the
    pull, not a file id, and Runbook 20 passed it to a UUID lookup — so every
    Apply at a utility that had added the runbook answered 500 after it had
    run. The runbook now reads it as *the City sent this* and asks the City's
    parcel check itself (`integrations_seam.city_parcels`, a PREVIEW); nothing
    in this function changed.

    `start` is injected so a caller can prove the hand-off happened without a
    runbook row existing; unbound, it resolves Runbooks' own service, which is
    the reviewed interface (B2 §2 — a service call, never a cross-module write).
    """
    if start is not None:
        return {"runbook": GIS_RUNBOOK_KEY, "started": bool(start(GIS_RUNBOOK_KEY, batch))}
    from apps.runbooks import models as runbook_models
    from apps.runbooks import services as runbook_services

    runbook = runbook_models.Runbook.objects.filter(key=GIS_RUNBOOK_KEY).first()
    if runbook is None:
        # ⚠ **NOT AN ERROR.** A tenant that has not added runbook 20 to its
        # catalogue has not asked for the reconciliation; the pull still landed
        # its batch and the fact is reported rather than raised.
        return {"runbook": GIS_RUNBOOK_KEY, "started": False,
                "detail": "this utility has not added the GIS reconciliation runbook"}
    definition = runbook_services.definition_for(runbook)
    if definition is None:  # pragma: no cover — the registry refuses at load
        return {"runbook": GIS_RUNBOOK_KEY, "started": False, "detail": "no definition"}
    runbook_services.run_to_completion(
        runbook, definition,
        trigger=runbook_models.TRIGGER_MANUAL,
        params={"batch": batch},
    )
    return {"runbook": GIS_RUNBOOK_KEY, "started": True}
