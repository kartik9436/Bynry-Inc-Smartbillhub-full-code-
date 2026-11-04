# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-10068 (a one-time DRAFT could not be approved or cancelled,
#           its duplicate refusal said "Already billed" and arrived at the
#           last step) · DEF-BIL-10069 (a one-time bill for a closed month was
#           refused instead of posting forward)
# Ruling:   PO 2026-10-12 — decision log "ONE-TIME BILL ACROSS A MID-PERIOD RATE
#           CHANGE": a draft gets Approve and Cancel; the duplicate check moves
#           to step 1 with "Draft already exists for this period." and Open /
#           Discard; an issued bill is still refused ("Do all three"); Cancel
#           deletes the draft with an audit row and its number is not reused; a
#           closed month posts forward under BR-TEN-038 as corrections do,
#           service period unchanged, "August is closed. Posts to October."
#           ("Okay").
# Rules:    BR-BIL-005 (idempotent) · BR-BIL-004 / hard rule 4 (a draft is not
#           issued) · BR-BIL-1045 / DEF-BIL-9255 (`runs.discard_run`) ·
#           BR-TEN-038 · BR-LED-006 · hard rule 7 (audit)
# Code:     apps/billing/one_time_answer.period_check · api.one_time_create /
#           one_time_period_check · posting_seam._book_date / forward_for
# ───────────────────────────────────────────────────────
"""A draft is a decision waiting to be made; a closed month is not a refusal.

Worked on this repo's July water fixture (`test_def_438_parity`):

* **Step 1 knows.** Before anything is drafted the period check answers
  nothing; after the draft it answers the draft, `status: draft`; a second
  draft is refused with *"Draft already exists for this period."*
  (`billing.oneTime.duplicateDraft`), never *"Already billed"*.
* **Cancel is the existing discard.** `POST /billing/runs/{id}/discard` deletes
  the draft and its lines, writes `bill_run.discarded` to `audit_log`, frees
  the period — and the next draft takes a NEW number, never the cancelled one.
* **An issued bill is still refused** with the old sentence.
* **Closed July and August post to September.** With both closed (the walk's
  own shape), step 1 says so and Send issues the bill: the bill still covers
  1–31 July, the journal entry is dated 1 September — the earliest open
  period — and the forward note is in `audit_log`.

Written RED first (law 7): the period-check route, the draft sentence and the
forward did not exist; the closed-month Send failed with the ledger's
`PostingError` (*"falls inside the CLOSED fiscal period"*).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.ledger import close
from apps.ledger import models as ledger_models
from tests.test_def_438_parity import PERIOD_END, PERIOD_START, _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import ALL_FIVE, _clerk, _post
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SENT_AT = datetime(2026, 8, 10, 15, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` — an interim bill needs a cycle; the name is enough here
    (`test_otb_a_one_time_api_contract`'s own fixture, same reason)."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


def _body(account, **overrides):
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


def _check(tenant, user, account, **overrides):
    response = _post(billing_api.one_time_period_check, tenant, user, _body(account, **overrides))
    assert response.status_code == 200, response.data
    return response.data


def _an_account(brazos, dana):
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
    return account


def _send(tenant, user, run_id):
    payload = {"confirmations": dict(ALL_FIVE), "delivery": "email", "sent_at": SENT_AT.isoformat()}
    return _post(billing_api.one_time_send, tenant, user, payload, run_id=run_id)


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-10068 — the duplicate on step 1, and a draft's two ways out
# ══════════════════════════════════════════════════════════════════════════
def test_step_1_names_a_draft_for_the_period_and_the_second_draft_says_so(brazos, dana):
    user = _clerk(brazos)
    account = _an_account(brazos, dana)
    assert _check(brazos, user, account) == {"duplicate": None, "closed_month": None}

    first = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert first.status_code == 201, first.data

    found = _check(brazos, user, account)["duplicate"]
    assert found["run_id"] == first.data["run_id"]
    assert found["invoice_id"] == first.data["invoice_id"]
    assert found["status"] == "draft"

    again = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert again.status_code == 409
    assert again.data["message_key"] == "billing.oneTime.duplicateDraft", again.data
    assert again.data["params"]["status"] == "draft"


def test_cancel_deletes_the_draft_audits_it_frees_the_period_and_never_reuses_the_number(
    brazos, dana, audit_rows
):
    user = _clerk(brazos)
    account = _an_account(brazos, dana)
    first = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert first.status_code == 201, first.data
    cancelled_no = first.data["invoice_no"]

    gone = _post(billing_api.run_discard, brazos, user, {}, run_id=first.data["run_id"])
    assert gone.status_code == 200, gone.data
    with tenant_ctx(brazos):
        assert not billing_models.Invoice.objects.filter(pk=first.data["invoice_id"]).exists()
        assert not billing_models.InvoiceLine.objects.filter(
            invoice_id=first.data["invoice_id"]
        ).exists()
    (row,) = [r for r in audit_rows if r["action"] == "bill_run.discarded"]
    assert row["after"]["drafts_removed"] == 1

    assert _check(brazos, user, account)["duplicate"] is None, "the period is free again"
    second = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert second.status_code == 201, second.data
    if cancelled_no is not None:
        assert second.data["invoice_no"] != cancelled_no, "a cancelled number is never reused"


def test_an_issued_bill_is_still_refused_as_already_billed(brazos, dana):
    user = _clerk(brazos)
    account = _an_account(brazos, dana)
    first = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert first.status_code == 201, first.data
    sent = _send(brazos, user, first.data["run_id"])
    assert sent.status_code == 201, sent.data

    found = _check(brazos, user, account)["duplicate"]
    assert found["status"] != "draft"
    again = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert again.status_code == 409
    assert again.data["message_key"] == "billing.oneTime.duplicate"
    refused = _post(billing_api.run_discard, brazos, user, {}, run_id=first.data["run_id"])
    assert refused.status_code >= 400, "an issued bill cannot be cancelled"


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-10069 — a closed month posts forward
# ══════════════════════════════════════════════════════════════════════════
def test_a_closed_july_and_august_is_named_on_step_1_and_the_bill_posts_to_september(
    brazos, dana, audit_rows
):
    user = _clerk(brazos)
    account = _an_account(brazos, dana)
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        # The walk's own shape (2026-10-12): TWO months closed, so the entry
        # skips the next one too and lands in the EARLIEST OPEN period.
        closed = ((date(2026, 7, 1), date(2026, 7, 31)), (date(2026, 8, 1), date(2026, 8, 31)))
        for start, end in closed:
            close.close_period(
                dana,
                period_start=start,
                period_end=end,
                closed_at=datetime(2026, 9, 5, 16, 30, tzinfo=UTC),
                reason="DEF-BIL-10069 — July and August are closed",
            )

    note = _check(brazos, user, account)["closed_month"]
    assert note == {
        "requested_period": ["2026-07-01", "2026-07-31"],
        "posted_period": ["2026-09-01", "2026-09-30"],
    }

    drafted = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert drafted.status_code == 201, drafted.data
    sent = _send(brazos, user, drafted.data["run_id"])
    assert sent.status_code == 201, sent.data

    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=drafted.data["invoice_id"])
        assert invoice.status != "draft"
        assert (invoice.period_start, invoice.period_end) == (PERIOD_START, PERIOD_END)
        entry = ledger_models.JournalEntry.objects.get(
            tenant=brazos, source_type="invoice", source_id=invoice.pk
        )
        assert entry.entry_date == date(2026, 9, 1), "BR-TEN-038 — the earliest open day"
    forwarded = [
        r
        for r in audit_rows
        if (r.get("after") or {}).get("period_closed_forward")
        or (r.get("after") or {}).get("audit_context", {}).get("period_closed_forward")
    ]
    assert forwarded, "the forward note reaches audit_log"


def test_an_open_month_posts_on_the_service_date_as_before(brazos, dana):
    user = _clerk(brazos)
    account = _an_account(brazos, dana)
    drafted = _post(billing_api.one_time_create, brazos, user, _body(account))
    assert drafted.status_code == 201, drafted.data
    sent = _send(brazos, user, drafted.data["run_id"])
    assert sent.status_code == 201, sent.data
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=drafted.data["invoice_id"])
        entry = ledger_models.JournalEntry.objects.get(
            tenant=brazos, source_type="invoice", source_id=invoice.pk
        )
        assert entry.entry_date == invoice.service_date
