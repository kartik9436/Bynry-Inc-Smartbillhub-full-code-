#!/usr/bin/env python3
"""G139's RED PROOF — the gate is shown failing on the defect it was written for.

CLAUDE.md hard-won law 7, both halves:

  * *"Prove a new guard goes RED before trusting it green"* — this reverts the
    fix in memory and asserts `check()` reports the leak;
  * *"AND PROVE IT IN THE HARNESS THAT WILL RUN IT"* (`DEF-GOV-3733`) — the
    assertions go through `run()`, the entry point `run_gates` calls, never
    `__main__`. `G85` and `G87` were both announced green while the suite
    reported `gate crashed: AttributeError: module has no attribute 'run'`.

THE REVERT IT SIMULATES is exactly what was there on 2026-09-29: the serialiser
reaches for `str(exc)` instead of `resolution.clerk_refusal(exc)`, so the
clerk's `detail` becomes the engineer's sentence, uuids and all.

    python3 10-scripts/tests/g139_red_proof.py
"""
from __future__ import annotations

import sys
from pathlib import Path

GATES = Path(__file__).resolve().parent.parent / "gates"
sys.path.insert(0, str(GATES))

import g139_no_database_id_in_a_refusal as g138  # noqa: E402


def main() -> int:
    green, notes = g138.check()
    assert not green, f"the gate is not green to begin with: {green[:2]}"
    assert g138.run()[0] == "PASS", g138.run()
    print(f"green first: {notes[0]}")

    chain = g138._chain()
    original = chain.clerk_refusal

    def pre_fix(exc):
        """2026-09-29's behaviour: the ENGINEER's sentence, served to a clerk."""
        answer = original(exc)
        if answer is None:
            return None
        return {**answer, "detail": str(exc)}

    chain.clerk_refusal = pre_fix
    try:
        red, _ = g138.check()
        verdict, detail = g138.run()
    finally:
        chain.clerk_refusal = original

    assert red, "REVERTED THE FIX AND THE GATE STAYED GREEN — it checks nothing"
    assert verdict == "FAIL", f"run() said {verdict!r}, not FAIL: {detail}"
    uuid_hits = [line for line in red if "a database uuid reaches a clerk" in line]
    assert len(uuid_hits) == 9, f"expected 9 leaking sites, saw {len(uuid_hits)}"
    print(f"RED on the revert: {len(red)} finding(s), {len(uuid_hits)} naming a uuid")
    print(f"  run() -> {verdict}: {detail[:120]}")

    again, _ = g138.check()
    assert not again, f"the gate did not come back green: {again[:2]}"
    print("green again after the revert was undone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
