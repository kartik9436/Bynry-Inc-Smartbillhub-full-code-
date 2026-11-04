"""CR-184-BRC10 — receivables by service: the sharing, the dataset, the library
report, the foot check and the ageing's Service filter.

The rule is the decision log's 2026-10-14 entry (PO C1 → a), quoted in
`apps/payments/receivables_by_service.py`. The worked figure the PO was shown
is the first case below and is asserted EXACTLY: water 80.00 + sewer 40.00 +
tax 8.00 + late fee 5.00 = 133.00; paid 60.00 → water 40.00 + sewer 20.00
owed, tax 8.00 and fee 5.00 untouched.

RED PROVED, in pytest (the harness that runs these), by breaking each guard
and restoring it byte for byte (2026-10-14, SQLite):

  * the ageing's Service branch disabled →
    `test_the_ageing_service_filter_counts_the_share_not_the_whole_bill`
    failed `assert Decimal('120') == Decimal('80.0000')` — the whole mixed
    bill under *water*, which is the defect R5 fixes;
  * `to` removed from the dataset's filters →
    `test_the_as_of_box_date_reaches_the_report_through_the_runner` failed
    `{'as_of': '2026-10-31'} != {'as_of': '2027-01-31'}` (found on the walk);
  * the leftover units not handed out →
    `test_rounding_100_over_three_equal_lines…` failed with sewer at
    `33.3333` instead of `33.3334`.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.payments import models as payment_models
from apps.payments import receivables_by_service as rbs
from apps.payments import reporting
from apps.payments.outstandings import AGEING_BANDS
from apps.reports import datasets, queries, runner
from apps.reports import receivables_by_service as library
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

from tests.test_us_bil_025_026_bills_read import a_line, an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
D = Decimal
L = rbs.BillLine
DEFAULT_ORDER = ("usage_base", "taxes", "tenant_defined", "fees")
AS_OF = date(2026, 9, 30)


# ════════════════════════════════════════════════════════════════════════════
# ONE BILL — pure
# ════════════════════════════════════════════════════════════════════════════
WORKED_LINES = [
    L("water", "usage", D("80.00")),
    L("sewer", "usage", D("40.00")),
    L(None, "tax", D("8.00")),
    L(None, "fee", D("5.00")),
]


def test_the_po_worked_figure_exactly():
    share = rbs.share_bill(
        owed=D("73.00"),
        lines=WORKED_LINES,
        allocated=D("60.00"),
        paid_by_class={},
        class_order=DEFAULT_ORDER,
    )
    assert share.shares == {
        ("water", None): D("40.0000"),
        ("sewer", None): D("20.0000"),
        (None, "taxes"): D("8.0000"),
        (None, "fees"): D("5.0000"),
    }
    assert share.method == rbs.METHOD_CLASS_WALK


def test_tax_and_fee_untouched_until_usage_base_is_cleared_in_the_tenants_order():
    # Default order: 125.00 clears usage+base (120.00) and 5.00 of the tax.
    default = rbs.share_bill(
        owed=D("8.00"), lines=WORKED_LINES, allocated=D("125.00"),
        paid_by_class={}, class_order=DEFAULT_ORDER,
    )
    assert default.shares == {(None, "taxes"): D("3.0000"), (None, "fees"): D("5.0000")}
    # A tenant who meets FEES before taxes: the same 125.00 clears the fee.
    fees_first = rbs.share_bill(
        owed=D("8.00"), lines=WORKED_LINES, allocated=D("125.00"),
        paid_by_class={}, class_order=("usage_base", "fees", "taxes", "tenant_defined"),
    )
    assert fees_first.shares == {(None, "taxes"): D("8.0000")}


def test_a_stored_class_breakdown_wins_over_the_walk():
    # 60.00 paid, and the record says it met TAX 8.00 + usage 52.00.
    share = rbs.share_bill(
        owed=D("73.00"), lines=WORKED_LINES, allocated=D("60.00"),
        paid_by_class={"taxes": D("8.00"), "usage_base": D("52.00")},
        class_order=DEFAULT_ORDER,
    )
    # usage+base still owes 68.00, shared 2:1 → water 45.3333|33, sewer 22.6666|67:
    # the one leftover unit goes to the LARGER cut-off fraction, sewer's.
    assert share.shares[(None, "fees")] == D("5.0000")
    assert (None, "taxes") not in share.shares or share.shares[(None, "taxes")] == D("0")
    assert share.shares[("water", None)] + share.shares[("sewer", None)] == D("68.0000")
    assert share.shares[("water", None)] == D("45.3333")
    assert share.shares[("sewer", None)] == D("22.6667")
    assert sum(share.shares.values()) == D("73.00")


def test_rounding_100_over_three_equal_lines_sums_exactly_and_deterministically():
    lines = [L("water", "usage", D("50")), L("sewer", "usage", D("50")), L("trash", "base", D("50"))]
    first = rbs.share_bill(owed=D("100.00"), lines=lines, allocated=D("50.00"),
                           paid_by_class={}, class_order=DEFAULT_ORDER)
    # Largest cut-off fraction ties → row order (services by code): sewer first.
    assert first.shares == {
        ("sewer", None): D("33.3334"),
        ("trash", None): D("33.3333"),
        ("water", None): D("33.3333"),
    }
    assert sum(first.shares.values()) == D("100.00")
    again = rbs.share_bill(owed=D("100.00"), lines=list(reversed(lines)), allocated=D("50.00"),
                           paid_by_class={}, class_order=DEFAULT_ORDER)
    assert again.shares == first.shares


def test_awkward_splits_always_foot_to_the_bill():
    rng = random.Random(184)
    for _ in range(400):
        lines = [
            L(rng.choice(["water", "sewer", "electric", None]),
              rng.choice(["usage", "base", "tax", "fee"]),
              D(rng.randint(1, 99999)) / D(100))
            for _ in range(rng.randint(1, 7))
        ]
        billed = sum((line.amount for line in lines), D("0"))
        paid = (billed * D(rng.randint(0, 99)) / D(100)).quantize(D("0.01"))
        owed = billed - paid
        if owed <= 0:
            continue
        share = rbs.share_bill(owed=owed, lines=lines, allocated=paid,
                               paid_by_class={}, class_order=DEFAULT_ORDER)
        assert sum(share.shares.values()) == owed, (lines, paid)
        for value in share.shares.values():
            assert value == value.quantize(D("0.0001"))


def test_a_line_no_class_places_on_a_part_paid_bill_is_shared_by_proportion_and_counted():
    lines = [L("water", "usage", D("90")), L("water", "minimum", D("10"))]
    share = rbs.share_bill(owed=D("50"), lines=lines, allocated=D("50"),
                           paid_by_class={}, class_order=DEFAULT_ORDER)
    assert share.method == rbs.METHOD_PROPORTION
    assert share.shares == {("water", None): D("50.0000")}
    # Unpaid, the same bill needs no class at all: line for line.
    unpaid = rbs.share_bill(owed=D("100"), lines=lines, allocated=D("0"),
                            paid_by_class={}, class_order=DEFAULT_ORDER)
    assert unpaid.method == rbs.METHOD_UNPAID


def test_a_bill_asking_less_than_its_lines_is_scaled_to_what_it_asks():
    # Budget billing — the bill's lines say 133.00 and it asks 100.00 (BR-BIL-072).
    share = rbs.share_bill(owed=D("100.00"), lines=WORKED_LINES, allocated=D("0"),
                           paid_by_class={}, class_order=DEFAULT_ORDER)
    assert share.scaled is True
    assert sum(share.shares.values()) == D("100.00")


def test_a_bill_with_no_lines_is_owed_on_other_charges():
    share = rbs.share_bill(owed=D("12.00"), lines=[], allocated=D("0"),
                           paid_by_class={}, class_order=DEFAULT_ORDER)
    assert share.shares == {(None, "other"): D("12.00")}


# ════════════════════════════════════════════════════════════════════════════
# THE DATABASE — real bills, real allocations
# ════════════════════════════════════════════════════════════════════════════
def _service(code):
    return tenancy_models.Service.objects.get(code=code)


def _bill(tenant, account, *, no, lines, due, issued=datetime(2026, 8, 1, 9, 0, tzinfo=UTC)):
    total = sum((amount for _, _, amount in lines), D("0"))
    bill = an_invoice(
        tenant, account, invoice_no=no, total=total, subtotal=total, tax_total=D("0"),
        due_date=due, issued_at=issued,
    )
    for service, kind, amount in lines:
        a_line(tenant, bill, account, kind=kind, amount=amount,
               service=_service(service) if service else None,
               description=f"{service or kind} {kind}", quantity=None, unit=None,
               unit_price=None)
    return bill


def _pay(tenant, account, bill, amount, *, no, posted=datetime(2026, 9, 1, 10, 0, tzinfo=UTC)):
    payment = payment_models.Payment.objects.create(
        tenant=tenant, account=account, payment_no=no, amount=amount, currency="USD",
        status=payment_models.PAYMENT_CLEARED, posted_at=posted, cleared_at=posted,
    )
    return payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=bill, amount=amount
    )


WORKED_DB_LINES = [
    ("water", "usage", D("80.00")),
    ("sewer", "usage", D("40.00")),
    (None, "tax", D("8.00")),
    (None, "fee", D("5.00")),
]


def _rows(found):
    return {
        (key[1]): position.total
        for key, position in found["positions"].items()
    }


def test_the_worked_figure_through_the_database(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-1", label="Svc one")
        bill = _bill(brazos, account, no="BL-SVC-1", lines=WORKED_DB_LINES, due=date(2026, 8, 25))
        _pay(brazos, account, bill, D("60.00"), no="PMT-SVC-1")
        found = rbs.account_service_positions(as_of=AS_OF, bands=AGEING_BANDS)
        assert _rows(found) == {
            ("water", None): D("40.0000"),
            ("sewer", None): D("20.0000"),
            (None, "taxes"): D("8.0000"),
            (None, "fees"): D("5.0000"),
        }
        assert found["population"] == D("73.00")


def test_the_tenants_own_class_order_is_the_one_walked(brazos, dana):
    actor = staff_actor(brazos, role="system_admin")
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            actor, "billing-defaults",
            {"allocation_class_order": ["usage_base", "fees", "taxes", "tenant_defined"]},
        )
        account = an_account(brazos, dana, account_no="AC-SVC-2", label="Svc two")
        bill = _bill(brazos, account, no="BL-SVC-2", lines=WORKED_DB_LINES, due=date(2026, 8, 25))
        _pay(brazos, account, bill, D("125.00"), no="PMT-SVC-2")
        found = rbs.account_service_positions(as_of=AS_OF, bands=AGEING_BANDS)
        assert _rows(found) == {(None, "taxes"): D("8.0000")}


def test_two_bills_band_on_their_own_due_dates(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-3", label="Svc three")
        _bill(brazos, account, no="BL-SVC-3A", lines=[("water", "usage", D("30.00"))],
              due=date(2026, 6, 1), issued=datetime(2026, 5, 10, tzinfo=UTC))
        _bill(brazos, account, no="BL-SVC-3B", lines=[("water", "usage", D("20.00")),
                                                      ("electric", "usage", D("10.00"))],
              due=date(2026, 9, 15))
        found = rbs.account_service_positions(as_of=AS_OF, bands=AGEING_BANDS)
        water = found["positions"][(account.id, ("water", None))]
        assert water.bands["90+"] == D("30.0000")
        assert water.bands["1-30"] == D("20.0000")
        assert water.total == D("50.0000")
        electric = found["positions"][(account.id, ("electric", None))]
        assert electric.bands["1-30"] == D("10.0000")
        # A date before the second bill was issued sees only the first.
        early = rbs.account_service_positions(as_of=date(2026, 7, 1), bands=AGEING_BANDS)
        assert {k[1] for k in early["positions"]} == {("water", None)}


def test_the_rows_foot_to_the_ageing_population(brazos, dana):
    with tenant_ctx(brazos):
        for n in range(3):
            account = an_account(brazos, dana, account_no=f"AC-SVC-F{n}", label=f"Foot {n}")
            bill = _bill(brazos, account, no=f"BL-SVC-F{n}", lines=WORKED_DB_LINES,
                         due=date(2026, 8, 25))
            _pay(brazos, account, bill, D("33.33") * (n + 1), no=f"PMT-SVC-F{n}")
        found = rbs.account_service_positions(as_of=AS_OF, bands=AGEING_BANDS)
        rows_total = sum((p.total for p in found["positions"].values()), D("0"))
        ageing = reporting.ar_aging(as_of=AS_OF, per=None)
        assert rows_total == found["population"] == ageing["population_total"]


def test_the_foot_check_states_a_difference_and_never_adjusts(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-4", label="Svc four")
        _bill(brazos, account, no="BL-SVC-4", lines=WORKED_DB_LINES, due=date(2026, 8, 25))
        monkeypatch.setattr(queries.seams, "ar_control", lambda **kw: D("140.00"))
        payload = runner.run(library.KEY, {"as_of": AS_OF.isoformat()}).payload
        codes = [entry.get("code") for entry in payload["unavailable"]]
        assert "receivables_by_service_does_not_foot_to_the_ar_control_total" in codes
        assert D(payload["totals"]["total"]) == D("133.00")
        assert D(payload["totals"]["ar_control"]) == D("140.00")
        monkeypatch.setattr(queries.seams, "ar_control", lambda **kw: D("133.00"))
        payload = runner.run(library.KEY, {"as_of": AS_OF.isoformat()}).payload
        codes = [entry.get("code") for entry in payload["unavailable"]]
        assert "receivables_by_service_does_not_foot_to_the_ar_control_total" not in codes


def test_another_tenants_bills_are_never_counted(brazos, lonestar, dana, erin):
    with tenant_ctx(lonestar):
        other = an_account(lonestar, erin, account_no="AC-LSR-1", label="Ridge", service="water")
        _bill(lonestar, other, no="BL-LSR-1", lines=[("water", "usage", D("999.00"))],
              due=date(2026, 8, 25))
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-5", label="Svc five")
        _bill(brazos, account, no="BL-SVC-5", lines=[("water", "usage", D("10.00"))],
              due=date(2026, 8, 25))
        found = rbs.account_service_positions(as_of=AS_OF, bands=AGEING_BANDS)
        assert found["population"] == D("10.00")
        assert {k[0] for k in found["positions"]} == {account.id}


def test_the_dataset_pages_after_totalling_the_whole_set(brazos, dana):
    with tenant_ctx(brazos):
        for n in range(3):
            account = an_account(brazos, dana, account_no=f"AC-SVC-P{n}", label=f"Page {n}")
            _bill(brazos, account, no=f"BL-SVC-P{n}",
                  lines=[("water", "usage", D(10 * (n + 1)))], due=date(2026, 8, 25))
        # The read model at a page of 2 (the screen clamps `per` to its kit sizes).
        first = rbs.receivables_dataset(as_of=AS_OF, per=2, page=1)
        second = rbs.receivables_dataset(as_of=AS_OF, per=2, page=2)
        assert (first["page"], first["pages"], first["total"]) == (1, 2, 3)
        assert len(first["rows"]) == 2 and len(second["rows"]) == 1
        assert first["totals"] == second["totals"]
        assert first["totals"]["total"] == D("60")
        # Largest first, stable across the boundary.
        seen = [row.account_no for row in first["rows"] + second["rows"]]
        served = queries.receivables_dataset({"as_of": AS_OF.isoformat()})
        assert served["page"] == {"page": 1, "per": 50, "total": 3, "pages": 1}
        assert seen == ["AC-SVC-P2", "AC-SVC-P1", "AC-SVC-P0"]
        whole = queries.receivables_dataset({"as_of": AS_OF.isoformat(), "per": "all"})
        assert "page" not in whole and len(whole["rows"]) == 3
        streamed = list(queries.receivables_dataset_rows({"as_of": AS_OF.isoformat()}))
        assert [r["account_no"] for r in streamed] == seen


def test_the_dataset_is_registered_and_a_custom_definition_runs_on_it(brazos, dana):
    assert datasets.BY_CODE["receivables"].paginates is True
    assert datasets.registry_payload()["count"] == 10
    assert queries.DATASET_QUERIES["receivables"] is queries.receivables_dataset
    assert queries.DATASET_STREAMS["receivables"] is queries.receivables_dataset_rows
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-6", label="Svc six")
        bill = _bill(brazos, account, no="BL-SVC-6", lines=WORKED_DB_LINES, due=date(2026, 5, 1),
                     issued=datetime(2026, 4, 1, tzinfo=UTC))
        _pay(brazos, account, bill, D("60.00"), no="PMT-SVC-6")
        query = runner.queries_for("my-receivables-90", "receivables")
        payload = query({"as_of": AS_OF.isoformat(), "service": "water"})
        assert [(r["service_code"], D(r["d90_plus"])) for r in payload["rows"]] == [("water", D("40"))]


def test_the_library_report_one_row_per_service(brazos, dana):
    with tenant_ctx(brazos):
        a = an_account(brazos, dana, account_no="AC-SVC-7", label="Svc seven")
        b = an_account(brazos, dana, account_no="AC-SVC-8", label="Svc eight")
        old = datetime(2026, 4, 1, tzinfo=UTC)
        bill = _bill(brazos, a, no="BL-SVC-7", lines=WORKED_DB_LINES, due=date(2026, 5, 1), issued=old)
        _pay(brazos, a, bill, D("60.00"), no="PMT-SVC-7")
        _bill(brazos, b, no="BL-SVC-8", lines=[("water", "usage", D("20.00"))],
              due=date(2026, 5, 1), issued=old)
        _bill(brazos, b, no="BL-SVC-8B", lines=[("sewer", "usage", D("7.00"))],
              due=date(2026, 9, 25))
        payload = runner.run(library.KEY, {"as_of": AS_OF.isoformat()}).payload
        rows = {(r["service_code"], r["charge_class"]): r for r in payload["rows"]}
        assert D(rows[("water", None)]["d90_plus"]) == D("60")
        assert rows[("water", None)]["debtors"] == 2
        assert D(rows[("sewer", None)]["d90_plus"]) == D("20")
        assert D(rows[("sewer", None)]["total"]) == D("27")
        assert D(rows[(None, "taxes")]["d90_plus"]) == D("8")
        assert D(rows[(None, "fees")]["d90_plus"]) == D("5")
        assert D(payload["totals"]["d90_plus"]) == D("93")
        # Distinct debtors, not the column's sum (2 + 1 + 1 + 1).
        assert payload["totals"]["debtors"] == 2
        assert D(payload["totals"]["total"]) == D("100")
        assert rows[("water", None)]["share_pct"] == "64.516129"
        assert payload["dataset"] == "receivables"


def test_the_as_of_box_date_reaches_the_report_through_the_runner(brazos):
    """The walk of 2026-10-14: the box writes `to`, and `runner.bind` dropped it
    because the dataset did not declare it — the box read 01/31/2027 while the
    report answered 2026-10-31. Red before `to` joined the dataset's filters."""
    with tenant_ctx(brazos):
        payload = runner.run(library.KEY, {"to": "2027-01-31"}).payload
        assert payload["window"] == {"as_of": "2027-01-31"}
        definition = runner.resolve(library.KEY)
        assert "to" in runner.bind(definition, {"to": "2027-01-31"})


def _tenant_definition(tenant, key, visibility, owner):
    from apps.reports.models import ReportDefinition

    return ReportDefinition.objects.create(
        tenant_id=tenant.id, key=key, name=key.replace("-", " ").title(),
        dataset="receivables", group_code="receivables", sub_group_code=None,
        columns=["account_no", "service", "service_code", "total"], filters={},
        group_by=[], sort=[], service_codes=[], visibility=visibility,
        owner_user_id=owner, version=1,
    )


def test_a_saved_multi_word_report_opens_by_the_spelling_the_viewer_sends(brazos, dana):
    """DEF-REP-10146 (the walk of 2026-10-14). Save as keys the report
    `receivables-over-90-days-by-service`; the viewer asks for
    `receivables_over_90_days_by_service`. It must open — and a colleague's
    PRIVATE report must stay absent through the same spelling (BR-REP-019)."""
    from apps.reports import api as reports_api
    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-K", label="Svc key")
        _bill(brazos, account, no="BL-SVC-K", lines=[("water", "usage", D("10.00"))],
              due=date(2026, 8, 25))
        # The row exactly as Save as writes it — keyed from the name with
        # hyphens (`definitions._unique_key`).
        shared = _tenant_definition(brazos, "receivables-over-90-days-by-service", "shared", None)
        response = api_call(
            reports_api.report, "get", user=FakeUser(), role="billing_clerk", tenant=brazos,
            query={"as_of": AS_OF.isoformat()}, key=shared.key.replace("-", "_"),
        )
        assert response.status_code == 200, getattr(response, "data", None)
        assert response.data["rows"][0]["service_code"] == "water"

        private = _tenant_definition(brazos, "someone-else-private", "private", uuid.uuid4())
        hidden = api_call(
            reports_api.report, "get", user=FakeUser(), role="billing_clerk", tenant=brazos,
            key=private.key.replace("-", "_"),
        )
        # "There is no report called this" — never the colleague's rows.
        assert hidden.status_code == 422, hidden.status_code
        assert "rows" not in (hidden.data or {})


def test_the_library_report_is_exportable(brazos):
    from apps.tenancy import exports as export_kernel

    assert export_kernel.export_resource(library.KEY) is not None


def test_the_ageing_service_filter_counts_the_share_not_the_whole_bill(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-SVC-9", label="Svc nine")
        _bill(brazos, account, no="BL-SVC-9", lines=[("water", "usage", D("80.00")),
                                                     ("electric", "usage", D("40.00"))],
              due=date(2026, 9, 15))
        water = reporting.ar_aging(as_of=AS_OF, service_code="water", per=None)
        assert water["totals"]["total"] == D("80.0000")
        assert water["rows"][0].total == D("80.0000")
        both = reporting.ar_aging(as_of=AS_OF, service_code="water,electric", per=None)
        assert both["totals"]["total"] == D("120.0000")
        # The tie-out side does not move with the chip.
        assert water["population_total"] == D("120.00")
        assert water["filtered"] is True
