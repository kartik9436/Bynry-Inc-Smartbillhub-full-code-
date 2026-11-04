"""CR-171-BRC10 P2.01 (lane MVI-LIST-UI) — plant one move-in of every status
on the demo utility so the list can be photographed beside image 01.

It calls the SAME scenario `06-backend/tests/test_cr171_p1_04_move_ins_list.py`
builds (`_scenario`), through the same real doors — requests created and
submitted, jobs approved, drafts parked, move-ins committed with and without a
reading — so the photograph shows rows the product itself wrote, not rows typed
into a table. Run once against a walk database:

    DATABASE_URL=postgres://…/<walk db> DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/cr171_movein_list_world.py

⚠ It writes REAL rows. Never point it at a database somebody uses.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))

import django  # noqa: E402

django.setup()


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> None:
    from core import tenancy as core_tenancy

    sjf = _load("seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
    tenant, actor = sjf.tenant_and_actor()
    scenario = _load(
        "cr171_list_scenario", REPO / "06-backend/tests/test_cr171_p1_04_move_ins_list.py"
    )
    import sys as _sys
    from datetime import timedelta

    from django.db import transaction

    step = _sys.argv[1] if len(_sys.argv) > 1 else "all"
    # One transaction, as a request would have: `select_for_update` refuses
    # to run outside one, and a half-planted world is worse than none.
    with transaction.atomic(), core_tenancy.tenant_context(tenant.id):
        if step == "all":
            # ⚠ The scenario's meter numbers (E-5041…) can collide with a
            # demo utility's own; `committed` below plants that half with
            # walk-only numbers when they do.
            out = scenario._scenario(actor, tenant)
            print("planted:", ", ".join(sorted(out)))
            return
        today = scenario.TODAY
        if step == "committed":
            unit_w = scenario._unit(
                actor, tenant, "SCW-K", meters=(("WLK-7201", "electric", "kWh"),)
            )
            scenario._committed(actor, unit_w, name="G, Nilesh", on=today - timedelta(days=2))
        # A completed move-in with TWO readings, each in its OWN meter's unit
        # (hard rule 3). `_committed(reads=…)` commits every read in kWh — the
        # test helper's default — which is why this half commits its own.
        unit_c = scenario._unit(
            actor, tenant, "SCW-M",
            meters=(("WLK-7301", "electric", "kWh"), ("WLK-7302", "water", "kgal")),
            services=("electric", "water"),
        )
        on = today - timedelta(days=5)
        for asset_no, value, uom in (("WLK-7301", "16082", "kWh"), ("WLK-7302", "841", "kgal")):
            scenario.commit_read(
                actor, scenario._asset_id(unit_c, asset_no), day=on.isoformat(), value=value,
                unit=uom,
            )
        scenario._committed(actor, unit_c, name="Raman, Priya", on=on)
        print(f"planted: {step}")


if __name__ == "__main__":
    main()
