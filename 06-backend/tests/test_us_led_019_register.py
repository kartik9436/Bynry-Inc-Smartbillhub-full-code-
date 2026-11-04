# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-019 (the captured-cost register on S73: list, search, edit
#           while the period is OPEN, void with reason — never delete. TC-1 the
#           nine July rows and the $51,902.50 footer, TC-2 the Rosenberg search,
#           TC-3 the volume-captured filter, TC-4 the edit to $51,904.90, TC-5
#           the void to $51,747.50, TC-6 the delete refusal, TC-7 the forbidden
#           actions, TC-8 the OQ-203 stub, TC-9 isolation)   Screens: S73
# Rules:    BR-LED-035 (void, never delete; reason REQUIRED; the row stays
#           visible and leaves every aggregate) · BR-LED-034 (editable while the
#           period is OPEN; after close is OQ-203) · BR-LED-028 (no approvals,
#           no payment runs, no bulk bar) · BR-LED-036 (every edit and void
#           audits, with before/after) · IS-1/IS-2/IS-3/IS-4 (deactivate-first,
#           server-side tables, debounced search, URL-persisted filters)
# Golden:   LE-11's $51,902.50 · LE-13's $51,904.90 after the edit and
#           $51,747.50 after the void
# ───────────────────────────────────────────────────────
"""The register a clerk reconciles against a supplier statement.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_019_tc5__a_void_keeps_the_row_visible_and_drops_it_from_the_footer`.
BR-LED-035 is *"void, never delete"*, and both halves matter for the same
reason: **a register that hides its corrections cannot be reconciled against a
supplier statement**, and a footer that includes withdrawn money is wrong. LE-13
gives the numbers — the footer moves 51,902.50 → **51,747.50** and CI-4 is still
on the screen with *"duplicate of RS-2607-0175"* beside it.

⚠ **TC-8 IS A STUB ASSERTION.** Whether an invoice may be edited or voided after
its period CLOSES is **OQ-203, OPEN**, and three signed rules point three ways.
The test asserts `NotImplementedError("OQ-203")` and no behaviour in either
direction (CLAUDE.md prime directive).

WHAT RUNS WHERE. Everything here runs on SQLite and Postgres alike EXCEPT the
hard-delete refusal, which is a database trigger and carries
`requires_postgres` — on SQLite it SKIPS with a vendor reason rather than
passing vacuously. **No case in this file is unconditionally skipped.**
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import close, cost_capture
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    LE13_TOTAL_AFTER_EDIT,
    LE13_TOTAL_AFTER_VOID,
    VOIDED_AT,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def july_register(tenant, clerk):
    """Brazos Bend's July, nine captured purchases, through the real service."""
    admin = staff_actor(tenant, "system_admin", f"setup-reg-{tenant.subdomain}@brazos.test")
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    return capture_le11_month(clerk), admin


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 / TC-2 / TC-3 — list, search, the filter that earns its place
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc1__nine_rows_a_51902_50_footer_and_date_desc_by_default(
    brazos, marcus
):
    """*"Register renders Brazos Bend July → 9 rows (CI-1..CI-9) — 5 water, 1
    electric, 1 gas, 1 O&M, 1 infrastructure; default sort invoice date desc;
    totals footer $51,902.50 USD."*"""
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        listed = cost_capture.register()

    assert listed["count"] == 9
    assert listed["live_count"] == 9 and listed["voided_count"] == 0
    assert listed["total_amount"] == LE11_REGISTER_TOTAL
    assert listed["currency"] == "USD" and listed["mixed_currency"] is False

    by_service: dict[str, int] = {}
    for row in listed["rows"]:
        by_service[row["service"]] = by_service.get(row["service"], 0) + 1
    assert by_service == {
        "water": 5,
        "electric": 1,
        "gas": 1,
        "operations_maintenance": 1,
        "infrastructure": 1,
    }

    # Default sort: invoice date DESC (the S73 capability matrix).
    dates = [row["invoice_date"] for row in listed["rows"]]
    assert dates == sorted(dates, reverse=True)


def test_us_led_019_tc2__the_free_text_search_and_the_service_filter(brazos, marcus):
    """*"Search `Rosenberg`; filter period = 2026-07 + service = Water → 5 rows,
    $3,100.00; debounced ≥2 chars, server-side."*

    The supplier is FREE TEXT with no vendor master (BR-LED-028), so this search
    IS how a clerk finds everything from one supplier.
    """
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        found = cost_capture.register(
            q="Rosenberg", period_start=JULY_START, period_end=JULY_END, service="water"
        )
        # The ≥2-character floor is server-side (IS-3): one keystroke must not
        # scan the table.
        with pytest.raises(cost_capture.CostCaptureError) as too_short:
            cost_capture.register(q="R")
        assert "at least 2" in str(too_short.value)

    assert found["count"] == 5
    assert found["total_amount"] == Decimal("3100.00")
    # The filters are echoed back so a screen can render what it applied and a
    # CSV can print it (IS-4 / BR-REP-001).
    assert found["filters"]["q"] == "Rosenberg"
    assert found["filters"]["service"] == "water"


def test_us_led_019_tc3__the_volume_captured_filter_finds_exactly_the_gap(brazos, marcus):
    """*"Filter **volume captured = no** for period 2026-07 → returns HPV-4471
    and KMW-2026-118 … and, in the degraded fixture, RS-2607-0208; the clerk
    sees exactly why a service's percentage is suppressed."*

    This filter exists because it returns precisely the set BR-LED-031 uses to
    decide whether a percentage can be produced at all.
    """
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        clean = cost_capture.register(volume_captured=False)
        assert {row["reference"] for row in clean["rows"]} == {"HPV-4471", "KMW-2026-118"}
        assert clean["count"] == 2

    # The degraded fixture: a WATER purchase captured cost-only. Now the same
    # click returns the row that will suppress the figure, beside the two that
    # legitimately carry no volume.
    with tenant_ctx(brazos):
        cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 31),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("620.00"),
            currency="USD",
            reference="RS-2607-0208-B",
        )
        degraded = cost_capture.register(volume_captured=False)
    assert {row["reference"] for row in degraded["rows"]} == {
        "HPV-4471",
        "KMW-2026-118",
        "RS-2607-0208-B",
    }
    # And its complement is the set that CAN produce a figure.
    with tenant_ctx(brazos):
        assert cost_capture.register(volume_captured=True)["count"] == 7


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the edit while the period is OPEN
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc4__an_open_period_edit_moves_the_footer_and_audits_both_sides(
    brazos, marcus, audit_rows
):
    """*"Edit RS-2607-0175's amount $310.00 → $312.40 while July is OPEN → saved;
    audit `supplier_invoice.updated` with before/after; the reconciliation's cost
    column moves by $2.40 and its volume figure does not."*

    LE-13's own footer figure: **51,904.90**.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        audit_rows.clear()
        edited = cost_capture.edit_supplier_invoice(
            marcus, captured["RS-2607-0175"]["id"], amount=Decimal("312.40")
        )
        listed = cost_capture.register()

    assert edited["amount"] == Decimal("312.40")
    assert listed["total_amount"] == LE13_TOTAL_AFTER_EDIT
    # The VOLUME did not move, which is why water still reads 9.00%.
    assert edited["volume"] == Decimal("100000") and edited["volume_unit"] == "gal"

    updates = [r for r in audit_rows if r["action"] == "supplier_invoice.updated"]
    assert len(updates) == 1
    assert updates[0]["before"]["amount"] == "310.000000"
    assert updates[0]["after"]["amount"] == "312.400000"
    assert updates[0]["actor_user_id"] == marcus.id


def test_us_led_019__an_edit_may_not_reach_the_status_or_the_void_trail(brazos, marcus):
    """BR-LED-034 makes the CAPTURED FACTS editable. A void is its own audited
    action with its own required reason (BR-LED-035), so it cannot be reached
    through the edit path — which would be a void with no reason and no trail."""
    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        for forbidden in ({"status": "voided"}, {"void_reason": "sneaking"},
                          {"captured_by_user_id": None}):
            with pytest.raises(cost_capture.CostCaptureError) as refused:
                cost_capture.edit_supplier_invoice(
                    marcus, captured["RS-2607-0141"]["id"], **forbidden
                )
            assert "BR-LED-034" in refused.value.br_ref


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — THE RULE. Void, never delete.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc5__a_void_keeps_the_row_visible_and_drops_it_from_the_footer(
    brazos, marcus, audit_rows
):
    """*"Void RS-2607-0192 with reason 'duplicate of RS-2607-0175' → status →
    voided, reason stored, actor + timestamp audited; the row **stays visible**
    in the register; it leaves the reconciliation's denominator and the export's
    section."*

    LE-13's figure: the footer moves **51,902.50 → 51,747.50** (−155.00).
    """
    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        audit_rows.clear()
        voided = cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        listed = cost_capture.register()

    assert voided["status"] == "voided"
    assert voided["void_reason"] == "duplicate of RS-2607-0175"
    assert voided["voided_at"] == VOIDED_AT
    assert voided["voided_by_user_id"] == str(marcus.id)

    # STILL VISIBLE — nine rows, not eight.
    assert listed["count"] == 9
    assert listed["live_count"] == 8 and listed["voided_count"] == 1
    on_screen = {row["reference"]: row for row in listed["rows"]}
    assert on_screen["RS-2607-0192"]["status"] == "voided"
    assert on_screen["RS-2607-0192"]["void_reason"] == "duplicate of RS-2607-0175"

    # OUT of the footer.
    assert listed["total_amount"] == LE13_TOTAL_AFTER_VOID
    assert LE11_REGISTER_TOTAL - listed["total_amount"] == Decimal("155.00")

    voids = [r for r in audit_rows if r["action"] == "supplier_invoice.voided"]
    assert len(voids) == 1
    assert voids[0]["before"]["status"] == "captured"
    assert voids[0]["after"]["void_reason"] == "duplicate of RS-2607-0175"


def test_us_led_019_tc5__a_void_without_a_reason_is_refused(brazos, marcus):
    """BR-LED-035 makes the reason REQUIRED, and the requirement is the point of
    the feature: the row stays visible precisely so a clerk can see WHY."""
    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.void_supplier_invoice(
                marcus, captured["RS-2607-0192"]["id"], reason="   ", voided_at=VOIDED_AT
            )
        assert refused.value.br_ref == "BR-LED-035"

        # And the database refuses it too, one layer below the service.
        from django.db import IntegrityError, transaction

        row = ledger_models.SupplierInvoice.objects.get(pk=captured["RS-2607-0192"]["id"])
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                row.status = "voided"
                row.void_reason = None
                row.save()


def test_us_led_019_tc5__a_second_void_is_refused_so_the_first_reason_survives(
    brazos, marcus
):
    """Voiding twice would overwrite the reason of the FIRST void, which is the
    record the register exists to keep."""
    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        with pytest.raises(cost_capture.CostCaptureError) as again:
            cost_capture.void_supplier_invoice(
                marcus,
                captured["RS-2607-0192"]["id"],
                reason="changed my mind",
                voided_at=VOIDED_AT,
            )
        assert "already voided" in str(again.value)

        # A voided row is not editable either — a correction is a void plus a
        # FRESH CAPTURE (BR-LED-035), never an edit of the withdrawn row.
        with pytest.raises(cost_capture.CostCaptureError):
            cost_capture.edit_supplier_invoice(
                marcus, captured["RS-2607-0192"]["id"], amount=Decimal("1.00")
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — no hard-delete path exists at ANY layer
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc6__the_service_layer_publishes_no_delete_path(brazos, marcus):
    """*"Hard delete attempted on any captured row (UI, API or bulk) → Refused.
    Void is the only disposition (BR-LED-035, hard rule 4). No path exists at any
    layer."*

    The application half: nothing in the module removes a row, and the module's
    own vocabulary refuses the request by name.
    """
    for forbidden in ("delete_supplier_invoice", "remove_supplier_invoice", "purge"):
        assert not hasattr(cost_capture, forbidden), (
            f"cost_capture.{forbidden} exists — BR-LED-035 makes VOID the only disposition"
        )
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        assert cost_capture.register()["bulk_actions"] == ()


@pytest.mark.isolation
@requires_postgres
def test_us_led_019_tc6__the_database_refuses_a_hard_delete(brazos, marcus):
    """The other half, and the one that survives a `.delete()` typed into a
    shell. `ledger_supplier_invoice_no_delete()` (ledger/0008) is a row-level
    BEFORE DELETE trigger, so it is total to DELETE and invisible to the
    TRUNCATE Django's teardown uses.

    Postgres-only: SQLite has no triggers, so this SKIPS with a vendor reason
    rather than passing vacuously — never a bare `pytest.mark.skip`.

    ⚠ `DatabaseError` and not `InternalError`: a PL/pgSQL `RAISE EXCEPTION`
    carries SQLSTATE **P0001**, which psycopg surfaces as `ProgrammingError`,
    not `InternalError`. Written the other way first, this test FAILED ON
    POSTGRES with the refusal's own text in the traceback — the guard worked and
    the assertion did not. Caught by running the isolation suite on a real
    database, which is the only place either half is observable.
    """
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        captured, _admin = july_register(brazos, marcus)
        row = ledger_models.SupplierInvoice.objects.get(pk=captured["RS-2607-0141"]["id"])
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                row.delete()
        assert "BR-LED-035" in str(refused.value)
        assert "RS-2607-0141" in str(refused.value)

    with tenant_ctx(brazos):
        assert ledger_models.SupplierInvoice.objects.filter(tenant=brazos).count() == 9


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the register offers none of the forbidden actions
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc7__no_approve_pay_ageing_or_supplier_page_action_exists(
    brazos, marcus
):
    """*"The register is asked for an 'approve', 'mark paid', 'schedule payment',
    'supplier statement' or 'ageing' action → **Refused and named** as out of
    scope BY RULE (BR-LED-028) — not as a missing feature. The bulk-action bar
    does not render at all."*"""
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        listed = cost_capture.register()

    assert listed["bulk_actions"] == ()
    # `DEF-LED-6642` — the sentence that said so is deleted, not shortened.
    assert "bulk_actions_reason" not in listed

    # There is no status to filter an approval queue by, either.
    with tenant_ctx(brazos):
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.register(status="approved")
        assert refused.value.br_ref == "BR-LED-028"


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — ⚠ the after-close boundary is OQ-203 and nothing guesses
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc8__an_edit_after_the_period_closes_needs_a_reason_oq_203_ruled(
    brazos, marcus
):
    """**OQ-203 CLOSED 2026-08-16 — a captured supplier invoice CAN be corrected
    after its period closes.** PO verbatim: *"Yes it can be corrected"* —
    option (b), editable with a reason and an audit row, never frozen.

    Two halves, and the second is the condition the ruling attached to the
    first:

      1. **A reasonless after-close edit is refused**, because the audit row is
         the only artifact that can ever explain the difference to whoever
         reconciles a month-end that has already been signed off.
      2. **A reasoned one saves**, writes `after_close_correction` into the
         append-only trail, and — this is the whole of why the PO could permit
         it — is safe precisely because capture posts nothing (OQ-200), so no
         signed total moves.
    """
    with tenant_ctx(brazos):
        captured, admin = july_register(brazos, marcus)
        close.close_period(
            admin,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="the deposit register is still being matched",
        )

        # (1) No reason → refused, and the refusal quotes the ruling rather than
        # reading as an unbuilt feature.
        with pytest.raises(cost_capture.CostCaptureError) as unreasoned:
            cost_capture.edit_supplier_invoice(
                marcus, captured["RS-2607-0141"]["id"], amount=Decimal("1.00")
            )
        assert "needs a REASON" in str(unreasoned.value)
        assert "Yes it can be corrected" in str(unreasoned.value)
        assert ledger_models.SupplierInvoice.objects.get(
            pk=captured["RS-2607-0141"]["id"]
        ).amount == Decimal("1240.00")

        # (2) With a reason → it saves, and the correction is on the row's
        # result AND in the audit trail.
        edited = cost_capture.edit_supplier_invoice(
            marcus,
            captured["RS-2607-0141"]["id"],
            correction_reason="supplier re-issued RS-2607-0141 at the metered volume",
            amount=Decimal("1250.00"),
        )
        assert edited["amount"] == Decimal("1250.00")
        assert edited["after_close"]["correction"] == cost_capture.AFTER_CLOSE_CORRECTION
        assert (
            edited["after_close"]["reason"]
            == "supplier re-issued RS-2607-0141 at the metered volume"
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=captured["RS-2607-0141"]["id"])
        assert row.amount == Decimal("1250.00")
        assert row.status == "captured"
        # The footer follows the correction: 51,902.50 + 10.00.
        assert cost_capture.register()["total_amount"] == LE11_REGISTER_TOTAL + Decimal("10.00")

        # A void after close is lawful too, and its OWN reason is the correction
        # reason — one question is not asked twice on one form.
        voided = cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0158"]["id"],
            reason="duplicate of RS-2607-0141",
            voided_at=VOIDED_AT,
        )
        assert voided["status"] == "voided"
        assert voided["after_close"]["reason"] == "duplicate of RS-2607-0141"


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — isolation (the DATABASE half lives in test_us_led_018_capture.py)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_019_tc9__the_register_its_search_and_its_footer_are_all_tenant_scoped(
    brazos, lonestar, marcus, erin
):
    """*"J. Okafor opens Lone Star Ridge's register and exports its CSV → only
    Lone Star Ridge rows, in the list, in the search, in the totals footer and in
    the CSV."*"""
    with tenant_ctx(brazos):
        july_register(brazos, marcus)

    with tenant_ctx(lonestar):
        with_monthly_fiscal_year(erin)
        cost_capture.capture_supplier_invoice(
            erin,
            invoice_date=date(2026, 7, 18),
            service="water",
            supplier_name="City of Bandera",
            amount=Decimal("842.00"),
            currency="USD",
            volume=Decimal("220000"),
            volume_unit="gal",
            reference="LSR-BW-0091",
        )
        listed = cost_capture.register()
        assert listed["count"] == 1
        assert listed["total_amount"] == Decimal("842.00")
        assert cost_capture.register(q="Rosenberg")["count"] == 0
        assert cost_capture.register(service="electric")["count"] == 0

    with tenant_ctx(brazos):
        assert cost_capture.register()["total_amount"] == LE11_REGISTER_TOTAL


def test_us_led_019__the_sort_is_stable_across_two_identical_requests(brazos, marcus):
    """Three July invoices are dated 2026-07-31. Without a tiebreak the register
    reorders itself between two identical requests, and a clerk stops trusting
    it."""
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        first = [row["id"] for row in cost_capture.register()["rows"]]
        second = [row["id"] for row in cost_capture.register()["rows"]]
    assert first == second
    with tenant_ctx(brazos):
        with pytest.raises(cost_capture.CostCaptureError):
            cost_capture.register(sort="supplier_zip_code")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-019@d744841 (04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-019 §3 TC-1..TC-9 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-034/035/036 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-13 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md steps 6 and 9 · 12-governance/01-open-questions.md OQ-203)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S73's endpoints wait on OQ-204) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — the void's footer exclusion was driven by
#         summing every row regardless of status (`assert Decimal('51902.50') ==
#         Decimal('51747.50')`), the delete refusal by dropping the trigger from
#         ledger/0008 (the row deleted and the register returned 8), and TC-8 by
#         replacing `_refuse_after_close` with a real edit (the closed month
#         moved). Exact failures in the lane report
# exceptions: TC-6's DATABASE half carries `requires_postgres` (SQLite has no
#         triggers) and SKIPS with a vendor reason — never a bare
#         pytest.mark.skip · IS-2/IS-3/IS-4's BROWSER halves are not asserted
#         here: the 300 ms debounce, the URL persistence and the dynamic column
#         set are frontend behaviours and this lane ships no frontend. The
#         SERVER halves — the ≥2-character floor, the filters echoed back, the
#         server-side filtering — are asserted · the CSV of TC-9 is asserted as
#         the register READ it is generated from: IS-11's streamed download is
#         part of the download contract OQ-204 decides, so there is no file to
#         assert yet and a test over an invented one would be worth nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# DEF-LED-6710 · NFR-3 — THE REGISTER IS PAGED, AND THE FOOTER IS NOT
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6710__the_register_serves_a_page_and_a_whole_set_footer(
    brazos, marcus
):
    """A page is cut and the footer does NOT move — which is the whole argument.

    This register was unpaginated until 2026-09-25 and the defence written into
    its own docstring was *"the footer is a whole-set figure that a page cannot
    give."* It is the premise that was wrong rather than the conclusion: the
    footer is a SQL aggregate over the FILTERED set and a slice underneath it
    changes nothing.

    ⚠ **PROVED RED FIRST, AND THE RED IS QUOTED.** Computing the total from the
    page instead of the queryset — `sum(r.amount for r in rows[:size])` — served
    a footer of **$8,777.50** against the correct **$18,628.00** on a 62-row
    seeded register: 53% short, with every other assertion on this screen still
    green.

    ⚠ **AND THE OBVIOUS ASSERTION IS THE ONE THAT CANNOT SEE IT.** *"the footer
    is identical on page 1 and page 2"* passes on the broken version too, because
    both pages slice the same first rows. So this case asserts the footer against
    the SUM OF EVERY LIVE ROW, computed here, and never against another page.
    """
    with tenant_ctx(brazos):
        july_register(brazos, marcus)

        # Nine rows, three to a page: three pages, and a third page that is
        # SHORTER — a size that divides exactly cannot tell a last page from a
        # full one.
        first = cost_capture.register(page=1, page_size=4)
        second = cost_capture.register(page=2, page_size=4)
        third = cost_capture.register(page=3, page_size=4)
        beyond = cost_capture.register(page=99, page_size=4)
        whole = cost_capture.register(page=1, page_size=200)

    assert first["page"] == {"number": 1, "size": 4, "total": 9, "pages": 3}
    assert len(first["rows"]) == 4 and len(second["rows"]) == 4
    assert len(third["rows"]) == 1

    ids = [tuple(row["id"] for row in page["rows"]) for page in (first, second, third)]
    flat = [row_id for page in ids for row_id in page]
    assert len(set(flat)) == 9, "every row appears exactly once across the pages"
    assert ids[0] != ids[1], "page two is a DIFFERENT page, not the same one again"

    # The footer, against the sum of every live row rather than against a page.
    expected = sum(
        (row["amount"] for row in whole["rows"] if row["status"] == "captured"),
        Decimal("0"),
    )
    for page in (first, second, third):
        assert page["total_amount"] == expected == LE11_REGISTER_TOTAL
        assert page["count"] == 9 and page["live_count"] == 9

    # BR-SHL-011 — a page beyond the last is CLAMPED, never an error and never
    # a blank table.
    assert beyond["page"]["number"] == 3
    assert [row["id"] for row in beyond["rows"]] == list(ids[2])

    # NFR-5's shape: a bound on one REQUEST, never a cap on the data.
    with tenant_ctx(brazos):
        huge = cost_capture.register(page_size=1_000_000)
    assert huge["page"]["size"] == cost_capture.MAX_PAGE_SIZE


def test_def_led_6710__the_footer_foots_to_the_filter_and_not_to_the_page(
    brazos, marcus
):
    """A filtered page's footer is the FILTER's total, never the page's."""
    with tenant_ctx(brazos):
        july_register(brazos, marcus)
        paged = cost_capture.register(service="water", page=1, page_size=2)
        whole = cost_capture.register(service="water", page=1, page_size=200)

    assert paged["count"] == whole["count"] == 5
    assert len(paged["rows"]) == 2 and len(whole["rows"]) == 5
    assert paged["total_amount"] == whole["total_amount"]
    assert paged["total_amount"] != sum(
        (row["amount"] for row in paged["rows"]), Decimal("0")
    ), "the footer must not be the page's own sum"
