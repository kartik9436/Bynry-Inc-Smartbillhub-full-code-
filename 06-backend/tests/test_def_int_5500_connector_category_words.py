# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-INT-5500 (2026-09-16) — the five ERP manifests introduced a new
#          category and no catalogue line was written, so `erp` reached a clerk
#          as the literal string `integrations.category.erp` on the filter chip
#          AND on the kicker of all five ERP cards. Measured on the running
#          build at 1440 before a line was changed: six occurrences.
# Rules:   B14 rule 31 (nothing internal is ever visible to a utility user) ·
#          B14 rule 32 (no rule id or internal code in clerk-facing copy) ·
#          BR-INT-037 (the chips are GENERATED from the registry — adding a
#          connector adds no React, which is exactly why nobody is prompted to
#          write the word)
# Screens: S8 (Settings → Integrations, CON-01)
# ───────────────────────────────────────────────────────
"""EVERY CATEGORY THE REGISTRY CAN EMIT MUST HAVE A WORD IN THE CATALOGUE.

WHY THIS TEST IS ON THE BACKEND, WHICH IS THE WHOLE POINT
---------------------------------------------------------
`REGISTRY.categories()` is GENERATED — its own docstring says the chips come
from it and are "never a typed list" — and that is the right design. It also
means **a new category arrives on a clerk's screen with nothing anywhere asking
whether anybody wrote the word for it.** Adding a connector is data, not code
(`BR-INT-037`), so there is no React diff for a reviewer to notice.

**Not one check in the repo could see it, and each one was telling the truth:**

  * `G15` asks whether the eleven catalogues hold the SAME key set. They did —
    the key was missing from all eleven equally.
  * `G27` resolves LITERAL ``t("some.key")`` call sites. The chip's key is
    BUILT — ``t(f"integrations.category.{key}")`` — so it is invisible to it.
  * `G18` treats a static stem, ``integrations.category.``, as covering every
    leaf beneath it, so `erp` was never reported missing.
  * `vitest` renders the grid over a fixture the TEST supplies, and every
    fixture named a category that happened to have a word.
  * i18next falls back to the KEY, so the string is genuinely in the DOM and
    every ``toContain`` assertion passes over it. **A missing key reaches a
    clerk as a machine word, not as an error.**

So the question is asked where the categories are DEFINED. This file reads
`REGISTRY.categories()` and the app's own `en.json`, and it fails the moment a
29th connector introduces a 12th category with no line — which is the point of
it. Fixing the one word would have left the next one to be found by the Product
Owner again.

**RED PROVED FIRST**, against the pre-fix catalogue read straight out of
``git show HEAD:07-frontend/src/i18n/locales/en.json``::

    RED  test_every_registry_category_has_a_word
         the connector category 'erp' has no word: integrations.category.erp
         is not in en.json — it would render as that string on the chip and on
         every ERP card's kicker

⚠ **ONE CASE WAS ALREADY GREEN AND IS RECORDED AS SUCH.**
``test_the_all_chip_has_its_own_word`` passed before this lane touched
anything: `integrations.category.all` has had copy since wave A. Saying so
matters — a case sitting beside one that went red reads as though it went red
too, and the next lane would take its green as proof of this lane's work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.integrations.registry import REGISTRY

CATALOGUE = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"

#: The eleven the product ships (`10-scripts/i18n_fanin.py` LANGS).
LOCALES = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
LANGS = ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]


@pytest.fixture(scope="module")
def copy() -> dict[str, str]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


def test_every_registry_category_has_a_word(copy: dict[str, str]) -> None:
    """The chip row and every card's kicker read `integrations.category.<key>`."""
    categories = REGISTRY.categories()
    # A guard against the check that cannot fail: an empty registry would make
    # every assertion below vacuously true and print a green over nothing.
    assert len(categories) >= 10, f"only {len(categories)} categories — is the registry loaded?"
    missing = [one for one in categories if f"integrations.category.{one}" not in copy]
    assert not missing, (
        "connector categories with no word: "
        + ", ".join(f"{one} (integrations.category.{one})" for one in missing)
        + " — each would render as that string on the chip and on every card's kicker"
    )


def test_every_registry_category_has_its_word_in_all_eleven(copy: dict[str, str]) -> None:
    """A word in `en` alone is a blank space on a real screen in ten languages."""
    short: dict[str, list[str]] = {}
    for lang in LANGS:
        data = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        for one in REGISTRY.categories():
            if f"integrations.category.{one}" not in data:
                short.setdefault(one, []).append(lang)
    assert not short, f"connector categories missing a word in some catalogues: {short}"


def test_the_all_chip_has_its_own_word(copy: dict[str, str]) -> None:
    """`all` is the chip row's own value and is not a registry category.

    ⚠ GREEN BEFORE THIS LANE EXISTED. It is here because the chip row is
    `[ALL, ...registry]` in the component, so a check that walked only the
    registry would leave the one chip nobody generated unguarded.
    """
    assert "integrations.category.all" in copy


def test_no_category_word_is_the_key_itself(copy: dict[str, str]) -> None:
    """A line written as its own key is the defect with a catalogue entry on it.

    A lane silencing the case above by writing
    ``"integrations.category.erp": "integrations.category.erp"`` would turn it
    green and change nothing on screen. This is the false pass, named and
    refused — the question law 7 says to ask of every check.
    """
    wrong = [
        one
        for one in REGISTRY.categories()
        if copy.get(f"integrations.category.{one}") == f"integrations.category.{one}"
    ]
    assert not wrong, f"category words that are just their own key: {wrong}"


# ── Lifecycle ──────────────────────────────────────────
# packet: DEF-INT-5500 (CR-110-BRC04)
# generated: 2026-09-16 by the CR-110 maintenance lane
# gates: proved RED against the pre-fix en.json in `pytest` — the harness that runs it
# status: VERIFIED-UNRATIFIED
# ───────────────────────────────────────────────────────
