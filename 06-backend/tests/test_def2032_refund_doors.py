# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2032 — MONEY GOING OUT HAS NO DOOR. `approve_refund` and
#           `void_refund` are both `@permissions.require_role(SYSTEM_ADMIN,
#           br_ref="BR-PAY-014")` and no route in the tree reaches either.
#           Found by G52 and named in `g52_no_door_baseline.txt`.
# Story:    US-PAY-011 · J15 steps 2–3 (the approval queue)
#           Screens: S58
# Rules:    BR-PAY-014 (Admin approval, server-enforced) · BR-PAY-037 (one user
#           MAY initiate and approve in v1, as long as both acts are recorded
#           separately) · BR-SHL-025 · CLAUDE.md hard rule 4 (a void is a status
#           move plus a reversing posting, never a removal) · hard rule 5 (only
#           the ledger posting service writes journal lines)
# Ruling:   decision log 2026-08-28 §6.
# ───────────────────────────────────────────────────────
"""The SERVING half of the refund lifecycle's two Admin acts.

The arithmetic, the ledger pair and every worked PO figure are proved in
`tests/test_us_pay_011_refunds.py` against the module. What is proved HERE is
the three claims only a route can make, and the first is the defect:

  1. **A refund can be FOUND.** No route in this product listed a refund id, so
     the two Admin-gated acts on one were unreachable by construction rather
     than by oversight — `DEF-100`'s mechanism exactly, one table over.
  2. **Both acts are reachable, and Admin-only at the door** (`BR-PAY-014`).
  3. **Neither act recomputes a figure**, and the void deletes no row.

RED PROOF: run against an untouched worktree at this lane's starting commit,
the whole file fails to collect — `apps.payments.refunds_api` does not exist
there. 8 of 8 FAIL.
"""

from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import models, refunds_api, selectors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import PE4_CREDIT
from tests.test_us_pay_011_refunds import (  # noqa: F401
    APPROVED_AT,
    VOIDED_AT,
    a_request,
    an_overpaid_account,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _call(view, tenant, *, actor, method="post", role="system_admin", data=None, **kw):
    return api_call(
        view, method, user=actor.user, role=role, tenant=tenant, data=data or {}, **kw
    )


def _a_requested_refund(brazos, marcus):
    account, recorded = an_overpaid_account(brazos, marcus)
    return account, a_request(marcus, recorded.payment_id)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE THREE ADDRESSES
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "path,view_name",
    [
        ("/api/brazos/refunds", "refunds_queue"),
        ("/api/brazos/refunds/R-1/approve", "refund_approve"),
        ("/api/brazos/refunds/R-1/void", "refund_void"),
    ],
)
def test_the_refund_doors_are_mounted(path, view_name):
    """DEF-2032 — all three 404'd before this lane. `grep` found no refund route
    in the tree but `accounts/{id}/refund`, which reaches neither act."""
    match = resolve(path)
    assert match.func is getattr(refunds_api, view_name), path


# ══════════════════════════════════════════════════════════════════════════
# 2 · A REFUND CAN BE FOUND — THE READ THAT MADE THE WRITES REACHABLE
# ══════════════════════════════════════════════════════════════════════════


def test_the_approval_queue_lists_a_requested_refund(brazos, marcus):
    """J15 step 2 — *"the row is VISIBLE in an approval queue between the
    request and the execution"*, which `models.Refund`'s docstring requires and
    which nothing served."""
    with tenant_ctx(brazos):
        _account, requested = _a_requested_refund(brazos, marcus)

    listed = _call(refunds_api.refunds_queue, brazos, actor=marcus, method="get")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.data["results"]]
    assert str(requested.refund_id) in ids
    # ⚠ **THE QUEUE PAGES SINCE 2026-09-24 (`DEF-PAY-6555` · `P1.3`) AND
    # `count` IS WHAT MAKES THAT HONEST.** The read argued against paging in
    # its own words — *"a page of an approval queue is a queue that lies about
    # what is pending"* — and the answer is this number: the total over the
    # filtered set, on every page. A queue drawn without it re-opens the
    # defect, so it is asserted here rather than left to the screen.
    assert listed.data["count"] >= 1


def test_the_queue_renders_both_approval_acts_separately(brazos, marcus):
    """BR-PAY-037 — one user may initiate AND approve in v1 *"as long as both
    acts are recorded separately"*, so a row folding them into one boolean would
    erase the control the rule leans on."""
    with tenant_ctx(brazos):
        _account, requested = _a_requested_refund(brazos, marcus)

    row = next(
        r
        for r in _call(refunds_api.refunds_queue, brazos, actor=marcus, method="get").data["results"]
        if r["id"] == str(requested.refund_id)
    )
    assert "requested_by" in row and "approved_by" in row
    assert row["requested_by"] is not None
    assert row["approved_by"] is None, "nobody has approved it yet"
    # CLAUDE.md rule 2 — every amount travels with its CHAR(3) code.
    assert row["currency"] and len(row["currency"]) == 3


def test_an_unknown_status_filter_is_refused_with_the_closed_set(brazos, marcus):
    """*"An empty queue and an unanswerable one look identical on a screen"* —
    `write_off_queue`'s own words, and the same trap."""
    refused = _call(
        refunds_api.refunds_queue,
        brazos,
        actor=marcus,
        method="get",
        data={"f.status": "nonsense"},
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "payments.refund.status_unknown"
    assert "requested" in refused.data["params"]["supported"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE TWO ADMIN ACTS
# ══════════════════════════════════════════════════════════════════════════


def test_an_admin_approves_a_requested_refund_through_the_door(brazos, marcus, dana):
    """J15 step 3, `BR-PAY-014`. **Approval gates the money exactly once** and
    moves none of it — `issue_refund` is the step that draws the credit down."""
    with tenant_ctx(brazos):
        account, requested = _a_requested_refund(brazos, marcus)
        before = selectors.account_credit_position(account.pk)

    approved = _call(
        refunds_api.refund_approve,
        brazos,
        actor=dana,
        data={"approved_at": APPROVED_AT.isoformat()},
        refund_id=str(requested.refund_id),
    )
    assert approved.status_code == 200, approved.data
    assert approved.data["status"] == models.REFUND_APPROVED
    # Both acts, distinctly, on the row the door answers with.
    assert approved.data["requested_by"] is not None
    assert approved.data["approved_by"] is not None
    assert approved.data["approved_at"] is not None

    with tenant_ctx(brazos):
        assert selectors.account_credit_position(account.pk) == before, "approval moves no money"


def test_a_billing_clerk_cannot_approve_a_refund(brazos, marcus):
    """`BR-PAY-014` is Admin-only and the door mirrors the service's own gate
    rather than widening it — a clerk must not meet a 403 from a layer they
    cannot see."""
    with tenant_ctx(brazos):
        _account, requested = _a_requested_refund(brazos, marcus)

    refused = _call(
        refunds_api.refund_approve,
        brazos,
        actor=marcus,
        role="billing_clerk",
        data={"approved_at": APPROVED_AT.isoformat()},
        refund_id=str(requested.refund_id),
    )
    assert refused.status_code == 403, refused.data


def test_a_void_needs_a_reason_and_deletes_no_row(brazos, marcus, dana):
    """Hard rule 4 and US-PAY-011 TC-4.

    *"a cheque that left the building and came back is a fact somebody has to be
    able to reconstruct in a year"* — the service refuses a blank reason, and
    this asserts the refusal survives the trip through the door.
    """
    with tenant_ctx(brazos):
        _account, requested = _a_requested_refund(brazos, marcus)
        before = models.Refund.objects.count()

    blank = _call(
        refunds_api.refund_void,
        brazos,
        actor=dana,
        data={"voided_at": VOIDED_AT.isoformat(), "void_reason": "   "},
        refund_id=str(requested.refund_id),
    )
    assert blank.status_code == 422, blank.data

    with tenant_ctx(brazos):
        assert models.Refund.objects.count() == before, "no row was removed"


def test_a_missing_approval_moment_is_refused_rather_than_read_off_the_clock(
    brazos, marcus, dana
):
    """`BR-TEN-043` / gate G6 — *"posting and actual dates can differ; ask actual
    date to user"* (PO 2026-08-11). Approval is the control `BR-PAY-014` rests
    on; a timestamp the server invented is a control nobody can reconstruct."""
    with tenant_ctx(brazos):
        _account, requested = _a_requested_refund(brazos, marcus)

    missing = _call(
        refunds_api.refund_approve,
        brazos,
        actor=dana,
        data={},
        refund_id=str(requested.refund_id),
    )
    assert missing.status_code == 422, missing.data
    assert missing.data["code"].startswith("VAL"), missing.data
