# ── Trace ──────────────────────────────────────────────
# Change:   CR-077 — import starters for *"Premises, Units, Meters, Sub meters,
#           Assets, Parts, Accounts, Reading"* (PO 2026-09-07). Parts was handed
#           back as an architecture question and the answer is in
#           12-governance/02-decision-log.md, 2026-09-07, "HOW PARTS GETS AN
#           IMPORT": a new target is a PARAMETER, and the load calls Work's own
#           writer through the `import_writer` seam kind.
# Story:    US-WRK-010 (the parts register — Work-025)
# Rules:    BR-MET-096 (PO 2026-08-21: *"same process for premises and Unit -
#           only at tranform stage we differntate field"* — ONE runner) ·
#           BR-WRK-002 / G78 (nothing outside `apps/work` writes `parts`) ·
#           BR-TEN-013 (a cross-module write is the owning module's own service
#           function) · DEF-1108 (a deferred load runs under `_JobActor` — an
#           id and NO ROLE, by design — so this door is UNDECORATED and the
#           role is checked once at `load()`) · DEF-075 (`None` means *this
#           module cannot answer*, never *this module has nothing*) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_cr077_parts_import.py
# Impacts:  apps/metering/seams.py (the three names) ·
#           apps/metering/import_runs.py (`TARGET_PARTS`)
# ───────────────────────────────────────────────────────
"""Work's INBOUND door for the one importer — and the first one this module has.

⚠ **EVERY OTHER FILE IN `apps/work/seams/` POINTS THE OTHER WAY.** All nine are
OUTBOUND and read-only: Work reading assets, connections, accounts, meter reads,
areas and users. This is the opposite direction — another module handing Work
rows to write — so it does **not** belong in `seams/`. It mirrors
`apps/customers/import_writer.py`, which exists for exactly this shape, and it
is published for exactly one caller.

⚠ **IT IS UNDECORATED, AND THAT IS THE WHOLE REASON IT IS A SEPARATE FILE FROM
`services.create_part` (`DEF-1108`).** A deferred import load runs in a BE-07
worker carrying `_JobActor` — *"an id, and no role, BY DESIGN"* — so a
`@require_role` writer would refuse **every row of every large migration**, at
the point where the operator has already been told the file is being loaded.
`import_runs.load()` is `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and checks
the role ONCE, where a role still exists; nothing downstream of that point may
re-ask a question the worker cannot answer.

⚠ **`services.create_part` HAPPENS TO BE UNDECORATED TODAY AND THAT IS NOT
SOMETHING TO RELY ON.** Publishing this address is what makes the guarantee
structural rather than a coincidence two files apart (hard-won law 1): a lane
that later gates `create_part` breaks a screen and not a migration, because the
migration comes through here.

⚠ **NOTHING OUTSIDE `apps/work` TOUCHES THE `parts` TABLE.** The runner stages,
maps and judges; this module writes. `G78` therefore stays satisfied BY
CONSTRUCTION rather than by care — there is no ORM statement to review in
`apps/metering/`.

WHAT IS DELIBERATELY NOT HERE
------------------------------
No validation of its own. `services._clean_part` is the one validator an edit
on `Work-025` already goes through — the part number's case-insensitive
uniqueness, the category lookup against the tenant's own list, the unit cost as
4-decimal money — and a second copy in this file would be two rules with one
owner, which is the thing `BR-MET-096` and hard-won law 5 both exist to stop.
A refused row raises exactly what the screen raises, and the loader turns it
into that row's sentence.
"""

from __future__ import annotations

from typing import Any


def parts_import_index() -> dict[str, dict[str, Any]]:
    """LOWERED part number → `{id, part_no, name}` — the existing-row index.

    Read ONCE per run and shared by stage 3 and stage 4, so the rehearsal and
    the commit resolve against the same world (`DEF-544`: a load that judges
    against a different world than the one the operator was shown is a defect
    in its own right, not a race).
    """
    from apps.work import models as work_models
    from core.tenancy import current_tenant_id

    return {
        str(row.part_no).strip().lower(): {
            "id": str(row.id),
            "part_no": row.part_no,
            "name": row.name,
        }
        for row in work_models.Part.objects.filter(tenant_id=current_tenant_id()).only(
            "id", "part_no", "name"
        )
    }


def part_category_index() -> dict[str, str]:
    """LOWERED category name AND code → the category's own name.

    The importer needs to judge an unknown category at stage 3 — before
    anything is written — and `services._clean_part` resolves the same two ways
    (name first, then code). Both are published here so the judgment and the
    write cannot disagree about what the tenant's list contains.
    """
    from apps.work import models as work_models
    from core.tenancy import current_tenant_id

    index: dict[str, str] = {}
    for row in work_models.PartCategory.objects.filter(tenant_id=current_tenant_id()):
        index[str(row.name).strip().lower()] = row.name
        index.setdefault(str(row.code).strip().lower(), row.name)
    return index


def create_part_from_import(*, actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """One import row → one row in the parts register.

    UNDECORATED on purpose — see this module's docstring. Raises whatever
    `services._clean_part` raises for a row it will not accept; the loader
    catches it per row inside its own savepoint and reports the sentence,
    because on PostgreSQL a refused statement aborts the whole transaction and
    the rows already written would be lost at COMMIT (CLAUDE.md law 14).
    """
    from apps.work import services as work_services

    return work_services.create_part(actor, dict(payload or {}))


def update_part_from_import(*, actor: Any, part_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """An existing part, updated from a file — the `upsert` half.

    ⚠ **A PART NUMBER IS NEVER CHANGED BY AN UPDATE, AND THE OMISSION IS THE
    POINT.** `part_no` is what the row was MATCHED on, so writing it back would
    at best be a no-op and at worst rename a part to something the file did not
    intend. It is dropped here rather than in the runner, because it is Work's
    key and Work is where a statement about it belongs.
    """
    from apps.work import services as work_services

    cleaned = {k: v for k, v in dict(payload or {}).items() if k != "part_no"}
    return work_services.update_part(actor, part_id, cleaned)


def rollback_part_from_import(*, actor: Any, part_id: Any) -> str:
    """Reverse one part this run created — or say why it is kept.

    Answers one of three words, and the caller writes the operator's sentence
    from it: `reversed` · `kept_issued` · `missing`.

    ⚠ **A PART THAT HAS BEEN ISSUED TO A JOB IS KEPT, AND IT IS THE SAME LAW
    THE ACCOUNTS ROLLBACK OBEYS.** `part_issues` records who took what and what
    for (`BR-WRK-049`), and it is a record of something that happened. Deleting
    the part would take the job's materials record with it — a costed work
    order whose parts no longer exist — so the part is switched OFF instead:
    it stops being offered on new issues and the history stands.

    ⚠ **AND IT DEACTIVATES RATHER THAN DELETES IN ONE MORE CASE — a part the
    utility has since edited is still deleted here, deliberately.** The rule the
    accounts half states is *"a row somebody has since moved into is not this
    run's to take back"*, and for a part there is no equivalent of moving in:
    an edited part is still a row this run created and nobody else is standing
    on. Only an ISSUE is somebody else's fact.
    """
    from apps.work import models as work_models
    from core import audit as core_audit
    from core.tenancy import current_tenant_id

    tenant_id = current_tenant_id()
    row = work_models.Part.objects.filter(tenant_id=tenant_id, pk=part_id).first()
    if row is None:
        return "missing"
    issued = work_models.PartIssue.objects.filter(tenant_id=tenant_id, part_id=row.pk).exists()
    if issued:
        if row.active:
            row.active = False
            row.save(update_fields=["active", "updated_at"])
            core_audit.write_row(
                action="work.part.deactivated_by_rollback",
                entity_type="part",
                entity_id=row.id,
                actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
                after={"part_no": row.part_no, "active": False},
            )
        return "kept_issued"
    core_audit.write_row(
        action="work.part.removed_by_rollback",
        entity_type="part",
        entity_id=row.id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before={"part_no": row.part_no, "name": row.name},
    )
    row.delete()
    return "reversed"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-077 (PO 2026-09-07) · decision log 2026-09-07 "HOW PARTS GETS AN IMPORT" · US-WRK-010
# generated: 2026-09-07 by the CR-077 parts-import lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — the runner's) E=n/a F✔ G✔ H=n/a(the unit cost is validated by services._clean_part, unchanged)
# gates: pytest tests/test_cr077_parts_import.py · G78 (Work writes only its own tables — and this is what keeps metering out of `parts`)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
