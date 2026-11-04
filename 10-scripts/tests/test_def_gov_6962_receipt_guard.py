"""DEF-GOV-6962 — a finished isolation proof survives a checkout refresh, and a
worse receipt does not replace a better one.

Run: python3 10-scripts/tests/test_def_gov_6962_receipt_guard.py
     (or under pytest; it is plain asserts and imports no django)

WHAT HAPPENED
-------------
`prove_isolation.py` wrote its only detailed record to
`12-governance/isolation-receipt.json` — a TRACKED file. On 2026-09-27 a
67-minute run finished FAIL (9 failed, 11 errored, 301 passed) and the receipt
was overwritten minutes later by an ordinary restore-from-branch. The counts
survived in a lane's notes; **the names of the twenty cases did not**, and
naming them is the one thing the receipt exists for (it was added for exactly
that reason after a 2026-09-07 receipt said *"1 failed"* and named nothing).
`12-governance/isolation-reproof-2026-09-25.md` §4 recorded the same class of
loss two days earlier from an interrupted run.

WHAT WOULD MAKE THIS TEST PASS WRONGLY (hard-won law 7, habit 2)
----------------------------------------------------------------
* **Asserting only that the archive file exists.** An empty or truncated file
  exists too. Every case reads the archive back and compares the failing-case
  NAMES, which is the payload that was lost.
* **Asserting only the refusals.** A `main()` that refused everything would
  pass those and record nothing ever again, which is worse than the defect.
  Case 1 asserts the ordinary newer-run path still WRITES.
* **Proving the guard on a receipt the archive never saw.** The whole design is
  that a refusal loses nothing, so every refusal case asserts the archive
  copy IS there afterwards.
* **Comparing `taken_on` as a string.** `"2026-09-27 09:07 UTC"` sorts after
  `"2026-09-07 18:32 UTC"` alphabetically AND chronologically, so a string
  comparison passes the obvious case and fails a format change silently. Case 4
  uses a pair where the two orderings agree and case 5 asserts the parser
  itself returns None on a shape it cannot read, rather than a date.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "10-scripts"))

import prove_isolation as pi  # noqa: E402

GOOD = {
    "failing_cases": ["FAILED tests/test_iso.py::test_cross_tenant_search"],
    "migration_digest": "70b163e9ec69c9e4",
    "taken_on": "2026-09-25 18:32 UTC",
    "role": "smartbillhub",
    "database": "localhost, test_sbh_gate_iso_70b163e9ec69c9e4",
    "summary": "1 failed, 294 passed, 1 skipped",
    "passed": 294, "failed": 1, "errors": 0, "skipped": 1, "vendor_skips": 0,
}
EMPTY = {**GOOD, "failing_cases": [], "summary": "no output",
         "taken_on": "2026-09-27 09:07 UTC",
         "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
NEWER = {**GOOD, "taken_on": "2026-09-27 12:40 UTC",
         "failing_cases": ["ERROR tests/test_iso.py::test_rls_forced"],
         "passed": 301, "failed": 9, "errors": 11, "skipped": 0}
OLDER = {**GOOD, "taken_on": "2026-09-07 08:00 UTC",
         "failing_cases": ["FAILED tests/test_iso.py::test_ancient"]}


def _run(tmp: Path, receipt: dict, on_disk: dict | None) -> tuple[int, dict | None, list[Path]]:
    """Drive `main()` with a stubbed proof, a private receipt path and a private
    archive. Returns (exit code, what the receipt holds after, archive files)."""
    repo_receipt = tmp / "isolation-receipt.json"
    if on_disk is not None:
        repo_receipt.write_text(json.dumps(on_disk), encoding="utf-8")
    archive = tmp / "archive"
    pi.ARCHIVE = archive
    pi.g5.RECEIPT = repo_receipt
    pi.g5.common.REPO_ROOT = tmp
    pi.g5.prove = lambda: ("FAIL", "stubbed", receipt)
    code = pi.main()
    after = json.loads(repo_receipt.read_text(encoding="utf-8")) if repo_receipt.exists() else None
    return code, after, sorted(archive.glob("*.json")) if archive.exists() else []


def main() -> int:
    import tempfile

    # 1 · the ordinary path — a newer real run REPLACES the recorded one, and is
    #     archived as well. Without this the other cases are satisfied by a
    #     program that never records anything.
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        code, after, kept = _run(tmp, NEWER, GOOD)
        assert code == 1, "a FAIL verdict still exits non-zero"
        assert after is not None and after["taken_on"] == NEWER["taken_on"], after
        assert after["failing_cases"] == NEWER["failing_cases"]
        assert len(kept) == 1, kept
        assert json.loads(kept[0].read_text())["failing_cases"] == NEWER["failing_cases"]

    # 2 · a run that reports NO CASES does not replace one that does…
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        code, after, kept = _run(tmp, EMPTY, GOOD)
        assert code == 1
        assert after == GOOD, "the last real proof must be left exactly as it was"
        # …and the refused run is still on disk, outside the repository.
        assert len(kept) == 1 and json.loads(kept[0].read_text())["summary"] == "no output"

    # 3 · an OLDER run does not replace a newer recorded one — which is what a
    #     stale checkout re-running an old tree looks like from here.
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        code, after, kept = _run(tmp, OLDER, GOOD)
        assert code == 1
        assert after == GOOD, after
        assert len(kept) == 1 and json.loads(kept[0].read_text())["taken_on"] == OLDER["taken_on"]

    # 4 · with nothing recorded at all, a real run records. A guard that refused
    #     an empty slot would make the first proof on a fresh checkout impossible.
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        code, after, kept = _run(tmp, GOOD, None)
        assert after is not None and after["taken_on"] == GOOD["taken_on"]
        assert len(kept) == 1

    # 5 · two runs in the same minute do not overwrite each other in the archive.
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _run(tmp, GOOD, None)
        code, after, kept = _run(tmp, GOOD, GOOD)
        assert len(kept) == 2, kept

    # 6 · the date comparison is a PARSE, not a string sort: an unreadable
    #     `taken_on` yields None and the guard then declines to order the two
    #     rather than guessing. A string comparison cannot express that.
    assert pi.taken_at({"taken_on": "2026-09-25 18:32 UTC"}) is not None
    assert pi.taken_at({"taken_on": "yesterday"}) is None
    assert pi.taken_at({}) is None
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        code, after, kept = _run(tmp, {**GOOD, "taken_on": "yesterday"}, NEWER)
        assert after is not None and after["taken_on"] == "yesterday", \
            "an unorderable pair is recorded, not silently refused"

    print("DEF-GOV-6962: 6 case(s) pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
