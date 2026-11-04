# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-TEN-9655 — a stored-document migration's rollback refusal ran
#          LAST on the way back (Django reverses operations), after the narrower
#          CHECK had already been restored, so the rollback failed on a raw
#          IntegrityError and the counted sentence never showed.
# Change:  CR-168-BRC10 round 6, lane CREWS-2 — the ordering fix SRV-4 made in
#          tenancy/0060, applied to the ten siblings that still carry it.
# Rules:   CLAUDE.md 🔒 migration ordering · hard-won law 7 (red first)
# ───────────────────────────────────────────────────────
"""Every reverse-only refusal is the LAST operation, so it runs FIRST backwards.

RED FIRST on `8badcb01c`: ten of the eleven cases below failed, each naming the
refusal's position (``refuse_rollback_over_live_rows is operation 1 of 3``…);
`tenancy/0060` (SRV-4's own fix) was the eleventh and passed.

⚠ **`tenancy/0020` IS NOT HERE, AND THAT IS MEASURED RATHER THAN MISSED.** The
defect row names it as where the pattern began; `0020_cr039_sample_run_blocks`
is one `AddField` and carries no refusal at all. The scan below is what decides
the scope, not the list in the row: it walks EVERY migration in the repo and
fails on any reverse-only refusal that is not last, so an eleventh sibling
written tomorrow goes red without anybody adding it to a list.

The forward half is untouched by construction: a reverse-only refusal's forward
code is `RunPython.noop`, so moving it changes no forward SQL and no state.
`test_moving_it_changed_no_forward_operation` holds the forward operations of
each file to their recorded order.
"""

from __future__ import annotations

import glob
import importlib
import pathlib

import pytest
from django.db import migrations

BACKEND = pathlib.Path(__file__).resolve().parents[1]

FIXED = [
    "apps.tenancy.migrations.0028_oq1164_every_customer_document_kind",
    "apps.tenancy.migrations.0039_cr070_k_work_document_kinds",
    "apps.tenancy.migrations.0040_cr070_k_attachment_source",
    "apps.tenancy.migrations.0044_cr094_i_account_document_source",
    "apps.tenancy.migrations.0045_service_request_document_source",
    "apps.tenancy.migrations.0051_p5_11_supplier_invoice_document",
    "apps.tenancy.migrations.0052_p4_3_remittance_receipt_source",
    "apps.tenancy.migrations.0054_def_not_8450_twelve_message_kinds",
    "apps.tenancy.migrations.0059_cr168_work_template_help_document",
    "apps.tenancy.migrations.0060_cr168_work_certificate_proof",
    "apps.work.migrations.0034_cr168_task_instruction_copy_and_help_link",
]


def _is_reverse_only_refusal(op) -> bool:
    return (
        isinstance(op, migrations.RunPython)
        and op.code is migrations.RunPython.noop
        and op.reverse_code is not None
        and "refuse" in getattr(op.reverse_code, "__name__", "")
    )


def _all_migration_modules() -> list[str]:
    found = []
    for path in sorted(glob.glob(str(BACKEND / "apps" / "*" / "migrations" / "0*.py"))):
        rel = pathlib.Path(path).relative_to(BACKEND).with_suffix("")
        found.append(".".join(rel.parts))
    return found


@pytest.mark.parametrize("module", FIXED)
def test_the_refusal_is_the_last_operation_so_it_runs_first_on_the_way_back(module):
    ops = importlib.import_module(module).Migration.operations
    positions = [i for i, op in enumerate(ops) if _is_reverse_only_refusal(op)]
    assert positions, f"{module} carries no reverse-only refusal"
    name = ops[positions[-1]].reverse_code.__name__
    assert positions == [len(ops) - 1], (
        f"{module}: {name} is operation {positions[-1] + 1} of {len(ops)} — on rollback "
        "it runs after the narrower CHECK is restored, and the counted sentence never shows"
    )


def test_no_migration_anywhere_carries_a_reverse_only_refusal_before_other_operations():
    modules = _all_migration_modules()
    late = []
    for module in modules:
        ops = getattr(importlib.import_module(module), "Migration").operations
        for index, op in enumerate(ops):
            if _is_reverse_only_refusal(op) and index != len(ops) - 1:
                late.append(f"{module} (operation {index + 1} of {len(ops)})")
    # The scan must have seen the whole repo, not an empty glob (law 7: a
    # check reporting zero over a scope it silently excludes).
    assert len(modules) > 500, f"only {len(modules)} migration modules found"
    assert late == [], late


#: The forward operations of each file, in order, as they stood before the move.
FORWARD = {
    FIXED[0]: ["RemoveConstraint", "AddConstraint"],
    FIXED[1]: ["RemoveConstraint", "AddConstraint", "RemoveConstraint", "AddConstraint"],
    FIXED[2]: ["RemoveConstraint", "AddConstraint"],
    FIXED[3]: ["RemoveConstraint", "AddConstraint"],
    FIXED[4]: ["RemoveConstraint", "AddConstraint", "RemoveConstraint", "AddConstraint"],
    FIXED[5]: ["RemoveConstraint", "AddConstraint", "RemoveConstraint", "AddConstraint"],
    FIXED[6]: ["RemoveConstraint", "AddConstraint"],
    FIXED[7]: ["RemoveConstraint", "AddConstraint"],
    FIXED[8]: ["RemoveConstraint", "AddConstraint", "RemoveConstraint", "AddConstraint"],
    FIXED[9]: ["RemoveConstraint", "AddConstraint", "RemoveConstraint", "AddConstraint"],
    FIXED[10]: [
        "AddField",
        "RemoveConstraint",
        "AddConstraint",
        "RemoveConstraint",
        "AddConstraint",
    ],
}


@pytest.mark.parametrize("module", FIXED)
def test_moving_it_changed_no_forward_operation(module):
    ops = importlib.import_module(module).Migration.operations
    forward = [type(op).__name__ for op in ops if not _is_reverse_only_refusal(op)]
    assert forward == FORWARD[module]
