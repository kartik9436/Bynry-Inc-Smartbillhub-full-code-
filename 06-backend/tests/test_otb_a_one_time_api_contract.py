"""The one-time bill redesign's API — `13-one-time-bill-api-contract.md`, tested (T4).

US-BIL-010..014, 032, 033, 034 · build plan A2–A8, DB2, DB3 · journey J70.

Written RED FIRST (hard-won law 7): before the routes changed, every case below
failed on the shape the redrawn screen needs — the preview refused ONE problem
at a time with the generic key, answered no `account`/`defaults`/`bill` block,
the duplicate refusal named no bill number, and `…/send` did not resolve. The
verbatim failures are in the lane report.

What each group proves, in the contract's words:

  * **All problems at once** (A3) — every step-1 problem in ONE 422, each on its
    own field with its own `billing.oneTime.err.*` key, and never
    `billing.run.refused`.
  * **Days to pay is the one tolerated gap on the PREVIEW** — the answer still
    carries the account and the cycle's default so the screen can prefill it;
    the DRAFT refuses it.
  * **Reason code** — checked against the tenant's ACTIVE `reason_codes`.
  * **Duplicate** (A8) — `409` with `{invoice_no, run_id, ran_by_name, ran_at}`.
  * **Send** (A6) — refused without the acknowledgement; twice = ONE bill.
  * **Delivery** (A7) — the clerk's choice reaches the delivery seam; paper
    stays the floor (BR-BIL-036).
  * **Tenant isolation** on every new or changed route (hard rule 1).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import delivery_seam, one_time_answer
from apps.billing import models as billing_models
from apps.tenancy import models as tenancy_models
from tests.test_cr108_w1_one_time_fee_lines_and_books import (
    TEST_CODE,
    a_charge_code,
    a_one_time_account,
)
from tests.test_def_438_parity import PERIOD_END, PERIOD_START, _account_on, _water_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` (PO 2026-10-01) — an interim bill for an account on no
    billing cycle is now REFUSED (*"No billing cycle. Assign one on the
    account."*). This file's interim cases are about something else, so their
    unit is put on a cycle through the same metering seam the card and the
    refusal read. Only the cycle's NAME is given, not its calendar, so the
    denominator falls back to the window's own length and no figure here moves.
    """
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )

FEE_ON = date(2026, 7, 9)
SENT_AT = datetime(2026, 7, 9, 15, 30, tzinfo=UTC)


def _clerk(tenant):
    """A billing clerk backed by a real `users` row — `bill_run_releases.
    confirmed_by` is an FK into identity (B2 §2)."""
    return FakeUser(user_id=staff_actor(tenant, "billing_clerk", "priya@otb-api.test").id)


def _post(view, tenant, user, data, **kwargs):
    return api_call(
        view, "post", user=user, role="billing_clerk", tenant=tenant, data=data, **kwargs
    )


def _keys(response):
    return {(row["field"], row["message_key"]) for row in response.data.get("field_errors") or ()}


# ══════════════════════════════════════════════════════════════════════════
# A3 · ALL PROBLEMS AT ONCE
# ══════════════════════════════════════════════════════════════════════════


def test_otb_a3__every_step_1_problem_arrives_in_one_refusal_each_on_its_field(brazos, dana):
    """Contract §2's own example, and two more: a catch-up whose SECOND period
    ends before it starts, no reason, no bill date and no days to pay."""
    user = _clerk(brazos)
    response = _post(
        billing_api.one_time_preview,
        brazos,
        user,
        {
            "account_id": "018f0000-0000-7000-8000-000000000001",
            "kind": "backbill",
            "sub_periods": [
                {"period_start": "2026-05-01", "period_end": "2026-05-31"},
                {"period_start": "2026-06-30", "period_end": "2026-06-01"},
            ],
            "reason_code": "",
            "bill_date": None,
            "due_days": None,
        },
    )
    assert response.status_code == 422, response.data
    assert _keys(response) == {
        ("sub_periods[1].period_end", "billing.oneTime.err.periodEndsBeforeStart"),
        ("reason_code", "billing.oneTime.err.reasonRequired"),
        ("bill_date", "billing.oneTime.err.billDateRequired"),
        ("due_days", "billing.oneTime.err.dueDaysRequired"),
    }
    assert response.data["message_key"] != "billing.run.refused"
    assert "cycle" not in str(response.data["message_key"])


def test_otb_a3__the_problems_come_in_screen_order_and_zero_days_is_lawful():
    """`0` is due ON the bill date (BR-MET-009) — never *nobody typed one* — and
    a negative or a boolean is refused by its own key."""
    base = {"account_id": "x", "kind": "fee", "charge_code": "RECON", "bill_date": "2026-07-09"}
    assert one_time_answer.problems_in({**base, "due_days": 0}) == []
    for bad in (-1, "3.5", True, "abc"):
        assert [
            p["message_key"] for p in one_time_answer.problems_in({**base, "due_days": bad})
        ] == ["billing.oneTime.err.dueDaysInvalid"], bad
    found = one_time_answer.problems_in({"kind": "fee", "due_days": None})
    assert [p["field"] for p in found] == ["account_id", "charge_code", "bill_date", "due_days"]


def test_otb_a2__a_reason_must_be_an_active_row_of_the_tenants_reason_codes(brazos):
    with tenant_ctx(brazos):
        tenancy_models.ReasonCode.objects.get_or_create(
            tenant=brazos, code="MISSED", defaults={"name": "Missed billing cycle"}
        )
        tenancy_models.ReasonCode.objects.update_or_create(
            tenant=brazos, code="RETIRED", defaults={"name": "Old reason", "active": False}
        )
        payload = {
            "account_id": "x",
            "kind": "penalty",
            "sub_periods": [{"period_start": "2026-05-01", "period_end": "2026-05-31"}],
            "bill_date": "2026-07-09",
            "due_days": 21,
        }
        ok = one_time_answer.problems_in({**payload, "reason_code": "MISSED"})
        unknown = one_time_answer.problems_in({**payload, "reason_code": "NOPE"})
        retired = one_time_answer.problems_in({**payload, "reason_code": "RETIRED"})
    assert ok == []
    assert [p["message_key"] for p in unknown] == ["billing.oneTime.err.reasonUnknown"]
    assert [p["message_key"] for p in retired] == ["billing.oneTime.err.reasonUnknown"]


# ══════════════════════════════════════════════════════════════════════════
# A4 · THE ANSWER — and the one tolerated gap
# ══════════════════════════════════════════════════════════════════════════


def _interim_body(account, **overrides):
    body = {
        "account_id": str(account.id),
        "kind": "interim",
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "bill_date": PERIOD_END.isoformat(),
        "due_days": 21,
    }
    body.update(overrides)
    return body


def test_otb_a4__the_preview_answers_every_section_of_the_contract(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    response = _post(billing_api.one_time_preview, brazos, user, _interim_body(account))
    assert response.status_code == 200, response.data
    body = response.data
    for key in (
        "kind",
        "account",
        "defaults",
        "due_date",
        "services",
        "rates",
        "readings",
        "periods",
        "move_in_charges",
        "settlement",
        "charge",
        "bill",
        "warnings",
        "duplicate",
    ):
        assert key in body, key
    assert body["account"]["id"] == str(account.id)
    assert body["due_date"] == "2026-08-21", "31 Jul + 21 days (BR-BIL-024)"
    assert [row["service"] for row in body["services"]] == ["water"]
    assert body["services"][0]["status"] in ("billed", "billed_base_zero")
    assert body["readings"]["needed"] == "every_meter"
    assert body["readings"]["rows"], "one reading row per meter"
    row = body["readings"]["rows"][0]
    assert row["previous"]["on_file"] is True and row["unit"], "a quantity carries its unit"
    groups = body["bill"]["groups"]
    assert groups and groups[0]["period_start"] == PERIOD_START.isoformat()
    lines = [line for group in groups for line in group["lines"]]
    assert {line["charge"] for line in lines} >= {"usage"}
    assert Decimal(body["bill"]["total"]) > 0
    # Sections the interim kind does not have are null, never empty lists.
    assert body["periods"] is None and body["settlement"] is None
    assert body["move_in_charges"] is None and body["charge"] is None
    assert body["duplicate"] is None


def test_otb_a3__an_empty_days_to_pay_still_answers_the_account_and_its_default(brazos, dana):
    """The frontend lane's report: the screen PREFILLS days to pay from the
    preview, so a preview refused for that one field would hide its own default."""
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    response = _post(
        billing_api.one_time_preview, brazos, user, _interim_body(account, due_days=None)
    )
    assert response.status_code == 200, response.data
    assert response.data["account"]["id"] == str(account.id)
    assert "due_days" in response.data["defaults"]
    assert response.data["due_date"] is None
    assert [p["field"] for p in response.data["field_errors"]] == ["due_days"]
    # …and the DRAFT refuses it — nothing is written without terms.
    drafted = _post(
        billing_api.one_time_create, brazos, user, _interim_body(account, due_days=None)
    )
    assert drafted.status_code == 422
    assert _keys(drafted) == {("due_days", "billing.oneTime.err.dueDaysRequired")}


# ══════════════════════════════════════════════════════════════════════════
# A8 · DUPLICATE — the bill number and who ran it
# ══════════════════════════════════════════════════════════════════════════


def test_otb_a8__a_second_draft_is_refused_naming_the_bill_and_who_ran_it(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    first = _post(billing_api.one_time_create, brazos, user, _interim_body(account))
    assert first.status_code == 201, first.data
    assert first.data["bill"]["groups"], "the draft answers the bill as written"
    again = _post(billing_api.one_time_create, brazos, user, _interim_body(account))
    assert again.status_code == 409
    params = again.data["params"]
    assert params["run_id"] == first.data["run_id"]
    assert params["invoice_no"] == first.data["invoice_no"]
    assert params["invoice_id"] == first.data["invoice_id"]
    assert "ran_by_name" in params and params["ran_at"]
    # The preview shows the same fact on step 2, where the banner is drawn.
    previewed = _post(billing_api.one_time_preview, brazos, user, _interim_body(account))
    assert previewed.status_code == 200
    assert previewed.data["duplicate"]["run_id"] == first.data["run_id"]


# ══════════════════════════════════════════════════════════════════════════
# A6 · SEND — acknowledged, idempotent, one bill
# ══════════════════════════════════════════════════════════════════════════


def _a_fee_draft(brazos, dana, user, **extra):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana)
        a_charge_code(brazos)
    body = {
        "account_id": str(account.id),
        "kind": "fee",
        "charge_code": TEST_CODE,
        "bill_date": FEE_ON.isoformat(),
        "due_days": 21,
        **extra,
    }
    made = _post(billing_api.one_time_create, brazos, user, body)
    assert made.status_code == 201, made.data
    return made.data


#: PO ruling 2026-09-30, option B, verbatim: *"B · Show all five ticks on the
#: one-time Send card."* The five a cycle release asks (BR-BIL-058), in the
#: server's own names.
FIVE = ("compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final")
ALL_FIVE = {name: True for name in FIVE}


def _send(tenant, user, run_id, **body):
    payload = {"confirmations": dict(ALL_FIVE), "delivery": "email", "sent_at": SENT_AT.isoformat()}
    payload.update(body)
    return _post(billing_api.one_time_send, tenant, user, payload, run_id=run_id)


def test_us_bil_033_tc4__send_is_refused_until_all_five_are_ticked_and_issues_nothing(brazos, dana):
    """Each untaken confirmation is named on its own field; anything that is not
    literal `true` is not a confirmation; and the retired single acknowledgement
    stands for nothing any more."""
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)
    required = "billing.oneTime.err.confirmRequired"
    for name in FIVE:
        for value in (False, None, "yes"):
            refused = _send(
                brazos, user, draft["run_id"], confirmations={**ALL_FIVE, name: value}
            )
            assert refused.status_code == 422, refused.data
            assert _keys(refused) == {(f"confirmations.{name}", required)}
    # The old one tick, alone: every one of the five is named.
    refused = _send(brazos, user, draft["run_id"], confirmations=None, acknowledged=True)
    assert refused.status_code == 422, refused.data
    assert _keys(refused) == {(f"confirmations.{name}", required) for name in FIVE}
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=draft["invoice_id"])
        assert invoice.status == "draft", "nothing issued"
        assert not billing_models.BillRunRelease.objects.filter(
            bill_run_id=draft["run_id"]
        ).exists()


def test_otb_f12__each_confirmation_is_recorded_as_given_with_the_clerk_and_the_moment(
    brazos, dana, audit_rows
):
    """The release row carries the five the clerk ticked, the clerk and Send's
    moment; the audit row lists all five and no longer says *acknowledged*."""
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)
    sent = _send(brazos, user, draft["run_id"])
    assert sent.status_code == 201, sent.data
    codes = {row["code"] for row in sent.data["unavailable"]}
    assert "one_acknowledgement_stands_for_the_five_release_confirmations" not in codes
    with tenant_ctx(brazos):
        release = billing_models.BillRunRelease.objects.get(bill_run_id=draft["run_id"])
        assert release.compliance_confirmed and release.email_mandate_confirmed
        assert release.sms_mandate_confirmed and release.autopay_mandate_confirmed
        assert str(release.confirmed_by_id) == str(user.id)
        assert release.confirmed_at == SENT_AT
    (row,) = [r for r in audit_rows if r["action"] == "invoice.one_time_sent"]
    assert row["after"]["confirmations"] == ALL_FIVE
    assert row["after"]["confirmed_at"] == SENT_AT.isoformat()
    assert row["after"]["confirmed_by"] == str(user.id)
    assert "acknowledged" not in row["after"]


def test_us_bil_033_tc5__send_twice_is_one_bill_with_one_number(brazos, dana):
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user, note="Reconnected after the meter was reset")
    first = _send(brazos, user, draft["run_id"])
    assert first.status_code == 201, first.data
    assert first.data["created"] is True
    assert first.data["invoice_no"] and first.data["due_date"] == "2026-07-30"
    assert first.data["delivery"] == "queued" and first.data["reads"] == "locked"
    second = _send(brazos, user, draft["run_id"])
    assert second.status_code == 200, second.data
    assert second.data["created"] is False
    assert second.data["invoice_no"] == first.data["invoice_no"]
    with tenant_ctx(brazos):
        bills = billing_models.Invoice.objects.filter(bill_run_id=draft["run_id"])
        assert bills.count() == 1
        assert bills.get().status != "draft"
        assert bills.get().bill_payload["note"] == "Reconnected after the meter was reset"
        assert (
            billing_models.BillRunRelease.objects.filter(bill_run_id=draft["run_id"]).count() == 1
        )


def test_otb_a6__a_bill_that_cannot_issue_leaves_nothing_behind(brazos, dana, monkeypatch):
    """ONE BILL OR NOTHING. A break inside issue's own per-bill savepoint (here:
    the delivery queue refusing) must not leave an authorised, RELEASED run over
    a bill that is still a draft — the next Send would answer *already sent*.
    The transaction-shaped claim: proved on PostgreSQL 16 as well (law 14)."""
    from apps.billing.exceptions import BillingRuleError

    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)

    def _refuse(*_args, **_kwargs):
        raise BillingRuleError("the delivery queue refused this bill")

    real = delivery_seam.queue_bill_delivery
    monkeypatch.setattr(delivery_seam, "queue_bill_delivery", _refuse)
    refused = _send(brazos, user, draft["run_id"])
    assert refused.status_code == 422, refused.data
    # DEF-BIL-8288 — the engine's own sentence, never the generic "can't be created as asked".
    assert refused.data["message_key"] == "billing.oneTime.err.engineSaid"
    assert refused.data["params"]["sentence"].endswith("the delivery queue refused this bill.")
    with tenant_ctx(brazos):
        assert billing_models.Invoice.objects.get(pk=draft["invoice_id"]).status == "draft"
        assert not billing_models.BillRunRelease.objects.filter(
            bill_run_id=draft["run_id"]
        ).exists(), "the authorisation rolled back with the failed issue"
    # Only THIS patch is put back — `monkeypatch.undo()` would also undo the
    # suite's autouse GUC fixture.
    monkeypatch.setattr(delivery_seam, "queue_bill_delivery", real)
    sent = _send(brazos, user, draft["run_id"])
    assert sent.status_code == 201, sent.data
    assert sent.data["created"] is True


# ══════════════════════════════════════════════════════════════════════════
# A7 · DELIVERY — the clerk's choice, and paper as the floor
# ══════════════════════════════════════════════════════════════════════════


def test_otb_a7__the_clerks_choice_is_what_the_delivery_seam_queues_for_that_send():
    channels, problem = delivery_seam.elected_channels(None)
    assert channels == () and problem["code"] == "delivery_election_unreadable"
    with delivery_seam.clerk_delivery_choice("paper"):
        assert delivery_seam.elected_channels("any") == ((), None)
    with delivery_seam.clerk_delivery_choice("email"):
        assert delivery_seam.elected_channels("any") == (("email",), None)
    with delivery_seam.clerk_delivery_choice("email_and_paper"):
        assert delivery_seam.elected_channels("any") == (("email",), None)
    # The choice ends with the send, even when the send raises.
    with pytest.raises(RuntimeError), delivery_seam.clerk_delivery_choice("paper"):
        raise RuntimeError("issue broke")
    assert delivery_seam._CLERK_CHANNELS.get() is None
    with pytest.raises(Exception):
        with delivery_seam.clerk_delivery_choice("fax"):
            pass


def test_otb_a6__a_penalty_approval_is_recorded_and_never_refuses():
    """PO 2026-09-30: `approved_by` is a staff user OR a typed name; absent is lawful."""
    assert billing_api._approved_by_from({}) is None
    assert billing_api._approved_by_from({"approved_by": {"name": " Alex Reed "}}) == {
        "name": "Alex Reed"
    }
    assert billing_api._approved_by_from({"approved_by": {"user_id": "u-1", "name": "x"}}) == {
        "user_id": "u-1"
    }
    from core import errors

    with pytest.raises(errors.ValidationError):
        billing_api._approved_by_from({"approved_by": "Alex"})


# ══════════════════════════════════════════════════════════════════════════
# DB2 · DB3 — the three snapshot fields
# ══════════════════════════════════════════════════════════════════════════


def test_otb_db2__a_settlement_path_outside_the_list_is_refused_on_its_field():
    assert one_time_answer.extras_problems({"settlement_path": "collect"}, kind="final") == []
    assert [
        p["message_key"]
        for p in one_time_answer.extras_problems({"settlement_path": "refund"}, kind="final")
    ] == ["billing.oneTime.err.settlementPathUnknown"]
    request = one_time_answer.request_from(
        {
            "account_id": "a",
            "kind": "penalty",
            "sub_periods": [{"period_start": "2026-05-01", "period_end": "2026-05-31"}],
            "reason_code": "THEFT",
            "bill_date": "2026-07-09",
            "due_days": 21,
            "evidence": "Bypass pipe found at the meter",
        }
    )
    assert request.evidence == "Bypass pipe found at the meter"
    assert not hasattr(request, "amount"), "BR-BIL-020 — still nowhere to put money"


# ══════════════════════════════════════════════════════════════════════════
# HARD RULE 1 · TENANT ISOLATION on every new or changed route
# ══════════════════════════════════════════════════════════════════════════


def test_us_bil_033_tc11__another_tenant_cannot_send_preview_or_draft_a_bill(brazos, dana, lonestar):
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)
    stranger = _clerk(lonestar)
    sent = _send(lonestar, stranger, draft["run_id"])
    assert sent.status_code == 404
    with tenant_ctx(brazos):
        account_id = str(billing_models.Invoice.objects.get(pk=draft["invoice_id"]).account_id)
    body = {
        "account_id": account_id,
        "kind": "fee",
        "charge_code": TEST_CODE,
        "bill_date": FEE_ON.isoformat(),
        "due_days": 21,
    }
    previewed = _post(billing_api.one_time_preview, lonestar, stranger, body)
    drafted = _post(billing_api.one_time_create, lonestar, stranger, body)
    assert previewed.status_code in (404, 422)
    assert drafted.status_code in (404, 422)
    assert account_id not in str(previewed.data) and account_id not in str(drafted.data)
    with tenant_ctx(brazos):
        assert (
            billing_models.Invoice.objects.get(pk=draft["invoice_id"]).status == "draft"
        ), "nothing issued across tenants"


# ══════════════════════════════════════════════════════════════════════════
# THE STORIES' TCs BY NAME — DEF-BIL-8308 (G10). The cases above prove US-BIL-033
# TC-4, TC-5 and TC-11 and carry those names; these two are the fee's refusal on
# its field (US-BIL-032 TC-5) and the dropdown's account-number search
# (US-BIL-034 TC-2), each through the code the page actually calls.
# ══════════════════════════════════════════════════════════════════════════


def test_us_bil_032_tc5__a_fee_with_no_charge_code_is_refused_on_its_charge_field():
    found = one_time_answer.problems_in(
        {"account_id": "x", "kind": "fee", "bill_date": "2026-07-09", "due_days": 21}
    )
    assert [(p["field"], p["message_key"]) for p in found] == [
        ("charge_code", "billing.oneTime.err.chargeRequired")
    ]


def test_us_bil_034_tc2__typing_an_account_number_finds_that_one_account(brazos, dana):
    from apps.customers import api as customers_api

    user = _clerk(brazos)
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    response = api_call(
        customers_api.accounts,
        "get",
        user=user,
        role="billing_clerk",
        tenant=brazos,
        query={"q": account.account_no, "per": 20},
    )
    assert response.status_code == 200, response.data
    rows = response.data.get("results") or response.data.get("data") or []
    assert [row["account_no"] for row in rows] == [account.account_no]


def test_us_bil_034_tc_address_prints_its_unit_once_def_bil_8302():
    """DEF-BIL-8302 — customers' `premise` cell is already "address · unit"."""
    request = one_time_answer.request_from(
        {
            "account_id": "018f0000-0000-7000-8000-000000000001",
            "kind": "fee",
            "charge_code": "RECON",
            "bill_date": "2026-07-09",
            "due_days": 21,
        }
    )
    block = one_time_answer.account_block(
        request,
        detail={"premise": "1408 Elm St · Unit A", "unit_label": "Unit A"},
        data=None,
        internal={},
    )
    assert block["address"] == "1408 Elm St · Unit A"


def test_def_bil_8314__a_move_in_fee_line_names_its_charge_code(monkeypatch):
    """A priced line carries `charge_id` only; the answer resolves the code."""
    from types import SimpleNamespace

    from apps.billing import gather

    rows = {"CONN": {"id": "chg-1", "code": "CONN"}}
    monkeypatch.setattr(
        gather, "_resolve", lambda module, name: (lambda code: rows.get(code))
    )
    line = SimpleNamespace(kind="fee", charge_id="chg-1", description="Connection fee")
    assert one_time_answer._fee_line_code(line) == "CONN"
    other = SimpleNamespace(kind="fee", charge_id="chg-9", description="Other fee")
    assert one_time_answer._fee_line_code(other) is None


def test_def_bil_8303__the_tax_rate_is_served_in_percent_points():
    assert one_time_answer._percent_points("0.020000") == "2.000000"
    assert one_time_answer._percent_points("0.0825") == "8.250000"
