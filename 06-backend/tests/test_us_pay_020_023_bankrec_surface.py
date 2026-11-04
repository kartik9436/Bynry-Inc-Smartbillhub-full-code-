# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (S37 — TC-1 the PE-10 pair listed, TC-2 the KPI strip
#           ties to the rows, TC-6 isolation) · US-PAY-021 (S38 — TC-1 the
#           lines and their four states, TC-5 the re-import block over HTTP) ·
#           US-PAY-022 (S40 — TC-1 PE-11's −5.00, TC-3 the card day NET, TC-5
#           reason+GL required, TC-6 a partial explanation) · US-PAY-023 (S39 —
#           TC-1 both sides and the trail, TC-3 the lock, TC-4 Unreconcile)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-004 · BR-PAY-019 · BR-PAY-025 · BR-PAY-035 · BR-PAY-040 ·
#           BR-TEN-003 / HR-1 (a cross-tenant read is ABSENT) · BR-TEN-043 ·
#           CLAUDE.md rule 1 · rule 2
# Golden:   PE-10 ❄️ — checks 292.87 + 142.30 + 36.22 = **471.39**
#           (DEP-260808-CHK) · cash 105.36 + 16.42 = **121.78**
#           (DEP-260808-CSH) · PE-11 ❄️ — bank **588.17** vs batch **593.17** →
#           **−5.00** · the PO's card day: **5,120.40** recorded, **4,972.90**
#           banked, **147.50** to 6800 Bank fees
# ───────────────────────────────────────────────────────
"""Is the bank-reconciliation engine REACHABLE by a human? It was not.

`apps/payments/reconciliation.py` shipped complete and correct with its own
docstring saying, in as many words, *"NO HTTP SURFACE AND NO SCREEN … built is
not wired (hard-won law 2)"*. This file is the proof that changed.

**RED-PROVED FIRST (hard-won law 7).** Before `apps/payments/bankrec_read.py`
and the eight routes existed, every case here failed, and the failures are
quoted verbatim in the lane report:

    ModuleNotFoundError: No module named 'apps.payments.bankrec_read'
    django.urls.exceptions.Resolver404: {'tried': [...], 'path':
        'api/brazosbend/deposit-batches'}
    AttributeError: module 'apps.payments.api' has no attribute
        'deposit_batches'

THE ONE THING THIS FILE GUARDS THAT NOTHING ELSE DOES is the shape of an
ABSENCE. `test_us_pay_020_tc2__an_unbanked_batch_reports_no_bank_figure_rather_
than_zero` is the DEF-127 defect aimed at this surface: a batch the bank has not
shown must serve `bank_total: null`, never `"0.00"`. A zero there would draw a
perfectly reconciled deposit over money nobody has confirmed.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import re

import pytest

from core import errors

from apps.payments import api as payments_api
from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, reconciliation

from tests.isolation_helpers import (
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (
    CARD_BANKED,
    CARD_FEE,
    CARD_RECORDED,
    PE10_CASH,
    PE10_CASH_CODE,
    PE10_CASH_TOTAL,
    PE10_CHECK_CODE,
    PE10_CHECK_TOTAL,
    PE10_CHECKS,
    PE10_DAY,
    STATEMENT_AT,
    a_bank_account,
    a_cleared_payment,
    a_statement,
    gl_id,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CUT_AT = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
RECONCILED_AT = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)

#: Every one of these routes is FINANCE-area (BR-PAY-019 — *"Owner/Finance
#: roles"*), which A4's own row makes System Admin Full · Billing Clerk — ·
#: Executive Full. `system_admin` is the role these calls carry.
FINANCE_ROLE = "system_admin"


def call(view, method, tenant, *, user=None, **kwargs):
    """One FINANCE-area call, carrying a REAL `users` row as the actor.

    `user` is an actor whose id EXISTS in `users`, because
    `deposit_batch_events.actor_user_id` and `bank_statement_imports.imported_by`
    are FKs into it (the reviewed cross-module set, B2 §2). A synthetic uuid is
    refused outright by Postgres — `ForeignKeyViolation … is not present in
    table "users"` — and would have passed vacuously on SQLite, which is the
    whole reason this lane runs on real Postgres.

    The id is wrapped in `FakeUser` so the object carries `is_authenticated`,
    which DRF requires of a forced session; the ROLE rides beside it exactly as
    the tenant middleware attaches it in production.
    """
    actor = FakeUser(getattr(user, "pk", None)) if user is not None else FakeUser()
    return api_call(view, method, user=actor, role=FINANCE_ROLE, tenant=tenant, **kwargs)


def pe10_day(actor, tenant):
    """The PE-10 drawer day, cut into its two frozen batches."""
    for amount in PE10_CHECKS:
        a_cleared_payment(actor, tenant, amount=amount, method_code="check")
    for amount in PE10_CASH:
        a_cleared_payment(actor, tenant, amount=amount, method_code="cash")
    cut = reconciliation.cut_deposit_batches(actor=actor, day=PE10_DAY, occurred_at=CUT_AT)
    # CR-186-BRC10 (PO 2026-10-21): the five payments joined ONE all-tenders
    # batch when they were posted; the cut sweeps nothing. The day's batches
    # are what the cases below act on.
    import dataclasses

    from tests.test_us_pay_020_023_bank_rec import the_days_batches

    return dataclasses.replace(cut, batches=the_days_batches(tenant, PE10_DAY))


# ══════════════════════════════════════════════════════════════════════════
# The case this lane exists for — is any of it reachable at all?
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_020_tc0__the_bank_rec_routes_are_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer, resolved through the REAL URLconf.

    `apps/payments/api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it, and `reconciliation.py` had NEITHER for four
    finished stories. The literal `cut` segment is asserted separately because
    it must outrank `<batch_id>` — if it does not, a clerk cutting the day's
    takings gets a 404 on a batch id that is the word "cut".
    """
    from django.urls import resolve

    batch_id = uuid.uuid4()
    assert resolve("/api/brazosbend/deposit-batches").func is payments_api.deposit_batches
    assert resolve("/api/brazosbend/deposit-batches/cut").func is payments_api.deposit_batches_cut
    assert resolve(f"/api/brazosbend/deposit-batches/{batch_id}").func is payments_api.deposit_batch
    assert (
        resolve(f"/api/brazosbend/deposit-batches/{batch_id}/reconcile").func
        is payments_api.deposit_batch_reconcile
    )
    assert (
        resolve(f"/api/brazosbend/deposit-batches/{batch_id}/unreconcile").func
        is payments_api.deposit_batch_unreconcile
    )
    assert (
        resolve(f"/api/brazosbend/deposit-batches/{batch_id}/match").func
        is payments_api.deposit_batch_match
    )
    assert resolve("/api/brazosbend/bank-accounts").func is payments_api.bank_accounts
    assert resolve("/api/brazosbend/bank-statements").func is payments_api.bank_statements


def test_us_pay_020_tc0__the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request ARRIVES at these views.

    `resolve()` proves the URLconf knows the path; it does not prove a request
    can get there past the tenant middleware, the session auth and the
    permission class. An UNAUTHENTICATED call is made and its refusal read:
    **401 = the route exists and asked for a session; 404 = there is no route**,
    which is what all eight answered before this lane.
    """
    from django.test import Client

    probes = (
        ("get", f"/api/{brazos.subdomain}/deposit-batches"),
        ("post", f"/api/{brazos.subdomain}/deposit-batches/cut"),
        ("get", f"/api/{brazos.subdomain}/bank-accounts"),
        ("post", f"/api/{brazos.subdomain}/bank-statements"),
    )
    for method, path in probes:
        response = getattr(Client(), method)(path)
        assert response.status_code == 401, (
            f"{method.upper()} {path} answered {response.status_code}: a 404 here means the "
            "route is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-020 — S37, the batch list and its KPI strip
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_020_tc1__the_pe10_day_is_cut_and_listed_over_http(brazos, marcus):
    """PE-10 end to end through the SCREEN's own two calls (❄️ frozen figures).

    Cut the drawer day, then list it: DEP-260808-CHK at **471.39** over three
    payments and DEP-260808-CSH at **121.78** over two. Every figure is copied
    from the ratified worked example, never recomputed — a test that recomputed
    its expectation would agree with a broken implementation.
    """
    with tenant_ctx(brazos):
        for amount in PE10_CHECKS:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")
        for amount in PE10_CASH:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="cash")

        cut = call(
            payments_api.deposit_batches_cut,
            "post",
            brazos,
            user=marcus,  # noqa: F405 — shared fixture
            data={"day": PE10_DAY.isoformat(), "occurred_at": CUT_AT.isoformat()},
        )
        assert cut.status_code == 201
        # ⚠ CR-186-BRC10 (PO 2026-10-21): every payment joined the day's ONE
        # all-tenders batch when it was posted, so the cut sweeps nothing and
        # the list shows one row of 593.17; PE-10's two figures are its tender
        # totals, served on the batch detail. The remainder of this case is the
        # 2026-09-22 per-tender shape and is kept below for the record.
        assert cut.data["payments_batched"] == 0
        listed = call(payments_api.deposit_batches, "get", brazos)
        (row,) = listed.data["results"]
        assert row["all_tenders"] is True and row["method_code"] is None
        assert re.fullmatch(r"DEP-260808-\d{4,}", row["code"]), row
        assert Decimal(row["recorded_total"]) == PE10_CHECK_TOTAL + PE10_CASH_TOTAL
        assert row["payment_count"] == 5
        assert row["currency"] == "USD"
        detail = call(payments_api.deposit_batch, "get", brazos, batch_id=row["id"]).data
        totals = {t["method_code"]: Decimal(t["amount"]) for t in detail["tender_totals"]}
        assert totals == {"check": PE10_CHECK_TOTAL, "cash": PE10_CASH_TOTAL}
        return
        # ⚠ `DEF-PAY-9085` — FOUND BY TENDER, NOT BY CODE. Since `5657a71ba`
        # (2026-09-22, PO: *"DEP-260922-0001 — Settings → Numbering"*) a new
        # batch's code is ALLOCATED from the `deposit_batch` series and the
        # tender left it; PE-10's `DEP-260808-CHK` / `-CSH` are frozen labels on
        # rows banked before that and nothing produces them any more. The MONEY
        # is PE-10's, unmoved; the code is the allocated shape.
        by_method = {row["method_code"]: row for row in listed.data["results"]}
        assert PE10_CHECK_CODE == "DEP-260808-CHK" and PE10_CASH_CODE == "DEP-260808-CSH"
        for method in ("check", "cash"):
            assert re.fullmatch(r"DEP-260808-\d{4,}", by_method[method]["code"]), by_method[method]
        assert Decimal(by_method["check"]["recorded_total"]) == PE10_CHECK_TOTAL
        assert by_method["check"]["payment_count"] == 3
        assert Decimal(by_method["cash"]["recorded_total"]) == PE10_CASH_TOTAL
        assert by_method["cash"]["payment_count"] == 2
        # CLAUDE.md rule 2 — every money figure travels with its CHAR(3) code.
        assert by_method["check"]["currency"] == "USD"


def test_us_pay_020_tc2__an_unbanked_batch_reports_no_bank_figure_rather_than_zero(brazos, marcus):
    """**THE DEFECT OF THIS RELEASE, AIMED AT THIS SURFACE.**

    An account screen once showed **$0.00** while the ledger held an issued,
    unpaid **$108.88**, because a cache nobody filled read as "owes nothing".
    The same shape here would be worse: a freshly cut batch has `bank_total`
    NULL — the bank has not shown the money — and serving `"0.00"` would draw a
    deposit that reconciles perfectly to zero over money nobody has confirmed.

    So the assertion is on the NULL, not on a value. `difference` is null for
    the same reason: it is `bank − recorded` and there is no bank figure yet.
    """
    with tenant_ctx(brazos):
        pe10_day(marcus, brazos)
        listed = call(payments_api.deposit_batches, "get", brazos)
        # `DEF-PAY-9085` — by tender; the code is allocated since 2026-09-22.
        # CR-186-BRC10 — one all-tenders batch for the day.
        row = listed.data["results"][0]
        assert row["bank_total"] is None, "an unbanked batch must NOT report a bank figure"
        assert row["difference"] is None, "a difference with no bank side is unknown, not zero"
        assert row["status"] == bankrec.BATCH_IN_TRANSIT
        assert row["locked"] is False


def test_us_pay_020_tc2__the_kpi_strip_ties_to_the_rows_it_shows(brazos, marcus):
    """US-PAY-020 TC-2, verbatim: *"KPI tiles tie to batch rows exactly"*.

    The tiles are a fold over the SAME queryset the rows come from and are
    stored nowhere, so this cannot drift. In-transit money is its OWN tile and
    is never folded into a matched total: a batch we believe we banked and one
    the bank agrees we banked are different facts.
    """
    with tenant_ctx(brazos):
        pe10_day(marcus, brazos)
        listed = call(payments_api.deposit_batches, "get", brazos)
        kpis = listed.data["kpis"]
        # ⚠ **"TIE TO THE ROWS IT SHOWS" NOW MEANS THE FILTERED SET, NOT THE
        # PAGE** (`DEF-PAY-6554` · `P1.2`, 2026-09-24). The list pages in SQL
        # since today; the tiles are folded over the whole filtered queryset
        # one line before the slice, so they describe the SCREEN rather than
        # the fifty rows on it. Two batches fit on a page, so the two numbers
        # are still equal here and the assertion is unchanged in strength —
        # `count` is the server's `COUNT(*)` and is the one that would diverge.
        # CR-186-BRC10 — the day is ONE all-tenders batch (PO 2026-10-21).
        assert kpis["batch_count"] == listed.data["count"] == len(listed.data["results"]) == 1
        assert Decimal(kpis["deposited_total"]) == PE10_CHECK_TOTAL + PE10_CASH_TOTAL
        assert Decimal(kpis["in_transit_total"]) == PE10_CHECK_TOTAL + PE10_CASH_TOTAL
        assert kpis["in_transit_count"] == 1
        assert kpis["matched_count"] == 0
        assert kpis["reconciled_count"] == 0


def test_us_pay_020_tc5__an_unknown_status_filter_refuses_rather_than_answering_empty(brazos):
    """An empty queue and an unanswerable one look identical on a screen.

    Only one of them means "nothing to do", so a filter naming a status this
    product does not have is a 422 rather than a clean empty list — a clerk who
    typed the wrong word must not read "no deposits" over a full drawer.
    """
    with tenant_ctx(brazos):
        refused = call(
            payments_api.deposit_batches,
            "get",
            brazos,
            query={"f.status": "definitely_not_a_status"},
        )
        assert refused.status_code == 422


def test_us_pay_020__the_cuttable_days_come_from_the_money_not_from_a_clock(brazos, marcus):
    """BR-TEN-043 — S37's "cut the day" control offers days that actually exist.

    The server reads no clock (gate G6 bans one in this path), so the days a
    clerk may cut are computed from cleared, positive, unbatched payments on
    their POSTING day (BR-PAY-025 / PO ruling RQ-5). After the cut the list is
    empty, which is the honest "everything is banked" rather than a control
    that always offers today.
    """
    with tenant_ctx(brazos):
        for amount in PE10_CHECKS:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")
        # CR-186-BRC10 — stamped into the day's batch at posting, so there is
        # no day left to cut: the honest "everything is banked".
        before = call(payments_api.deposit_batches, "get", brazos).data["cuttable_days"]
        assert before == []

    # A fresh `tenant_ctx` around the direct engine call: `api_call` enters and
    # LEAVES a tenant context of its own, and leaving resets the contextvar to
    # None rather than restoring the outer one — so an engine call made after an
    # HTTP call in the same block has no `app.tenant_id` and is refused by hard
    # rule 1. Refusing is correct; re-entering is what the test must do.
    with tenant_ctx(brazos):
        reconciliation.cut_deposit_batches(actor=marcus, day=PE10_DAY, occurred_at=CUT_AT)
        after = call(payments_api.deposit_batches, "get", brazos).data["cuttable_days"]
        assert after == [], "money already in a batch is not a day left to cut"


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-021 — S38, the import wizard
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_021_tc1__the_statement_imports_and_step_two_states_every_line(brazos, marcus):
    """S38 steps 1–2 over HTTP: the file lands and every line gets a state.

    The exact-amount line auto-matches; a credit matching nothing of ours is the
    fourth tile ("not in our system") and is COUNTED, not resolved — creating a
    payment from a bank line is unruled (batch decision G3), and the response
    says so on `unavailable` rather than leaving a clerk to discover it.
    """
    import base64

    with tenant_ctx(brazos):
        pe10_day(marcus, brazos)
        account = a_bank_account(brazos)
        payload = a_statement(
            [
                # CR-186-BRC10 — the day's ONE batch holds cheques and cash.
                ("2026-08-11", "CHECK DEPOSIT 4410", str(PE10_CHECK_TOTAL + PE10_CASH_TOTAL)),
                ("2026-08-14", "BANK INTEREST", "1.07"),
            ]
        )
        response = call(
            payments_api.bank_statements,
            "post",
            brazos,
            user=marcus,  # noqa: F405 — the shared `marcus` fixture
            data={
                "bank_account_id": str(account.pk),
                "period_start": "2026-08-01",
                "period_end": "2026-08-14",
                # LBX-09 (DEF-PAY-10695): imported AFTER its last line (14 Aug)
                # — a line dated after the import is refused by name.
                "imported_at": "2026-08-14T18:00:00+00:00",
                "file_name": "chase-aug.csv",
                "file_base64": base64.b64encode(payload).decode(),
            },
        )
        assert response.status_code == 201
        review = response.data["review"]
        assert review["tiles"]["lines"] == 2
        assert review["tiles"]["auto"] == 1
        states = {row["reference"]: row["state"] for row in review["rows"]}
        assert states["CHECK DEPOSIT 4410"] == "auto"
        assert states["BANK INTEREST"] == "not_in_our_system"
        codes = {gap["code"] for gap in review["unavailable"]}
        # LBX-05 (DEF-PAY-10694, G3 RULED 2026-10-30) — the "counted only" note
        # is retired: a returned line and a fee line now post.
        assert "unmatched_bank_lines_are_counted_only" not in codes
        # ⚠ **THIS ASSERTION WAS INVERTED ON 2026-09-01 (CR-059 task 45 / CS-17).**
        # It read `assert "grouped_bank_credits_not_matchable" in codes` under the
        # comment *"OQ-161 is CONFIRMED law and unbuilt — the screen must SAY so
        # before a clerk opens a batch that can never tie."* That was right while
        # the code was owed and became a FALSE CLAIM the moment `match_set` landed:
        # the sentence rendered in eleven languages telling a clerk *"Those deposits
        # will stay unmatched"*, on the same page as the control that matches them.
        # It is asserted ABSENT now so the false sentence cannot come back.
        assert "grouped_bank_credits_not_matchable" not in codes


def test_us_pay_021_tc5__the_same_file_twice_is_refused_over_http_with_who_and_when(brazos, marcus):
    """BR-PAY-028 🔒 — file + tags idempotency, as a 422 a form can render.

    Importing the same bytes for the same account and period again would write
    every bank line a second time and every one of them would look like money
    the bank sent twice. The refusal carries the sentence naming who imported it
    first and when (`params.detail`), which is what the wizard shows.
    """
    import base64

    with tenant_ctx(brazos):
        pe10_day(marcus, brazos)
        account = a_bank_account(brazos)
        body = {
            "bank_account_id": str(account.pk),
            "period_start": "2026-08-01",
            "period_end": "2026-08-14",
            "imported_at": STATEMENT_AT.isoformat(),
            "file_base64": base64.b64encode(
                a_statement([("2026-08-11", "CHECK DEPOSIT 4410", str(PE10_CHECK_TOTAL))])
            ).decode(),
        }
        first = call(payments_api.bank_statements, "post", brazos, user=marcus, data=body)
        assert first.status_code == 201
        refused = call(payments_api.bank_statements, "post", brazos, user=marcus, data=body)
        assert refused.status_code == 422
        assert "already imported" in refused.data["params"]["detail"]


def test_us_pay_021__a_file_that_is_not_base64_is_a_422_and_not_a_500(brazos, marcus):
    """A mangled upload is the clerk's problem to fix, not a stack trace.

    The API decodes and refuses at the boundary; `lockbox.py` stays the only
    parser and never sees bytes that were never bytes.
    """
    with tenant_ctx(brazos):
        account = a_bank_account(brazos)
        refused = call(
            payments_api.bank_statements,
            "post",
            brazos,
            user=marcus,
            data={
                "bank_account_id": str(account.pk),
                "period_start": "2026-08-01",
                "period_end": "2026-08-14",
                "imported_at": STATEMENT_AT.isoformat(),
                "file_base64": "this is not base64 !!!",
            },
        )
        assert refused.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-022 — S40, every difference explained with a reason AND a GL
# ══════════════════════════════════════════════════════════════════════════
def matched_card_day(actor, tenant):
    """The PO's card day, matched to its NET bank credit and awaiting S40.

    5,120.40 recorded, 4,972.90 banked. `auto_match` cannot tie these — the
    amounts differ — so a human names the pairing, which is exactly what
    `POST /deposit-batches/{id}/match` is for and is NOT a force-match.
    """
    import base64

    a_cleared_payment(actor, tenant, amount=CARD_RECORDED, method_code="card")
    reconciliation.cut_deposit_batches(actor=actor, day=PE10_DAY, occurred_at=CUT_AT)
    # CR-186-BRC10 — the payment joined the day's batch when it was posted.
    from tests.test_us_pay_020_023_bank_rec import the_days_batches

    batch = the_days_batches(tenant, PE10_DAY)[0]
    account = a_bank_account(tenant)
    call(
        payments_api.bank_statements,
        "post",
        tenant,
        user=actor,
        data={
            "bank_account_id": str(account.pk),
            "period_start": "2026-08-01",
            "period_end": "2026-08-14",
            "imported_at": STATEMENT_AT.isoformat(),
            "file_base64": base64.b64encode(
                a_statement([("2026-08-11", "CARD SETTLEMENT STRIPE", str(CARD_BANKED))])
            ).decode(),
        },
    )
    line = bankrec.BankLine.objects.get(tenant=tenant, deposit_batch__isnull=True)
    matched = call(
        payments_api.deposit_batch_match,
        "post",
        tenant,
        user=actor,
        data={"bank_line_id": str(line.pk), "occurred_at": STATEMENT_AT.isoformat()},
        batch_id=batch.batch_id,
    )
    assert Decimal(matched.data["difference"]) == CARD_BANKED - CARD_RECORDED
    return batch


def test_us_pay_022_tc3__the_card_day_reconciles_net_with_its_fee_as_its_own_line(brazos, marcus):
    """The PO's ruling of 2026-08-11 driven through the SCREEN's own route.

    *"Match net with a fee line"*: the batch reconciles against the bank's NET
    **4,972.90** and the **147.50** posts as its OWN line to **6800 Bank fees**
    — resolved by DESIGNATION, never by number. The prototype names *6200
    Merchant Fees*, which is in NO signed chart (DEF-067); B5 line 74 ❄️ has
    6800 Bank fees, and that is what this asserts.
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        response = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "resolutions": [
                    {
                        "reason_code": "processor_fee",
                        "gl_account_id": str(gl_id(brazos, "bank_fees")),
                        "amount": str(-CARD_FEE),
                    }
                ],
            },
            batch_id=batch.batch_id,
        )
        assert Decimal(response.data["recorded_total"]) == CARD_RECORDED
        assert Decimal(response.data["bank_total"]) == CARD_BANKED
        assert Decimal(response.data["difference"]) == -CARD_FEE
        assert Decimal(response.data["explained"]) == -CARD_FEE
        assert response.data["journal_entry_id"]


def test_us_pay_022_tc6__a_partial_explanation_is_refused_over_http(brazos, marcus):
    """US-PAY-022 TC-6 — explain −80.00 of a −147.50 difference and nothing ties.

    BR-PAY-035 made *"Force match anyway"* permanently superseded, and this
    route carries no flag that would express it: there is no field on the body a
    caller could set to reconcile a residual. The refusal names the leftover so
    a clerk can see exactly how much is still unexplained.
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        refused = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "resolutions": [
                    {
                        "reason_code": "processor_fee",
                        "gl_account_id": str(gl_id(brazos, "bank_fees")),
                        "amount": "-80.00",
                    }
                ],
            },
            batch_id=batch.batch_id,
        )
        assert refused.status_code == 422
        assert "does not tie" in refused.data["params"]["detail"]
        assert bankrec.DepositBatch.objects.get(pk=batch.batch_id).status != (
            bankrec.BATCH_RECONCILED
        )


def test_us_pay_022_tc5__a_resolution_with_no_gl_account_is_refused(brazos, marcus):
    """BR-PAY-019 requires a reason AND a GL on every difference.

    A difference posted to no account is money that left the tie-out and landed
    nowhere. The API refuses the missing field before the service is called, so
    the form gets a field-level 422 rather than a sentence.
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        refused = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "resolutions": [{"reason_code": "processor_fee", "amount": "-147.50"}],
            },
            batch_id=batch.batch_id,
        )
        assert refused.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-023 — S39, the detail, the trail and the lock
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_023_tc1__the_detail_serves_both_sides_and_the_whole_trail(brazos, marcus):
    """S39's four panels: members, the bank side, the trail, the resolutions.

    The members sum to `recorded_total` — that is the batch's own definition and
    the screen's tfoot — and the trail is read OLDEST FIRST because a trail
    answers *"what happened to this money, in order?"*.
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        detail = call(payments_api.deposit_batch, "get", brazos, batch_id=batch.batch_id).data
        assert sum(Decimal(m["amount"]) for m in detail["members"]) == Decimal(
            detail["batch"]["recorded_total"]
        )
        assert detail["bank_line"]["reference"] == "CARD SETTLEMENT STRIPE"
        assert Decimal(detail["bank_line"]["amount"]) == CARD_BANKED
        events = [row["event"] for row in detail["trail"]]
        assert events[0] == bankrec.EVENT_CREATED
        assert bankrec.EVENT_MATCHED in events
        assert bankrec.EVENT_FLAGGED in events


def test_us_pay_023__an_unmatched_batch_reports_no_bank_panel_rather_than_empty_fields(
    brazos, marcus
):
    """ "The bank has not shown us this deposit" is a STATE, not missing data.

    `bank_line: null` lets the screen draw its own sentence. A panel of empty
    fields reads as data that failed to load, which is the same lie as a zero.
    """
    with tenant_ctx(brazos):
        cut = pe10_day(marcus, brazos)
        detail = call(
            payments_api.deposit_batch, "get", brazos, batch_id=cut.batches[0].batch_id
        ).data
        assert detail["bank_line"] is None
        assert detail["resolutions"] == []


def test_us_pay_023_tc3__a_reconciled_batch_is_locked_and_the_row_says_so(brazos, marcus):
    """BR-PAY-004 — the lock, and the screen's own knowledge of it.

    `locked` is SERVED, not derived on the client from `status ==
    'reconciled'`: a screen that computed the rule would be a second copy of it,
    free to drift the day a fifth status arrives. The service refuses a second
    reconcile, so the control the screen hides is a control that would fail.
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "resolutions": [
                    {
                        "reason_code": "processor_fee",
                        "gl_account_id": str(gl_id(brazos, "bank_fees")),
                        "amount": str(-CARD_FEE),
                    }
                ],
            },
            batch_id=batch.batch_id,
        )
        row = next(
            r
            for r in call(payments_api.deposit_batches, "get", brazos).data["results"]
            if r["id"] == batch.batch_id
        )
        assert row["locked"] is True
        assert row["status"] == bankrec.BATCH_RECONCILED

        refused = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={"posted_at": RECONCILED_AT.isoformat(), "resolutions": []},
            batch_id=batch.batch_id,
        )
        assert refused.status_code == 422
        assert "LOCKED" in refused.data["params"]["detail"]


def test_us_pay_023_tc4__unreconcile_needs_a_reason_and_keeps_every_trail_row(brazos, marcus):
    """US-PAY-023 TC-4 — the ONLY way back, and it costs a written reason.

    Unreconcile re-opens a signed-off day; the trail is the only record of why,
    so a blank reason is refused. Afterwards every prior trail entry is still
    there — the trail is append-only and this asserts it rather than trusting
    the docstring (hard-won law 1).
    """
    with tenant_ctx(brazos):
        batch = matched_card_day(marcus, brazos)
        call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "resolutions": [
                    {
                        "reason_code": "processor_fee",
                        "gl_account_id": str(gl_id(brazos, "bank_fees")),
                        "amount": str(-CARD_FEE),
                    }
                ],
            },
            batch_id=batch.batch_id,
        )
        before = len(
            call(payments_api.deposit_batch, "get", brazos, batch_id=batch.batch_id).data["trail"]
        )
        refused = call(
            payments_api.deposit_batch_unreconcile,
            "post",
            brazos,
            user=marcus,
            data={"posted_at": RECONCILED_AT.isoformat(), "reason": "  "},
            batch_id=batch.batch_id,
        )
        assert refused.status_code == 422
        assert refused.data["code"] == errors.VAL_REQUIRED

        call(
            payments_api.deposit_batch_unreconcile,
            "post",
            brazos,
            user=marcus,
            data={
                "posted_at": RECONCILED_AT.isoformat(),
                "reason": "bank confirmed the settlement file was wrong",
            },
            batch_id=batch.batch_id,
        )
        after = call(payments_api.deposit_batch, "get", brazos, batch_id=batch.batch_id).data
        assert len(after["trail"]) > before
        assert after["batch"]["locked"] is False
        assert bankrec.EVENT_RECONCILED in [row["event"] for row in after["trail"]]


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-020 TC-6 / US-PAY-023 TC-6 — isolation
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_pay_020_tc6__one_tenants_batches_are_invisible_to_another(
    brazos, lonestar, marcus, rls_probe_role  # noqa: F811
):
    """CLAUDE.md rule 1 under RLS FORCE, on the READ path this lane added.

    A new read is a new place a tenant boundary can leak, so it is probed the
    same way every other one is: Brazos Bend cuts a batch, Lone Star Ridge lists
    and sees nothing, and a direct fetch of the other tenant's batch id is
    ABSENT (BR-TEN-003 / HR-1 — a 404, never a 403 that confirms the row).
    """
    with live_tenant_context(brazos.id):
        cut = pe10_day(marcus, brazos)
        mine = cut.batches[0].batch_id
        assert call(payments_api.deposit_batches, "get", brazos).data["results"]

    with live_tenant_context(lonestar.id):
        assert call(payments_api.deposit_batches, "get", lonestar).data["results"] == []
        absent = call(payments_api.deposit_batch, "get", lonestar, batch_id=mine)
        assert absent.status_code == 404, (
            "a cross-tenant read must be ABSENT (BR-TEN-003 / HR-1) — a 403 would confirm the "
            "row exists in some other utility's books"
        )


@pytest.mark.isolation
@requires_postgres
def test_us_pay_020__a_read_with_no_tenant_in_scope_refuses(brazos, rls_probe_role):  # noqa: F811
    """Hard rule 1 has no default. No `app.tenant_id`, no rows — an AuthError.

    Refusing rather than defaulting is the whole guarantee: a batch list
    computed with no tenant in scope is blocked by RLS on Postgres and would
    list another utility's banking on a database without it.
    """
    with pytest.raises(errors.AuthError):
        bankrec_read.batch_list()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020/021/022/023 §3 test-case tables · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-004/019/025/035/040 · 08-qa/01-e2e/journeys/J14-lockbox-day.md · 04-docs/05-modules/08-payments/07-pre-session-model.md §7 PE-10/PE-11; co-packets US-PAY-021, US-PAY-022, US-PAY-023)
# generated: 2026-08-16 by story-coder (payments SURFACE lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case failed with `ModuleNotFoundError: No module named 'apps.payments.bankrec_read'` and `AttributeError: module 'apps.payments.api' has no attribute 'deposit_batches'`, and the live-HTTP probe failed `assert 404 == 401` on all four paths. Verbatim in the lane report. pytest✔ · pytest -m isolation✔ · run_gates✔
# exceptions: (1) the money figures are COPIED from PE-10, PE-11 and the PO's card day and never recomputed — a test that recomputed its expectation would agree with a broken implementation · (2) the isolation cases carry `requires_postgres` and SKIP on SQLite rather than passing vacuously, because RLS is the guarantee being probed · (3) `test_us_pay_020_tc2__an_unbanked_batch_reports_no_bank_figure_rather_than_zero` asserts on a NULL rather than on a value, which is the DEF-127 shape aimed at this surface
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
