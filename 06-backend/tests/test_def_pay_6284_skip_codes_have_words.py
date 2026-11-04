"""Every skip code the backend can EMIT reaches a clerk as words (DEF-PAY-6284).

── Trace ──────────────────────────────────────────────
Rules:  B14 rule 31 — no internal code is ever the visible value of a field.
        B14 rule 33 — a FACT is at most six words.
Defect: DEF-PAY-6284 (this file) · DEF-PAY-6281 (the same escape, hours earlier)
───────────────────────────────────────────────────────

WHY THIS TEST IS KEYED OFF THE EMITTERS AND NOT OFF THE RENDERER
----------------------------------------------------------------
`ladderSkipLabel` is `t("payments.skip." + reason)` and i18next returns THE KEY
ITSELF when it cannot resolve one. So a code with no catalogue entry renders as
`payments.skip.tier_already_sent` on screen — an internal code in front of a
clerk, at the moment the Send-notice wizard has just posted real letters.

**`G15` cannot see it.** G15 checks PARITY across the eleven catalogues, and a
key absent from all eleven is parity-perfect. That is exactly how it escaped
twice in one day: `DEF-PAY-6281` swept the codes `ladder.py` emits (eight, all
present) and `notices.py` — a different module reaching the same renderer —
still had two of its three missing.

**So the subject of this test is the set of codes the BACKEND CAN PRODUCE**,
read from the `SKIP_*` constants themselves. Checking the renderer finds the
codes you already thought of; checking the emitters finds the ones you did not.
A code added to either module with no catalogue entry fails here, by name.
"""

from __future__ import annotations

import json
import pathlib

import pytest

LOCALES = (
    pathlib.Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "i18n"
    / "locales"
)


def _emitted_skip_codes() -> dict[str, str]:
    """Every skip code, by the constant that defines it. Read from the modules,
    never from a hand-kept list — a list is the thing that goes stale."""
    from apps.payments import ladder, notices

    found: dict[str, str] = {}
    for module in (ladder, notices):
        for name in dir(module):
            if not name.startswith("SKIP_"):
                continue
            value = getattr(module, name)
            if isinstance(value, str):
                found[value] = f"{module.__name__.split('.')[-1]}.{name}"
    return found


def _flatten(obj, prefix: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _flatten(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, obj


def _catalogue(path: pathlib.Path) -> dict[str, str]:
    return dict(_flatten(json.loads(path.read_text(encoding="utf-8"))))


def test_the_emitters_are_found_at_all():
    """DEF-057's shape, and the reason it is here: every assertion below loops
    over this mapping, so a reflection bug that returned {} would make the whole
    file pass while checking nothing."""
    codes = _emitted_skip_codes()
    assert len(codes) >= 10, codes
    assert "tier_already_sent" in codes
    assert "collections_paused_by_active_plan" in codes
    assert "medical_hold" in codes


@pytest.mark.parametrize("path", sorted(LOCALES.glob("*.json")), ids=lambda p: p.stem)
def test_every_emitted_skip_code_has_words_in_every_catalogue(path):
    catalogue = _catalogue(path)
    missing = {
        code: origin
        for code, origin in sorted(_emitted_skip_codes().items())
        if f"payments.skip.{code}" not in catalogue
    }
    assert not missing, (
        f"{path.name}: these codes reach a clerk as a RAW KEY, because i18next "
        f"returns the key when it cannot resolve one — B14 rule 31. "
        f"Add them through 10-scripts/i18n_fanin.py, which writes all eleven at "
        f"once: {missing}"
    )


#: Skip wordings that were ALREADY over B14 rule 33's six-word cap for a fact
#: when this file was written, measured 2026-09-23 — `DEF-PAY-6285`. They are
#: named rather than tolerated silently, because a declared blind spot with no
#: NUMBER beside it is indistinguishable from an empty one (hard-won law 7's
#: fifth shape). **This set may only ever shrink**: the test below fails on any
#: code not in it, and fails again if one of these is fixed and left listed.
#: Not fixed here on purpose — they are live clerk-facing copy on another
#: lane's screen, and rewording shipped copy is that lane's call, not a
#: passing test's.
ALREADY_OVER_THE_CAP = {
    "below_ladder_floor": 7,
    "next_step_not_due": 7,
    "payment_plan_pause": 8,
}


def _longest_sentence(text: str) -> tuple[int, str]:
    parts = [s.strip() for s in text.replace("\u2014", ".").split(".") if s.strip()]
    return max(((len(s.split()), s) for s in parts), key=lambda pair: pair[0])


def test_english_skip_words_respect_the_six_word_cap():
    """B14 rule 33: a FACT is at most six words.

    A RATCHET, not a pass/fail on today's copy. It prints what it skipped
    beside what it checked, so the exemption cannot quietly grow."""
    catalogue = _catalogue(LOCALES / "en.json")
    over: dict[str, tuple[int, str]] = {}
    for code in sorted(_emitted_skip_codes()):
        text = catalogue.get(f"payments.skip.{code}")
        if text is None:
            continue  # the test above owns absence; this one owns length
        words, sentence = _longest_sentence(text)
        if words > 6:
            over[code] = (words, sentence)

    new_breaches = {c: v for c, v in over.items() if c not in ALREADY_OVER_THE_CAP}
    assert not new_breaches, (
        f"new wording over B14 rule 33's six-word cap for a fact: {new_breaches}. "
        f"Two sentences of six beat one sentence of twelve."
    )

    fixed = sorted(set(ALREADY_OVER_THE_CAP) - set(over))
    assert not fixed, (
        f"these were reworded and are now inside the cap — delete them from "
        f"ALREADY_OVER_THE_CAP so the exemption shrinks with the debt: {fixed}"
    )

    # The number, printed beside the check, so nobody reads silence as zero.
    print(
        f"skip wordings checked: {len(_emitted_skip_codes())} · "
        f"inside the cap: {len(_emitted_skip_codes()) - len(over)} · "
        f"grandfathered over it (DEF-PAY-6285): {sorted(over)}"
    )
