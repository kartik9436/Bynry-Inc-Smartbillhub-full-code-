# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-6431` (2026-09-24) — selling an account a SECOND time failed
#           with a server error, because `uq_transfers_to_account` (customers
#           0021) let an account be the incoming half of ONE transfer, ever.
# Rules:    BR-CUS-1030 (a sale reassigns ONE account — `to_account_id` is the
#           sold account itself) · CLAUDE.md hard rules 1 and 4 · hard-won
#           laws 7 and 14 (the constraint cases are proved on PostgreSQL)
# Migration: 06-backend/apps/customers/migrations/0069_def_cus_6431_resale.py
# ───────────────────────────────────────────────────────
"""**A property is sold many times over its life, and the product must let it.**

`BR-CUS-1030` made a sale REASSIGN the account rather than open a new one, so
the commit writes `to_account_id = from_account_id`. The unique index 0021 wrote
for the OLD model — *"an account may be the INCOMING half of exactly one
transfer, ever"* — then meant an account could be sold once, ever. The second
sale died inside the commit's transaction on a duplicate key and reached the
clerk as *"Something went wrong on our side."*

Worked, as lane TRANSFER met it on 2026-09-24: A-11512 sold to *Aiden, Tim*
(`TRF-26-0001`), then resold — refused with a 500.

**What each case pins:**

  * a second sale of the same account COMMITS, and both records survive, each
    naming its own seller and buyer;
  * ONE OPEN SALE AT A TIME still holds — refused BY NAME before any write
    (`from_account_already_being_sold`), and by `uq_transfers_open_from` at the
    database for two clerks racing;
  * the old invariant survives exactly where it meant something — two
    transfers that each OPENED the same new account (the pre-`BR-CUS-1030`
    shape) are still refused, by `uq_transfers_opened_account`.

Run the constraint cases on PostgreSQL (`--ds=config.settings.pgtest`): a
refused statement there aborts the transaction, which SQLite cannot show.
"""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.customers import models as customers_models
from apps.customers import transfers
from core import errors

from tests.test_cr058_w4_transfer_reassigns import BUYER, SELLER_NAME, _sell, _sold_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The SECOND buyer — a different person with a different phone, so the
#: commit's *buyer is the seller* guard has nothing to match.
SECOND_BUYER = {
    "display_name": "Reyes, Carla",
    "kind": "person",
    "identity": {"phone": "+1-555-0199"},
}


def _live_names(tenant, account):
    return sorted(
        link.customer.display_name
        for link in customers_models.CustomerAccount.live(tenant_id=tenant.id, account=account)
    )


def test_an_account_sold_twice_commits_and_keeps_both_records(brazos, marcus):
    """**THE DEFECT, AND THE WHOLE OF IT.** Sale one: Alvarez → Okafor. Sale two,
    of the SAME account: Okafor → Reyes. Both commit; both rows stay."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        first = _sell(marcus, account, buyer=BUYER, sold_on="2026-09-01")
        second = _sell(marcus, account, buyer=SECOND_BUYER, sold_on="2026-09-20")

        rows = list(
            transfers.Transfer.objects.filter(from_account_id=account.id).order_by("created_at")
        )
        assert [str(r.id) for r in rows] == [first["id"], second["id"]], (
            "both sales are on file — the second did not replace the first"
        )
        one, two = rows
        for row in rows:
            assert row.state == transfers.Transfer.STATE_DONE
            assert row.committed_at is not None
            assert row.to_account_id == account.id == row.from_account_id, (
                "BR-CUS-1030: each sale reassigned the same account"
            )
        assert one.transfer_no != two.transfer_no, "two sales, two references"

        # WHO sold and WHO bought, per record — the second sale's SELLER is the
        # first sale's BUYER, and neither record was rewritten by the other.
        assert one.seller_name == SELLER_NAME
        assert two.seller_name == BUYER["display_name"]
        assert one.buyer_customer_id == two.customer_id, (
            "the first buyer is the second seller"
        )
        assert one.customer_id != two.customer_id
        assert two.buyer_customer_id not in (one.customer_id, two.customer_id)

        # The links: each seller's is ENDED by the sale that ended it, and only
        # the last buyer is live.
        ended = {
            str(link.customer_id): str(link.ended_by_transfer_id)
            for link in customers_models.CustomerAccount.objects.filter(
                account=account, ended_at__isnull=False
            )
        }
        assert ended == {str(one.customer_id): str(one.id), str(two.customer_id): str(two.id)}
        assert _live_names(brazos, account) == ["Reyes, Carla"]


def test_one_open_sale_at_a_time_is_still_refused_by_name(brazos, marcus):
    """The rule the old index was NOT — one OPEN sale per account — still holds,
    both before the first sale commits and after it."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        open_one = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        with pytest.raises(errors.BizError) as refused:
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        assert refused.value.params["reason"] == transfers.REFUSAL_ALREADY_BEING_SOLD

        transfers.cancel_transfer(marcus, open_one["id"])
        _sell(marcus, account, buyer=BUYER)
        # The sale committed; a NEW sale may open…
        reopened = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        assert reopened["state"] == transfers.Transfer.STATE_SCHEDULED
        # …and a second open one beside it is refused by name, as before.
        with pytest.raises(errors.BizError) as refused_again:
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        assert refused_again.value.params["reason"] == transfers.REFUSAL_ALREADY_BEING_SOLD


def test_the_database_still_refuses_a_second_open_sale(brazos, marcus):
    """Two clerks racing past `sale_refusal`: `uq_transfers_open_from` is the
    backstop and must still fire. SAVEPOINTED — hard-won law 14."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        first = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        row = transfers.Transfer.objects.get(id=first["id"])
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                transfers.Transfer.objects.create(
                    tenant_id=row.tenant_id,
                    from_account_id=account.id,
                    customer_id=row.customer_id,
                    step=1,
                    state=transfers.Transfer.STATE_SCHEDULED,
                )
        assert "uq_transfers_open_from" in str(refused.value) or connection.vendor == "sqlite", (
            "PostgreSQL names the constraint that refused"
        )
        # The transaction is still usable after the savepoint unwound.
        assert transfers.Transfer.objects.filter(from_account_id=account.id).count() == 1


def test_two_transfers_that_opened_one_new_account_are_still_refused(brazos, marcus):
    """**THE OLD INVARIANT, KEPT WHERE IT MEANT SOMETHING.** Before `BR-CUS-1030`
    a transfer OPENED a new account (`to_account_id <> from_account_id`), and two
    transfers each claiming to have opened the same one is still a contradiction.
    The narrowed index keeps refusing that shape — it only stopped refusing a
    SALE, where both sides are the same account."""
    with tenant_ctx(brazos):
        _p1, _u1, old_a = _sold_account(marcus, brazos, label="1 Old Road")
        _p2, _u2, old_b = _sold_account(marcus, brazos, label="2 Old Road")
        _p3, _u3, opened = _sold_account(marcus, brazos, label="3 New Road")
        seller = customers_models.CustomerAccount.live(
            tenant_id=brazos.id, account=old_a
        ).first().customer
        common = {
            "tenant_id": brazos.id,
            "customer_id": seller.id,
            "to_account_id": opened.id,
            "step": 5,
            "state": transfers.Transfer.STATE_DONE,
        }
        from django.utils import timezone

        transfers.Transfer.objects.create(
            from_account_id=old_a.id, committed_at=timezone.now(), **common
        )
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                transfers.Transfer.objects.create(
                    from_account_id=old_b.id, committed_at=timezone.now(), **common
                )
        assert "uq_transfers_opened_account" in str(refused.value) or (
            connection.vendor == "sqlite"
        )


def test_the_index_is_narrowed_to_the_opened_account_shape():
    """Read the index the database actually holds, not the migration's text."""
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                "select indexname, indexdef from pg_indexes where tablename = 'transfers'"
            )
        else:
            cursor.execute(
                "select name, sql from sqlite_master where type = 'index' "
                "and tbl_name = 'transfers' and sql is not null"
            )
        indexes = dict(cursor.fetchall())
    assert "uq_transfers_to_account" not in indexes, (
        "the once-ever index is gone — it made every account sellable once"
    )
    assert "uq_transfers_opened_account" in indexes
    definition = indexes["uq_transfers_opened_account"].lower()
    assert "unique" in definition
    assert "to_account_id <> from_account_id" in definition
    assert "uq_transfers_open_from" in indexes, "one open sale per account — untouched"
