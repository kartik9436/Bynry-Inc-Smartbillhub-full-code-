"""CR-199-BRC10 S4 — a published version's email FORMAT is frozen with its
body, held by the database (`notifications/0037`'s trigger).

A rich body read back as plain prints its markup as characters, so the format
is as much the document as the words: a version that left draft keeps the
layout it was sent in. Every case writes through the ORM's bulk `.update()`,
which calls no service function — the shape of a shell or a data migration.

POSTGRES ONLY, by `requires_postgres` (sqlite has no triggers).
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, transaction

from apps.notifications import template_models as tm
from apps.notifications import template_service

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

BODY = "Hello {first_name}\n\n[[Pay now|{pay_link}]]"


def _rich_draft(actor):
    template, _created = template_service.register(
        code="email_past_due",
        name="Past due",
        actor=actor,
        category=tm.VARIANT_DEFAULT,
        language=tm.VARIANT_DEFAULT,
    )
    return template_service.save_draft(
        template=template, body=BODY, actor=actor, body_format=tm.BODY_FORMAT_RICH
    )


@requires_postgres
def test_cr199__a_published_versions_format_cannot_be_changed(brazos, dana):
    with tenant_ctx(brazos):
        draft = _rich_draft(dana)
        template_service.publish(version_row=draft, actor=dana)
        with pytest.raises(DatabaseError, match="email format is frozen"):
            with transaction.atomic():
                tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).update(
                    body_format=tm.BODY_FORMAT_PLAIN
                )
        draft.refresh_from_db()
        assert draft.body_format == tm.BODY_FORMAT_RICH


@requires_postgres
def test_cr199__a_draft_may_still_change_format_and_a_bad_value_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        draft = _rich_draft(dana)
        tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).update(
            body_format=tm.BODY_FORMAT_PLAIN
        )
        draft.refresh_from_db()
        assert draft.body_format == tm.BODY_FORMAT_PLAIN
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).update(
                    body_format="html"
                )
