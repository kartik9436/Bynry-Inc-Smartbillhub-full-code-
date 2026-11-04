# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-025 (S30 All-bills list — search, segments, sorts, the
#           header roll-up) · US-BIL-026 (S30 bill detail — stamped lines, the
#           A19 summary box, the correction chain)
#           Screens: S30 · S21 (the Bills tab is the same list, `f.account_id`)
# Rules:    BR-BIL-004 (issued history is immutable — this surface is READ-only)
#           · BR-BIL-010 (a line shows the STAMPED GL, never today's mapping) ·
#           BR-BIL-024 (the due date is derived at issue; a draft has none) ·
#           BR-BIL-026 (the template version pinned at issue) · BR-BIL-030 (the
#           document instance is locked at issue — `has_payload`, never the
#           payload) · BR-BIL-031 (payload_version is a different axis) ·
#           BR-BIL-063 (the number is allocated when the DRAFT is created) ·
#           BR-SHL-011 (list grammar q/sort/dir/page/per/f.<name>) ·
#           BR-TEN-003 (cross-tenant is a 404, never a 403) · BR-TEN-043
#           (event-time law — "today" is the tenant's clock, not a wall clock)
# ───────────────────────────────────────────────────────
"""`GET /invoices` and `GET /invoices/{id}` — the two reads S30 was built against.

WHY THIS FILE IS MOSTLY ABOUT WHAT IS **NOT** SERVED. The screens exist; the
endpoints did not, and the failure that produced this lane is hard-won law 2
read from the other end. The easy way to make them green is to fill every field
with something plausible: `past_due: false` because the due date has not passed,
a `document_url` pointing at a route nobody mounted, `deliveries: []` because
there is no delivery table. Each of those is a sentence about a customer's money
that no row in this database supports, and each would pass a shape test.

So the assertions that matter here are the negative ones:

  * `past_due` is **null on every row**, because "unpaid" is the payments/ledger
    position and those modules have no tables. A comparison of `due_date` to a
    clock would report a PAID bill as past due, and `timezone.now()` is banned
    in a money path anyway (BR-TEN-043 / gate G6).
  * a DRAFT carries its **number** (BR-BIL-063, PO 2026-08-11) and carries no
    issue date, no due date and no template pin.
  * the detail exposes `has_payload` as a BOOLEAN and no key named
    `bill_payload` anywhere — two lanes guessing one JSON schema is DEF-014.
  * `deliveries` was **null and not `[]`** until 2026-08-16, because an empty
    array claims this bill was never sent and that is a different statement
    from "nobody looked". ⚠ **THE READ EXISTS NOW** (US-BIL-024) and the
    distinction is REAL rather than a stand-in: `[]` means the queue was asked
    and holds nothing — true of a draft, since queueing happens at issue — and
    `None` means notifications publishes no read and nobody can say. The rule
    is unchanged and is asserted where it can now bite, in
    `tests/test_us_bil_024_deliveries.py::…tc3`, which makes the queue genuinely
    unreachable and requires `None`.
  * an unknown id and another tenant's id are ONE answer, byte-identical (HR-1).

The route-mounting case is deliberately here rather than in a wiring lane: an
`api.py` with `urlpatterns` that `config/urls.py` never includes is exactly the
defect this whole task exists to fix, and it passes every other test in the file.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors
from core import errors

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)
from tests.test_w3_billing_models import a_cycle, a_run

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — the US-BIL-025 §4 world, small enough to assert exactly
# ══════════════════════════════════════════════════════════════════════════
def an_account(
    tenant, actor, *, account_no="A-10432", contact_name=None, label="Unit A", service="electric"
):
    """One account on its own unit, optionally with a primary contact.

    The contact is what `customer_name` reads (BR-CUS-054's `customers` entity
    is PROPOSED-SCHEMA and not built), so a name search has to have one to find.

    `service` is a parameter because the isolation tenant (Lone Star Ridge) has
    only Water enabled and BR-TEN-026 refuses a service point on a service the
    tenant never turned on — the two tenants are deliberately not identical.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="1901 Bluestem Ln", services_available=[service])
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    status = customer_models.AccountStatus.objects.filter(tenant=tenant).first()
    account_type = customer_models.AccountType.objects.first()
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=status,
        account_type=account_type,
        account_no=account_no,
    )
    if contact_name is not None:
        customer_models.Contact.objects.create(
            tenant=tenant, account=account, full_name=contact_name, is_primary=True
        )
    return account


def an_invoice(tenant, account, **overrides):
    values = dict(
        tenant=tenant,
        account=account,
        invoice_no="BL-2608-018410",
        bill_type="cycle",
        status=billing_models.INVOICE_ISSUED,
        service_date=date(2026, 7, 31),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        due_date=date(2026, 8, 25),
        issued_at=datetime(2026, 8, 8, 9, 42, tzinfo=timezone.utc),
        subtotal=Decimal("226.90"),
        tax_total=Decimal("20.97"),
        total=Decimal("247.87"),
        currency="USD",
        template_version=3,
        payload_version=1,
        bill_payload={"customer_name": "Miller, Sarah"},
    )
    values.update(overrides)
    return billing_models.Invoice.objects.create(**values)


def a_draft(tenant, account, **overrides):
    """BR-BIL-063: a draft HAS its number. It has nothing that comes from issue."""
    values = dict(
        invoice_no="BL-2608-018320",
        status=billing_models.INVOICE_DRAFT,
        due_date=None,
        issued_at=None,
        template_version=None,
        bill_payload=None,
        total=Decimal("145.70"),
    )
    values.update(overrides)
    return an_invoice(tenant, account, **values)


def a_line(tenant, invoice, account, **overrides):
    values = dict(
        tenant=tenant,
        invoice=invoice,
        account=account,
        kind="usage",
        description="Electric usage 684 kWh",
        quantity=Decimal("684"),
        unit="kWh",
        unit_price=Decimal("0.12"),
        amount=Decimal("82.08"),
        taxable=True,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
    )
    values.update(overrides)
    return billing_models.InvoiceLine.objects.create(**values)


def listed(tenant, **query):
    return api_call(
        billing_api.invoices,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query=query or None,
    )


def detail_of(tenant, invoice_id, role="billing_clerk"):
    return api_call(
        billing_api.invoice_item,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        invoice_id=str(invoice_id),
    )


def ids_of(response):
    return [row["id"] for row in response.data["results"]]


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-025 — the S30 list
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_025_tc1__the_invoice_routes_are_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer, and the defect that opened this lane.

    `apps/billing/api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it. The S30 screens 404'd against a file that
    looked finished. This resolves the REAL paths through the REAL root
    URLconf, so a forgotten one-line include goes red here.
    """
    from django.urls import resolve

    assert resolve("/api/brazosbend/invoices").func is billing_api.invoices
    assert resolve(f"/api/brazosbend/invoices/{brazos.id}").func is billing_api.invoice_item


def test_us_bil_025_tc1__the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request, through the real
    middleware and the real authentication, actually ARRIVES at these views.

    `resolve()` above proves the URLconf knows the path. It does not prove a
    request can get there — the tenant middleware, the session authentication
    and the permission class all sit in front, and any one of them answering
    404 would leave S30 exactly as broken as it was. So an UNAUTHENTICATED call
    is made and its refusal is read: 401 AUTH-001 means the route exists and
    asked for a session; 404 means there is no route (which is precisely what
    both paths answered before this lane, and what the screens were reporting).
    """
    from django.test import Client

    for path in (
        f"/api/{brazos.subdomain}/invoices",
        f"/api/{brazos.subdomain}/invoices/{uuid.uuid4()}",
    ):
        response = Client().get(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means the route "
            "is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


def test_us_bil_025_tc1__the_list_serves_the_s30_row_and_an_honest_rollup(brazos, dana):
    """US-BIL-025 §5 + the 11b §2.8a body contract, field for field.

    Every name here is the one `07-frontend/src/api/endpoints.ts` declares. A
    rename on either side is a broken screen, so the row's key set is asserted
    exactly rather than sampled.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        an_invoice(brazos, account, bill_run=run)
        response = listed(brazos)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert set(response.data) == {"count", "next", "previous", "results", "rollup"}
    row = response.data["results"][0]
    assert set(row) == {
        "id",
        "invoice_no",
        "bill_type",
        "status",
        "past_due",
        "account_id",
        "account_no",
        "customer_name",
        "cycle_label",
        # `CR-105-BRC03` — the cycle's NAME beside its code, so the bill
        # detail can say "Silver Creek — monthly" where the printed bill
        # already does and this payload said `CY-007`. Additive: nothing
        # reading `cycle_label` moves.
        "cycle_name",
        "bill_run_id",
        "service_date",
        "period_start",
        "period_end",
        "issued_at",
        "due_date",
        "subtotal",
        "tax_total",
        "total",
        "currency",
        "template_version",
    }
    assert row["invoice_no"] == "BL-2608-018410"
    assert row["bill_type"] == "cycle"
    assert row["status"] == "issued"
    assert row["account_no"] == "A-10432"
    assert row["customer_name"] == "Miller, Sarah"
    assert row["cycle_label"] == "06-A"  # bill_runs.cycle_id -> metering (B1)
    assert row["service_date"] == "2026-07-31"
    assert row["period_start"] == "2026-07-01"
    assert row["period_end"] == "2026-07-31"
    assert row["due_date"] == "2026-08-25"
    assert row["issued_at"].startswith("2026-08-08T09:42")
    # CLAUDE.md rule 2: NUMERIC(18,6) DECIMAL STRINGS with their CHAR(3) partner.
    assert (row["subtotal"], row["tax_total"], row["total"]) == (
        "226.900000",
        "20.970000",
        "247.870000",
    )
    assert row["currency"] == "USD"
    assert row["template_version"] == 3

    rollup = response.data["rollup"]
    assert set(rollup) == {
        "bills",
        "billed_this_cycle",
        "billed_currency",
        "unresolved_from_last_run",
    }
    assert rollup["bills"] == 1
    # NOT COMPUTED, never zero: no signed document defines "this cycle" for this
    # header, and a money KPI on a guessed definition is a claim about money.
    assert rollup["billed_this_cycle"] is None
    assert rollup["billed_currency"] is None
    assert rollup["unresolved_from_last_run"] == 0


def test_us_bil_025_tc1__a_draft_carries_its_number_and_nothing_issue_stamps(brazos, dana):
    """BR-BIL-063 (PO ruling 2026-08-11): *"Give a running number always even
    for Draft"*. The number is allocated when the draft is CREATED.

    Everything that comes from ISSUE is still absent, and each absence is a
    different statement: no issue date, no due date (BR-BIL-024 derives it at
    issue), no template pin (BR-BIL-026), no stamped document (BR-BIL-030).
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_draft(brazos, account)
        row = listed(brazos).data["results"][0]

    assert row["status"] == "draft"
    assert row["invoice_no"] == "BL-2608-018320"  # NOT null — this changed 2026-08-11
    assert row["issued_at"] is None
    assert row["due_date"] is None
    assert row["template_version"] is None


def test_us_bil_025_tc2__past_due_is_served_null_and_never_derived_from_a_clock(brazos, dana):
    """`past_due` = issued ∧ **unpaid** ∧ due_date < today.

    Two of the three terms are unavailable: "unpaid" is the payments/ledger
    position and NEITHER module has a table, and "today" is the TENANT's clock
    (BR-TEN-043), not this process's. So the server serves null — "unknown" —
    and the screen renders the reason.

    The bill below is issued with a due date in 2026 and would be reported past
    due by any wall-clock comparison. It might also be paid in full. Saying
    either would be a claim about a customer's money that no row supports.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        an_invoice(brazos, account, due_date=date(2020, 1, 1))
        row = listed(brazos).data["results"][0]

    assert row["status"] == "issued"
    assert row["past_due"] is None, (
        "past_due must be NULL until payments/ledger exist — a due date in the "
        "past does not make a bill past due, it may have been paid"
    )
    assert billing_selectors.PAST_DUE_UNAVAILABLE == "BR-TEN-043"


def test_us_bil_025_tc2__search_covers_bill_number_account_number_and_customer_name(brazos, dana):
    """IS-3 / the US-BIL-025 capability row: "bill #, account #, customer name".

    Three legs, three sources: the invoice's own column, the reviewed
    `invoices.account_id` FK edge, and customers' published read (B1 — billing
    never queries `contacts`).
    """
    with tenant_ctx(brazos):
        miller = an_account(brazos, dana, account_no="A-10432", contact_name="Miller, Sarah")
        okafor = an_account(
            brazos, dana, account_no="A-77281", contact_name="Okafor, Jane", label="Unit B"
        )
        first = an_invoice(brazos, miller, invoice_no="BL-2608-018410")
        second = an_invoice(brazos, okafor, invoice_no="BL-2608-090001")

        assert ids_of(listed(brazos, q="018410")) == [str(first.id)]  # bill #
        assert ids_of(listed(brazos, q="77281")) == [str(second.id)]  # account #
        assert ids_of(listed(brazos, q="Miller")) == [str(first.id)]  # customer name
        assert ids_of(listed(brazos, q="nothing-matches-this")) == []


def test_us_bil_025_tc2__the_declared_filters_narrow_and_undeclared_ones_are_ignored(brazos, dana):
    """The `INVOICE_FILTERS` vocabulary the frontend declares, each proved to
    narrow. BR-SHL-011: an UNDECLARED filter is ignored, never an error."""
    with tenant_ctx(brazos):
        run = a_run(brazos)
        other_cycle = a_cycle(brazos, code="07-B")
        other_run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=other_cycle,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            idempotency_key="2026-07|cycle-2",
        )
        account = an_account(brazos, dana)
        other_account = an_account(brazos, dana, account_no="A-99999", label="Unit B")
        issued = an_invoice(brazos, account, bill_run=run)
        draft = a_draft(
            brazos,
            other_account,
            bill_run=other_run,
            bill_type="final",
            invoice_no="BL-2608-018320",
        )

        assert ids_of(listed(brazos, **{"f.status": "issued"})) == [str(issued.id)]
        assert ids_of(listed(brazos, **{"f.bill_type": "final"})) == [str(draft.id)]
        assert ids_of(listed(brazos, **{"f.cycle_id": str(other_cycle.id)})) == [str(draft.id)]
        assert ids_of(listed(brazos, **{"f.bill_run_id": str(run.id)})) == [str(issued.id)]
        assert ids_of(listed(brazos, **{"f.account_id": str(account.id)})) == [str(issued.id)]
        assert ids_of(listed(brazos, **{"f.issued_from": "2026-08-01"})) == [str(issued.id)]
        assert ids_of(listed(brazos, **{"f.issued_to": "2026-08-01"})) == []
        # Undeclared → ignored (both rows come back), never a 4xx.
        undeclared = listed(brazos, **{"f.plan": "RES-STD"})
        assert undeclared.status_code == 200
        assert set(ids_of(undeclared)) == {str(issued.id), str(draft.id)}


def test_us_bil_025_tc2__the_past_due_segment_refuses_rather_than_guessing(brazos, dana):
    """The prototype's segment strip carries a `past_due` value the server
    cannot resolve, and every silent answer to it is false.

    Returning the issued rows says "these are past due"; returning none says
    "there are none". Both are statements about customers' money made with no
    payments module in the database. So this ONE filter value refuses, naming
    the rule — a deliberate, reported deviation from BR-SHL-011's "a list URL
    never errors over its params", taken because the alternatives lie.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        an_invoice(brazos, account, due_date=date(2020, 1, 1))
        response = listed(brazos, **{"f.status": "past_due"})

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-TEN-043"


def test_us_bil_025_tc1__the_default_sort_is_issue_date_desc_and_every_sort_narrows(brazos, dana):
    """IS-2 / the capability row: default `issue_date` desc, sortable on bill #,
    issue date, due date, total and status.

    A default of ASC would put the oldest of 7,240 bills on page 1 — the newest
    bill is the one a clerk is looking at, and a draft run is the newest thing
    there is, so an unissued draft sorts FIRST under the default.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        older = an_invoice(
            brazos,
            account,
            invoice_no="BL-2608-000001",
            issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            due_date=date(2026, 7, 20),
            total=Decimal("10.00"),
            status=billing_models.INVOICE_PAID,
        )
        newer = an_invoice(
            brazos,
            account,
            invoice_no="BL-2608-000002",
            issued_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
            due_date=date(2026, 8, 25),
            total=Decimal("999.00"),
        )
        draft = a_draft(brazos, account, invoice_no="BL-2608-000003")

        # No params at all: the ratified default, not the parser's asc fallback.
        assert ids_of(listed(brazos)) == [str(draft.id), str(newer.id), str(older.id)]
        assert ids_of(listed(brazos, sort="invoice_no", dir="asc")) == [
            str(older.id),
            str(newer.id),
            str(draft.id),
        ]
        assert ids_of(listed(brazos, sort="total", dir="desc"))[0] == str(newer.id)
        assert ids_of(listed(brazos, sort="due_date", dir="asc"))[0] == str(older.id)
        assert ids_of(listed(brazos, sort="status", dir="asc"))[0] == str(draft.id)
        # BR-SHL-011: an unknown sort falls back to the default, never 4xxs.
        assert listed(brazos, sort="nonsense").status_code == 200


def test_us_bil_025_tc1__the_page_envelope_and_its_ratified_page_sizes(brazos, dana):
    """A11 Addendum r2: 50/100/200/500/1000, default 50; `per` clamps DOWN and
    a list URL never errors over it (BR-SHL-011)."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        for index in range(3):
            an_invoice(brazos, account, invoice_no=f"BL-2608-00000{index}")

        default_page = listed(brazos)
        assert default_page.data["count"] == 3
        assert default_page.data["next"] is None and default_page.data["previous"] is None
        # 75 is between steps: it clamps DOWN to 50, never up.
        assert len(ids_of(listed(brazos, per="75"))) == 3
        assert listed(brazos, per="nonsense", page="9999").status_code == 200


def test_us_bil_025_tc7__the_list_and_the_detail_are_tenant_scoped(brazos, lonestar, dana, erin):
    """US-BIL-025 TC-7 / US-BIL-026 TC-6, app-layer half. The RLS half is the
    isolation case at the foot of this file."""
    with tenant_ctx(brazos):
        bb_account = an_account(brazos, dana)
        bb_invoice = an_invoice(brazos, bb_account)
    with tenant_ctx(lonestar):
        lsr_account = an_account(lonestar, erin, account_no="LSR-1001", service="water")
        lsr_invoice = an_invoice(lonestar, lsr_account, invoice_no="LSR-2608-000102")

        assert ids_of(listed(lonestar)) == [str(lsr_invoice.id)]
        # The other tenant's bill number finds nothing, even searched exactly.
        assert ids_of(listed(lonestar, q="BL-2608-018410")) == []

    cross = detail_of(lonestar, bb_invoice.id)
    assert cross.status_code == 404


def test_us_bil_026_tc6__an_unknown_id_and_a_cross_tenant_id_are_one_answer(
    brazos, lonestar, dana, erin
):
    """HR-1 / 11b G4: existence must not leak, so the two bodies are IDENTICAL
    apart from the per-request trace id. Comparing them field by field is the
    only way to prove it — a status-code check would pass on a body that named
    the difference."""
    with tenant_ctx(brazos):
        bb_invoice = an_invoice(brazos, an_account(brazos, dana))

    cross_tenant = detail_of(lonestar, bb_invoice.id)
    unknown = detail_of(lonestar, uuid.uuid4())
    malformed = detail_of(lonestar, "not-a-uuid")

    for response in (cross_tenant, unknown, malformed):
        assert response.status_code == 404
        assert response.data["code"] is None  # 404 has no B12 §3 catalog code
    assert {k: v for k, v in cross_tenant.data.items() if k != "trace_id"} == {
        k: v for k, v in unknown.data.items() if k != "trace_id"
    }


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-026 — the bill detail
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_026_tc1__the_detail_carries_the_row_plus_its_stamped_lines(brazos, dana):
    """US-BIL-026 §5: every `invoice_line` with quantity/unit/unit-price/amount,
    the taxable flag, the STAMPED GL (BR-BIL-010) and the tariff version."""
    gl_account = "3f1a5a3e-1a4b-4c2d-9e77-0f1c2d3e4a5b"
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        invoice = an_invoice(brazos, account)
        a_line(brazos, invoice, account, gl_account_id=gl_account)
        a_line(
            brazos,
            invoice,
            account,
            kind="tax",
            description="State + local tax",
            quantity=None,
            unit=None,
            unit_price=None,
            amount=Decimal("20.97"),
            taxable=False,
        )
        response = detail_of(brazos, invoice.id)

    assert response.status_code == 200
    body = response.data
    # The detail is the ROW plus the detail-only keys — one shape, not two.
    assert body["invoice_no"] == "BL-2608-018410"
    assert body["customer_name"] == "Miller, Sarah"
    assert set(body) - {
        "id",
        "invoice_no",
        "bill_type",
        "status",
        "past_due",
        "account_id",
        "account_no",
        "customer_name",
        "cycle_label",
        # `CR-105-BRC03` — the cycle's NAME beside its code, so the bill
        # detail can say "Silver Creek — monthly" where the printed bill
        # already does and this payload said `CY-007`. Additive: nothing
        # reading `cycle_label` moves.
        "cycle_name",
        "bill_run_id",
        "service_date",
        "period_start",
        "period_end",
        "issued_at",
        "due_date",
        "subtotal",
        "tax_total",
        "total",
        "currency",
        "template_version",
    } == {
        "lines",
        "payload_version",
        "has_payload",
        "document_url",
        "summary",
        "credit_notes",
        "rebill_of_invoice_id",
        "corrected_by_invoice_id",
        "adjustments",
        "deliveries",
        # Added 2026-08-16 (billing-9 lane, US-BIL-030): BR-BIL-032's tie-out
        # and BR-BIL-011's balanced handoff, answered for THIS bill. Both were
        # computed only inside their own test file until that day, so "drift can
        # never be silent" was enforced against fixtures and against no real
        # bill. This key set is asserted EXACTLY on purpose — that is why adding
        # it had to be a deliberate edit here and not a silent contract growth.
        "integrity",
        # Added 2026-08-11 (budget-billing lane, US-BIL-019): the three WE-8
        # columns and the running variance balance, null on an ordinary bill.
        # The set is asserted EXACTLY on purpose — a detail key that appears
        # without a test noticing is a contract that grew in the dark.
        "budget",
        # Added 2026-08-30 (CR-053 task 9): what this bill charged PER SERVICE,
        # plus the bill-level bucket every tax and fee lands in and a tie-out
        # against `invoices.total`. 🔒 money — the subtotal is Σ of the ROUNDED
        # line amounts (B4.4 + B4's 2026-08-11 ruling), so the printed lines
        # foot against the printed subtotal. This assertion is exactly why the
        # key had to be added here on purpose: it went RED the moment the
        # selector started serving it, which is the contract growing in the
        # light. Shape and figures: tests/test_cr053_charges_tab_backend.py.
        "charges_by_service",
        # ⚠ **ADDED 2026-09-14 (`DEF-BIL-5291`) — AND IT IS SIX DAYS LATE.**
        # `_taxes_by_authority` has been in this payload since `faf130c5`
        # (2026-09-08, `git blame selectors.py:2250`) and this set never grew
        # with it, so the case above has been RED ever since. The comments on
        # the four keys before this one each say the assertion is exact ON
        # PURPOSE, *"which is the contract growing in the light"* — and it only
        # grows in the light if somebody reads the red. Found by a lane adding
        # `cycle_name` to the same payload and running this file. The bill's
        # tax lines grouped a SECOND way, on the axis a remittance return is
        # filed on (PO 2026-08-31, closing `OQ-1190`).
        "taxes_by_authority",
    }

    usage, tax = body["lines"]
    assert set(usage) == {
        "id",
        "kind",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "amount",
        "taxable",
        "gl_account_id",
        "gl_account_code",
        # DEF-937, 2026-08-27. `gl_account_code` alone is "4110", a number a
        # clerk still has to go and look up; the NAME beside it is what makes
        # the column's own footnote — *"the accounting code … recorded when the
        # bill was issued"* — a promise this product can keep. Added as a
        # deliberate edit here, because this set is asserted EXACTLY so that a
        # detail key cannot appear without a test noticing.
        "gl_account_name",
        "tariff_version_id",
        "tariff_version_label",
        "service",
        # CR-053 task 7, 2026-08-30. Both columns were REAL and WRITTEN and
        # neither reached the Charges tab, so the screen could not say which
        # authority levied a tax (BR-BIL-069 — on the reference bill one $8.30
        # line is three authorities and three returns to file) nor which charge
        # code produced a fee (BR-BIL-010). Serialization of stored facts only.
        # The same ID-plus-label pairing `gl_account_*` uses above: the id is
        # the stored fact and is always served; the label is resolved live and
        # is null when nobody can answer. `charge_code`/`charge_name` are null
        # TODAY because rating publishes no charge-id → code read (DEF-2428).
        "tax_id",
        "tax_authority",
        "charge_id",
        "charge_code",
        "charge_name",
        "period_start",
        "period_end",
        # 2026-09-30, added deliberately by the billing red triage of
        # 2026-10-01: a line names the METER it priced (PO 2026-09-30: two
        # meters on one service bill as two lines — `31358c239` stores
        # `invoice_lines.asset_id`, `5c2bc32e2` serves it with its label).
        # Red from that commit until today.
        "asset_id",
        "asset_label",
    }
    assert usage["kind"] == "usage"
    # A usage line names no tax and no charge code, and that absence is BY
    # CONSTRUCTION rather than a gap: `assemble_document` stamps a tax with its
    # authority and a fee with its code, and a usage line is neither.
    assert usage["tax_id"] is None
    assert usage["charge_id"] is None
    assert usage["quantity"] == "684.000000"
    assert usage["unit"] == "kWh"  # CLAUDE.md rule 3 — never a bare number
    assert usage["unit_price"] == "0.120000"
    assert usage["amount"] == "82.080000"
    assert usage["taxable"] is True
    assert usage["gl_account_id"] == gl_account  # BR-BIL-010: the STAMP
    # ⚠ **THESE THREE ASSERTED `None` AND THE COMMENTS BESIDE THEM WERE THE
    # DEFECT (DEF-937, CR-043 finding 3).** *"`ledger_accounts` is W5"* was true
    # when written and W5 landed; *"rating stores no version label"* is still
    # true and does not mean there is nothing honest to print. Meanwhile the
    # Charges tab printed the raw uuid at a clerk on every line of every bill.
    #
    # They stay `None` HERE and the assertion is now explicit about WHY: this
    # fixture's line carries a `gl_account_id` that is not a row in this
    # tenant's chart, and no `tariff_version_id` at all. That is the honest
    # fallback path — an id whose label cannot be resolved keeps its id — and it
    # is worth holding, because it is what stops a deleted chart row blanking a
    # column headed ACCOUNTING CODE. The RESOLVED path is asserted in
    # `tests/test_cr043_line_labels.py`, against real ledger and rating rows.
    assert usage["gl_account_code"] is None  # this id is not a row in the chart
    assert usage["gl_account_name"] is None
    assert usage["tariff_version_id"] is None
    assert usage["tariff_version_label"] is None  # no version stamped on this line
    assert tax["kind"] == "tax"
    assert (tax["quantity"], tax["unit"], tax["unit_price"]) == (None, None, None)


def test_us_bil_026_tc1__the_detail_reports_the_payload_and_never_opens_it(brazos, dana):
    """BR-BIL-030/031 + 11b §2.8a point 3. No signed document names the JSON
    keys inside `bill_payload`, and BR-BIL-026 puts the render on the SERVER, so
    the detail exposes a BOOLEAN and links nothing it has not built.

    A `bill_payload` key in this response would be two lanes guessing one schema
    — DEF-014 wearing a different hat.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        issued = an_invoice(brazos, account)
        draft = a_draft(brazos, account)
        issued_body = detail_of(brazos, issued.id).data
        draft_body = detail_of(brazos, draft.id).data

    assert issued_body["has_payload"] is True
    assert issued_body["payload_version"] == 1
    assert draft_body["has_payload"] is False  # the trigger requires one AT issue
    # The ONLY payload-shaped keys are the boolean and the version. Anything
    # else here would be a second lane's guess at the frozen instance's schema.
    assert [key for key in issued_body if "payload" in key] == [
        "payload_version",
        "has_payload",
    ]
    # ⚠ WAS `is None` WITH THE COMMENT *"`GET /invoices/{id}/document` is not
    # mounted, so a URL here would be a link to a 404"*, and that had been FALSE
    # — and this assertion FAILING — since the route landed on 2026-08-16.
    # Invisible, because no gate runs a full pytest (DEF-155). The link is
    # DERIVED from the BR-BIL-026 pin, so an issued bill has one and a DRAFT
    # still answers null: a bill with no pin has no document to render, and
    # serving a link that answers 422 would put a broken control on the detail
    # screen of every draft. Both halves asserted, because the null is the half
    # that keeps a dead link off the screen.
    assert issued_body["document_url"] == f"/invoices/{issued.pk}/document"
    assert draft_body["document_url"] is None


def test_us_bil_026_tc1__the_a19_summary_serves_what_it_has_and_nulls_the_rest(brazos, dana):
    """A19 / US-BIL-026 §7: `previous balance − payments/credits + current
    charges = total due`.

    `current_charges` is this bill's own total and is served. The other three
    are BR-BIL-035's stamped block, read straight off the bill's frozen payload
    — and null here because THIS FIXTURE IS AN UNSTAMPED BILL (`an_invoice`
    writes the row directly rather than issuing it, so nothing ever ran
    `issue._stamp_balance_forward`). That case is real in the product too: a
    draft, and an issued bill whose payments seam was unreachable, both carry
    no block and both must render an absence. **Never 0.00**, which would tell a
    customer in arrears that they are square.

    ⚠ AMENDED 2026-08-16 (DEF-127). This case used to prove the nulls were
    UNCONDITIONAL — *"the other three need the ledger/payments position (B1)"* —
    and that had stopped being true on 2026-08-15, when DEF-116 started stamping
    the figures at issue. The read model went on answering null off a payload
    carrying 108.880000, so the bill screen printed an em-dash. The STAMPED path
    is asserted in tests/test_def_127_one_account_one_figure.py::…tc3; this one
    now pins the other half — that an unstamped bill still refuses to invent
    the figures.
    """
    with tenant_ctx(brazos):
        invoice = an_invoice(brazos, an_account(brazos, dana))
        assert "balance_forward" not in (invoice.bill_payload or {}), (
            "this case is ABOUT an unstamped bill; if the fixture starts issuing "
            "properly, assert the stamped figures instead of loosening this"
        )
        summary = detail_of(brazos, invoice.id).data["summary"]

    assert summary == {
        "previous_balance": None,
        "payments_credits": None,
        "current_charges": "247.870000",
        "total_due": None,
        # DEF-099 / CLAUDE.md rule 2 — the summary carries the CHAR(3) its
        # figures are in even when three of the four are absent: the currency is
        # the BILL's own frozen column and cannot be missing.
        "currency": "USD",
        # BR-BIL-035's window, stamped ON the bill (OQ-217, ruled 2026-10-01). Null here
        # because this bill carries no block at all — not a default.
        "basis": None,
        "basis_oq": None,
        # PO ruling 2026-08-11 (*"Level is due"*): what the bill ASKS FOR.
        # On an ordinary bill that is the total, and this fixture is one — the
        # budget case is asserted in tests/test_us_bil_019_budget_bill.py, where
        # the same bill totals 292.87 and asks for 242.00.
        "amount_due": "247.870000",
    }


def test_us_bil_026_tc3__the_correction_chain_is_served_and_deliveries_are_read(brazos, dana):
    """WE-9's chain, and the one field that must not be smoothed.

    `credit_notes` and `adjustments` have TABLES, so an empty list there is a
    served fact. `deliveries` is null — an empty array would tell a clerk this
    bill was never sent when the truth is that nobody looked. CORRECTED
    2026-08-11: this used to say the queue has NO table, and it has one
    (`outbound_messages`, r12 #16) which issue writes to; what did not exist was
    the READ (US-BIL-024). ⚠ **AMENDED 2026-08-16 — THE READ EXISTS**, so this
    bill answers `[]` rather than `None`: it was built by hand and never issued,
    so nothing ever queued it, and the queue saying "nothing for this bill" is
    the truth. The RULE this case used to carry — an empty array must never
    stand in for an unanswerable question — is unchanged and now has a case that
    can actually bite it (`test_us_bil_024_deliveries.py::…tc3`), which removes
    the published selector and requires `None`.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        invoice = an_invoice(brazos, account)
        billing_models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=invoice,
            credit_note_no="CN-2608-000004",
            # NEGATIVE since DEF-085 / BR-BIL-074 (billing/0020) — see there.
            amount=Decimal("-247.87"),
            currency="USD",
            reason="misread",
        )
        billing_models.Adjustment.objects.create(
            tenant=brazos,
            account=account,
            invoice=invoice,
            direction="credit",
            amount=Decimal("25.00"),
            currency="USD",
            reason_code="goodwill",
        )
        body = detail_of(brazos, invoice.id).data

    assert [note["credit_note_no"] for note in body["credit_notes"]] == ["CN-2608-000004"]
    # ⚠ NEGATIVE since DEF-085 / BR-BIL-074 (billing migration 0020), and this
    # assertion had been asserting the pre-ruling sign. The fixture six lines
    # above already writes `Decimal("-247.87")` with that rule named beside it;
    # only this line had not caught up, and it had been FAILING rather than
    # protecting anything — invisible because no gate runs a full pytest
    # (DEF-155). A credit note reduces what is owed, so its amount is signed.
    assert body["credit_notes"][0]["amount"] == "-247.870000"
    assert [row["reason_code"] for row in body["adjustments"]] == ["goodwill"]
    # `[]` and not `None`: this bill was never issued, so nothing queued it and
    # the queue is answering. `None` is reserved for a queue that cannot be
    # asked at all — asserted in test_us_bil_024_deliveries.py::…tc3.
    assert body["deliveries"] == []
    # No column carries either citation yet (EP-BIL-04, W5) — null, not omitted.
    assert body["rebill_of_invoice_id"] is None
    assert body["corrected_by_invoice_id"] is None


def test_us_bil_026_tc5__the_read_surface_offers_no_write_verb(brazos, dana):
    """BR-BIL-004 / 11b G8 / HR-4: no PUT, PATCH or DELETE exists on an issued
    invoice or line. A forged one is refused by the router, not by a screen."""
    with tenant_ctx(brazos):
        invoice = an_invoice(brazos, an_account(brazos, dana))
        for method in ("patch", "put", "delete"):
            response = api_call(
                billing_api.invoice_item,
                method,
                user=FakeUser(),
                role="system_admin",
                tenant=brazos,
                invoice_id=str(invoice.id),
            )
            assert response.status_code == 405, f"{method.upper()} must not be served"


def test_us_bil_025_tc2__a_missing_customer_read_refuses_instead_of_under_matching(
    brazos, dana, monkeypatch
):
    """HARD-WON LAW 2, in the shape that hides best.

    The customer-name leg of the search resolves customers' published selector
    at call time. If that read is not there, the obvious behaviour — skip the
    leg — returns FEWER bills with a 200, and a clerk searching "Miller" reads
    the empty result as "Miller has no bills". So the seam refuses loudly.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, contact_name="Miller, Sarah")
        an_invoice(brazos, account)
        monkeypatch.setattr(billing_selectors, "_resolve", lambda *a, **k: None)
        response = listed(brazos, q="Miller")

    assert response.status_code == 500
    assert response.data["code"] == errors.SYS_INTERNAL


# ══════════════════════════════════════════════════════════════════════════
# The database half (G5) — RLS, under a role row-level security applies to
# ══════════════════════════════════════════════════════════════════════════
INVOICE_TABLES = ("invoices", "invoice_lines")


def _billed_tenant(payload, *, service="electric"):
    """A provisioned tenant with one account, one bill and one bill line.

    Built through `provisioned_tenant` rather than through the `brazos` /
    `lonestar` fixtures on purpose: the session-scoped probe-role fixture and
    those function-scoped tenant fixtures cannot be composed in one signature
    (pytest tears the finalizers down in the wrong order), and this is the same
    shape `tests/test_us_met_reads_isolation.py` settled on for the same reason.
    """
    tenant, _ = provisioned_tenant(payload)
    actor = staff_actor(tenant, "system_admin", f"admin@{tenant.id}.test")
    with live_tenant_context(tenant.id):
        account = an_account(tenant, actor, contact_name="Miller, Sarah", service=service)
        invoice = an_invoice(tenant, account)
        a_line(tenant, invoice, account)
    return tenant, invoice


@pytest.mark.isolation
@requires_postgres
def test_us_bil_025_tc7__a_bill_never_crosses_a_tenant_boundary(rls):  # noqa: F811
    """US-BIL-025 TC-7 / US-BIL-026 TC-6 at the DATABASE, with the app-layer
    filter deliberately out of the path — under a NON-SUPERUSER probe role, so
    the policies are genuinely consulted rather than bypassed.

    The id-guessing probe is the one that matters: a selector that forgot its
    tenant filter still passes every list test in this file, and only this
    fails. Proved RED by dropping `invoices_tenant_isolation` on the live
    cluster — the probe then sees both tenants' bills and this names the leak.
    """
    brazos_tenant, bb_invoice = _billed_tenant(brazosbend_payload())
    lsr_tenant, lsr_invoice = _billed_tenant(lonestarridge_payload(), service="water")

    assert_rls_scoped(
        rls,
        "invoices",
        owner=brazos_tenant,
        intruder=lsr_tenant,
        owner_ids={str(bb_invoice.id)},
    )
    assert_rls_scoped(rls, "invoice_lines", owner=brazos_tenant, intruder=lsr_tenant)
    with live_tenant_context(lsr_tenant.id):
        assert rls.count("invoices", "id = %s", [str(bb_invoice.id)]) == 0
        assert rls.ids("invoices") == {str(lsr_invoice.id)}
    assert_no_foreign_rows_anywhere(rls, lsr_tenant, INVOICE_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_bil_025_tc7__invoices_are_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """CLAUDE.md hard rule 1, both halves.

    The DATABASE half: with `app.tenant_id` unset the policy's ::uuid cast of
    '' fails and NO row is visible — deny-by-default, never filter-by-default.
    The APP half: the selector refuses before a query is ever built, so an
    endpoint called outside a tenant context cannot lean on RLS being the only
    thing between one utility and another's bills.
    """
    _billed_tenant(brazosbend_payload())
    assert_denied_without_context(rls, *INVOICE_TABLES)
    with pytest.raises(errors.AuthError) as excinfo:
        billing_selectors.invoices_rollup()
    assert excinfo.value.code == errors.AUTH_TENANT_UNRESOLVABLE


@pytest.mark.isolation
@requires_postgres
def test_us_bil_025_tc7__a_write_into_another_tenants_bills_is_refused(rls):  # noqa: F811
    """WITH CHECK, not just USING: knowing a neighbour's tenant_id is not enough
    to stamp a row with it.

    TWO GUARDS SIT ON THIS TABLE AND THEY FIRE IN A FIXED ORDER, which is worth
    asserting rather than discovering. An ISSUED bill is refused by hard rule
    4's own trigger (`billing_invoice_immutable`, migration 0002) before RLS is
    ever consulted — so the generic helper cannot be pointed at issued rows and
    conclude anything about the POLICY. A DRAFT is editable by that trigger by
    design (it was never sent to anyone), and it is on a draft that the RLS
    WITH CHECK has to be the thing that refuses. Both halves are asserted, so a
    lane that ever relaxed the immutability trigger would still find the policy
    proved underneath it.
    """
    brazos_tenant, bb_invoice = _billed_tenant(brazosbend_payload())
    lsr_tenant, _ = _billed_tenant(lonestarridge_payload(), service="water")

    # (1) hard rule 4 refuses the ISSUED row first, and says why.
    with live_tenant_context(brazos_tenant.id):
        message = rls.refused(
            "UPDATE invoices SET tenant_id = %s WHERE id = %s",
            [str(lsr_tenant.id), str(bb_invoice.id)],
        )
    assert "BR-BIL-004" in message and "issued" in message

    # (2) …and on a DRAFT, which that trigger permits, the POLICY refuses.
    with live_tenant_context(brazos_tenant.id):
        account = billing_models.Invoice.objects.get(pk=bb_invoice.id).account
        draft = a_draft(brazos_tenant, account, invoice_no="BL-2608-000999")
        policy_message = rls.refused(
            "UPDATE invoices SET tenant_id = %s WHERE id = %s",
            [str(lsr_tenant.id), str(draft.id)],
        )
    assert "row-level security" in policy_message, (
        "a cross-tenant write on a DRAFT was refused, but not by the RLS "
        f"policy — {policy_message}"
    )


def test_def_075__any_bill_arms_the_currency_lock_including_a_draft(brazos, marcus):
    """**DEF-075**, as amended by the PO's ruling of 2026-08-12 (**OQ-181**).

    THE DEFECT WAS MEASURED IN A BROWSER. `PUT /api/brazosbend/settings/regional
    {"currency":"CAD"}` answered **200** on a tenant holding issued bill
    BL-2606-000001 (108.88 USD), and the tenant's currency changed. `apps/tenancy/
    services.py` asks `seams.financial_records_exist()`, which polls the `billing`
    and `payments` modules; only payments had ever authored it, so an issued
    INVOICE armed nothing. Every backend test passed because the tenancy suite
    proves the refusal with a PAYMENT present and nobody asked this question.

    Asserted THROUGH TENANCY'S SEAM, not by calling billing's selector, because
    what was missing was the wiring (hard-won law 2) — calling the new function
    directly would pass even if the re-export in `apps/billing/services.py` were
    dropped tomorrow.

    **THIS TEST ASSERTED THE OPPOSITE OF ITS DRAFT CASE UNTIL 2026-08-12, AND
    THE OLD REASONING IS QUOTED HERE RATHER THAN DELETED.** It read: *"A draft is
    discarded and re-run as ordinary bill-run work; no customer has seen it and
    nothing has posted. Locking a tenant's currency on a row the product is about
    to delete would refuse a legitimate setup change, so draft → still free."*
    That was a judgment, not a rule, which is exactly why it was raised as
    OQ-181 instead of left as a silent choice — and the PO overturned it in one
    word: *"currency locked"*.

    Their reading is the stronger one. A draft ALREADY CARRIES AMOUNTS STAMPED
    `USD`. Move the currency under it and the run's figures and the tenant's
    setting disagree until somebody happens to notice and delete the draft, and
    nothing makes them notice. A draft is not a plan to compute money; it is
    money already computed.
    """
    from apps.tenancy import seams as tenancy_seams

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)

        # Nothing billed at all — the currency is still free to move.
        assert tenancy_seams.financial_records_exist() is False

        draft = a_draft(brazos, account, invoice_no="BL-2608-000123")
        assert tenancy_seams.financial_records_exist() is True, (
            "PO ruling 2026-08-12 (OQ-181): a DRAFT bill locks the currency, "
            "because it already carries amounts stamped in it"
        )

        # …and deleting the draft releases the lock again, which is what makes
        # the ruling livable: a run abandoned before issue does not permanently
        # freeze a tenant that is still setting itself up.
        draft.delete()
        assert tenancy_seams.financial_records_exist() is False

        an_invoice(brazos, account, invoice_no="BL-2608-000124")
        assert tenancy_seams.financial_records_exist() is True


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-025@e4b0504 (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-07-bills-list.md · 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md; co-packet US-BIL-026, same three sources — matches apps/billing/api.py)
# generated: 2026-08-11 by story-coder (W3 billing read lane — the two S30 endpoints)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S30's list, detail and the S21 tab already ship and already call these paths) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the whole file was run against the unbuilt endpoints and failed 17/17 with `AttributeError: module 'apps.billing.api' has no attribute 'invoices'` and `django.urls.exceptions.Resolver404` on `/api/brazosbend/invoices`; the three isolation cases were separately RED-proved on the live cluster by removing the `invoices` policy from db/rls_billing_w3.sql (verbatim output in the lane report). Green: 17 passed / 3 skipped (sqlite tier) · 3 passed on live PostgreSQL (-m isolation)
# exceptions: the deviations this suite pins are listed in apps/billing/api.py's trailer — chiefly the `f.status=past_due` refusal and the six fields served null under their contracted names
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
