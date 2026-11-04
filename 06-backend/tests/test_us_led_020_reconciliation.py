# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-020 (bought vs billed on S74: the unaccounted-for percentage
#           and the ABSENT-with-reason case that protects it — TC-1 water
#           9.00%, TC-2 electric 5.50%, TC-3 the suppressed −13.75%, TC-4 O&M
#           and infrastructure suppress nothing, TC-5 MMBtu vs ccf, TC-6
#           drill-back, TC-7 the voided purchase, TC-8 no money percentage,
#           TC-9 the unavailable billing read, TC-10 isolation)
#           Screens: S74 · S73
# Rules:    BR-LED-031 (ALL-OR-NOTHING per service per period; ABSENT with the
#           reason AND the count) · BR-LED-032 (the formula; a VOLUME ratio,
#           never a money ratio) · BR-LED-033 (same explicit unit both sides or
#           ABSENT by name) · BR-LED-030 (optional at capture) · BR-LED-035
#           (voided purchases leave every aggregate) · BR-REP-001 (every report
#           labels its basis) · BR-REP-002 (a report never recomputes money) ·
#           BR-REP-006 (the LIVE service list) · BR-REP-008 (state what could
#           not be attributed)
# Golden:   LE-12 — water 1,000,000 gal bought / 910,000 billed = **9.00%**;
#           electric 412,000 / 389,340 kWh = **5.50%**; the degraded month's
#           **−13.75%** which never prints
# ───────────────────────────────────────────────────────
"""The figure no accounting package can produce, and the reasons it refuses.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_020_tc3__one_cost_only_purchase_suppresses_the_figure_and_minus_13_75_never_prints`.
Producing 9.00% is arithmetic; REFUSING to produce −13.75% is the rule the
Product Owner ruled (OQ-190, 2026-08-12) and the reason BR-LED-031 exists —
*"nonsense a reader would try to explain rather than distrust"*.

⚠ **TWO OPEN QUESTIONS RIDE EVERY ASSERTION HERE.** The period basis of the
billed denominator is **OQ-202** (issue-basis reads 11.55% where service-period
reads 9.00% — a 2.55-point swing) and the purchase-unit vocabulary is
**OQ-201** (gas bought in MMBtu against gas billed in ccf). Both are asserted as
LABELS and REFUSALS, never as chosen answers.

WHAT RUNS WHERE. Everything here runs on SQLite and Postgres alike; the
DATABASE-level isolation proof for `supplier_invoices` lives in
`test_us_led_018_capture.py` under `requires_postgres`. The isolation case here
is the APP-layer half and needs no vendor guard, so it carries none — a
`requires_postgres` on a test that does not touch RLS would be a skip pretending
to be coverage.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.ledger import billing_seam, cost_capture, cost_reconciliation

from tests.cost_of_service_fixtures import (
    BILLED_ELECTRIC,
    BILLED_GAS,
    BILLED_WATER,
    ELECTRIC_PCT,
    ISSUE_BASIS_BILLED_WATER,
    ISSUE_BASIS_PCT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    LE11_WATER_COST,
    LSR_BILLED,
    LSR_PCT,
    SUPPRESSED_PCT,
    VOIDED_AT,
    WATER_PCT,
    WATER_PCT_AFTER_VOID,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.ledger_le_fixtures import make_accounts, service_id
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

ISSUED_AT = datetime(2026, 8, 3, 14, 0, tzinfo=dt_timezone.utc)
JUNE_START = date(2026, 6, 1)
JUNE_END = date(2026, 6, 30)


def bill_usage(tenant, account, *, service, quantity, unit, period, issued_at=ISSUED_AT):
    """One ISSUED bill carrying one usage line — the billed half of the ratio.

    Created through the ORM rather than a bill run on purpose: this file tests
    the LEDGER's reconciliation, and driving a full run would make a failure
    here indistinguishable from a failure in billing. The seam reads what a real
    run would leave — an issued invoice with a usage line carrying its quantity
    and unit — so the SHAPE is the real one.
    """
    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        service_date=period[1],
        period_start=period[0],
        period_end=period[1],
        status=billing_models.INVOICE_ISSUED,
        issued_at=issued_at,
        subtotal=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("0"),
        currency="USD",
    )
    billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        service_id=service_id(service),
        kind="usage",
        description=f"{service} usage",
        quantity=quantity,
        unit=unit,
        amount=Decimal("0"),
        period_start=period[0],
        period_end=period[1],
    )
    return invoice


def brazos_july(tenant, clerk, *, volumeless=(), skip=()):
    """LE-11's month captured, plus LE-12's billed volumes on issued bills."""
    admin = staff_actor(tenant, "system_admin", f"setup-rec-{tenant.subdomain}@brazos.test")
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    captured = capture_le11_month(clerk, volumeless=volumeless, skip=skip)
    accounts = make_accounts(admin, tenant, {}, service="water")
    account = accounts["ACC-1042"]
    bill_usage(
        tenant,
        account,
        service="water",
        quantity=BILLED_WATER,
        unit="gal",
        period=(JULY_START, JULY_END),
    )
    bill_usage(
        tenant,
        account,
        service="electric",
        quantity=BILLED_ELECTRIC,
        unit="kWh",
        period=(JULY_START, JULY_END),
    )
    # Gas is billed in ccf against a purchase in MMBtu — LE-12's unit mismatch.
    bill_usage(
        tenant,
        account,
        service="gas",
        quantity=BILLED_GAS,
        unit="ccf",
        period=(JULY_START, JULY_END),
    )
    return captured, admin, accounts


def rows_by_service(result):
    return {row["service"]: row for row in result["rows"]}


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 / TC-2 — the ruled figures
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc1__water_reads_nine_percent_with_both_volumes_and_its_cost(
    brazos, marcus
):
    """*"Brazos Bend, July 2026, Water: all five purchases carry volume —
    400,000 + 250,000 + 100,000 + 50,000 + 200,000 = 1,000,000 gal; billed
    910,000 gal → **9.00% unaccounted for**; both volumes shown beside the
    percentage; bought cost $3,100.00 in its own column; basis labeled."*

    The PO's own figure (OQ-188/OQ-190), computable only here because only this
    product holds the billed volumes.
    """
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        result = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
    water = rows_by_service(result)["water"]

    assert water["bought_volume"] == Decimal("1000000")
    assert water["bought_unit"] == "gal"
    assert water["billed_volume"] == BILLED_WATER
    assert water["billed_unit"] == "gal"
    assert water["unaccounted_for_pct"] == WATER_PCT
    assert water["bought_cost"] == LE11_WATER_COST
    assert water["currency"] == "USD"
    assert water["purchase_count"] == 5 and water["purchases_missing_volume"] == 0

    # BR-REP-001 — no unlabelled figure anywhere.
    assert result["basis"] == billing_seam.BASIS_SERVICE_PERIOD
    # ⚠ **THE LABEL IS THE CODE (`DEF-LED-6669`).** `basis_label` composed an
    # English paragraph here and `formula` spelled this module's own field
    # names; both reached a clerk, and B14 rules 32 and 33 refuse both. The
    # figure is still labelled — by `basis`, rendered from the catalogue.
    assert "basis_label" not in result
    assert "formula" not in result
    # Every row states the basis too, so a row copied into a CSV keeps it.
    assert water["basis"] == billing_seam.BASIS_SERVICE_PERIOD


def test_us_led_020_tc2__electric_reads_five_point_five_and_is_independent_of_water(
    brazos, marcus
):
    """*"Same period, Electric: bought 412,000 kWh / billed 389,340 kWh →
    **5.50%**; the row is independent of Water's — the figure is per service,
    never a blended one."*"""
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        rows = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )
    assert rows["electric"]["unaccounted_for_pct"] == ELECTRIC_PCT
    assert rows["electric"]["bought_volume"] == Decimal("412000")
    assert rows["electric"]["bought_unit"] == "kWh"
    assert rows["water"]["unaccounted_for_pct"] == WATER_PCT
    # And the two are genuinely different numbers computed from different
    # denominators — a blended figure would make them equal.
    assert rows["electric"]["unaccounted_for_pct"] != rows["water"]["unaccounted_for_pct"]


def test_us_led_020_tc1__the_total_cost_is_51902_50_and_no_money_is_recomputed(
    brazos, marcus
):
    """BR-REP-002 — the cost column is a Σ of STORED amounts, not a re-derived
    figure, and it foots to LE-11's $51,902.50."""
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        result = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
    assert result["total_bought_cost"] == LE11_REGISTER_TOTAL
    assert sum(
        (row["bought_cost"] for row in result["rows"]), Decimal("0")
    ) == LE11_REGISTER_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — THE RULE. −13.75% never reaches anything.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc3__one_cost_only_purchase_suppresses_the_figure_and_minus_13_75_never_prints(
    brazos, marcus
):
    """*"RS-2607-0208 is captured cost-only ($620.00, no volume); the other four
    water purchases total 800,000 gal; billed is still 910,000 → Water reads
    **ABSENT — 'no volume captured for 1 of 5 water purchases this period'**.
    The percentage is NOT shown. The partial denominator would have read
    **−13.75%** and that number never reaches a screen, a CSV, a PDF or an API
    payload."*

    Both halves are asserted: the reason with its COUNT, and the ABSENCE of the
    number anywhere in the whole result — not merely in the cell it would have
    occupied.
    """
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus, volumeless=("RS-2607-0208",))
        result = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
    water = rows_by_service(result)["water"]

    assert water["unaccounted_for_pct"] is None
    assert water["reason"] == "no volume captured for 1 of 5 water purchases this period"
    assert cost_reconciliation.NO_VOLUME_FOR_SOME_PURCHASES in water["problems"]
    assert water["purchase_count"] == 5 and water["purchases_missing_volume"] == 1

    # The arithmetic the rule exists to hide, verified as arithmetic and then
    # asserted absent from every value the result carries.
    assert cost_reconciliation.unaccounted_for_pct(
        Decimal("800000"), BILLED_WATER
    ) == SUPPRESSED_PCT
    rendered = repr(result)
    assert "-13.75" not in rendered and "-0.1375" not in rendered

    # Electric is untouched — the rule is PER SERVICE PER PERIOD.
    assert rows_by_service(result)["electric"]["unaccounted_for_pct"] == ELECTRIC_PCT


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the case that must NOT suppress
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc4__om_and_infrastructure_suppress_no_services_figure(brazos, marcus):
    """*"The same period contains HPV-4471 (O&M, $1,845.50, no volume) and
    KMW-2026-118 (Infrastructure, $12,500.00, no volume) → Water still reads
    **9.00%** and Electric **5.50%**. They appear as cost-only rows with '—' in
    the percentage column and the reason 'no volume denominator for this
    category'."*

    Read literally, the decision-log sentence (*"a period containing any
    cost-only purchase"*) would suppress every service for every utility that
    ever buys a valve. BR-LED-031's per-service scope — from OQ-190 option (a),
    the one the PO answered — is what this asserts, and the tension is flagged
    on the rule rather than resolved here.
    """
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        rows = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )

    assert rows["water"]["unaccounted_for_pct"] == WATER_PCT
    assert rows["electric"]["unaccounted_for_pct"] == ELECTRIC_PCT

    for category, cost in (
        ("operations_maintenance", Decimal("1845.50")),
        ("infrastructure", Decimal("12500.00")),
    ):
        row = rows[category]
        assert row["is_cost_category"] is True
        assert row["bought_cost"] == cost
        assert row["unaccounted_for_pct"] is None
        assert cost_reconciliation.NO_VOLUME_DENOMINATOR in row["problems"]
        assert "no volume denominator" in row["reason"]
        # Never a blank cell — BR-REP-008.
        assert row["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the unit mismatch, and no conversion is invented (OQ-201)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc5__gas_bought_in_mmbtu_against_ccf_is_absent_by_name(brazos, marcus):
    """*"Gas bought 1,450 MMBtu; gas billed 18,900 ccf → **ABSENT —
    `purchase_unit_does_not_match_billed_unit` (MMBtu vs ccf)**, naming both
    units and citing OQ-201. No conversion is applied and no number is
    produced."*"""
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        gas = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )["gas"]

    assert gas["unaccounted_for_pct"] is None
    assert cost_reconciliation.UNIT_MISMATCH in gas["problems"]
    assert "MMBtu" in gas["reason"] and "ccf" in gas["reason"]
    assert "OQ-201" in gas["reason"]
    # Both volumes are still SHOWN — the reader can see what did not match.
    assert gas["bought_volume"] == Decimal("1450") and gas["bought_unit"] == "MMBtu"
    assert gas["billed_volume"] == BILLED_GAS and gas["billed_unit"] == "ccf"
    # And the cost is still reported: a suppressed ratio is not a suppressed row.
    assert gas["bought_cost"] == Decimal("6235.00")


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — a voided purchase leaves the denominator
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc7__a_voided_purchase_leaves_the_denominator_and_the_cost(
    brazos, marcus
):
    """*"A voided purchase (RS-2607-0192) is in the period → excluded from both
    the bought volume and the bought cost; the 'N of M' count reports the LIVE
    purchases, not the voided one."*

    LE-13's figures: water bought becomes **950,000 gal / $2,945.00** and the
    percentage becomes `(950,000 − 910,000) ÷ 950,000 = **4.21%**`. **A void
    moves the loss figure, and that is correct** — those 50,000 gallons were
    never bought.
    """
    with tenant_ctx(brazos):
        captured, _admin, _accounts = brazos_july(brazos, marcus)
        cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        water = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )["water"]

    assert water["bought_volume"] == Decimal("950000")
    assert water["bought_cost"] == Decimal("2945.00")
    assert water["unaccounted_for_pct"] == WATER_PCT_AFTER_VOID
    # The count reports the LIVE purchases — four, not five.
    assert water["purchase_count"] == 4 and water["purchases_missing_volume"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 / TC-9 — what is never served, and what is never zero
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc8__no_money_percentage_is_served_anywhere(brazos, marcus):
    """*"The reconciliation is asked for a MONEY percentage ('what margin did we
    make on water?') → not served — BR-LED-032 makes this a volume ratio. A
    margin figure needs revenue beside cost and the revenue basis question has
    not been asked for this surface; nothing is invented."*"""
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        water = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )["water"]
    assert set(water) & {"margin", "margin_pct", "revenue", "cost_pct"} == set()
    for forbidden in ("margin", "margin_by_service", "cost_ratio"):
        assert not hasattr(cost_reconciliation, forbidden)


def test_us_led_020_tc9__an_unreadable_billed_volume_is_absent_and_never_zero(
    brazos, marcus, monkeypatch
):
    """*"The period's billed volume cannot be read (the billing seam is
    unavailable) → the row reports **ABSENT with the reason**, exactly as it does
    for a missing volume — it never falls back to zero, and a zero billed volume
    would read as **100.00% unaccounted for** on a healthy month."*"""
    monkeypatch.setattr(billing_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)
        rows = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )

    water = rows["water"]
    assert water["unaccounted_for_pct"] is None
    assert billing_seam.BILLED_READ_UNAVAILABLE in water["problems"]
    assert "NOT treated as zero" in water["reason"]
    # The alarming figure a zero fallback would have produced, and its absence.
    assert cost_reconciliation.unaccounted_for_pct(
        Decimal("1000000"), Decimal("0")
    ) == Decimal("100.00")
    assert "100.00" not in repr(rows["water"]["unaccounted_for_pct"])
    # The BOUGHT side is still reported — half an answer beats none, provided
    # the missing half is named.
    assert water["bought_volume"] == Decimal("1000000")
    assert water["bought_cost"] == LE11_WATER_COST


def test_us_led_020__a_service_with_no_purchases_says_so_rather_than_reading_zero(
    brazos, marcus
):
    """Workbook V-8 — *"a period with NO purchases at all: every service reports
    ABSENT with reason 'no purchases captured', never 0.00%"*, because 0.00%
    claims a perfect month when the truth is that nobody bought anything."""
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus, skip=("BVPC-070026",))
        electric = rows_by_service(
            cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
        )["electric"]
    assert electric["unaccounted_for_pct"] is None
    assert cost_reconciliation.NO_PURCHASES in electric["problems"]
    assert "never bought" not in electric["reason"]  # it says what it means
    assert "no purchases captured" in electric["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# ⚠ OQ-202 — the basis is carried, labelled and NOT chosen
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020__the_period_basis_is_the_service_period_oq_202_ruled(
    brazos, marcus
):
    """**OQ-202 CLOSED 2026-08-16 — the SERVICE PERIOD.** PO verbatim: *"(b).
    You're measuring physical water loss, so match the physical period."*

    Bills issue in arrears: Brazos Bend issues July's bills on **3 August** for
    the July service period. Count the bills ISSUED in July and the denominator
    is JUNE's deliveries — **884,500 gal** — reading **11.55%** where the ruled
    basis reads **9.00%**: a **2.55-point** swing on the headline loss figure.

    Both bases are still computable, because an accountant asking a REVENUE
    question wants the issued one. What changed is that only one of them is the
    ruled answer, and the other now says so — the ruled result carries **no
    problem code at all**, because a report still apologising for a settled
    question reads as a number about to change.
    """
    with tenant_ctx(brazos):
        _captured, _admin, accounts = brazos_july(brazos, marcus)
        # June's water, billed on 3 JULY — the bill ISSUED inside the July
        # window under the other reading, carrying JUNE's deliveries.
        bill_usage(
            brazos,
            accounts["ACC-1051"],
            service="water",
            quantity=ISSUE_BASIS_BILLED_WATER,
            unit="gal",
            period=(JUNE_START, JUNE_END),
            issued_at=datetime(2026, 7, 3, 14, 0, tzinfo=dt_timezone.utc),
        )

        service_period = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
        issued = cost_reconciliation.reconciliation(
            period_start=JULY_START,
            period_end=JULY_END,
            basis=billing_seam.BASIS_ISSUED,
        )

    assert rows_by_service(service_period)["water"]["unaccounted_for_pct"] == WATER_PCT
    assert rows_by_service(issued)["water"]["billed_volume"] == ISSUE_BASIS_BILLED_WATER
    assert rows_by_service(issued)["water"]["unaccounted_for_pct"] == ISSUE_BASIS_PCT
    # The 2.55-point swing that makes this finance's call.
    assert ISSUE_BASIS_PCT - WATER_PCT == Decimal("2.55")

    # The RULED basis apologises for nothing and still labels itself.
    assert service_period["problems"] == ()
    assert "basis_label" not in service_period
    assert rows_by_service(service_period)["water"]["problems"] == ()

    # The other basis is served, and NAMES itself as not the ruled one — so a
    # figure lifted out of it into a spreadsheet cannot pass for the ruled one.
    # ⚠ **THE WARNING WAS NEVER `basis_label`'S JOB, WHICH IS WHY DELETING IT
    # COST NOTHING (`DEF-LED-6669`).** The code below is what the screen
    # renders, and all eleven catalogues carry a sentence for it.
    assert billing_seam.BASIS_NOT_THE_RULED_ONE in issued["problems"]
    assert "basis_label" not in issued
    assert (
        billing_seam.BASIS_NOT_THE_RULED_ONE
        in rows_by_service(issued)["water"]["problems"]
    )
    # The superseded code is emitted by nothing.
    for result in (service_period, issued):
        assert billing_seam.BASIS_NOT_RULED not in result["problems"]

    with pytest.raises(ValueError) as invented:
        billing_seam.billed_volume_by_service(
            period_start=JULY_START,
            period_end=JULY_END,
            services=("water",),
            basis="whichever_looks_better",
        )
    assert "OQ-202" in str(invented.value)


def test_us_led_020__the_ledger_read_model_still_does_not_import_billing():
    """`01-overview.md` v5.1's law: *"no import of billing, payments or customers
    exists in either file, and a test asserts that on the source"*.

    The billed VOLUME is not money, but the assertion is on the IMPORT — so the
    read goes through `apps/ledger/billing_seam.py`, which resolves billing's
    published callables BY NAME at call time. This asserts the law still holds on
    the source of the two read-model files AND on the reconciliation itself.
    """
    from pathlib import Path

    root = Path(cost_reconciliation.__file__).parent
    for name in ("reporting.py", "selectors.py", "cost_reconciliation.py"):
        source = (root / name).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(
                ("from apps.billing", "import apps.billing")
            ), f"{name} imports billing: {stripped}"
    # The seam itself does not import billing's MODELS either — it resolves
    # billing's published selectors by name (G6 rule 4).
    # The seam itself does not import billing's MODELS either — it resolves
    # billing's published selectors by name (G6 rule 4). Asserted on the PARSED
    # module rather than on its text: this file's own docstring names the import
    # it forbids, and a substring check would fail on the prose that explains
    # the rule.
    import ast

    tree = ast.parse((root / "billing_seam.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any(name.startswith("apps.billing") for name in imported), (
        f"billing_seam.py imports billing at module level: {sorted(imported)}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — isolation (app layer; the RLS proof is in test_us_led_018_capture.py)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_020_tc10__each_tenants_denominator_is_its_own(
    brazos, lonestar, marcus, erin
):
    """*"Lone Star Ridge opens its own July reconciliation → its own purchases
    against its own billed volumes; Brazos Bend's 1,000,000 gal is not in the
    denominator, the drill-back or the CSV."*

    Lone Star Ridge: 220,000 gal bought / 214,500 billed = **2.50%**.
    """
    with tenant_ctx(brazos):
        brazos_july(brazos, marcus)

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
        accounts = make_accounts(erin, lonestar, {}, service="water")
        bill_usage(
            lonestar,
            accounts["ACC-1042"],
            service="water",
            quantity=LSR_BILLED,
            unit="gal",
            period=(JULY_START, JULY_END),
        )
        theirs = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )

    water = rows_by_service(theirs)["water"]
    assert water["bought_volume"] == Decimal("220000")
    assert water["billed_volume"] == LSR_BILLED
    assert water["unaccounted_for_pct"] == LSR_PCT
    assert theirs["total_bought_cost"] == Decimal("842.00")
    # Brazos Bend's month is nowhere in it.
    assert "1000000" not in repr(theirs)
    assert rows_by_service(theirs).get("electric", {}).get("bought_volume") is None

    with tenant_ctx(brazos):
        ours = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )
    assert rows_by_service(ours)["water"]["unaccounted_for_pct"] == WATER_PCT


def test_us_led_020__the_reconciliation_refuses_outside_a_tenant_context():
    """CLAUDE.md rule 1's app half — refused before any query is built."""
    from core import errors

    with pytest.raises(errors.AuthError) as raised:
        cost_reconciliation.reconciliation(period_start=JULY_START, period_end=JULY_END)
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-020@d744841 (04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-020 §3 TC-1..TC-10 + §7 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-030..033 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-12/LE-13 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md steps 4-5 · 12-governance/01-open-questions.md OQ-201/202)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S74's route and download contract are OQ-204's) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — TC-3 is the guard this file exists for and it
#         was driven RED first: with the `purchases_missing_volume` branch
#         removed the degraded month produced `Decimal('-13.75')` and the test
#         failed `assert Decimal('-13.75') is None`. TC-5 was driven the same way
#         (gas produced a ratio of MMBtu to ccf before the unit check). Exact
#         failures in the lane report
# exceptions: the BILLED half is created through the ORM rather than through a
#         bill run — this file tests the LEDGER's reconciliation, and driving a
#         full run would make a failure here indistinguishable from a failure in
#         billing. The SHAPE is the real one (an issued invoice with a usage line
#         carrying quantity + unit), which is what the seam reads · TC-6's
#         DRILL-BACK is asserted only on the BOUGHT side, through
#         `cost_capture.register(service=…, period=…)`: the billed side needs an
#         invoice-line read billing does not publish, and a half-built drill-back
#         is worse than a named gap · the isolation case here is the APP-layer
#         half and carries no vendor guard, because it touches no RLS — the
#         DATABASE proof is in tests/test_us_led_018_capture.py under
#         `requires_postgres`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
