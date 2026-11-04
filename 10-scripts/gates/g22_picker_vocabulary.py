"""G22 — a picker offers the vocabulary its endpoint accepts. Added 2026-08-15
from DEF-114, and from DEF-095 the same day, which is why it is a gate and not
a one-line fix.

THE DEFECT, IN ITS OWN NUMBERS
------------------------------
DEF-114: the S15 unit screen's *Assign plan* picker was filled from
`GET /rate-schedules`. `POST /units/{id}/plan-assignments` resolves the posted
id against **`rate_plans`** — the PO's ruling of 2026-08-11 moved what a unit
holds from a tariff to a plan, `apps/rating/selectors.plan_ref` moved with it,
and the picker did not. So every option the screen offered came back
`422 VAL-005 metering.plan.tariff_unknown`, rendered as *"That plan wasn't
found."* The picker offered two TARIFFS; the published PLAN it should have
offered was not in the list at all.

The consequence was the whole product: `unit_plan_assignments` was EMPTY on a
fully seeded stack, no human anywhere could put a unit on a plan, and BR-MET-040
held **every account activation** behind that step. 21 gates and ~2,000 tests
were green over it, because **both halves were correct on their own**. The
picker's tests asserted the picker; the endpoint's tests asserted the endpoint;
nothing in the repo asked whether the set one offers is the set the other takes.

DEF-095 is the same shape one module along: three finance screens sent their
period as `f.from`/`f.to` under BR-SHL-011's LIST grammar while the servers read
bare `from`/`to`. Its prevention column asks for exactly this comparison —
*"the only kind of check that catches two halves that are each self-consistent"*.

WHAT THIS GATE CHECKS, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------------
It is the STATIC half of a two-lock guard, and it is honest about which half it
is. It needs no database, so it runs in `gates.yml` beside the other 21.

  R1  PATH DRIFT — for every registered pair, the picker wrapper's own path
      literal, re-extracted from `07-frontend/src/api/endpoints.ts`, must equal
      the `list_path` in the register, and the writer wrapper's must equal
      `write_path`. Repointing a picker at a different endpoint without moving
      the register is DEF-114 exactly, and it goes RED here.

  R2  WIRED — the picker wrapper must be CALLED from a screen under
      `src/features/`. A picker nobody calls is dead UI (hard-won law 2), and a
      register row for one is a guard over nothing.

  R3  PROBED — the pair id must appear in the LIVE probe,
      `06-backend/tests/test_def_114_picker_vocabulary.py`. This gate can prove
      the two path literals are the ones the register describes; it cannot prove
      that the ids one endpoint SERVES are ids the other ACCEPTS, because that
      is a fact about rows in a database. Deleting the probe therefore fails
      here rather than quietly halving the guard.

  R4  REGISTER INTEGRITY — every row names a picker and a writer that exist, and
      every field the two locks read is present. A register nobody audits is how
      a gate becomes DEF-077 (a ratified merge-blocking gate that was a hardcoded
      `return SKIP`).

It does NOT claim to discover pickers by itself. "This list of ids feeds that
endpoint's id field" is a fact about a SCREEN's intent, and inferring it from
TypeScript would produce a check that is either silent about the real pairs or
noisy about imaginary ones. The register is explicit, and R2/R3 are what stop it
rotting.
"""

import json
import re
from pathlib import Path

from common import FRONTEND_SRC, REPO_ROOT, read_text, rel

REGISTER = Path(__file__).resolve().parent / "picker_endpoint_pairs.json"
ENDPOINTS_TS = FRONTEND_SRC / "api" / "endpoints.ts"
LIVE_PROBE = REPO_ROOT / "06-backend" / "tests" / "test_def_114_picker_vocabulary.py"

REQUIRED_FIELDS = (
    "id",
    "picker_wrapper",
    "list_path",
    "list_query",
    "writer_wrapper",
    "write_path",
    "id_field",
)

_WRAPPER_RE_CACHE: dict[str, str] = {}


def wrapper_body(source: str, name: str) -> str | None:
    """The source text of `export async function <name>(…)` up to the next
    top-level `export ` — enough to hold the wrapper's own path literal and
    nothing of its neighbour's."""
    start = source.find(f"export async function {name}(")
    if start == -1:
        return None
    tail = source[start + 1 :]
    end = tail.find("\nexport ")
    return tail if end == -1 else tail[:end]


def declared_path(body: str) -> str | None:
    """The API path a wrapper calls, normalised so a template literal and a
    plain string compare as the same shape.

        client.get("/plans", …)                      → /plans
        client.post(`/units/${encodeURIComponent(x)}/plan-assignments`)
                                                     → /units/{}/plan-assignments

    The FIRST call in the body wins: these wrappers are one call each, which is
    the house style (`api/README.md`), and a wrapper that grew a second one is a
    wrapper this gate should stop rather than guess about.
    """
    match = re.search(r"client\.(?:get|post|put|patch|del|request)\b", body)
    if match is None:
        return None
    # A generic argument may sit between the method name and the call —
    # `client.get<Paginated<UnitPlanOption>>(…)` — and it can nest, so the
    # generic is skipped by finding the call paren rather than by matching `<>`:
    # TypeScript type arguments never contain one.
    open_paren = body.find("(", match.end())
    if open_paren == -1:
        return None
    rest = body[open_paren + 1 :].lstrip()
    if not rest or rest[0] not in "\"'`":
        return None
    quote = rest[0]
    rest = rest[1:]
    close = rest.find(quote)
    if close == -1:
        return None
    literal = rest[:close]
    # `${…}` is a path SEGMENT the caller fills; the register writes it `{}`.
    return re.sub(r"\$\{[^}]*\}", "{}", literal)


def picker_call_sites(name: str) -> list[str]:
    """Files under src/features/ that CALL this wrapper (R2, hard-won law 2).
    An import with no call is not a call — that is precisely the dead-UI shape
    G13 exists for, so `<name>(` is the pattern, not `<name>`."""
    hits = []
    features = FRONTEND_SRC / "features"
    if not features.is_dir():
        return hits
    for path in sorted(features.rglob("*")):
        if path.suffix not in (".ts", ".tsx") or path.name.endswith(".test.tsx"):
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", read_text(path)):
            hits.append(rel(path))
    return hits


def run():
    if not REGISTER.is_file():
        return "FAIL", f"{rel(REGISTER)} is missing — the picker/endpoint register is the gate"
    if not ENDPOINTS_TS.is_file():
        return "SKIP", "07-frontend/src/api/endpoints.ts not present"

    register = json.loads(read_text(REGISTER))
    pairs = register.get("pairs") or []
    if not pairs:
        return "FAIL", f"{rel(REGISTER)} declares no pairs — an empty register checks nothing"

    source = read_text(ENDPOINTS_TS)
    probe = read_text(LIVE_PROBE) if LIVE_PROBE.is_file() else ""
    violations: list[str] = []

    for pair in pairs:
        # R4 — register integrity, first, so later rules read real fields.
        missing = [field for field in REQUIRED_FIELDS if field not in pair]
        if missing:
            violations.append(f"{pair.get('id', '<unnamed>')}: register row missing {missing}")
            continue
        pair_id = pair["id"]

        for role, wrapper_key, path_key in (
            ("picker", "picker_wrapper", "list_path"),
            ("writer", "writer_wrapper", "write_path"),
        ):
            name = pair[wrapper_key]
            body = wrapper_body(source, name)
            if body is None:
                violations.append(
                    f"{pair_id}: {role} wrapper `{name}` is not in {rel(ENDPOINTS_TS)}"
                )
                continue
            found = declared_path(body)
            if found is None:
                violations.append(f"{pair_id}: cannot read the path `{name}` calls")
            elif found != pair[path_key]:
                # R1 — DEF-114 itself.
                violations.append(
                    f"{pair_id}: {role} `{name}` calls {found!r}, register says "
                    f"{pair[path_key]!r} — a picker and its endpoint must speak one "
                    f"vocabulary (DEF-114)"
                )

        # R2 — a registered picker nobody calls is a guard over dead UI.
        if not picker_call_sites(pair["picker_wrapper"]):
            violations.append(
                f"{pair_id}: no screen under src/features/ calls "
                f"`{pair['picker_wrapper']}` — built is not wired"
            )

        # R3 — the live half must still exist.
        if not probe:
            violations.append(f"{pair_id}: the live probe {rel(LIVE_PROBE)} is missing")
        elif pair_id not in probe:
            violations.append(f"{pair_id}: {rel(LIVE_PROBE)} does not exercise this pair")

    if violations:
        return "FAIL", f"{len(violations)} picker/endpoint violation(s): " + " · ".join(
            violations[:4]
        )
    return "PASS", f"{len(pairs)} picker/endpoint pair(s) agree (paths, wiring, live probe)"


if __name__ == "__main__":
    status, detail = run()
    print(f"G22 {status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)
