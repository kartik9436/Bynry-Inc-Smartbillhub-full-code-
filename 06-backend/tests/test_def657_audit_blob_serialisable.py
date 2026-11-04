# ── Trace ──────────────────────────────────────────────
# Rules:    BR-AUD-003 (the standard row) · BR-AUD-006 (PII masked) ·
#           CLAUDE.md hard rule 7 (every money action writes audit_log)
# ───────────────────────────────────────────────────────
"""DEF-657 — an audit blob holding a UUID used to kill the whole transaction.

FOUND BY A BROWSER WALKTHROUGH AND BY NOTHING ELSE (hard-won law 6). Every unit
test, `tsc` and every gate were green over it. What a clerk met was:

    POST /service-requests/{id}/category   ->  200   (first call)
    POST /service-requests/{id}/category   ->  500   (every call after it)

i.e. changing your mind about a customer category was a server error, and the
FIRST call always worked — which is why no test caught it. `set_customer_category`
built its `before` blob from `request.account_type_id`, and on a fresh request
that is `None`, which is JSON. Only once a category HAD been set was it a `UUID`,
and `json.dumps` cannot hold one. The same function's `after` block already wrote
`str(subtype.id)`, so the two halves of one row disagreed about their own types.

WHY THE FIX IS IN `core.audit` AND NOT AT THAT CALL SITE. `write_row` is the one
writer for the whole product and it stored `before`/`after` VERBATIM, so the trap
belonged to every module with an audit blob, not to service requests. Two `str()`
calls would have closed one instance of a class. Coercing at the writer also makes
the careless callers agree with the careful ones, which is what the correct call
sites were already doing by hand.

WHAT IS NOT COERCED, deliberately: anything `json` can already hold keeps its own
type, so a bool stays a bool and an int stays an int. An audit trail that turned
`False` into `"False"` would be a different kind of wrong.
"""

import datetime as dt
import decimal
import json
import uuid

import pytest

from core import audit


@pytest.fixture
def captured(monkeypatch):
    """Capture the row the sink is handed, with tenant context faked."""
    rows: list[dict] = []
    monkeypatch.setattr(audit, "_sink", rows.append)
    monkeypatch.setattr(audit, "current_tenant_id", lambda: uuid.uuid4())
    return rows


def _write(**kw):
    return audit.write_row(
        action="service_request.category_set",
        entity_type="service_request",
        entity_id=uuid.uuid4(),
        **kw,
    )


def test_def657_the_reported_case__a_uuid_in_before_survives_json(captured):
    """The exact shape of the 500: a `before` holding the PREVIOUS category id.

    First call: `account_type` is None and the row serialises. Second call: it is
    a UUID and, before this fix, `json.dumps` raised
    `TypeError: Object of type UUID is not JSON serializable` — inside the
    transaction, so the clerk's edit was rolled back and answered 500.
    """
    previous = uuid.uuid4()
    _write(
        before={"account_type": previous, "account_subtype": None},
        after={"account_type": "commercial", "account_subtype": None},
    )
    stored = captured[-1]
    json.dumps(stored["before"])  # the assertion: this used to raise
    assert stored["before"]["account_type"] == str(previous)
    assert stored["before"]["account_subtype"] is None


def test_def657_the_first_call_still_worked__which_is_why_no_test_caught_it(captured):
    """A fresh request has `None`, which is JSON — so call one always passed."""
    _write(before={"account_type": None}, after={"account_type": "residential"})
    json.dumps(captured[-1]["before"])
    assert captured[-1]["before"] == {"account_type": None}


def test_def657_the_other_types_a_blob_reaches_for(captured):
    """Dates, Decimals and sets reach audit blobs the same way UUIDs do.

    A Decimal becomes a STRING and never a float — CLAUDE.md hard rule 2, and an
    audit row is where a money figure is read back in a dispute.
    """
    _write(
        after={
            "on": dt.date(2026, 8, 24),
            "at": dt.datetime(2026, 8, 24, 14, 53),
            "amount": decimal.Decimal("181.9400"),
            "services": {"water", "electric"},
        }
    )
    stored = captured[-1]["after"]
    json.dumps(stored)
    assert stored["on"] == "2026-08-24"
    assert stored["at"].startswith("2026-08-24T14:53")
    assert stored["amount"] == "181.9400"  # a STRING, never 181.94 the float
    assert isinstance(stored["amount"], str)
    assert stored["services"] == ["electric", "water"]  # sorted, so a diff is stable


def test_def657_json_native_values_keep_their_own_types(captured):
    """The half that must NOT change: a bool stays a bool, an int stays an int.

    An audit trail that recorded `False` as `"False"` would be a different kind of
    wrong from the one being fixed, and a reader cannot tell them apart later.
    """
    _write(after={"required": False, "count": 3, "ratio": 0.5, "note": "x", "gone": None})
    stored = captured[-1]["after"]
    assert stored["required"] is False
    assert stored["count"] == 3
    assert stored["ratio"] == 0.5
    assert stored["note"] == "x"
    assert stored["gone"] is None


def test_def657_nested_structures_are_reached(captured):
    """Blobs in this product nest — `{"services": [...]}` and lists of dicts."""
    a, b = uuid.uuid4(), uuid.uuid4()
    _write(after={"rows": [{"id": a}, {"id": b}], "meta": {"parent": a}})
    stored = captured[-1]["after"]
    json.dumps(stored)
    assert stored["rows"] == [{"id": str(a)}, {"id": str(b)}]
    assert stored["meta"]["parent"] == str(a)


def test_def657_a_blob_that_cannot_be_serialised_at_all_still_refuses(captured):
    """⚠ COERCION MUST NOT BECOME A SILENT SWALLOW.

    Rule 7 says the audit row is not optional, so the writer refuses a blob it
    cannot represent rather than storing a lie about it. An arbitrary object gets
    a STRING with its type named — enough for a human reading the trail to see
    that something unusual was written and go and look — never a dropped key.
    """

    class Opaque:
        def __repr__(self):
            return "<Opaque object>"

    _write(after={"thing": Opaque()})
    stored = captured[-1]["after"]
    json.dumps(stored)
    assert "Opaque" in stored["thing"]
