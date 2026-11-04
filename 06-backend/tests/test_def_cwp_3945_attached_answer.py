# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3945 — a clerk can pin a help answer to a screen and the
#           customer never sees it. `also_show_on_screen` is a column;
#           `SettingsPortalHelp.tsx` writes it with a picker and a summary
#           line; `published_content.attached_answer` reads it and its own
#           docstring names the placement; `AttachedAnswerCard` draws it. Every
#           end was built and NOTHING joined them.
# Rules:    US-CWP-071 §1 (ONE field, TWO placements — the utility writes the
#           answer once) · BR-CWP-093 (nothing empty ever appears) ·
#           BR-CWP-094 (a missing translation beats a missing answer) ·
#           G88 (apps/portal may reach published_content only through the
#           declared GUEST_READS) · CLAUDE.md hard-won law 2
# Tests:    this file
# Impacts:  apps/portal/seams/tenancy_seam.py `attached_answer` ·
#           apps/portal/selectors.py `arrears_position` · apps/portal/api.py
#           `account_arrears` · 07-frontend/src/portal/arrears/Overdue.tsx
# ───────────────────────────────────────────────────────
"""The chain a pinned answer travels, asserted at every link that was missing.

⚠ **THE FEATURE LOOKED FINISHED FROM BOTH ENDS, WHICH IS WHY IT SURVIVED.** The
clerk sets the field and gets a confirmation; the column holds the value; the
staff screen's tests pass because a clerk really can set it; the back end's
tests pass because `published_content.attached_answer` really does return the
answer. Nobody checked the customer's side, and `G13` could not: it asks
whether a component's props have callers, and `AttachedAnswerCard` had NO
callers at all, which is a different question. `G40` saw it only as a COUNT —
*unmounted components rose by 3* — beside a genuinely dead scaffolding
component, which is exactly how a real finding hides in a number.

**THREE LINKS WERE MISSING, NOT ONE**, and this file asserts each separately so
that breaking any one of them names itself:

  1. `apps/portal/seams/tenancy_seam.attached_answer` — the seam did not exist.
     Its neighbour `tip_for_screen` is the same shape one content type over and
     is what it was copied from.
  2. the field on a screen's payload — `arrears_position` now carries
     `attached_answer` for `CWP-057`.
  3. a caller for the card — asserted on the front end
     (`Overdue.dom.test.tsx`), because that is where the DOM is.
"""
from __future__ import annotations

from datetime import date

import pytest

from apps.portal import selectors
from apps.portal.seams import tenancy_seam
from apps.tenancy import published_content
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on


TODAY = date(2026, 9, 2)


def _publish_answer(tenant, actor, *, question: str, screen: str | None):
    """One PUBLISHED answer with a body, optionally pinned to `screen`.

    ⚠ **`create_answer` MAKES A DRAFT WHATEVER THE PAYLOAD SAYS** — law 3, in
    `published_content`'s own words: *the state that shows a customer something
    is the one you have to type*. So the publish is a second, deliberate call,
    and a fixture that skipped it would prove nothing: `attached_answer`
    filters on `status = published`, so an unpublished answer is `None` and
    every negative case below would pass for the wrong reason.
    """
    with tenant_context(tenant.id):
        created = published_content.create_answer(
            actor,
            tenant.id,
            {
                "question": question,
                "topic": "billing",
                "also_show_on_screen": screen,
                # ⚠ `variants` maps a locale to the BODY STRING itself, not to
                # a `{"body": …}` object — `_save_variants` does `(body or
                # "").strip()`. And the locale vocabulary is `LOCALES`, whose
                # English is `en` and NOT `en-US`.
                "variants": {"en": "A hot month means more water on the garden."},
            },
        )
        published_content.publish_answer(actor, tenant.id, created["slug"], status="published")
    return created


@pytest.mark.django_db
def test_the_seam_exists_at_all(pine_hill):
    """⚠ **LINK 1, AND THE ABSENCE WAS THE DEFECT.** `apps/portal/` could not
    reach `attached_answer` by any route; the read was correct and unreachable.
    """
    assert hasattr(tenancy_seam, "attached_answer")
    # `G88`: the portal seam may call NOTHING from `published_content` that is
    # not declared. If a lane ever removes this row the seam becomes a
    # cross-module read nobody reviewed.
    assert "attached_answer" in published_content.GUEST_READS


@pytest.mark.django_db
def test_an_answer_pinned_to_overdue_reaches_the_screens_payload(pine_hill, sarah):
    """Link 2 — the tick a clerk makes arrives on the customer's screen."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _publish_answer(pine_hill, sarah, question="Why is my bill higher?", screen="overdue")

    with tenant_context(pine_hill.id):
        body = selectors.arrears_position(account, as_of=TODAY)

    assert body["attached_answer"] is not None
    assert body["attached_answer"]["question"] == "Why is my bill higher?"
    # The BODY travels too — a question with no answer under it is the empty
    # card `BR-CWP-093` forbids.
    assert "body" in body["attached_answer"]
    # ⚠ **THE SLUG IS THE ADDRESS THE CARD LINKS TO** — a slug and never a
    # uuid, because B14 rule 31 makes a URL a visible value.
    assert body["attached_answer"]["slug"] == "why-is-my-bill-higher"


@pytest.mark.django_db
def test_an_answer_pinned_to_another_screen_does_not_leak_onto_this_one(pine_hill, sarah):
    """⚠ **THE ASSERTION THAT MAKES THE ONE ABOVE MEAN ANYTHING.** A reader that
    returned the first published answer regardless of the pin would pass every
    positive case and put the wrong answer under every screen."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _publish_answer(pine_hill, sarah, question="How do I read my meter?", screen="usage")

    with tenant_context(pine_hill.id):
        body = selectors.arrears_position(account, as_of=TODAY)

    assert body["attached_answer"] is None


@pytest.mark.django_db
def test_nothing_pinned_is_a_normal_answer_and_closes_the_slot(pine_hill, sarah):
    """`BR-CWP-093` — `None`, never an empty card headed with a question."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _publish_answer(pine_hill, sarah, question="An answer nobody pinned", screen=None)

    with tenant_context(pine_hill.id):
        body = selectors.arrears_position(account, as_of=TODAY)

    assert "attached_answer" in body, "the key is always present; the VALUE is the absence"
    assert body["attached_answer"] is None
