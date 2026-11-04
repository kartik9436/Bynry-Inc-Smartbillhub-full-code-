# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 wave E task E9 · BR-NOT-026 (PO ruling 2026-08-30)
# Rules:    BR-NOT-026 (templates live in ONE PLACE and that place is the SCREEN
#           and the SERVICE, not the schema — both table pairs survive and no
#           row moves) · BR-NOT-025 (a version any sent document points at is
#           archived, never deleted — which is why `archived_at` has to exist on
#           BOTH sides) · BR-NOT-027 (a sent legal document is frozen as issued)
#           · BR-BIL-026 · BR-BIL-027 · CLAUDE.md hard rule 4
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**THE GUARD BR-NOT-026 NAMES: BOTH TABLE PAIRS ARE STILL THERE.**

The Product Owner ruled on 2026-08-30, verbatim: *"Yes, Go with option B; I
agree"* — one Templates screen and one draft→publish service over **two stores**.
No row moves. `notification_templates` + `notification_template_versions` keep
the authored words; `bill_templates` + `bill_template_versions` keep the layout
choice.

⚠ **WHY THIS FILE EXISTS AND WHY IT IS THE ONE THAT MATTERS.** The ruling's cost,
which the PO accepted with it, is that *"one place"* is now a promise about the
PRODUCT and not about the database — **so a future engineer opening the schema
finds two table pairs behind one screen and reads it as an unfinished merge.**
Finishing it is exactly the migration this ruling declined. Nothing else in this
repo would object: both pins are LOOSE COLUMNS and not foreign keys
(`invoices.template_id` / `.template_version` and `outbound_messages.template_id`
/ `.template_version` are a plain UUID and a plain integer), so a migration that
dropped the rows they name would raise no error and break no other test.

**This file is what goes red instead.**

⚠ **WHAT THE PIN IS FOR, STATED HERE BECAUSE COLLAPSING THE TWO JOBS IS HOW ONE
OF THEM GETS DELETED.** The pin answers *which wording was in force when we sent
this* — PROVENANCE. It is NOT the archive of what the customer actually read:
`BR-NOT-027` (PO 2026-08-30) rules that a sent legal document is FROZEN as issued
and that reproducing one by re-rendering from today's data is not correct, and
building that freeze is `CR-049`, not this task. The two rules answer different
questions and both are still required — a reader who folds them together will
drop one.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.billing import template_models as bill_tm
from apps.notifications import template_models as note_tm

pytestmark = pytest.mark.django_db

#: The four tables the ruling preserves, named as LITERAL STRINGS rather than
#: read off the models under test. A test that asks the model for its own
#: `db_table` and then asserts the answer equals itself would stay green through
#: a rename, which is one of the two ways the merge could be "finished".
NOTIFICATION_PAIR = ("notification_templates", "notification_template_versions")
BILL_PAIR = ("bill_templates", "bill_template_versions")


def test_br_not_026__both_table_pairs_exist_in_the_database():
    """The whole ruling, in one assertion a migration cannot talk its way past.

    If this goes red, read `BR-NOT-026` before "fixing" it: two template stores
    behind one screen is the DECISION, not a leftover.
    """
    present = set(connection.introspection.table_names())
    missing = [name for name in NOTIFICATION_PAIR + BILL_PAIR if name not in present]
    assert not missing, (
        f"{missing} is gone. BR-NOT-026 (PO 2026-08-30, 'Yes, Go with option B; I agree') "
        "keeps BOTH template table pairs — the merge is a SCREEN and a SERVICE, never a "
        "migration. Restore the table; do not finish the merge."
    )


def test_br_not_026__each_module_still_owns_its_own_pair():
    """No row moved, and neither did a model. Ownership is half the ruling.

    B2 §2 forbids cross-module writes, so `notification_templates` living in
    billing (or the reverse) would be the merge arriving by the back door even
    with four tables still standing.
    """
    assert note_tm.NotificationTemplate._meta.db_table == "notification_templates"
    assert note_tm.NotificationTemplateVersion._meta.db_table == "notification_template_versions"
    assert bill_tm.BillTemplate._meta.db_table == "bill_templates"
    assert bill_tm.BillTemplateVersion._meta.db_table == "bill_template_versions"
    assert note_tm.NotificationTemplate._meta.app_label == "notifications"
    assert bill_tm.BillTemplate._meta.app_label == "billing"


def test_br_not_026__the_two_content_models_stayed_apart():
    """One stores WORDS A PERSON TYPED; the other stores WHICH OF FIVE LAYOUTS.

    This is the half of the ruling a schema check alone would miss. Four tables
    could stand while somebody quietly added a `body` column to the bill side
    "so the editors can be shared" — and that is the same merge, paid for the
    same way: a column meaningless on one side of every row.
    """
    note_fields = {f.name for f in note_tm.NotificationTemplateVersion._meta.get_fields()}
    bill_fields = {f.name for f in bill_tm.BillTemplateVersion._meta.get_fields()}

    assert {"subject", "preheader", "body"} <= note_fields
    assert {"layout_key", "options"} <= bill_fields
    assert "body" not in bill_fields, (
        "a `body` column on bill_template_versions is the merge BR-NOT-026 declined. "
        "A bill version names one of five PLATFORM layouts and holds no authored text — "
        "see billing/template_models.py on why the absence of this column is what keeps "
        "an HTML rendering engine out of the deployment image."
    )
    assert "layout_key" not in note_fields


def test_br_not_025__both_sides_can_archive_a_version():
    """`archived_at` on BOTH pairs — the column E9 owed the billing side.

    BR-NOT-025: a version any sent document points at is ARCHIVED, never
    deleted. The notification side has carried `archived_at` since it was
    written; the bill side carried an archived STATUS and no timestamp, so
    *when* a layout stopped being offered could not be answered at all.
    """
    note_fields = {f.name for f in note_tm.NotificationTemplateVersion._meta.get_fields()}
    bill_fields = {f.name for f in bill_tm.BillTemplateVersion._meta.get_fields()}
    assert "archived_at" in note_fields
    assert "archived_at" in bill_fields, (
        "bill_template_versions has no archived_at. BR-NOT-025 requires archiving on BOTH "
        "sides of the unified Templates screen."
    )
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, "bill_template_versions"
            )
        }
    assert (
        "archived_at" in columns
    ), "the model declares archived_at and the table does not — the migration is missing."
