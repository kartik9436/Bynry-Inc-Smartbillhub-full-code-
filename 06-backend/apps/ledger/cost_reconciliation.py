# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-020 (bought vs billed on S74: the unaccounted-for
#           percentage, and the ABSENT-with-reason case that protects it —
#           TC-1 water 9.00%, TC-2 electric 5.50%, TC-3 the suppressed
#           −13.75%, TC-4 O&M/infrastructure suppress nothing, TC-5 the
#           MMBtu-vs-ccf unit mismatch, TC-7 the voided purchase, TC-9 the
#           unavailable billing read, TC-10 isolation)
#           Screens: S74 · S73
# Rules:    BR-LED-031 (ALL-OR-NOTHING per service per period; ABSENT with the
#           reason and the COUNT, never a percentage from a partial
#           denominator) · BR-LED-032 (the formula, and it is a VOLUME ratio,
#           never a money ratio) · BR-LED-033 (both sides in the SAME explicit
#           unit or ABSENT by name) · BR-LED-030 (the volume is optional at
#           capture — which is exactly why BR-LED-031 exists) · BR-LED-035
#           (voided purchases leave every aggregate) · BR-REP-001 (every report
#           labels its basis) · BR-REP-002 (a report is a read model, never a
#           side-maintained number) · BR-REP-006 (the service list is LIVE) ·
#           BR-REP-008 (a report states what it could not attribute)
# Tests:    06-backend/tests/test_us_led_020_reconciliation.py
# Impacts:  apps/ledger/billing_seam.py (the billed half, read by name) ·
#           apps/ledger/cost_capture.py (the bought half)
# ───────────────────────────────────────────────────────
"""**The figure no accounting package can produce** — and the reasons it refuses.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module computes the headline loss
number of the whole capability, and its most important behaviour is REFUSING to
compute it. AI-authored 2026-08-15 under the PO ruling of 2026-08-09. **A row in
12-governance/09-human-review-ledger.md is OWED** — that directory is the
Product Owner's to write, so the lane report names this file and the row.

════════════════════════════════════════════════════════════════════════════
THE FIGURE, IN THE PO'S OWN NUMBERS (OQ-190, 2026-08-12)
════════════════════════════════════════════════════════════════════════════
Bought **1,000,000 gallons**, billed **910,000** → **9.00% unaccounted for** —
leak, meter under-registration or theft, in one number, **computable only here
because only this product holds the billed volumes.**

BR-LED-032's formula, and it is a VOLUME ratio and never a money ratio:

    unaccounted_for_pct = (bought_volume − billed_volume) ÷ bought_volume

per service, per period, both sides in the SAME unit, displayed to 2dp with both
volumes beside it and its basis labelled.

    Water:    (1,000,000 − 910,000) ÷ 1,000,000 = 90,000 ÷ 1,000,000 = 0.0900 → 9.00%
    Electric: (412,000   − 389,340) ÷ 412,000   = 22,660 ÷ 412,000   = 0.0550 → 5.50%

════════════════════════════════════════════════════════════════════════════
THE RULE THAT MATTERS MOST IS THE ONE THAT PRODUCES NOTHING (BR-LED-031)
════════════════════════════════════════════════════════════════════════════
**The percentage is ALL-OR-NOTHING per service per period.** It is produced only
when EVERY live captured purchase of that service in that period carries a
volume. Otherwise the cell reads **ABSENT with its reason, naming the count** —
*"no volume captured for 1 of 5 water purchases this period"*.

Why, in one line of arithmetic: with RS-2607-0208 captured cost-only, water has
volume on four of five purchases totalling 800,000 gal against 910,000 billed —

    (800,000 − 910,000) ÷ 800,000 = −110,000 ÷ 800,000 = −0.1375 → **−13.75%**

a utility that appears to have delivered more water than it bought. In the
decision log's own words, *"nonsense a reader would try to explain rather than
distrust"*. **−13.75% never reaches a screen, a CSV, a PDF or an API payload**,
and `unaccounted_for_pct` is `None` on that row — not a negative number a caller
might format.

**Optional at capture, all-or-nothing at report.** The same posture the finance
screens already take for collection % and DSO, and what BR-REP-008 requires of a
report that cannot attribute something.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT ENTERS THE DENOMINATOR IS A FLAG ON THE CATEGORY — CR-060 TASK T7c
════════════════════════════════════════════════════════════════════════════
**Until 2026-09-01 this module asked `code in chart.COST_CATEGORIES` — "is this
not a service?" — to answer "does this have no volume denominator?".** Those two
questions had the same answer because the only two categories in existence were
O&M and Infrastructure.

**CR-060's C15 widened the vocabulary to sixteen** — payroll, insurance,
professional fees, postage, printing, meter reading, office, rent, vehicles and
fuel, and the utility's own property, franchise and payroll taxes — **and that
coupling became the defect waiting to happen.** A category added to the
vocabulary and forgotten in an excluded set would be read as a commodity, summed
into a denominator and sent to the billed-volume read. **That is how payroll
ends up inside a water ratio**, and it is not a smaller error than −13.75%; it
is the same error with a friendlier-looking number.

So every category declares `enters_recovery_denominator` in
`chart.COST_CATEGORY_SPECS`, **the field has no default so a new category cannot
be added without answering it**, and this module asks
`chart.enters_recovery_denominator(code)` in the two places that matter: which
codes reach `billing_seam.billed_volume_by_service`, and which rows return
ABSENT before any arithmetic happens. **The all-or-nothing rule below is NOT
re-implemented for this** — it already handles the absent case and continues to.

════════════════════════════════════════════════════════════════════════════
AND WHY ONE PIPE INVOICE DOES NOT POISON THE WATER FIGURE
════════════════════════════════════════════════════════════════════════════
CI-8 (Hillcrest Pipe & Valve, O&M, $1,845.50) and CI-9 (Katy Meter Works,
Infrastructure, $12,500.00) carry no volume and never will — pipe and meters are
not a commodity with a delivered quantity.

⚠ **Read at its most literal, the decision-log sentence** *"a period containing
any cost-only purchase"* **would suppress every service for every utility that
ever buys a valve.** OQ-190's option (a) — the one the PO actually answered —
reads *"an unaccounted-for percentage **per service**"*, so only purchases
carrying that service enter its denominator. BR-LED-031 carries that scope with
the tension FLAGGED rather than silently resolved, and this module implements
the per-service scope: O&M and Infrastructure appear as cost-only rows with no
percentage and the reason `no volume denominator for this category`, and
neither touches water's or electric's ratio.

════════════════════════════════════════════════════════════════════════════
⚠ TWO OPEN QUESTIONS RIDE EVERY ROW THIS MODULE PRODUCES
════════════════════════════════════════════════════════════════════════════
**OQ-201 — the purchase-side unit vocabulary, and whether a signed conversion
factor may be applied.** Gas is bought in **MMBtu** and billed in **ccf**; the
row reads **ABSENT — `purchase_unit_does_not_match_billed_unit`**, naming both
units, and **no conversion is invented**. Water (gal/gal) and electric
(kWh/kWh) compute today. OQ-004 closed this exact shape for the water register
(*"unit must match or conversion factor defined; mismatch → user message +
block"*), and applying that ruling here is a READING rather than a ruling, which
is why the question is asked instead of answered.

**OQ-202 — which bills form the billed denominator.** Issue-basis reads
**11.55%** where service-period reads **9.00%**, a 2.55-point swing on the
headline number caused by a basis nobody labelled. Every row carries
`billed_volume_period_basis_is_not_ruled` beside its explicit basis label, and
`apps/ledger/billing_seam.py` computes either basis and chooses neither.

**OQ-204 — where this view lives** (a Finance sub-view or a report beside
S59/S60) is OPEN too, which is why this module publishes a read and no route:
navigation and the download contract are what that question decides.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE NEVER DOES
════════════════════════════════════════════════════════════════════════════
  * **It never falls back to zero.** A billed volume of zero reads as **100.00%
    unaccounted for** on a healthy month — the most alarming possible way to be
    wrong (TC-9). Unanswerable is `None` with a reason, always.
  * **It never serves a MONEY percentage.** BR-LED-032 makes this a volume
    ratio; *"what margin did we make on water?"* needs revenue beside cost and
    the revenue-basis question has not been asked for this surface (TC-8).
  * **It never recomputes money** (BR-REP-002). The bought COST column is a Σ
    of stored amounts and nothing is re-derived or re-rounded — BR-LED-025
    keeps the ledger from being a second rounding site.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from apps.ledger import billing_seam, chart, dimension_seam, models, tenancy_seam
from core import errors
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: BR-LED-032 — *"displayed 2dp"*. The RATIO is computed at full precision and
#: only the PERCENTAGE is quantized, once, here. Rounding the ratio first and
#: multiplying would lose the second decimal the rule asks for.
PERCENT_PLACES = Decimal("0.01")

# ── the problem codes, named once so a screen, a CSV and a payload group on the
# ── same strings (BR-REP-008's shape, `apps/billing/delivery_seam` precedent) ─

#: BR-LED-031's headline case. Always accompanied by the COUNT — the rule says
#: *"naming the count"* and a bare "no volume captured" leaves a clerk hunting.
NO_VOLUME_FOR_SOME_PURCHASES = "no_volume_captured_for_some_purchases"

#: BR-LED-033 / OQ-201. Names BOTH units; converts nothing.
UNIT_MISMATCH = "purchase_unit_does_not_match_billed_unit"

#: Two purchases of one service in one period, bought in different units. The
#: bought side's own mismatch, suppressed for the same reason as the cross-side
#: one — 400,000 gal + 1,450 MMBtu is not a number.
PURCHASE_UNIT_IS_MIXED = "purchase_units_disagree_within_the_period"

#: BR-LED-031's per-service scope: a non-commodity category carries no volume
#: and enters no service's denominator. **Not a failure** — a stated absence,
#: and the reason TC-4 exists.
#:
#: ⚠ **AMENDED 2026-09-01 (CR-060 C15 · C9 · task T7c).** It read *"O&M and
#: Infrastructure"* because those were the only two categories that existed.
#: **There are sixteen now** — payroll, insurance, professional fees, postage,
#: rent, fuel and the utility's own taxes among them — and every one of them
#: answers this way. The CODE is unchanged so a screen, a CSV and a payload that
#: already group on this string keep working; only its scope widened.
NO_VOLUME_DENOMINATOR = "no_volume_denominator_for_this_category"

#: A service with purchases whose volumes are all present but sum to zero. The
#: ratio's denominator would be zero, so no percentage is produced and the
#: reason says which zero it was.
BOUGHT_VOLUME_IS_ZERO = "bought_volume_is_zero"

#: A service the tenant sells and bought nothing of this period. Workbook V-8:
#: *"every service reports ABSENT with reason 'no purchases captured', never
#: 0.00%"* — because 0.00% claims a perfect month and the truth is that nobody
#: bought anything.
NO_PURCHASES = "no_purchases_captured"


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is read without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _live_purchases(period_start: date, period_end: date) -> Any:
    """Live captured purchases whose PERIOD falls in the window.

    **`status=captured` is BR-LED-035 in one clause** — a voided purchase leaves
    every aggregate from the moment it is voided (TC-7). It stays in the
    REGISTER, visible with its reason; it is out of the denominator, out of the
    bought cost and out of the `N of M` count, which reports the LIVE purchases
    and not the voided one.

    Filtered on the stored PERIOD rather than on `invoice_date`, deliberately:
    the period is where the capture LANDED, which for an invoice dated into a
    closed month is not the month on the document (BR-LED-034's auto-forward).
    A reconciliation keyed on the invoice date would count a purchase in a month
    the register does not show it in.
    """
    return models.SupplierInvoice.objects.filter(
        tenant_id=_tenant_id(),
        status=models.SUPPLIER_INVOICE_CAPTURED,
        period_start__gte=period_start,
        period_end__lte=period_end,
    ).select_related("ledger_account")


def unaccounted_for_pct(bought: Decimal, billed: Decimal) -> Decimal:
    """BR-LED-032, and nothing else: `(bought − billed) ÷ bought`, 2dp.

    Worked, the ruled case: `(1000000 − 910000) / 1000000 = 0.09` → `9.00`.
    Worked, electric: `(412000 − 389340) / 412000 = 0.055` → `5.50`.

    Returned as a PERCENTAGE (9.00, not 0.09) so no caller has to remember to
    multiply — a caller that forgot would render a 9% loss as 0.09%.

    Half-up at two decimals, matching the money rule's rounding mode (B4 ❄️).
    The RATIO is not rounded first: quantizing 0.055 to two places and then
    multiplying gives 6.00%, not 5.50%.
    """
    if bought == ZERO:
        raise ZeroDivisionError(
            "the unaccounted-for ratio divides by the BOUGHT volume and it is zero — the caller "
            "must report `bought_volume_is_zero` rather than ask for a figure that does not "
            "exist. BR-LED-031: a reason, never a number nobody can read."
        )
    return ((bought - billed) / bought * Decimal("100")).quantize(
        PERCENT_PLACES, rounding=ROUND_HALF_UP
    )


def _bought_side(purchases: tuple[Any, ...]) -> dict[str, Any]:
    """One service's bought volume, cost, unit and the counts behind them."""
    total_cost = sum((row.amount for row in purchases), ZERO)
    with_volume = tuple(row for row in purchases if row.volume is not None)
    units = {row.volume_unit for row in with_volume if row.volume_unit}
    return {
        "purchase_count": len(purchases),
        "purchases_with_volume": len(with_volume),
        "purchases_missing_volume": len(purchases) - len(with_volume),
        "bought_cost": total_cost,
        "bought_volume": sum((row.volume for row in with_volume), ZERO) if with_volume else None,
        "bought_unit": next(iter(units)) if len(units) == 1 else None,
        "bought_units_disagree": len(units) > 1,
        "currency": (
            next(iter({row.currency for row in purchases}))
            if len({row.currency for row in purchases}) == 1
            else None
        ),
    }


#: CR-060 C9 / task T4 — the two grains this report is produced at.
#:
#: `service` is the original and is unchanged: one row per service, over the
#: whole tenant. `premises` is the sub-metering company's question — CR-060's
#: own words, *"for a sub-metering company that IS the product"* — and its rows
#: are at the **(building, service)** grain, which is BR-LED-031 as amended:
#: all-or-nothing per service per PREMISES per period.
GROUP_BY_SERVICE = "service"
GROUP_BY_PREMISES = "premises"
GROUP_BYS = (GROUP_BY_SERVICE, GROUP_BY_PREMISES)

#: ⚠ **THE BUILDING NOBODY NAMED, AND IT IS A ROW RATHER THAN A SILENCE.**
#: `supplier_invoices.premises_id` is nullable by rule (ledger 0011), so a
#: tenant-wide cost — payroll, insurance, the office rent — legitimately has no
#: building, and so does a commodity purchase a clerk simply did not key one on.
#: BR-REP-008 requires a report to STATE what it could not attribute, so those
#: purchases are gathered into one row of their own with their reason. Folding
#: them into a building would put money on a building that did not buy it;
#: dropping them would make the footer disagree with the register.
UNATTRIBUTED = None
NO_PREMISES_KEYED = "no_building_keyed_on_these_purchases"


def reconciliation(
    *,
    period_start: date,
    period_end: date,
    basis: str = billing_seam.BASIS_SERVICE_PERIOD,
) -> dict[str, Any]:
    """S74 — bought vs billed per service per period, or the reason it is absent.

    Brazos Bend, July 2026 (LE-12), reads exactly:

        Water          1,000,000 gal / $3,100.00   vs 910,000 gal   →  9.00%
        Electric         412,000 kWh / $28,222.00  vs 389,340 kWh   →  5.50%
        Gas                1,450 MMBtu / $6,235.00 vs 18,900 ccf    →  ABSENT (unit mismatch)
        O&M                        — / $1,845.50   —                →  ABSENT (no denominator)
        Infrastructure             — / $12,500.00  —                →  ABSENT (no denominator)
        Total cost                   $51,902.50

    Every row carries **both volumes**, its **cost**, its **basis label** and —
    when there is no percentage — the **reason with its count**. There is no
    blank cell anywhere in the result: BR-REP-008 requires a report to state
    what it could not attribute, and a blank is the one thing a reader will fill
    in for themselves.
    """
    purchases = tuple(_live_purchases(period_start, period_end))
    by_category: dict[str, list[Any]] = {}
    for row in purchases:
        by_category.setdefault(row.service, []).append(row)

    # BR-REP-006 — the LIVE service list, never a hardcoded one. A service the
    # tenant sells but bought nothing of still gets a row (workbook V-8's
    # "no purchases captured" rather than a silent absence), and a category with
    # purchases but no live service row still gets one too: a purchase that
    # exists must appear somewhere, even if the tenant has since switched the
    # service off.
    services = tuple(tenancy_seam.enabled_service_codes())
    # ⚠ **AMENDED 2026-09-01 (task T7c). A NON-COMMODITY CATEGORY GETS A ROW
    # ONLY WHEN IT HAS PURCHASES IN THE WINDOW.**
    #
    # This unioned `chart.COST_CATEGORIES` unconditionally, so O&M and
    # Infrastructure always appeared. That was two rows. **Union sixteen and
    # Brazos Bend's July goes from 7 rows to 21, fourteen of them "no volume
    # denominator" for categories nobody bought anything in** — on the one
    # screen whose whole value is that the worst figure is the first row.
    # (Measured, not estimated: the July fixture sells five services, so the
    # served table is 5 + O&M + Infrastructure = 7. LE-12's illustration lists
    # FIVE because it prints only the rows with content — a different count,
    # and worth naming so the next reader does not take one for the other.)
    #
    # A SERVICE the tenant sells still always gets a row (workbook V-8's *"no
    # purchases captured"*, never 0.00%), because the absence of a water
    # purchase is information about water. The absence of a payroll run is not.
    # July still reads exactly seven rows: CI-8 and CI-9 are real purchases, so
    # O&M and Infrastructure are both present, and the footer is $51,902.50.
    ordered = sorted(set(services) | set(by_category))

    billed = billing_seam.billed_volume_by_service(
        period_start=period_start,
        period_end=period_end,
        # ⚠ **THE FLAG, NOT A MEMBERSHIP TEST (task T7c).** This read `code not
        # in chart.COST_CATEGORIES` — *"is this a service"* asked to answer
        # *"does this have a billed volume"*. The two had one answer while two
        # categories existed. **`chart.enters_recovery_denominator` asks the
        # second question directly**, so payroll and insurance cannot reach the
        # billed read however the vocabulary grows.
        services=tuple(code for code in ordered if chart.enters_recovery_denominator(code)),
        basis=basis,
    )

    rows: list[dict[str, Any]] = []
    for code in ordered:
        rows.append(
            _row_for(
                code,
                tuple(by_category.get(code, ())),
                billed.get(code),
                basis=basis,
            )
        )

    total_cost = sum((row.amount for row in purchases), ZERO)
    currencies = {row.currency for row in purchases}
    return {
        "period": [period_start.isoformat(), period_end.isoformat()],
        "rows": tuple(rows),
        "total_bought_cost": total_cost,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        # BR-REP-001 — no unlabelled figure anywhere, and the label is
        # MANDATORY rather than decorative.
        #
        # ⚠ **THE LABEL IS THE CODE NOW, AND THE 90-WORD PARAGRAPH IS GONE
        # (`DEF-LED-6669`, 2026-09-25).** `basis_label` composed an English
        # paragraph here — `OQ-202`, a PO ruling quoted verbatim, a 2.55-point
        # swing worked out in prose — and the Bought-vs-billed screen printed
        # it above the table. Three rules refused it: B14 rule 33 (rationale is
        # ZERO words on screen, and REMOVED rather than shortened), rule 32 (no
        # rule id in clerk-facing copy) and **TD-16 / B8** (the server may not
        # send language to a product with eleven catalogues).
        #
        # **BR-REP-001 is satisfied by `basis` itself.** The screen renders
        # `finance.cost.basis.<code>` in the Finance blueprint's own drawn words
        # (p063: *Service period · Issued*), so the figure is still labelled and
        # the label is still mandatory — it is now three words instead of
        # ninety, and it is translated.
        #
        # **The "not the ruled basis" half was never this paragraph's job.**
        # `_basis_problem_tuple` below already publishes it as the CODE
        # `billed_volume_basis_is_not_the_ruled_service_period`, and all eleven
        # catalogues already carry a sentence for it. The paragraph was a second
        # statement of the same fact, in English, on the wire.
        #
        # `formula` went with it: `(bought_volume - billed_volume) /
        # bought_volume` is this module's own field names, and rule 32 forbids
        # an internal code reaching a clerk. BR-REP-009's numerator,
        # denominator and basis are each a served FIELD on every row — Bought,
        # Billed and `basis` — so the arithmetic is shown rather than spelled.
        "basis": basis,
        "problems": billing_seam._basis_problem_tuple(basis),
    }


def by_premises(
    *,
    period_start: date,
    period_end: date,
    basis: str = billing_seam.BASIS_SERVICE_PERIOD,
) -> dict[str, Any]:
    """CR-060 C9 — bought vs billed PER BUILDING, worst first.

    **THE SCREEN A SUB-METERING COMPANY OPENS EVERY MONTH.** CR-060's own
    argument for it, and it is an argument about arithmetic rather than layout:
    bought-versus-billed *"is calculated per service, per period, across the
    whole tenant, and a sub-metering company runs forty buildings — blending a
    leaking building with a tight one produces an average that describes
    neither and points at nothing anyone can go and fix."*

    ════════════════════════════════════════════════════════════════════════
    THE GRAIN IS (BUILDING, SERVICE), AND THAT IS NOT A HALF-MEASURE
    ════════════════════════════════════════════════════════════════════════
    BR-LED-031 as amended by this task moves all-or-nothing from *per service
    per period* to *per service per PREMISES per period*, and the grain follows
    it exactly. **A single percentage per building is not computable and is not
    produced**, because BR-LED-032 is a VOLUME ratio: a building that buys
    water in gallons and gas in MMBtu has no one denominator, and adding the
    two is the failure BR-LED-033 already forbids one dimension over. So a
    building that buys two commodities gets two rows, and *"worst building
    first"* is *"worst (building, service) first"* — which puts the same
    leaking building at the top and never invents a number to rank it by.

    ════════════════════════════════════════════════════════════════════════
    ALL-OR-NOTHING APPLIES PER BUILDING, AND THAT IS THE POINT OF C9
    ════════════════════════════════════════════════════════════════════════
    C9's own proof: *"a building with no volume reports absent with its reason
    and does NOT poison the others"*. Under the tenant-wide read, ONE water
    purchase captured cost-only suppresses water for the WHOLE tenant — every
    building's figure gone because of one invoice at one of them. Here the
    suppression is bounded by the building it happened at, and the other
    thirty-nine still read. `_row_for` is the same function the service-grained
    report uses, so the rule is not re-implemented for this: it is the same
    all-or-nothing branch, handed a smaller set of purchases.

    ════════════════════════════════════════════════════════════════════════
    WORST FIRST, AND WHAT "WORST" MEANS WHEN THERE IS NO NUMBER
    ════════════════════════════════════════════════════════════════════════
    Rows that HAVE a percentage sort by it descending — the biggest loss is the
    first row, which is C9's *"ranked worst-first, so the leaking building is
    the FIRST ROW, not an average"*. Rows that have NO percentage cannot be
    ranked against ones that do, and are NOT sorted to the top as if they were
    the worst or to the bottom as if they were fine: they follow, in a stable
    order (building label, then service), each carrying its own reason. The
    unattributed bucket is last, because it is not a building.
    """
    purchases = tuple(_live_purchases(period_start, period_end))

    # Keyed on (premises_id, service). `UNATTRIBUTED` (None) is a real key —
    # see the constant's own note: a purchase with no building is a stated
    # absence, never a silent one.
    by_key: dict[tuple[Any, str], list[Any]] = {}
    for row in purchases:
        premises_id = str(row.premises_id) if row.premises_id else UNATTRIBUTED
        by_key.setdefault((premises_id, row.service), []).append(row)

    # BR-REP-006's spirit, one dimension over: the billed side is asked ONLY
    # about codes that can carry a denominator at all (task T7c's flag, not a
    # membership test), so payroll at a building never reaches the billed read.
    commodity_services = tuple(
        {service for (_premises, service) in by_key if chart.enters_recovery_denominator(service)}
    )
    billed = (
        billing_seam.billed_volume_by_service_and_premises(
            period_start=period_start,
            period_end=period_end,
            services=commodity_services,
            basis=basis,
        )
        if commodity_services
        else {}
    )

    labels = dimension_seam.premises_labels(
        {premises for (premises, _service) in by_key if premises is not UNATTRIBUTED}
    )

    rows: list[dict[str, Any]] = []
    for (premises_id, service), group in by_key.items():
        row = _row_for(
            service,
            tuple(group),
            billed.get((premises_id, service)) if premises_id is not UNATTRIBUTED else None,
            basis=basis,
        )
        row["premises_id"] = premises_id
        row["premises_label"] = (
            labels.get(premises_id) if premises_id is not UNATTRIBUTED else None
        )
        if premises_id is UNATTRIBUTED:
            # ⚠ Overwrites whatever `_row_for` concluded, deliberately: without
            # a building there is no per-building denominator to compare
            # against, so the honest answer is "nobody said where this went"
            # and NOT a percentage computed against the whole tenant's bills.
            # That number would look like a building's recovery and would be a
            # tenant-wide one wearing a building's row.
            row["unaccounted_for_pct"] = None
            row["billed_volume"] = None
            row["billed_unit"] = None
            row["problems"] = (NO_PREMISES_KEYED,)
            row["reason"] = (
                f"no building was keyed on {len(group)} {service} "
                f"purchase{'' if len(group) == 1 else 's'} this period, so this cost belongs to "
                "no building's recovery figure. A tenant-wide cost — payroll, insurance, rent — "
                "correctly has no building (BR-LED-029, as amended 2026-09-01); a commodity "
                "purchase that should have one is corrected by editing the row while the "
                "period is open (BR-LED-034)"
            )
        rows.append(row)

    def order(row: dict[str, Any]) -> tuple[Any, ...]:
        pct = row["unaccounted_for_pct"]
        unattributed = row["premises_id"] is UNATTRIBUTED
        return (
            1 if unattributed else 0,  # the bucket that is not a building, last
            0 if pct is not None else 1,  # ranked rows first — see the docstring
            -pct if pct is not None else ZERO,  # biggest loss at the top
            str(row["premises_label"] or row["premises_id"] or ""),
            row["service"],
        )

    rows.sort(key=order)

    total_cost = sum((row.amount for row in purchases), ZERO)
    currencies = {row.currency for row in purchases}
    return {
        "group_by": GROUP_BY_PREMISES,
        "period": [period_start.isoformat(), period_end.isoformat()],
        "rows": tuple(rows),
        "total_bought_cost": total_cost,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "basis": basis,
        "problems": billing_seam._basis_problem_tuple(basis),
    }


# ⚠ **`_basis_label` STOOD HERE UNTIL 2026-09-25 AND IS DELETED, NOT SHORTENED
# (`DEF-LED-6669`).** It returned one of two English paragraphs — 90 words and
# 60 — naming `OQ-202`, quoting the PO's ruling of 2026-08-16 verbatim and
# working a 2.55-point swing out in prose, and `CostOfServicePage` printed the
# result above the table. **Rationale is removed rather than rewritten** (B14
# rule 33), so there is no successor function: the basis is the served CODE and
# the screen names it from the catalogue in the blueprint's drawn words.
#
# Nothing was lost with it. The reasoning it carried is `OQ-202` in the open
# questions register and `BR-REP-001` in the ledger's business rules, which is
# where a reason belongs; the "not the ruled basis" warning is
# `_basis_problem_tuple`'s code and has been all along.

def _row_for(
    code: str,
    purchases: tuple[Any, ...],
    billed: billing_seam.BilledVolume | None,
    *,
    basis: str,
) -> dict[str, Any]:
    """One S74 row — the figure, or the reason there is none, never a blank."""
    bought = _bought_side(purchases)
    row: dict[str, Any] = {
        "service": code,
        "is_cost_category": code in chart.COST_CATEGORIES,
        # ⚠ Task T7c — SERVED, not inferred by the reader. A screen that decided
        # for itself which rows can carry a percentage would be a second
        # implementation of this rule sitting downstream of the first, which is
        # the mistake `issue._gl_account_for` and the posting seam already refuse
        # to make on the other side of the module.
        "enters_recovery_denominator": chart.enters_recovery_denominator(code),
        "bought_volume": bought["bought_volume"],
        "bought_unit": bought["bought_unit"],
        "bought_cost": bought["bought_cost"],
        "currency": bought["currency"],
        "purchase_count": bought["purchase_count"],
        "purchases_missing_volume": bought["purchases_missing_volume"],
        "purchases_with_volume": bought["purchases_with_volume"],
        "billed_volume": None,
        "billed_unit": None,
        "unaccounted_for_pct": None,
        "basis": basis,
        "problems": (),
        "reason": None,
    }

    # ── a NON-COMMODITY category: cost-only BY NATURE (BR-LED-031, TC-4) ────
    # It enters NO service's denominator, which is why one pipe invoice does not
    # suppress the water figure. This is a stated absence, not a failure.
    #
    # ⚠ **TASK T7c IS THIS BRANCH, AND TWO THINGS ABOUT IT CHANGED ON
    # 2026-09-01.** (1) The test is the CATEGORY'S OWN FLAG rather than *"is
    # this code not a service"*; those two questions had one answer while O&M
    # and Infrastructure were the only categories, and with payroll, insurance,
    # postage, rent, fuel and the utility's own taxes in the list they do not.
    # **Payroll and insurance have no delivered quantity and must NEVER enter
    # bought-versus-billed** — a payroll figure in a water denominator is not a
    # smaller error than the −13.75% the all-or-nothing rule exists to suppress,
    # it is the same error. (2) The reason is per GROUP: the single sentence
    # about pipe, valves and meters was true of Infrastructure and would have
    # been wrong on fourteen of sixteen rows.
    #
    # ⚠ **A VOLUME KEYED HERE IS INERT, NOT REFUSED.** BR-LED-030 is the PO's
    # own ruling that the volume is optional and that nothing refuses a
    # cost-only invoice, and an hours figure on contract services is meaningful
    # to the clerk who typed it. So it is stored, it enters no ratio, and the
    # reason SAYS SO rather than leaving a figure sitting there looking as
    # though it counted.
    if not chart.enters_recovery_denominator(code):
        spec = chart.COST_CATEGORY_BY_CODE.get(code)
        group = spec.group_label if spec is not None else "this category"
        row["problems"] = (NO_VOLUME_DENOMINATOR,)
        keyed = "" if bought["bought_volume"] is None else (
            f" A volume was keyed on {bought['purchases_with_volume']} of "
            f"{bought['purchase_count']} of these purchases; it is kept on the row and enters "
            "no ratio."
        )
        row["reason"] = (
            f"no volume denominator for this category — {group} is not a commodity with a "
            "delivered quantity, so this cost enters no service's unaccounted-for ratio "
            f"(BR-LED-031, as amended 2026-09-01).{keyed}"
        )
        return row

    # ── nothing bought at all (workbook V-8) ────────────────────────────────
    if not purchases:
        row["problems"] = (NO_PURCHASES,)
        row["reason"] = (
            f"no purchases captured for {code} in this period — reported rather than shown as "
            "0.00%, which would claim a perfect month when the truth is that nobody bought "
            "anything"
        )
        return row

    # ── BR-LED-031: ALL-OR-NOTHING. The rule this module exists for. ────────
    if bought["purchases_missing_volume"]:
        missing = bought["purchases_missing_volume"]
        total = bought["purchase_count"]
        row["problems"] = (NO_VOLUME_FOR_SOME_PURCHASES,)
        row["reason"] = (
            f"no volume captured for {missing} of {total} {code} purchases this period"
        )
        # ⚠ The partial denominator is NOT computed, not stored and not returned
        # under any key. For July's degraded water fixture it would read
        # −13.75% — a utility that delivered more than it bought — and
        # BR-LED-031 exists so that number never reaches a screen, a CSV, a PDF
        # or an API payload.
        return row

    if bought["bought_units_disagree"]:
        units = sorted({row_.volume_unit for row_ in purchases if row_.volume_unit})
        row["problems"] = (PURCHASE_UNIT_IS_MIXED,)
        row["reason"] = (
            f"this period's {code} purchases were captured in {' and '.join(units)} — two units "
            "cannot be added into one denominator, and whether a signed conversion factor may "
            "be applied is OQ-201, OPEN"
        )
        return row

    if bought["bought_volume"] == ZERO:
        row["problems"] = (BOUGHT_VOLUME_IS_ZERO,)
        row["reason"] = (
            f"every {code} purchase this period carries a volume and they sum to zero, so the "
            "ratio has no denominator (BR-LED-032 divides BY the bought volume)"
        )
        return row

    # ── the billed side ─────────────────────────────────────────────────────
    if billed is None or billed.quantity is None:
        problems = tuple(billed.problems) if billed is not None else (
            billing_seam.BILLED_READ_UNAVAILABLE,
            billing_seam.BASIS_NOT_RULED,
        )
        row["problems"] = problems
        row["reason"] = (
            f"the billed volume for {code} could not be read for this period, so no percentage "
            "is produced. It is NOT treated as zero: a zero billed volume would read as 100.00% "
            "unaccounted for on a healthy month (US-LED-020 TC-9)"
        )
        return row

    row["billed_volume"] = billed.quantity
    row["billed_unit"] = billed.unit

    # ── BR-LED-033 / OQ-201: same unit both sides, or ABSENT by name ────────
    if billed.unit is None or bought["bought_unit"] != billed.unit:
        row["problems"] = tuple(billed.problems) + (UNIT_MISMATCH,)
        row["reason"] = (
            f"{code} was bought in {bought['bought_unit']} and billed in "
            f"{billed.unit or 'no stated unit'} — a ratio of two different quantities is not a "
            "figure. No conversion is applied and none is invented: the per-service purchase-"
            "unit vocabulary, and whether a signed conversion factor may be used, is OQ-201 "
            "and is OPEN"
        )
        return row

    row["unaccounted_for_pct"] = unaccounted_for_pct(bought["bought_volume"], billed.quantity)
    row["problems"] = tuple(billed.problems)
    return row


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-020@d744841 (sha1[:7], newline-joined in order — the authorities this file was written from: 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-030..033 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-020 §1/§3/§7/§8 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-12/LE-13 · 04-docs/05-modules/09-ledger/03-field-map.md §"Cost-of-service capture" + D-13 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md steps 4-5 · 12-governance/01-open-questions.md OQ-201/202/204)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S74's route and its download contract are what OQ-204 decides) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row OWED and named in the lane report)
# gates: PROVED RED BEFORE GREEN — the all-or-nothing suppression is the guard
#         this file exists for and it was driven RED first: with the
#         `purchases_missing_volume` branch removed, July's degraded water
#         fixture produced `Decimal('-13.75')` and the test failed with
#         `assert Decimal('-13.75') is None`; restored, it reports "no volume
#         captured for 1 of 5 water purchases this period". The unit-mismatch
#         branch was driven the same way (gas produced -1203.45% from 1,450
#         MMBtu against 18,900 ccf before the check). See
#         tests/test_us_led_020_reconciliation.py
# exceptions: (1) **THE PERIOD BASIS IS OQ-202, OPEN.** Every result carries
#         `billed_volume_period_basis_is_not_ruled` and an explicit basis label
#         that says the basis is unruled; both bases are computable through
#         `billing_seam`. The default reproduces the PO's own ruled 9.00%, which
#         is a REPRODUCTION and not a resolution · (2) **THE UNIT VOCABULARY IS
#         OQ-201, OPEN.** Units are compared as exact strings and NOTHING is
#         converted; gas reports ABSENT by name · (3) **WHERE THIS VIEW LIVES IS
#         OQ-204, OPEN**, so this module publishes a read and no route: what
#         that question decides is navigation and the download contract ·
#         (4) BR-LED-031's PER-SERVICE scope is carried from OQ-190 option (a)
#         with the tension FLAGGED — the decision-log sentence read literally
#         (*"a period containing any cost-only purchase"*) would suppress every
#         service for every utility that ever buys a valve. The flag is
#         BR-LED-031's, not this file's invention · (5) NO CSV OR PDF is
#         produced here (IS-11): the download contract is OQ-204's, and a
#         streamed file whose filters and basis label are not settled is a
#         second contract to reconcile later · (6) NO DRILL-BACK helper is
#         published (TC-6): the bought side drills to `cost_capture.register`
#         filtered by service and period, which already exists, and the billed
#         side needs an invoice-line read billing does not publish — REPORTED
#         rather than half-built
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
