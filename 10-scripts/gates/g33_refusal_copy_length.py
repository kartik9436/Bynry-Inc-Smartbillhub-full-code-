#!/usr/bin/env python3
"""G33 — a refusal sentence a utility reads is SHORT.

WHY THIS GATE EXISTS (2026-08-19 · PO ruling `6baa846`)
--------------------------------------------------------
The PO was shown four real strings from our own product — the words a utility
saw on screen that week — and said *"all these messages should not be on screen
for user"*. Shown three replacements they said: **"these kind of messagesa re
okay; you need shorter sentences not long ones"**. Two halves, both binding: the
SHAPE was approved (plain, second person, says what to do next) and the
SENTENCES must be shorter.

THE RULE, AS A NUMBER A CHECK CAN HOLD
--------------------------------------
**No sentence over 6 words. At most two sentences per message.**

⚠ **SIX, NOT TWELVE — PO ruling 2026-08-30, verbatim:** *"Refusal copy is short
— your 12-word ruling - this shuld be 6 words only - not too long; this family
BORN ASPIRATIONAL it cannot be ASPIRATIONAL any more - there are so many bugs
becuase of this."* The twelve came from this gate's own 2026-08-19 measurement
(median longest sentence 9 words over the 271 messages of that day, rounded up).
The PO has now ruled the number down to six. Six is the rule from today and it
binds every NEW or CHANGED refusal.

⚠ **AND THE SECOND HALF OF THAT RULING IS WHY THE BASELINE FILE BELOW EXISTS.**
Re-measured on 2026-08-31 over all **850** English refusal messages this gate
walks:

    cap 12 (the old rule)   817 pass · 96%    33 to rewrite
    cap 10                  714 pass · 84%   136 to rewrite
    cap  8                  536 pass · 63%   314 to rewrite
    cap  6 (the ruling)     252 pass · 30%   598 to rewrite

Median longest sentence 8, 90th percentile 11, and not one message exceeds two
sentences. **Setting six with no baseline would take this gate from 96% passing
to 30% passing — a backlog of 598 wearing a gate's clothes**, which is exactly
the "BORN ASPIRATIONAL → NEVER GREEN" shape the same ruling forbids and the
2026-08-27 decision-log entry measures. So the 598 that already exist are named
one per line in `g33_refusal_copy_baseline.txt`, which may only SHRINK, and
every message that is new or whose English text CHANGES must be ≤6 words.
That gives all four properties at once: the PO's number is law from today · no
lane is blocked by prose it did not write · the gate is GREEN and therefore READ
· and the number can only fall. DEF-2606 carries the 598 as a tracked project.

⚠⚠ THE CLAUSE THAT MATTERS MORE AT SIX THAN IT DID AT TWELVE, AND IT IS PRINTED
IN THIS GATE'S OWN FAILURE OUTPUT RATHER THAN LEFT IN A DOCSTRING NOBODY OPENS
AT THE MOMENT OF THE MISTAKE:

    **SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION.
      TWO SENTENCES OF SIX BEAT ONE SENTENCE OF TWELVE.**

At twelve words a lane could keep both halves. At six the temptation is to cut
the sentence that says what to do next — which PASSES this gate and makes the
message useless, so nothing downstream can catch it.
*"A budget-level override needs a reason."* is six words and complete;
*"Enter one and we'll record it."* is six more and is the half a user acts on.
Cutting the second to reach six on a single sentence is the failure this gate
cannot see. `payments.as_of_required` is the model: keep *"Choose the day to
report on."*, drop the sentence about whose clock a business day belongs to.
Rationale belongs in the code comment beside the string.

ENGLISH ONLY, AND THAT IS THE RULING'S OWN WORDS
------------------------------------------------
*"It is a COPY rule, not a translation rule: the eleven locales follow their own
language's natural length, and a gate must count English only."* Counting words
in ja-JP or ko-KR by splitting on whitespace would be meaningless arithmetic
reported as a finding, which is how a gate earns a `noqa` instead of a fix.

⚠ But a message you SHORTEN is eleven files of work, not one: a shortened
English string with ten unshortened translations is the parity failure G15
watches. All eleven catalogues move together.

WHAT IT MEASURES
----------------
Every en.json value a REFUSAL resolves to — the same key set G32 walks, so the
two gates cannot disagree about what a refusal is. A catalogue entry no refusal
reaches (a label, a column heading, a page of help text) is not copy this rule
was written about and is not counted.

Sentence splitting is deliberately crude and deliberately GENEROUS: split on
`.`/`!`/`?` followed by whitespace, count whitespace-separated tokens, and treat
a `{{placeholder}}` as one word. A message that fails this counter is long by
any reading of it.

THE BASELINE FILE, AND WHY IT IS KEYED ON THE TEXT AND NOT ON THE KEY
---------------------------------------------------------------------
One line per baselined message: `<key> :: <the English text, whitespace
normalised>`. **The text is part of the identity on purpose.** The ruling binds
"every NEW or CHANGED refusal"; a baseline keyed on the KEY alone would let a
lane rewrite a message and keep it long forever, which is decoration rather than
a ratchet. Change the English and the line stops matching — the message is then
new copy and owes six words.

A baselined line whose message no longer exists or is now short is STALE: it is
reported as a note asking for its deletion, and it grants no licence to anything,
so the effective ceiling has already fallen.

⚠ `--list` PRINTS A REPORT, NOT THE BASELINE FORMAT, AND THAT IS DELIBERATE.
`python3 g33_refusal_copy_length.py --list > g33_refusal_copy_baseline.txt`
must not be a way to make this gate quiet, so `--list` emits a leading
`<n>w <n>s` column that no baseline line will ever match. Redirecting it makes
the gate LOUDER, not quieter. To retire a line you delete it; to add one you
have to mean it.

⚠ WHAT THIS GATE'S OWN SUMMARY USED TO CLAIM, AND DID NOT MEASURE (DEF-2609).
`main()` printed *"every refusal message is within N words / M sentences"* and
`run()` returned *"all within N words / M sentences"* on ANY run where the
violation count was at or under the baseline. With the baseline at 0 that was
true by accident. The moment a baseline holds 598 messages it is a false
sentence in the headline a reader trusts — the exact failure the 2026-08-27
decision-log entry records for four gates in this family. Both lines now say how
many are over the cap and how many are baselined, every time.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import g32_refusal_keys  # noqa: E402 — same directory, the shared key set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EN = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"

#: PO ruling 2026-08-30. Was 12 (PO ruling 2026-08-19). See the docstring.
MAX_WORDS_PER_SENTENCE = 6
MAX_SENTENCES = 2

#: The messages that were already over the cap when six became the rule.
#: 598 lines, measured 2026-08-31. It may only SHRINK. DEF-2606.
BASELINE = Path(__file__).resolve().parent / "g33_refusal_copy_baseline.txt"

#: Printed on every failure. It is here, and not only in the docstring, because
#: a lane reads a failure at the moment it is about to shorten a message — and
#: the wrong way to shorten one passes every check in this repo.
SHORTEN_RULE = (
    "SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION. "
    "Two sentences of six beat one sentence of twelve: the first says what is "
    "wrong, the second says what to do next, and cutting the second passes this "
    "gate and makes the message useless. Move the reason into the code comment "
    "beside the string. All eleven catalogues move together (G15)."
)

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])[\s ]+")
_PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


def sentences(value: str) -> list[str]:
    """The message as sentences, with placeholders collapsed to one token."""
    flattened = _PLACEHOLDER.sub("X", value).replace("…", ".")
    return [part.strip() for part in _SENTENCE_BREAK.split(flattened.strip()) if part.strip()]


def identity(key: str, value: str) -> str:
    """The baseline line for one message — key plus its whitespace-normalised
    English. The TEXT is part of the identity: change the copy and the licence
    lapses, because the ruling binds every new or CHANGED refusal."""
    return f"{key} :: {' '.join(value.split())}"


def measure(key: str, value: str) -> tuple[int, int] | None:
    """`(longest sentence in words, sentence count)`, or None for empty copy."""
    parts = sentences(value)
    if not parts:
        return None
    return max(len(part.split()) for part in parts), len(parts)


def over_cap(key: str, value: str) -> str | None:
    """The human-readable finding, or None when the message is within the cap."""
    measured = measure(key, value)
    if measured is None:
        return None
    longest, count = measured
    if count > MAX_SENTENCES:
        return f"{key}: {count} sentences (max {MAX_SENTENCES}) — {value[:70]}…"
    if longest > MAX_WORDS_PER_SENTENCE:
        return f"{key}: a {longest}-word sentence (max {MAX_WORDS_PER_SENTENCE}) — {value[:70]}…"
    return None


def refusal_messages() -> dict[str, str]:
    """Every en.json value a refusal resolves to — G32's key set, plurals included."""
    catalogue = json.loads(EN.read_text(encoding="utf-8"))
    raised = set(g32_refusal_keys.raised_keys())
    checked: dict[str, str] = {}
    for key in sorted(raised):
        if key in catalogue:
            checked[key] = catalogue[key]
            continue
        for suffix in g32_refusal_keys.PLURAL_SUFFIXES:
            if key + suffix in catalogue:
                checked[key + suffix] = catalogue[key + suffix]
    return checked


def baselined() -> set[str]:
    if not BASELINE.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def check() -> tuple[list[str], list[str], dict[str, int]]:
    """`(fresh findings, notes, counts)`.

    `fresh` is what FAILS: a message over the cap whose exact key-and-text is
    not in the baseline file. Everything the baseline holds is counted and
    reported, never hidden.
    """
    if not EN.is_file():
        return [f"{EN} is missing — the catalogue must exist"], [], {}
    checked = refusal_messages()
    known = baselined()

    fresh: list[str] = []
    over_ids: set[str] = set()
    for key, value in checked.items():
        finding = over_cap(key, value)
        if finding is None:
            continue
        line = identity(key, value)
        over_ids.add(line)
        if line not in known:
            fresh.append(finding)

    stale = sorted(known - over_ids)
    counts = {
        "measured": len(checked),
        "over": len(over_ids),
        "baselined": len(known),
        "fresh": len(fresh),
        "stale": len(stale),
    }
    notes = [
        f"{counts['measured']} English refusal message(s) measured (en.json only)",
        f"{counts['over']} over {MAX_WORDS_PER_SENTENCE} words or "
        f"{MAX_SENTENCES} sentences, of which {counts['baselined'] - counts['stale']} "
        f"are baselined in {BASELINE.name} (the file holds {counts['baselined']})",
    ]
    if stale:
        notes.append(
            f"{len(stale)} baselined message(s) are now short or gone — delete them "
            f"from {BASELINE.name} to tighten the ratchet: {stale[0][:90]}"
        )
    return sorted(fresh), notes, counts


def main() -> int:
    if "--list" in sys.argv:
        # ⚠ A REPORT, NOT THE BASELINE FORMAT. See the docstring: redirecting
        # this into the baseline file produces lines that match nothing, so the
        # gate gets LOUDER. That is the safety property, not an oversight.
        for key, value in sorted(refusal_messages().items()):
            measured = measure(key, value)
            if measured is None:
                continue
            longest, count = measured
            if longest > MAX_WORDS_PER_SENTENCE or count > MAX_SENTENCES:
                print(f"{longest}w {count}s  {identity(key, value)}")
        return 0

    fresh, notes, counts = check()
    for note in notes:
        print(f"note: {note}")
    for violation in fresh[:12]:
        print(f"FAIL: {violation}")
    if fresh:
        print(
            f"\n{len(fresh)} refusal message(s) are new or changed copy over "
            f"{MAX_WORDS_PER_SENTENCE} words "
            f"({counts['over']} over the cap in all, {counts['baselined']} baselined).\n"
            f"\n  ⚠ {SHORTEN_RULE}\n"
        )
        return 1
    print(
        f"no new or changed refusal exceeds {MAX_WORDS_PER_SENTENCE} words / "
        f"{MAX_SENTENCES} sentences; {counts['over']} of {counts['measured']} "
        f"message(s) are over the cap and baselined (DEF-2606)"
    )
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE DETAIL SAYS WHAT WAS MEASURED, INCLUDING ON A PASS. It used to claim
    "all within N words" whenever the count was at or under the baseline, which
    became a false sentence the moment the baseline stopped being zero
    (DEF-2609). The count over the cap is in the line on every run.
    """
    fresh, notes, counts = check()
    if not counts:
        return "FAIL", notes[0] if notes else "en.json is missing"
    tail = (
        f"{counts['over']}/{counts['measured']} over {MAX_WORDS_PER_SENTENCE} words, "
        f"{counts['baselined']} baselined"
    )
    if fresh:
        return "FAIL", (
            f"{len(fresh)} new or changed refusal(s) over {MAX_WORDS_PER_SENTENCE} "
            f"words ({tail}): {fresh[0][:90]} — shorten by deleting the RATIONALE, "
            "never the instruction"
        )
    if counts["stale"]:
        return "PASS", (
            f"no new or changed refusal over {MAX_WORDS_PER_SENTENCE} words; {tail}; "
            f"{counts['stale']} baselined line(s) now stale — delete them from "
            f"{BASELINE.name} to hold the gain"
        )
    return "PASS", f"no new or changed refusal over {MAX_WORDS_PER_SENTENCE} words; {tail}"


if __name__ == "__main__":
    raise SystemExit(main())
