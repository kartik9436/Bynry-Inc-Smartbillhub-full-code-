#!/usr/bin/env python3
"""G12's own red-proof, executable — the guard that proves the journey guard fails.

WHY THIS FILE EXISTS (hard-won law 1 + law 7).

    Law 7 says a guard is trusted only after it has been SEEN RED on the defect
    it was written for. Law 1 says a comment claiming a guarantee is not the
    guarantee. Put together they forbid what this repository did until today:
    G12's docstring said "all six failure modes were proved RED before the gate
    was trusted", and that proof existed only as a sentence in a lane report.
    Nothing re-ran it. A later edit could have made any of those six checks
    unfireable and every gate would still have printed PASS.

    So the proof is a FILE now. It ran in CI (`.github/workflows/gates.yml`);
    ⚠ NOT ANY MORE — every workflow was disabled on 2026-09-04 (PO: Actions minutes exhausted); see .github/workflows/README.md. Run it by hand.
    Each case BREAKS something and asserts G12 says so, in words; one case
    repairs the break and asserts G12 goes quiet. A check that cannot be made to
    fail is reported here as a failure of this file — which is the only way a
    dead check ever announces itself.

WHAT IT COVERS, and which defect each case comes from:

  · DEF-113 (the receipt is destroyed by any concurrent run) — cases 7-12. The
    receipt used to live inside Playwright's `outputDir`, which Playwright PURGES
    at the start of every run: in a shared working tree a real receipt vanished
    within nine seconds, twice, and two wave-close runs reported "no run receipt"
    while a genuine one had existed minutes earlier. These cases assert the four
    ways evidence can be absent — missing, unreadable, undated, stale — all read
    as NOT PROVEN, and that a narrow run's shard never displaces another
    journey's record.
  · The frontmatter hole (no defect row; found while fixing DEF-113) — cases 1-6.
    Nothing refused a journey file whose `id:` or `stories:` frontmatter could
    not be parsed, so a malformed journey was INVISIBLE rather than loud.

Run it directly; it needs nothing but Python 3.12 stdlib and this repository:

    python3 10-scripts/gates/g12_selftest.py

It writes only into a temporary directory of its own and never touches
`07-frontend/journey-evidence/`, so running it can neither create nor destroy
real journey evidence.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import g12_journeys  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ✔ {name}")
    else:
        print(f"  ✘ {name}{(' — ' + detail) if detail else ''}")
        FAILURES.append(name)


def expect_problem(name: str, problems: list[str], fragment: str) -> None:
    """The guard must not merely fail — it must SAY the thing a human can act on."""
    hit = [p for p in problems if fragment in p]
    check(name, bool(hit), f"no problem contained {fragment!r}; got {problems!r}")
    if hit:
        print(f"      RED: {hit[0]}")


# ── The frontmatter half (checks 1-6) ───────────────────────────────────────


def with_journeys(files: dict[str, str]) -> list[str]:
    """Run G12's frontmatter check over a throwaway catalog."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for name, text in files.items():
            (directory / name).write_text(text, encoding="utf-8")
        original = g12_journeys.JOURNEY_DIR
        g12_journeys.JOURNEY_DIR = directory
        try:
            return g12_journeys._frontmatter_problems()
        finally:
            g12_journeys.JOURNEY_DIR = original


GOOD = "# J77 — a well-formed journey\n\n---\nid: J77\ntier: 2\nstories: [US-BIL-001, US-BIL-002]\n---\n"


def frontmatter_cases() -> None:
    print("\n── Journey frontmatter: a malformed file must be LOUD, not invisible ──")

    # A file with no frontmatter block at all is LEGAL (J6 predates the
    # convention). If this ever fails, the gate has become stricter than the
    # catalog and 300 files go red for a rule nobody agreed.
    check(
        "a journey with NO frontmatter block is accepted (J6's shape)",
        with_journeys({"J6-corrections.md": "# J6 — Corrections\nwrong bill → credit note\n"}) == [],
    )
    check("a well-formed journey file is accepted", with_journeys({"J77-good.md": GOOD}) == [])

    expect_problem(
        "1. an EMPTY `id:` is refused",
        with_journeys({"J77-good.md": GOOD.replace("id: J77", "id:")}),
        "EMPTY `id:`",
    )
    expect_problem(
        "2. an id that is not a journey id is refused",
        with_journeys({"J77-good.md": GOOD.replace("id: J77", "id: 77")}),
        "is not a journey id",
    )
    expect_problem(
        "3. an id that disagrees with its filename is refused",
        with_journeys({"J77-good.md": GOOD.replace("id: J77", "id: J78")}),
        "is not named for it",
    )
    expect_problem(
        "4. an unparseable `stories:` line is refused",
        with_journeys({"J77-good.md": GOOD.replace("stories: [US-BIL-001, US-BIL-002]", "stories: US-BIL-001")}),
        "cannot parse",
    )
    expect_problem(
        "5. a non-story token inside `stories:` is refused",
        with_journeys({"J77-good.md": GOOD.replace("US-BIL-002", "TBD")}),
        "which are not US-IDs",
    )
    expect_problem(
        "6. two files claiming one journey id are refused",
        with_journeys({"J77-good.md": GOOD, "J77-copy.md": GOOD}),
        "is claimed by 2 files",
    )


# ── The run-receipt half (checks 7-12) — DEF-113 ────────────────────────────


def record(status: str = "passed", assertions: int = 3, age_seconds: float = 0.0, **extra: object) -> dict:
    stamp = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "status": status,
        "assertions": assertions,
        "tests": 1,
        "specs": ["J77.spec.ts"],
        "recorded_at": stamp.isoformat().replace("+00:00", "Z"),
        **extra,
    }


def with_evidence(
    shards: list[dict],
    merged: dict | None = None,
    legacy: dict | None = None,
    spec_mtime_offset: float = -60.0,
    corrupt_shard: bool = False,
) -> list[str]:
    """Run G12's wave-close check over a throwaway evidence tree for journey J77."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        runs = root / "evidence" / "runs"
        runs.mkdir(parents=True)
        specs = root / "e2e"
        specs.mkdir()
        spec = specs / "J77.spec.ts"
        spec.write_text('journey("J77", () => {});\n', encoding="utf-8")
        # The spec's mtime is what each record is aged against: negative offset =
        # the spec is OLDER than the record, which is the healthy direction.
        stamp = time.time() + spec_mtime_offset
        import os

        os.utime(spec, (stamp, stamp))

        for i, shard in enumerate(shards):
            (runs / f"run-{i}.json").write_text(json.dumps(shard), encoding="utf-8")
        if corrupt_shard:
            (runs / "run-corrupt.json").write_text("{ this is not json", encoding="utf-8")
        if merged is not None:
            (root / "evidence" / "journey-run.json").write_text(json.dumps(merged), encoding="utf-8")
        legacy_path = root / "test-results" / "journey-run.json"
        if legacy is not None:
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

        saved = (
            g12_journeys.EVIDENCE_RUNS_DIR,
            g12_journeys.MERGED_RECEIPT,
            g12_journeys.LEGACY_RECEIPT,
            g12_journeys.SPEC_DIR,
        )
        g12_journeys.EVIDENCE_RUNS_DIR = runs
        g12_journeys.MERGED_RECEIPT = root / "evidence" / "journey-run.json"
        g12_journeys.LEGACY_RECEIPT = legacy_path
        g12_journeys.SPEC_DIR = specs
        try:
            return g12_journeys._wave_close_problems({"activated": ["J77"]})
        finally:
            (
                g12_journeys.EVIDENCE_RUNS_DIR,
                g12_journeys.MERGED_RECEIPT,
                g12_journeys.LEGACY_RECEIPT,
                g12_journeys.SPEC_DIR,
            ) = saved


def receipt_cases() -> None:
    print("\n── The run receipt: absent, unreadable, undated and stale all read NOT PROVEN ──")

    check(
        "a fresh passing record in a durable shard closes the wave",
        with_evidence([{"journeys": {"J77": record()}}]) == [],
    )

    # DEF-113's core: a narrow run writes a shard about ONE journey, and the
    # other journeys' records must still be there. Two shards, one journey each.
    both = with_evidence(
        [
            {"journeys": {"J77": record(age_seconds=600)}},
            {"journeys": {"J78": record()}},
        ],
        # The spec is older than BOTH records, so neither is stale and the only
        # thing under test is whether the narrow shard displaced the wide one.
        spec_mtime_offset=-1800.0,
    )
    check(
        "7. a narrow run's shard does NOT displace another journey's record",
        both == [],
        f"expected no problems, got {both!r}",
    )

    expect_problem(
        "8. no receipt anywhere is NOT PROVEN (never a pass)",
        with_evidence([]),
        "NO run receipt anywhere",
    )
    expect_problem(
        "9. an unreadable receipt is NOT PROVEN, and says unreadable ≠ absent",
        with_evidence([], corrupt_shard=True),
        "evidence unreadable, not absent",
    )
    expect_problem(
        "10. an UNDATED record is refused (it cannot be aged)",
        with_evidence([{"journeys": {"J77": {"status": "passed", "assertions": 3, "specs": []}}}]),
        "no `recorded_at`",
    )
    expect_problem(
        "11. a STALE record — older than the spec it vouches for — is refused",
        with_evidence([{"journeys": {"J77": record(age_seconds=3600)}}], spec_mtime_offset=-1.0),
        "STALE",
    )
    expect_problem(
        "12. a record found ONLY in the purged legacy path is refused",
        with_evidence([], legacy={"journeys": {"J77": record()}}),
        "the next run of anything deletes it",
    )
    expect_problem(
        "13. a red journey cannot close a wave",
        with_evidence([{"journeys": {"J77": record(status="failed")}}]),
        "a wave cannot close red",
    )
    expect_problem(
        "14. a journey that passed asserting NOTHING is refused",
        with_evidence([{"journeys": {"J77": record(assertions=0)}}]),
        "ZERO executed assertions",
    )


def main() -> int:
    print("G12 self-test — breaking the journey gate on purpose, one break at a time")
    frontmatter_cases()
    receipt_cases()
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks held")
    if FAILURES:
        print("\nG12 SELF-TEST FAILED. A gate check that cannot be made to fail is not a check:")
        for name in FAILURES:
            print(f"  · {name}")
        return 1
    print("Every G12 check above was seen RED on the defect it exists for (law 7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
