#!/usr/bin/env python3
"""G27 — every translation key a component asks for must exist in the catalogue.

WHY THIS GATE EXISTS (2026-08-19)
---------------------------------
The Product Owner photographed the deployed Settings → Notifications screen and
it read, as its own panel heading, the literal string:

    notifications.rights.title

`DisconnectRightsFooterCard` asks for ELEVEN `notifications.rights.*` keys and
**all eleven were absent from every catalogue**. A System Admin saw
`notifications.rights.edit` on a button and `notifications.rights.hint` where the
explanation should be. The whole card rendered its own source code.

**IT WAS THE THIRD OCCURRENCE THAT DAY.** The dashboard's five service labels
(DEF-282) and its aging columns were the first two. Every one reached a deployed
build and every one was found by a person looking at a screen.

WHY NOTHING ELSE CATCHES IT — and this is the whole argument for the gate
--------------------------------------------------------------------------
* **tsc cannot.** A translation key is a string literal; there is no type that
  says "this string must be a member of that JSON file".
* **eslint cannot**, for the same reason.
* **vitest cannot.** A component test renders the component and asserts on text
  the TEST ITSELF supplies. Written alongside the component, it happily asserts
  the key name and passes.
* **⚠ G15 CANNOT, AND THIS IS THE INSTRUCTIVE PART.** G15 checks PARITY BETWEEN
  the eleven catalogues. Eleven keys missing from all eleven files are perfectly
  in parity, so G15 reports nothing at all. A check can be green precisely
  BECAUSE the failure is uniform.

So the only detector was a human reading a rendered screen — which is CLAUDE.md
hard-won law 6 (*"no gate looks at rendered output"*) charging its rent for the
third time in one day.

WHAT THIS CHECKS
----------------
Every LITERAL `t("some.key")` in the frontend source resolves in `en.json`.

⚠ **AND SINCE 2026-09-05, EVERY KEY HANDED TO THE SHARED KIT AS *CONFIG* — WHICH
IS THE HOLE THAT PUT A RAW KEY BACK ON A SCREEN (`DEF-WRK-3957`).**
`Work → Templates` declared `searchPlaceholder: "work.templates.search"`, the key
was in a hand-over file rather than a catalogue, and `DataTable` — not the screen
— made the `t()` call. So the search box on a deployed screen read the literal
words **`work.templates.search`**, and this gate said *every literal translation
key resolves* because there is no `t("…")` in that file to find. The screen was
photographed by a person, again, which is exactly the cost this gate was built to
stop paying.

The kit translates 410 such keys today: `labelKey`, `titleKey`, `bodyKey`,
`unavailable_reason_key`, `searchPlaceholder` and friends, read by `DataTable`,
`AppShell`, `SegmentedControl`, `WizardFrame` and the workflow kit. They are
**exactly as visible to a clerk** as a `t()` call and had **no check at all**.

⚠ **A CONFIG KEY HAS NO FALLBACK AND CANNOT HAVE ONE**, so unlike a `t()` call
there is no debt bucket to fall into: the caller hands over a key and the kit
makes the call, so a config key either resolves or a clerk reads it. That is why
this half fails outright.

**Which puts a lane that may not edit `src/i18n/locales/` in a real bind**, and
the remedy is worth stating because the bind is what produced the defect: land
the key in the eleven catalogues, or do not declare the config key at all —
`DataTable` falls back to `table.search.placeholder`, which is generic but is
words. Do NOT declare a key you cannot resolve. If a kit slot ever needs an
inline English bridge, the shape is `t(key, { defaultValue })` with the default
carried in the config beside the key, and this gate should then count it as debt
the way `CALL_WITH_OPTIONS` is counted — built when a caller needs it, not
before, so it cannot sit here as a prop nothing passes (hard-won law 2).

**Literal only, and that limit is deliberate.** A dynamic key —
`t(\\`dashboard.todo.item.${row.code}\\`)` — cannot be resolved without running the
app, and most such call sites already pass a `defaultValue`, which is the correct
pattern for a key whose name is data. Checking them would mean guessing, and a
gate that guesses gets switched off. This one is exact: it finds only real
failures, and it finds every one of the literal kind.

`i18next` PLURALS are honoured: a key answered by `key_one`/`key_other` is
present, because that is how i18next resolves a call carrying a `count`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = REPO_ROOT / "07-frontend" / "src"
EN = SRC / "i18n" / "locales" / "en.json"

# t("a.b.c") and t('a.b.c') — a dotted literal, nothing interpolated.
CALL = re.compile(r"""\bt\(\s*["']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)["']""")

#: The same call, but passing a SECOND argument — `t("k", { defaultValue: "…" })`.
#: i18next renders that fallback when the key is missing, so such a key shows the
#: user correct English and is a TRANSLATION-COVERAGE gap, not a raw key on screen.
#: Keeping the two apart is DEF-1788: this gate reported 556 keys as "raw" when
#: not one of them was, and the count went unexamined for weeks because the gate
#: had never once passed and so was never read.
#:
#: ⚠ A key handed to the shared kit as CONFIG — `labelKey: "a.b"`,
#: `searchPlaceholder: "a.b"` — never appears inside a `t(...)` in the file that
#: writes it, so neither pattern above can see it and the kit makes the call
#: instead. `DEF-WRK-3957`: that put the literal `work.templates.search` in a
#: search box on a deployed screen while this gate printed PASS.
#:
#: The property NAME is what identifies one: `*Key` / `*Keys` is this repo's own
#: convention for "this string is a translation key", and `searchPlaceholder` is
#: the one slot that predates it. Matching on the name rather than on the value
#: keeps the check exact — a dotted string in some other property is data, not a
#: key, and a gate that guesses gets switched off.
CONFIG_KEY = re.compile(
    r"""\b([A-Za-z_][A-Za-z0-9_]*(?:Key|Keys)|searchPlaceholder)\s*:\s*"""
    r"""["']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)["']"""
)

CALL_WITH_OPTIONS = re.compile(
    r"""\bt\(\s*["']([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)["']\s*,"""
)

#: Keys that are absent AND carry a fallback. A backlog, not a break. Baselined at
#: what was actually there the day the split landed, so the gate can go GREEN and
#: be read again, and any NEW one fails on its own. Measured, not wished for —
#: an aspirational baseline is why this gate was never read (decision log
#: 2026-08-27, "WHY SOME GATE FAMILIES BREACH").
COVERAGE_BASELINE = 558  # measured 2026-08-28 on the branch; may fall, never rise
# ⚠ COMMENTS ARE STRIPPED FIRST, and the first run of this gate is why. It
# reported `w0.scaffold` in App.tsx — a key that appears ONLY inside a comment
# explaining that the string used to render and no longer does. A gate whose
# first finding is a false positive is a gate somebody switches off, and this
# repo already learned that today when G26's first draft invented a status
# vocabulary and reported nine failures on states the register uses on purpose.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)


def _code_only(text: str) -> str:
    # ⚠ **LINE COMMENTS GO FIRST, AND THE ORDER IS THE WHOLE POINT (DEF-741).**
    # This read `LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))` for six days.
    # A `//` line that spells a path with a star in it — `// see
    # src/i18n/locales/*.json` — contains `/*`, so stripping BLOCK first opened a
    # comment there and closed it at the next `*/` ANYWHERE BELOW, swallowing
    # every line between. Measured 2026-08-26: 3,608 bytes of real code across
    # eight files were invisible to this gate, and in `NewConnectsTab.tsx` that
    # hid a live `t()` call from the check written to find exactly those.
    # A gate cannot report what it cannot see, and it reports PASS either way —
    # which is this repo's most-repeated flaw: a check whose output cannot
    # distinguish pass from fail is worse than no check, because it is trusted.
    return BLOCK_COMMENT.sub("", LINE_COMMENT.sub("", text))


# i18next resolves a `count` call through these suffixes.
PLURAL_SUFFIXES = ("_zero", "_one", "_two", "_few", "_many", "_other")


#: Keys already known to be missing — see the file's own header for why it is
#: empty and why adding a line is an admission rather than a to-do.
BASELINE = Path(__file__).with_name("g27_translation_keys_baseline.txt")


def _baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    out = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def check() -> tuple[list[str], list[str]]:
    if not EN.is_file():
        return [f"{EN} is missing"], []
    catalogue = set(json.loads(EN.read_text(encoding="utf-8")))
    baselined = _baseline()

    def present(key: str) -> bool:
        return key in catalogue or any(key + s in catalogue for s in PLURAL_SUFFIXES)

    violations: list[str] = []
    notes: list[str] = []
    known: set[str] = set()
    covered_total = 0
    scanned = 0
    for path in sorted(SRC.rglob("*.tsx")):
        if ".test." in path.name:
            continue
        scanned += 1
        source = _code_only(path.read_text(encoding="utf-8"))
        absent = {k for k in CALL.findall(source) if not present(k)}
        # A key called anywhere in this file with a second argument renders its
        # fallback, so it is coverage debt rather than a raw key on screen.
        with_fallback = set(CALL_WITH_OPTIONS.findall(source))
        # ⚠ AND THE KEYS THE KIT CALLS ON THIS FILE'S BEHALF (`DEF-WRK-3957`).
        # They reach a clerk through `DataTable`, `AppShell` and friends, so
        # they belong in exactly the same two buckets: absent-and-covered is
        # debt, absent-and-bare is a raw key on a screen.
        for _prop, key in CONFIG_KEY.findall(source):
            if not present(key):
                absent.add(key)
        covered = absent & with_fallback
        covered_total += len(covered)
        absent = absent - covered
        # ⚠ THE SPLIT IS THE POINT (DEF-662). A known miss is REPORTED and does
        # not fail; an unknown one fails on its own however long the known list
        # is. Without this the gate answered only "clean or not", and the day it
        # was not clean every new break hid inside the same red.
        known |= absent & baselined
        missing = sorted(absent - baselined)
        if missing:
            rel = path.relative_to(REPO_ROOT)
            shown = ", ".join(missing[:6]) + (
                f" … +{len(missing) - 6} more" if len(missing) > 6 else ""
            )
            violations.append(
                f"{rel} asks for {len(missing)} key(s) no catalogue defines: {shown}"
            )
    notes.append(f"{scanned} components scanned")
    notes.append(
        f"{covered_total} absent key(s) carry a fallback and render English "
        f"(coverage debt, baseline {COVERAGE_BASELINE})"
    )
    if covered_total > COVERAGE_BASELINE:
        violations.append(
            f"translation coverage ROSE: {covered_total} absent key(s) carry a "
            f"fallback, against a baseline of {COVERAGE_BASELINE}. These render "
            f"correct English to a user and a raw key to nobody — but the debt may "
            f"fall and never rise."
        )
    if baselined:
        notes.append(
            f"{len(known)} of {len(baselined)} baselined key(s) still missing "
            "(baseline may fall, never rise — see the baseline file's header)"
        )
        stale = sorted(baselined - known)
        if stale:
            notes.append(
                f"{len(stale)} baselined key(s) now resolve and should be DELETED from the "
                f"baseline: {', '.join(stale[:4])}"
            )
    return violations, notes


def main() -> int:
    violations, notes = check()
    for n in notes:
        print(f"note: {n}")
    for v in violations:
        print(f"FAIL: {v}")
    if violations:
        # ⚠ NOT every violation is component-shaped (2026-09-01). `check()` emits
        # TWO kinds: a per-component finding that reads "... asks for N key(s) ...",
        # and a RATCHET finding ("translation coverage ROSE: ...") that names no
        # component and no count. Summing blindly over both crashed this summary
        # with an IndexError the moment the ratchet fired alone — the gate had
        # already printed its FAIL line correctly, and then died formatting the
        # sentence that says what to do about it. `run()` was never affected, so
        # the merge gate kept working and only a human running the file directly
        # ever saw it, which is why it survived. Split the two shapes and report
        # each in its own terms.
        component = [v for v in violations if "asks for " in v]
        ratchet = [v for v in violations if "asks for " not in v]
        if component:
            total = sum(int(v.split("asks for ")[1].split(" ")[0]) for v in component)
            print(
                f"\n{len(component)} component(s), {total} key(s). Each renders its own key name to a user. "
                "Add the keys to all eleven catalogues — G15 then keeps them in parity."
            )
        if ratchet:
            print(
                f"\n{len(ratchet)} ratchet finding(s). The absent-but-fallback debt may fall and never rise: "
                "either remove the newly absent keys or add them to all eleven catalogues. "
                "Do NOT raise the baseline to make this quiet."
            )
        return 1
    print("every literal and config-carried translation key resolves in en.json")
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ **THE DETAIL NAMES THE NUMBER IT MEASURED, NOT ITS RELATION TO A CEILING
    (DEF-2600, 2026-08-31).** It used to read *"absent-but-fallback debt is at
    or below its baseline of 558"* — true, and the same words whether the debt
    is 558 or zero, so a reader of the gates table could not see it fall and had
    no reason to lower the ceiling. This is the gate the 2026-08-27 decision-log
    entry names for having claimed *"19 components render raw translation keys"*
    when almost all rendered correct English through a fallback, which is exactly
    why its headline should carry its measurement.
    """
    violations, notes = check()
    if violations:
        return (
            "FAIL",
            f"{len(violations)} finding(s), the first being: {violations[0][:110]}",
        )
    covered = next(
        (n.split(" ")[0] for n in notes if n.endswith(f"baseline {COVERAGE_BASELINE})")),
        "?",
    )
    return "PASS", (
        f"no key renders raw to a user; {covered} absent key(s) carry a fallback and "
        f"render English (coverage debt, baseline {COVERAGE_BASELINE})"
    )


if __name__ == "__main__":
    raise SystemExit(main())
