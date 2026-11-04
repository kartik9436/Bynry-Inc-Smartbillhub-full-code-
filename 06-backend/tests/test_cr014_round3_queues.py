# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 group 5 — the notification-queue cohorts (T5-23 · T7-16 ·
#           T7-17), the first in this CR whose COUNTS are the fixture: 340
#           accounts, 680 queued rows, a 2,000-row drop draining at 500.
# Defect:   DEF-577 (2026-08-22) — the `unit` number series stood at 102 while
#           units up to U-00420 existed, so the 340th unit creation raised
#           `duplicate key … (unit_no)=(U-00102) already exists`. The cohort
#           advances the counter through the S63 service (forward-only,
#           BR-TEN-035) and the defect is filed rather than papered over.
# Rules:    BR-NOT-009 (quiet hours, on the TENANT's clock) · BR-PAY-018 (the
#           `held` column is PAPER SUPPRESSION, not quiet hours) · BR-TEN-043
#           (the dispatch moment is a parameter, never a clock read) ·
#           CLAUDE.md rule 6 (a re-boot re-runs every seeder and writes nothing
#           twice — the source id is deterministic for exactly that reason).
# Red-proof: shown RED before green; the failures are quoted in the commit
#           message and the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""Three cohorts whose whole content is a NUMBER.

A journey about a dispatcher draining 2,000 rows at batch size 500 asserts four
hand-offs. Over twelve rows it asserts one, passes, and has proved nothing
about batching — which is DEF-108 with arithmetic instead of an empty table. So
these cases assert counts, and the builders refuse rather than round.

The subtler property is the one a reader is most likely to get wrong.
`outbound_messages.held` is **not** quiet hours: it is BR-PAY-018's paper
suppression, set when an account's address is known to be bad, and a held row
is skipped by every cycle until an address verification releases it. Quiet
hours leave a row `queued` and unheld, and `dispatcher._within_send_window`
declines to dispatch while the tenant's local clock is outside the window. A
fixture that read the journeys' phrase *"queued-and-held"* as the column would
have seeded 680 permanently-suppressed rows — and T7-16, whose whole subject is
moving the window and watching them go, would have been permanently false.
"""

from __future__ import annotations

import pytest

from tests import journey_cohort_fixtures as cohort
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_round3_queue__the_counts_are_exact(brazos, dana):
    """340 accounts × 3 channels = 1,020 rows, and the builder refuses otherwise.

    ⚠ **THIS SAID "2 channels = 680" UNTIL `DEF-2467` (2026-08-30), AND IT WAS THE
    LANE THAT MOVED THE RULE — MINE — THAT LEFT IT SAYING SO.** The journeys ask
    for email + SMS and still do; what changed is that `BR-NOT-024` was amended on
    2026-08-29, on the PO's ruling that print is the floor on every customer
    document rather than on bills alone, and this cohort's source kind is
    `notice`. So `queue_document` adds a third row per account.

    The count is now DERIVED from the floor (`cohort._queue_row_channels`) rather
    than multiplied by a typed 2 — the same fix `DEF-738` needed for tax classes,
    for the same reason: a second hand-copy of a rule is a rule that goes stale
    silently, and the copy is always the half nobody re-reads.
    """
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        result = cohort.ensure_reminder_queue_cohort(brazos, dana)
        rows = notification_models.OutboundMessage.objects.filter(
            tenant=brazos, source_type=cohort.QUEUE_SOURCE_TYPE
        ).count()

    assert result["accounts"] == cohort.QUEUE_ACCOUNT_COUNT
    assert rows == cohort.QUEUE_ACCOUNT_COUNT * len(cohort._queue_row_channels())
    assert result["rows"] == rows


def test_round3_queue__not_one_row_is_HELD(brazos, dana):
    """The distinction the whole cohort turns on.

    `held=True` is BR-PAY-018's paper suppression — a fact about a bad address,
    released only by an address verification. T7-16 moves the quiet-hours
    WINDOW, which releases nothing held. A held row here would make its central
    assertion permanently false while every count still looked right.
    """
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        cohort.ensure_reminder_queue_cohort(brazos, dana)
        held = notification_models.OutboundMessage.objects.filter(
            tenant=brazos, source_type=cohort.QUEUE_SOURCE_TYPE, held=True
        ).count()
        queued = notification_models.OutboundMessage.objects.filter(
            tenant=brazos,
            source_type=cohort.QUEUE_SOURCE_TYPE,
            status=notification_models.STATUS_QUEUED,
        ).count()

    assert held == 0
    assert queued == cohort.QUEUE_ACCOUNT_COUNT * len(cohort._queue_row_channels())


def test_round3_queue__email_is_addressed_and_sms_is_honestly_not(brazos, dana):
    """*"channels: email + SMS"* — and only one of them can be spoken to.

    `customers.selectors.delivery_recipients_for_account` answers SMS
    `recipient_not_resolvable` ALWAYS, because the mobile-consent column is
    PROPOSED-SCHEMA: nobody has asked these customers whether they consent to
    texts. The row count the journeys assert is exact and half of it is
    unaddressed BY A RULE. Inventing phone numbers to make the other half
    "work" would be seeding consent nobody gave.
    """
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        cohort.ensure_reminder_queue_cohort(brazos, dana)
        rows = notification_models.OutboundMessage.objects.filter(
            tenant=brazos, source_type=cohort.QUEUE_SOURCE_TYPE
        )
        email_addressed = rows.filter(channel="email", recipient_address__isnull=False).count()
        sms_addressed = rows.filter(channel="sms", recipient_address__isnull=False).count()
        # The print rows BR-NOT-024's floor adds are counted too, so this case
        # cannot pass by simply not looking at the third channel (`DEF-2467`).
        print_rows = rows.filter(channel="pdf_print").count()

    assert email_addressed == cohort.QUEUE_ACCOUNT_COUNT
    assert sms_addressed == 0
    assert print_rows == cohort.QUEUE_ACCOUNT_COUNT


def test_round3_queue__a_second_pass_queues_nothing_new(brazos, dana):
    """CLAUDE.md rule 6, and the reason the source id is deterministic.

    `outbound_messages` is unique on the source ref × channel. A random source
    id per pass would mint a SECOND full set of rows on every boot and the count
    both journeys assert would drift upward forever — silently, because more rows
    look like more work rather than like a broken fixture.
    """
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        first = cohort.ensure_reminder_queue_cohort(brazos, dana)
        second = cohort.ensure_reminder_queue_cohort(brazos, dana)
        rows = notification_models.OutboundMessage.objects.filter(
            tenant=brazos, source_type=cohort.QUEUE_SOURCE_TYPE
        ).count()

    assert first["rows"] == second["rows"] == rows


def test_round3_t7_17__two_thousand_rows_divide_into_four_handoffs(brazos, dana):
    """*"a bill-run drop of 2,000 queued email rows, dispatcher draining at
    batch size 500"* — and the DIVISION is the fixture.

    The journey changes the size to 200 *after the second hand-off*. A drop
    that fits in one batch has no second hand-off for anything to happen after,
    so the assertion would be unreachable and the run would still be green.
    """
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        result = cohort.ensure_dispatch_drop_cohort(brazos, dana)
        drop = notification_models.OutboundMessage.objects.filter(
            tenant=brazos, source_type="report", channel="email"
        )
        total = drop.count()
        addressed = drop.filter(recipient_address__isnull=False).count()

    assert total == cohort.T717_QUEUE_ROWS
    assert addressed == total, (
        "an unaddressed row is never claimed by a cycle, so an unaddressed drop drains in "
        "ZERO hand-offs and the batching this journey measures never happens"
    )
    assert result["batch_size"] == cohort.T717_BATCH_SIZE
    assert result["batches_at_seeded_size"] == 4
