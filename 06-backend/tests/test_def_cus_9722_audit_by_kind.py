"""**DEF-CUS-9722 — `GET /audit-log?f.entity_id=<account>&f.kind=all|changes|messages`.**

Image 29 draws the move-in's Audit tab with an *All · Changes · Messages*
filter. The move-in's history is the audit log of the account it opened, and
nothing served it split by kind: `f.action` matches ONE code, and a message
queued for the account is audited against the MESSAGE (`outbound_message`,
its own id), so `f.entity_id=<account>` never found a message at all.

`f.kind` on the existing read (no new endpoint):

  * `changes`  — the rows written against the account itself;
  * `messages` — the `outbound_message.*` rows whose `after.account_id` is it;
  * `all`      — both, in one page, paged and counted by the server.

Without `f.kind` the read is exactly what it was (the Audit log page's
`f.entity_id` is untouched). An unknown value falls back (BR-SHL-011).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **An undeclared filter is DROPPED, not refused** — so the API case asserts
    COUNTS that differ by kind; a dropped `f.kind` answers the same count for
    all three.
  * **Another account's message** is seeded, so *messages* cannot pass by
    returning every `outbound_message` row in the tenant.
"""

import uuid

import pytest

from apps.audit import selectors as audit_selectors
from apps.audit.models import AuditLog

from tests.test_us_idn_helpers import api_get, idn, signed_in_client  # noqa: F401

pytestmark = pytest.mark.django_db

ADMIN = ("alex@silvercreek.example", "Canyon2026rapids")


def _row(tenant, *, action, entity_type, entity_id, after=None):
    return AuditLog.objects.create(
        tenant_id=tenant.id, action=action, entity_type=entity_type,
        entity_id=entity_id, after=after,
    )


def _seed(tenant):
    account, other = uuid.uuid4(), uuid.uuid4()
    changes = [
        _row(tenant, action="account.created", entity_type="account", entity_id=account),
        _row(tenant, action="account.move_in_date_changed", entity_type="account", entity_id=account),
    ]
    messages = [
        _row(tenant, action="outbound_message.queued", entity_type="outbound_message",
             entity_id=uuid.uuid4(), after={"account_id": str(account), "channel": "email"}),
    ]
    # Noise: another account's change and message.
    _row(tenant, action="account.created", entity_type="account", entity_id=other)
    _row(tenant, action="outbound_message.queued", entity_type="outbound_message",
         entity_id=uuid.uuid4(), after={"account_id": str(other), "channel": "email"})
    return account, changes, messages


def test_kind_is_a_declared_filter():
    assert "kind" in audit_selectors.AUDIT_FILTERS


def test_the_three_kinds_split_one_accounts_history(idn):
    idn.seed_silvercreek()
    account, changes, messages = _seed(idn.silvercreek)

    def ids(kind=None):
        filters = {"entity_id": str(account)}
        if kind is not None:
            filters["kind"] = kind
        return {r.id for r in audit_selectors.audit_queryset(idn.silvercreek.id, filters=filters)}

    assert ids() == {r.id for r in changes}  # no kind: unchanged
    assert ids("changes") == {r.id for r in changes}
    assert ids("messages") == {r.id for r in messages}
    assert ids("all") == {r.id for r in changes + messages}
    assert ids("nonsense") == {r.id for r in changes}  # falls back


def test_the_route_honours_f_kind(idn):
    users = idn.seed_silvercreek()
    assert users is not None
    account, changes, messages = _seed(idn.silvercreek)
    admin = signed_in_client(*ADMIN)
    base = f"/audit-log?f.entity_id={account}"
    counts = {
        kind: api_get(admin, f"{base}&f.kind={kind}").json()["count"]
        for kind in ("all", "changes", "messages")
    }
    assert counts == {"all": 3, "changes": 2, "messages": 1}, counts
