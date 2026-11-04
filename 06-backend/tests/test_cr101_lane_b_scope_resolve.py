# ── Trace ──────────────────────────────────────────────
# Change:   CR-101-BRC03 §06 lane B — the Fix a bill wizard's step-1 table
#           (p133 of `05-prototype/04 Billing, As Built.pdf`, read as an image —
#           it has no text layer): `BILL · PERIOD · AMOUNT · PAID · STATE`, a
#           totals row (*"Six bills · $1,454.10 · $904.50"*), and *"Only an
#           issued or paid bill can be corrected."*
# Rules:    BR-BIL-014 (the five selectors; ISSUED and PAID only) · BR-BIL-072
#           (a bill is measured at what it ASKS for) · BR-PAY-010/031 (what has
#           met a bill is payments' fact, net of reversals) · NFR-3 (server
#           pagination, no cap) · CLAUDE.md rule 1 (tenant scoping) · rule 2
#           (money as strings) · B1 (billing reads payments through the seam)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The bills a scope resolves to, paged, with what each asked and what was paid.

Proved RED first (2026-09-15) against the tip `9cda92e6` extracted into a
scratch tree (`git archive 9cda92e6 06-backend`, the file copied in, the same
`pytest` from the same venv): **all nine failed** — the seven API cases on
`AttributeError: module 'apps.billing.corrections_api' has no attribute
'correction_scope_resolve'`, the route case the same way, and the SQL tie-out
case on `resolve_scope_queryset` not existing — and all nine pass here.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.billing import bulk_corrections, corrections_api, models, payments_seam, selectors
from apps.payments import models as payment_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_016_bulk_corrections import an_issued_bill
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def _paid(tenant, account, invoice, amount: Decimal, *, no: str):
    """One cleared receipt, applied to `invoice` in full — payments' own rows."""
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=no,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
    )
    payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=invoice, amount=amount
    )
    return payment


def _p133_run(brazos, dana):
    """p133's shape at three bills: one paid, one part paid, one unpaid."""
    account = an_account(dana, brazos)
    run = a_run(brazos, key="2026-07|cycle-A")
    paid = an_issued_bill(
        brazos, account, run, invoice_no="BL-2607-000401", total=Decimal("241.80")
    )
    part = an_issued_bill(
        brazos, account, run, invoice_no="BL-2607-000402", total=Decimal("239.90")
    )
    unpaid = an_issued_bill(
        brazos, account, run, invoice_no="BL-2607-000403", total=Decimal("247.20")
    )
    _paid(brazos, account, paid, Decimal("241.80"), no="PMT-000001")
    _paid(brazos, account, part, Decimal("180.00"), no="PMT-000002")
    return run, (paid, part, unpaid)


def _resolve(brazos, dana, **query):
    return api_call(
        corrections_api.correction_scope_resolve,
        "get",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        query=query,
    )


# ═══════════════════════════════════════════════════════════════════════════
# p133 — the five columns and the totals row
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc1__each_bill_carries_amount_paid_and_state_and_the_totals_tie(brazos, dana):
    """*"Six bills · $1,454.10 · $904.50"* at three bills: 728.90 asked, 421.80 paid."""
    with tenant_ctx(brazos):
        run, (paid, part, unpaid) = _p133_run(brazos, dana)
        response = _resolve(brazos, dana, scope_kind="run", bill_run_id=str(run.pk))

    assert response.status_code == 200, response.data
    body = response.data
    rows = {row["invoice_no"]: row for row in body["results"]}
    assert list(rows) == ["BL-2607-000401", "BL-2607-000402", "BL-2607-000403"], "bill order"
    assert rows["BL-2607-000401"]["state"] == bulk_corrections.STATE_PAID
    assert rows["BL-2607-000402"]["state"] == bulk_corrections.STATE_PART_PAID
    assert rows["BL-2607-000403"]["state"] == bulk_corrections.STATE_UNPAID
    assert Decimal(rows["BL-2607-000402"]["paid"]) == Decimal("180.00")
    assert Decimal(rows["BL-2607-000403"]["paid"]) == Decimal("0")
    assert Decimal(rows["BL-2607-000401"]["amount"]) == Decimal("241.80")
    for row in rows.values():
        assert row["period_start"] == "2026-07-01" and row["period_end"] == "2026-07-31"
        assert row["bill_status"] == "issued"
        assert row["currency"] == "USD"
        assert isinstance(row["amount"], str) and isinstance(row["paid"], str), "money as strings"
    totals = body["totals"]
    assert totals["bills"] == 3
    assert Decimal(totals["amount"]) == Decimal("728.90")
    assert Decimal(totals["paid"]) == Decimal("421.80")
    assert totals["currency"] == "USD"
    assert body["correctable_statuses"] == ["issued", "paid"], "p133's closing sentence, as a fact"
    assert body["problems"] == []
    assert body["count"] == 3, "the standard envelope"


def test_lane_b_tc2__the_totals_are_over_the_whole_scope_not_the_page(brazos, dana):
    """NFR-3: fifty-five bills, a fifty-row page, and a totals row that reads
    all fifty-five on BOTH pages. A run at T5 is forty thousand of these."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        for n in range(55):
            invoice = an_issued_bill(
                brazos, account, run, invoice_no=f"BL-2607-01{n:04d}", total=Decimal("10.00")
            )
            if n < 20:
                _paid(brazos, account, invoice, Decimal("10.00"), no=f"PMT-{n:06d}")
        first = _resolve(brazos, dana, scope_kind="run", bill_run_id=str(run.pk), per="50")
        second = _resolve(
            brazos, dana, scope_kind="run", bill_run_id=str(run.pk), per="50", page="2"
        )

    assert first.status_code == 200 and second.status_code == 200
    assert len(first.data["results"]) == 50 and len(second.data["results"]) == 5
    assert first.data["count"] == 55 and first.data["next"] is not None
    for body in (first.data, second.data):
        assert body["totals"]["bills"] == 55
        assert Decimal(body["totals"]["amount"]) == Decimal("550.00")
        assert Decimal(body["totals"]["paid"]) == Decimal("200.00")
    states = [row["state"] for row in first.data["results"]]
    assert states.count(bulk_corrections.STATE_PAID) == 20
    assert states.count(bulk_corrections.STATE_UNPAID) == 30


def test_lane_b_tc3__amount_is_what_the_bill_asked_and_the_sql_agrees_with_the_rule(brazos, dana):
    """BR-BIL-072: ❄️ WE-8's budget bill totals 292.87 and ASKS 242.00. The row
    shows both; the SQL totals use the same rule as `amount_due_for`."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        budget = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2607-000501",
            total=Decimal("292.87"),
            bill_payload={"account_no": account.account_no, "budget": {"amount_due": "242.00"}},
        )
        plain = an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000502", total=Decimal("100.00")
        )
        queryset = bulk_corrections.resolve_scope_queryset(kind="run", bill_run_id=run.pk)
        table = bulk_corrections.scope_table(tuple(queryset), queryset=queryset)
        by_sql = {
            str(row["id"]): row["asked"]
            for row in queryset.annotate(asked=bulk_corrections.amount_asked_expression()).values(
                "id", "asked"
            )
        }

    rows = {row["invoice_no"]: row for row in table["rows"]}
    assert Decimal(rows["BL-2607-000501"]["amount"]) == Decimal("242.00")
    assert Decimal(rows["BL-2607-000501"]["total"]) == Decimal("292.87")
    assert Decimal(rows["BL-2607-000502"]["amount"]) == Decimal("100.00")
    assert Decimal(table["totals"]["amount"]) == Decimal("342.00")
    # The one rule and its SQL twin, tied on both shapes of bill.
    assert Decimal(by_sql[str(budget.pk)]) == selectors.amount_due_for(budget) == Decimal("242.00")
    assert Decimal(by_sql[str(plain.pk)]) == selectors.amount_due_for(plain) == Decimal("100.00")


def test_lane_b_tc4__payments_unreachable_is_null_and_a_problem_never_unpaid(
    brazos, dana, monkeypatch
):
    """The seam's rule — an unwired read reports, it never answers zero. Forty
    thousand bills drawn as `Unpaid` because nobody could ask is a false fact."""
    monkeypatch.setattr(payments_seam, "_resolve", lambda module, attribute: None)
    with tenant_ctx(brazos):
        run, _ = _p133_run(brazos, dana)
        response = _resolve(brazos, dana, scope_kind="run", bill_run_id=str(run.pk))

    assert response.status_code == 200
    for row in response.data["results"]:
        assert row["paid"] is None and row["state"] is None
        assert row["amount"] is not None, "the bill's own figure is unaffected"
    assert response.data["totals"]["paid"] is None
    assert Decimal(response.data["totals"]["amount"]) == Decimal("728.90")
    assert [p["code"] for p in response.data["problems"]] == [bulk_corrections.PAYMENTS_UNREACHABLE]


# ═══════════════════════════════════════════════════════════════════════════
# Eligibility, refusals, the door, and the tenant
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc5__only_an_issued_or_paid_bill_resolves(brazos, dana):
    """p133: *"Only an issued or paid bill can be corrected."* A draft, a void
    and a corrected bill in the same run are not drawn."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        an_issued_bill(brazos, account, run, invoice_no="BL-2607-000601")
        an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000602", status=models.INVOICE_PAID
        )
        an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000603", status=models.INVOICE_DRAFT
        )
        an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000604", status=models.INVOICE_VOID
        )
        an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-000605", status=models.INVOICE_CORRECTED
        )
        as_tuple = bulk_corrections.resolve_scope(kind="run", bill_run_id=run.pk)
        # Last, because `api_call` enters and LEAVES its own tenant context.
        response = _resolve(brazos, dana, scope_kind="run", bill_run_id=str(run.pk))

    numbers = [row["invoice_no"] for row in response.data["results"]]
    assert numbers == ["BL-2607-000601", "BL-2607-000602"]
    assert [bill.invoice_no for bill in as_tuple] == numbers, "one filter, two shapes"
    assert response.data["totals"]["bills"] == 2


def test_lane_b_tc6__a_scope_that_names_nothing_or_names_garbage_is_refused_with_a_sentence(
    brazos, dana
):
    """Before this change a run scope with no run matched `bill_run_id IS NULL`
    and a non-uuid id reached the database. Both refuse at the door, as a 422
    the catalogue resolves (`billing.correction.refused`), never a 500."""
    with tenant_ctx(brazos):
        missing = _resolve(brazos, dana, scope_kind="run")
        garbage = _resolve(brazos, dana, scope_kind="cycle", cycle_id="not-an-id")
        unknown = _resolve(brazos, dana, scope_kind="postcode")

    for response in (missing, garbage, unknown):
        assert response.status_code == 422, response.data
        assert response.data["message_key"] == "billing.correction.refused"
    assert "names the bill_run_id" in missing.data["params"]["detail"]
    assert "not an id this product issues" in garbage.data["params"]["detail"]
    assert "unknown correction scope" in unknown.data["params"]["detail"]


def test_lane_b_tc7__the_route_is_mounted_and_is_not_read_as_a_case_id(brazos):
    """`corrections/resolve` sits before `corrections/<case_id>`; a build that
    registered them the other way round would 404 the table as a missing case."""
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/corrections/resolve")
    # `@api_view` wraps the function in a class that borrows its name.
    assert match.func.cls.__name__ == "correction_scope_resolve", match.func


def test_lane_b_tc8__a_single_scope_resolves_one_bill_by_id(brazos, dana):
    """US-BIL-015's one-bill case enters by the same door (`invoice_id`)."""
    with tenant_ctx(brazos):
        run, (paid, _, _) = _p133_run(brazos, dana)
        response = _resolve(brazos, dana, scope_kind="single", invoice_id=str(paid.pk))

    assert response.status_code == 200
    (row,) = response.data["results"]
    assert row["invoice_id"] == str(paid.pk) and row["state"] == bulk_corrections.STATE_PAID
    assert response.data["totals"] == {
        "bills": 1,
        "amount": response.data["totals"]["amount"],
        "paid": response.data["totals"]["paid"],
        "currency": "USD",
        # CR-180-BRC10 contract A1 — the totals row counts accounts too.
        "accounts": 1,
    }
    assert Decimal(response.data["totals"]["paid"]) == Decimal("241.80")


def test_lane_b_tc9__another_tenants_run_resolves_to_nothing_here(brazos, lonestar, dana, erin):
    """Hard rule 1. Lone Star's run, asked for under Brazos Bend, is empty —
    and the payments read never sees the other tenant's allocations either."""
    with tenant_ctx(lonestar):
        from tests.test_us_bil_015_single_correction import a_water_account

        account = a_water_account(erin, lonestar)
        run = a_run(lonestar, key="2026-07|cycle-A")
        an_issued_bill(lonestar, account, run, invoice_no="LSR-2607-000001")
    with tenant_ctx(brazos):
        response = _resolve(brazos, dana, scope_kind="run", bill_run_id=str(run.pk))

    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["totals"]["bills"] == 0
    assert Decimal(response.data["totals"]["amount"]) == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-101-BRC03 §06 (05-prototype/04 Billing, As Built.pdf p129–p144,
#         read as images; p133 has no text layer) · 04-docs/05-modules/
#         07-billing/02-business-rules.md BR-BIL-014/072 · 04-docs/05-modules/
#         08-payments/02-business-rules.md BR-PAY-010/031 · 04-docs/05-modules/
#         07-billing/conformance/CR-101-BRC03-step2-06-lane-B-backend.md
# generated: 2026-09-15 by the CR-101-BRC03 §06 lane B (backend) — Fable 5.1
# checklist: A✔ B✔ C✔ D✔ E=deferred(lane A owns 07-frontend/src/features/billing;
#         the TypeScript types landed in api/billingOpsEndpoints.ts) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 rows in 12-governance/09-human-review-
#         ledger.md for bulk_corrections.py and payments_seam.py)
# gates: RED PROVED FIRST — run against the tip 9cda92e6 extracted into a
#         scratch tree: all nine failed (`AttributeError: … has no attribute
#         'correction_scope_resolve'` on eight, `resolve_scope_queryset` absent
#         on the ninth); green here after the read landed (9/9). The same table was then walked through
#         `GET /api/brazosbend/corrections/resolve` against PostgreSQL 16 and
#         the seeded demo tenant (conformance file §5).
# exceptions: reads only, no catch-and-continue on the path (law 14 does not
#         bind) — and this file was nevertheless RUN ON POSTGRESQL 16 as well,
#         under config.settings.local against a fresh test database (9/9,
#         2026-09-15), because `amount_asked_expression`'s JSON key transform,
#         the paid total's `IN (subquery)` and the aggregates are SQL the
#         default SQLite suite cannot vouch for. Both engines green.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
