#!/usr/bin/env python3
"""G129 — B14 rule 33's caps on the PREMISES and UNITS copy.

WHY THIS GATE EXISTS (DEF-MET-5836, 2026-09-19)
------------------------------------------------
B14 records rule 33 as **RATIFIED and NOT ENFORCED** for its five kinds. Only
the REFUSAL half has a gate, `G33`. Everything else — a field's help, an empty
state, a note beside a control, an absence paragraph — was capped by a rule that
nothing read.

Measured the day this was written, over `metering.premises*` and
`metering.units*` (744 strings): **218 breached the caps, 2,551 words in all**.
The longest was 47 words and argued a design decision to a reviewer on a live
screen. Every one of them passed `tsc`, every unit test and every tier-1 gate,
because **no gate in this repo reads rendered output** and no gate read the
catalogue for length either.

The Product Owner found it by looking at the screen — *"On premsies list page
reduce this text"* — which is the same instrument that found `DEF-712`,
`DEF-718`, `CR-092` and the nine defects of 2026-08-10.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT
----------------------------------------------------
It checks the ONE property a machine can decide: **how long a string is, in
sentences and in words per sentence.**

It does NOT decide whether a string is RATIONALE. Rule 33's zero-word kind is
*why the product works this way* — a judgment about whether a reader can ACT on
a sentence, and `G38`'s lesson applies exactly: *"Not the truth of the sentence
— no source-reading check can know that, and a gate that pretends to would be
worse than none."* Deleting rationale stays a human act; this gate stops the
length from growing back.

THE CAPS, FROM B14 RULE 33's OWN STATUS TABLE
----------------------------------------------
* a **LABEL or heading** (a name) ≤ **3 words**, and it is not a sentence;
* a **FACT** (a status, an age, a count qualifier, an audit line) ≤ **6 words**;
* an **INSTRUCTION** ≤ **6 words PER SENTENCE**, and *two sentences of six beat
  one sentence of twelve*;
* a **CONSEQUENCE** before an irreversible act ≤ **6 per sentence, at most two**,
  and **never cut below clarity**;
* **RATIONALE** = **ZERO words on screen**.

⚠ **THE FACT CAP IS MEASURED PER SENTENCE HERE, NOT IN TOTAL, AND THAT IS
DELIBERATE.** A first draft of this check capped a FACT at six words in TOTAL and
flagged *"The books could not be asked. This is not zero."* — copy rule 33
explicitly BLESSES, because the rule's own words are *two sentences of six beat
one sentence of twelve*. A check that refuses what the rule endorses would have
driven a lane to cut the second sentence, which is the exact failure the rule
names ("cutting the second passes this gate and makes the message useless"). So
the measurement is G33's, imported rather than copied: longest sentence in
words, and the sentence count.

⚠ **IT READS THE CATALOGUE, NOT THE SCREEN, AND IT PRINTS THE SIZE OF THAT BLIND
SPOT ON EVERY RUN.** A word count taken from `en.json` is not a word count of
the screen: a component that types its English out by hand is invisible here,
which is hard-won law 2's silent failure (`SignupWizard.tsx` types the eleven
services out by hand). Law 7's rule for this is that *a declared blind spot with
no NUMBER attached is indistinguishable from an empty one*, so the summary line
carries the count of prose-shaped literals found in the in-scope components
beside the count of catalogue strings measured.

⚠ **ENGLISH ONLY**, for G33's reason: B14 rule 35 says a catalogue is written in
its own language, so the ten others follow their own natural length and a word
count of them would be measuring the wrong thing.

THE BASELINE
------------
`g129_premises_units_copy_baseline.txt`, one line per string, `<key> :: <the
English text>`. **The text is part of the identity**, exactly as in G33: change
the copy and the licence lapses, so a lane cannot rewrite a message and keep it
long forever. **The file may only SHRINK.** A baselined line whose message is
now short or gone is reported as stale and grants no licence.

Born aspirational is born never-green and therefore never read (the 2026-08-27
decision-log entry, and G33's own docstring). So the strings still over the cap
on the day this landed are baselined, the gate is GREEN, and the number can only
fall.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import g33_refusal_copy_length as g33  # noqa: E402 — ONE sentence splitter, not two

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EN = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
COMPONENTS = REPO_ROOT / "07-frontend" / "src" / "features" / "metering"
BASELINE = Path(__file__).resolve().parent / "g129_premises_units_copy_baseline.txt"

#: The two key namespaces the premises and units screens draw from.
SCOPE = re.compile(r"^metering\.(premises|units)")

MAX_WORDS_PER_SENTENCE = g33.MAX_WORDS_PER_SENTENCE  # 6 — PO 2026-08-30
MAX_SENTENCES = g33.MAX_SENTENCES  # 2
MAX_LABEL_WORDS = 3  # B14 rule 33, the LABEL kind

#: A key whose leaf names a thing rather than says something. Rule 33's LABEL.
LABEL_LEAVES = (
    "label", "title", "heading", "tab", "col", "column", "legend",
    "kicker", "subtitle", "caption", "badge", "chip", "placeholder",
)

#: Leaves that are ACTIONS. B14 rule 4 gives these their own grammar
#: (`+ Noun`, `Verb →`, `Verb ✓`), so they are labels but carry a verb and a
#: glyph, and three words is the cap the rule intends for the NOUN.
ACTION_LEAVES = ("action", "cta", "button")

SHORTEN_RULE = (
    "SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION (B14 rule 33). "
    "Two sentences of six beat one sentence of twelve. Rationale — why the "
    "product works this way, why a control is absent — is ZERO words on screen: "
    "move it to the code's docstring and the register, which is what they are "
    "for. All eleven catalogues move together (G15), through "
    "10-scripts/i18n_fanin.py."
)

#: Prose-shaped literal text in JSX, for the blind-spot count only. A run of
#: three or more words between tags, ignoring props, entities and code.
_JSX_TEXT = re.compile(r">\s*([A-Z][a-z]+(?:\s+[a-z][A-Za-z'’-]+){2,}[.!?]?)\s*<")

#: A `t("some.key")` call, for the out-of-namespace half of the blind spot.
_T_CALL = re.compile(r"""\bt\(\s*["'`]([A-Za-z][\w.]*)["'`]""")


def is_label(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1].lower()
    return any(leaf == name or leaf.endswith(name.capitalize()) or leaf.endswith(name)
               for name in LABEL_LEAVES + ACTION_LEAVES)


def identity(key: str, value: str) -> str:
    """`<key> :: <whitespace-normalised English>` — the text is part of it."""
    return f"{key} :: {' '.join(value.split())}"


def over_cap(key: str, value: str) -> str | None:
    """The human-readable finding, or None when the string is within its cap."""
    parts = g33.sentences(value)
    if not parts:
        return None
    longest = max(len(part.split()) for part in parts)
    if is_label(key):
        words = len(" ".join(parts).split())
        if words > MAX_LABEL_WORDS:
            return f"{key}: a {words}-word label (max {MAX_LABEL_WORDS}) — {value[:70]}"
        return None
    if longest > MAX_WORDS_PER_SENTENCE:
        return f"{key}: a {longest}-word sentence (max {MAX_WORDS_PER_SENTENCE}) — {value[:70]}"
    if len(parts) > MAX_SENTENCES:
        return f"{key}: {len(parts)} sentences (max {MAX_SENTENCES}) — {value[:70]}"
    return None


def blind_spot() -> tuple[int, int]:
    """`(prose-shaped literals, out-of-namespace keys)` in the in-scope screens.

    This is the SIZE OF THE BLIND SPOT, never a failure. It is reported so that
    a green run cannot be read as *"the premises and units screens are within
    the cap"*, which is a stronger claim than this gate can make.

    TWO numbers, because there are two ways copy reaches these screens without
    passing under this gate:

    * a **prose-shaped literal** typed into the component by hand. That is
      hard-won law 2's silent failure — `SignupWizard.tsx` types the eleven
      services out this way — and nothing in `en.json` can see it.
    * a **key from another namespace**. These screens draw plenty of copy from
      `common.*`, `shell.*` and the rest, and `SCOPE` matches none of it, so a
      40-word sentence on the premises list is invisible here if its key begins
      with anything but `metering.premises` or `metering.units`.

    ⚠ **THE FIRST NUMBER IS 0 TODAY AND THAT IS A MEASUREMENT, NOT A BROKEN
    REGEX.** It was checked by hand when this gate was written: the only
    prose-shaped literals under `features/metering` are in test files and in
    comments, because the module is disciplined about `t()`. The second number
    is in the hundreds, which is why both are printed — a blind spot reported as
    a single 0 is indistinguishable from one nobody measured (law 7).
    """
    if not COMPONENTS.is_dir():
        return 0, 0
    literals = 0
    foreign: set[str] = set()
    for path in sorted(COMPONENTS.glob("*.tsx")):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        literals += len(_JSX_TEXT.findall(text))
        for key in _T_CALL.findall(text):
            if not SCOPE.match(key):
                foreign.add(key)
    return literals, len(foreign)


def load_baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def check() -> tuple[list[str], list[str], dict[str, int]]:
    if not EN.is_file():
        return [], [f"{EN} is missing"], {}
    catalogue = json.loads(EN.read_text(encoding="utf-8"))
    baseline = load_baseline()
    literals, foreign = blind_spot()

    fresh: list[str] = []
    seen: set[str] = set()
    measured = over = baselined = 0
    for key in sorted(catalogue):
        value = catalogue[key]
        if not SCOPE.match(key) or not isinstance(value, str) or not value.strip():
            continue
        measured += 1
        finding = over_cap(key, value)
        if finding is None:
            continue
        over += 1
        line = identity(key, value)
        seen.add(line)
        if line in baseline:
            baselined += 1
        else:
            fresh.append(finding)

    stale = sorted(baseline - seen)
    notes = [
        f"{measured} English premises/units string(s) measured (en.json only)",
        f"{over} over the cap, of which {baselined} are baselined in {BASELINE.name} "
        f"(the file holds {len(baseline)})",
        "BLIND SPOT: this reads the CATALOGUE, not the screen, and only the two "
        f"premises/units namespaces — {literals} prose-shaped literal(s) and "
        f"{foreign} key(s) from other namespaces are drawn by these screens and "
        "are NOT measured here",
    ]
    if stale:
        notes.append(
            f"{len(stale)} baselined line(s) now short or gone — delete them from "
            f"{BASELINE.name} to tighten the ratchet: {stale[0][:100]}"
        )
    return fresh, notes, {
        "measured": measured, "over": over, "baselined": baselined, "stale": len(stale),
        "literals": literals, "foreign": foreign,
    }


def main() -> int:
    fresh, notes, counts = check()
    for note in notes:
        print(f"note: {note}")
    if not counts:
        return 1
    for finding in fresh:
        print(f"FAIL: {finding}")
    if fresh:
        print(
            f"\n{len(fresh)} new or changed premises/units string(s) over B14 rule 33's "
            f"caps ({counts['over']} over in all, {counts['baselined']} baselined)."
        )
        print(f"\n  ⚠ {SHORTEN_RULE}")
        return 1
    print(
        f"no new or changed premises/units string exceeds rule 33's caps; "
        f"{counts['over']} of {counts['measured']} are over and baselined"
    )
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE DETAIL SAYS WHAT WAS MEASURED ON A PASS TOO, and it names the blind
    spot every time (DEF-2609's lesson, and law 7's *reporting zero over a scope
    it silently excludes*). A green line here means the CATALOGUE is within cap.
    It says nothing about a string typed into a component by hand.
    """
    fresh, notes, counts = check()
    if not counts:
        return "FAIL", notes[0] if notes else "en.json is missing"
    tail = (
        f"{counts['over']}/{counts['measured']} over rule 33's caps, "
        f"{counts['baselined']} baselined; catalogue only — "
        f"{counts['literals']} literal(s) and {counts['foreign']} foreign key(s) unmeasured"
    )
    if fresh:
        return "FAIL", (
            f"{len(fresh)} new or changed premises/units string(s) over cap "
            f"({tail}): {fresh[0][:90]} — shorten by deleting the RATIONALE, "
            "never the instruction"
        )
    if counts["stale"]:
        return "PASS", (
            f"no new or changed premises/units string over cap; {tail}; "
            f"{counts['stale']} baselined line(s) now stale — delete them from "
            f"{BASELINE.name} to hold the gain"
        )
    return "PASS", f"no new or changed premises/units string over cap; {tail}"


if __name__ == "__main__":
    raise SystemExit(main())
