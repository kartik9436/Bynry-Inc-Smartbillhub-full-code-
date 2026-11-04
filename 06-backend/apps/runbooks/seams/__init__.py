# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4: the nine read seams.
# Rules:    BR-RBS-039 (a runbook reaches another module ONLY through a seam
#           this module owns, calling the owner's selector by name in the same
#           process; every seam is a row in the cross-module interface register;
#           never the product's own HTTP endpoints, never another module's
#           models) · B2 §2 (cross-module writes forbidden; FKs are the reviewed
#           interface set) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py (the nine exist, are
#           named for the far side, and declare READ)
# Impacts:  10-scripts/gates/g115_runbooks_import_census.py — this package is
#           the ONLY place under apps/runbooks where a foreign import is lawful
# ───────────────────────────────────────────────────────
"""The nine read seams — `operations → <module>`, one file per module read.

⚠ **THIS `__init__.py` IMPORTS NOTHING AND RE-EXPORTS NOTHING, ON PURPOSE.**
A package `__init__` that pulled the seam modules in would launder every foreign
import into `apps.runbooks.seams`, so a caller anywhere in the module could
reach another module's models through this name without any file appearing to
import them. That is a real hole and `G115` closes it by refusing a foreign
import in any file under `seams/` that is not itself a `*_seam.py`. This file
stays empty of imports so the rule has nothing to argue with.

THE NINE, AND THE NAMING
------------------------
`customers` · `metering` · `rating` · `billing` · `payments` · `ledger` ·
`notifications` · `tenancy` (settings — **policy is read, never duplicated**) ·
`integrations` (a landed batch, for the three events).

The source specification names seams *"for the pair (operations → customers)"*.
**The repository's own convention names only the FAR side** —
`apps/work/seams/customers_seam.py`, not `work_customers_seam.py` — because the
near side is already in the path. This module follows the repository and keeps
the pair naming in each file's docstring, so a reader of either document lands
on the same seam (`12-the-contract.md` §7).

WHY A `seams/` SUB-PACKAGE AND NOT FLAT FILES
----------------------------------------------
Two layouts exist in this product and the choice was deliberate: `billing` puts
its nine seams flat in the app package, `work` puts its eight in a `seams/`
directory. With nine seams and a gate to write against them, a directory is what
a gate can glob and what a tenth seam does not crowd.

WHAT A SEAM MAY AND MAY NOT DO
-------------------------------
* It **reads**, in process, under the tenant context, by calling the owning
  module's own selector **by name**.
* It **never writes**. A write to another module is a PORT
  (`apps/runbooks/ports/`), and `G115` fails an ORM write on a foreign model
  **including inside this package** — a seam that writes is a seam in name only.
* **A selector another module does not expose yet is added by the module that
  OWNS the table**, never by this module reaching past the seam. The whole list
  of those is `04-docs/05-modules/17-runbooks/13-selector-inventory.md`,
  written in wave A precisely so it is not discovered in phase 5.
"""
