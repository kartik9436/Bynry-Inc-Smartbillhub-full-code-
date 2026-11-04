# ── Trace ──────────────────────────────────────────────
# Story:  `DEF-LED-6600` — the close checklist's SEVENTH item rendered its raw
#         code `unpaid_cost_accrual` to a clerk, on the live month-close screen,
#         from 2026-09-02 until 2026-09-24. Finance blueprint `P5.9`.
# Rules:  B14 rule 31 (nothing internal is ever visible — not a database id, not
#         an enum code) · B14 rule 32 (no internal code in clerk-facing copy) ·
#         CLAUDE.md hard-won law 2 (built is not wired) · hard-won law 7 (a
#         check must be able to fail, and on the thing it names)
# ───────────────────────────────────────────────────────
"""THE CHECKLIST'S WORDS EXIST FOR EVERY ITEM THE SERVER PUBLISHES.

WHY THIS TEST IS IN THE BACKEND AND NOT IN THE FRONT END
--------------------------------------------------------
**Because the thing that moves is here.** `apps/ledger/close.CHECKLIST_ITEMS`
gained a sixth item on 2026-09-02 and a seventh on the same day, and neither the
eleven catalogues nor the front end's fallback map moved with either. A test
living beside the catalogues would have to hard-code the list it expects, which
agrees with itself and says nothing the day an EIGHTH item lands — the exact
failure that produced the defect.

This reads the SERVER's own tuple and asks the catalogue about it, so the day a
lane appends `ITEM_SOMETHING_NEW` to `CHECKLIST_ITEMS` this goes red naming it,
in the same commit, before the row can reach a clerk as a word.

WHAT WOULD MAKE IT PASS WRONGLY — asked first, per law 7
--------------------------------------------------------
**(a) READING ONLY `en.json`.** A key present in English and missing in ten
languages is a BLANK SPACE on a real screen, which is worse than the code. So
every one of the eleven is read, and the test names which language is missing
what.

**(b) ASSERTING THE KEYS EXIST AND NOT THAT THEY SAY ANYTHING.** A catalogue
entry of `""` satisfies *the key is present* and renders nothing at all. Each
value is asserted non-empty.

**(c) ASSERTING AGAINST A LIST TYPED INTO THIS FILE.** That is the defect
again, one level up. The expected set is `close.CHECKLIST_ITEMS` itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.ledger import close

#: The eleven the product ships. Read from disk rather than typed, so a twelfth
#: language is covered the day it is added.
LOCALES = (
    Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
)


def _catalogues() -> dict[str, dict[str, str]]:
    files = sorted(LOCALES.glob("*.json"))
    assert len(files) >= 11, f"expected the eleven catalogues, found {len(files)}"
    return {one.stem: json.loads(one.read_text(encoding="utf-8")) for one in files}


def test_every_checklist_item_has_a_label_in_every_language() -> None:
    """`DEF-LED-6600`. The row label is a DYNAMIC i18next key
    (`finance.close.item.<code>`), so a missing entry is **not** a missing-key
    failure — i18next renders the key itself, and a clerk reads
    `unpaid_cost_accrual` on the month-close screen. `tsc`, every front-end test
    and every gate were green over it for three weeks.
    """
    catalogues = _catalogues()
    missing: list[str] = []
    for code in close.CHECKLIST_ITEMS:
        key = f"finance.close.item.{code}"
        for lang, catalogue in catalogues.items():
            if not str(catalogue.get(key, "")).strip():
                missing.append(f"{lang}:{key}")
    assert not missing, (
        "a checklist item with no catalogue entry renders its own CODE to a clerk "
        f"(B14 rules 31 and 32) — missing: {sorted(missing)}"
    )


def test_every_checklist_item_has_a_state_word_in_every_language() -> None:
    """The three states are a fixed set and the same trap applies to them:
    `finance.close.state.<state>` is interpolated the same way, so an
    unrecognised state would put `unknown` on screen as a bare English word in
    ten catalogues."""
    catalogues = _catalogues()
    missing: list[str] = []
    for state in (close.STATE_COMPLETE, close.STATE_INCOMPLETE, close.STATE_UNKNOWN):
        key = f"finance.close.state.{state}"
        for lang, catalogue in catalogues.items():
            if not str(catalogue.get(key, "")).strip():
                missing.append(f"{lang}:{key}")
    assert not missing, sorted(missing)


@pytest.mark.parametrize("code", close.CHECKLIST_ITEMS)
def test_every_unfinished_item_can_name_a_screen_that_clears_it(code: str) -> None:
    """`P5.9` — *"every unfinished item links to the screen that clears it"*
    (p068 item 4), which the blueprint calls *"the change that makes this
    usable"*.

    ⚠ **THIS ASSERTS THE DOOR'S LABEL EXISTS, NOT THAT THE DOOR OPENS.** Where
    the address goes is the front end's, and `CloseView.dom.test.tsx` asserts
    every one of them is a real tenant address rather than a protocol-relative
    one. What this catches is the half that has actually failed twice in this
    file's own subject: a row added on the server with no words anywhere.
    """
    catalogues = _catalogues()
    key = f"finance.close.fix.{code}"
    missing = [
        lang for lang, catalogue in catalogues.items()
        if not str(catalogue.get(key, "")).strip()
    ]
    assert not missing, (
        f"{code} has no door label in {sorted(missing)} — an unfinished row would "
        "draw a link with no words in it"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-LED-6600 · Finance blueprint p067–p069 (`P5.9`)
# generated: 2026-09-24 by lane FIN-P5
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a (no money math)
# gates: pytest tests/test_fin_p5_checklist_catalogue.py — PROVED RED FIRST by deleting `finance.close.item.unpaid_cost_accrual` from `en.json`, which is the exact state the product shipped in
# exceptions: (1) a BACKEND test reading FRONT-END files, deliberately — the thing that moves is `close.CHECKLIST_ITEMS` and a test on the other side would have to hard-code the list it expects, which is the defect one level up
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
