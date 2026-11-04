#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-WRK-4518 — `Work-008` made fourteen calls with the order NUMBER
#          against fourteen `<uuid:order_id>` routes, got fourteen 404s and drew
#          a dash for each, so the screen looked finished and said nothing ·
#          DEF-WRK-4637 — the sibling template screen, found BY THIS GATE, says
#          "Loading" for ever over the same failure
# Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
#          running app) · law 7 (proved RED first, in the harness that runs it,
#          and a declared blind spot carries a NUMBER) · A18 §3/§4 (the loading
#          and failed state frames) · B14 rule 36 (the shared kit is how you
#          comply)
# Tests:   self_test() below, which runs on every invocation
# ───────────────────────────────────────────────────────
"""G122 — a screen may not draw VALUES over a read it never got.

WHAT HAPPENED
-------------
`OrderDetailPage` asked fourteen endpoints for an order using the order NUMBER.
Every route on that family is `<uuid:order_id>`, so every request 404'd. The
screen rendered its header, its six tabs and its fact list anyway, because a
failed read arrives as `data === undefined` and every `<Fact>` turns `undefined`
into a dash. **The page looked finished.**

That is the whole difficulty, and it is worth stating plainly: **the dash is not
the bug.** A dash is the right answer for a value that is genuinely absent, and
two dashes on that very screen are exactly that. The bug is a dash standing in
for *we do not know* — a different fact, needing different words. A screen that
draws dashes while it loads and dashes when it failed cannot tell a person which
happened, and it could not tell US either: `tsc` was green (an order number IS a
string), 75 component cases were green (each pre-seeds the query cache or
answers 200 to any path), and 165 gates were green. **The only thing in this
repository that could see it was somebody opening the page** — law 6's whole
claim, and the reason this gate exists.

WHAT IT READS, AND WHAT IT ASKS
--------------------------------
Every `.tsx` under `07-frontend/src/features` that BOTH creates a
`const <name> = useQuery(…)` AND draws a `<FactList` — i.e. a screen whose job
is to put server values in front of a person. Of those it requires two branches,
each keyed on a QUERY (never on a mutation — `mutation.isPending` is a spinner
on a button and says nothing about a read):

    1. an early guard  `if (<query>.isPending)`  or `.isLoading`
    2. an absent-data branch — `<query>.data === undefined`, `.isError`,
       or `.error` — the branch that gets to SAY what went wrong

The house shape for both is `BillDetailPage`: `LoadingSkeleton` while pending,
then `FailedWithRetry` naming the failure. This gate does not require those two
components by name — a screen may answer in its own way — only that the two
questions are ASKED.

⚠ **WHY THE SUBJECT IS `<FactList` AND NOT EVERY SCREEN.** A list that comes
back empty is honestly empty and its own empty state says so; a wizard step
guards its own submit. The screens that fail SILENTLY are the ones whose whole
purpose is to display fields, because a field has a legitimate blank. Widening
this to every `useQuery` in the product would produce a backlog wearing a gate's
clothes — the "BORN ASPIRATIONAL → NEVER GREEN" shape G33's ruling forbids.

⚠ **THE BLIND SPOT, WITH ITS NUMBER, BECAUSE A DECLARED BLIND SPOT WITH NO
NUMBER IS INDISTINGUISHABLE FROM AN EMPTY ONE (law 7, G32's 21 live refusals).**
This reads TEXT, so it cannot see a guard that lives in a component this file
imports, and it cannot see whether the branch it found renders anything useful.
The PASS line prints how many fact-drawing files were examined and how many were
skipped for having no query at all, so a reader can tell a real zero from an
unmeasured one.

THE BASELINE
------------
`g122_reads_that_failed_are_visible_baseline.txt` names the files that already
fail, one per line with the reason. It may only SHRINK — a NEW file, or one that
starts drawing a FactList, must guard from its first commit.

PROVED RED
----------
`self_test()` carries the real `OrderDetailPage` shape before the fix and after
it, and runs on every invocation, so the gate cannot rot into one that always
passes. It was also proved red against the tree: with the fix reverted the gate
named `07-frontend/src/features/work/OrderDetailPage.tsx`, through
`run_gates.py` and not only through `__main__` (DEF-GOV-3733 — a red proof
through the wrong entry point is no proof of the thing that matters).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BASELINE = Path(__file__).resolve().parent / "g122_reads_that_failed_are_visible_baseline.txt"

#: `const detailQuery = useQuery({` — the reads. `useMutation` is deliberately
#: not here: a mutation's `isPending` is a button spinner, and reading it as a
#: read-guard is how a check starts passing on screens it should fail.
QUERY_CONST = re.compile(r"\bconst\s+(\w+)\s*=\s*useQuery\b")

#: The screens this gate is about: their job is to put server values in fields.
DRAWS_FACTS = "<FactList"


def _pending_guard(text: str, query: str) -> bool:
    """Is this read's PENDING state consulted anywhere?

    ⚠ **DELIBERATELY NOT `if (q.isPending)`.** The first draft of this gate
    demanded an early return and reported `NewAccountWizard` — which answers the
    question perfectly well by passing `loading={unitsQuery.isPending}` to the
    control that draws it, and elsewhere by a ternary. A gate that dictates the
    SHAPE of a correct answer rather than asking whether the question is asked
    manufactures work and then gets suppressed. What DEF-WRK-4518 did was never
    consult a read's pending state at ALL — the three `isPending` references on
    that file were mutations, i.e. button spinners — and that is what this asks.
    """
    return re.search(rf"\b{re.escape(query)}\.(isPending|isLoading)\b", text) is not None


def _absent_branch(text: str, query: str) -> bool:
    q = re.escape(query)
    return (
        re.search(rf"{q}\.data\s*===\s*undefined|{q}\.isError\b|{q}\.error\b", text) is not None
    )


def unguarded(text: str) -> tuple[bool, list[str]]:
    """`(is a fact-drawing screen, the questions it fails to ask)`."""
    if DRAWS_FACTS not in text:
        return False, []
    queries = QUERY_CONST.findall(text)
    if not queries:
        return False, []
    missing: list[str] = []
    if not any(_pending_guard(text, q) for q in queries):
        missing.append(
            "no read's pending state is consulted — a loading page is drawn as a finished one"
        )
    if not any(_absent_branch(text, q) for q in queries):
        missing.append("no absent-data branch — a failed read is drawn as a page of dashes")
    return True, missing


# ── the self-test's two fixtures: OrderDetailPage before and after ──────────
RED = """
const order = useQuery({ queryKey: k, queryFn: f });
const row = order.data;
return (<FactList><Fact label="Type">{row?.type ?? <Dash />}</Fact></FactList>);
"""

GREEN = """
const order = useQuery({ queryKey: k, queryFn: f });
const row = order.data;
if (order.isPending) { return <LoadingSkeleton variant="card" />; }
if (row === undefined) {
  const notFound = isApiError(order.error) && order.error.status === 404;
  return <FailedWithRetry reason={notFound ? a : b} />;
}
return (<FactList><Fact label="Type">{row.type}</Fact></FactList>);
"""

#: A mutation's spinner is NOT a read guard. This fixture is the false pass this
#: gate would have if `useMutation` were folded in with `useQuery` (law 7's
#: second habit: ask what would make the check pass WRONGLY).
MUTATION_ONLY = """
const order = useQuery({ queryKey: k, queryFn: f });
const save = useMutation({ mutationFn: m });
if (save.isPending) { return <Spinner />; }
return (<FactList><Fact label="Type">{order.data?.type}</Fact></FactList>);
"""

#: A list screen is not this gate's subject and must not be dragged in.
NO_FACTS = """
const rows = useQuery({ queryKey: k, queryFn: f });
return (<PlainTable rows={rows.data ?? []} />);
"""


#: The answer `NewAccountWizard` gives, and it is a correct one: the pending
#: state reaches a control as a PROP rather than as an early return. A gate that
#: refused this would be dictating a shape rather than asking a question.
PROP_GUARD = """
const unitsQuery = useQuery({ queryKey: k, queryFn: f });
if (unitsQuery.isError && isPermissionDenied(unitsQuery.error)) { return <Denied />; }
return (<FactList><Picker loading={unitsQuery.isPending} rows={unitsQuery.data} /></FactList>);
"""


def self_test() -> list[tuple[str, bool, str]]:
    return [
        ("the real DEF-WRK-4518 shape bites", unguarded(RED) == (True, [
            "no read's pending state is consulted — a loading page is drawn as a finished one",
            "no absent-data branch — a failed read is drawn as a page of dashes",
        ]), "OrderDetailPage before"),
        ("the fix is green", unguarded(GREEN) == (True, []), "OrderDetailPage after"),
        ("a MUTATION spinner is not a read guard", unguarded(MUTATION_ONLY)[1] != [], "useMutation"),
        ("a screen with no FactList is not this gate's subject", unguarded(NO_FACTS)[0] is False,
         "a list"),
        ("a pending state passed as a PROP is a correct answer", unguarded(PROP_GUARD) == (True, []),
         "NewAccountWizard"),
    ]


def baselined() -> dict[str, str]:
    if not BASELINE.is_file():
        return {}
    out: dict[str, str] = {}
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path, _, why = line.partition(" — ")
        out[path.strip()] = why.strip()
    return out


def run() -> tuple[str, str]:
    failures = [name for name, ok, _ in self_test() if not ok]
    if failures:
        return "FAIL", f"self-test broken: {', '.join(failures)}"

    features = common.FRONTEND_SRC / "features"
    if not features.is_dir():
        return "SKIP", "no 07-frontend/src/features directory to read"

    known = baselined()
    problems: list[str] = []
    examined = 0
    skipped_no_query = 0
    still_baselined = 0

    for path in sorted(features.rglob("*.tsx")):
        if ".test." in path.name:
            continue
        text = common.read_text(path)
        is_subject, missing = unguarded(text)
        if DRAWS_FACTS in text and not is_subject:
            skipped_no_query += 1
        if not is_subject:
            continue
        examined += 1
        rel = common.rel(path)
        if not missing:
            if rel in known:
                problems.append(
                    f"{rel} now guards its reads — DELETE its line from "
                    f"{BASELINE.name}, the baseline may only shrink"
                )
            continue
        if rel in known:
            still_baselined += 1
            continue
        problems.append(f"{rel}: " + "; ".join(missing))

    if problems:
        return "FAIL", (
            common.summarize(problems)
            + ". A screen that draws dashes while it loads and dashes when it failed cannot tell "
            "a person which happened — DEF-WRK-4518 survived a build, 75 tests and 165 gates on "
            "exactly that. BillDetailPage is the house shape: LoadingSkeleton while pending, "
            "FailedWithRetry naming the failure, the page only when the data is there."
        )
    return "PASS", (
        f"{examined} fact-drawing screen(s) guard both the pending and the absent state; "
        f"{still_baselined} still named in {BASELINE.name} (that file may only shrink); "
        f"{skipped_no_query} file(s) draw a FactList from no query of their own and are this "
        "gate's declared blind spot; self-test: 5/5 bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
