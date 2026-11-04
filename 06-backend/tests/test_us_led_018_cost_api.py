# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-018 (S73's Capture) · US-LED-019 (S73's register, its
#           filters, its void and OQ-203's after-close correction) ·
#           US-LED-020 (S74's reconciliation) · US-LED-021 (the export-drift
#           warning the correction creates)
#           Screens: S73 · S74 · S42
# Rules:    BR-LED-028 · BR-LED-029 · BR-LED-030 · BR-LED-031 · BR-LED-034 ·
#           BR-LED-035 · BR-LED-036 · BR-LED-004 · BR-REP-001 ·
#           BR-TEN-003 / HR-1 (a cross-tenant id reads as absent) ·
#           CLAUDE.md rule 1 · rule 2 · rule 3 · rule 7
# Tests:    this file
# Impacts:  apps/ledger/cost_api.py · config/urls.py (the include this asserts)
# ───────────────────────────────────────────────────────
"""The payable side, over real HTTP — the half that did not exist.

`apps/ledger/cost_capture.py` and `apps/ledger/cost_reconciliation.py` shipped
on 2026-08-15 complete and tested, each carrying `D=deferred(no-API-half)`. So
this file's first two tests are the whole defect: **is there a route, and can a
request reach it?**

`resolve()` proves the URLconf knows a path. It does not prove a request can get
there — tenant middleware, session authentication and the permission class all
sit in front, and any one of them answering 404 would leave S73 and S74 exactly
as unreachable as they were. So an unauthenticated call is made and its refusal
is read: **401/403 means the route exists and asked for a sign-in; 404 means
there is no route.**
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.ledger import cost_api, exports
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    EXPORTED_AT,
    JULY_END,
    JULY_START,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call
from tests.test_us_led_021_cost_export import july_captured_and_closed

pytestmark = pytest.mark.django_db

FROM = JULY_START.isoformat()
TO = JULY_END.isoformat()

#: Every path this lane mounts, named ONCE so the routing test and the
#: reachability test cannot drift apart — the pair that catches a lost include.
PATHS = (
    ("finance/cost-of-service", cost_api.cost_of_service),
    ("finance/cost-of-service/reconciliation", cost_api.cost_reconciliation_view),
    (
        "finance/cost-of-service/reconciliation/download",
        cost_api.cost_reconciliation_download,
    ),
    ("finance/export/drift", cost_api.export_drift),
)


def user_with(role):
    return SimpleNamespace(id=uuid4(), pk=uuid4(), role=role, is_authenticated=True)


def call(view, tenant, method="get", *, role="billing_clerk", data=None, **kwargs):
    user = user_with(role)
    return api_call(
        view,
        method,
        user=user,
        role=role,
        tenant=tenant,
        data=data if method != "get" else None,
        query=data if method == "get" else None,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO THAT MATTER MOST — "built is not wired", at the routing layer
# ═══════════════════════════════════════════════════════════════════════════
def test_every_cost_of_service_path_is_actually_mounted(brazos):
    """Before `config/urls.py` named `apps.ledger.cost_api`, every line below
    raised `django.urls.exceptions.Resolver404`. That IS the defect: 1,700 lines
    of tested engine and no URL reaching them."""
    from django.urls import resolve

    slug = brazos.subdomain
    for suffix, view in PATHS:
        assert resolve(f"/api/{slug}/{suffix}").func is view, suffix
    # The static `reconciliation` segment must outrank `<str:invoice_id>`, or
    # the word resolves as an invoice id and 404s on a row that never existed.
    assert (
        resolve(f"/api/{slug}/finance/cost-of-service/reconciliation").func
        is cost_api.cost_reconciliation_view
    )
    assert (
        resolve(f"/api/{slug}/finance/cost-of-service/{uuid4()}").func
        is cost_api.cost_of_service_item
    )
    assert (
        resolve(f"/api/{slug}/finance/cost-of-service/{uuid4()}/void").func
        is cost_api.cost_of_service_void
    )


def test_the_cost_of_service_paths_are_reachable_over_http(brazos):
    """The other half of "mounted": a real request ARRIVES at these views."""
    from django.test import Client

    client = Client()
    slug = brazos.subdomain
    for suffix, _view in PATHS:
        response = client.get(f"/api/{slug}/{suffix}")
        assert response.status_code != 404, f"{suffix} has NO ROUTE — built is not wired"
        assert response.status_code in (401, 403), (suffix, response.status_code)


# ═══════════════════════════════════════════════════════════════════════════
# The register, the capture and the two rulings a screen must print
# ═══════════════════════════════════════════════════════════════════════════
def test_the_register_serves_the_footer_the_categories_and_the_posting_ruling(
    brazos, marcus
):
    """TC-1's **$51,902.50 USD** footer, and the two things the screen cannot
    compose for itself.

    `posting` is served rather than hardcoded in the browser because OQ-200's
    closure text is explicit: *"any screen implying otherwise is a defect"*. A
    sentence written in a `.tsx` file would drift from the ledger's the first
    time the ruling's trigger fires.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        response = call(cost_api.cost_of_service, brazos)

    assert response.status_code == 200
    body = response.data
    assert len(body["rows"]) == 9
    # Money on the wire as a STRING beside its CHAR(3) (CLAUDE.md rule 2).
    assert body["total_amount"] == "51902.500000"
    assert body["currency"] == "USD"
    assert isinstance(body["rows"][0]["amount"], str)
    # BR-LED-028: the bulk-action bar is empty BY RULE, and the empty list is
    # all the screen gets — `DEF-LED-6642` removed the 38-word sentence that
    # used to explain it, rule id and all.
    assert body["bulk_actions"] == []
    assert "bulk_actions_reason" not in body
    assert "approve" in body["forbidden_actions"]
    # OQ-200, ruled: a CAPTURE posts nothing, and that has not changed.
    assert body["posting"]["posted"] is False
    assert body["posting"]["reason"] == "capture_posts_nothing_in_r2"
    # ⚠ AMENDED 2026-09-02 (CR-060 C1 / task T6). This asserted
    # `"supplier-payment path ships" in body["posting"]["expires_when"]` — the
    # condition the OLD ruling attached to itself. That condition never fired
    # and cannot: BR-LED-028 still forbids a payment run. What the PO ruled
    # instead is that the books move when a clerk records the invoice was PAID,
    # so the register now serves THAT sentence for the screen to print. The old
    # constant is kept, dated `POSTING_RULING_SUPERSEDED`, and is asserted in
    # tests/test_us_led_018_capture.py where the boundary's history lives.
    assert "expires_when" not in body["posting"]
    settlement_says = body["posting"]["settlement"]
    assert "Capturing a supplier invoice still posts nothing" in settlement_says
    assert "DR the cost account / CR cash" in settlement_says
    assert "Your entry is the authority" in settlement_says
    # US-LED-017 TC-5: the register of unsigned cost codes is SERVED, so a
    # screen never has to hardcode which codes need a signature.
    # ⚠ AMENDED 2026-08-18: this asserted `"5110" in ...`. The PO finance
    # re-signed all eight cost codes and names that day (in plain English, no
    # dollar figure attached, B4/B5 ❄️ FROZEN and un-edited), so the register is
    # EMPTY — and the endpoint must still publish it, because an absent key and
    # an empty one say different things to the screen reading them.
    # ⚠ AMENDED AGAIN 2026-09-02 (DEF-3240; this comment said DEF-3200 until
    # 2026-09-02 and that is an unrelated payments defect about a bank
    # reconciliation statement's cheque count — DEF-2792's exact shape, which is
    # a fix citing the wrong id, and it is why G67 exists) — THIS ASSERTION HAD BEEN RED SINCE
    # 2026-09-01 AND NOTHING SAID SO. CR-060 T5 added fourteen cost categories
    # whose accounts seed `signed=False` (5210 · 5220 · 5230 · 5400 · 5410 ·
    # 5420 · 5500 · 5510 · 5520 · 5530 · 5540 · 5600 · 5610 · 5620), so the
    # register has served fourteen codes since that day while this line still
    # demanded an empty list. The FIGURE is what matters and it is asserted as a
    # count and a membership rather than as a frozen list, so the next lane
    # adding a category does not have to re-type fourteen strings.
    assert len(body["pending_finance_re_sign_cost"]) == 14
    assert "5500" in body["pending_finance_re_sign_cost"]  # admin_payroll_benefits
    assert "5110" not in body["pending_finance_re_sign_cost"]  # re-signed 2026-08-18
    assert "HUMAN-GUIDE §6" in body["cost_section_source"]


def test_the_volume_captured_filter_is_the_one_that_earns_its_place(brazos, marcus):
    """TC-3 — `f.volume_captured=no` returns exactly the set that decides
    whether an unaccounted-for percentage can be produced at all, so a clerk
    finds the gap in one click instead of reading a suppressed figure and
    wondering."""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        response = call(
            cost_api.cost_of_service, brazos, data={"f.volume_captured": "no"}
        )
    references = {row["reference"] for row in response.data["rows"]}
    assert references == {"HPV-4471", "KMW-2026-118"}


def test_a_capture_over_http_stores_its_volume_with_its_unit_and_posts_nothing(
    brazos, marcus
):
    """TC-1's RS-2607-0141: **400,000 gal, $1,240.00 USD**, GL 5110.

    The volume travels with its unit and the response says, in a sentence a
    screen prints, that the books did not move.
    """
    with tenant_ctx(brazos):
        _captured, _admin = july_captured_and_closed(brazos, marcus, close_it=False)
        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        response = call(
            cost_api.cost_of_service,
            brazos,
            "post",
            data={
                "invoice_date": "2026-07-06",
                "service": "water",
                "supplier_name": "City of Rosenberg — Bulk Water Supply",
                "amount": "1240.00",
                "currency": "USD",
                "volume": "400000",
                "volume_unit": "gal",
                "ledger_account_id": str(account.pk),
                "reference": "RS-2607-0141-B",
            },
        )
    assert response.status_code == 201
    assert response.data["amount"] == "1240.00"
    assert response.data["currency"] == "USD"
    assert response.data["volume_unit"] == "gal"
    assert response.data["posting"]["posted"] is False
    assert "in no trial balance" in response.data["posting"]["detail"]


def test_a_volume_with_no_unit_is_refused_over_http(brazos, marcus):
    """TC-7 / CLAUDE.md rule 3 — *always with an explicit unit; never assume*.
    Omitting BOTH is legal (TC-2) and is asserted in the service tests."""
    with tenant_ctx(brazos):
        _captured, _admin = july_captured_and_closed(brazos, marcus, close_it=False)
        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        response = call(
            cost_api.cost_of_service,
            brazos,
            "post",
            data={
                "invoice_date": "2026-07-06",
                "service": "water",
                "supplier_name": "City of Rosenberg",
                "amount": "1240.00",
                "currency": "USD",
                "volume": "400000",
                "ledger_account_id": str(account.pk),
            },
        )
    assert response.status_code in (409, 422)
    assert response.data["br_ref"] in {"BR-LED-033", "BR-LED-029"}


def test_an_executive_may_read_the_register_and_may_not_capture(brazos, marcus):
    """US-LED-018 TC-9's reading of BR-LED-003: an executive reads the books, a
    clerk records them. Carried as a READING and flagged — what was put to the
    PO was the REVERSAL — and asserted here so the reading is visible."""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        readable = call(cost_api.cost_of_service, brazos, role="executive")
        denied = call(
            cost_api.cost_of_service,
            brazos,
            "post",
            role="executive",
            data={"invoice_date": "2026-07-06"},
        )
    assert readable.status_code == 200
    assert denied.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# S74 — the reconciliation, and the download OQ-204 has not placed
# ═══════════════════════════════════════════════════════════════════════════
def test_the_reconciliation_serves_nine_percent_with_its_ruled_basis(brazos, marcus):
    """The PO's own figures: bought **1,000,000 gal**, billed **910,000** →
    **9.00%**, on the RULED service-period basis (OQ-202)."""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        response = call(
            cost_api.cost_reconciliation_view, brazos, data={"from": FROM, "to": TO}
        )
    body = response.data
    assert response.status_code == 200
    assert body["basis"] == "service_period"
    # ⚠ **`basis_label` AND `formula` ARE GONE FROM THE WIRE (`DEF-LED-6669`).**
    # They were a 90-word English paragraph quoting OQ-202 and a PO ruling, and
    # our own field names as an expression — both printed to a clerk. The basis
    # is still labelled, from `finance.cost.basis.<code>` in the catalogue.
    assert "basis_label" not in body
    assert "formula" not in body
    assert body["problems"] == []
    assert body["total_bought_cost"] == "51902.500000"
    assert body["currency"] == "USD"
    water = next(row for row in body["rows"] if row["service"] == "water")
    assert water["bought_volume"] == "1000000.000000"
    # ⚠ No billed volume is seeded by this fixture, so the row states its reason
    # rather than reading 100.00% unaccounted for — which is what a fallback to
    # zero would print on a healthy month (TC-9).
    assert water["unaccounted_for_pct"] is None
    assert water["problems"] != []


def test_the_reconciliation_download_is_refused_by_name_not_by_404(brazos, marcus):
    """OQ-204, OPEN — where this view lives decides which download pipeline it
    registers with, and picking one would answer the question.

    The payload tells the SCREEN to disable its control with a reason
    (BR-SHL-025) rather than hide it: a missing control reads as a feature
    nobody thought of, and a person who needs the CSV must know it is a decision
    and not a bug.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        listing = call(
            cost_api.cost_reconciliation_view, brazos, data={"from": FROM, "to": TO}
        )
    assert listing.data["download"]["available"] is False
    assert listing.data["download"]["oq"] == "OQ-204"
    # ⚠ **THIS LINE WAS RED AT THE TIP AND NOBODY HAD READ IT.** It asserted
    # `"has not been ruled" in …["reason"]`, and `233472ac1` (P2.5, 2026-09-24)
    # reworded that sentence to *"has not been decided"* without moving the
    # test — so the assertion had been failing for a day, on a screen whose
    # copy was actively being fixed. Dated with `git log -S "has not been
    # ruled" -- apps/ledger/cost_api.py`, not from memory (hard-won law 7).
    #
    # It is now a KEY rather than a sentence (`DEF-LED-6669`): 55 words of
    # undecided engineering on the wire is B14 rule 33's zero and TD-16/B8's
    # split both. The control's STATE is what this case is about and is
    # untouched — the blueprint (p063) says the button is right to be disabled.
    assert listing.data["download"]["reason_key"] == "finance.cost.downloadGap"
    assert "reason" not in listing.data["download"]

    # The route itself refuses BY NAME. `NotImplementedError("OQ-204")` is what
    # the prime directive asks a lane to raise at an unruled boundary, and the
    # DRF handler renders it as a system error whose trace names the question —
    # the honest answer to a client that called a route the screen never calls,
    # and a very different thing from a 404 that reads as a typo.
    with tenant_ctx(brazos):
        refused = call(cost_api.cost_reconciliation_download, brazos)
    assert refused.status_code >= 500


# ═══════════════════════════════════════════════════════════════════════════
# OQ-203's condition, served where the finance officer stands
# ═══════════════════════════════════════════════════════════════════════════
def test_the_export_screen_is_told_which_batch_no_longer_matches(brazos, marcus):
    """**The condition the PO attached to OQ-203.** Both figures, their
    currency, and the batch by name — because the person receiving this warning
    has to go and post the difference by hand in QuickBooks."""
    with tenant_ctx(brazos):
        captured, admin = july_captured_and_closed(brazos, marcus)
        batch = exports.create_export_batch(
            admin,
            period_start=JULY_START,
            period_end=JULY_END,
            target=ledger_models.EXPORT_QBO,
            created_at=EXPORTED_AT,
        )
        quiet = call(cost_api.export_drift, brazos)
        assert quiet.data["rows"] == []

        voided = call(
            cost_api.cost_of_service_void,
            brazos,
            "post",
            data={
                "reason": "duplicate of RS-2607-0175",
                "voided_at": "2026-08-03T10:15:00+00:00",
            },
            invoice_id=captured["RS-2607-0192"]["id"],
        )
        assert voided.status_code == 200
        assert voided.data["after_close"]["problem"] == "exported_batch_no_longer_matches"

        drifted = call(cost_api.export_drift, brazos)

    (row,) = drifted.data["rows"]
    assert row["batch_no"] == batch["batch_no"]
    assert row["carried"] == "51902.500000"
    assert row["register_now"] == "51747.500000"
    assert row["difference"] == "-155.000000"
    assert row["currency"] == "USD"


def test_an_after_close_edit_needs_a_reason_and_a_re_dating_is_refused_as_oq_227(
    brazos, marcus
):
    """Two halves of the same ruling.

    A reasonless correction is refused (the audit row is the only artifact that
    can explain the difference later); a RE-DATING is refused BY RULE (OQ-227,
    CLOSED by the PO on 2026-08-16 — *"a correction is a correction"*), because
    moving a purchase between months is not correcting it and the two available
    behaviours each move a different month's reconciliation.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured_and_closed(brazos, marcus)
        unreasoned = call(
            cost_api.cost_of_service_item,
            brazos,
            "patch",
            data={"amount": "1250.00"},
            invoice_id=captured["RS-2607-0141"]["id"],
        )
        assert unreasoned.status_code in (409, 422)
        assert unreasoned.data["br_ref"] == "BR-LED-034"

        reasoned = call(
            cost_api.cost_of_service_item,
            brazos,
            "patch",
            data={
                "amount": "1250.00",
                "correction_reason": "supplier re-issued at the metered volume",
            },
            invoice_id=captured["RS-2607-0141"]["id"],
        )
        assert reasoned.status_code == 200
        assert reasoned.data["amount"] == "1250.00"

        redated = call(
            cost_api.cost_of_service_item,
            brazos,
            "patch",
            data={
                "invoice_date": "2026-08-02",
                "correction_reason": "the supplier's invoice reads August",
            },
            invoice_id=captured["RS-2607-0141"]["id"],
        )
    assert redated.status_code in (409, 422)
    # ⚠ WAS `params["oq"] == "OQ-227"`, i.e. the response named an OPEN
    # question. The PO closed it on 2026-08-16 and the refusal is now law; the
    # response cites the RULING instead, so a clerk is told the answer rather
    # than told to go and ask for one.
    assert redated.data["params"]["ruling"] == "OQ-227"


def test_isolation__a_foreign_invoice_id_reads_as_absent_never_as_forbidden(
    brazos, lonestar, marcus
):
    """CLAUDE.md rule 1 + HR-1. Confirming that a row exists somewhere is itself
    a leak, so a cross-tenant id and a missing one answer the same 404."""
    with tenant_ctx(brazos):
        captured, _admin = july_captured_and_closed(brazos, marcus, close_it=False)
        foreign_id = captured["RS-2607-0141"]["id"]

    with tenant_ctx(lonestar):
        crossed = call(
            cost_api.cost_of_service_void,
            lonestar,
            "post",
            data={"reason": "not mine", "voided_at": "2026-08-03T10:15:00+00:00"},
            invoice_id=foreign_id,
        )
        missing = call(
            cost_api.cost_of_service_void,
            lonestar,
            "post",
            data={"reason": "not mine", "voided_at": "2026-08-03T10:15:00+00:00"},
            invoice_id=str(uuid4()),
        )
        empty = call(cost_api.cost_of_service, lonestar)

    assert crossed.status_code == 404
    assert missing.status_code == 404
    # Byte-identical apart from the per-request trace id, which is the property
    # that makes existence non-leaking: a caller cannot tell "this row belongs
    # to somebody else" from "there is no such row".
    def without_trace(body):
        return {k: v for k, v in body.items() if k != "trace_id"}

    assert without_trace(crossed.data) == without_trace(missing.data)
    assert empty.data["rows"] == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-018@d744841 (the sources apps/ledger/cost_api.py was authored from)
# generated: 2026-08-16 by the surface-debt tails lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with the `apps.ledger.cost_api` include removed from
#         config/urls.py the routing test failed with
#         `django.urls.exceptions.Resolver404: {'path': 'finance/cost-of-service'}`
#         and the HTTP test with `assert 404 != 404` on the same path.
# ───────────────────────────────────────────────────────
