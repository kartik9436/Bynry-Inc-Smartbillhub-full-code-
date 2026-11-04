# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6344 — Payments → Summary → *Mark returned post* printed a raw
#          database uuid in its Account column on every row. PO, on the
#          deployed build, 2026-09-23: *"this modal is showing db keys"*.
#          DEF-1122 — the same cell, filed 2026-08-27 and left open.
# Rules:   B14 rule 31 (PO 2026-08-30: *"no Databse ID on screen - that is a
#          rule"*) · BR-TEN-013 (a cross-module read resolves the owner's
#          published callable) · NFR-3 (a list is paged in the database, so a
#          label read is per PAGE) · CLAUDE.md hard rule 1 (tenant scoping)
# Screens: S35 bulk mark returned post (the only screen that printed it) · S8
# ───────────────────────────────────────────────────────
"""`GET /outbound` serves the account NUMBER beside the id — once per page.

⛔ **PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** Every case
below was run under `pytest` against the tip this lane started from, with
`apps/notifications/selectors.py` and `api.py` as they stood, before a line of
the fix existed. The failures are quoted in this lane's report and in the
commit message: `6 failed` — `KeyError: 'account_no'` on the four cases that
read the served row, `AttributeError: module 'apps.notifications.selectors' has
no attribute 'queue_page'` on the statement count, and `ImportError: cannot
import name 'customers_seam' from 'apps.notifications'` on the empty page.

⛔ **THE STATEMENT COUNT COMPARES TWO PAGE SIZES WITH A DIFFERENT ACCOUNT ON
EVERY ROW** — the `DEF-MET-6304` shape, for the reason that file gives: a count
alone proves nothing (eight statements is fine for a page of fifty and a
catastrophe for a page of one), and a per-row read that memoised by account id
would spend one statement on a page whose rows share an account and still be an
N+1 on a real estate. What proves a batch is that **the cost did not follow the
page.**
"""

from __future__ import annotations

import re
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.notifications import api as notifications_api
from apps.notifications import models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def an_account(tenant, *, account_no, actor, service="electric"):
    """One numbered account — `test_def_128_notifications_api.an_account`'s shape.

    `service` because the isolation tenant runs Water only, and a premises
    offering a service its utility does not run is refused (VAL-005).
    """
    from apps.customers import models as customer_models

    premises = make_premises(
        actor,
        address_line=f"{account_no or 'unnumbered'} {uuid.uuid4().hex[:6]} Ln",
        services_available=[service],
    )
    unit = make_unit(actor, premises["id"], label=f"U-{uuid.uuid4().hex[:6]}", services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def a_paper_piece(tenant, *, account_id, address="107 Mill Pond Ln"):
    """One unreturned paper row — the stack S35 lists."""
    return models.OutboundMessage.objects.create(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        account_id=account_id,
        channel=models.CHANNEL_PRINT,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=2,
        recipient_address=address,
        status=models.STATUS_QUEUED,
    )


def the_stack(tenant, actor):
    """`GET /outbound` exactly as S35 asks for it (`per=200`, a ratified size)."""
    return api_call(
        notifications_api.outbound,
        "get",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        query={"f.channel": models.CHANNEL_PRINT, "f.returned": "false", "per": 200},
    )


def test_def_pay_6344__the_list_serves_the_account_number(brazos, dana):
    """RED before the fix: `KeyError: 'account_no'`.

    The PO's screenshot, from the server's side: the row the Account column is
    drawn from carries `AC-2026-00054`, not only `01a07fa5-…`.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, account_no="AC-2026-00054", actor=dana)
        a_paper_piece(brazos, account_id=account.id)

    rows = the_stack(brazos, dana).data["results"]

    assert len(rows) == 1
    assert rows[0]["account_no"] == "AC-2026-00054"
    # The id is still served — it is what the row is keyed and filtered by —
    # and it is not what a screen prints.
    assert rows[0]["account_id"] == str(account.id)
    assert not UUID.search(rows[0]["account_no"])


def test_def_pay_6344__an_unnumbered_account_is_null_never_blank(brazos, dana):
    """RED before the fix: `KeyError: 'account_no'`.

    ⚠ `account_no` is a TextField, so an account nobody numbered holds `""`.
    `""` slips past a screen's `?? "No account number"` and draws an EMPTY
    cell — which rule 31 forbids in the same sentence as the id (`DEF-2580`).
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, account_no="", actor=dana)
        a_paper_piece(brazos, account_id=account.id)

    rows = the_stack(brazos, dana).data["results"]

    assert rows[0]["account_no"] is None


def test_def_pay_6344__a_piece_with_no_account_serves_null(brazos, dana):
    """RED before the fix: `KeyError: 'account_no'`. No account, no number —
    and certainly no read spent looking for one."""
    with tenant_ctx(brazos):
        a_paper_piece(brazos, account_id=None, address="12 Ridge Rd")

    rows = the_stack(brazos, dana).data["results"]

    assert rows[0]["account_id"] is None
    assert rows[0]["account_no"] is None


def test_def_pay_6344__another_utilitys_account_number_never_crosses(brazos, lonestar, dana, erin):
    """CLAUDE.md hard rule 1. RED before the fix: `KeyError: 'account_no'`.

    A Brazos Bend row pointing at a Lone Star account id — which no honest
    writer produces, and which is exactly the case a cross-module read has to
    survive — gets NO number, because customers' own queryset is tenant-scoped.
    Another utility's account number on this screen would be a leak.
    """
    with tenant_ctx(lonestar):
        theirs = an_account(lonestar, account_no="LS-000777", actor=erin, service="water")
    with tenant_ctx(brazos):
        a_paper_piece(brazos, account_id=theirs.id)

    rows = the_stack(brazos, dana).data["results"]

    assert rows[0]["account_no"] is None
    assert "LS-000777" not in str(rows)


def test_def_pay_6344__the_number_costs_one_statement_per_page_not_per_row(brazos, dana):
    """⛔ **THE ASSERTION THAT STOPS THIS BECOMING `DEF-324` AGAIN.**

    RED before the fix: `AttributeError: … no attribute 'queue_page'`.

    Six rows, SIX DIFFERENT ACCOUNTS. The seam's cost on a page of two and a
    page of six must be the same — and must be exactly ONE statement — and the
    whole endpoint's cost must not follow the page either.

    ⚠ **THE ENDPOINT HALF VARIES THE ROWS, NOT `per`.** `per` snaps to the
    ratified sizes (50/100/200/500/1000, A11 Addendum r2), so asking for a page
    of two returns every row there is — the first draft of this case did that
    and measured one page twice. So the endpoint is measured with two rows in
    the stack and again with six, at the same page size.
    """
    with tenant_ctx(brazos):
        accounts = [
            an_account(brazos, account_no=f"AC-2026-{index:05d}", actor=dana)
            for index in range(60, 66)
        ]
        pieces = [
            a_paper_piece(brazos, account_id=account.id, address=f"{index} Counting Way")
            for index, account in enumerate(accounts)
        ]
        ids = [piece.pk for piece in pieces]

        def seam_cost(how_many):
            rows = list(models.OutboundMessage.objects.filter(pk__in=ids[:how_many]))
            assert len(rows) == how_many
            with CaptureQueriesContext(connection) as captured:
                served = selectors.queue_page(rows)
            return len(captured.captured_queries), served

        small, small_rows = seam_cost(2)
        large, large_rows = seam_cost(6)

    # Six distinct numbers came back, so a memoising per-row read could not
    # have produced them in a constant number of statements.
    assert len({row["account_no"] for row in large_rows}) == 6
    assert small == large == 1, (
        f"the page's cost followed the page: {small} statement(s) for 2 rows, "
        f"{large} for 6 — that is DEF-324's shape, not a batch"
    )

    def endpoint_cost(expected_rows):
        with CaptureQueriesContext(connection) as captured:
            response = the_stack(brazos, dana)
        assert len(response.data["results"]) == expected_rows
        assert all(row["account_no"] for row in response.data["results"])
        return len(captured.captured_queries)

    # Hide four of the six from the stack, measure; bring them back, measure.
    with tenant_ctx(brazos):
        models.OutboundMessage.objects.filter(pk__in=ids[2:]).update(channel=models.CHANNEL_EMAIL)
    two = endpoint_cost(2)
    with tenant_ctx(brazos):
        models.OutboundMessage.objects.filter(pk__in=ids[2:]).update(channel=models.CHANNEL_PRINT)
    six = endpoint_cost(6)
    print(f"GET /outbound statements: {two} for a page of 2 rows, {six} for a page of 6 rows")
    assert two == six, f"GET /outbound spent {two} statements for 2 rows and {six} for 6"


def test_def_pay_6344__an_empty_page_asks_customers_nothing(brazos, dana):
    """The degenerate page: no ids, no statement.

    Imported HERE rather than at the top so that, on the tip before the fix,
    the other cases fail on their own assertions instead of the whole file
    failing to collect — a red proof has to name what each case is about.
    """
    from apps.notifications import customers_seam

    with tenant_ctx(brazos):
        with CaptureQueriesContext(connection) as captured:
            assert customers_seam.account_numbers([]) == {}
            assert customers_seam.account_numbers([None, ""]) == {}
    assert len(captured.captured_queries) == 0


# ── Lifecycle ─────────────────────────────────────────────
# defect: DEF-PAY-6344
# generated: 2026-09-23 by lane RETURNED-POST
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# exceptions:
#   E3 the statement counts run on SQLite like the rest of this suite. They
#      count statements, which SQLite reports the same way PostgreSQL does, and
#      the read catches no database error, so hard-won law 14's aborted-
#      transaction trap cannot arise from it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
