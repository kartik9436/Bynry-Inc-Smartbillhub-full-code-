# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 wave E task E9 · BR-NOT-026
# Rules:    BR-NOT-026 (one screen and one service, TWO stores) · BR-NOT-025
#           (archived, never deleted) · BR-BIL-026 · BR-BIL-027 · B2 §2
#           (cross-module writes are forbidden)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The one Templates list, and the docstring the ruling makes a deliverable.

**WHY A TEST READS A DOCSTRING, WHICH LOOKS ODD UNTIL YOU READ `BR-NOT-026`.**
The rule names the explanation as the thing that keeps the two stores alive:
*"the unified template SERVICE is the boundary that carries that fact and MUST
say so in its own docstring — otherwise the next lane reads two tables as an
unfinished merge and finishes it, which is exactly the migration this ruling
declined."* A paragraph nothing checks is a paragraph a tidy-up deletes, so the
four things it has to say are asserted here.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.billing import templates_service as bill_service
from apps.notifications import unified_templates as unified

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 30)


# ══ THE DOCSTRING BR-NOT-026 REQUIRES ═══════════════════════════════════════


def test_br_not_026__the_service_docstring_says_two_stores_is_the_decision():
    """Four facts, each one of them load-bearing for the next lane."""
    text = unified.__doc__ or ""
    assert "notification_templates" in text and "bill_templates" in text, (
        "the docstring must NAME both table pairs — a reader who cannot see which two "
        "stores are meant cannot tell the decision from a leftover."
    )
    assert "2026-08-30" in text, "the ruling's date, so the reader can go and read it."
    assert "BR-NOT-026" in text
    assert "declined" in text, (
        "it must say the migration was DECLINED, not merely that two tables exist. "
        "'There are two tables' reads as a confession; 'the merge was declined' reads "
        "as a decision, which is what it is."
    )


def test_br_not_026__the_two_editors_are_named_apart():
    """A unified LIST and a unified LIFECYCLE — never a unified editor."""
    assert unified.EDITOR_TEMPLATE_DETAIL != unified.EDITOR_LAYOUT_CHOOSER
    assert unified.CONTENT_AUTHORED_WORDS != unified.CONTENT_LAYOUT_CHOICE


# ══ THE ONE LIST ════════════════════════════════════════════════════════════


def test_br_not_026__one_call_lists_both_kinds(brazos, dana):
    """What a person can now do: open Templates ONCE and see everything."""
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        rows = unified.list_templates()

    kinds = {row.kind for row in rows}
    assert kinds == {
        unified.KIND_NOTIFICATION,
        unified.KIND_BILL,
    }, f"the one list must carry both kinds; it carried {kinds}"
    notes = [row for row in rows if row.kind == unified.KIND_NOTIFICATION]
    bills = [row for row in rows if row.kind == unified.KIND_BILL]
    assert len(notes) >= 30, "every notification class the platform sends is listed"
    assert len(bills) >= 1, "the tenant's seeded bill template is listed beside them"


def test_br_not_026__every_row_says_what_it_stores_and_which_editor_it_opens(brazos, dana):
    """The half a merged list would hide: one holds words, one holds a choice."""
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        rows = unified.list_templates()

    for row in rows:
        if row.kind == unified.KIND_NOTIFICATION:
            assert row.content_model == unified.CONTENT_AUTHORED_WORDS
            assert row.editor == unified.EDITOR_TEMPLATE_DETAIL
        else:
            assert row.content_model == unified.CONTENT_LAYOUT_CHOICE
            assert row.editor == unified.EDITOR_LAYOUT_CHOOSER


def test_the_list_filters_by_kind(brazos, dana):
    """*"filterable by kind"* — the one thing the two-panel screen could not do."""
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        only_bills = unified.list_templates(kind=unified.KIND_BILL)
        only_notes = unified.list_templates(kind=unified.KIND_NOTIFICATION)

    assert only_bills and {row.kind for row in only_bills} == {unified.KIND_BILL}
    assert only_notes and {row.kind for row in only_notes} == {unified.KIND_NOTIFICATION}


def test_an_unknown_kind_is_refused_by_name(brazos):
    """A third kind means a third STORE, not a third string. The refusal says so."""
    with tenant_ctx(brazos):
        with pytest.raises(unified.UnifiedTemplateRefused) as refusal:
            unified.list_templates(kind="statement")
    assert "not a template kind" in str(refusal.value)


# ══ THE ONE VERSION HISTORY ═════════════════════════════════════════════════


def test_version_history_speaks_one_vocabulary_over_the_bill_store(brazos, dana):
    """A bill version reads in the same shape a notification version does."""
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        bills = unified.list_templates(kind=unified.KIND_BILL)
        history = unified.version_history(kind=unified.KIND_BILL, key=bills[0].key)

    assert history, "a seeded tenant has a published bill version"
    first = history[0]
    assert first.version >= 1
    assert first.status in ("draft", "published", "archived")
    assert first.pinned_by == 0, "nothing has been issued in this test"


def test_archiving_a_bill_version_stamps_when(brazos, dana):
    """BR-NOT-025 on the side that could not answer *when* until task E9.

    The list is one list, so a person archiving a bill layout and a person
    archiving a disconnection notice must both be told the same thing about
    what happened. Before this column existed one of them got a blank.
    """
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        bills = unified.list_templates(kind=unified.KIND_BILL)
        key = bills[0].key
        version_row = bill_service.BillTemplateVersion.objects.get(
            tenant_id=brazos.id, template_id=key
        )
        unified.archive(kind=unified.KIND_BILL, version_row=version_row, actor=dana, on_date=TODAY)
        history = unified.version_history(kind=unified.KIND_BILL, key=key)

    archived = [row for row in history if row.status == "archived"]
    assert archived, "the version archived"
    assert (
        archived[0].archived_at is not None
    ), "archived_at was not stamped — BR-NOT-025 needs BOTH sides able to say when"
    assert archived[0].pinned_by == 0


def test_archive_is_not_delete(brazos, dana):
    """The whole of BR-NOT-025 in one assertion: the row is still there."""
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        bills = unified.list_templates(kind=unified.KIND_BILL)
        before = len(unified.version_history(kind=unified.KIND_BILL, key=bills[0].key))
        version_row = bill_service.BillTemplateVersion.objects.get(
            tenant_id=brazos.id, template_id=bills[0].key
        )
        unified.archive(kind=unified.KIND_BILL, version_row=version_row, actor=dana, on_date=TODAY)
        after = len(unified.version_history(kind=unified.KIND_BILL, key=bills[0].key))

    assert after == before, "archiving removed a version row — BR-NOT-025 forbids it"


# ══ THE CONTENT MODELS STAY APART ═══════════════════════════════════════════


def test_a_bill_draft_carrying_a_body_is_refused_in_words(brazos, dana):
    """The meaningless column, refused where it would have been introduced.

    BR-NOT-026 declined a schema with a `body` on the bill side. A `content`
    dict that accepted one would have re-introduced exactly that, in a place no
    migration guard looks.
    """
    with tenant_ctx(brazos):
        bill_service.seed_platform_default(on_date=TODAY, actor=dana)
        template = bill_service.tenant_fallback_template()
        with pytest.raises(unified.UnifiedTemplateRefused) as refusal:
            unified.save_draft(
                kind=unified.KIND_BILL,
                target=template,
                actor=dana,
                content={"layout_key": "standard-letter-v1", "body": "Dear customer"},
            )
    assert "no body text on this side" in str(refusal.value)


def test_a_notification_draft_carrying_a_layout_key_is_refused(brazos, dana):
    """And the mirror image, so neither store leaks into the other's shape."""
    with tenant_ctx(brazos):
        with pytest.raises(unified.UnifiedTemplateRefused) as refusal:
            unified.save_draft(
                kind=unified.KIND_NOTIFICATION,
                target=None,
                actor=dana,
                content={"body": "hello", "layout_key": "standard-letter-v1"},
            )
    assert "layout_key" in str(refusal.value)
