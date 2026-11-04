# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10653 — Customer 360 › Write to customer › Already sent
#           named every message "A message": the
#           `notifications.templateClass.<code>` keys its WHAT column resolves
#           through existed for four classes out of eighty-seven
# Ruling:   PO 2026-10-29, D2 A — *"Customer 360 › Already sent names every
#           message type properly"*
# Rules:    B14 rule 31 (a code is never the visible value) · CLAUDE.md
#           hard-won law 2 (built is not wired — the honest fallback hid it)
# ───────────────────────────────────────────────────────
"""Every template class the platform catalogues has a NAME in every catalogue.

The column has an honest fallback (*"A message"*), so a missing key renders a
plausible word, `tsc` and every web test pass, and G15 compares the key sets
that EXIST — it cannot see a key a template string asks for and nobody wrote.
This test reads the source of truth, `catalogs.LISTINGS` (which carries every
class the rule catalogue sends), so a class added tomorrow without a name goes
RED here, naming it.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from apps.notifications import catalogs, rule_catalog

LOCALES = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
PREFIX = "notifications.templateClass."


def _catalogues() -> dict[str, dict[str, str]]:
    found = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in LOCALES.glob("*.json")}
    assert len(found) == 11, f"expected the eleven catalogues, found {sorted(found)}"
    return found


def test_every_rule_template_class_is_a_catalogue_listing():
    """The rule catalogue cannot send a class `LISTINGS` does not know — so
    `LISTINGS` is the whole list a WHAT cell can be asked to name."""
    sent = {code for event in rule_catalog.EVENTS for code in event.template_classes.values()}
    assert sorted(sent - set(catalogs.LISTINGS)) == []


@pytest.mark.parametrize("lang", sorted(path.stem for path in LOCALES.glob("*.json")))
def test_def_cus_10653_every_listing_has_a_name_in_every_catalogue(lang):
    """RED on the tip: 83 of 87 classes had no name in any catalogue."""
    catalogue = _catalogues()[lang]
    missing = sorted(code for code in catalogs.LISTINGS if PREFIX + code not in catalogue)
    assert missing == []
    blank = sorted(code for code in catalogs.LISTINGS if not str(catalogue[PREFIX + code]).strip())
    assert blank == []


def test_def_cus_10653_english_names_are_the_listing_names():
    """English reuses the listing's own human name (Settings › Templates) —
    adjusted only to US spelling and sentence case — so one class is never
    called two different things on two screens."""
    english = _catalogues()["en"]
    for code, listing in catalogs.LISTINGS.items():
        assert english[PREFIX + code].lower().replace("installment", "instalment") == (
            listing.name.lower()
        ), code
