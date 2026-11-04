#!/usr/bin/env python3
"""Fan a batch of message keys into all eleven locale catalogues at once.

WHY THIS IS IN THE REPO AND NOT IN A SCRATCHPAD
-----------------------------------------------
It has been written from scratch **three times**. The second copy carried this
line in its own docstring:

    ⚠ RECREATED 2026-08-25 — the original was lost from the scratchpad when the
    container restarted. The scratchpad is not durable; the repo is.

…and was then left in the scratchpad, where it was lost again the same day.
**A tool that knows why it keeps dying and stays where it dies is a note, not a
fix** (hard-won law 1). This is the third copy and it lives in `10-scripts/`.

WHAT IT GUARANTEES
------------------
1. **Parity or nothing.** G15 requires every catalogue to hold the same key set.
   A key missing ANY language is a failure here, before a byte is written — not
   a warning, and not eleven files left at ten different sizes.
2. **No silent overwrite.** An existing key raises unless it is named in
   `allow_overwrite`, so a lane cannot quietly re-word another lane's message.
3. **Nothing that is already there moves.** A fan-in of N keys changes exactly N
   lines in each catalogue; a retirement of N keys deletes exactly N lines. The
   tool edits the file's LINES and never re-serialises it (hard-won law 11: never
   round-trip a shared file through a serializer).
4. **All-or-nothing across the eleven.** Every catalogue is parsed and updated in
   memory first; a failure anywhere means no file is written.

⚠ **GUARANTEE 3 READ *"Catalogues are flat maps sorted by key, so the diff shows
the inserted lines and nothing else"* UNTIL 2026-10-21 (`DEF-GOV-10345`).** The
premise was false — the catalogues on the branch are NOT sorted, and nothing
keeps them so — and the tool sorted the whole file on every write. A 3-key
change became about 470 reordered lines in each of the eleven files, which is
the 1,967-hunk diff law 11 describes: unreadable, so the "read every hunk" check
cannot be performed, and two lanes worked around it by inserting keys by hand.
`10-scripts/tests/test_def_gov_10345_fanin_in_place.py` holds the line count.

WHERE A NEW KEY GOES (the placement rule, chosen 2026-10-21)
-----------------------------------------------------------
**Next to its prefix siblings.** A new key is inserted directly after the LAST
existing key that shares the most leading dot-segments with it (at least one),
so `billing.run.newThing` lands after the last `billing.run.*` line, or failing
that the last `billing.*` line. Keys of one batch are placed in batch order, so a
batch of new siblings stays together in the order it was written.
A key whose FIRST segment is new to the catalogue (a whole new area, such as
`field.*` on 2026-10-21) starts a new group immediately BEFORE the catalogue's
final run of same-area lines — i.e. it becomes the second-to-last group.
Siblings were chosen over "append at the end" because two lanes appending at the
end of the same file always collide in git, while two lanes adding to different
areas touch different places.

**Why never after the final entry:** the last line of a JSON object is the only
one without a trailing comma, so writing after it changes that line as well and
the diff is N + 1. Where the sibling anchor IS the final entry, the new key goes
directly above it instead, still among its siblings. The one unavoidable
exception is `retire` deleting the FINAL entry: the line above it must lose its
comma, so that retirement shows N deletions and one comma-only change.

The tool requires the format every catalogue has today — `{`, one
`  "key": "value"` entry per line, `}` — and refuses (writing nothing) a file in
any other shape, rather than guess.

USAGE
-----
    from i18n_fanin import apply
    apply({"module.some_key": {"en": "...", "de": "...", ...}})

or as a script, from a JSON file shaped `{key: {lang: text}}`:

    python3 10-scripts/i18n_fanin.py newkeys-<lane>.json

⚠ **A refusal message must also survive G33**, which caps a sentence at **SIX
words** — the Product Owner tightened it from twelve on 2026-08-30 (*"this
shuld be 6 words only - not too long"*). Count before you write; this tool does
not, because G33 already does and two checks that disagree are worse than one.

⚠ **THIS DOCSTRING SAID TWELVE UNTIL 2026-09-19 (`DEF-GOV-5792`), WHICH IS THE
SUPERSEDED NUMBER AND THE ONE A LANE IS MOST LIKELY TO REACH FOR.** It is the
same rot `DEF-RAT-5739` recorded one file over: a cap moved, the rule moved with
it, and every pointer that restated the old figure stayed where it was. A lane
measuring its copy against twelve under-reports by about three words per string
and reports a clean sweep over work that G33 will refuse at merge. **Read B14
rule 33's own status table; never a number restated in a tool's docstring,
including this one.**
"""

from __future__ import annotations

import json
import pathlib
import sys

LOCALES = pathlib.Path(__file__).resolve().parents[1] / "07-frontend" / "src" / "i18n" / "locales"

#: The eleven the product ships. Order is the catalogue order, not a preference.
LANGS = ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]


class _Catalogue:
    """One catalogue held as its LINES, so an edit touches only the lines it means to.

    `entries` is a list of `(key, text_without_trailing_comma)`; the opening `{`
    and closing `}` are re-emitted exactly as they were read. Every entry but the
    last gets its comma back on write, which reproduces the file byte for byte
    when nothing changed (proved in `__init__` before anything is edited).
    """

    def __init__(self, path: pathlib.Path):
        self.path = path
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not raw.endswith("}\n"):
            raise SystemExit(f"{path.name}: does not end in '}}\\n' — refusing to guess its format")
        lines = raw[:-1].split("\n")
        if lines[0] != "{" or lines[-1] != "}":
            raise SystemExit(f"{path.name}: not one '{{' line and one '}}' line — refusing to guess its format")
        self.entries: list[tuple[str, str]] = []
        for number, line in enumerate(lines[1:-1], start=2):
            body = line[:-1] if line.endswith(",") else line
            try:
                one = json.loads("{" + body + "}")
            except json.JSONDecodeError:
                raise SystemExit(f"{path.name}:{number}: not one entry per line — refusing to guess its format")
            if len(one) != 1:
                raise SystemExit(f"{path.name}:{number}: not one entry per line — refusing to guess its format")
            self.entries.append((next(iter(one)), body))
        if [k for k, _ in self.entries] != list(data):
            raise SystemExit(f"{path.name}: line keys disagree with the parsed object — refusing")
        if self.render() != raw:
            raise SystemExit(f"{path.name}: would not reproduce byte for byte — refusing")
        self.index = {key: i for i, (key, _) in enumerate(self.entries)}

    @staticmethod
    def _line(key: str, value: str) -> str:
        return "  " + json.dumps(key, ensure_ascii=False) + ": " + json.dumps(value, ensure_ascii=False)

    def _reindex(self) -> None:
        self.index = {key: i for i, (key, _) in enumerate(self.entries)}

    def _position_for(self, key: str) -> int:
        """Where a NEW key is inserted — the placement rule in the module docstring."""
        segments = key.split(".")
        best, anchor = 0, -1
        for i, (other, _) in enumerate(self.entries):
            theirs = other.split(".")
            shared = 0
            for a, b in zip(segments, theirs):
                if a != b:
                    break
                shared += 1
            if shared and shared >= best:
                best, anchor = shared, i
        last = len(self.entries) - 1
        if anchor >= 0:
            # After the sibling — but never after the final entry, whose line
            # carries no comma and would change too.
            return anchor + 1 if anchor < last else last
        if last < 0:
            return 0
        # A new area: before the final run of lines sharing the last entry's area.
        area = self.entries[last][0].split(".")[0]
        start = last
        while start > 0 and self.entries[start - 1][0].split(".")[0] == area:
            start -= 1
        return start if start > 0 else last

    def put(self, key: str, value: str) -> None:
        if key in self.index:
            self.entries[self.index[key]] = (key, self._line(key, value))
            return
        self.entries.insert(self._position_for(key), (key, self._line(key, value)))
        self._reindex()

    def drop(self, key: str) -> None:
        del self.entries[self.index[key]]
        self._reindex()

    def __contains__(self, key: str) -> bool:
        return key in self.index

    def __len__(self) -> int:
        return len(self.entries)

    def render(self) -> str:
        body = [text + ("," if i < len(self.entries) - 1 else "") for i, (_, text) in enumerate(self.entries)]
        return "\n".join(["{", *body, "}"]) + "\n"


def _write_all(staged: dict[str, _Catalogue]) -> int:
    sizes = {len(one) for one in staged.values()}
    if len(sizes) != 1:
        raise SystemExit(
            "PARITY BROKEN: catalogues would end at different sizes — "
            + str({lang: len(one) for lang, one in staged.items()})
        )
    rendered = {lang: one.render() for lang, one in staged.items()}
    for lang, text in rendered.items():
        json.loads(text)  # a malformed result is refused before any file is written
    for lang, text in rendered.items():
        (LOCALES / f"{lang}.json").write_text(text, encoding="utf-8")
    return sizes.pop()


def apply(batch: dict[str, dict[str, str]], *, allow_overwrite: tuple[str, ...] = ()) -> int:
    """Write every key of `batch` into all eleven catalogues. Returns the new size.

    A new key is INSERTED next to its siblings and an overwritten key is
    replaced on its own line; no other line of any catalogue changes.
    """
    for key, by_lang in batch.items():
        missing = [lang for lang in LANGS if lang not in by_lang]
        if missing:
            raise SystemExit(f"{key}: no value for {missing} — parity would break")
        empty = [lang for lang in LANGS if not str(by_lang[lang]).strip()]
        if empty:
            raise SystemExit(f"{key}: empty string for {empty} — an empty message is not a message")

    # Parse and update EVERYTHING before writing ANYTHING, so a refusal on the
    # eleventh catalogue cannot leave the first ten already changed.
    staged: dict[str, _Catalogue] = {}
    for lang in LANGS:
        catalogue = _Catalogue(LOCALES / f"{lang}.json")
        for key, by_lang in batch.items():
            if key in catalogue and key not in allow_overwrite:
                raise SystemExit(f"{key} already exists in {lang}.json — pass allow_overwrite")
            catalogue.put(key, by_lang[lang])
        staged[lang] = catalogue

    size = _write_all(staged)
    print(f"applied {len(batch)} key(s); every catalogue now holds {size}")
    return size



def retire(keys: list[str], *, allow_missing: bool = False) -> int:
    """Delete every key of `keys` from all eleven catalogues. Returns the new size.

    The mirror of `apply`, and it exists for the same reason: a retirement done
    by hand is eleven edits, and the tenth one is the one that gets forgotten —
    which G15 then reports as a parity break in a file nobody was editing.
    Each key's own line is deleted and no other line moves.

    ⚠ **A KEY WITH A LIVE CALL SITE MUST NOT BE RETIRED**, and this function
    cannot tell: it reads catalogues, not `src/`. Grep first. A catalogue entry
    BEATS a code `defaultValue`, so deleting a key that is still called does not
    fall back to the default the call site names — it prints the KEY.
    """
    missing_anywhere: dict[str, list[str]] = {}
    staged: dict[str, _Catalogue] = {}
    for lang in LANGS:
        catalogue = _Catalogue(LOCALES / f"{lang}.json")
        for key in keys:
            if key not in catalogue:
                missing_anywhere.setdefault(key, []).append(lang)
                continue
            catalogue.drop(key)
        staged[lang] = catalogue

    if missing_anywhere and not allow_missing:
        raise SystemExit(
            "not present to retire (pass allow_missing if that is expected): "
            + str(missing_anywhere)
        )

    size = _write_all(staged)
    print(f"retired {len(keys)} key(s); every catalogue now holds {size}")
    return size


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    batch = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    # A hand-off file may also carry a top-level "retire" list. It is drained
    # first so the rest of the file is read as key → language map, unchanged.
    retiring = batch.pop("retire", [])
    # Lane hand-off files carry metadata keys alongside the real ones; a key with
    # no language map is not a message and is skipped loudly, never silently.
    real = {k: v for k, v in batch.items() if isinstance(v, dict) and "en" in v}
    for skipped in sorted(set(batch) - set(real)):
        print(f"skipped (not a key → language map): {skipped}")
    if real:
        apply(real)
    if retiring:
        retire(list(retiring))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
