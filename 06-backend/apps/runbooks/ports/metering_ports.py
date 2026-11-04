# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-019 (the unit of work is the meter-day) ·
#           CLAUDE.md hard rule 3 (consumption always carries its unit) ·
#           hard rule 8 (an address lives on premises and nowhere else)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 · apps/runbooks/interfaces.py
# ───────────────────────────────────────────────────────
"""Three ports owned by `metering`. **ONE is bound; two have nothing to bind.**

⚠ **THIS DOCSTRING SAID *"None is bound"* UNTIL 2026-09-06, AND THE HONEST
REPLACEMENT IS NOT *"all bound"*.** Wave L task L2 binds
`apply_premise_change` to `apps.metering.runbook_ports.apply_premise_change`.
The other two bind nothing and that is **`DEF-RBS-4331`**, filed the moment it
was found rather than papered over:

  * **`write_read`** — metering's event-read door certifies the reading as the
    acting HUMAN (`US-MET-010`: *"the acting user committing the wizard IS the
    person certifying the entry"*), and **an automation may not sign a meter
    reading**. Binding it would be `BR-RBS-015`'s failure landing on the read
    itself instead of on the trail.
  * **`flag_meter`** — there is no column anywhere to hold *"told about a leak
    on <date>"*, and `Asset` lives in `apps/assets`, which is not one of the
    five modules a port may write.

`bound_ports()` therefore reports **9 of 13**, which is a true number.
`test_us_rbs_010_port_writers.py` asserts the exact membership of both sets, so
neither can drift silently in either direction.

⚠ **`write_read` STAMPS ITS SOURCE, AND THAT IS NOT DECORATION.** A meter-day a
runbook validated and wrote is a different fact from one a meter reported, and a
bill that cannot say which it used cannot be defended. The quantity carries its
unit (CLAUDE.md hard rule 3) — a read written without one is a guess wearing a
number.

⚠ **`apply_premise_change` KEEPS BEFORE-AND-AFTER AND TOUCHES ONE FIELD ON ONE
PREMISE.** Premises is the product's **one address home** (hard rule 8,
`BR-MET-1161`), so this is the only port in the thirteen that can change an
address at all, and every account, route, cycle, invoice, work order and map pin
derives from it. A bulk change here is a bulk change to everything downstream,
which is exactly what the cap and the dry run are for.

⚠ **`flag_meter` IS *"TOLD ABOUT A LEAK ON"* A DATE — A NOTE, NOT A JUDGMENT.**
It records that we said something and when; it does not decide whether the leak
is real, because that is a person's call and a runbook that made it would be
wrong on the day it mattered.
"""

# ⚠ A FOREIGN IMPORT IN ONE OF THE TWO LAWFUL DOORS (`G115` rule 1).
from apps.metering import runbook_ports as metering_writers

from apps.runbooks.boundary import PortDeclaration

#: ⚠ NO `writer=` — see the module docstring and `DEF-RBS-4331`. A reading is
#: certified by the person who commits it (`US-MET-010`); an automation cannot
#: sign one, so there is nothing lawful to bind here yet.
WRITE_READ = PortDeclaration(
    name="write_read",
    owning_module="metering",
    what_it_does="A validated meter-day as a read, source stamped",
)

APPLY_PREMISE_CHANGE = PortDeclaration(
    name="apply_premise_change",
    owning_module="metering",
    what_it_does="One field on one premise, before-and-after kept",
    writer=metering_writers.apply_premise_change,
)

#: ⚠ NO `writer=` — see the module docstring and `DEF-RBS-4331`. Nothing in the
#: product holds this fact, and the row it would belong to is `apps/assets`',
#: which is not one of the five modules a port may write.
FLAG_METER = PortDeclaration(
    name="flag_meter",
    owning_module="metering",
    what_it_does='"Told about a leak on" a date',
)

PORTS = (WRITE_READ, APPLY_PREMISE_CHANGE, FLAG_METER)
