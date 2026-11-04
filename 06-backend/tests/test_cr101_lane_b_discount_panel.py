# ── Trace ──────────────────────────────────────────────
# Change:   CR-101-BRC03 §06 lane B — the Fix a bill wizard's step-2 DISCOUNTS
#           panel (p129 of `05-prototype/04 Billing, As Built.pdf`: drawn in all
#           five variants, *"an absent panel is drawn, never omitted"*).
# Rules:    BR-BIL-044 (nine sections, none added, none collapsed away — the
#           panel lives INSIDE section 3, the money) · BR-BIL-792 (a correction
#           re-prices WITH the account's discounts at the corrected period's
#           own service date) · BR-RAT-007 (the service date is the pivot) ·
#           CLAUDE.md rule 2 (money as strings, never floats) · hard-won law 1
#           (a comment claiming a stamp is not the stamp — `discount_grants`)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""What reduced the original bill, what reduces the corrected one, which version.

Proved RED first (2026-09-15) against the tip `9cda92e6` extracted into a
scratch tree (`git archive 9cda92e6 06-backend`, these two files copied in,
the same `pytest` from the same venv): **all twelve failed**, every one on
`KeyError: 'discounts'` — the preview and the batch panel carried no such key —
and all twelve pass here. The recomputation is SUPPLIED, as every correction test in
this repo supplies it — B5 owns the corrected figures and the golden suite
proves the engine; what is tested here is what the preview PUBLISHES about the
discount lines both bills carry.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import bulk_corrections, corrections, models, rating_seam, single_correction
from apps.billing.correction_models import (
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    CorrectionCaseBill,
)
from apps.rating import discounts as discount_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_016_bulk_corrections import (
    CORRECTED_TOTAL,
    TODAY,
    _RatedBill,
    _RatedLine,
    an_issued_bill,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

SENIOR_LABEL = "Senior discount"
SENIOR_CODE = "SENIOR"
REDUCTION = Decimal("-10.00")


def _a_programme(
    tenant, *, code=SENIOR_CODE, name=SENIOR_LABEL, versions=((1, date(2026, 1, 1), None),)
):
    """A discount programme whose bill line label is `name`, with ACTIVE versions."""
    discount = discount_models.Discount.objects.create(
        tenant=tenant, code=code, name=name, status=discount_models.DISCOUNT_ACTIVE
    )
    made = []
    for version_no, effective_from, effective_to in versions:
        made.append(
            discount_models.DiscountVersion.objects.create(
                tenant=tenant,
                discount=discount,
                version_no=version_no,
                status=discount_models.VERSION_ACTIVE,
                effective_from=effective_from,
                effective_to=effective_to,
                discount_type=discount_models.DISCOUNT_PERCENTAGE,
                value=Decimal("10"),
                currency="USD",
            )
        )
    return discount, made


def _with_discount_line(tenant, invoice, *, label=SENIOR_LABEL, amount=REDUCTION):
    """The ORIGINAL bill's reduction — its own `discount` line, negative (BR-RAT-068)."""
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=invoice.account,
        kind="discount",
        description=label,
        amount=amount,
        taxable=False,
    )
    return invoice


def _recomputed(invoice, *, discount_lines=((SENIOR_LABEL, REDUCTION),)):
    """WE-9's recomputation, plus the engine's discount line(s) — supplied."""
    lines = [
        _RatedLine(
            line.kind,
            line.description,
            Decimal("26.50") if line.kind == "usage" else line.amount,
            service=line.service.code if line.service_id else None,
        )
        for line in invoice.lines.all().order_by("created_at", "id")
        if line.kind != "discount"
    ]
    for label, amount in discount_lines:
        lines.append(_RatedLine("discount", label, amount))
    return _RatedBill(lines, CORRECTED_TOTAL)


def _bill(brazos, dana, *, invoice_no="BL-2607-000201", discounted=True):
    account = an_account(dana, brazos)
    run = a_run(brazos, key="2026-07|cycle-A")
    invoice = an_issued_bill(brazos, account, run, invoice_no=invoice_no)
    if discounted:
        _with_discount_line(brazos, invoice)
    return invoice


def _panel(invoice, *, correction_class=CLASS_RESTATEMENT, corrected=None, goodwill=None):
    impact = corrections.build_impact(
        invoice,
        reason_codes=("wrong_read",),
        correction_class=correction_class,
        corrected=corrected,
        goodwill_amount=goodwill,
    )
    return impact.as_dict()["discounts"]


# ═══════════════════════════════════════════════════════════════════════════
# 26.1 · one bill — "On both bills" + which version
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc1__a_restatement_shows_the_discount_on_both_bills_with_its_version(brazos, dana):
    """p129, 26.1: *"On both bills" + which version*. The original's discount line
    and the corrected bill's discount line, each naming SENIOR version 1."""
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        panel = _panel(invoice, corrected=_recomputed(invoice))

    assert panel["outcome"] == corrections.DISCOUNTS_ON_BOTH
    assert [row["label"] for row in panel["original"]] == [SENIOR_LABEL]
    assert [row["label"] for row in panel["corrected"]] == [SENIOR_LABEL]
    for side in ("original", "corrected"):
        (row,) = panel[side]
        assert row["amount"] == "-10.00", "the reduction is the line's own, negative"
        assert row["code"] == SENIOR_CODE
        assert row["version_no"] == 1
        assert row["version_id"], "which VERSION is the drawn requirement"
        assert row["reason"] is None
    assert panel["original_total"] == "-10.00"
    assert panel["corrected_total"] == "-10.00"
    assert panel["delta"] == "0.00"
    assert panel["currency"] == "USD"
    assert panel["version_basis"] == corrections.DISCOUNT_VERSION_BASIS
    assert panel["problems"] == []
    # Money travels as STRINGS (rule 2): nothing in the panel is a float.
    for row in panel["original"] + panel["corrected"]:
        assert isinstance(row["amount"], str)


def test_lane_b_tc2__a_recomputation_that_drops_the_discount_says_so_by_code(brazos, dana):
    """The corrected period re-prices WITHOUT the reduction (the enrolment lapsed):
    the panel says `on_the_original_only` and shows the money that left."""
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        panel = _panel(invoice, corrected=_recomputed(invoice, discount_lines=()))

    assert panel["outcome"] == corrections.DISCOUNTS_ORIGINAL_ONLY
    assert len(panel["original"]) == 1 and panel["corrected"] == []
    assert panel["original_total"] == "-10.00"
    assert panel["corrected_total"] == "0.00"
    assert panel["delta"] == "10.00", "the customer loses the reduction — shown, not netted away"


def test_lane_b_tc2b__no_discount_anywhere_is_a_drawn_panel_not_an_absent_one(brazos, dana):
    """p129: *"An absent panel is drawn, never omitted."* WE-9's own bill carries
    no reduction, and the panel still exists with the code saying so."""
    with tenant_ctx(brazos):
        invoice = _bill(brazos, dana, discounted=False)
        panel = _panel(invoice, corrected=_recomputed(invoice, discount_lines=()))

    assert panel["outcome"] == corrections.DISCOUNTS_NONE
    assert panel["original"] == [] and panel["corrected"] == []
    assert panel["original_total"] == "0.00" and panel["delta"] == "0.00"


# ═══════════════════════════════════════════════════════════════════════════
# 26.4 goodwill · 26.5 the page only — the two ABSENT panels, drawn
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc3__goodwill_says_nothing_is_repriced(brazos, dana):
    """p129, 26.4: *"Nothing is re-priced."* The bill is untouched (PO
    2026-08-11), so what reduces the corrected bill IS what reduced the original."""
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        panel = _panel(invoice, correction_class=CLASS_CREDIT_ONLY, goodwill=Decimal("25.00"))

    assert panel["outcome"] == corrections.DISCOUNTS_NOT_REPRICED
    assert panel["original"] == panel["corrected"]
    assert panel["original"][0]["version_no"] == 1
    assert panel["delta"] == "0.00"


def test_lane_b_tc4__a_document_correction_says_unchanged(brazos, dana):
    """p129, 26.5: *"Unchanged."*"""
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        panel = _panel(invoice, correction_class=CLASS_DOCUMENT)

    assert panel["outcome"] == corrections.DISCOUNTS_UNCHANGED
    assert panel["original"] == panel["corrected"]
    assert panel["delta"] == "0.00"


# ═══════════════════════════════════════════════════════════════════════════
# WHICH version — resolved at the bill's own service date, by LABEL
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc5__the_version_is_the_one_in_force_on_the_bills_service_date(brazos, dana):
    """26.2's *"each month on its own enrolment"*: a July bill names July's
    version even though version 2 is in force today. BR-RAT-007's pivot."""
    with tenant_ctx(brazos):
        _, (v1, v2) = _a_programme(
            brazos,
            versions=((1, date(2026, 1, 1), date(2026, 7, 31)), (2, date(2026, 8, 1), None)),
        )
        invoice = _bill(brazos, dana)  # service_date 2026-07-31
        assert invoice.service_date == date(2026, 7, 31)
        panel = _panel(invoice, corrected=_recomputed(invoice))

    (row,) = panel["original"]
    assert row["version_no"] == 1 and row["version_id"] == str(v1.id)
    assert row["effective_from"] == "2026-01-01"
    assert str(v2.id) not in {r["version_id"] for r in panel["original"] + panel["corrected"]}


def test_lane_b_tc6__a_label_that_names_no_programme_or_two_is_a_named_miss(brazos, dana):
    """`Discount.name` is the only identity a bill's discount line carries, and
    `name` is not unique. Neither miss is silent and neither drops the row."""
    with tenant_ctx(brazos):
        _a_programme(brazos, code="SENIOR", name="Senior discount")
        _a_programme(brazos, code="SENIOR2", name="Senior discount")  # the same label twice
        invoice = _bill(brazos, dana)
        _with_discount_line(brazos, invoice, label="Hardship credit", amount=Decimal("-5.00"))
        panel = _panel(
            invoice,
            corrected=_recomputed(
                invoice,
                discount_lines=((SENIOR_LABEL, REDUCTION), ("Hardship credit", Decimal("-5.00"))),
            ),
        )

    by_label = {row["label"]: row for row in panel["original"]}
    assert by_label[SENIOR_LABEL]["reason"] == "label_names_several_programmes"
    assert by_label[SENIOR_LABEL]["version_id"] is None
    assert by_label["Hardship credit"]["reason"] == "no_programme_carries_this_label"
    assert by_label["Hardship credit"]["amount"] == "-5.00", "the money is the bill's own"
    assert panel["original_total"] == "-15.00"


def test_lane_b_tc7__rating_unpublished_is_a_problem_not_a_blank_column(brazos, dana, monkeypatch):
    """The seam's rule: an unwired read REPORTS. The amounts are unaffected."""
    monkeypatch.setattr(rating_seam, "_resolve", lambda module, attribute, kind="services": None)
    with tenant_ctx(brazos):
        invoice = _bill(brazos, dana)
        panel = _panel(invoice, corrected=_recomputed(invoice))

    assert panel["outcome"] == corrections.DISCOUNTS_ON_BOTH
    assert [p["code"] for p in panel["problems"]] == [corrections.DISCOUNT_VERSIONS_UNAVAILABLE]
    assert panel["original"][0]["version_id"] is None
    assert panel["original"][0]["amount"] == "-10.00"


# ═══════════════════════════════════════════════════════════════════════════
# Where it lives: section 3 of nine, in the hash, and on the batch panel
# ═══════════════════════════════════════════════════════════════════════════
def test_lane_b_tc8__the_panel_is_in_section_three_and_the_nine_are_still_nine(
    brazos, dana, monkeypatch
):
    """BR-BIL-044: no tenth section. The panel rides inside `the_money`, as the
    settlement panel rides inside `the_customers_balance` (CR-059 task 20)."""
    monkeypatch.setattr(corrections, "recompute", _recomputed)
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        single = single_correction.open_for_bill(
            invoice, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        sections = single_correction.nine_sections(single)

    assert list(sections) == [name for _, name in single_correction.PREVIEW_SECTIONS]
    assert len(sections) == 9
    panel = sections["the_money"]["discounts"]
    assert panel["outcome"] == corrections.DISCOUNTS_ON_BOTH
    assert panel["original"][0]["code"] == SENIOR_CODE


def test_lane_b_tc9__approval_binds_the_panel_because_it_is_inside_the_hash(brazos, dana):
    """BR-BIL-044: approval binds THE ARTIFACT. Two impacts differing only in
    the discounts panel hash differently, so a moved version cannot execute
    against a signature that never saw it."""
    with tenant_ctx(brazos):
        _a_programme(brazos)
        invoice = _bill(brazos, dana)
        impact = corrections.build_impact(
            invoice,
            reason_codes=("wrong_read",),
            correction_class=CLASS_RESTATEMENT,
            corrected=_recomputed(invoice),
        ).as_dict()
    moved = dict(impact, discounts=dict(impact["discounts"], corrected=[]))
    assert bulk_corrections._hash_of([impact]) != bulk_corrections._hash_of([moved])


def test_lane_b_tc10__a_case_stored_before_the_panel_existed_draws_it_by_code(
    brazos, dana, monkeypatch
):
    """Approval binds the stored artifact, so an old case is NOT recomputed to
    fill the gap — the panel is drawn with `not_in_this_preview` instead."""
    monkeypatch.setattr(corrections, "recompute", _recomputed)
    with tenant_ctx(brazos):
        invoice = _bill(brazos, dana, discounted=False)
        single = single_correction.open_for_bill(
            invoice, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        row = CorrectionCaseBill.objects.get(pk=single.bill_row.pk)
        stale = dict(row.impact)
        del stale["discounts"]
        row.impact = stale
        row.save(update_fields=["impact"])
        single = single_correction.SingleCase(case=single.case, bill_row=row, invoice=invoice)
        panel = single_correction.nine_sections(single)["the_money"]["discounts"]

    assert panel["outcome"] == single_correction.DISCOUNTS_NOT_IN_ARTIFACT
    assert panel["original"] == [] and panel["original_total"] is None


def test_lane_b_tc11__the_batch_panel_counts_bills_and_accounts_affected(brazos, dana, monkeypatch):
    """p129, 26.3: *"Accounts affected."* Three bills on two accounts, two of
    them discounted — the batch cell is a display sum over the per-bill panels."""
    monkeypatch.setattr(corrections, "recompute", _recomputed)
    with tenant_ctx(brazos):
        _a_programme(brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        first = an_account(dana, brazos, account_no="A-20001")
        second = an_account(dana, brazos, account_no="A-20002")
        bills = (
            _with_discount_line(
                brazos, an_issued_bill(brazos, first, run, invoice_no="BL-2607-000301")
            ),
            _with_discount_line(
                brazos, an_issued_bill(brazos, second, run, invoice_no="BL-2607-000302")
            ),
            an_issued_bill(brazos, second, run, invoice_no="BL-2607-000303"),
        )
        case = bulk_corrections.open_case(
            reason_codes=("wrong_rate_plan",),
            scope_kind="run",
            scope={"bill_run_id": str(run.pk)},
            invoices=bills,
            actor=dana,
            as_of=TODAY,
        )
        panel = bulk_corrections.aggregate(case).as_dict()["discounts"]
        rows = bulk_corrections.case_bills(case)

    # The third bill's recomputation ALSO carries the engine's discount line
    # (the supplied recomputation is uniform), so it counts on the corrected
    # side: three bills, two accounts.
    assert panel["outcome"] == bulk_corrections.BATCH_DISCOUNTS_REPRICED
    assert panel["bills"] == 3
    assert panel["accounts_affected"] == 2
    assert panel["original_total"] == "-20.00", "two original bills carried the reduction"
    assert panel["corrected_total"] == "-30.00", "all three corrected bills carry it"
    assert panel["delta"] == "-10.00"
    (cell,) = panel["by_label"]
    assert cell["label"] == SENIOR_LABEL and cell["code"] == SENIOR_CODE and cell["bills"] == 3
    # Every pinned row carries its own panel — 26.2's "each month on its own enrolment".
    assert all("discounts" in row.impact for row in rows)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-101-BRC03 §06 (05-prototype/04 Billing, As Built.pdf p129–p144,
#         read as images) · 04-docs/05-modules/07-billing/02-business-rules.md
#         BR-BIL-044/792 · 04-docs/05-modules/07-billing/conformance/
#         CR-101-BRC03-step2-06-lane-B-backend.md
# generated: 2026-09-15 by the CR-101-BRC03 §06 lane B (backend) — Fable 5.1
# checklist: A✔ B✔ C✔ D✔ E=deferred(lane A owns 07-frontend/src/features/billing)
#         F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 rows in
#         12-governance/09-human-review-ledger.md for corrections.py and
#         bulk_corrections.py)
# gates: RED PROVED FIRST — run against the tip 9cda92e6 extracted into a
#         scratch tree: all twelve failed on `KeyError: 'discounts'`; green
#         here after the panel landed (12/12)
# exceptions: pure reads over rows this file writes and no catch-and-continue
#         anywhere on the path (law 14 does not bind) — run on PostgreSQL 16 as
#         well (12/12 under config.settings.local, 2026-09-15) beside its
#         sibling; the recomputation is SUPPLIED as in every correction
#         test, so the engine's own discount pricing is proved elsewhere
#         (tests/test_def_502_discount_stage.py, tests/test_def_536_discount_gl.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
