"""G12 - journey gate (B12 r2): every activated E2E journey green at wave close.

WHAT THIS GATE WAS UNTIL 2026-08-11, and why that had to end:

    def run() -> tuple[str, str]:
        return "SKIP", "wave-close gate — run via run_gates.py --wave-close once journeys are automated"

A hardcoded return. Not a check that found nothing — a function that cannot fail,
in the row of a table that reads "18 PASS · 0 FAIL · 1 SKIP" on every merge. It
is the same shape as the `qa.yml` job that printed *"Passing by design"* for
weeks (DEF-057), and the PO's ruling of that day — **"we ahve to prove against
human clicking"** — is what makes leaving it unacceptable now that a browser
suite exists to gate.

G12 IS A PO-RATIFIED GATE (run_gates.py header: G1–G16 are the confirmed
merge-blocking set, PO 2026-08-11 option A). Changing one is a PROCESS EVENT, not
a refactor: this rewrite is recorded in 12-governance/02-decision-log.md
(2026-08-11, "G12 made real") and is REPORTED to the PO batch for ratification.
It only ever gets STRICTER — the gate now FAILs where it used to SKIP, and there
is no path through it that a hardcoded return could take.

WHAT IT CHECKS (per merge — everything here is repo-readable, no stack needed):

  1. **The index is fresh.** `08-qa/01-e2e/01-journey-story-index.json` is the
     machine view of the activation authority. G12 re-derives it in memory and
     fails on any difference, so a hand-edit or a stale copy cannot make the
     activated list say what the journeys do not (hard-won law 5).
  2. **A spec named for a journey claims that journey.** `J12.spec.ts` must call
     `journey("J12", …)`. A file that looks like an activation and is not one is
     the false comfort this whole lane exists to stop.
  3. **A spec claiming a journey is named for it.** The reverse direction, so a
     journey cannot be claimed from a file nobody would look in.
  4. **No spec claims a journey that does not exist** in the catalog.
  5. **No spec claims a journey whose declared stories are not all built.**
     `ready_by_stories: false` in the index means the wiring index says this
     journey's last story is NOT built yet, so a spec claiming it is asserting a
     flow the product cannot perform end to end (DEF-057's exact class).
  6. **Every journey file's own frontmatter parses.** Added 2026-08-15. Until
     then NOTHING in this repository refused a journey file whose `id:` or
     `stories:` frontmatter could not be read: the generator falls back to
     `path.name.split("-")[0]` for a missing id — which yields the id `T3M` for
     `T3M-001-flat-cycle-full.md` — and treats an unparseable `stories:` line as
     "declares no stories", which the index then reports as `ready_by_stories:
     null`, i.e. neither ready nor unready, in no count anyone quotes. A
     malformed journey file was INVISIBLE rather than loud. It is loud now:
     an unreadable id, an id that disagrees with its filename, an unparseable
     stories list, a non-story token inside one, or two files claiming one id
     all FAIL. A file with NO frontmatter block at all is still allowed (J6
     predates the convention and says so) — silence is a documented state; a
     half-written declaration is not.

WHAT `--wave-close` ADDS (B12 r2's actual requirement — green, not merely
present): every activated journey must appear in a FRESH run receipt from the
Playwright suite with status `passed` and a non-zero assertion count. A missing
receipt, a record older than the spec it vouches for, an undated record or a
journey recorded skipped/failed FAILS the wave. That is the half no repo-only
check can do: a spec file proves someone wrote it, and only a receipt proves it
ran.

WHERE THE RECEIPT IS READ FROM, AND WHY IT MOVED (DEF-113, 2026-08-15):

    The receipt used to be read from `07-frontend/test-results/journey-run.json`
    — inside Playwright's `outputDir`, **which Playwright purges at the start of
    every run**. With five journey lanes in one working tree, a genuine receipt
    vanished within NINE SECONDS of the run that produced it, twice, and two
    full wave-close runs reported "no run receipt" while a real one had existed
    minutes earlier. So a wave-close answer read off that path was never an
    answer about this tree — it was an answer about whichever lane finished most
    recently, and a GREEN one was the more dangerous direction.

    Evidence now lives in `07-frontend/journey-evidence/`, which no run purges:
    one immutable shard per run under `runs/`, plus a merged view folded from
    them. This gate FOLDS THE SHARDS ITSELF rather than trusting the merged file,
    so a merged file that is missing, corrupt or mid-write costs nothing. Each
    record carries its own `recorded_at`, so a narrow run (`--grep J23`) refreshes
    one journey and every other journey keeps the timestamp it was really
    produced at — and this gate ages each one SEPARATELY against the spec file
    that claims it. The old path is still read, last and lowest-precedence, for a
    tree whose census predates the change; a record found only there is accepted
    but SAID SO, because that file is destroyed by the next run of anything.

    Everything here fails closed (hard-won law 3): a missing receipt, an
    unparseable one, a record with no timestamp and a record older than its spec
    all read as NOT PROVEN. There is no path through this gate on which absent
    evidence becomes a pass.

Today the catalog has 303 journeys and ZERO activations, so checks 2–5 pass
vacuously and say so with the count. That is not the same statement as the old
SKIP: it is "nothing claims a journey", asserted, rather than "this gate does not
look".
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import common

GENERATOR = common.REPO_ROOT / "10-scripts" / "07-e2e-wiring-index.py"
INDEX_JSON = common.REPO_ROOT / "08-qa" / "01-e2e" / "01-journey-story-index.json"
JOURNEY_DIR = common.REPO_ROOT / "08-qa" / "01-e2e" / "journeys"
SPEC_DIR = common.REPO_ROOT / "07-frontend" / "e2e"

# The durable evidence tree (DEF-113). NOT under test-results/ — nothing purges it.
EVIDENCE_DIR = common.REPO_ROOT / "07-frontend" / "journey-evidence"
EVIDENCE_RUNS_DIR = EVIDENCE_DIR / "runs"
MERGED_RECEIPT = EVIDENCE_DIR / "journey-run.json"
# The pre-DEF-113 path. Read last, believed least: Playwright deletes it.
LEGACY_RECEIPT = common.REPO_ROOT / "07-frontend" / "test-results" / "journey-run.json"

# `journey("T5-04", …)` / `journey('J12', …)` — the support-kit call that claims
# a catalog id (07-frontend/e2e/support/journey.ts).
JOURNEY_CALL_RE = re.compile(r"""journey\(\s*["']([^"']+)["']""")

# A record older than the spec it vouches for was written before that spec
# existed, so it cannot say anything about it. No grace period: re-running the
# suite is cheap and a wave close is not.
RECEIPT_STALE_SECONDS = 0

# ── The journey-file frontmatter grammar (check 6) ──────────────────────────
# `id: J12` / `id: T3M-001`. Anchored and whole-line: `id: 24` and a bare `id:`
# must FAIL rather than fall through to a filename guess.
FRONTMATTER_ID_RE = re.compile(r"^id:(.*)$", re.M)
VALID_JOURNEY_ID_RE = re.compile(r"^[JT][A-Za-z0-9]*(?:-\d+)?$")
# `stories: [US-BIL-001, US-BIL-002]`, possibly wrapped over lines.
FRONTMATTER_STORIES_LINE_RE = re.compile(r"^stories:(.*)$", re.M)
FRONTMATTER_STORIES_LIST_RE = re.compile(r"^stories: \[(.*?)\]", re.M | re.S)
WHOLE_US_ID_RE = re.compile(r"^US-[A-Z]{3}-\d{3,6}$")
# `T3M-001-flat-cycle-full.md` → `T3M-001`; `J6-corrections.md` → `J6`.
FILENAME_ID_RE = re.compile(r"^([JT][A-Za-z0-9]*(?:-\d+)?)")


def _index() -> tuple[dict | None, str]:
    if not INDEX_JSON.is_file():
        return None, f"{common.rel(INDEX_JSON)} is missing — run 10-scripts/07-e2e-wiring-index.py"
    try:
        return json.loads(common.read_text(INDEX_JSON)), ""
    except json.JSONDecodeError as exc:
        return None, f"{common.rel(INDEX_JSON)} is not valid JSON: {exc}"


def _index_is_fresh() -> str | None:
    """None when both generated views match the journeys; else the failure text."""
    if not GENERATOR.is_file():
        return f"{common.rel(GENERATOR)} is missing — the index has no generator"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=str(common.REPO_ROOT),
    )
    if result.returncode != 0:
        return (result.stdout + result.stderr).strip().splitlines()[-1]
    return None


def _spec_texts() -> dict[str, str]:
    if not SPEC_DIR.is_dir():
        return {}
    return {p.name: common.read_text(p) for p in sorted(SPEC_DIR.glob("*.spec.ts"))}


def _static_problems(index: dict) -> list[str]:
    catalog = {j["id"]: j for j in index["journeys"]}
    problems: list[str] = []
    for name, text in _spec_texts().items():
        stem = name[: -len(".spec.ts")]
        claimed = sorted(set(JOURNEY_CALL_RE.findall(text)))
        # (2) named for a journey ⇒ must claim it.
        if stem in catalog and stem not in claimed:
            problems.append(
                f"e2e/{name} is named for journey {stem} but never calls journey(\"{stem}\", …) — "
                "a file that looks like an activation and is not one"
            )
        for jid in claimed:
            # (4) claims something the catalog does not define.
            if jid not in catalog:
                problems.append(
                    f"e2e/{name} claims journey {jid}, which is not in 08-qa/01-e2e/journeys/"
                )
                continue
            # (3) claims a journey ⇒ must live in <ID>.spec.ts.
            if stem != jid:
                problems.append(
                    f"e2e/{name} claims journey {jid} — the convention is {jid}.spec.ts "
                    "(e2e/README.md §Journey activation)"
                )
            # (5) claims a journey whose last story is not built.
            if catalog[jid]["ready_by_stories"] is False:
                problems.append(
                    f"e2e/{name} claims journey {jid}, whose stories are not all built "
                    f"({', '.join(catalog[jid]['stories_unbuilt'])}) — the wiring index has not "
                    "activated it"
                )
    return problems


def _rel(path: Path) -> str:
    """`common.rel`, but it never raises on a path outside the repo.

    `g12_selftest.py` points these constants at a temporary directory to prove
    each failure mode RED, and a message-formatting crash there would make the
    guard's own proof impossible to write — which is how a check quietly stops
    being checkable.
    """
    try:
        return common.rel(path)
    except ValueError:
        return str(path)


def _frontmatter_problems() -> list[str]:
    """Check 6 — a journey file whose own frontmatter cannot be read is REFUSED.

    The hole this closes, precisely: `10-scripts/07-e2e-wiring-index.py` never
    fails on a journey file. A missing `id:` silently becomes
    `path.name.split("-")[0]` (so `T3M-001-flat-cycle-full.md` would index as the
    id `T3M`, colliding with 146 siblings), and a `stories:` line the list regex
    cannot read silently becomes "declares no stories", which the index reports as
    `ready_by_stories: null` — a third state that appears in no count. Neither
    outcome is an error anywhere. A typo therefore removed a journey from the
    activation authority without a single red light.

    The refusal lives HERE rather than in the generator on purpose: the generator
    must keep producing an index for this gate to compare against (a generator
    that dies produces no evidence at all), and a gate is the thing that blocks a
    merge. The generator's docstring points at this function.

    A file carrying NO frontmatter block at all stays legal — J6 predates the
    convention and its own text says so. The rule is about a declaration that is
    half-written, not about one that was never made.
    """
    if not JOURNEY_DIR.is_dir():
        return [f"{_rel(JOURNEY_DIR)} is missing — the journey catalog has no directory"]
    problems: list[str] = []
    claimed_by: dict[str, list[str]] = {}
    for path in sorted(list(JOURNEY_DIR.glob("T*.md")) + list(JOURNEY_DIR.glob("J*.md"))):
        text = common.read_text(path)
        stem = path.name[: -len(".md")]
        name = f"journeys/{path.name}"

        id_line = FRONTMATTER_ID_RE.search(text)
        if id_line is None:
            # No id declared at all: legal only for a file with no frontmatter
            # fence, and its id is then its filename (the generator's fallback).
            filename_id = FILENAME_ID_RE.match(stem)
            if filename_id is None:
                problems.append(
                    f"{name} declares no `id:` and its filename yields no journey id either — "
                    "the wiring index would invent one"
                )
                continue
            claimed_by.setdefault(filename_id.group(1), []).append(name)
            continue

        jid = id_line.group(1).strip()
        if not jid:
            problems.append(f"{name} has an EMPTY `id:` — the wiring index falls back to the filename")
            continue
        if not VALID_JOURNEY_ID_RE.match(jid):
            problems.append(
                f"{name} declares `id: {jid}`, which is not a journey id "
                "(J<n> / T<tier>[M|P]-<nnn>) — the wiring index cannot read it and falls back "
                "to the filename"
            )
            continue
        if stem != jid and not stem.startswith(f"{jid}-"):
            problems.append(
                f"{name} declares `id: {jid}` but is not named for it — the catalog names files "
                "after ids, and a spec is matched to a journey by FILENAME (check 3), so these "
                "two disagreeing means one of them is unreachable"
            )
        claimed_by.setdefault(jid, []).append(name)

        stories_line = FRONTMATTER_STORIES_LINE_RE.search(text)
        if stories_line is None:
            continue
        stories_list = FRONTMATTER_STORIES_LIST_RE.search(text)
        if stories_list is None:
            problems.append(
                f"{name} has a `stories:` line the index cannot parse "
                f"(`stories:{stories_line.group(1)[:40]}`) — the expected form is "
                "`stories: [US-XXX-000, …]`; as written the journey indexes as declaring NO "
                "stories, which is reported as neither ready nor unready"
            )
            continue
        tokens = [t.strip() for t in stories_list.group(1).replace("\n", " ").split(",") if t.strip()]
        junk = [t for t in tokens if not WHOLE_US_ID_RE.match(t)]
        if junk:
            problems.append(
                f"{name} declares `stories:` containing {junk!r}, which are not US-IDs — the "
                "index keeps only what matches US-XXX-000 and drops the rest SILENTLY, so the "
                "journey would index as needing fewer stories than it names"
            )
    for jid, files in sorted(claimed_by.items()):
        if len(files) > 1:
            problems.append(
                f"journey id {jid} is claimed by {len(files)} files ({', '.join(files)}) — the "
                "index keys journeys by id, so all but one disappear"
            )
    return problems


def _receipt_records() -> tuple[dict[str, dict], list[str], list[str]]:
    """(journey-id → newest record, sources read, problems) across every evidence store.

    Folds the per-run shards itself (DEF-113): they are immutable, so folding
    them is safe while another run is writing a NEW one, and a merged file that
    is corrupt or missing costs nothing. Newest `recorded_at` per journey wins;
    an unparseable store is a REPORTED problem, never a silent zero.
    """
    records: dict[str, dict] = {}
    sources: list[str] = []
    problems: list[str] = []

    def absorb(payload: dict, origin: str) -> None:
        journeys = payload.get("journeys")
        if not isinstance(journeys, dict):
            problems.append(f"{origin} carries no `journeys` object — it is not a run receipt")
            return
        for jid, record in journeys.items():
            if not isinstance(record, dict):
                problems.append(f"{origin} records journey {jid} as {record!r}, not a record")
                continue
            held = records.get(jid)
            if held is None or str(record.get("recorded_at") or "") > str(held.get("recorded_at") or ""):
                records[jid] = {**record, "_origin": origin}

    def load(path: Path, origin: str) -> None:
        try:
            absorb(json.loads(common.read_text(path)), origin)
            sources.append(origin)
        except json.JSONDecodeError as exc:
            # NOT PROVEN, loudly. An unreadable receipt must never read as "no
            # journeys ran and that is fine" (hard-won law 3).
            problems.append(f"{origin} is not valid JSON: {exc} — evidence unreadable, not absent")

    if EVIDENCE_RUNS_DIR.is_dir():
        for shard in sorted(EVIDENCE_RUNS_DIR.glob("*.json")):
            load(shard, f"journey-evidence/runs/{shard.name}")
    if MERGED_RECEIPT.is_file():
        load(MERGED_RECEIPT, "journey-evidence/journey-run.json")
    if LEGACY_RECEIPT.is_file():
        load(LEGACY_RECEIPT, "test-results/journey-run.json (LEGACY — purged by the next run)")
    return records, sources, problems


def _spec_mtimes_by_journey() -> dict[str, float]:
    """journey-id → mtime of the spec that claims it, so each record ages on its own."""
    newest: dict[str, float] = {}
    for path in SPEC_DIR.glob("*.spec.ts"):
        mtime = path.stat().st_mtime
        for jid in set(JOURNEY_CALL_RE.findall(common.read_text(path))):
            newest[jid] = max(newest.get(jid, 0.0), mtime)
    return newest


def _wave_close_problems(index: dict) -> list[str]:
    activated = index["activated"]
    if not activated:
        return []
    records, sources, problems = _receipt_records()
    if not sources and not problems:
        return [
            f"{len(activated)} activated journey(s) and NO run receipt anywhere — looked in "
            f"{_rel(EVIDENCE_RUNS_DIR)}, {_rel(MERGED_RECEIPT)} and "
            f"{_rel(LEGACY_RECEIPT)}. Boot 08-qa/01-e2e/stack/boot_stack.sh and run "
            "`npx playwright test` in 07-frontend; a spec file proves it was written, "
            "not that it ran"
        ]
    spec_mtime = _spec_mtimes_by_journey()
    for jid in activated:
        record = records.get(jid)
        if record is None:
            problems.append(
                f"journey {jid} is activated and NO run receipt records it — not proven"
            )
            continue
        recorded_at = record.get("recorded_at")
        if not recorded_at:
            problems.append(
                f"journey {jid} has a record with no `recorded_at` — an undated claim that "
                "something passed cannot be aged, so it is not evidence (re-run the suite; the "
                "census has stamped every record since DEF-113)"
            )
            continue
        try:
            recorded = datetime.fromisoformat(recorded_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            problems.append(f"journey {jid} records `recorded_at: {recorded_at!r}`, which is not a time")
            continue
        claimed_at = spec_mtime.get(jid, 0.0)
        if recorded + RECEIPT_STALE_SECONDS < claimed_at:
            age = int(time.time() - recorded)
            problems.append(
                f"journey {jid}'s record is STALE — written {age}s ago, "
                f"{int(claimed_at - recorded)}s BEFORE the spec that claims it was last changed; "
                "it vouches for a file that has since moved. Re-run the suite"
            )
            continue
        if record.get("status") != "passed":
            problems.append(f"journey {jid} last ran {record.get('status')} — a wave cannot close red")
        elif not record.get("assertions"):
            problems.append(
                f"journey {jid} passed with ZERO executed assertions — it asserted nothing"
            )
        elif str(record.get("_origin", "")).startswith("test-results/"):
            problems.append(
                f"journey {jid} is vouched for ONLY by {record['_origin']} — that file lives in "
                "Playwright's output directory and the next run of anything deletes it (DEF-113). "
                "Re-run the suite so a durable shard is written"
            )
    return problems


def run() -> tuple[str, str]:
    stale = _index_is_fresh()
    if stale is not None:
        # ⚠ STALE IS NOT AN EARLY RETURN ANY MORE (`DEF-GOV-9130`). It used to
        # be, and a stale index hid every frontmatter finding behind it: on
        # 2026-10-02 regenerating the index turned G12's one-line "STALE" into
        # thirteen findings that had been there since 2026-09-06 — G17's shape
        # (an early return hid 14 number shares) in a different gate. The
        # frontmatter checks do not read the index, so they are reported beside
        # the staleness; the index-dependent checks still wait for a fresh one,
        # because judging them against a stale index would mislead.
        return "FAIL", common.summarize([stale] + _frontmatter_problems())
    index, error = _index()
    if index is None:
        return "FAIL", error

    problems = _frontmatter_problems() + _static_problems(index)
    wave_close = "--wave-close" in sys.argv[1:]
    if wave_close:
        problems += _wave_close_problems(index)
    if problems:
        return "FAIL", common.summarize(problems)

    activated = index["activated"]
    ready = len(index["ready_by_stories"])
    scope = "wave-close (specs + durable run receipt)" if wave_close else "per-merge (specs + index)"
    if not activated:
        return "PASS", (
            f"{scope}: index fresh, {index['journey_files']} journeys parse, 0 activated "
            f"({ready} story-ready, none claimed by a spec)"
        )
    return "PASS", (
        f"{scope}: index fresh, {index['journey_files']} journeys parse, "
        f"{len(activated)} activated journey(s) ({', '.join(activated)}), all conventions held"
    )


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
