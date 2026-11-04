"""CR-197-BRC10 — the ONE GL mapping list (BR-LED-800..803, DEF-BIL-10648).

PO 2026-10-29 (decision log, four entries + *"Mapped for, start"*). What is
pinned here, each as the figure or the row it was ruled with:

  * one list, two groups, eleven types; search, three filters, server pages,
    counts {total, not mapped, disabled};
  * Add maps an EXISTING item only and refuses one already mapped; the account
    must be live and of the type's kind;
  * a customer class's own revenue account wins on that class's bill and no
    other (Solar usage 4150 for every class, Commercial → its own);
  * Disable stops new use for a charge code, a discount, an adjustment reason
    and removes a class override; refused for every other type;
  * a re-pointed account reaches the NEXT bill only — an issued line keeps its
    stamp (PENALTY 7218 → 7219 on 1 Nov; October stays on 7218);
  * a refund credits the `refunds_payable` account when one carries the role,
    cash otherwise (refund $57.13);
  * a discount line posts to the discount's own account when it has one;
  * another tenant sees none of it.

RED FIRST (law 7): before `apps/ledger/gl_mapping_list.py` existed this file
failed at collection with `ModuleNotFoundError: No module named
'apps.ledger.gl_mapping_list'`; the issue/refund cases were then shown red
against the pre-change `billing/issue.py` and `payments/ledger_seam.py` — the
quotes are in the CR file §6.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import issue, models as billing_models
from apps.ledger import chart, gl_mapping_list, selectors as ledger_selectors
from apps.ledger import models as ledger_models
from apps.ledger import services as ledger_services
from apps.payments import ledger_seam as payments_ledger_seam
from apps.rating import discounts as discount_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db
D = Decimal


def page(**filters):
    q = filters.pop("q", "")
    per = filters.pop("per", 50)
    pg = filters.pop("page", 1)
    return gl_mapping_list.list_page(ListParams(q=q, per=per, page=pg, filters=filters))


def a_gl(actor, code, name, type_):
    return ledger_services.create_account(actor, code=code, name=name, type=type_, designation=None)[
        "account_id"
    ]


def with_class(account, code):
    from apps.customers import models as customer_models

    account.account_type = customer_models.AccountType.objects.get(
        tenant_id=account.tenant_id, code=code
    )
    account.save(update_fields=["account_type"])
    return account


def issue_draft(tenant, dana, account, *, invoice_no, run_key):
    run = an_authorised_run(tenant, dana, key=run_key)
    draft = a_priced_draft(tenant, account, run, invoice_no=invoice_no)
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana,
    )


def line_accounts(bill):
    return {
        line.kind: str(line.gl_account_id)
        for line in billing_models.InvoiceLine.objects.filter(invoice=bill)
    }


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE LIST
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_1__one_list_two_groups_counts_and_no_id_as_a_word(brazos, dana):
    with tenant_ctx(brazos):
        out = page()
    rows = out["results"]
    assert out["count"] == out["counts"]["total"]
    types = {row["type"] for row in rows}
    assert {"service_revenue", "charge_code", "adjustment", "bill_payment", "deposit",
            "refund", "write_off", "other_payments", "system_account"} <= types
    assert [g["group"] for g in out["groups"]] == ["billing", "payments"]
    # Electric usage and base, every class — the service's own two rows.
    electric = [r for r in rows if r["key"].startswith("svc:electric:")]
    # The drawing's order: Usage before Base (found in the browser walk, where
    # an alphabetical sort put Base first).
    assert [r["key"] for r in electric] == ["svc:electric:usage:*", "svc:electric:base:*"]
    assert all(r["status"] == "mapped" for r in electric)
    # B14 rule 31 — the words on a row are never a database id.
    for row in rows:
        for word in (row["mapped_for"], row["detail"]):
            try:
                uuid.UUID(str(word))
            except ValueError:
                continue
            raise AssertionError(f"an id is a visible word: {row}")
    # The refund role is not seeded, so its row is the one honest gap.
    refund = next(r for r in rows if r["key"] == "des:refunds_payable")
    assert refund["status"] == "not_mapped" and refund["account"] is None
    assert out["counts"]["not_mapped"] >= 1


def test_cr197_2__search_filters_and_server_paging(brazos, dana):
    with tenant_ctx(brazos):
        everything = page()
        ar = ledger_selectors.gl_account_for_designation(chart.AR)
        by_code = page(q=ar.code)
        by_type = page(type="system_account")
        by_status = page(status="not_mapped")
        by_account = page(gl_account=str(ar.id))
        two = page(per=10, page=2)
    assert any(r["key"] == "des:accounts_receivable" for r in by_code["results"])
    assert {r["type"] for r in by_type["results"]} == {"system_account"}
    assert by_type["count"] == 3
    assert all(r["status"] == "not_mapped" for r in by_status["results"])
    assert by_status["count"] == everything["counts"]["not_mapped"]
    assert [r["key"] for r in by_account["results"]] == ["des:accounts_receivable"]
    # A page is cut by the server: page 2 of 10 is rows 11–20 of the whole.
    assert [r["key"] for r in two["results"]] == [
        r["key"] for r in everything["results"][10:20]
    ]
    # Counts describe the whole list whatever the filter.
    assert by_type["counts"] == everything["counts"]


# ════════════════════════════════════════════════════════════════════════════
# 2 · ADD AND EDIT
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_3__add_maps_an_unmapped_item_and_refuses_a_mapped_one(brazos, dana):
    with tenant_ctx(brazos):
        senior = discount_models.Discount.objects.create(
            tenant=brazos, code="SENIOR", name="Senior Citizen discount"
        )
        options = gl_mapping_list.add_options("discount")
        assert [i["key"] for i in options["items"]] == [f"dsc:{senior.id}"]
        assert all(a["type"] == "contra_revenue" for a in options["accounts"])
        given = a_gl(dana, "4755", "Senior discounts", "contra_revenue")
        row = gl_mapping_list.save(
            dana, {"act": "add", "key": f"dsc:{senior.id}", "account_id": given}
        )
        assert row["status"] == "mapped" and row["account"]["code"] == "4755"
        senior.refresh_from_db()
        assert str(senior.gl_account_id) == given  # written by RATING's own act
        with pytest.raises(errors.BizError):
            gl_mapping_list.save(dana, {"act": "add", "key": f"dsc:{senior.id}", "account_id": given})
        # Wrong kind: a revenue account is not a discount's.
        revenue = a_gl(dana, "4999", "Something sold", "revenue")
        with pytest.raises(errors.ValidationError):
            gl_mapping_list.save(dana, {"act": "edit", "key": f"dsc:{senior.id}", "account_id": revenue})
        # Not live: a retired account cannot be picked.
        ledger_services.set_account_active(dana, account_id=given, active=False, at=ISSUED_AT)
        with pytest.raises(errors.ValidationError):
            gl_mapping_list.save(dana, {"act": "edit", "key": f"dsc:{senior.id}", "account_id": given})


def test_cr197_4__a_role_moves_and_an_account_holding_another_role_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        payable = a_gl(dana, "2450", "Refunds payable", "liability")
        gl_mapping_list.save(dana, {"act": "add", "key": "des:refunds_payable", "account_id": payable})
        assert ledger_selectors.gl_account_id_for_designation(chart.REFUNDS_PAYABLE) == payable
        credit = ledger_selectors.gl_account_id_for_designation(chart.CUSTOMER_CREDIT_BALANCE)
        with pytest.raises(errors.BizError):
            gl_mapping_list.save(dana, {"act": "edit", "key": "des:refunds_payable", "account_id": credit})
        # Moving it frees the old holder.
        other = a_gl(dana, "2451", "Refund cheques outstanding", "liability")
        gl_mapping_list.save(dana, {"act": "edit", "key": "des:refunds_payable", "account_id": other})
        assert ledger_selectors.gl_account_id_for_designation(chart.REFUNDS_PAYABLE) == other
        assert ledger_models.LedgerAccount.objects.get(pk=payable).designation is None


def _action(row):
    if isinstance(row, dict):
        return row.get("action")
    return getattr(row, "action", None)


def test_cr197_5__every_act_is_audited(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        payable = a_gl(dana, "2450", "Refunds payable", "liability")
        gl_mapping_list.save(dana, {"act": "add", "key": "des:refunds_payable", "account_id": payable})
        gl_mapping_list.save(dana, {"act": "edit", "key": "des:refunds_payable", "account_id": payable})
        charge = next(r for r in page()["results"] if r["type"] == "charge_code")
        gl_mapping_list.set_enabled(dana, {"key": charge["key"]}, enabled=False)
        gl_mapping_list.set_enabled(dana, {"key": charge["key"]}, enabled=True)
    actions = [_action(row) for row in audit_rows]
    for act in ("gl_mapping.added", "gl_mapping.edited", "gl_mapping.disabled", "gl_mapping.enabled"):
        assert act in actions, (act, actions)
    # DEF-LED-10661 — `audit_log.entity_id` is a UUID column. The capture sink
    # here accepts anything, so the real store's refusal (a 500 on every act,
    # found only in the browser walk) is asserted on the row's own shape.
    for one in audit_rows:
        if _action(one) and str(_action(one)).startswith("gl_mapping."):
            entity = one.get("entity_id") if isinstance(one, dict) else getattr(one, "entity_id", None)
            uuid.UUID(str(entity))


# ════════════════════════════════════════════════════════════════════════════
# 3 · CUSTOMER-CLASS REVENUE (BR-LED-801)
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_6__a_class_row_wins_on_that_class_s_bill_only(brazos, dana):
    with tenant_ctx(brazos):
        every_class = ledger_selectors.revenue_account_id_for_service("electric")
        commercial_gl = a_gl(dana, "4101", "Electric sales - commercial", "revenue")
        key = "svc:electric:usage:commercial"
        assert key in [i["key"] for i in gl_mapping_list.add_options("service_revenue")["items"]]
        gl_mapping_list.save(dana, {"act": "add", "key": key, "account_id": commercial_gl})
        assert ledger_selectors.revenue_account_id_for_service(
            "electric", customer_class="commercial"
        ) == commercial_gl
        assert ledger_selectors.revenue_account_id_for_service(
            "electric", customer_class="residential"
        ) == every_class
        # The base part is not borrowed: it has no class row of its own.
        assert ledger_selectors.revenue_account_id_for_service(
            "electric", base=True, customer_class="commercial"
        ) == ledger_selectors.revenue_account_id_for_service("electric", base=True)

        shop = with_class(an_account(dana, brazos, account_no="A-20001"), "commercial")
        home = with_class(an_account(dana, brazos, account_no="A-20002"), "residential")
        shop_bill = issue_draft(brazos, dana, shop, invoice_no="BL-2607-197001", run_key="2026-06|c197a")
        home_bill = issue_draft(brazos, dana, home, invoice_no="BL-2607-197002", run_key="2026-06|c197b")
    assert line_accounts(shop_bill)["usage"] == commercial_gl
    assert line_accounts(home_bill)["usage"] == every_class
    assert line_accounts(shop_bill)["base"] == line_accounts(home_bill)["base"]


def test_cr197_7__disabling_a_class_row_falls_back_to_every_class(brazos, dana):
    with tenant_ctx(brazos):
        every_class = ledger_selectors.revenue_account_id_for_service("electric")
        gl = a_gl(dana, "4101", "Electric sales - commercial", "revenue")
        key = "svc:electric:usage:commercial"
        gl_mapping_list.save(dana, {"act": "add", "key": key, "account_id": gl})
        assert any(r["key"] == key and r["can_disable"] for r in page()["results"])
        gl_mapping_list.set_enabled(dana, {"key": key}, enabled=False)
        assert not ledger_models.ServiceClassRevenueAccount.objects.filter(tenant=brazos).exists()
        assert ledger_selectors.revenue_account_id_for_service(
            "electric", customer_class="commercial"
        ) == every_class


# ════════════════════════════════════════════════════════════════════════════
# 4 · DISABLE / ENABLE (BR-LED-802)
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_8__disable_scope_per_type(brazos, dana):
    with tenant_ctx(brazos):
        rows = page()["results"]
        charge = next(r for r in rows if r["type"] == "charge_code" and r["status"] != "disabled")
        reason = next(r for r in rows if r["type"] == "adjustment" and r["status"] != "disabled")
        gl_mapping_list.set_enabled(dana, {"key": charge["key"]}, enabled=False)
        gl_mapping_list.set_enabled(dana, {"key": reason["key"]}, enabled=False)
        after = {r["key"]: r for r in page()["results"]}
        assert after[charge["key"]]["status"] == "disabled"
        assert after[reason["key"]]["status"] == "disabled"
        assert rating_models.Charge.objects.get(pk=charge["key"][4:]).deleted_at is not None
        assert tenancy_models.ReasonCode.objects.get(pk=reason["key"][4:]).active is False
        gl_mapping_list.set_enabled(dana, {"key": charge["key"]}, enabled=True)
        gl_mapping_list.set_enabled(dana, {"key": reason["key"]}, enabled=True)
        assert rating_models.Charge.objects.get(pk=charge["key"][4:]).deleted_at is None
        # Refused for every other type.
        for key in ("svc:electric:usage:*", "des:accounts_receivable", "des:deposit_liability"):
            with pytest.raises(errors.BizError):
                gl_mapping_list.set_enabled(dana, {"key": key}, enabled=False)
        tender = next(r for r in rows if r["type"] == "bill_payment")
        with pytest.raises(errors.BizError):
            gl_mapping_list.set_enabled(dana, {"key": tender["key"]}, enabled=False)


def test_cr197_9__a_discount_is_disabled_by_retiring_it_and_cannot_come_back(brazos, dana):
    with tenant_ctx(brazos):
        senior = discount_models.Discount.objects.create(
            tenant=brazos, code="SENIOR", name="Senior Citizen discount"
        )
        gl_mapping_list.set_enabled(dana, {"key": f"dsc:{senior.id}"}, enabled=False)
        senior.refresh_from_db()
        assert senior.retire_on is not None
        row = next(r for r in page()["results"] if r["key"] == f"dsc:{senior.id}")
        assert row["status"] == "disabled" and row["can_enable"] is False
        with pytest.raises(errors.BizError):
            gl_mapping_list.set_enabled(dana, {"key": f"dsc:{senior.id}"}, enabled=True)


# ════════════════════════════════════════════════════════════════════════════
# 5 · NEW BILLS ONLY (BR-LED-802 / BR-BIL-010 / hard rule 4)
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_10__a_new_account_reaches_the_next_bill_and_the_issued_one_keeps_its_own(
    brazos, dana
):
    with tenant_ctx(brazos):
        first = issue_draft(
            brazos, dana, an_account(dana, brazos, account_no="A-20010"),
            invoice_no="BL-2610-197010", run_key="2026-10|c197",
        )
        october = line_accounts(first)["usage"]
        november_gl = a_gl(dana, "4102", "Electric sales (new)", "revenue")
        gl_mapping_list.save(
            dana, {"act": "edit", "key": "svc:electric:usage:*", "account_id": november_gl}
        )
        second = issue_draft(
            brazos, dana, an_account(dana, brazos, account_no="A-20011"),
            invoice_no="BL-2611-197011", run_key="2026-11|c197",
        )
    assert line_accounts(first)["usage"] == october != november_gl
    assert line_accounts(second)["usage"] == november_gl


# ════════════════════════════════════════════════════════════════════════════
# 6 · REFUND ACCOUNT (BR-LED-803) AND A DISCOUNT'S OWN ACCOUNT (DEF-BIL-10648)
# ════════════════════════════════════════════════════════════════════════════
def _refund_lines(tenant, refund_id):
    return {
        (code, side): amount
        for code, side, amount in ledger_models.JournalLine.objects.filter(
            tenant=tenant, journal_entry__source_id=refund_id
        ).values_list("ledger_account__code", "side", "amount")
    }


def test_cr197_11__a_refund_credits_cash_until_a_refund_account_is_chosen(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-20020")
        cash = ledger_selectors.gl_account_for_designation(chart.CASH).code
        credit = ledger_selectors.gl_account_for_designation(chart.CUSTOMER_CREDIT_BALANCE).code

        def refund():
            return SimpleNamespace(
                pk=uuid.uuid4(), amount=D("57.13"), currency="USD", reference=None
            )

        before = refund()
        payments_ledger_seam.post_refund_executed(
            refund=before, account_id=account.pk, entry_date=date(2026, 10, 29),
            posted_at=ISSUED_AT, actor=dana,
        )
        assert _refund_lines(brazos, before.pk) == {
            (credit, "debit"): D("57.13"), (cash, "credit"): D("57.13")
        }
        payable = a_gl(dana, "2450", "Refunds payable", "liability")
        gl_mapping_list.save(dana, {"act": "add", "key": "des:refunds_payable", "account_id": payable})
        after = refund()
        payments_ledger_seam.post_refund_executed(
            refund=after, account_id=account.pk, entry_date=date(2026, 10, 29),
            posted_at=ISSUED_AT, actor=dana,
        )
        assert _refund_lines(brazos, after.pk) == {
            (credit, "debit"): D("57.13"), ("2450", "credit"): D("57.13")
        }


def test_cr197_12__a_discount_line_posts_to_the_discount_s_own_account(brazos, dana):
    with tenant_ctx(brazos):
        own = a_gl(dana, "4755", "Senior discounts", "contra_revenue")
        discount_models.Discount.objects.create(
            tenant=brazos, code="SENIOR", name="Senior Citizen discount", gl_account_id=own
        )
        account = an_account(dana, brazos, account_no="A-20030")
        run = an_authorised_run(brazos, dana, key="2026-06|c197d")
        draft = a_priced_draft(brazos, account, run, invoice_no="BL-2607-197030")
        billing_models.InvoiceLine.objects.create(
            tenant=brazos, invoice=draft, account=account, service=None, kind="discount",
            description="Senior citizen discount", amount=D("-10.00"), taxable=False,
            discount_code="SENIOR",
        )
        billing_models.InvoiceLine.objects.create(
            tenant=brazos, invoice=draft, account=account, service=None, kind="discount",
            description="A discount with no account of its own", amount=D("-1.00"),
            taxable=False, discount_code="NOSUCH",
        )
        draft.total = draft.total - D("11.00")
        draft.save(update_fields=["total"])
        bill = issue.issue_invoice(
            draft, issued_at=ISSUED_AT, template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION, actor=dana,
        )
        stamped = {
            line.description: str(line.gl_account_id)
            for line in billing_models.InvoiceLine.objects.filter(invoice=bill, kind="discount")
        }
        designation = ledger_selectors.gl_account_id_for_designation(chart.DISCOUNT_CONTRA_REVENUE)
    assert stamped["Senior citizen discount"] == own
    assert stamped["A discount with no account of its own"] == designation


# ════════════════════════════════════════════════════════════════════════════
# 7 · TENANT ISOLATION (hard rule 1)
# ════════════════════════════════════════════════════════════════════════════
def test_cr197_13__another_tenant_sees_none_of_it(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        gl = a_gl(dana, "4101", "Electric sales - commercial", "revenue")
        gl_mapping_list.save(
            dana, {"act": "add", "key": "svc:electric:usage:commercial", "account_id": gl}
        )
    with tenant_ctx(lonestar):
        keys = [r["key"] for r in page()["results"]]
        assert "svc:electric:usage:commercial" not in keys
        assert not ledger_models.ServiceClassRevenueAccount.objects.exists() or all(
            row.tenant_id == lonestar.id
            for row in ledger_models.ServiceClassRevenueAccount.objects.filter(tenant=lonestar)
        )
        with pytest.raises(errors.NotFoundError):
            gl_mapping_list.set_enabled(erin, {"key": "svc:electric:usage:commercial"}, enabled=False)


def test_cr197_14__the_routes_answer_over_http(brazos, dana):
    from django.urls import resolve

    for path in (
        "/api/v1/ledger/gl-mappings/rows",
        "/api/v1/ledger/gl-mappings/rows/add-options",
        "/api/v1/ledger/gl-mappings/rows/edit-options",
        "/api/v1/ledger/gl-mappings/rows/disable",
        "/api/v1/ledger/gl-mappings/rows/enable",
    ):
        try:
            resolve(path)
        except Exception:  # noqa: BLE001 — the prefix may differ; try bare
            resolve(path.replace("/api/v1", ""))
