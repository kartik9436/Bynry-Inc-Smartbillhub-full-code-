#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-046 (2026-08-27) — *"the identifier is ours to issue"*. PO
#           verbatim: *"here we should not allow usse to fill in Asset ID - we
#           have number system set in the settings, we shoudl call that function
#           and get unique number and assign it"*, widened by the fifth message
#           to all four uploads: *"can you use similar logic and update the
#           upload logic for all 4 entities we discussed"*.
# Rules:    BR-AST-049 (where the utility's own number goes now) · BR-AST-026
#           (the series allocates ALWAYS on this target, amended not superseded)
#           · BR-TEN-035 (the format grammar) · BR-MET-088 (the model decides
#           which columns are offered)
# Defects:  DEF-1840 (this gate's first finding — five served strings send an
#           operator to a tab that does not exist) · DEF-962 (a template that
#           ships an INVENTED number in the one column the PO objected to being
#           asked to invent) · DEF-577 (a series standing behind the rows that
#           exist) · DEF-615 (a series whose default and whose test disagree) ·
#           DEF-1077 (the template gives an operator no way to know what to put)
# ───────────────────────────────────────────────────────
"""G49 — an import template's identifier column must agree with the series that issues it.

WHY THIS GATE EXISTS
--------------------
Step 3 of `12-governance/19-execution-sequence.md`, PO-approved, names three
escapes that each crossed a boundary nothing watches. This is the third:
**meters were numbered from the file** rather than from Settings › Numbering,
against the CR-046 identifier law.

The law has three moving parts and they live in three different places:

    THE SERIES        `core/numbering.py::SERIES_CATALOG`      what a number looks like
    THE WIRING        `import_runs.py::TARGET_SERIES`          which series a target draws from
    THE TEMPLATE      the shipped `*_COLUMNS` declarations     what the operator is asked for

**Nothing has ever compared the three.** A target can name a series the
catalogue does not have; a series can be wired to a column the template does not
offer; and a column can be declared with a worked sample number that teaches an
operator to invent exactly the identifier the ruling took away from them. Each
of those is silent: the file loads, the dry run is clean, and the number is
wrong or absent.

WHAT IT CHECKS — FOUR CLAUSES, ALL HARD ZERO
----------------------------------------------
The three facts are READ out of the modules that own them, through a subprocess
that imports the real Django module and prints JSON. **The real objects, not a
parse of the text that builds them** — `_asset_column` writes `sample` only when
one was declared (that conditional IS `DEF-962`'s fix), and no regex over the
source can tell a declared `""` from an absent key. Reading the built dict can.

**(a) A TARGET MAY NOT NAME A SERIES THE CATALOGUE DOES NOT HAVE.** `TARGET_
SERIES` points six targets at four series. A series that is not a `SERIES_
CATALOG` key allocates nothing — `next_number` raises `NumberingError`, the
import warns `numbering_series_missing`, and the row loads with no number at
all. `DEF-615` is this family: the import-run series seeds `IMP-` while CR-023's
own test expects `RUN-`, and one of the two had been wrong since it landed.

**(b) THE SERIES' COLUMN MUST BE A COLUMN THE TEMPLATE ACTUALLY OFFERS.** Under
CR-046 the identifier column keeps a second job the ruling deliberately did not
take away — it is *"the MATCH KEY that tells Insert & update which record a row
is about"* (`_issued_number_column`'s own docstring). A wiring that names a
column the shipped file does not carry leaves *Insert & update* with nothing to
match on, and every row reads as new.

**(c) A COLUMN WHOSE NUMBER IS ISSUED MAY NOT SHIP A WORKED NUMBER.** This is
the escape itself, in the artefact the operator actually opens. An issued
column declares `sample=""` and a `blank_means`; a sample of `M-9001` or
`P-9001` is the template teaching the operator to fill in the one column the
ruling exists to stop them filling in. `DEF-962` is exactly this, from the other
side, and its fix — *"an explicitly declared empty sample"* — is what this
clause pins.

⚠ **ACCOUNTS ARE EXCLUDED BY A PO RULING AND THE EXCLUSION IS CHECKED, NOT
SKIPPED.** `_issued_numbers_preview` says so in its own words: *"ACCOUNTS ARE
EXCLUDED BY NAME (PO ruling 2026-08-27). They take their number from the file."*
So the accounts target is required to be the OPPOSITE — a declared sample and
`required=True` — because a target that takes its number from the file and
ships a blank sample is `DEF-962` in the other direction: an operator who leaves
it blank gets a refusal the template told them nothing about. Law 13's shape:
the ruling is in the check, so nobody re-asks it.

**(d) A SERVED STRING NAMING THE NUMBERING SCREEN MUST USE THE SCREEN'S NAME.**
The identifier column's whole job under CR-046 is to send the operator to that
screen. The name is READ from `settings.tab.numbering` in `en.json` — the label
a user actually sees — and never typed here, so renaming the tab moves the rule
with it rather than stranding a literal in a gate.

This clause found `DEF-1840` on its first run: **five** served strings say
*"Settings › Numbers"* against a tab called **Numbering**, while five others in
the same repo say it correctly. Premises and units name the screen right,
because they go through `_issued_number_column`; the three ASSETS templates —
the ones the Product Owner walked through — name it wrong.

⚠ **AND IT IS NOT A ONE-WORD FIX, WHICH IS THE MORE USEFUL HALF OF THE
FINDING.** `tests/test_br_ast_049_external_ref.py:630` asserts `"Settings ›
Numbers ›" in columns["asset_no"]["help"]`, `tests/test_cr046_identifiers.py:287`
asserts it in a `fix_hint`, and `12-governance/02-decision-log.md:14904` records
the click path as *"Settings › Numbers › Meter"* under the standing PO
instruction that a rule reaches a person by the path they click. **Three
artefacts agree with each other and disagree with the product**, and the suite
is GREEN ON THE BUG — the same shape as CR-039 A2's *"exactly the six signup
services render as chips"*, where a test written from the same misunderstanding
as the code could not catch it. Only a comparison against the OTHER artefact
can, which is what this clause is.

So this lane did NOT change the strings: doing so turns two pinning tests red
and contradicts a recorded decision, and which of the two names is the product's
is the CR-046 owner's to rule. **The five are BANKED BY NAME** in
`WRONG_SCREEN_NAME_BANKED` — a named set, not a count, so a SIXTH fails at its
own line while these are pending, and the gate goes RED as STALE the moment one
is fixed and left in the list (DEF-490, G44 clause (c)'s shape).

**The SEPARATOR is deliberately not checked.** `›` and `→` both appear and
nothing turns on which; a gate that argued about punctuation would be switched
off, and G43/G45 both stop at the same line.

WHY A SUBPROCESS, AND WHY THAT IS NOT A DATABASE
--------------------------------------------------
`apps.metering.import_runs` imports Django models, so it needs `django.setup()`
— which the gate runner must not do in its own process, because it would leak
app-registry state into every gate after it. A subprocess isolates that
completely.

**No database is touched.** Only module-level declarations are read:
`EXPLICIT_COLUMNS_BY_TARGET` and the `*_FIELD_OVERRIDES` dicts, which are the
files' own literals. `target_columns()` is deliberately NOT called — it resolves
custom fields against a tenant and raises `AuthError AUTH-003` with no request,
and a clause that needs a live tenant is a clause that would report NOT
EVALUATED here for ever (G21's words, and G24's actual output).

If Django is not importable the gate returns **SKIP with the reason**, never a
PASS: a check that could not run has not passed.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — the verbatim failure for
clause (d) is in the `RED PROOF` block below, taken on this tree before the
five strings were fixed. Clauses (a)–(c) are proved by `selftest()`, which
plants each violation and requires it to bite, on every run.

Python 3.12 stdlib only in this file. Safe to run from any cwd. Nothing writes.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "06-backend"
EN_JSON = ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
NUMBERING_TAB_KEY = "settings.tab.numbering"

#: Targets that take the identifier FROM THE FILE, by a PO ruling quoted in the
#: module: "ACCOUNTS ARE EXCLUDED BY NAME (PO ruling 2026-08-27). They take
#: their number from the file". They are checked for the OPPOSITE contract.
FILE_ISSUED_BY_RULE: dict[str, str] = {
    "accounts": (
        "PO ruling 2026-08-27, quoted in `_issued_numbers_preview`: accounts take their number "
        "from the file, so a rehearsal promising 'we will issue AC-2026-00001' would promise "
        "something that never happens. The column is `required=True` and carries a worked sample"
    ),
}

#: `DEF-1840` — the five served strings that name the numbering screen by a word
#: it is not. BANKED, by NAME rather than by a count, and NOT fixed here on
#: purpose: two tests pin the wrong wording and the decision log carries it, so
#: which name is the product's is the CR-046 owner's to rule. It may SHRINK and
#: may never GROW; a fall that is not banked is a FAIL.
#:
#: ⚠ **THE KEY IS `file:LINE`, SO ANY EDIT ABOVE ONE OF THESE SITES MOVES IT AND
#: THE GATE READS THE MOVE AS FOUR STRINGS HEALED AND FOUR NEW ONES APPEARING
#: (2026-08-28, the connection-size doors lane).** That lane added a column to
#: `_assets_meter_columns` and a rule to `ASSETS_METERS_RULES` — nothing to do
#: with numbering, and not one of these five sentences changed by a byte — and
#: `G49` went from PASS to FAIL because four of them slid down the file:
#: `import_rules.py` 1737→1765 and 2370→2398 (+28), `import_runs.py` 4510→4626
#: and 4564→4680 (+116). The strings were verified IDENTICAL at both line
#: numbers with `git show db84bc6:<path> | sed -n '<old>p'` before re-banking,
#: so this edit re-points the ratchet and does NOT loosen it: still five sites,
#: still by name, still may shrink and never grow.
#:
#: **A LINE-KEYED BANK IS A CHECK THAT FAILS ON EDITS IT IS NOT ABOUT**, and
#: re-pointing it by hand is a step the next lane touching these two files will
#: also have to take without being told. Keying on the SENTENCE — or on
#: `<path>::<message_key>` — would survive a shift and would still bite a sixth
#: offender. That is the CR-046 owner's call and is REPORTED here rather than
#: taken, because narrowing what a ratchet counts is a process event.
WRONG_SCREEN_NAME_BANKED: frozenset[str] = frozenset()
#: ⚠ **EMPTIED 2026-08-30 — `DEF-1840`'s copy is FIXED, not banked.** This set
#: held five `path:line` entries for sentences that sent an operator to
#: *"Settings › Numbers"* when the tab is called **Numbering**. All six
#: occurrences across `import_rules.py` and `import_runs.py` now name the tab
#: correctly, so the bank has nothing to hold and an empty set is the honest
#: state — a ratchet that never tightens is a number nobody reads (`DEF-490`),
#: and this gate said exactly that about itself before the fix.
#:
#: ⚠ **AND THE GATE IS WHY IT WAS FOUND, TWICE OVER.** It reported BOTH halves
#: in one run: five NEW offenders (the sentences `CR-047` added while widening
#: the import refusals, which copied the wrong tab name from the ones already
#: banked) and five STALE entries (lines that had since moved or been fixed).
#: **A bank keyed on `path:line` goes stale on any edit upstream of it** — the
#: 2026-08-28 note this replaces recorded exactly that, two entries drifting by
#: 142 lines when `DEF-1077` inserted code above them. Keeping it empty removes
#: that whole failure mode; if a sixth ever appears, FIX THE SENTENCE rather
#: than banking a line number that will drift.

#: Read the tenant-facing tab label out of the module that imports Django, in a
#: subprocess. Prints ONE JSON object; touches no database.
PROBE = r"""
import json, os, sys
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
import django
django.setup()
from apps.metering import import_runs as ir
from core import numbering

def name_of(entry):
    return entry.get("target") or entry.get("field") or entry.get("name")

columns = {}
for target, cols in ir.EXPLICIT_COLUMNS_BY_TARGET.items():
    columns[target] = {name_of(c): c for c in cols if name_of(c)}
# premises and units DERIVE their columns from the model and override a few by
# name; the identifier is always one of the overrides.
for attr in dir(ir):
    if attr.endswith("_FIELD_OVERRIDES"):
        stem = attr[: -len("_FIELD_OVERRIDES")].lower()
        target = {"premises": "premises", "units": "units"}.get(stem, stem)
        merged = dict(columns.get(target, {}))
        merged.update(getattr(ir, attr))
        columns[target] = merged

print(json.dumps({
    "target_series": {t: list(v) for t, v in ir.TARGET_SERIES.items()},
    "catalog": sorted(numbering.SERIES_CATALOG),
    "columns": {
        t: {n: {k: c.get(k) for k in ("label", "sample", "blank_means", "required", "help")
                if k in c}
            for n, c in cols.items()}
        for t, cols in columns.items()
    },
}))
"""


def _probe() -> tuple[dict, str | None]:
    """`(facts, error)` — the real module's declarations, or why not.

    ⚠ **THE INTERPRETER IS ASKED FOR, NOT ASSUMED (`DEF-GOV-7813`).** This read
    `sys.executable` — the interpreter running `run_gates`, which on this
    machine is bare `python3` with no Django — so the gate SKIPPED on every run
    with *"No module named 'django'"* while `SBH_GATE_PYTHON` named an
    interpreter that has it and G4/G5 used that one beside it. The shared
    helper is the one list every gate consults.
    """
    python, tried = common.interpreter_with("django")
    if python is None:
        return {}, (
            "no interpreter on this machine can import Django (tried: "
            + ", ".join(tried)
            + "); set SBH_GATE_PYTHON to the project's venv python"
        )
    try:
        done = subprocess.run(
            [python, "-c", PROBE],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - defensive
        return {}, f"could not start the probe: {exc}"
    if done.returncode != 0:
        return {}, (done.stderr.strip().splitlines() or ["no stderr"])[-1]
    try:
        return json.loads(done.stdout.strip().splitlines()[-1]), None
    except (ValueError, IndexError):
        return {}, "the probe printed nothing a reader could parse"


def numbering_tab_label() -> str | None:
    """The label a user actually sees on the numbering tab, from `en.json`."""
    if not EN_JSON.exists():
        return None
    try:
        catalogue = json.loads(EN_JSON.read_text("utf-8"))
    except ValueError:  # pragma: no cover - defensive
        return None
    node: object = catalogue
    if NUMBERING_TAB_KEY in catalogue:
        return str(catalogue[NUMBERING_TAB_KEY])
    for part in NUMBERING_TAB_KEY.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return str(node) if isinstance(node, str) else None


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"\S", " ", match.group(0))


def _strip_py(text: str) -> str:
    text = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', _blank, text)
    text = re.sub(r"'''(?:[^'\\]|\\.|'(?!''))*'''", _blank, text)
    return re.sub(r"#[^\n]*", lambda m: " " * len(m.group(0)), text)


def wrong_screen_names(sources: list[tuple[str, str]], label: str) -> list[str]:
    """Served strings that name the numbering screen by a word it is not.

    The SEPARATOR is deliberately free (`›` and `→` both appear, and nothing
    turns on which). Only the NAME is checked, against the label a user sees.
    """
    pattern = re.compile(r"Settings\s*[›>→\-]+\s*([A-Za-z]+)")
    out: list[str] = []
    for rel, text in sources:
        for match in pattern.finditer(text):
            word = match.group(1)
            if word.lower() == label.lower():
                continue
            if not word.lower().startswith(label.lower()[:4]):
                continue  # a different Settings tab entirely, not this one
            line = text[: match.start()].count("\n") + 1
            out.append(f"{rel}:{line} says `Settings … {word}`, the tab is `{label}`")
    return out


def contract_problems(facts: dict) -> tuple[list[str], list[str], list[str]]:
    """Clause (a), (b) and (c) offenders."""
    series_missing: list[str] = []
    column_missing: list[str] = []
    contract: list[str] = []
    catalog = set(facts.get("catalog") or ())
    columns = facts.get("columns") or {}
    for target, pair in sorted((facts.get("target_series") or {}).items()):
        series, column = pair[0], pair[1]
        if series not in catalog:
            series_missing.append(
                f"{target} draws from series `{series}`, which SERIES_CATALOG does not define"
            )
        declared = (columns.get(target) or {})
        entry = declared.get(column)
        if entry is None:
            column_missing.append(
                f"{target}: series `{series}` issues `{column}` and the shipped template "
                f"declares no such column (it offers {len(declared)})"
            )
            continue
        sample = entry.get("sample")
        if target in FILE_ISSUED_BY_RULE:
            if not sample:
                contract.append(
                    f"{target}.{column} takes its number FROM THE FILE by ruling and ships no "
                    "worked sample — an operator who leaves it blank gets a refusal the "
                    "template never warned them about"
                )
            continue
        if sample:
            contract.append(
                f"{target}.{column} is ISSUED from series `{series}` and ships the worked "
                f"sample {sample!r} — the template is teaching the operator to invent the one "
                "number CR-046 took away from them (DEF-962)"
            )
        if not entry.get("blank_means"):
            contract.append(
                f"{target}.{column} is ISSUED from series `{series}` and declares no "
                "`blank_means`, so the downloaded template never says what leaving it blank does"
            )
    return series_missing, column_missing, contract


def selftest() -> list[str]:
    """Shown to BITE on planted facts before it is trusted on the real tree."""
    problems: list[str] = []

    good = {
        "catalog": ["asset", "account"],
        "target_series": {
            "assets_meters": ["asset", "asset_no"],
            "accounts": ["account", "account_no"],
        },
        "columns": {
            "assets_meters": {"asset_no": {"sample": "", "blank_means": "issued", "label": "x"}},
            "accounts": {"account_no": {"sample": "A-10432", "required": True, "label": "y"}},
        },
    }
    if any(contract_problems(good)):
        problems.append("bites the tree's own correct contract — false positive")

    bad_series = json.loads(json.dumps(good))
    bad_series["target_series"]["assets_meters"][0] = "nosuchseries"
    if not contract_problems(bad_series)[0]:
        problems.append("does not bite a target naming a series the catalogue lacks")

    bad_column = json.loads(json.dumps(good))
    bad_column["columns"]["assets_meters"] = {"something_else": {"sample": ""}}
    if not contract_problems(bad_column)[1]:
        problems.append("does not bite a series wired to a column the template does not offer")

    # ⚠ THE ESCAPE: an issued column shipping a worked number.
    worked = json.loads(json.dumps(good))
    worked["columns"]["assets_meters"]["asset_no"]["sample"] = "M-9001"
    if not contract_problems(worked)[2]:
        problems.append("does not bite an ISSUED column shipping a worked number (DEF-962)")

    no_blank = json.loads(json.dumps(good))
    del no_blank["columns"]["assets_meters"]["asset_no"]["blank_means"]
    if not contract_problems(no_blank)[2]:
        problems.append("does not bite an issued column that never says what blank does")

    # The ruled EXCEPTION is checked, not skipped.
    file_issued = json.loads(json.dumps(good))
    file_issued["columns"]["accounts"]["account_no"]["sample"] = ""
    if not contract_problems(file_issued)[2]:
        problems.append("does not bite a FILE-issued column shipping a blank sample")

    # Clause (d).
    if not wrong_screen_names([("planted.py", 'f"from Settings › Numbers › {noun}"')], "Numbering"):
        problems.append("does not bite `Settings › Numbers` against a tab called Numbering")
    if wrong_screen_names([("planted.py", '"from Settings → Numbering → Meter"')], "Numbering"):
        problems.append("bites the correct screen name — false positive")
    if wrong_screen_names([("planted.py", '"Settings → Services and UoM"')], "Numbering"):
        problems.append("bites an unrelated Settings tab — the clause is not scoped")
    return problems


def _sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if "/tests/" in rel or path.name.startswith("test_"):
            continue
        out.append((rel, _strip_py(path.read_text("utf-8", errors="replace"))))
    return out


def run() -> tuple[str, str]:
    """`("PASS"|"FAIL"|"SKIP", detail)` — the runner's contract, not a bool."""
    if not BACKEND.exists():
        return "SKIP", "06-backend does not exist yet"

    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    label = numbering_tab_label()
    if label is None:
        return "SKIP", f"`{NUMBERING_TAB_KEY}` is not in en.json — clause (d)'s authority"

    facts, error = _probe()
    if error:
        # ⚠ NEVER A PASS. A check that could not run has not passed.
        return "SKIP", (
            "could not read the import module's declarations, so nothing was checked: "
            f"{error}. The probe runs `python -c` in 06-backend with "
            "DJANGO_SETTINGS_MODULE=config.settings.test and touches no database"
        )

    series_missing, column_missing, contract = contract_problems(facts)
    wrong_names = wrong_screen_names(_sources(), label)
    seen_sites = {name.split(" says ", 1)[0] for name in wrong_names}
    new_names = [n for n in wrong_names if n.split(" says ", 1)[0] not in WRONG_SCREEN_NAME_BANKED]
    healed = sorted(WRONG_SCREEN_NAME_BANKED - seen_sites)
    targets = facts.get("target_series") or {}

    note = (
        f"CR-046: {len(targets)} import target(s) wired to "
        f"{len({v[0] for v in targets.values()})} series, all in SERIES_CATALOG; "
        f"{len(FILE_ISSUED_BY_RULE)} target(s) file-issued by a ruling; "
        f"the numbering tab is `{label}` and {len(wrong_names)} served string(s) call it "
        f"something else ({len(WRONG_SCREEN_NAME_BANKED)} banked, DEF-1840); "
        "self-test: 9/9 clauses bite"
    )

    # ── RED PROOF ─────────────────────────────────────────────────────────
    # Clause (d), taken on THIS tree with `WRONG_SCREEN_NAME_BANKED` emptied —
    # which is the tree exactly as CR-046 wave A left it. The defect is live
    # here, so no worktree was needed and none was mutated:
    #
    #   FAIL: CR-046: 6 import target(s) wired to 4 series, all in
    #   SERIES_CATALOG; 1 target(s) file-issued by a ruling; the numbering tab
    #   is `Numbering` and 5 served string(s) call it something else (0 banked,
    #   DEF-1840); self-test: 9/9 clauses bite. clause (d) — 5 NEW served
    #   string(s) send an operator to a Settings tab that does not exist. Under
    #   CR-046 the identifier column's whole job is to send them to that screen
    #   (DEF-1840):
    #     06-backend/apps/metering/import_rules.py:1737 says `Settings …
    #       Numbers`, the tab is `Numbering`
    #     06-backend/apps/metering/import_rules.py:2370 says `Settings …
    #       Numbers`, the tab is `Numbering`
    #     06-backend/apps/metering/import_runs.py:785 says `Settings …
    #       Numbers`, the tab is `Numbering`
    #     06-backend/apps/metering/import_runs.py:4510 says `Settings …
    #       Numbers`, the tab is `Numbering`
    #     06-backend/apps/metering/import_runs.py:4564 says `Settings …
    #       Numbers`, the tab is `Numbering`
    #
    # The STALE half was proved the same way, by banking a line that names the
    # screen correctly: the gate FAILS and names the row to remove.
    failures: list[str] = []
    if series_missing:
        failures.append(
            f"clause (a) — {len(series_missing)} target(s) name a series SERIES_CATALOG does "
            "not define. `next_number` raises, the import warns "
            "`numbering_series_missing`, and the row loads with no number at all (DEF-615):"
            "\n    " + "\n    ".join(series_missing)
        )
    if column_missing:
        failures.append(
            f"clause (b) — {len(column_missing)} series wired to a column the shipped template "
            "does not offer. That column is also the MATCH KEY for *Insert & update*, so every "
            "row would read as new:\n    " + "\n    ".join(column_missing)
        )
    if contract:
        failures.append(
            f"clause (c) — {len(contract)} identifier column(s) disagree with the series that "
            "issues them:\n    " + "\n    ".join(contract)
        )
    if new_names:
        failures.append(
            f"clause (d) — {len(new_names)} NEW served string(s) send an operator to a Settings "
            "tab that does not exist. Under CR-046 the identifier column's whole job is to "
            "send them to that screen (DEF-1840):\n    " + "\n    ".join(new_names)
        )
    if healed:
        failures.append(
            f"clause (d) — the banked set is STALE: {', '.join(healed)} no longer name the "
            "screen wrongly. A ratchet that never tightens is a number nobody reads (DEF-490). "
            f"Remove the line(s) from WRONG_SCREEN_NAME_BANKED in {Path(__file__).name}"
        )
    if failures:
        return "FAIL", f"{note}. " + "\n  ".join(failures)
    return "PASS", note


def main() -> int:
    """Run this gate from the command line.

    ⚠ A `run()` with no main block exits 0 with no output, which is
    indistinguishable from a pass to the eye and to `$?` (DEF-672).
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
