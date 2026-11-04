#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-7991 (2026-09-29) — the Product Owner, on the One-time bill
#          screen: "R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-
#          25fa070287cc' are in force for 'sewer' on 2026-10-29 (01a0b366-…,
#          01a0b388-…, 01a0b424-…, 01a0e712-…)". FOUR database uuids, read by
#          a clerk, on a live screen.
# Rules:   B14 rule 31 — PO verbatim, *"no Databse ID on screen - that is a
#          rule"* · rule 32 (no rule id or internal code in clerk-facing copy)
#          · rule 33 (six words a sentence; rationale is ZERO words on screen)
#          · BR-SHL-020 r2 (server detail text does not reach customer screens)
#          · CLAUDE.md hard-won law 7 (prove a guard RED first, in the harness
#          that will RUN it, and say what it cannot see WITH A NUMBER)
# Impacts: G28 (rule 31's string half — it reads SOURCE and cannot see an
#          f-string's runtime value) · G69 (a sliced or joined id in frontend
#          source — also source) · G32 (every raised key resolves)
# ───────────────────────────────────────────────────────
"""G139 — A DATABASE UUID MAY NOT REACH A CLERK THROUGH A REFUSAL.

WHY THE THREE CHECKS THAT ALREADY COVER RULE 31 MISSED THIS ONE
----------------------------------------------------------------
* **G28** reads STRINGS, with `ast`. The offending text is an **f-string**:
  `f"R2: {len(bound)} versions of schedule {tariff_id!r} …"`. The source holds
  a placeholder; the uuid exists only at runtime. G28's own docstring already
  concedes it — *"a uuid-shaped VALUE in a field is the one thing G28 cannot
  see"* — and its part-3 baseline PARKS eleven `resolution.py` sites on the
  measured argument that *"this prose reaches the audit row and the server log
  and stops there"*. **That argument was true of an ApiError and false of this
  path**, which is why a truthful baseline covered a live leak for weeks.
* **G69** reads FRONTEND SOURCE for a sliced or joined id. Nothing is sliced
  here; the screen renders a server string whole.
* **`refusalParams`** (`api/client.ts:204`, `delete rest.detail`) is
  `BR-SHL-020 r2`'s enforcement and it strips `detail` from an **ApiError's
  params**. Every string this gate exists for arrives in a **200-response
  body**. The guard existed and was not anywhere near the shape.

WHAT THIS GATE DOES INSTEAD — IT RUNS THE ENGINE
------------------------------------------------
A source grep cannot see an f-string's value, so this one **provokes the
refusal and reads what comes out**. `apps.rating.resolution` is a pure module
over frozen dataclasses — no Django, no database — so each refusal can be
raised in-process from a catalogue whose every id is a real uuid, and the
CLERK-FACING payload inspected as the wire would carry it:

    resolution.clerk_refusal(exc) -> {"message_key", "detail", "message_params"}

Three assertions per case:

  1. **no uuid, anywhere** — not in `detail`, not in `message_key`, not in any
     value of `message_params`. Dashed and bare-32-hex both;
  2. **the key resolves** in `en.json` (G32 asks this of the dict literal; this
     asks it of the object the chain actually raised);
  3. **`detail` IS the `en` sentence, interpolated** — the same tie
     `test_def_bil_5339_clerk_facing_copy.py` holds over `budget_api`, so the
     backend mirror and the catalogue cannot drift apart.

The ENGINEER's sentence — `str(exc)` — is deliberately NOT checked. It keeps
its uuids on purpose: it is the log line, the audit row and the shadow
report's own field, and `DEF-CUS-6464` is the record of what removing a
sentence altogether costs.

WHAT WOULD MAKE IT PASS WRONGLY, SAID OUT LOUD AND PRINTED IN ITS OUTPUT
------------------------------------------------------------------------
This is law 7's habit 2, and the honest answer is that **this gate covers nine
raise sites out of thirty-six and four render sites out of an unknown total**.

  * A tenth raise site could start interpolating an id tomorrow and this gate
    would not see it, because it exercises a NAMED list of cases rather than
    discovering them. Mitigated, not cured: `CASES` below is asserted against
    the set of sites that state a `message_key`, so a site that GAINS one
    without gaining a case here fails, and the SKIPPED count is printed beside
    the checked count on every run — `G32` reported `0 unresolved` truthfully
    over 21 live refusals, and a blind spot with no number beside it is
    indistinguishable from an empty one.
  * It reads a PAYLOAD and not a rendered screen. No check in this repository
    reads rendered output (CLAUDE.md's own note on B14), so the client half is
    held by `refusalSentence`'s uuid branch and its unit test instead, and the
    number of render sites NOT covered is printed too.
  * It cannot see a refusal raised by another module and served on the same
    screens. That is 27 further `resolution.py` sites plus every
    `GatherProblem` — counted and printed, never claimed as clean.

HOW IT WAS PROVED RED (law 7, and in `run()`, not `__main__`)
--------------------------------------------------------------
`10-scripts/tests/g137_red_proof.py` reverts the fix in memory — it calls the
chain and reads `str(exc)` where the gate reads `clerk_refusal(exc)` — and
asserts this module's own `check()` returns violations. It is run through
`run()`, the entry point `run_gates` uses, because `G85` and `G87` were each
shown red through `__main__` and announced green while the suite reported
`gate crashed: AttributeError: module has no attribute 'run'` (DEF-GOV-3733).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "06-backend"
EN = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
CHAIN = BACKEND / "apps" / "rating" / "resolution.py"

#: Dashed uuid, and the bare 32-hex form. `G69`'s own measurement is why the
#: 8-hex truncation is NOT matched here: `01a00000` is not uuid-shaped and
#: reads like a reference number, so it belongs to a source check, not to this
#: one, and claiming it would produce false positives on real account numbers.
UUID_SHAPED = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\b[0-9a-f]{32}\b",
    re.IGNORECASE,
)

#: Real uuids, so a leak looks exactly like the one the PO photographed.
PLAN_ID = "01a0b366-61fa-7f50-8cc4-25fa070287cc"
TARIFF_ID = "01a0b366-61fa-7f50-8cc4-25fa070287cc"
OTHER_TARIFF = "01a0c000-1111-7000-8000-000000000001"
VERSION_IDS = (
    "01a0b366-6200-75a1-b0ca-a47e7ba7f490",
    "01a0b388-86ba-726e-91c9-1ad57e082b3b",
    "01a0b424-e5ce-7b18-81b9-b696cbbfc1ff",
    "01a0e712-0c79-7c63-988e-e54d1173aa8e",
)
ON = date(2026, 10, 29)
IN_FORCE = {"effective_from": date(2026, 1, 1), "effective_to": date(2026, 12, 31)}

#: How many `raise` statements the chain holds in total, and how many of them
#: this gate exercises. The difference is PRINTED, never implied.
#: 9 until 2026-10-01; R2's two ambiguity refusals were retired by `BR-RAT-1055`.
CHECKED_RAISE_SITES = 7
#: The screens that render a served refusal. Four are wired through
#: `api/refusalSentence.ts`; none is read by this gate, which reads payloads.
RENDER_SITES_NOT_READ = 4


def _chain():
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from apps.rating import resolution  # noqa: PLC0415 — the module under test

    return resolution


def _cases(r) -> list[tuple[str, Exception]]:
    """Every uuid-bearing refusal, RAISED, with real uuids in the catalogue."""
    plan = r.PlanVersion(
        plan_id=PLAN_ID, version=1, services=("sewer",),
        schedules={"sewer": TARIFF_ID}, **IN_FORCE,
    )
    twin = r.PlanVersion(
        plan_id=OTHER_TARIFF, version=2, services=("sewer",),
        schedules={"sewer": TARIFF_ID}, **IN_FORCE,
    )
    def version(vid: str, *, service: str = "sewer", tariff: str = TARIFF_ID, **kw):
        return r.ScheduleVersion(
            version_id=vid, service=service, tariff_id=tariff,
            **{**IN_FORCE, **kw},
        )

    account = r.AccountFacts(account_no="A-10432", unit_id="unit-1")
    meter = r.MeterFacts(service="sewer", connection_size='2"')
    out: list[tuple[str, Exception]] = []

    def caught(label, fn):
        try:
            fn()
        except r.ResolutionError as exc:
            out.append((label, exc))
        else:  # pragma: no cover — a case that stopped refusing is a real find
            out.append((label, AssertionError(f"{label}: nothing was raised")))

    all_versions = tuple(version(v) for v in VERSION_IDS)

    # R1 — two plan versions in force
    caught("R1 plans ambiguous", lambda: r.resolve_plan(
        r.Catalogue(plan_versions=(plan, twin), schedule_versions=all_versions),
        account, ON))
    # R2 — the plan binds no schedule to the service
    unbound = r.PlanVersion(plan_id=PLAN_ID, version=1, services=("sewer",), schedules={}, **IN_FORCE)
    caught("R2 no schedule bound", lambda: r.resolve_schedule(
        r.Catalogue(plan_versions=(unbound,), schedule_versions=()), unbound, "sewer", ON))
    # R2 — bound, but no version in force on the date
    retired = version(VERSION_IDS[0], effective_from=date(2020, 1, 1), effective_to=date(2020, 12, 31))
    caught("R2 no version in force", lambda: r.resolve_schedule(
        r.Catalogue(plan_versions=(plan,), schedule_versions=(retired,)), plan, "sewer", ON))
    # R2 — FOUR versions in force. THE SENTENCE THE PO PHOTOGRAPHED. ⚠ RETIRED
    # 2026-10-01 with its raise site: PO ruling on `DEF-RAT-8004` (option A,
    # `BR-RAT-1055`) — the newest prices and the bill-run Check names the
    # overlap, so there is no refusal left here to carry a uuid.

    one = (version(VERSION_IDS[0]),)
    base = r.Catalogue(plan_versions=(plan,), schedule_versions=one)
    # R2 override — a schedule this utility does not have
    caught("R2 override missing", lambda: r.resolve_schedule_with_override(
        base, plan, "sewer", ON, override_tariff_id=OTHER_TARIFF))
    # R2 override — a schedule that prices another service
    wrong = r.Catalogue(
        plan_versions=(plan,),
        schedule_versions=one + (version(VERSION_IDS[1], service="water", tariff=OTHER_TARIFF),),
    )
    caught("R2 override wrong service", lambda: r.resolve_schedule_with_override(
        wrong, plan, "sewer", ON, override_tariff_id=OTHER_TARIFF))
    # R2 override — retired
    gone = r.Catalogue(
        plan_versions=(plan,),
        schedule_versions=one + (version(
            VERSION_IDS[1], tariff=OTHER_TARIFF,
            effective_from=date(2020, 1, 1), effective_to=date(2020, 12, 31)),),
    )
    caught("R2 override retired", lambda: r.resolve_schedule_with_override(
        gone, plan, "sewer", ON, override_tariff_id=OTHER_TARIFF))
    # R2 override — two versions of the overriding schedule: RETIRED 2026-10-01
    # with the case above, for the same ruling (`BR-RAT-1055`).
    # R3 — the size is on the schedule with a BLANK base
    blank = r.ScheduleVersion(
        version_id=VERSION_IDS[0], service="sewer", tariff_id=TARIFF_ID,
        size_rows={'2"': None}, **IN_FORCE,
    )
    caught("R3 blank base", lambda: r.resolve_size_row(blank, meter))
    return out


def _sites_that_state_a_key() -> int:
    """How many `raise` sites in the chain pass a `message_key`, read with ast.

    ⚠ **THIS IS THE CLAUSE THAT STOPS THE CASE LIST GOING STALE.** A tenth site
    that starts stating a key, with no case added here, moves this number past
    `CHECKED_RAISE_SITES` and the gate fails by name rather than quietly
    covering nine of ten.
    """
    tree = ast.parse(CHAIN.read_text(encoding="utf-8"))
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if any(k.arg == "message_key" for k in node.exc.keywords):
            total += 1
    return total


def _all_raise_sites() -> int:
    tree = ast.parse(CHAIN.read_text(encoding="utf-8"))
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Raise))


def check() -> tuple[list[str], list[str]]:
    """(violations, notes). Notes carry the SKIPPED counts, always."""
    violations: list[str] = []
    r = _chain()
    catalogue = json.loads(EN.read_text(encoding="utf-8"))
    cases = _cases(r)

    for label, exc in cases:
        if isinstance(exc, AssertionError):
            violations.append(str(exc))
            continue
        clerk = r.clerk_refusal(exc)
        if clerk is None:
            violations.append(f"{label}: states no clerk sentence — a uuid is all a screen has")
            continue
        key = str(clerk["message_key"])
        detail = str(clerk["detail"])
        params = dict(clerk["message_params"])
        for field, text in [("detail", detail), ("message_key", key)] + [
            (f"message_params[{n}]", str(v)) for n, v in params.items()
        ]:
            hit = UUID_SHAPED.search(text)
            if hit:
                violations.append(f"{label}: a database uuid reaches a clerk in {field} — {hit.group(0)}")
        if key not in catalogue:
            violations.append(f"{label}: {key} resolves to nothing — a clerk would read the key")
            continue
        expected = catalogue[key].replace("{{", "{").replace("}}", "}")
        try:
            rendered = expected.format(**{**params, "service": _titled(params.get("service", ""))})
        except (KeyError, IndexError) as gap:
            violations.append(f"{label}: {key} interpolates {gap} which the server does not state")
            continue
        if rendered != detail:
            violations.append(
                f"{label}: the backend mirror and en.json have drifted\n"
                f"    detail : {detail!r}\n    en.json: {rendered!r}"
            )

    stating = _sites_that_state_a_key()
    if stating != CHECKED_RAISE_SITES:
        violations.append(
            f"{stating} raise site(s) in resolution.py state a message_key and this gate "
            f"exercises {CHECKED_RAISE_SITES}. Add the case, or lower CHECKED_RAISE_SITES."
        )

    total = _all_raise_sites()
    notes = [
        f"checked {len(cases)} refusal payload(s) raised by the live chain",
        f"SKIPPED: {total - CHECKED_RAISE_SITES} of {total} `raise` sites in "
        f"{CHAIN.relative_to(REPO_ROOT)} state no message_key and are NOT exercised here — "
        "they name no id today and nothing in this gate would notice if one started",
        f"SKIPPED: {RENDER_SITES_NOT_READ} render site(s) — this gate reads PAYLOADS, never "
        "rendered output. The client half is api/refusalSentence.ts and its unit test",
    ]
    return violations, notes


def _titled(service: str) -> str:
    """The backend's own English title-caser, mirrored so the tie can be made."""
    return service.replace("_", " ").capitalize() if service else ""


def main() -> int:
    violations, notes = check()
    for note in notes:
        print(f"  · {note}")
    for line in violations:
        print(f"FAIL: {line}")
    if violations:
        print(f"\n{len(violations)} clerk-facing refusal problem(s). B14 rule 31.")
        return 1
    print("\nno database uuid reaches a clerk through a rating refusal")
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    try:
        violations, notes = check()
    except Exception as crash:  # pragma: no cover — a crash must not read as a pass
        return "FAIL", f"gate could not run the chain: {type(crash).__name__}: {crash}"
    skipped = "; ".join(notes[1:])
    if violations:
        return "FAIL", f"{len(violations)} clerk-facing refusal problem(s): {violations[0][:110]}"
    return "PASS", f"{notes[0]}; {skipped}"


if __name__ == "__main__":
    raise SystemExit(main())
