# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-021 (the cost-of-service section of the accounting export on
#           S42/S43: both sides leave in ONE idempotent batch — TC-1 the five
#           cost rows summing $51,902.50, TC-2 no second July batch, TC-3 the
#           open-period refusal, TC-4 drill-back on $28,222.00, TC-5 the missing
#           qbo_ref atomic block, TC-6 the voided purchase out of the payload
#           and the hash, TC-7 the register-derived label, TC-8 isolation)
#           Screens: S42 · S43
# Rules:    BR-LED-039 (the export carries the payable side out beside the
#           receivable side, in the SAME (period, target) batch) · BR-LED-004
#           (one recorded IDEMPOTENT batch; every figure drills back) ·
#           BR-LED-017 (export requires the covered period CLOSED) ·
#           BR-LED-014 (export codes on the GL mapping page) · BR-LED-035 (a
#           voided purchase leaves every aggregate) · BR-LED-015 (the export
#           audits)
# Golden:   LE-14 — July → QuickBooks, batch EXP-2607-QBO: LE-5's receivable
#           section footing **598.69 = 598.69** PLUS 5100 $28,222.00 · 5110
#           $3,100.00 · 5140 $6,235.00 · 5200 $1,845.50 · 5300 $12,500.00 =
#           **$51,902.50**, register-derived and NOT in the 598.69 footer
# ───────────────────────────────────────────────────────
"""Both sides of the books, out in one batch — and the label that keeps them apart.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_021_tc7__the_register_derived_section_is_labelled_and_never_summed_into_the_footer`.

⚠ **THE ROW SHAPE IS BLOCKED ON OQ-200, WHICH IS OPEN.** If a capture POSTS
(reading (a)) these are ordinary GL summary rows read out of the books, and
July's trial balance moves from LE-1's **598.69 = 598.69** to **52,501.19 =
52,501.19** — a change to golden test **GT-51** needing the HUMAN-GUIDE §6
finance re-sign. If it does not (reading (b)) the section is a **register
extract** and its total must never be added to a trial-balance footer that does
not contain it. Nothing here chooses: the section is register-derived, labelled
in three places, and carries `posting_shape_is_not_ruled`.

What US-LED-021 says is SETTLED either way — the arithmetic, the export codes,
the idempotency, the drill-back and the refusals — is what the rest of this file
asserts. **Adding the payable side loosens no existing gate.**
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import close, cost_capture, exports
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    EXPORTED_AT,
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    LE14_COST_ROWS,
    LE14_QBO_REFS,
    LE13_TOTAL_AFTER_VOID,
    VOIDED_AT,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
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

pytestmark = pytest.mark.django_db


def july_captured_and_closed(tenant, clerk, *, close_it=True, refs=True):
    """LE-11's nine purchases, the QBO refs Norma sets, and (optionally) the
    close BR-LED-017 requires before anything may be exported."""
    admin = staff_actor(tenant, "system_admin", f"setup-exp-{tenant.subdomain}@brazos.test")
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    captured = capture_le11_month(clerk)
    if refs:
        # LE-14: the cost section's QBO refs are UNSET in the fixture, so TC-5's
        # atomic block fires until Norma sets them. Setting them here is the
        # precondition for every case that is not TC-5 itself.
        for code, ref in LE14_QBO_REFS.items():
            ledger_models.LedgerAccount.objects.filter(tenant=tenant, code=code).update(
                qbo_ref=ref
            )
    if close_it:
        close.close_period(
            admin,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="the deposit register is still being matched",
        )
    return captured, admin


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the five cost rows, in ONE batch, with ONE hash
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc1__the_cost_section_carries_five_rows_summing_51902_50(
    brazos, marcus, monkeypatch
):
    """*"Export July to QuickBooks after close → the batch carries LE-5's
    existing receivable rows **plus 5 cost rows** — 5100 $28,222.00 · 5110
    $3,100.00 · 5140 $6,235.00 · 5200 $1,845.50 · 5300 $12,500.00, Σ
    $51,902.50 — each with its `qbo_ref`; ONE batch, one hash, one audit row."*
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    section = preview["cost_section"]

    assert {row["code"]: row["amount"] for row in section["rows"]} == LE14_COST_ROWS
    assert section["entries"] == 5
    assert section["cost_total"] == LE11_REGISTER_TOTAL
    assert sum(LE14_COST_ROWS.values(), Decimal("0")) == LE11_REGISTER_TOTAL
    # Each row carries the ref the target addresses it by (BR-LED-014).
    assert {row["code"]: row["target_ref"] for row in section["rows"]} == LE14_QBO_REFS
    # And its `unsigned` marker, because no column carries it (field map D-10)
    # and US-LED-017 TC-5 forbids presenting a proposed code as signed.
    #
    # ⚠ AMENDED 2026-08-18: this pinned `is True` on every row. The Product
    # Owner finance re-signed all eight cost codes and names that day — shown in
    # plain English, no dollar figure attached to any of them, B4/B5 ❄️ FROZEN
    # and un-edited — so an export row marked unsigned would carry a stale
    # warning into a QuickBooks batch.
    assert all(row["unsigned"] is False for row in section["rows"])

    # ── the marker mechanism, on a code unsigned only inside this test ───────
    # With nothing real left unsigned the assertion above would pass just as
    # happily if the export had stopped carrying the marker at all — a vacuous
    # guard reads as protection and is none. So the export is re-run against a
    # synthetic unsigned 5110 and must mark that row and only that row.
    # Precedent: CR-011 item 9 on `test_us_not_005`.
    from apps.ledger import chart as ledger_chart

    monkeypatch.setattr(ledger_chart, "PENDING_FINANCE_RE_SIGN_COST", ("5110",))
    with tenant_ctx(brazos):
        marked = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    by_code = {row["code"]: row for row in marked["cost_section"]["rows"]}
    assert by_code["5110"]["unsigned"] is True
    assert by_code["5100"]["unsigned"] is False


def test_us_led_021_tc1__one_batch_one_hash_one_audit_row(brazos, marcus, audit_rows):
    """BR-LED-039: *"inside the SAME recorded, idempotent `export_batches` row
    keyed on (period, target) — **not a second batch**"*."""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        audit_rows.clear()
        batch = exports.create_export_batch(
            staff_actor(brazos, "system_admin", "sender@brazos.test"),
            period_start=JULY_START,
            period_end=JULY_END,
            target=ledger_models.EXPORT_QBO,
            created_at=EXPORTED_AT,
        )
        stored = ledger_models.ExportBatch.objects.filter(tenant=brazos)

    assert stored.count() == 1, "the payable side created a SECOND July batch"
    row = stored.first()
    assert len(row.content_hash) == 64
    # The cost rows are IN the stored payload — one hash over both sections.
    cost_rows = [entry for entry in row.payload if entry.get("section") == "cost_of_service"]
    assert len(cost_rows) == 5
    assert {entry["code"] for entry in cost_rows} == set(LE14_COST_ROWS)

    created = [r for r in audit_rows if r["action"] == "export.batch_created"]
    assert len(created) == 1
    # Stored at the column's own NUMERIC(18,6) scale — never rounded to display
    # (BR-LED-025: the ledger is not a second rounding site).
    assert Decimal(created[0]["after"]["cost_of_service_total"]) == LE11_REGISTER_TOTAL
    assert created[0]["after"]["cost_of_service_rows"] == 5
    assert created[0]["after"]["cost_of_service_source"] == "register"
    assert batch["content_hash"] == row.content_hash


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 — the existing gates are unchanged
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc2__a_re_run_is_still_blocked_with_a_link_to_the_batch(
    brazos, marcus
):
    """*"Re-run July to QBO after the cost section exists → **blocked with a link
    to the existing batch**. Adding the payable side does NOT create a second
    July batch — a utility must never receive one month twice."*"""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        sender = staff_actor(brazos, "system_admin", "sender2@brazos.test")
        first = exports.create_export_batch(
            sender,
            period_start=JULY_START,
            period_end=JULY_END,
            target=ledger_models.EXPORT_QBO,
            created_at=EXPORTED_AT,
        )
        with pytest.raises(exports.ExportError) as blocked:
            exports.create_export_batch(
                sender,
                period_start=JULY_START,
                period_end=JULY_END,
                target=ledger_models.EXPORT_QBO,
                created_at=EXPORTED_AT,
            )
        assert blocked.value.existing_batch["batch_id"] == first["batch_id"]
        assert ledger_models.ExportBatch.objects.filter(tenant=brazos).count() == 1


def test_us_led_021_tc3__an_open_period_is_still_refused(brazos, marcus):
    """*"Export attempted for a period that is still OPEN → refused —
    BR-LED-017's L-3b gate is unchanged by this section."*

    Adding the payable side must loosen no existing gate.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, close_it=False)
        with pytest.raises(exports.ExportError) as refused:
            exports.create_export_batch(
                staff_actor(brazos, "system_admin", "sender3@brazos.test"),
                period_start=JULY_START,
                period_end=JULY_END,
                target=ledger_models.EXPORT_QBO,
                created_at=EXPORTED_AT,
            )
        assert "NOT CLOSED" in str(refused.value)
        assert not ledger_models.ExportBatch.objects.filter(tenant=brazos).exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — every exported figure explains itself
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc4__drill_back_on_28222_opens_the_power_cooperative_invoice(
    brazos, marcus
):
    """*"Drill-back on a cost row: 'what is the $28,222.00?' opens **BVPC-070026,
    Brazos Valley Power Cooperative, 412,000 kWh, 2026-07-31**."*

    The BR-LED-004 discipline applied to the payable side.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        answer = exports.cost_drill_back(
            code="5100", period_start=JULY_START, period_end=JULY_END
        )
    assert answer["total"] == Decimal("28222.00")
    assert len(answer["purchases"]) == 1
    purchase = answer["purchases"][0]
    assert purchase["reference"] == "BVPC-070026"
    assert purchase["supplier_name"] == "Brazos Valley Power Cooperative"
    assert purchase["volume"] == Decimal("412000") and purchase["volume_unit"] == "kWh"
    assert purchase["invoice_date"] == date(2026, 7, 31)
    # The drill-back says what it is derived FROM, for the same reason the
    # section does.
    assert answer["source"] == exports.COST_SECTION_SOURCE_REGISTER
    # ⚠ AMENDED 2026-09-02 (CR-060 T6c). This asserted `COST_SHAPE_NOT_RULED`,
    # the code that says *"nobody has decided whether a capture posts"*. The PO
    # decided on 2026-08-16 closing OQ-200, and `cost_section` was moved to
    # `COST_SHAPE_RULED_REGISTER` the same day — the drill-back was left behind,
    # so it went on telling a finance officer a ruled question was open for a
    # fortnight. Hard-won law 1, in a payload rather than in a comment, and this
    # line is why nothing caught it: the test pinned the stale value.
    assert exports.COST_SHAPE_RULED_REGISTER in answer["problems"]
    assert exports.COST_SHAPE_NOT_RULED not in answer["problems"]

    # Water's five purchases drill back as five rows footing $3,100.00.
    with tenant_ctx(brazos):
        water = exports.cost_drill_back(
            code="5110", period_start=JULY_START, period_end=JULY_END
        )
    assert len(water["purchases"]) == 5 and water["total"] == Decimal("3100.00")


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — a cost account with no target ref blocks the export ATOMICALLY
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc5__a_cost_account_without_a_qbo_ref_blocks_the_export_by_name(
    brazos, marcus
):
    """*"A cost account has no `qbo_ref` → export to QBO blocked **naming the
    account**; code-addressed CSV and IIF remain available."*

    LE-14: the cost section's refs are UNSET in the fixture, so this fires until
    Norma sets 5100→412, 5110→413, 5140→414, 5200→420, 5300→430.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus, refs=False)
        sender = staff_actor(brazos, "system_admin", "sender4@brazos.test")
        with pytest.raises(exports.ExportError) as blocked:
            exports.create_export_batch(
                sender,
                period_start=JULY_START,
                period_end=JULY_END,
                target=ledger_models.EXPORT_QBO,
                created_at=EXPORTED_AT,
            )
        message = str(blocked.value)
        for code, name in (
            ("5100", "Purchased power"),
            ("5110", "Purchased water"),
            ("5140", "Purchased gas"),
            ("5200", "Operations & maintenance"),
            ("5300", "Infrastructure"),
        ):
            assert f"{code} · {name}" in message
        # ATOMIC — nothing partial handed over.
        assert not ledger_models.ExportBatch.objects.filter(tenant=brazos).exists()

        # CSV addresses accounts by code+name and stays available, which is
        # US-LED-006 TC-5's own second sentence — unchanged by this section.
        csv_batch = exports.create_export_batch(
            sender,
            period_start=JULY_START,
            period_end=JULY_END,
            target=ledger_models.EXPORT_CSV,
            created_at=EXPORTED_AT,
        )
        assert csv_batch["target"] == "csv"
        stored = ledger_models.ExportBatch.objects.get(tenant=brazos, target="csv")
        cost_rows = [e for e in stored.payload if e.get("section") == "cost_of_service"]
        assert len(cost_rows) == 5


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — a voided purchase is out of the payload AND out of the hash
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc6__a_voided_purchase_leaves_the_payload_and_the_hash(
    brazos, marcus
):
    """*"A voided purchase (RS-2607-0192) sits in the period → excluded from the
    exported section; the batch hash reflects the live set only."*

    BR-LED-035: the row stays visible in the REGISTER and leaves every
    AGGREGATE. The section total moves 51,902.50 → **51,747.50** and the two
    hashes differ, which is what "out of the hash" means in one assertion.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured_and_closed(brazos, marcus, close_it=False)
        before = exports.cost_section(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
        hash_before = exports.content_hash(exports._cost_payload(before))

        cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        after = exports.cost_section(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
        hash_after = exports.content_hash(exports._cost_payload(after))

    assert before["cost_total"] == LE11_REGISTER_TOTAL
    assert after["cost_total"] == LE13_TOTAL_AFTER_VOID
    assert before["cost_total"] - after["cost_total"] == Decimal("155.00")
    assert hash_before != hash_after
    # Water's row moved by exactly the voided amount; nothing else moved.
    water_before = {r["code"]: r["amount"] for r in before["rows"]}["5110"]
    water_after = {r["code"]: r["amount"] for r in after["rows"]}["5110"]
    assert water_before - water_after == Decimal("155.00")
    # And the row is STILL in the register, with its reason.
    with tenant_ctx(brazos):
        listed = {row["reference"]: row for row in cost_capture.register()["rows"]}
    assert listed["RS-2607-0192"]["status"] == "voided"
    assert listed["RS-2607-0192"]["void_reason"] == "duplicate of RS-2607-0175"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — ⚠ THE HONESTY GUARD. OQ-200 is OPEN and the label says so.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc7__the_register_derived_section_is_labelled_and_never_summed_into_the_footer(
    brazos, marcus
):
    """*"The cost section is register-derived while the receivable rows are
    journal-derived → the section is **labelled as register-derived** and its
    total is **not** added to the trial-balance footer; an unlabelled mixed
    total is a figure no reader can reconcile, and it is the failure this TC
    exists to catch."*

    **OQ-200 is RULED (PO 2026-08-16, option (b) for R2)**, so this is no longer
    one of two possible shapes — it is THE shape, and the problem code says so:
    `cost_section_is_register_derived`, not `posting_shape_is_not_ruled`. A
    screen still calling a ruled question open reads to a finance officer as
    "this number may be about to change", which it is not.

    Asserted four ways, because a label that lives in one place is a label
    somebody will drop.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        preview = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    section = preview["cost_section"]

    # 1 · The section says what it is derived from.
    assert section["source"] == exports.COST_SECTION_SOURCE_REGISTER
    assert section["in_trial_balance"] is False
    assert exports.COST_SHAPE_RULED_REGISTER in section["problems"]
    # The SUPERSEDED code must be gone, not merely joined: a payload carrying
    # both would let a reader pick the one that suits them.
    assert exports.COST_SHAPE_NOT_RULED not in section["problems"]
    assert "OQ-200" in section["label"]
    assert "that is the RULING rather than a gap" in section["label"]
    # ⚠ AMENDED 2026-09-02 (CR-060 T6c). This also required the label to carry
    # **52,501.19** as *"where July's trial balance moves the day a
    # supplier-payment path ships"*. Two things about that sentence are now
    # false and it is retired rather than reworded. (1) The DAY came by a
    # different route — a paid-on date, not a payment path — so the label was
    # naming an expiry that would never arrive. (2) The FIGURE was a projection
    # (598.69 + 51,902.50) and it is **150.00 high**: the T6 lane measured
    # **52,351.19** settling all nine, because a trial balance nets each account
    # onto one side and paying suppliers takes 1000 Cash out of the debit column
    # altogether. Nothing signed moved — 598.69 is the signature and 52,501.19
    # never was one — and `tests/test_cr060_t6_settlement_posting.py` asserts
    # both numbers and the 150.00 between them.
    assert "52,501.19" not in section["label"]
    # What the label must now say instead: a SETTLED purchase is not in these
    # rows, because it is in the books (DEF-3380).
    assert "SETTLED" in section["label"]

    # 2 · EVERY ROW says it too, so a row copied out of the payload keeps it.
    assert all(row["source"] == exports.COST_SECTION_SOURCE_REGISTER for row in section["rows"])

    # 3 · The $51,902.50 is NOT in the balanced footer. LE-1's July trial
    # balance is untouched by nine captures, because nothing was posted.
    assert preview["total_debits"] == preview["total_credits"]
    assert preview["total_debits"] != preview["total_debits"] + section["cost_total"]
    assert section["cost_total"] not in (preview["total_debits"], preview["total_credits"])
    assert preview["balanced"] is True

    # 4 · No cost row carries a DEBIT or a CREDIT. A captured purchase has no
    # SIDE, because OQ-200 ruled that it does not post — writing one would
    # assert a posting that did not happen, inside a payload an ERP reads.
    payload = exports._cost_payload(section)
    assert all("debit" not in row and "credit" not in row for row in payload)
    assert all(row["source"] == "register" for row in payload)


def test_us_led_021__nine_captures_move_no_journal_row_at_all(brazos, marcus):
    """The invariance J25 step 13 asks for: *"LE-1's July trial balance is still
    598.69 = 598.69"*.

    Nothing in this whole capability posts, because whether it should is OQ-200.
    Asserted as the absence of any journal row rather than as a figure, so it
    holds whatever else the month contains.
    """
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)
        assert ledger_models.SupplierInvoice.objects.filter(tenant=brazos).count() == 9
        assert not ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type="supplier_invoice"
        ).exists()
        assert not ledger_models.JournalLine.objects.filter(
            tenant=brazos, source_type="supplier_invoice"
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_021_tc8__no_foreign_purchase_reaches_another_tenants_payload(
    brazos, lonestar, marcus, erin
):
    """*"Lone Star Ridge exports its own July → its own cost rows, its own refs,
    its own batch series; no Brazos Bend purchase appears in its payload or its
    hash."*"""
    with tenant_ctx(brazos):
        july_captured_and_closed(brazos, marcus)

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
        ledger_models.LedgerAccount.objects.filter(tenant=lonestar, code="5110").update(
            qbo_ref="901"
        )
        close.close_period(
            erin,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="closing our own July",
        )
        theirs = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
        batch = exports.create_export_batch(
            erin,
            period_start=JULY_START,
            period_end=JULY_END,
            target=ledger_models.EXPORT_QBO,
            created_at=EXPORTED_AT,
        )
        stored = ledger_models.ExportBatch.objects.get(tenant=lonestar)

    assert theirs["cost_section"]["cost_total"] == Decimal("842.00")
    assert [row["code"] for row in theirs["cost_section"]["rows"]] == ["5110"]
    assert theirs["cost_section"]["rows"][0]["target_ref"] == "901"
    # No Brazos Bend figure, supplier or ref anywhere in the payload.
    payload = repr(stored.payload)
    for foreign in ("28222", "Rosenberg", "Brazos Valley", "412", "413", "51902.50"):
        assert foreign not in payload, f"{foreign!r} leaked into Lone Star Ridge's payload"
    assert batch["content_hash"] != ""

    # And Brazos Bend's own batch is unaffected.
    with tenant_ctx(brazos):
        ours = exports.export_preview(
            period_start=JULY_START, period_end=JULY_END, target=ledger_models.EXPORT_QBO
        )
    assert ours["cost_section"]["cost_total"] == LE11_REGISTER_TOTAL


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-021@d744841 (04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-021 §3 TC-1..TC-8 + §7 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-039/004/017 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-14 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md steps 10-11 · 12-governance/01-open-questions.md OQ-200)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S42/S43's endpoints are US-LED-016's own deferral, unchanged) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — TC-7 was driven by adding the section total
#         to `total_debits` (`assert Decimal('52501.19') != Decimal('52501.19')`
#         failed, which is the unlabelled mixed total the TC exists to catch);
#         TC-6 by dropping the `status=captured` filter from `cost_section` (the
#         voided $155.00 stayed in the payload and the two hashes matched); TC-5
#         by leaving the cost accounts out of `missing_refs` (the QBO batch
#         recorded with five unaddressable rows). Exact failures in the lane
#         report
# exceptions: **THE ROW SHAPE IS BLOCKED ON OQ-200** — the section is
#         REGISTER-DERIVED and labelled in three places, its total is carried
#         outside total_debits/total_credits, and no row carries a debit or a
#         credit. Under reading (a) these become journal-derived and July's
#         trial balance moves 598.69 → 52,501.19, which is GT-51 and takes the
#         HUMAN-GUIDE §6 re-sign · `EXP-2607-QBO` is still not reproduced: no
#         tenant has the `export_batch` number series, so `batch_no` is None and
#         the batch's identity is (period, target) — US-LED-016's own reported
#         gap, unchanged by this section · NO FILE IS WRITTEN (BR-LED-020 v1
#         records the batch and its payload; the S43 modal and IS-11 streamed
#         downloads are other lanes') · the isolation case is the APP-layer half;
#         the RLS proof for `supplier_invoices` is in
#         tests/test_us_led_018_capture.py under `requires_postgres`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
