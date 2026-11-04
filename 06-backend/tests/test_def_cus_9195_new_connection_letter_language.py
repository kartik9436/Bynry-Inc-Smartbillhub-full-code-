# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9195 — the language chosen on New Connection step 1 was
#           saved on the owner's account and never used: every New Connection
#           letter went in the utility's language.
# Ruling:   decision log 2026-10-02, "SEVEN PO ANSWERS IN ONE MESSAGE", item 2:
#           *"A with the English fallback. She asked for Spanish. Today her
#           choice is saved but never used."* — supersedes `OQ-CUS-12619`
#           (*"(a) Portal only; emails in English."*) FOR NEW CONNECTION
#           LETTERS ONLY.
# Rules:    BR-NOT-006 (the pinning tuple includes the language variant) ·
#           BR-BIL-026 (a pinned row keeps its pin). ⊕ 2026-10-29 (PO option B):
#           this narrowing is now the rule for EVERY message, guarded by
#           test_cr199_messages_follow_the_customers_language.py.
# ───────────────────────────────────────────────────────
"""**Ana picks Español on step 1 at an English-speaking utility. Her *Build
confirmed* letter goes in Spanish; her quote letter, which the utility never
wrote in Spanish, goes in English.**

⚠ **THE DISCRIMINATING FIXTURE IS A PUBLISHED SPANISH VARIANT** — the argument
`test_cr199_messages_follow_the_customers_language` makes: without one, every letter resolves to the default
wording whatever is asked, and a case reading *"English"* passes over the old
code and the new alike. Only `new_connect_confirmed` gets one, so the quote
letter is the fallback in the same build.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
language the code ASKED for and never what was PINNED — case 1 reads the queue
row's own `template_language` and the build record's delivery, and the other
cases capture the language at the seam the queue is called through.

RED PROVED FIRST, against 2.466.0 (`_letter_language` returning the utility's
language): cases 1, 2 and 4 failed — the row pinned `default`, the preview and
the base-language case asked `en-US`, and the record carried no language.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.metering import connection_messages as step7
from apps.metering import connection_record as record
from apps.work import connection_models as work_tables
from apps.notifications import models as notification_models

from tests.test_cr199_messages_follow_the_customers_language import (
    _spanish_variant,
    _utility_language,
)
from tests.test_new_connect_step7_messages import _a_build
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CONFIRMED = "new_connect_confirmed"


def _ana(build, language):
    customers_models.Account.objects.filter(pk=build.owner_account_id).update(
        preferred_language=language
    )


def _preview_asks(monkeypatch):
    asked: dict[str, str | None] = {}

    def capture(**kwargs):
        asked[kwargs["template_code"]] = kwargs["language"]
        return {"available": True}

    monkeypatch.setattr(step7.seams, "connection_message_preview", capture)
    return asked


def test_anas_build_confirmed_letter_goes_in_spanish(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _spanish_variant(dana, CONFIRMED)
        build = _a_build(dana, brazos, "14 Idioma Lane")
        _ana(build, "es")
        sent = step7.send_now(dana, build, "build_created", channel="email")
        assert sent["state"] == step7.STATE_QUEUED
        row = notification_models.OutboundMessage.objects.get(
            source_type="connection",
            source_id=step7.occasion_source_id(build.id, "build_created"),
        )
        assert row.template_language == "es"
        # The Messages tab says which language it went in.
        build = work_tables.Connection.objects.get(pk=build.id)
        rows = record.build_record(build.id)["sections"]["communication"]["results"]
        confirmed = next(one for one in rows if one["code"] == "build_created")
        assert [d["language"] for d in confirmed["deliveries"]] == ["es"]


def test_a_letter_with_no_spanish_wording_falls_back_to_the_utilitys(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _spanish_variant(dana, CONFIRMED)
        build = _a_build(dana, brazos, "15 Idioma Lane")
        _ana(build, "es")
        asked = _preview_asks(monkeypatch)
        step7.preview(build, "build_created")
        step7.preview(build, "quote_and_what_is_owed")
    assert asked == {CONFIRMED: "es", "new_connect_quote": "en-US"}


def test_nothing_published_in_spanish_means_english(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        build = _a_build(dana, brazos, "16 Idioma Lane")
        _ana(build, "es")
        asked = _preview_asks(monkeypatch)
        step7.preview(build, "build_created")
    assert asked == {CONFIRMED: "en-US"}


def test_mexican_spanish_finds_the_spanish_wording(brazos, dana, monkeypatch):
    """A judgment (decision log 2026-10-02): `es-MX` is Spanish, so an `es`
    template is the language she asked for, not a fallback."""
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _spanish_variant(dana, CONFIRMED)
        build = _a_build(dana, brazos, "17 Idioma Lane")
        _ana(build, "es-MX")
        asked = _preview_asks(monkeypatch)
        step7.preview(build, "build_created")
    assert asked == {CONFIRMED: "es"}


def test_an_owner_who_stated_nothing_gets_the_utilitys_language(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _spanish_variant(dana, CONFIRMED)
        build = _a_build(dana, brazos, "18 Idioma Lane")
        _ana(build, None)
        asked = _preview_asks(monkeypatch)
        step7.preview(build, "build_created")
    assert asked == {CONFIRMED: "en-US"}
