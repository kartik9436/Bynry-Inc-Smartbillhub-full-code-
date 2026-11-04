"""CR-157-BRC10 wave C — write the matrix half of RESULTS.md from the walk's state.

    python3 10-scripts/rswalk_results.py <state.json>  > matrix-table.md

`10-scripts/rate_schedule_wave_c_walk.mjs` keeps one record per matrix row in
its state file; this prints the per-row table and the pass counts per check, so
the published figures are the measured ones and never retyped by hand.
"""

import json
import sys

state = json.load(open(sys.argv[1]))
rows = state["rows"]
SERVICES = ["electric", "water", "gas", "sewer", "trash", "storm_water", "solar",
            "broadband", "thermal_heat", "battery", "fire"]
METHODS = ["flat", "tiered", "time_of_use", "demand", "seasonal", "capacity", "percent_of_service"]
CHECKS = [("add", "Add"), ("db", "DB"), ("change", "Change the rate"), ("fix", "Fix an error"),
          ("history", "History"), ("oneVersion", "One version to billing"), ("plan", "Plan impact"),
          ("bill", "Bill preview")]


def mark(value):
    return {True: "ok", False: "**FAIL**", None: "n/a"}.get(value, "—")


def order(key):
    r = rows[key]
    return (r.get("klass") != "Every class", SERVICES.index(r["service"]) if r.get("service") in SERVICES else 99,
            METHODS.index(r["model"]) if r.get("model") in METHODS else 99, r.get("klass") or "")


keys = sorted(rows, key=order)
print("| # | Service | Method | Class | Add | DB | Change the rate | Fix an error | History | One version to billing | Plan impact | Bill preview | Bill figure expected/got | Notes |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for n, key in enumerate(keys, 1):
    r = rows[key]
    notes = []
    for side in ("billBefore", "billAfter"):
        if r.get(side, {}).get("note"):
            notes.append(r[side]["note"])
    notes += [x for x in r.get("notes", []) if not x.startswith("BILL")]
    if r.get("minimumToBilling") is False:
        notes.append("minimum to billing differs")
    text = "; ".join(dict.fromkeys(notes)).replace("|", "/").replace("\n", " ")
    if len(text) > 300:
        text = text[:297] + "…"
    print(f"| {n} | {r.get('service')} | {r.get('model')} | {r.get('klass')} | "
          + " | ".join(mark(r.get(k)) for k, _ in CHECKS)
          + f" | {r.get('billFigure', '—')} | {text} |")
print()
print("| Check | ok | FAIL | n/a | of |")
print("|---|---|---|---|---|")
for k, label in CHECKS:
    values = [rows[key].get(k, "—") for key in keys]
    print(f"| {label} | {sum(v is True for v in values)} | {sum(v is False for v in values)} | "
          f"{sum(v is None for v in values)} | {len(values)} |")
