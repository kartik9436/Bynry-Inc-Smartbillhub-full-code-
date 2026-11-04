"""DEF-BIL-5339 — what `/budget-billing` serves for a clerk to read carries no id.

── Trace ──────────────────────────────────────────────
Defect:   DEF-BIL-5339 (rule ids, open-question ids and Python identifiers
          reached a clerk on the Budget Bills tab through two sites that
          printed the server's sentences unchanged)
Rules:    B14 rule 32 (no rule id or internal code in clerk-facing copy) ·
          rule 33 (rationale is ZERO words on screen; a fact is six words or
          fewer) · the 2026-08-19 ruling (DEF-322: a served sentence's words
          come from the catalogue entry for its `message_key`)
Gates:    G32 (every dict-literal `message_key` resolves) · G33 (six words a
          sentence on every NEW key) · G28 (three lines left its served-dict
          baseline with this fix)
───────────────────────────────────────────────────────

WHY A BACKEND TEST WHEN THE FRONT END HAS ONE
---------------------------------------------
`budgetBillsClerkCopy.dom.test.tsx` reads the RENDERED tab and fails on any id
in it — but it renders a FIXTURE, and a fixture is a copy of the server's
payload made on a day that has passed. This file pins the server side so the
two cannot drift apart: every gap entry carries a `message_key` that resolves
in `en.json`, its `detail` IS that English sentence, and neither holds an id or
a dotted identifier. Change a server sentence without the catalogue, or the
catalogue without the sentence, and this goes red; change either to carry an
id and it goes red.

⚠ THE SIBLING TEST IN `test_s253_budget_asks.py` COULD NOT COVER THIS. Its own
docstring said so on 2026-09-15 — *"the two `BUDGET_UNAVAILABLE` rows on the
sibling screen carry ids in `detail` and are another surface's defect"* — a
finding written in prose in the file the lane happened to be in, which is the
shape `CLAUDE.md` hard rule 4 names: nothing counted it until the Product
Owner photographed the screen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apps.billing import budget_api
from apps.billing.exceptions import BillingConfigError
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

EN = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales" / "en.json"

#: `CLAUDE.md`'s id grammar, with the load-bearing lookahead, plus a dotted
#: Python identifier (a segment carrying an underscore, or three segments).
INTERNAL_ID = re.compile(r"\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR|NFR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)")
DOTTED = re.compile(r"\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+\b")


def _internal_references(text: str) -> list[str]:
    found = INTERNAL_ID.findall(text)
    for run in DOTTED.findall(text):
        if "_" in run or run.count(".") >= 2:
            found.append(run)
    return found


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?]\s*", text) if s]


@pytest.fixture(scope="module")
def en_catalogue() -> dict[str, str]:
    return json.loads(EN.read_text(encoding="utf-8"))


GAPS = (*budget_api.BUDGET_UNAVAILABLE, budget_api.BUDGET_PARAMETERS_UNREADABLE)


@pytest.mark.parametrize("entry", GAPS, ids=[g["code"] for g in GAPS])
def test_gap_carries_a_key_that_resolves_and_detail_is_that_sentence(entry, en_catalogue):
    key = entry["message_key"]
    assert key in en_catalogue, f"{entry['code']}: {key} resolves to nothing — a clerk would read silence"
    assert entry["detail"] == en_catalogue[key], (
        f"{entry['code']}: `detail` and the `en` catalogue have drifted apart:\n"
        f"  detail: {entry['detail']!r}\n  en.json: {en_catalogue[key]!r}"
    )


@pytest.mark.parametrize("entry", GAPS, ids=[g["code"] for g in GAPS])
def test_no_id_or_identifier_in_what_a_clerk_reads(entry, en_catalogue):
    for field in ("detail", "message_key"):
        assert not _internal_references(entry[field].replace(entry["message_key"], "")), (
            f"{entry['code']}: an internal reference reached clerk-facing copy in {field}"
        )
    assert not _internal_references(en_catalogue[entry["message_key"]])
    # The rule is still there for support — on the machine field, by name.
    assert entry["br_ref"], f"{entry['code']} carries no br_ref"


@pytest.mark.parametrize("entry", GAPS, ids=[g["code"] for g in GAPS])
def test_each_sentence_is_six_words_or_fewer_and_at_most_two(entry):
    sentences = _sentences(entry["detail"])
    assert 1 <= len(sentences) <= 2, entry["detail"]
    for sentence in sentences:
        assert len(sentence.split()) <= 6, f"{entry['code']}: over rule 33's cap: {sentence!r}"


def test_enrollments_serve_the_keys_and_the_settings_gap_in_the_same_shape(brazos, dana, monkeypatch):
    """The wire, not the constant: `unavailable[]` carries the keys, and when
    the settings seam cannot read, `parameters_unavailable` is the SAME shape as
    a gap — never `str(BillingConfigError)`, which names a module path."""

    def unreadable():
        raise BillingConfigError(
            "apps.tenancy.selectors.settings_family is not published (BR-BIL-017)"
        )

    monkeypatch.setattr(budget_api.settings_seam, "budget_billing", unreadable)
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_enrollments, "get",
            f"/api/{brazos.subdomain}/budget-billing/enrollments",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    assert response.status_code == 200
    assert response.data["parameters"] is None
    absent = response.data["parameters_unavailable"]
    assert isinstance(absent, dict), absent
    assert set(absent) == {"code", "br_ref", "message_key", "detail"}
    assert absent["message_key"] == "billing.budget.gap.parametersUnreadable"
    assert not _internal_references(absent["detail"])
    served_keys = [g["message_key"] for g in response.data["unavailable"]]
    assert served_keys == [g["message_key"] for g in budget_api.BUDGET_UNAVAILABLE]
    for gap in response.data["unavailable"]:
        assert not _internal_references(gap["detail"]), gap["code"]
