# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · BR-INT-054 as amended
#           2026-09-06 (integrations connects; Runbooks transforms) ·
#           CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → integrations — a landed batch, for the three events. READ ONLY.

Cash application, statement matching, the parcel night report and the
delivery-feedback runbook each start from a batch that has landed, and read it
here. `BR-INT-054` as amended on 2026-09-06 draws the line: **integrations
connects; Runbooks transforms.**

⚠ **THE THREE EVENT KINDS ARE BLOCKED-BY THE INTEGRATIONS SUBSTRATE** (`CR-069`).
`batch.landed` and `feedback.landed` are **not emitted yet** and are phase 5's
dependency, not phase 1's; `bill_run.completed` is billing's. **Manual and
schedule triggers wait on nothing**, which is why phases 1 to 3 can start
immediately (`RB-022`).

⚠ **A RUNBOOK WHOSE ONLY TRIGGER IS AN UNBUILT EVENT IS NOT RUNNABLE, AND ITS
SCREEN MUST SAY SO** rather than offering a **Run ▶** that refuses. That is
hard-won law 2's mirror — a live control over a dead one — and on 2026-09-05 it
cost the customer portal six of its eight front-page doors. **When the event
lands, the control that was holding it must be released in the same breath**,
and the test that fires on that day is written with the hold, not after it.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; wave O brings the first event-triggered
runbook and the reads it actually needs. A selector written here now would be a
function nothing calls (hard-won law 2), and naming one in prose that
`integrations` does not expose would fail `G20` — the guard that caught
`DEF-075`. What this module will need and `integrations` does not offer today is
inventoried in `17-runbooks/13-selector-inventory.md`, and **`integrations` adds
each of them** — never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="integrations",
    pair="operations → integrations",
    crosses="a landed batch, for the three events",
)


# ── CR-075 wave P · the connection check (US-RBS-022 · US-RBS-026) ────────
#
# ⚠ **"NO CONNECTION" IS A RESULT, NOT A BLOCKER — PO ruling 2026-09-06**,
# verbatim: *"in absence of API conenctions you will not find anything and you
# can stop the job saying APi or conenct not available; that is a valid case and
# state for us"*. So this read exists to let a runbook's FIRST step answer *what
# is connected*, in words, and stop the run when the answer is nothing. It is
# not a precondition the runbook waits on — it is the runbook's first finding.
#
# ⚠ **AND IT IS NOT THE ONLY WAY WORK ARRIVES.** The same day, the Product
# Owner ruled that a person collects the cheques and uploads them: *"runbook
# cannot annouce the checks are arrive, it is human who will collect it and
# uplaod in system"*. A run therefore stops only when there is NEITHER a live
# connection NOR a file somebody uploaded — a connection is one of two doors,
# and reporting *"no connection"* over a file a clerk is waiting on would be a
# refusal nobody deserved.


def live_connections(provider_keys) -> list[dict[str, object]]:
    """The named providers this tenant has an ENABLED, connected link to.

    `apps.integrations.selectors.grid` — the one read that joins every manifest
    to this tenant's own state, and the same one `GET /integrations` serves, so
    a runbook's answer and the Integrations screen's cannot disagree.

    Each row is `{key, display_name, category, status, enabled}` and carries **no
    credential, no config and no connection id** — a runbook needs to know *is
    there a door*, and anything more would be this module holding facts it has no
    reason to hold.

    ⚠ **`enabled` AND `status` ARE BOTH READ, BECAUSE A DISABLED CONNECTION IS
    NOT A CONNECTION.** A row that exists with the switch off is exactly the case
    a clerk needs named — *"the lockbox link is set up and switched off"* is a
    different sentence from *"nothing is set up"*, and one of them has a
    two-second fix.
    """
    from apps.integrations import selectors as integrations_selectors
    from core import tenancy as core_tenancy

    wanted = {str(one) for one in provider_keys}
    if not wanted:
        return []
    grid = integrations_selectors.grid(core_tenancy.current_tenant_id())
    live: list[dict[str, object]] = []
    for provider in grid.get("providers", []):
        if provider.get("key") not in wanted:
            continue
        connection = provider.get("connection")
        if connection is None:
            continue
        live.append(
            {
                "key": provider["key"],
                "display_name": provider.get("display_name"),
                "category": provider.get("category"),
                "status": connection.get("status"),
                "enabled": bool(connection.get("enabled")),
            }
        )
    return live


def receipt_file_default_day():
    """Yesterday on the utility's own clock — what a nightly receipt push sends.

    `apps.integrations.receipt_push.default_day` (CR-173-BRC10). The tenant's
    zone is read on integrations' side of the door through tenancy's own read,
    so the runbook and the file builder cannot disagree about whose midnight it
    is (PO 2026-10-07 Q2). `None` when no zone can be read.
    """
    from apps.integrations import receipt_push

    return receipt_push.default_day()


def receipt_file_preview(day) -> dict[str, object]:
    """The New World file for `day` as it WOULD be sent — built, counted, sent nowhere.

    `apps.integrations.receipt_push.preview` (CR-173-BRC10): the file name,
    the folder, whether the utility has set a City folder up at all, the
    receipt count and the flagged counts (not balanced, no City GL number),
    and whether that day already went. READ ONLY — it builds bytes in memory
    and writes no row; the write is the `send_partner_file` port.
    """
    from apps.integrations import receipt_push

    return receipt_push.preview(day)


# ── 2026-10-07 · `DEF-INT-9848` · THE CITY'S PARCELS, FOR RUNBOOK 20 ──────
#
# PO ruling 2026-10-07, verbatim: *"Can we do it in runbook … I dont want to
# start nightly jobs immediately - we will run nightly jobs using runbook and not
# crete new code ofr this - we will call APi manually and test it first when
# everything work then we will do nightly job for specific utility/tenant"*.
#
# ⚠ **ONE PULL IN THE PRODUCT, AND THIS IS A DOOR TO IT RATHER THAN A SECOND
# ONE.** `apps.integrations.gis.reconcile` is the parcel check the Integrations
# screen's *Preview* already runs: the connection, the sandbox refusal, the
# *sync switched off* refusal, the throttle, the key, the walk, the match on
# `gis_parcel_id` then address, and `R28`'s *never touch by default* on every
# address field. Runbook 20 asks it for a PREVIEW and nothing else, so the
# runbook and the screen cannot disagree about what the City said.
#
# ⚠ **A PREVIEW WRITES NO PREMISES AND NO UNIT; IT DOES WRITE ONE ATTEMPT ROW**
# — integrations' own `integration_runs` record of having dialled the City
# (`BR-INT-039`), exactly as the *Preview* button does. That is integrations
# recording its own act in its own table, not this module writing; a dry run
# that dialled the City and left no trace on the Integrations screen would be a
# call nobody could account for.
#
# ⚠ **WHAT AN UNATTENDED (NIGHTLY) RUN SHOULD DO WITH THE ANSWER IS DEFERRED BY
# THE PO** (*"not rightnnow"*), so this asks for a preview whatever the run's
# mode is. Nothing here is a scheduler.

#: The refusals `gis.reconcile` raises before it dials, in the runbook's own
#: language (English, like every step label). ⚠ **EACH IS THE SAME SENTENCE THE
#: ELEVEN CATALOGUES HOLD FOR ITS KEY, AND A TEST READS `en.json` TO KEEP IT SO**
#: (`tests/test_def_int_9848_runbook_20_city_door.py`) — a second copy that can
#: drift is only tolerable while something goes red when it does.
CITY_REFUSAL_SENTENCES = {
    "integrations.gis.not_connected": "No city address service is connected.",
    "integrations.gis.sync_off": "This sync is switched off.",
    "integrations.refusal.sandbox_only": "Sandbox connection — test only.",
    "integrations.gis.pages_whole_number": "Give pages as a whole number.",
    # 2026-10-07, Lane B leftover (a): `gis.reconcile` now refuses a connection
    # naming no layer by this key, before it opens a run row.
    "integrations.gis.no_layer": "The city layer address is missing.",
}

#: What a refusal this file has no sentence for reads as. Never silence.
CITY_REFUSED_GENERAL = "The city's parcels could not be read."


def city_parcels(*, pages=None, started_by_name=None) -> dict[str, object]:
    """The City's parcel check, as a PREVIEW, for this tenant — or why it stopped.

    Returns one of two shapes, both plain JSON (the runbook pins it in its step
    result, and what reaches the frozen report must serialise):

    * `{"refused": True, "message_key", "headline", "detail"}` — refused before
      the City was dialled (no connection, switched off, sandbox, a bad page
      number, a connection naming no layer). Never raised: a stopped step is a
      designed answer (`BR-RBS-027`) and a raise here would be a 500.
    * the report `gis.reconcile` serves `POST …/reconcile` — `stopped`,
      `complete`, `counts`, `differences`, `queue`, `headline`. A City that
      ANSWERED and refused us (`DEF-INT-9846`'s three reasons) arrives here as
      `stopped: True` with `stop_reason_key` and its sentence in `headline`.

    `pages` stops the walk after that many pages (`DEF-INT-9849`); `None` reads
    the whole register, which is right for a run that is not on the web worker.
    `started_by_name` is the person who started a by-hand run; without one the
    attempt row reads as the schedule's.
    """
    import json

    from apps.integrations import gis, gis_parcels
    from core import tenancy as core_tenancy

    name = (str(started_by_name).strip() if started_by_name else "") or None
    try:
        report = gis.reconcile(
            None,
            core_tenancy.current_tenant_id(),
            mode=gis_parcels.PREVIEW,
            started_by=gis_parcels.BY_PERSON if name else gis_parcels.BY_SCHEDULE,
            started_by_name=name,
            max_pages=pages,
        )
    except gis.GisRefusal as refusal:
        return {
            "refused": True,
            "message_key": refusal.message_key,
            "headline": CITY_REFUSAL_SENTENCES.get(refusal.message_key, CITY_REFUSED_GENERAL),
            "detail": "",
        }
    except gis_parcels.GisRunRefused as refusal:
        # A connection that names no layer to read — the City was never dialled.
        return {
            "refused": True,
            "message_key": None,
            "headline": CITY_REFUSED_GENERAL,
            "detail": str(refusal),
        }
    # Coordinates arrive as `Decimal`; what reaches the frozen report is JSON. A
    # coordinate is TEXT from here on — it is shown, never computed with.
    return json.loads(json.dumps(report, default=str))
