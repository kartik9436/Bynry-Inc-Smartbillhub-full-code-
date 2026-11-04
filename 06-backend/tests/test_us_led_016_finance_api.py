# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-015 (the S42 close endpoints — checklist, close, reopen) ·
#           US-LED-016 (the S42/S43 export endpoints — preview, recorded batch,
#           history, drill-back, dimension extracts) · US-LED-014 (the WRITE
#           half of S41 — recording a remittance)
#           Screens: S41 · S42 · S43
# Rules:    BR-LED-006 · BR-LED-018 (WARN + CONFIRM) · BR-LED-017 (the export
#           needs a CLOSED period) · BR-LED-004 (recorded + IDEMPOTENT) ·
#           BR-LED-007 (drift refuses the handover) · BR-LED-014 (export codes)
#           · BR-LED-002 / BR-LED-013 / BR-LED-019 (the remittance record) ·
#           BR-TEN-038 (auto-forward) · BR-TEN-043 (event time is an INPUT) ·
#           BR-TEN-042 (currency beside every amount — DEF-099) · HR-1
#           (cross-tenant reads as absent) · CLAUDE.md rule 1 · rule 2 · rule 7
# Golden:   LE-1 (598.69 = 598.69) · LE-5 (the July handover and its re-run
#           block) · LE-9 (July closed Aug 5)
# ───────────────────────────────────────────────────────
"""DEF-112 — the finance surface, proved REACHABLE.

**WHY THIS FILE EXISTS.** `apps/ledger/close.py` and `apps/ledger/exports.py`
shipped on 2026-08-15 complete, unit-tested, G7-guarded and correct, each with
`D=deferred(the S42 close endpoints are the API half — not built by this lane)`
in its own Lifecycle trailer. The J19 month-end-close journey then booted a real
stack, signed in through a browser, and went red at STEP 1 — *not on a wrong
figure, on the absence of anything to click*. 2,400 unit tests passed against a
module a human could not open.

So the FIRST TWO TESTS BELOW ARE THE ONES THAT MATTER, and they are about
plumbing rather than money, exactly as `tests/test_us_led_ledger_api.py` argued
for the read half: a module exporting `urlpatterns` is not an endpoint until
`config/urls.py` includes it, and a route the URLconf knows is not reachable
until a real request survives the middleware, the authentication and the
permission class. **401 means the route exists and asked for a sign-in; 404
means there is no route at all** — which is what all nine answered before this
lane, verbatim `django.urls.exceptions.Resolver404`.

Every expected figure is LE-1 / LE-5 / LE-9 through `tests/ledger_le_fixtures.py`.
Nothing here recomputes an expectation.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.ledger import close, finance_api, models, reporting
from core import errors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    ensure_authority_accounts,
    make_accounts,
    post_le1_month,
    post_le3_authorities,
)
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

FROM = JULY_START.isoformat()
TO = JULY_END.isoformat()

#: LE-9 verbatim — "July closed Aug 5".
CLOSED_ON = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)
#: J19 step 4 — "Aug 8 — export JULY to QBO".
SENT_ON = datetime(2026, 8, 8, 9, 0, tzinfo=dt_timezone.utc)
REOPENED_ON = datetime(2026, 8, 20, 11, 0, tzinfo=dt_timezone.utc)

#: The nine paths this lane mounts. Named ONCE so the routing test and the
#: reachability test cannot drift apart — the pair that catches a lost include.
PATHS = (
    ("finance/close-checklist", finance_api.close_checklist),
    ("finance/periods", finance_api.periods),
    ("finance/periods/close", finance_api.close_period),
    ("finance/periods/reopen", finance_api.reopen_period),
    ("finance/export/preview", finance_api.export_preview),
    ("finance/export/batches", finance_api.export_batches),
    ("finance/taxes/remittances", finance_api.record_remittance),
)


def user_with(role):
    """A signed-in user carrying the role the SERVICE guards read.

    `apps/identity/auth.py` attaches `user.role` beside `request.tenant_role`
    (*"for @require_role service guards"*), so a fixture that set only the
    request attribute would pass the permission class and be refused by the
    service — which is a real shape and is asserted separately in TC-6, not the
    default here.
    """
    return SimpleNamespace(id=uuid4(), pk=uuid4(), role=role, is_authenticated=True)


def call(view, tenant, method="get", *, role="billing_clerk", data=None, **kwargs):
    user = user_with(role)
    return api_call(
        view, method, user=user, role=role, tenant=tenant,
        data=data if method != "get" else None,
        query=data if method == "get" else None,
        **kwargs,
    )


def july_books(tenant, actor):
    """LE-1's July, posted through the real posting service (598.69 = 598.69)."""
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def close_july(actor, reason="the deposit register is still being matched"):
    return close.close_period(
        actor, period_start=JULY_START, period_end=JULY_END, closed_at=CLOSED_ON, reason=reason
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO THAT MATTER MOST — DEF-112 itself
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc2a__every_close_and_export_path_is_actually_mounted(brazos):
    """DEF-112 at the routing layer.

    Before `config/urls.py` named `apps.ledger.finance_api`, every line below
    raised `django.urls.exceptions.Resolver404: Resolver404({'tried': [...],
    'path': 'finance/close-checklist'})`. That is the whole defect: the engines
    were complete and no URL reached them.
    """
    from django.urls import resolve

    slug = brazos.subdomain
    for suffix, view in PATHS:
        assert resolve(f"/api/{slug}/{suffix}").func is view, suffix
    assert (
        resolve(f"/api/{slug}/finance/export/batches/{uuid4()}/drill-back").func
        is finance_api.export_drill_back
    )
    assert (
        resolve(f"/api/{slug}/finance/export/extracts/service").func
        is finance_api.export_extract
    )


def test_us_led_016_tc1a__the_close_and_export_paths_are_reachable_over_http(brazos):
    """The other half of "mounted": a real request ARRIVES at these views.

    `resolve()` proves the URLconf knows the path. It does not prove a request
    can get there — tenant middleware, session authentication and the permission
    class all sit in front, and any one of them answering 404 would leave S42 and
    S43 exactly as unreachable as they were. So an UNAUTHENTICATED call is made
    and its refusal is read: **401 means the route exists and asked for a
    sign-in; 404 means there is no route.**
    """
    from django.test import Client

    client = Client()
    slug = brazos.subdomain
    for suffix, _view in PATHS:
        method = client.post if "close" in suffix or "remittance" in suffix else client.get
        if suffix == "finance/close-checklist":
            method = client.get
        response = method(f"/api/{slug}/{suffix}")
        assert response.status_code != 404, f"{suffix} has NO ROUTE — this is DEF-112"
        assert response.status_code in (401, 403), (suffix, response.status_code)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-015 — the close checklist and the close (TC-1 · TC-2 · TC-4 · TC-6)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc1__the_checklist_endpoint_serves_five_items_and_three_unknowns(brazos):
    """TC-1 — five computed items, and the third state served as itself.

    `unknown` is NOT flattened into `incomplete` on the wire. The distinction is
    the difference between *"we looked and it is not done"* and *"nobody can
    look"*, and the three seam items each name the callable they want.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        response = call(
            finance_api.close_checklist, brazos, data={"from": FROM, "to": TO}
        )
    assert response.status_code == 200
    body = response.data
    assert [item["code"] for item in body["items"]] == list(close.CHECKLIST_ITEMS)
    states = {item["code"]: item["state"] for item in body["items"]}
    assert states[close.ITEM_RUNS_ISSUED] == close.STATE_UNKNOWN
    # ⚠ SUPERSEDED 2026-09-01 (CR-059 CS-13) — see the same change in
    # test_us_led_015_month_close.py for the reasoning. The item was pinned to
    # UNKNOWN because no caller could count; it can now, and this tenant has no
    # batches outstanding, so it is COMPLETE over a measured zero.
    assert states[close.ITEM_BATCHES_RECONCILED] == close.STATE_COMPLETE
    assert states[close.ITEM_BANK_REC_CURRENT] == close.STATE_UNKNOWN
    unknowns = [item for item in body["items"] if item["state"] == close.STATE_UNKNOWN]
    assert all(item["wanted_reads"] for item in unknowns), "an unknown item must name its read"
    assert body["closed"] is False
    assert body["ready"] is False
    # ⚠ AMENDED 2026-09-24 — this asserted the screen could SEE the role-gate
    # reading. The PO ruled the gate that day, the marker is retired, and the
    # served list is empty: no sentence about the gate reaches the close panel.
    assert body["unavailable"] == []


def test_us_led_015_tc2__closing_july_needs_a_reason_and_then_closes(brazos):
    """TC-2 + BR-LED-018 — the WARN is a 422 naming the items, not a lockout.

    Both halves in one test on purpose: the same request, with a reason added,
    must succeed. A refusal that could not be satisfied would be the hard lockout
    BR-LED-018 forbids.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        body = {"from": FROM, "to": TO, "closed_at": CLOSED_ON.isoformat()}
        warned = call(finance_api.close_period, brazos, "post", role="system_admin", data=body)
        assert warned.status_code == 422
        assert warned.data["code"] == errors.BIZ_APPROVAL
        assert warned.data["br_ref"] == "BR-LED-018"
        assert warned.data["params"]["count"] == len(warned.data["params"]["incomplete"])
        assert close.ITEM_RUNS_ISSUED in warned.data["params"]["incomplete"]

        confirmed = call(
            finance_api.close_period,
            brazos,
            "post",
            role="system_admin",
            data={**body, "reason": "deposit register still being matched"},
        )
    assert confirmed.status_code == 201
    assert confirmed.data["status"] == models.PERIOD_CLOSED
    assert confirmed.data["reason"] == "deposit register still being matched"
    # J19 step 1: "reason + incomplete-item snapshot recorded on the close".
    assert len(confirmed.data["incomplete_items"]) >= 3


def test_us_led_015_tc2b__a_second_close_of_the_same_month_is_refused(brazos):
    """Closing twice would overwrite the FIRST close's reason and snapshot —
    the record J19 step 1 asks for. 409 BIZ-LOCKED, never a silent overwrite."""
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        close_july(actor)
        again = call(
            finance_api.close_period,
            brazos,
            "post",
            role="system_admin",
            data={"from": FROM, "to": TO, "closed_at": CLOSED_ON.isoformat(), "reason": "again"},
        )
    assert again.status_code == 409
    assert again.data["code"] == errors.BIZ_LOCKED


def test_us_led_015_tc2c__closed_at_is_required_because_nothing_here_reads_a_clock(brazos):
    """BR-TEN-043 — the moment a period shut is a business fact the caller
    states. A defaulted `now()` would stamp a different instant on a retry."""
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        response = call(
            finance_api.close_period, brazos, "post", role="system_admin",
            data={"from": FROM, "to": TO, "reason": "x"},
        )
    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_REQUIRED
    assert response.data["message_key"] == "ledger.close.closed_at_required"


def test_us_led_015_tc4__reopen_is_system_admin_only_and_needs_a_reason(brazos):
    """TC-4 — a Billing Clerk who may close a month may NOT reopen one.

    This is the one role gate in the close family that IS separately ruled
    (BR-LED-006 and BR-TEN-038 both say *SysAdmin reopens*), unlike the close
    gate, which is carried as a flagged reading of OQ-175.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        close_july(actor)
        body = {"from": FROM, "to": TO, "reopened_at": REOPENED_ON.isoformat()}
        clerk = call(
            finance_api.reopen_period, brazos, "post", role="billing_clerk",
            data={**body, "reason": "a correction must land in July"},
        )
        assert clerk.status_code == 403

        no_reason = call(
            finance_api.reopen_period, brazos, "post", role="system_admin", data=body
        )
        assert no_reason.status_code == 422
        assert no_reason.data["message_key"] == "ledger.reopen.reason_required"

        reopened = call(
            finance_api.reopen_period, brazos, "post", role="system_admin",
            data={**body, "reason": "a correction must land in July"},
        )
    assert reopened.status_code == 200
    assert reopened.data["status"] == models.PERIOD_OPEN


def test_us_led_015_tc6__an_executive_may_not_close_the_month(brazos):
    """TC-6 — the role gate is server-enforced, at the door and at the service.

    ⚠ The gate is RULED as of 2026-09-24 (PO, *"system admin and clark"*,
    BR-LED-006 amended) and no longer carries a reading marker. What is asserted
    here is unchanged and is the reason this test exists: the API layer and the
    service layer agree — a mismatch would answer 403 in one and 200 in the other.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        response = call(
            finance_api.close_period, brazos, "post", role="executive",
            data={"from": FROM, "to": TO, "closed_at": CLOSED_ON.isoformat(), "reason": "x"},
        )
    assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-016 — the export (TC-1 · TC-2 · TC-3 · TC-4 · TC-6)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc1__the_preview_foots_to_le1_and_carries_its_currency(brazos):
    """LE-1 through the wire: **598.69 = 598.69**, balanced, with `currency`.

    DEF-099 is the second assertion and it is not decoration: a money body with
    no CHAR(3) makes the screen guess, and guessing `USD` prints a wrong symbol
    on a Canadian tenant's books.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        july = reporting.trial_balance(start=JULY_START, end=JULY_END)
        response = call(
            finance_api.export_preview,
            brazos,
            data={"from": FROM, "to": TO, "target": models.EXPORT_QBO},
        )
    assert response.status_code == 200
    body = response.data
    assert body["currency"] == "USD"
    assert body["balanced"] is True
    # ⚠ **LE-5's 598.69 is the WHOLE-BOOK footing, not the July window's.**
    # LE-1's opening-balance entry is dated BEFORE July, so the July-windowed
    # trial balance foots at 553.69 and the book at 598.69 — both are LE-1 and
    # `tests/test_us_led_016_export.py` records the same distinction. What is
    # asserted is the PROPERTY (the preview equals the period's trial balance),
    # never a retyped figure: a test that hardcoded a total would agree with a
    # broken implementation the day the window changed.
    assert Decimal(body["period_total_debits"]) == Decimal(body["period_total_credits"])
    assert Decimal(body["period_total_debits"]) == july["total_debit"]
    assert body["period_closed"] is False  # July is still open at this point
    assert body["sendable"] is False
    assert all(row["currency"] == "USD" for row in body["rows"])
    # BR-LED-039 / US-LED-021 TC-7: the payable side is carried SEPARATELY and
    # is not inside the footing above.
    assert body["cost_section"]["in_trial_balance"] is False


def test_us_led_016_tc6__an_open_july_refuses_the_export(brazos):
    """BR-LED-017, J19 step 3 — *the ERP never receives numbers that can still
    move*. 409 BIZ-LOCKED, and the refusal writes a BR-AUD-018 attempt row."""
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        response = call(
            finance_api.export_batches, brazos, "post", role="system_admin",
            data={
                "from": FROM, "to": TO, "target": models.EXPORT_QBO,
                "created_at": SENT_ON.isoformat(),
            },
        )
    assert response.status_code == 409
    assert response.data["code"] == errors.BIZ_LOCKED
    assert response.data["br_ref"] == "BR-LED-017"


def test_us_led_016_tc2__july_exports_once_and_a_re_run_is_blocked_with_the_link(brazos):
    """LE-5 / J19 steps 4-5 — the handover happens once, forever.

    The 409 carries the EXISTING batch on `params`, because T5-07's recovery path
    is *re-DOWNLOAD, never re-export*: a refusal without the link sends a clerk
    hunting for it.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        close_july(actor)
        july = reporting.trial_balance(start=JULY_START, end=JULY_END)
        body = {
            "from": FROM, "to": TO, "target": models.EXPORT_CSV,
            "created_at": SENT_ON.isoformat(),
        }
        first = call(finance_api.export_batches, brazos, "post", role="system_admin", data=body)
        assert first.status_code == 201, first.data
        assert first.data["currency"] == "USD"
        assert Decimal(first.data["total_debits"]) == july["total_debit"]
        assert Decimal(first.data["total_credits"]) == july["total_credit"]
        batch_id = first.data["batch_id"]

        again = call(finance_api.export_batches, brazos, "post", role="system_admin", data=body)
        assert again.status_code == 409
        assert again.data["code"] == errors.BIZ_IDEMPOTENT
        assert again.data["params"]["batch_id"] == batch_id

        history = call(finance_api.export_batches, brazos, data={})
    assert history.status_code == 200
    assert history.data["count"] == 1
    assert history.data["rows"][0]["batch_id"] == batch_id


def test_us_led_016_tc3__drill_back_reaches_the_dimensioned_lines(brazos):
    """TC-3 — *"what is the 506.31?"* answered in journal lines, LE-5 verbatim.

    The figure is read out of the STORED payload, so the answer is what was
    HANDED OVER rather than what the books say now — the question an auditor
    holding the ERP's copy is actually asking.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        close_july(actor)
        created = call(
            finance_api.export_batches, brazos, "post", role="system_admin",
            data={
                "from": FROM, "to": TO, "target": models.EXPORT_CSV,
                "created_at": SENT_ON.isoformat(),
            },
        )
        batch_id = created.data["batch_id"]
        code = next(
            row["code"] for row in created.data and call(
                finance_api.export_preview, brazos,
                data={"from": FROM, "to": TO, "target": models.EXPORT_CSV},
            ).data["rows"]
            if row["type"] == "revenue"
        )
        drill = call(
            finance_api.export_drill_back, brazos, data={"code": code}, batch_id=batch_id
        )
    assert drill.status_code == 200
    assert drill.data["currency"] == "USD"
    assert drill.data["exported"], "an exported figure must be found in the stored payload"
    assert drill.data["lines"], "every exported figure drills back to its lines (BR-LED-004)"


def test_us_led_016_tc4__the_dimension_extracts_serve_and_by_premises_refuses(brazos):
    """TC-4 — by service · by authority · by premises.

    ⚠ **THE PREMISES EXTRACT USED TO ANSWER `available: false`** with the figure
    it could not attribute, because `journal_lines.premises_id` was NULL on
    every line (US-LED-002 unbuilt) and an empty table would have read as *no
    activity this period* over 553.69 of billed money. US-LED-002 landed on
    2026-08-16, so the extract SERVES: an ERP now receives the money split by
    premises, and the residue it cannot attribute is 0.00 rather than all of it.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        by_service = call(
            finance_api.export_extract, brazos, data={"from": FROM, "to": TO}, kind="service"
        )
        by_premises = call(
            finance_api.export_extract, brazos, data={"from": FROM, "to": TO}, kind="premises"
        )
        nonsense = call(
            finance_api.export_extract, brazos, data={"from": FROM, "to": TO}, kind="by_unicorn"
        )
    assert by_service.status_code == 200
    assert by_service.data["rows"]
    assert by_premises.status_code == 200
    assert by_premises.data["available"] is True
    assert by_premises.data["rows"]
    assert Decimal(by_premises.data["unattributed_billed"]) == Decimal("0")
    assert nonsense.status_code == 422


def test_us_led_016_tc7__another_tenants_batch_is_absent_not_forbidden(brazos, lonestar):
    """TC-7 / HR-1 — a foreign batch id answers **404**, never 403.

    Existence must not leak: a 403 would confirm the batch is real.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        close_july(actor)
        created = call(
            finance_api.export_batches, brazos, "post", role="system_admin",
            data={
                "from": FROM, "to": TO, "target": models.EXPORT_CSV,
                "created_at": SENT_ON.isoformat(),
            },
        )
        batch_id = created.data["batch_id"]
    with tenant_ctx(lonestar):
        stolen = call(
            finance_api.export_drill_back, lonestar, data={"code": "4100"}, batch_id=batch_id
        )
    assert stolen.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-014 — the remittance WRITE half (TC-3 · TC-6)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc3__recording_a_remittance_drains_the_authority_liability(brazos):
    """LE-3 — State of Texas, **13.87**: DR 2200-01 / CR cash, balanced.

    The amount is the CALLER's — the figure a human read off S41 and actually
    paid. Deriving it here would make the payment agree with the report by
    construction, which is the property that hides a wrong report.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        accounts = make_accounts(actor, brazos, {})
        authorities = ensure_authority_accounts(brazos, actor)
        post_le3_authorities(brazos, accounts, authorities)
        state = authorities["2200-01"]
        response = call(
            finance_api.record_remittance, brazos, "post", role="system_admin",
            data={
                "tax_account_id": str(state.id),
                "from": FROM,
                "to": TO,
                "amount": "13.87",
                "basis": "collected",
                "confirmation_ref": "TXC-2026-08-9012",
                "entry_date": "2026-08-18",
                "posted_at": "2026-08-18T14:00:00+00:00",
            },
        )
    assert response.status_code == 201, response.data
    assert response.data["currency"] == "USD"
    assert Decimal(response.data["amount"]) == Decimal("13.87")
    assert response.data["confirmation_ref"] == "TXC-2026-08-9012"
    assert response.data["tax_account_code"].startswith("2200")


def test_us_led_014_tc6__a_remittance_without_its_confirmation_ref_is_refused(brazos):
    """BR-LED-019 — the confirmation ref is the only auditor artifact this build
    can keep (`tax_remittances` is not in the schema), so recording without it
    would drain the liability and leave nothing proving the return was filed."""
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        accounts = make_accounts(actor, brazos, {})
        authorities = ensure_authority_accounts(brazos, actor)
        post_le3_authorities(brazos, accounts, authorities)
        response = call(
            finance_api.record_remittance, brazos, "post", role="system_admin",
            data={
                "tax_account_id": str(authorities["2200-01"].id),
                "from": FROM,
                "to": TO,
                "amount": "13.87",
                "basis": "collected",
                "posted_at": "2026-08-18T14:00:00+00:00",
            },
        )
    assert response.status_code == 422
    assert response.data["message_key"] == "ledger.remittance.confirmation_required"


def test_us_led_014_tc6b__a_float_amount_is_refused_at_the_door(brazos):
    """CLAUDE.md rule 2. A JSON float has ALREADY lost digits by the time it
    reaches this layer, so it is refused rather than converted — a conversion
    hides the place where money became binary."""
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        accounts = make_accounts(actor, brazos, {})
        authorities = ensure_authority_accounts(brazos, actor)
        post_le3_authorities(brazos, accounts, authorities)
        response = call(
            finance_api.record_remittance, brazos, "post", role="system_admin",
            data={
                "tax_account_id": str(authorities["2200-01"].id),
                "from": FROM,
                "to": TO,
                "amount": 13.87,
                "basis": "collected",
                "confirmation_ref": "TXC-1",
                "posted_at": "2026-08-18T14:00:00+00:00",
            },
        )
    assert response.status_code == 422
    assert response.data["message_key"] == "ledger.remittance.amount_invalid"


# ═══════════════════════════════════════════════════════════════════════════
# DEF-095 — one spelling for a period bound, asserted from the SERVER side
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_016_tc1b__a_period_bound_is_read_bare_and_never_under_an_f_prefix(brazos):
    """DEF-095, from the half that was never checked.

    The frontend sent `f.from` / `f.to` under BR-SHL-011's LIST grammar to three
    endpoints that read the bare names, so three screens asked for a window the
    server never saw and two of them answered 422. Nothing caught it because the
    frontend suite asserted the wrapper's OUTPUT against a hand-built response
    and the backend suite called its own views with the names it reads — each
    half internally consistent, never compared.

    **A period bound is not a list filter.** This asserts the server's side of
    the one spelling: the bare names work and the prefixed ones are not a second
    accepted door.
    """
    with tenant_ctx(brazos):
        actor = admin_actor()  # noqa: F405
        with_monthly_fiscal_year(actor)
        july_books(brazos, actor)
        bare = call(finance_api.close_checklist, brazos, data={"from": FROM, "to": TO})
        prefixed = call(finance_api.close_checklist, brazos, data={"f.from": FROM, "f.to": TO})
    assert bare.status_code == 200
    assert prefixed.status_code == 422
    assert prefixed.data["message_key"] == "ledger.report.period_required"
