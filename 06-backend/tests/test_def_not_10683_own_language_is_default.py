# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-NOT-10683 — a utility's edits to its own-language wording never
#          reached its customers: the queue asks for the utility's tag
#          (`en-US`), and resolution found the platform's SEEDED `en-US` variant
#          before the `default` variant the Templates screen edits.
# Rules:   BR-BIL-025 (resolution order) · CR-199-BRC10 PO ruling B · lane
#          TPL-SRV-VAR's `normalise_language` (the utility's tag IS `default`)
# ───────────────────────────────────────────────────────
"""The utility's own language tag resolves to the `default` variant once a
person has published it; while both rows are the platform's seed the literal
row is kept (lane TPL-SRV-LANG judgment 3)."""

from __future__ import annotations

import pytest

from apps.notifications import template_models as tm
from apps.notifications import template_service

from tests.test_cr199_messages_follow_the_customers_language import _utility_language
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CODE = "email_bill_ready"


def _seeded_own_language_variant(admin, language):
    """A published `language` variant nobody is on record for — the shape the
    platform's language seeder plants (`created_by` NULL)."""
    default = template_service.resolve(code=CODE)
    pinned = template_service.load_pinned(template_id=default.template_id, version=default.version)
    row, _created = template_service.register(code=CODE, name=language, actor=admin, language=language)
    draft = template_service.save_draft(
        template=row, body=f"SEED. {pinned.body}", subject=pinned.subject, actor=admin
    )
    tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).update(created_by=None)
    draft.refresh_from_db()
    template_service.publish(version_row=draft, actor=admin)
    return row


def _body(resolved):
    return template_service.load_pinned(
        template_id=resolved.template_id, version=resolved.version
    ).body


def test_the_utilitys_own_tag_pins_the_default_a_person_published(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        seeded = _seeded_own_language_variant(dana, "en-US")
        default = template_service.resolve(code=CODE)
        pinned = template_service.load_pinned(template_id=default.template_id, version=default.version)
        draft = template_service.save_draft(
            template=tm.NotificationTemplate.objects.get(pk=default.template_id),
            body=f"EDITED. {pinned.body}",
            subject=pinned.subject,
            actor=dana,
        )
        template_service.publish(version_row=draft, actor=dana)

        resolved = template_service.resolve(code=CODE, language="en-US")
        assert resolved.template_id == default.template_id
        assert resolved.template_id != seeded.pk
        # The pin keeps the utility's tag: money and dates format by it
        # ("$247.30", not "247.30 USD").
        assert resolved.language == "en-US"
        assert _body(resolved).startswith("EDITED.")


def test_while_the_default_is_still_the_seed_the_literal_row_is_kept(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        default = template_service.resolve(code=CODE)
        live = tm.NotificationTemplateVersion.objects.get(
            template_id=default.template_id, version=default.version
        )
        if live.created_by is not None:
            pytest.skip("this fixture's default wording carries an author; the seed case needs none")
        seeded = _seeded_own_language_variant(dana, "en-US")
        resolved = template_service.resolve(code=CODE, language="en-US")
        assert resolved.template_id == seeded.pk
        assert _body(resolved).startswith("SEED.")
