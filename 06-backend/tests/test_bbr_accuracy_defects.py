# ── Trace ──────────────────────────────────────────────
# Journey:  J72 accuracy walk (clerk checks A1–A6, 2026-09-30 evening) — the
#           walk filed these against the tip; each test is the walk's shape.
# Checks:   20-bulk-run-clerk-acceptance.md A1 (everything adds up), A3 (no
#           account disappears), A6 (every decision traceable)
# Defects:  DEF-BIL-8551 (Estimate refused: no quantity reaches the server) ·
#           DEF-BIL-8552 (Waive: one spelling, a reason) · DEF-BIL-8553
#           (blocked accounts vanish after Send) · DEF-BIL-8554 (Price N counts
#           held accounts) · DEF-BIL-8555 (no decision report) · DEF-BIL-8416
#           (a waived account reads Failed to draft) · DEF-BIL-8474's wider
#           shape (EVERY unanswered decision is queued at Send)
# Rules:    BR-BIL-015 (estimate is a quantity with its unit) · BR-BIL-1054
#           (at Send every account not billed enters Pending billing) · PO
#           2026-09-30 fixed-charge case 2 (Waive needs a reason, bills nothing,
#           carries nothing)
# ───────────────────────────────────────────────────────
"""The accuracy walk's defects, written red first against `e75bf57e1` (the
bulk-run-rest lane rebased onto `f4999860c`)."""

from __future__ import annotations

import pytest

from apps.billing import (
    check_api,
    check_models,
    check_store,
    decisions,
    not_in_run,
    pending,
    runs,
    selectors,
    signoff,
)
from apps.billing import models as billing_models

from tests.test_bbr_check_engine import reads_without_unit, three_accounts
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _checked(brazos, dana, monkeypatch):
    """A-00102 BLOCKED (a reading with no unit); A-00101 and A-00106 READY."""
    cycle, _plan, accounts = three_accounts(brazos, dana)
    reads_without_unit(monkeypatch, accounts["A-00102"].unit_id, meter_unit=None)
    run = a_run(cycle)
    check_store.check_run(run)
    return run, accounts


def _raise(run, account, code, *, params=None, service_code=None):
    """A saved DECISION finding on an account the Check already saved — the
    Check's own record, without building the world that raises it."""
    saved = check_models.BillRunAccountCheck.objects.get(bill_run=run, account_id=account.id)
    check_models.BillRunFinding.objects.create(
        tenant_id=saved.tenant_id,
        bill_run=run,
        account_check=saved,
        account_id=account.id,
        code=code,
        category="payments_and_balances",
        severity="decision",
        service_code=service_code,
        detail=f"{code} on {account.account_no}",
        params=params or {},
    )


def _priced(run):
    prepared = selectors.prepared_for(run)
    runs.calculate_run(decisions.apply_decisions(prepared, bill_run=run), bill_run=run)


def _clerk(brazos):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    return an_actor_user(brazos)


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8554 · Price N is the accounts that will be priced
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-37 · A1
def test_8554__price_n_counts_only_the_accounts_that_will_be_priced(brazos, dana, monkeypatch):
    """Two ready accounts; the clerk HOLDS one. The tiles still say Ready 2
    (answered is ready), and *Price N* must say 1 — the drafts Calculate makes."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        _raise(run, a101, "missing_read", service_code="water")
        decisions.record_decision(
            bill_run=run, account_id=str(a101.id), case="missing_read", choice="hold"
        )
        tiles = check_store.counts(run)
        _priced(run)
        drafts = billing_models.Invoice.objects.filter(bill_run=run).count()
    print(
        f"\nPROOF 8554: ready {tiles['ready']}; to_price {tiles.get('to_price')}; drafts {drafts}"
    )
    assert tiles["to_price"] == drafts == 1
    assert tiles["held"] == 1


# BULK-CHG-37 · A1
def test_8554__a_standing_estimate_does_not_answer_a_missing_read(brazos, dana, monkeypatch):
    """*Answer for all: Estimate* carries no quantity, so Calculate never takes
    it as an answer (`apply_decisions`); the Check must not call the account
    ready on it either — that is the account the server held itself."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        _raise(run, a101, "missing_read", service_code="water")
        decisions.set_standing_answer(bill_run=run, case="missing_read", choice="estimate")
        status = check_store.account_statuses(run)[str(a101.id)]
        tiles = check_store.counts(run)
    assert status == "decision"
    assert tiles["to_price"] == 1  # A-00106 only


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8416 · a waived account is Waived, never Failed to draft
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-37 · BULK-CHG-41 · A1 · A3
def test_8416__a_waived_account_is_waived_on_sign_off_and_listed_after_send(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a106 = accounts["A-00106"]
        _raise(run, a106, "base_only_billing")
        decisions.record_decision(
            bill_run=run,
            account_id=str(a106.id),
            case="base_only_billing",
            choice="waive",
            reason="Vacant all month",
        )
        tiles = check_store.counts(run)
        _priced(run)
        whole = signoff.sign_off_summary(run)["who_is_billed"]
        who = whole["accounts"]
        units = whole["units"]
        pending.queue_not_in_run(bill_run=run)
        listed = not_in_run.not_in_run(run, {})
        queued = billing_models.BillRunExclusion.objects.filter(bill_run=run, account=a106).exists()
    print(f"\nPROOF 8416: {who}")
    assert tiles["to_price"] == 1 and tiles["waived"] == 1
    assert who["failed_to_draft"] == 0 and who["waived"] == 1
    assert who["reconciles"] is True
    # Its UNIT is not billed either (the J72 accuracy walk: 12 units in the
    # cycle, 6 billed, 4 + 1 nobody not billed — the waived unit was nowhere).
    assert units["account_not_billed"] == 2, units  # A-00102 blocked, A-00106 waived
    [row] = [r for r in listed["results"] if r.get("account_no") == "A-00106"]
    assert row["group"] == "waived" and row["queue"] is None
    assert not queued, "a waiver carries nothing (PO case 2)"


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8553 + DEF-BIL-8474 (wider) · every account ends in exactly one place
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40 · A3
@pytest.mark.parametrize("case", sorted(decisions.MUST_ANSWER_CASES))
def test_8474_wider__every_unanswered_must_answer_case_is_queued_at_send(
    brazos, dana, monkeypatch, case
):
    """Not only paid after cut-off: ANY decision Calculate will not price
    unanswered (a price change mid-period on the October walk) leaves the run
    queued, as *held*, with its reason — never with no bill and no row."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101 = accounts["A-00101"]
        _raise(run, a101, case)
        billing_models.Invoice.objects.filter(bill_run=run, account=a101).delete()
        written = pending.queue_not_in_run(bill_run=run)
        row = billing_models.BillRunExclusion.objects.get(bill_run=run, account=a101)
        [listed] = [
            r for r in not_in_run.not_in_run(run, {})["results"] if r.get("account_no") == "A-00101"
        ]
    assert written == 2  # A-00101 undecided + A-00102 blocked
    assert row.reason_code == pending.REASON_CHECK_UNDECIDED
    assert listed["group"] == "held"


# BULK-CHG-40 · A3
def test_8553__after_send_blocked_accounts_are_queued_and_held_ones_read_held(
    brazos, dana, monkeypatch
):
    """The walk's shape: after Send, the BLOCKED account is in Not in this run
    as blocked and in Pending billing; the HELD one reads held, never blocked;
    the priced one is billed. Every account ends in exactly one place."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a101, a102, a106 = accounts["A-00101"], accounts["A-00102"], accounts["A-00106"]
        _raise(run, a101, "missing_read", service_code="water")
        decisions.record_decision(
            bill_run=run, account_id=str(a101.id), case="missing_read", choice="hold"
        )
        _priced(run)
        pending.queue_not_in_run(bill_run=run)
        billed = set(
            billing_models.Invoice.objects.filter(bill_run=run).values_list("account_id", flat=True)
        )
        listed = {
            r["account_no"]: r["group"]
            for r in not_in_run.not_in_run(run, {})["results"]
            if r.get("account_no")
        }
        queued = set(
            billing_models.BillRunExclusion.objects.filter(bill_run=run).values_list(
                "account_id", flat=True
            )
        )
    assert billed == {a106.id}
    assert listed == {"A-00101": "held", "A-00102": "blocked"}
    assert queued == {a101.id, a102.id}


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8551 · an Estimate carries its quantity and unit through the Check
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36 · U5
def test_8551__the_check_decisions_write_records_an_estimate_with_its_quantity(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        clerk = _clerk(brazos)
        a101 = accounts["A-00101"]
        _raise(run, a101, "missing_read", service_code="water")
    body = {
        "case": "missing_read",
        "choice": "estimate",
        "scope": "accounts",
        "account_ids": [str(a101.id)],
        "service_code": "water",
        "amount": "7.5",
        "unit": "kgal",
    }
    made = api_call(
        check_api.run_check_decide,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        data=body,
        run_id=str(run.pk),
    )
    assert made.status_code == 201, made.data
    with tenant_ctx(brazos):
        row = billing_models.BillRunDecision.objects.filter(
            bill_run=run, account=a101, case="missing_read"
        ).last()
        status = check_store.account_statuses(run)[str(a101.id)]
    assert row is not None and row.choice == "estimate"
    assert (str(row.amount.normalize()), row.unit) == ("7.5", "kgal")
    assert status == "ready"


# BULK-CHG-36 · U5
def test_8551__a_no_reading_row_serves_what_the_estimate_box_needs(brazos, dana, monkeypatch):
    """The row carries the account's own average month (metering's figure,
    DEF-2859) or null — the key is always there, so the screen can tell *no
    history* from *not asked*."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        _raise(run, accounts["A-00101"], "missing_read", service_code="water")
        page = check_store.tag_accounts(run, "missing_read", {})
    [row] = page["results"]
    assert "basis" in row


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8552 · Waive: the served spelling, with a reason
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-36 · U5
def test_8552__the_served_choice_is_waive_and_the_write_takes_it_with_a_reason(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        clerk = _clerk(brazos)
        a106 = accounts["A-00106"]
        _raise(run, a106, "base_only_billing")
        [tag] = [
            t
            for c in check_store.findings_summary(run)["categories"]
            for t in c["tags"]
            if t["code"] == "base_only_billing"
        ]

    def post(reason):
        return api_call(
            check_api.run_check_decide,
            "post",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            data={
                "case": "base_only_billing",
                "choice": "waive",
                "scope": "accounts",
                "account_ids": [str(a106.id)],
                **({"reason": reason} if reason else {}),
            },
            run_id=str(run.pk),
        )

    assert "waive" in tag["choices"] and "exclude" not in tag["choices"]
    refused = post(None)
    assert refused.status_code == 422
    assert post("Vacant all month").status_code == 201


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8555 · the check report says who answered what, when
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-53 · A6
def test_8555__the_check_report_serves_each_accounts_answers_with_who_and_when(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        clerk = _clerk(brazos)
        a101, a106 = accounts["A-00101"], accounts["A-00106"]
        _raise(run, a101, "missing_read", service_code="water")
        _raise(run, a106, "base_only_billing")
        decisions.record_decision(
            bill_run=run,
            account_id=str(a106.id),
            case="base_only_billing",
            choice="waive",
            reason="Vacant all month",
            decided_by=clerk,
        )
        decisions.set_standing_answer(
            bill_run=run, case="missing_read", choice="hold", decided_by=clerk
        )
        report = check_store.check_report(run, {})
    rows = {r["account_no"]: r for r in report["accounts"]["results"]}
    [own] = rows["A-00106"]["decisions"]
    assert (own["case"], own["choice"], own["reason"], own["scope"]) == (
        "base_only_billing",
        "waive",
        "Vacant all month",
        "account",
    )
    assert own["decided_by"] and own["decided_at"]
    [standing] = rows["A-00101"]["decisions"]
    assert (standing["case"], standing["choice"], standing["scope"]) == (
        "missing_read",
        "hold",
        "all",
    )
    assert standing["decided_by"] and standing["decided_at"]
    assert rows["A-00102"]["decisions"] == []
