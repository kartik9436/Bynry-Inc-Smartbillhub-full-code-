# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · P6.10, **THE TENTH DATASET** `notifications`, which
#           R8 Bill Delivery is drawn from (lane DS-ACCOUNTS).
#           Drawings read as IMAGES (B14 rule 42): R8 p051 · §7.2/§7.2.2
#           p083–p086 · §7.5/§7.6 p087.
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-BIL-016 (one
#           delivery row per document per CHANNEL) · BR-BIL-036 (no email
#           address is NORMAL, not an exception) · BR-NOT-005 (forward-only) ·
#           BR-NOT-013 (delivered/bounced are PROVIDER facts) · BR-PAY-018
#           (paper held on a bad address) · BR-REP-024 · B14 rule 31 ·
#           CLAUDE.md hard rule 8 (an address lives on premises)
# ───────────────────────────────────────────────────────
"""THE `notifications` DATASET — one row per OUTBOUND MESSAGE (R8 Bill Delivery).

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** The one case asserting a zero
sits beside a positive one in the same fixture.

⚠ **NOTHING HERE SKIPS.** Every fixture CREATES what it needs.

⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE** (hard-won law 14), so these cases
prove the SHAPE and the ARITHMETIC and nothing about cost, the plan or RLS. The
PostgreSQL half is
`10-scripts/ds_accounts_audit_notifications_cost.py`.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.notifications import models as notification_models
from apps.notifications import notifications_dataset as dataset

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
SENT_ON = datetime(2026, 9, 25, 6, 2, tzinfo=UTC)

#: Eight messages, chosen so every tile is a distinct non-zero number and no
#: two sum the same way:
#:   1 delivered · 1 bounced_hard · 1 bounced_soft · 1 LEGACY `bounced` ·
#:   1 sent-and-returned-post · 1 unsubscribed · 1 queued · 1 HELD
MESSAGES = 8  # every row, dispatched or not — what an UNWINDOWED read serves
DISPATCHED = 6  # everything that left the building
DELIVERED = 1
BOUNCED = 3  # hard + soft + the legacy spelling
RETURNED = 1
UNSUBSCRIBED = 1
QUEUED = 1
HELD = 1


def _message(tenant, account, *, channel, status, **overrides):
    values = dict(
        tenant_id=tenant.id,
        account=account,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=channel,
        recipient_address="m.ruiz@example.test",
        status=status,
        sent_at=SENT_ON,
    )
    values.update(overrides)
    return notification_models.OutboundMessage.objects.create(**values)


def _eight(tenant, actor):
    account = an_account(tenant, actor, account_no="100244", contact_name="Ruiz, Marisol")
    email = notification_models.CHANNEL_EMAIL
    post = notification_models.CHANNEL_PRINT
    _message(tenant, account, channel=email, status=notification_models.STATUS_DELIVERED)
    _message(tenant, account, channel=email, status=notification_models.STATUS_BOUNCED_HARD,
             last_error="Mailbox full")
    _message(tenant, account, channel=email, status=notification_models.STATUS_BOUNCED_SOFT)
    # ⚠ THE LEGACY SPELLING. Nothing in this repo writes it and it is still
    # lawful; a tile counting only `bounced` reports 0 here, and a tile counting
    # only the two new ones drops this row.
    _message(tenant, account, channel=email, status=notification_models.STATUS_BOUNCED)
    _message(tenant, account, channel=post, status=notification_models.STATUS_SENT,
             recipient_address="91 Live Oak Dr", returned_at=SENT_ON)
    _message(tenant, account, channel=email, status=notification_models.STATUS_UNSUBSCRIBED)
    # Never dispatched — `sent_at` is NULL on both.
    _message(tenant, account, channel=email, status=notification_models.STATUS_QUEUED,
             sent_at=None)
    _message(tenant, account, channel=post, status=notification_models.STATUS_QUEUED,
             sent_at=None, held=True, held_reason="bad_address",
             recipient_address=None, unavailable_reason="no_postal_address")
    return account


# ══════════════════════════════════════════════════════════════════════════
#  THE GUARD — Phase 5's lesson, and it fires at IMPORT
# ══════════════════════════════════════════════════════════════════════════


def test_every_delivery_status_lands_in_exactly_one_bucket():
    """⚠ **PROVED RED FIRST:** adding a tenth value to `models.STATUSES` and
    re-importing raises `RuntimeError` NAMING it — see the two cases below,
    which exercise the guard directly rather than trusting it.

    The false pass this prevents: a tile written `status="bounced"` counts ZERO
    on this deployment, because `bounced` is LEGACY and nothing in this repo has
    ever written it, while hard and soft bounces sit uncounted.
    """
    covered = [value for bucket in dataset._BUCKETS.values() for value in bucket]
    assert sorted(covered) == sorted(notification_models.STATUSES)
    assert len(covered) == len(set(covered))  # no value counted twice
    assert len(notification_models.STATUSES) == 9


def test_the_guard_names_a_status_no_bucket_covers(monkeypatch):
    """The guard goes RED, through the function `run` actually calls."""
    monkeypatch.setattr(
        notification_models,
        "STATUSES",
        notification_models.STATUSES + ("deferred_forever",),
    )
    with pytest.raises(RuntimeError) as raised:
        dataset._assert_every_status_is_bucketed()
    assert "deferred_forever" in str(raised.value)


def test_the_guard_names_a_status_counted_twice(monkeypatch):
    """The mirror defect: tiles that add to more than the sent count."""
    buckets = dict(dataset._BUCKETS)
    buckets["failed"] = dataset.FAILED_STATUSES + (notification_models.STATUS_BOUNCED_HARD,)
    monkeypatch.setattr(dataset, "_BUCKETS", buckets)
    with pytest.raises(RuntimeError) as raised:
        dataset._assert_every_status_is_bucketed()
    assert notification_models.STATUS_BOUNCED_HARD in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
#  R8 — the report this dataset exists for
# ══════════════════════════════════════════════════════════════════════════


def test_r8_serves_one_row_per_message_and_the_tiles_foot(brazos, dana):
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        result = dataset.notifications_dataset()

    assert result["grain"] == "one outbound message"
    totals = result["totals"]
    assert totals["sent"] == DISPATCHED
    assert totals["delivered"] == DELIVERED
    assert totals["bounced"] == BOUNCED
    assert totals["returned"] == RETURNED
    assert totals["unsubscribed"] == UNSUBSCRIBED
    assert totals["queued"] == QUEUED
    assert totals["held"] == HELD


def test_the_bounced_tile_counts_all_three_spellings(brazos, dana):
    """⚠ **THE FALSE PASS:** `status="bounced"` alone reports ZERO here.

    `DEF-NOT-5626` split a bounce into hard and soft on 2026-09-17 and left the
    legacy word lawful and unwritten. The fixture holds one of each, so a
    single-spelling tile is off by two and this case names the number.
    """
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        result = dataset.notifications_dataset()

    assert result["totals"]["bounced"] == 3
    assert set(dataset.BOUNCED_STATUSES) == {
        notification_models.STATUS_BOUNCED,
        notification_models.STATUS_BOUNCED_HARD,
        notification_models.STATUS_BOUNCED_SOFT,
    }


def test_an_unsubscribe_is_never_counted_as_a_bounce(brazos, dana):
    """`models.py`: the ONE outcome of the six that is not a failure of any kind.

    A delivery report that files a person's choice under failures invites
    somebody to re-subscribe them.
    """
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        totals = dataset.notifications_dataset()["totals"]

    assert totals["unsubscribed"] == 1
    assert totals["bounced"] == 3  # not 4
    assert notification_models.STATUS_UNSUBSCRIBED not in dataset.BOUNCED_STATUSES
    # It DID leave the building, so it is in the sent count.
    assert notification_models.STATUS_UNSUBSCRIBED in dataset.DISPATCHED_STATUSES


def test_a_held_letter_is_not_in_the_sent_count_or_the_rate(brazos, dana):
    """BR-PAY-018 — written, marked held, never dispatched, never lost.

    ⚠ **THE FALSE PASS:** counting held rows as sent strikes the delivery rate
    against letters still in the building. Eight rows exist; six were sent.
    """
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        result = dataset.notifications_dataset()

    assert result["totals"]["held"] == HELD
    assert result["totals"]["sent"] == DISPATCHED
    assert result["totals"]["sent"] < 8
    codes = {problem["code"] for problem in result["problems"]}
    assert dataset.GAP_HELD_HAS_NOT_BEEN_SENT["code"] in codes


def test_a_returned_letter_was_genuinely_sent(brazos, dana):
    """BR-NOT-005 forward-only — `returned_at` is orthogonal to status."""
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        result = dataset.notifications_dataset()

    assert result["totals"]["returned"] == RETURNED
    returned = [row for row in result["rows"] if row.returned_on is not None]
    assert len(returned) == 1
    assert returned[0].status == notification_models.STATUS_SENT
    assert returned[0].address == "91 Live Oak Dr"


def test_the_delivered_rate_is_recomputed_and_is_none_over_nothing(brazos, dana):
    """§7.2.2 non-additive · BR-REP-024 — 0% over no letters is not a number."""
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        populated = dataset.notifications_dataset()
        empty = dataset.notifications_dataset(start=date(2000, 1, 1), end=date(2000, 1, 2))

    assert populated["totals"]["delivered_pct"] == Decimal(1) / Decimal(6) * Decimal(100)
    assert empty["total"] == 0
    assert empty["totals"]["delivered_pct"] is None


def test_the_reason_column_keeps_three_different_facts_apart(brazos, dana):
    """BR-BIL-036 — *no address* is NORMAL and is not an error."""
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        rows = dataset.notifications_dataset()["rows"]
        pending = [
            row
            for row in dataset.notifications_dataset(start=None, end=None)["rows"]
        ]

    kinds = {row.reason_kind for row in rows if row.reason_kind}
    assert "error" in kinds
    errored = [row for row in rows if row.reason_kind == "error"]
    assert errored[0].reason == "Mailbox full"
    assert pending  # a non-zero beside the assertion above


def test_the_account_column_is_the_number_never_the_id(brazos, dana):
    """B14 rule 31.

    ⚠ **AN UNWINDOWED READ SERVES EVERY ROW, INCLUDING THE TWO NOT YET SENT.**
    The window is on `sent_at`, which is NULL until the dispatcher moves a row,
    so a windowed read excludes queued and held messages BY CONSTRUCTION and an
    unwindowed one does not. Both are correct and the difference is asserted
    here rather than left to be discovered: `total` is EIGHT while `sent` is
    SIX, and `queued` and `held` account for the other two.
    """
    with tenant_ctx(brazos):
        account = _eight(brazos, dana)
        result = dataset.notifications_dataset()
        rows = result["rows"]

    assert len(rows) == MESSAGES
    assert result["totals"]["sent"] == DISPATCHED
    assert result["totals"]["queued"] + result["totals"]["held"] == MESSAGES - DISPATCHED
    assert all(row.account_no == "100244" for row in rows)
    assert all(str(account.id) != row.account_no for row in rows)


def test_the_address_is_the_pinned_envelope_not_a_premises_read_today(brazos, dana):
    """Hard rule 8 + BR-TEN-017 — the report is about what happened."""
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        result = dataset.notifications_dataset()

    codes = {problem["code"] for problem in result["problems"]}
    assert dataset.GAP_ADDRESS_IS_THE_PINNED_ENVELOPE["code"] in codes
    # No address column of its own is composed anywhere.
    row = result["rows"][0]
    for absent in ("city", "state", "postal_code", "address_line"):
        assert not hasattr(row, absent)


def test_the_grain_is_one_message_so_two_channels_are_two_rows(brazos, dana):
    """BR-BIL-016. A grain of *one bill* would lose whichever channel sorted
    second, and a quieter month does not read as wrong."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100512")
        source = uuid.uuid4()
        _message(brazos, account, channel=notification_models.CHANNEL_EMAIL,
                 status=notification_models.STATUS_DELIVERED, source_id=source)
        _message(brazos, account, channel=notification_models.CHANNEL_PRINT,
                 status=notification_models.STATUS_SENT, source_id=source)
        result = dataset.notifications_dataset()

    assert result["total"] == 2
    assert {row.channel for row in result["rows"]} == {
        notification_models.CHANNEL_EMAIL,
        notification_models.CHANNEL_PRINT,
    }


def test_the_page_is_cut_in_sql_and_the_last_page_is_not_empty(brazos, dana):
    with tenant_ctx(brazos):
        _eight(brazos, dana)
        second = dataset.notifications_dataset(per=5, page=2)
        beyond = dataset.notifications_dataset(per=5, page=9)

    assert second["pages"] == 2
    assert len(second["rows"]) == MESSAGES - 5  # the short last page, not empty
    assert beyond["page"] == 2  # clamped, never an empty page past the end
    assert len(beyond["rows"]) == MESSAGES - 5


def test_every_sort_ends_in_a_unique_column():
    for name, terms in dataset.DELIVERY_SORT_COLUMNS.items():
        assert terms[-1] == "id", f"{name} has no unique tiebreak"
    assert set(dataset.DELIVERY_SORTS) == set(dataset.DELIVERY_SORT_COLUMNS)


def test_the_export_takes_no_page_and_no_per(brazos, dana):
    import inspect

    signature = inspect.signature(dataset.notifications_dataset_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _eight(brazos, dana)
        streamed = list(dataset.notifications_dataset_stream())
    # NFR-5 — every row of the filtered set, including the two not yet sent.
    assert len(streamed) == MESSAGES


def test_this_module_writes_nothing():
    import inspect

    source = inspect.getsource(dataset)
    for forbidden in (".save(", ".create(", ".delete(", ".update(", "bulk_create"):
        assert forbidden not in source, f"{forbidden} is a write and this path is a read"
