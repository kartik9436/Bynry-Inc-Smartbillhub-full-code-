#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-GOV-4044 (nothing asks whether a TEMPLATE-built catalogue key
#          resolves to anything) · DEF-WRK-4036 (`work.tabs.crews` printed as a
#          tab label on every Work screen, in all eleven languages) · DEF-322 ·
#          DEF-036 / DEF-041 / DEF-049 (G18's three, the literal half)
# Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 7
#          (proved RED first, through `run_gates` and not through `__main__` —
#          DEF-GOV-3733) · law 1 (a comment claiming a guarantee is not the
#          guarantee) · B14 rule 35 (a catalogue is written in its own language)
# Tests:   selftest() below, replayed on every run
# Impacts: 07-frontend/src/**/*.ts{,x} · 07-frontend/src/i18n/locales/en.json
# ───────────────────────────────────────────────────────
"""G112 — a key the code BUILDS must name a family the catalogue HAS.

THE HOLE, STATED PRECISELY
--------------------------
Three checks look at catalogue keys and none of them asks this question.

  `G15` compares the eleven catalogues to EACH OTHER. A key missing from all
        eleven is perfectly parity-clean — which is exactly how
        `DEF-WRK-4036` shipped `work.tabs.crews` to a clerk on every Work
        screen, in every language, with G15 green.

  `G18` closes that for a LITERAL key: `t("a.b.c")` where `a.b.c` is in no
        catalogue is one of its findings. **But a COMPUTED key is only ever
        read as a PREFIX, and G18 uses prefixes in ONE DIRECTION ONLY** — to
        stop a catalogue key being called dead by direction A. Read its
        `compare()`: `prefixes` is consumed by `any(key.startswith(prefix))`
        and then discarded. Nothing asks the mirror question.

  `G27` reads translation keys for a different property again.

So `` t(`work.order.tabs.${id}`) `` — where NO key in `en.json` begins
`work.order.tabs.` — renders the string `work.order.tabs.overview` into a tab
on the Work order detail screen, six times, and every check in this repo is
green over it. That is not hypothetical: it is one of this gate's first five
findings and it had been live since the screen shipped.

**WHY IT IS ITS OWN GATE AND NOT A THIRD DIRECTION INSIDE G18.** `DEF-WRK-4036`
records that G18 *did* report its key and the finding was invisible anyway —
*"G18 has been red for a long backlog and a new entry does not stand out in a
count."* G18 reports 113 unparked missing keys today. A finding added to a red
gate is a finding nobody can see, so adding this one there would reproduce the
escape it exists to close. This gate ships GREEN, so its first new finding is
the only thing on its line.

WHAT COUNTS, AND WHAT DELIBERATELY DOES NOT
-------------------------------------------
A finding is a **static prefix, taken from a translate call**, that no key in
`en.json` begins with.

  COUNTED   `` t(`work.order.tabs.${id}`) `` · `` translate(`a.b.${x}`) `` ·
            `` labelKey={`a.b.${x}`} `` — the shapes this codebase actually
            renders copy from.

  NOT COUNTED — **any template literal that is not a translate argument.**
            This is the whole reason the gate does not reuse G18's
            `KEY_PREFIX`, which matches a backtick anywhere on a line. Live
            today: `` `S8.${card.code}` `` is a SCREEN ID and
            `` query[`f.${name}`] `` is a QUERY PARAMETER. Both look exactly
            like dotted keys and neither is one. Scanning every template
            literal turned 5 real findings into 54, and a gate with a 90%
            false-positive rate is `DEF-041`'s warning coming true —
            *"a widened gate that fires on 40 legitimate items teaches people
            to add ALLOW entries, which is how a gate stops being a gate."*

  NOT A FAILURE, BUT COUNTED AND PRINTED — a call carrying `defaultValue`.
            i18next renders the default, so the author has stated IN CODE that
            a miss is the expected path and the user reads English rather than
            a dotted key. It is not nothing (the default is untranslatable, so
            ten languages get English), which is why the number is on the line
            of every run rather than silently dropped. 42 of them today.

  NOT RESOLVED — the VARIABLE. `${row.state}` is not chased into an enum and
            leaf-level checking is not attempted. G18 measured that and
            refused it: requiring each leaf to appear as a literal found 8 dead
            keys of which 3 were false positives. **A prefix that matches
            nothing needs no such inference** — if no key begins
            `work.order.tabs.`, then no value of `id` can resolve, whatever
            `id` turns out to be. That is the whole reason this check can be
            exact where leaf checking cannot.

THE PARK FILE IS NOT AN ALLOWLIST (`g112_computed_key_gaps.txt`)
----------------------------------------------------------------
Same three properties `i18n_known_gaps.txt` and `g33_refusal_copy_baseline.txt`
are held to, and for the same reason — the alternative is a permanently-red
gate, and `10-scripts/03-golden-verify.py` says what happens to one of those:
*"someone deletes the check."*

  NARROW    keyed on the EXACT prefix. A prefix not on the list fails. The list
            cannot cover "the next one like it".
  LOUD      the count is printed in this gate's one-line detail on EVERY run.
  EXPIRING  an entry that no longer reproduces is STALE and FAILS, so a line
            must be deleted in the same diff as the copy that fixes it. The
            file can only shrink.

Every entry cites a defect row, and the gate checks that row EXISTS and is not
already fixed/closed. Adding a line is a process event.

⚠ **WHAT THIS GATE CANNOT SEE, SAID PLAINLY SO NOBODY READS MORE INTO IT
(law 1).** It reads TEXT, not a rendered page. A prefix that resolves proves
the FAMILY exists; it does not prove the particular leaf does — `t(`a.b.${x}`)`
passes here while `a.b.zebra` is missing, and G18's own measurement is why that
is left alone. **The concatenation form (`t("a." + kind)`) IS read, since 2026-09-07** — this
paragraph said it was not until a lane arriving to write a second gate for
exactly that shape found this one instead. There are no instances in `src/`
today, so it adds no finding; fixture 8 plants one. The LEAF hole above is not
closed by this file and must not be claimed closed.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import csv
import json
import re
from pathlib import Path

import common

LOCALES = common.REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales"
BASE = "en.json"
REGISTER = Path(__file__).resolve().parent / "g112_computed_key_gaps.txt"
DEFECT_LOG = common.REPO_ROOT / "12-governance" / "10-defect-log.csv"
CLOSED_STATUSES = {"fixed", "closed", "wontfix", "won't fix"}
MAX_NAMED = 4

#: A template literal that is the FIRST argument of a translate call. The
#: function names are the three this codebase uses; `tt` is the portal's.
#: ⚠ The alternation is anchored with `\b` on BOTH sides so `format(` and
#: `emit(` do not match through their trailing `t`.
CALL_PREFIX = re.compile(r"\b(?:t|tt|translate)\(\s*`([A-Za-z][A-Za-z0-9_.]*\.)\$\{")
#: `` t("a.b." + kind) `` — the CONCATENATION form. ⚠ **THIS GATE'S OWN
#: DOCSTRING NAMED THIS AS A HOLE IT DID NOT CLOSE, and it was closed on
#: 2026-09-07 by the lane that came to write a second gate for it** and found
#: this one already here (CLAUDE.md law 11's last clause: read `10-scripts/`
#: before writing a helper — the tool that owns the job usually exists and is
#: usually stricter). There are ZERO instances in `src/` today, so this line
#: adds no finding and cannot be proved red against the corpus; fixture 8
#: below plants one, which is the only honest way to show a guard for a shape
#: that has not happened yet can fail at all.
CONCAT_PREFIX = re.compile(r"""\b(?:t|tt|translate)\(\s*["']([A-Za-z][A-Za-z0-9_.]*\.)["']\s*\+""")
#: `` labelKey={`a.b.${x}`} `` — a computed key passed as data, which is how
#: `DEF-041`'s nine keys and `DEF-WRK-4036`'s tab label were used. The capital
#: K is deliberate and is G18's rule: a bare `key:` is React's list key.
PROP_PREFIX = re.compile(r"\b[A-Za-z_]*[a-z]Key\s*[:=]\s*\{?\s*`([A-Za-z][A-Za-z0-9_.]*\.)\$\{")

#: How far past the opening line a `defaultValue` still belongs to the same
#: call. Measured against the corpus: every live multi-line translate call in
#: `src/` closes within three lines of its key.
DEFAULT_WINDOW = 4


def english_keys() -> set[str]:
    """Every flattened key in `en.json`, or an empty set if it is unreadable."""
    path = LOCALES / BASE
    if not path.is_file():
        return set()
    def walk(node, prefix=""):
        for name, value in node.items():
            full = f"{prefix}.{name}" if prefix else name
            if isinstance(value, dict):
                yield from walk(value, full)
            else:
                yield full
    return set(walk(json.loads(common.read_text(path))))


def sources() -> list[tuple[str, str]]:
    """Frontend `.ts`/`.tsx`, comments stripped by G18's own `_code_only`.

    Imported rather than re-implemented, so the two i18n gates read the same
    text with the same eyes — `DEF-769` (a key named only in a JSX comment) and
    `DEF-741` (a `//` line spelling a path with a star in it) are both fixed
    there, and a second copy of that logic here would be a second place for
    them to come back.

    ⚠ **`.test.ts{,x}` IS EXCLUDED.** A test's template prefix is a FIXTURE. It
    describes a hypothetical render, and `SignupWizard.test.tsx` carries one
    (`tenancy.signup.success.`) that names no real family on purpose.
    """
    import g18_i18n_call_sites as g18

    return [(path, text) for path, text in g18.frontend_sources() if ".test." not in path]


def findings(keys: set[str], files: list[tuple[str, str]]):
    """(raw, defaulted) — each {prefix: "path:line"}.

    `raw` renders the dotted key to a person. `defaulted` renders English.
    """
    raw: dict[str, str] = {}
    defaulted: dict[str, str] = {}
    for path, text in files:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            for pattern in (CALL_PREFIX, PROP_PREFIX, CONCAT_PREFIX):
                for prefix in pattern.findall(line):
                    if any(key.startswith(prefix) for key in keys):
                        continue
                    window = "\n".join(lines[index : index + DEFAULT_WINDOW])
                    where = f"{path}:{index + 1}"
                    bucket = defaulted if "defaultValue" in window else raw
                    bucket.setdefault(prefix, where)
    # A prefix that renders raw ANYWHERE is a finding, even if some other call
    # site of the same family remembered a defaultValue.
    for prefix in raw:
        defaulted.pop(prefix, None)
    return raw, defaulted


# ── the park file ───────────────────────────────────────────────────────────
def parked() -> dict[str, str]:
    """{prefix: defect id} from the register, ignoring blanks and comments."""
    if not REGISTER.is_file():
        return {}
    entries: dict[str, str] = {}
    for line in common.read_text(REGISTER).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        prefix, _, defect = line.partition("::")
        entries[prefix.strip()] = defect.strip()
    return entries


def defect_status() -> dict[str, str]:
    if not DEFECT_LOG.is_file():
        return {}
    with DEFECT_LOG.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: (row.get("status") or "").strip().lower() for row in csv.DictReader(handle)}


def check(keys: set[str], files, register: dict[str, str], statuses: dict[str, str]):
    """(problems, tally) — pure over its inputs so selftest can mutate them."""
    raw, defaulted = findings(keys, files)
    problems: list[str] = []

    unparked = sorted(prefix for prefix in raw if prefix not in register)
    for prefix in unparked:
        problems.append(
            f"`{prefix}` at {raw[prefix]} — no key in en.json begins with it, so every value "
            f"renders its own dotted key to a user"
        )

    # EXPIRING: a licence for something that no longer happens is a dead
    # licence, and a dead licence sitting in the file is how the next real one
    # gets waved through.
    for prefix in sorted(register):
        if prefix not in raw:
            problems.append(
                f"`{prefix}` is parked in {REGISTER.name} and no longer reproduces — "
                f"delete the line in the same diff as the fix"
            )

    # A park entry must point at a defect row that exists and is still open.
    for prefix, defect in sorted(register.items()):
        if not defect:
            problems.append(f"`{prefix}` is parked with no defect id")
        elif defect not in statuses:
            problems.append(f"`{prefix}` cites {defect}, which is in no row of the defect register")
        elif statuses[defect] in CLOSED_STATUSES:
            problems.append(
                f"`{prefix}` cites {defect}, which is already {statuses[defect]} — "
                f"a closed row cannot license an open gap"
            )

    tally = {"raw": len(raw), "parked": len(register), "defaulted": len(defaulted)}
    return problems, tally


# ═══════════════════════════════════════════════════════════════════════════
# SELF-TEST (law 7). Replayed on every run against an in-memory corpus, so a
# green run proves the COMPARISON works and not merely that the park file is
# full. A fixture that fails to bite fails the gate. Nothing is written.
# ═══════════════════════════════════════════════════════════════════════════
def selftest() -> tuple[bool, str]:
    keys = {"work.tabs.orders", "work.tabs.parts", "a.b.c"}

    def one(name, files, register, statuses, want):
        problems, _tally = check(keys, files, register, statuses)
        hit = any(want in problem for problem in problems)
        return hit, f"{name}: expected a finding naming {want!r}, got {problems!r}"

    # 1 — DEF-WRK-4036's own shape: a tab strip whose family is in no catalogue.
    ok, why = one(
        "1 missing family",
        [("x.tsx", "const label = t(`work.tabs.crews.${id}`);")],
        {}, {}, "work.tabs.crews.",
    )
    if not ok:
        return False, why

    # 2 — a family that DOES exist must not be reported.
    problems, _ = check(keys, [("x.tsx", "t(`work.tabs.${id}`)")], {}, {})
    if problems:
        return False, f"2 live family: a resolvable prefix was reported — {problems!r}"

    # 3 — a `defaultValue` renders English, so it is counted and not failed.
    problems, tally = check(
        keys, [("x.tsx", 't(`z.z.${id}`, {\n  defaultValue: "Hi",\n})')], {}, {}
    )
    if problems or tally["defaulted"] != 1:
        return False, f"3 defaultValue: expected 0 problems and 1 counted — {problems!r} {tally!r}"

    # 4 — NOT a translate call. A screen id and a query parameter are the two
    #     live shapes that made the naive version 90% false positives.
    problems, _ = check(
        keys,
        [("x.tsx", 'const screenId = `S8.${card.code}`;\nquery[`f.${name}`] = value;')],
        {}, {},
    )
    if problems:
        return False, f"4 non-translate template: reported anyway — {problems!r}"

    # 5 — the register is NARROW: a parked prefix off by one character still fails.
    problems, _ = check(
        keys, [("x.tsx", "t(`q.q.${id}`)")], {"q.q": "DEF-1"}, {"DEF-1": "open"}
    )
    if not any("`q.q.`" in problem for problem in problems):
        return False, f"5 narrow: a near-miss park entry silenced the finding — {problems!r}"

    # 6 — the register EXPIRES: an entry that no longer reproduces fails.
    problems, _ = check(keys, [("x.tsx", "")], {"gone.": "DEF-1"}, {"DEF-1": "open"})
    if not any("no longer reproduces" in problem for problem in problems):
        return False, f"6 expiring: a stale park entry was tolerated — {problems!r}"

    # 7 — a park entry citing a CLOSED row is not a licence.
    problems, _ = check(
        keys, [("x.tsx", "t(`q.q.${id}`)")], {"q.q.": "DEF-1"}, {"DEF-1": "fixed"}
    )
    if not any("already fixed" in problem for problem in problems):
        return False, f"7 closed citation: a fixed row licensed an open gap — {problems!r}"

    # 8 — the CONCATENATION form, which this gate could not see until
    #     2026-09-07. Nothing in `src/` is written this way today, so this
    #     fixture is the only thing that can show the new pattern fires at all
    #     (law 7: a guard proved on an empty corpus is proved on nothing).
    ok, why = one(
        "8 concatenation form",
        [("x.tsx", 'const label = t("work.tabs.crews." + id);')],
        {}, {}, "work.tabs.crews.",
    )
    if not ok:
        return False, why

    # 8b — and it must not swallow an ORDINARY literal key: `t("a.b.c")` names
    #      one key and is not a family. Reading it as one would fail every
    #      screen in the product.
    problems, _ = check(keys, [("x.tsx", 'const s = t("a.b.c");')], {}, {})
    if problems:
        return False, f"8b literal key read as a computed family — {problems!r}"

    return True, "8 fixtures bit (template, prop and concatenation forms)"


def run() -> tuple[str, str]:
    """⚠ **`tuple[str, str]`, NOT an exit code.** `run_gates` does
    `status, detail = module.run()`; a gate returning an `int` unpacks into
    nothing and is reported as *gate returned invalid status*, and a gate with
    no callable `run` is *gate crashed: AttributeError*. Both were shipped and
    announced green on 2026-09-04 (`DEF-GOV-3733`) because they had only ever
    been proved through `python3 <gate>.py`, which is not the path the runner
    uses. This one was proved RED and green through `run_gates`' own import
    path — `_assert_registry_sane()` then `module.run()`."""
    ok, detail = selftest()
    if not ok:
        return "FAIL", f"self-test: {detail}"

    keys = english_keys()
    if not keys:
        return "FAIL", f"{LOCALES / BASE} is missing or empty; it is the catalogue this gate reads"

    problems, tally = check(keys, sources(), parked(), defect_status())
    line = (
        f"{tally['raw']} computed key famil{'y' if tally['raw'] == 1 else 'ies'} "
        f"name nothing in en.json ({tally['parked']} parked in {REGISTER.name}) · "
        f"{tally['defaulted']} more carry a defaultValue, so they render English, not the key"
    )
    if problems:
        return "FAIL", f"{common.summarize(problems, MAX_NAMED)} — {line}"
    return "PASS", line


def main() -> int:
    status, detail = run()
    print(f"G112 {status} {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
