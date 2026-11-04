# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave D — `DEF-CUS-5010`
# Screens:  S84 service request detail → Decision tab · Location & services tab
# Rules:    PO ruling 2026-08-19 (server `detail` text never reaches a screen —
#           a refusal's words come from its catalogue entry and nothing else) ·
#           B14 rule 32 (no internal code in clerk-facing copy) · B14 rule 33 /
#           G33 (a refusal is ≤6 words per sentence, at most two) · G15 (eleven
#           catalogues hold one key set)
# Defects:  DEF-CUS-5010
# ───────────────────────────────────────────────────────
"""Every catalogue key the service-request resolver can EMIT resolves to words.

WHY THIS TEST EXISTS, AND WHY IT IS AT THE RAISE SITE RATHER THAN IN A GATE
--------------------------------------------------------------------------
`DEF-CUS-5010`: eight keys this module mints were declared in **0 of the 11
catalogues**, so a clerk on the Decision tab read

    customers.serviceRequest.verdict.moveOut.noAccountHere

as **the reason a control was disabled** — measured in Chromium on
`SR-26-0006` and `SR-26-0004`, 2026-09-12, at `2.238.0`.

**Nothing in the repository could see it, and that is the point.** The keys are
built as f-strings from `_REASON_KEY` (`service_request.py:299`), so:

  * no front-end grep for a literal key finds one — the screen renders
    `props.t(verdict.message_key)`, a value off the wire;
  * **`G32` cannot see them either.** It reads `message_key=` keyword arguments
    and `{"message_key": "..."}` dict literals with `ast`. These are returned
    in a tuple from `_verdict_for`, so G32 reported **0 unresolved** —
    truthfully, of everything it can see. That is CLAUDE.md law 7's *reporting
    zero over a scope it silently excludes*, one layer further out than the
    instance that law already records;
  * and **`G33` walks G32's key set by construction** (*"so the two gates
    cannot disagree about what a refusal is"*), so the copy cap could not reach
    them either.

So the check is put where the keys are BORN: it drives `outcome_verdicts()`
over **every** evidence combination and reads the three `LOOKUP_*` constants,
which makes the key list exhaustive by construction rather than by a regex. A
ninth key cannot be minted in this module without this test finding it.

RED-FIRST PROOF (r11 step 2d · CLAUDE.md law 7)
-----------------------------------------------
Run against the tree BEFORE the catalogue lines were written — the same
`pytest` entry point that runs it green:

    FAILED test_every_emitted_key_resolves_in_english
    E   AssertionError: 8 key(s) the resolver emits resolve to NOTHING in
    E   en.json — a clerk reads the dotted key as the reason:
    E     customers.serviceRequest.lookup.noPremiseRecord
    E     customers.serviceRequest.lookup.servedAndOccupied
    E     customers.serviceRequest.lookup.servedAndVacant
    E     customers.serviceRequest.verdict.moveIn.servedAndVacant
    E     customers.serviceRequest.verdict.moveOut.noAccountHere
    E     customers.serviceRequest.verdict.newConnection.noPremiseRecord
    E     customers.serviceRequest.verdict.newConnection.premiseExists
    E     customers.serviceRequest.verdict.transfer.noLiveAccount
    FAILED test_every_emitted_key_is_in_all_eleven_catalogues
    E   AssertionError: parity broken for 8 key(s) ...
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

from apps.customers import service_request as rules
from apps.customers import service_request_service as sr

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCALES = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales"

#: G15's eleven, in catalogue order.
LANGS = ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]

#: G33's cap, PO ruling 2026-08-30. Duplicated here rather than imported
#: because G33 lives in `10-scripts/` and this suite must not reach into it;
#: the numbers are asserted against the gate's own constants by nothing, which
#: is why they are written with the ruling's date beside them.
MAX_WORDS_PER_SENTENCE = 6
MAX_SENTENCES = 2


def _every_emitted_key() -> set[str]:
    """Every key this module can put on the wire.

    EXHAUSTIVE BY CONSTRUCTION rather than by a pattern: the verdict half is
    read out of `outcome_verdicts()` over the full cartesian product of the
    evidence fields it branches on, and the lookup half is the three published
    constants. A new branch that mints a new key is covered the moment it
    exists — which a grep for `f"{_REASON_KEY}..."` would not be.
    """
    keys: set[str] = {sr.LOOKUP_NO_PREMISE, sr.LOOKUP_SERVED_VACANT, sr.LOOKUP_SERVED_OCCUPIED}
    kinds = ["unresolved", "no_premise", "served_vacant", "served_occupied"]
    flags = itertools.product([False, True], repeat=4)
    for kind, (premise, served, vacant, holds_here) in itertools.product(kinds, flags):
        for anywhere in (False, True):
            evidence = rules.Evidence(
                resolution_kind=kind,
                premise_exists=premise,
                unit_is_served=served,
                unit_is_vacant=vacant,
                applicant_holds_account_here=holds_here,
                applicant_holds_live_account_anywhere=anywhere,
            )
            for row in rules.outcome_verdicts(evidence):
                if row["message_key"] is not None:
                    keys.add(row["message_key"])
    return keys


def _catalogue(lang: str) -> dict[str, str]:
    return json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))


def test_the_key_list_is_the_seven_this_resolver_can_still_emit() -> None:
    """A count, so an eighth key arriving is VISIBLE rather than merely covered.

    `DEF-CUS-5010` counted eight. If this number moves UP, the lane that moved
    it owes eleven catalogue lines and should be told so here rather than by a
    clerk reading a dotted key.

    ⛔ **IT WAS EIGHT UNTIL 2026-09-21 AND IS SEVEN — `DEF-CUS-6109`.**
    `customers.serviceRequest.verdict.newConnection.premiseExists` is no longer
    EMITTED by anything: the verdict it carried — *"There is already a premise
    record at this address"* — was withdrawn when **Accounts blueprint p089,
    read as an image, was found to draw `A new connection` LIVE on a request
    whose address matched `PR-0731 · exact`.** An existing property with no
    service is an ordinary new connection.

    ⚠ **THE KEY STAYS IN ALL ELEVEN CATALOGUES AND THAT IS NOT AN OVERSIGHT.**
    This file's job is that every key the resolver CAN emit resolves to words;
    a catalogue entry nothing emits renders to nobody and is `G18`'s question,
    not this one. Deleting eleven lines to satisfy a count here would be a
    shared-file edit across eleven catalogues for no reader's benefit.
    """
    keys = _every_emitted_key()
    assert len(keys) == 7, f"the resolver now emits {len(keys)} keys, not 7: {sorted(keys)}"
    assert "customers.serviceRequest.verdict.newConnection.premiseExists" not in keys


def test_every_emitted_key_resolves_in_english() -> None:
    en = _catalogue("en")
    missing = sorted(key for key in _every_emitted_key() if key not in en)
    assert not missing, (
        f"{len(missing)} key(s) the resolver emits resolve to NOTHING in en.json — "
        "a clerk reads the dotted key as the reason:\n  " + "\n  ".join(missing)
    )


def test_every_emitted_key_is_in_all_eleven_catalogues() -> None:
    """G15's parity, asked of this module's own keys.

    English alone is not the fix: a key present in `en.json` and absent from
    `hi.json` renders the dotted key to a Hindi-speaking clerk and to nobody
    else, which is the hardest version of this defect to find.
    """
    keys = _every_emitted_key()
    broken: dict[str, list[str]] = {}
    for lang in LANGS:
        catalogue = _catalogue(lang)
        absent = sorted(key for key in keys if key not in catalogue)
        if absent:
            broken[lang] = absent
    assert not broken, f"parity broken for these keys: {broken}"


def test_the_english_copy_is_within_the_refusal_cap() -> None:
    """B14 rule 33 / G33 — and it is asserted HERE because G33 cannot see these.

    G33 walks G32's key set, and G32 cannot read an f-string key. So the cap
    that binds every new refusal string would not have bound these eight, which
    is exactly how a message ships at fifteen words. Six words per sentence, at
    most two sentences, measured the way G33 measures it.
    """
    en = _catalogue("en")
    over: list[str] = []
    for key in sorted(_every_emitted_key()):
        raw = en.get(key)
        if raw is None:
            # Absence is the test above's finding, and reporting it twice as a
            # KeyError traceback would bury the readable failure under a crash.
            continue
        text = " ".join(raw.split())
        sentences = [one for one in re.split(r"(?<=[.!?])\s+", text) if one]
        if len(sentences) > MAX_SENTENCES:
            over.append(f"{key}: {len(sentences)} sentences — {text!r}")
        for sentence in sentences:
            words = len(sentence.split())
            if words > MAX_WORDS_PER_SENTENCE:
                over.append(f"{key}: {words} words in one sentence — {sentence!r}")
    assert not over, "SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION:\n  " + "\n  ".join(
        over
    )


def test_no_catalogue_line_is_an_internal_code() -> None:
    """B14 rule 32 — no rule id or internal code in clerk-facing copy.

    The defect's own shape, asserted in the other direction: a lane that
    "fixed" parity by writing the key as its own value would satisfy every
    check above and change nothing a clerk reads.
    """
    keys = _every_emitted_key()
    echoed: list[str] = []
    for lang in LANGS:
        catalogue = _catalogue(lang)
        for key in sorted(keys):
            value = catalogue.get(key, "")
            if value == key or "customers.serviceRequest." in value:
                echoed.append(f"{lang}: {key}")
    assert not echoed, "a catalogue line that IS its own key is not a sentence:\n  " + "\n  ".join(
        echoed
    )
