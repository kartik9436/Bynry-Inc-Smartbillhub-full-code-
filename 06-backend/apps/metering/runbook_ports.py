# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-014 (EP-RBS-04) — CR-075 wave L task L2: the
#           three ports metering owns. ONE of them binds a writer today; the
#           other two name what is missing rather than pretending.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-MET-048 (a premises edit is one transaction, audited)
#           · BR-MET-017 (a committed read is append-only) · US-MET-010 (the
#           person committing a read IS the person certifying it) ·
#           CLAUDE.md hard rule 8 (an address lives on premises and nowhere
#           else) · BR-TEN-043 (event time is an argument)
# Tests:    06-backend/tests/test_us_rbs_010_port_writers.py
# Impacts:  apps/runbooks/ports/metering_ports.py (binds `apply_premise_change`
#           and states the absence behind the other two) · DEF-RBS-4331
# ───────────────────────────────────────────────────────
"""One of metering's three ports has a writer. The other two have nothing to bind.

⚠ **THIS FILE SAYS WHAT IS ABSENT RATHER THAN BINDING SOMETHING THAT LOOKS
CLOSE, AND THAT IS THE POINT OF WRITING IT DOWN** (hard-won law 1: a comment
claiming a guarantee is not the guarantee; law 2: a bound port nothing can
honour is dead UI one layer down). `CR-075` wave A declared thirteen ports from
`12-the-contract.md` §8's coverage table. Wave L is the first time anybody has
tried to put a writer behind each of them, and two of metering's three turn out
to have **no service and no column to write to**. Both are filed as
`DEF-RBS-4331` and both are named in the port declaration, so a reader of
`bound_ports()` sees a number that is true.

**`write_read` — NOT BOUND, and the reason is a rule rather than a missing
function.** `apps.metering.services.commit_event_reads` is the module's own
event-read door and it exists. Its docstring states US-MET-010's certification
rule: *"the acting user committing the wizard IS the person certifying the
entry, one human act"*, and the committed read carries that user as
`imported_by`. **An automation cannot certify a meter reading.** Binding this
port to that door would make a runbook sign a reading as a person — the exact
failure `BR-RBS-015` exists to prevent, wearing different clothes, and worse
than the audit-actor gap `US-AUD-010` closed because it lands on the read
itself rather than on the trail. What is owed is a metering door that accepts
an `AutomationActor` and records the read as machine-certified, which is
metering's design decision and not a runbook lane's to take.

**`flag_meter` — NOT BOUND, and there is nowhere to put the fact.** *"Told
about a leak on <date>"* has no column: `Asset` carries no flag, no note and no
leak field, and — the harder half — **`Asset` lives in `apps/assets`, not in
`apps/metering`**, so even a new column there would make this a metering→assets
cross-module write, which B2 §2 forbids and which the thirteen-port list does
not contemplate (`assets` is not one of the five `WRITE_MODULES`). This is a
declaration made from a coverage table, and the module map moved underneath it.

⚠ **NEITHER ABSENCE IS A `NotImplementedError("OQ-…")` STUB**, deliberately.
The prime directive's stub is for a story blocked on an OPEN QUESTION the
Product Owner must answer. Neither of these is a question for them: one is a
metering design decision and one is a schema gap, both ours to make and both
written down. `G8` reads a `NotImplementedError` as a blocked story and would
report two questions that do not exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.metering import services


def apply_premise_change(
    *,
    actor: Any,
    premises_id: Any,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    """PORT `apply_premise_change` — one field on one premises, before and after kept.

    Delegates to `apps.metering.services.update_premises`, which is `S14`'s own
    edit: ONE transaction, audited with the full before/after (`BR-MET-048`).
    The before-and-after the port's declaration promises is that function's
    audit row, not a second copy this file would keep.

    ⚠ **THIS IS THE ONE PORT THAT CAN MOVE AN ADDRESS, AND AN ADDRESS LIVES IN
    EXACTLY ONE PLACE** (hard rule 8, `BR-MET-1161`). Every other entity in the
    product — an account, a meter, a route, a cycle, an invoice, a work order,
    a map pin — DERIVES its address by walking to the premises, so a runbook
    correcting a premises corrects all of them at once and a map and an
    envelope cannot disagree. That is also why there is no `apply_account_
    address_change` port and why there must never be one.

    ⚠ **CHANGING `inside_city_limits` CHANGES WHAT THIS ADDRESS IS CHARGED, AND
    IT IS FORWARD-ONLY.** `update_premises` says so in full: it writes the
    column and stops, and every issued invoice is left exactly as it was (hard
    rule 4). **A runbook must not be pointed at that field** — this port cannot
    refuse a field list, so the refusal belongs in the runbook that declares the
    change. `CR-075` wave Q′'s runbook 20 is the first that could, and it does
    not: `inside_city_limits`, `city` and `state` are a NEVER-TOUCH constant in
    its code, fixed on the money-path fields and not widenable by a tenant
    (`RBR-17`, restating the integration substrate's C25).

    ⚠ **THIS PARAGRAPH SAID *"whether a corrected flag owes an adjustment on
    bills already issued is `OQ-423` and is OPEN"* UNTIL 2026-09-06, AND
    `OQ-423` HAD BEEN CLOSED SINCE 2026-08-27** — PO ruling *"(a) Forward only,
    and nothing else"*, `BR-RAT-103`: the next bill is corrected, the ~$350
    already billed the other way stands, and no adjustment is raised. That is
    `DEF-MET-4349`. **The instruction survived its reason**, which is why it is
    corrected here rather than quietly deleted: the prohibition rests on
    `RBR-17` and never rested on that question at all, so a lane that had read
    the stale sentence and concluded *the question is closed, so the field is
    now fair game* would have been wrong twice over.
    """
    detail = services.update_premises(actor, premises_id, dict(changes))
    return {
        "entity_type": "premises",
        "entity_id": str(premises_id),
        "created": False,
        "fields": sorted(changes),
        "routes_joined": [dict(row) for row in detail.get("routes_joined", [])],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-014 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a port is called by the engine, never over HTTP) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path: this delegates to metering's own audited edit and composes no key)
# gates: pytest tests/test_us_rbs_010_port_writers.py · G115 · G6 (no clock read)
# exceptions: `write_read` and `flag_meter` bind NO writer — DEF-RBS-4331, with the reason for each in the module docstring and in the port declaration
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
