#!/usr/bin/env python3
"""G35 — the two version literals must be equal, and both must be real.

WHY THIS GATE EXISTS
--------------------
`12-governance/13-change-process.md` step 7 exists because the PO said versioning
is *"many times not followed correctly"*, and the repo proved them right —
`package.json` read `0.0.1` after 159 recorded defects. Step 7 fixed that by
declaring ONE version, `<release>.<change>.<fix>`, derived everywhere.

It is not derived. It is **copied**, by a human, between two files in two
languages:

    07-frontend/package.json   "version": "2.29.8"
    06-backend/pyproject.toml  version = "2.29.8"

and until now **nothing compared them**. Thirty-six gates and not one opened
`pyproject.toml`.

THREE OCCURRENCES, THE LAST ONE MEASURED
----------------------------------------
DEF-242, DEF-296, and DEF-341 — at commit `8ea7847`, `package.json` said
**2.29.7** while `pyproject.toml` said **2.29.6**. Each earlier one was fixed by
correcting the number; none made the pair checkable, which is why there was a
third.

WHY EVERY EXISTING CHECK IS BLIND TO IT
---------------------------------------
Each literal is individually **well-formed**, so JSON parsing, TOML parsing, lint
and every test on either side is clean. The only thing wrong is a RELATIONSHIP
BETWEEN TWO FILES, and no file can see that from inside itself.

It is also the LAST edit a lane makes — after its own checks have passed — so the
single moment the mistake is possible is the moment nobody is looking. That is
not carelessness; it is where the process puts the step.

WHAT THIS CHECKS
----------------
1. Both literals exist and parse.
2. **They are equal.** This is the whole gate; the other clauses only make its
   failures legible.
3. Both match `<release>.<change>.<fix>` — step 7's scheme, so `0.0.1` or a
   `2.29` cannot pass as a version.

CLAUSE 4, ADDED 2026-08-26 — THE VERSION HAS A CHANGELOG ENTRY
--------------------------------------------------------------
`13-change-process.md` step 7 rule 4 says, in as many words: *"A GATE REFUSES a
CR marked done with no version, and a version bump with no CHANGELOG entry."*
The rule was written on 2026-08-16. **The gate was not built, and the very next
version cut skipped the entry** — `2.52.0` went into all four literals while
`CHANGELOG.md`'s newest heading stayed `2.51.0`, so a user on 2.52.0 opening the
changelog was told about a build they were not running (DEF-806). The entry was
written by hand after the fact; nothing stopped the next one.

**And the PO's ruling of 2026-08-26 made this clause load-bearing rather than
tidy.** Verbatim: *"We have to bump version when major when minor so we are able
to keep track of"* — the version now moves on **every wave**, not once per CR.
That multiplies the number of bumps by roughly ten, and with it every chance to
repeat DEF-806. Per-wave bumping is safe BECAUSE this clause exists; without it,
it is ten times as fragile as what it replaced.

So: whatever `package.json` says, `CHANGELOG.md` must carry a `## [<version>]`
heading for it. That is a RELATIONSHIP BETWEEN TWO FILES, which is the only kind
of thing this gate has ever been able to see and no file can see from inside
itself.

CLAUSE 5, ADDED 2026-09-27 — *EVERY* PUBLISHED VERSION KEEPS ITS ENTRY
----------------------------------------------------------------------
Clause 4 asks one question: *does the version in `package.json` RIGHT NOW have
an entry?* That question is complete only while a version stays current long
enough to be asked about. On a branch where six lanes each bump the fix digit,
**a version is current for about twenty minutes**, and if nobody runs the gate
in that window it ships unrecorded and nothing ever looks at it again — clause 4
is by then busy asking about a later number that does have an entry.

Measured on 2026-09-27: **21 versions had been published with no entry**, and
three of them that day (`2.377.1`, `2.377.2`, `2.380.3`). A person told *"look
in build 2.377.1"* found nothing between `2.376.1` and `2.377.3`. `DEF-GOV-6813`
had already written the hole down two days earlier — *"the check that should
have said so only ever looks at the newest version"* — in a `### Known` block of
the changelog, where no gate reads. `DEF-GOV-6930` is the second occurrence.

So clause 5 asks the whole question: **every version this branch's history has
ever written into `package.json` must have a heading.** The history is the only
record of what was published — a version leaves no other trace once a sibling
bumps past it.

⚠ **IT IS RATCHETED, AND THE EIGHTEEN IT DOES NOT ASK ABOUT ARE NAMED**
(`12-governance/changelog-gaps-baseline.txt`). Writing eighteen entries three
weeks late, from commits whose lanes are gone, would be invention; a gate born
red on eighteen rows gets switched off. The baseline is a list with a count, not
a silence — law 7's fifth shape, *a declared blind spot with no number attached
is indistinguishable from an empty one*.

⚠ **AND WHERE IT CANNOT READ THE HISTORY IT SAYS SO RATHER THAN PASSING.** An
export with no `.git` cannot answer *what was published*, so clause 5 reports
that it did not run and clauses 1–4 stand on their own. A clause that silently
covers nothing is the hole this one was written to close.

⚠ **THAT PARAGRAPH SAID "A SHALLOW CLONE OR" AND THE CODE NEVER ASKED
(`DEF-GOV-7807`, 2026-09-28).** It detected only the EMPTY case; a shallow clone
is not empty, it is SHORT, so the clause read whatever was inside the graft and
returned it as the whole answer. **Measured on this branch that day:
`--is-shallow-repository` is `true`, clause 5 saw 16 versions, and `CHANGELOG.md`
carries 772 entries** — it was answering about roughly one version in fifty
while the PASS line said *"every one of the 16 version(s) this branch has
published"*. Hard-won law 1 on the paragraph, law 7's fifth shape on the check,
inside the gate written to close that shape.

**The clause still RUNS on a shallow clone, deliberately** — the versions inside
the graft are the recent ones, which is exactly where a lane's own omission
lands, and it caught `2.385.0` and `2.385.1` there the day this was fixed.
What changed is what it CLAIMS: `history_is_shallow()` is asked before the
result is phrased, and both the PASS and the FAIL say how deep they could see,
so the unread part carries a NUMBER instead of being absent.

CLAUSE 6, ADDED 2026-10-21 — THE NATIVE FIELD APP IS A THIRD LITERAL
--------------------------------------------------------------------
The native field app (`field-app/`, CR-187-BRC10) has its OWN `package.json`
and lockfile, because it needs React 19 and the web app is on React 18
(decision log 2026-10-21, *"twelve conflicts"*, #1). Conflict #4 of the same
ruling: *"one product version; the field app shows it and keeps its own
app-store build number. `field-app/package.json` joins `G35` and
`allocate.py version`."*

So `field-app/package.json` must read the SAME `<release>.<change>.<fix>` as the
other two, and its lockfile's two copies mirror it exactly as
`07-frontend/package-lock.json` mirrors the web one (DEF-347's lesson applied
on day one rather than learned a fourth time). The field app shows this number
in its menu beside the store build number (`field-app/src/release/build.ts`),
so a technician's defect report names a version the rest of the product also
shipped. The STORE BUILD NUMBER (`ios.buildNumber` / `android.versionCode` in
`field-app/app.json`) is deliberately NOT a version literal and is not compared:
it counts binaries, moves only when a binary is built, and the stores refuse a
reused one by themselves.

Measured the day it was added: `field-app/package-lock.json` read **2.589.0**
while `field-app/package.json` read **2.590.0** — the drift DEF-347 describes,
one release old, caught by this clause before it shipped.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not check that the version ROSE. A lane may legitimately land a commit at
the same version as the tip, and two lanes racing can produce a version that is
correct in both files and not monotonic — that is a different defect with a
different fix, and a gate that argued about it would be switched off. This gate
answers exactly one question, and answers it completely.

The real fix is to stop having two literals: derive the backend version from
`package.json` at build time, then this gate asserts a derivation instead of a
copy. Until then, this is the check that would have caught all three.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO / "07-frontend" / "package.json"
BACKEND = REPO / "06-backend" / "pyproject.toml"
LOCKFILE = REPO / "07-frontend" / "package-lock.json"
#: Clause 6 — the native field app's own manifest and lockfile (CR-187-BRC10).
FIELD_APP = REPO / "field-app" / "package.json"
FIELD_APP_LOCKFILE = REPO / "field-app" / "package-lock.json"
#: The PRODUCT changelog — not `04-docs/CHANGELOG.md`, which is the
#: design-handoff log serving a different reader (step 7 says so).
CHANGELOG = REPO / "CHANGELOG.md"
#: Versions published before clause 5 existed, which will not be written up.
#: Read the file's own header before adding a line to it.
GAPS_BASELINE = REPO / "12-governance" / "changelog-gaps-baseline.txt"

# step 7's scheme: <release>.<change>.<fix>
SCHEME = re.compile(r"^\d+\.\d+\.\d+$")
_TOML_VERSION = re.compile(r"^version\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def frontend_version() -> str | None:
    try:
        return json.loads(FRONTEND.read_text(encoding="utf-8")).get("version")
    except Exception:  # noqa: BLE001 — an unreadable file is a finding, not a crash
        return None


def backend_version() -> str | None:
    """The FIRST `version = "..."` at the start of a line.

    ⚠ Not any `version` anywhere: `pyproject.toml` also carries
    `requires-python`, tool tables and dependency pins, several of which contain
    the word. Anchoring to the line start and taking the first match is what
    `12-governance/13-change-process.md` means by the project version.
    """
    try:
        m = _TOML_VERSION.search(BACKEND.read_text(encoding="utf-8"))
        return m.group(1) if m else None
    except Exception:  # noqa: BLE001
        return None


def field_app_version() -> str | None:
    """`field-app/package.json`'s version — clause 6."""
    try:
        return json.loads(FIELD_APP.read_text(encoding="utf-8")).get("version")
    except Exception:  # noqa: BLE001 — an unreadable file is a finding, not a crash
        return None


def field_app_lockfile_versions() -> list[tuple[str, str | None]]:
    """The field app's lockfile, both copies — clause 6, DEF-347's shape."""
    try:
        data = json.loads(FIELD_APP_LOCKFILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return [("field-app/package-lock.json", None)]
    return [
        ("field-app/package-lock.json", data.get("version")),
        ('field-app/package-lock.json packages[""]', (data.get("packages", {}).get("") or {}).get("version")),
    ]


def lockfile_versions() -> list[tuple[str, str | None]]:
    """The lockfile's TWO copies of the version — `version` at the top level and
    the same field inside `packages[""]`. Both mirror `package.json`.

    ⚠ DEF-347. G35 shipped comparing exactly the two files DEF-341 named, and
    the lockfile drifted to **thirteen releases behind** without a single check
    noticing — it read 2.28.0 while `package.json` read 2.29.13. Nobody thinks
    of a lockfile as a version literal because npm regenerates it rather than a
    lane editing it, and no npm command fails on the mismatch. A check built
    from one incident is scoped to that incident, which is exactly what
    DEF-341's own row warned would happen.
    """
    try:
        data = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return [("package-lock.json", None)]
    return [
        ("package-lock.json", data.get("version")),
        ('package-lock.json packages[""]', (data.get("packages", {}).get("") or {}).get("version")),
    ]


def changelog_versions() -> set[str]:
    """Every version `CHANGELOG.md` carries a `## [x.y.z]` heading for.

    Read from the heading rather than anywhere in the text on purpose: the body
    of an entry legitimately NAMES other versions ("fixed since 2.51.0"), and a
    substring search would accept an entry that only mentions the version it is
    supposed to be about.
    """
    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — an unreadable file is a finding, not a crash
        return set()
    return set(re.findall(r"^##\s*\[(\d+\.\d+\.\d+)\]", text, re.MULTILINE))


def baseline_gaps() -> set[str]:
    """The versions clause 5 is told not to ask about, and why is in the file."""
    try:
        text = GAPS_BASELINE.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — a missing baseline means "excuse nothing"
        return set()
    return {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and SCHEME.match(line.strip())
    }


def history_is_shallow() -> bool:
    """True when this checkout's git history is TRUNCATED rather than whole.

    ⚠ **THE DOCSTRING ABOVE PROMISED THIS AND THE CODE NEVER ASKED IT
    (`DEF-GOV-7807`, 2026-09-28).** Clause 5's own paragraph says *"a shallow
    clone or an export with no `.git` cannot answer what was published, so
    clause 5 reports that it did not run"*. `published_versions()` detected only
    the EMPTY case — no `+  "version"` line anywhere — and a shallow clone is
    not empty, it is SHORT. So on a shallow clone the clause read whatever
    happened to be inside the graft and returned it as the whole answer, and the
    PASS line said *"every one of the N version(s) this branch has published"*
    over a fraction of them.

    **Measured on this branch on 2026-09-28**: `--is-shallow-repository` is
    `true`, 18 commits touch `07-frontend/package.json`, clause 5 saw **16**
    versions — while `CHANGELOG.md` carries **772** versioned entries. So the
    clause was answering about roughly one version in fifty and saying *every*.

    That is hard-won law 7's fifth shape (*a check reporting zero — or here,
    sixteen — over a scope it silently excludes*) sitting inside the very gate
    written to close that shape for changelog entries, and hard-won law 1 (*a
    comment claiming a guarantee is not the guarantee*) on the paragraph that
    claimed it.

    ⚠ **THE CLAUSE IS NOT SWITCHED OFF ON A SHALLOW CLONE, AND THAT IS
    DELIBERATE.** The sixteen it can see are the RECENT ones — exactly the
    window where a lane's own omission lands — and it caught `2.385.0` and
    `2.385.1` there on the day this was written. Turning it off would trade a
    true finding for silence. What changes is only what it CLAIMS: it now says
    how deep it could see, so the unread part has a number beside it instead of
    being absent.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Cannot tell — say SHALLOW, because the unsafe option must be the one
        # you type (hard-won law 3). Claiming completeness is the unsafe one.
        return True
    return proc.returncode != 0 or proc.stdout.strip() == "true"


def published_versions() -> tuple[set[str], str | None]:
    """Every version this branch's history has written into `package.json`.

    ⚠ **THE HISTORY IS THE ONLY RECORD OF WHAT WAS PUBLISHED.** A version that a
    sibling lane bumps past leaves no trace in any file — `package.json` holds
    one number, and it is the newest one. Reading the ADDED `"version"` lines of
    that file's own log is the only way to ask *which numbers has a user ever
    been able to be running?*

    Returns `(versions, why_not)`. `why_not` is a sentence wherever git could
    not answer, and the caller says so instead of passing.
    """
    try:
        proc = subprocess.run(
            ["git", "log", "-p", "--", "07-frontend/package.json"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return set(), "git is not on PATH"
    except subprocess.TimeoutExpired:
        return set(), "git log over package.json did not finish in 120s"
    if proc.returncode != 0:
        return set(), f"git log exited {proc.returncode}: {proc.stderr.strip()[:200]!r}"
    found = set(re.findall(r'^\+\s*"version":\s*"(\d+\.\d+\.\d+)"', proc.stdout, re.MULTILINE))
    if not found:
        # Not an empty answer — an unreadable one. A repository with no history
        # of this file cannot be distinguished from one where the pattern moved,
        # and either way clause 5 has checked nothing.
        return set(), "no `+  \"version\": \"x.y.z\"` line in the history of 07-frontend/package.json"
    return found, None


def run() -> tuple[str, str]:
    fe, be = frontend_version(), backend_version()
    locks = lockfile_versions()
    fa = field_app_version()
    fa_locks = field_app_lockfile_versions()

    missing = [
        n
        for n, v in [("package.json", fe), ("pyproject.toml", be), *locks, ("field-app/package.json", fa), *fa_locks]
        if v is None
    ]
    if missing:
        return "FAIL", f"no readable version literal in: {', '.join(missing)}"

    disagree = [(n, v) for n, v in locks if v != fe]
    if disagree:
        return "FAIL", (
            f"the LOCKFILE disagrees with package.json ({fe!r}): "
            + ", ".join(f"{n} says {v!r}" for n, v in disagree)
            + " — a lockfile mirrors its package.json version, and npm will not "
            "tell you when it stops. Run `npm version --no-git-tag-version <v>` "
            "or edit both copies (DEF-347)."
        )

    if fe != be:
        return "FAIL", (
            f"THE TWO VERSION LITERALS DISAGREE — package.json says {fe!r}, "
            f"pyproject.toml says {be!r}. One bump moved and the other did not "
            f"(DEF-341, third occurrence). Move BOTH, forward for both and "
            f"backward for neither; if a sibling lane has already taken the next "
            f"number, skip it rather than reusing it."
        )

    # ── clause 6 · the native field app carries the same product version ────
    if fa != fe:
        return "FAIL", (
            f"THE FIELD APP'S VERSION DISAGREES — field-app/package.json says {fa!r}, "
            f"07-frontend/package.json and pyproject.toml say {fe!r}. One product version, "
            f"three literals (decision log 2026-10-21, twelve conflicts, #4): move "
            f"field-app/package.json AND its lockfile with the other two. The store build "
            f"number in field-app/app.json is separate and is not a version literal."
        )
    fa_disagree = [(n, v) for n, v in fa_locks if v != fa]
    if fa_disagree:
        return "FAIL", (
            f"the FIELD APP's LOCKFILE disagrees with field-app/package.json ({fa!r}): "
            + ", ".join(f"{n} says {v!r}" for n, v in fa_disagree)
            + " — run `npm version --no-git-tag-version <v>` in field-app/ or edit both "
            "copies (DEF-347's shape, clause 6)."
        )

    off_scheme = [f"{n}={v!r}" for n, v in (("package.json", fe), ("pyproject.toml", be)) if not SCHEME.match(v)]
    if off_scheme:
        return "FAIL", (
            f"version does not match <release>.<change>.<fix>: {', '.join(off_scheme)} "
            f"(change-process step 7)"
        )

    entries = changelog_versions()
    if not entries:
        return "FAIL", (
            f"CHANGELOG.md carries no `## [x.y.z]` heading at all, so nothing can "
            f"say what is in {fe}. Step 7 rule 4: a version bump with no changelog "
            f"entry is refused."
        )
    if fe not in entries:
        newest = max(entries, key=lambda v: tuple(int(p) for p in v.split(".")))
        return "FAIL", (
            f"VERSION {fe} HAS NO CHANGELOG ENTRY — CHANGELOG.md's newest heading is "
            f"{newest}. A user on {fe} opening the changelog is told about a build they "
            f"are not running (DEF-806, which is exactly this, on the very next version "
            f"after the rule requiring this check was written). The entry and the bump "
            f"land in the SAME commit — see 13-change-process.md step 7, as amended by "
            f"the PO ruling of 2026-08-26 that moves the version on every wave."
        )

    # ── clause 5 · every version ever published keeps its entry ───────────────
    published, why_not = published_versions()
    baseline = baseline_gaps()
    # Asked BEFORE the results are phrased, because it changes what may be
    # claimed about them and not what is checked (DEF-GOV-7807).
    shallow = history_is_shallow()
    if why_not is not None:
        print(f"note: package.json, pyproject.toml, field-app/package.json and all four lockfile copies read {fe}")
        print(f"note: CHANGELOG.md carries {len(entries)} versioned entr(ies); {fe} is one")
        return "PASS", (
            f"all {3 + len(locks) + len(fa_locks)} version literals agree at {fe}, and it has a changelog "
            f"entry. ⚠ CLAUSE 5 DID NOT RUN — {why_not} — so every version published "
            f"BEFORE this one went unchecked this run; only the current one was asked about. "
            f"That is the exact hole DEF-GOV-6930 is, stated with its cause rather than "
            f"passed over in silence."
        )

    unrecorded = sorted(
        published - entries - baseline,
        key=lambda v: tuple(int(part) for part in v.split(".")),
    )
    if unrecorded:
        return "FAIL", (
            f"{len(unrecorded)} version(s) were published with NO changelog entry: "
            + ", ".join(unrecorded)
            + f". A person told to look in one of them finds nothing between the entries "
            f"either side of it (DEF-GOV-6930; DEF-GOV-6813 recorded the same hole two days "
            f"earlier and nothing closed it). Clause 4 cannot see this — it only ever asks "
            f"about the version that is CURRENT, and on this branch a version is current for "
            f"about twenty minutes. Write the entry from the COMMIT that bumped it "
            f"(`git log -S '\"version\": \"<v>\"' -- 07-frontend/package.json`), with a "
            f"BRACKETED `## [<v>]` heading in version order. "
            f"{len(baseline)} version(s) predating this clause are excused by name in "
            f"12-governance/changelog-gaps-baseline.txt; adding a line there is not the fix."
            + (
                f" ⚠ AND THIS IS A FLOOR, NOT A TOTAL: the checkout is a SHALLOW clone, so "
                f"clause 5 could only ask about the {len(published)} most recent published "
                f"version(s) of the {len(entries)} the changelog records — there may be more "
                f"gaps behind the graft (DEF-GOV-7807)."
                if shallow
                else ""
            )
        )

    print(f"note: package.json, pyproject.toml, field-app/package.json and all four lockfile copies read {fe}")
    print(f"note: CHANGELOG.md carries {len(entries)} versioned entr(ies); {fe} is one")
    print(
        f"note: clause 5 read {len(published)} published version(s) out of the history of "
        f"07-frontend/package.json; {len(baseline)} are excused by the baseline file"
    )
    # ⚠ THE SCOPE IS STATED IN THE PASS LINE, NOT ONLY IN A `note:` (DEF-GOV-7807).
    # `run_gates` prints the returned detail in its results table; the `note:`
    # lines above scroll past in a 137-gate run. A blind spot a reader never
    # sees is the same as no blind spot declared at all.
    if shallow:
        print(
            f"note: ⚠ clause 5's history is SHALLOW — it saw {len(published)} version(s); "
            f"CHANGELOG.md holds {len(entries)} entries, so most of what this branch has "
            f"published is OUTSIDE what was checked."
        )
        return "PASS", (
            f"all {3 + len(locks) + len(fa_locks)} version literals agree at {fe}, and it has a changelog "
            f"entry. ⚠ CLAUSE 5 RAN OVER A TRUNCATED HISTORY: this checkout is a SHALLOW "
            f"clone, so it could ask about only the {len(published)} most recent published "
            f"version(s) — of the {len(entries)} the changelog records — and all of those "
            f"have an entry ({len(baseline)} excused by name in the baseline). Anything "
            f"published before the graft was NOT checked. Deepen with "
            f"`git fetch --unshallow` to ask the whole question (DEF-GOV-7807)."
        )
    return "PASS", (
        f"all {3 + len(locks) + len(fa_locks)} version literals agree at {fe}, and every one of the "
        f"{len(published)} version(s) this branch has published has a changelog entry "
        f"({len(baseline)} excused by name in the baseline)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
