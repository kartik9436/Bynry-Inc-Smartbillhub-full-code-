# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-013 (back-bill: an arbitrary past period, each sub-period
#           priced on ITS OWN tariff version)   Screens: S30 · S31
# Rules:    BR-BIL-018 (per-sub-period pricing on the version in force THEN;
#           tenant window cap, default 12 months; theft EXEMPT; reason-coded +
#           approval-gated) · BR-RAT-007 (price on the SERVICE date) ·
#           BR-RAT-002 (tiers reset per period) · BR-BIL-004 (a draft is not
#           money) · BR-BIL-030 (the payload is locked at issue)
# Golden:   GT-26 (= WE-10, ❄️ FROZEN 2026-08-08) — v3 water 6 kgal = usage
#           **26.50** + base **8.00**; v4 = **28.10** + **8.50**.
# ───────────────────────────────────────────────────────
"""The rate-change back-bill, on real rows across four modules.

THE ONE ASSERTION THIS FILE EXISTS FOR is in `tc1`: a January group priced at
**26.50 + 8.00** and an April group priced at **28.10 + 8.50** on the same
bill. Those four numbers are WE-10's, frozen and finance-signed, and they are
the difference between billing history correctly and billing it at today's
rates — which is the same bill, plausible in every respect, ~7% too expensive,
and undetectable without exactly this test.

WHAT IS ASSERTED AND WHAT IS NOT. WE-10's month totals of 45.10 / 47.84 include
a SEWER line at 40% of the water usage-charge, and the rating engine does not
implement percent-of-service pricing (its own docstring says so, and B5 freezes
no figure for it that could be bound to). So the WATER half of every frozen
month is asserted exactly, and the sewer half is absent rather than
approximated: a hand-built tariff that happened to total 45.10 would be a green
test proving nothing about a signed number.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, models as billing_models, single
from apps.billing.exceptions import BillingConfigError  # noqa: F401 — cited in docstrings
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

# WE-10 verbatim: water 6 kgal/mo, tariff v3 until Mar 31, v4 from Apr 1.
V3_FROM = date(2025, 1, 1)  # earlier than WE-10's window so a 14-month span is priceable
V3_TO = date(2026, 3, 31)
V4_FROM = date(2026, 4, 1)
MONTHLY_2026 = [
    (date(2026, 1, 1), date(2026, 1, 31)),
    (date(2026, 2, 1), date(2026, 2, 28)),
    (date(2026, 3, 1), date(2026, 3, 31)),
    (date(2026, 4, 1), date(2026, 4, 30)),
    (date(2026, 5, 1), date(2026, 5, 31)),
    (date(2026, 6, 1), date(2026, 6, 30)),
]
#: WE-10's per-month WATER figures, per version. usage + base.
V3_USAGE = Decimal("26.50")  # 5 kgal x 4.00 + 1 kgal x 6.50
V3_BASE = Decimal("8.00")
V4_USAGE = Decimal("28.10")  # 5 kgal x 4.25 + 1 kgal x 6.85
V4_BASE = Decimal("8.50")
#: The engine emits ONE LINE PER TIER (B5 GT-2's shape), so WE-10's month
#: figure of 26.50 reaches the bill as 20.00 + 6.50. Both are stated so the
#: assertions bind to the frozen figure AND to what the customer reads.
V3_TIERS = [Decimal("20.00"), Decimal("6.50")]
V4_TIERS = [Decimal("21.25"), Decimal("6.85")]
assert sum(V3_TIERS) == V3_USAGE and sum(V4_TIERS) == V4_USAGE
REASON = "unbilled-service — meter never linked"  # US-BIL-013 §4 verbatim


def a_two_version_water_plan(tenant, *, v3_to=V3_TO, v4_from=V4_FROM):
    """WE-10's water tariff: v3 (4.00 / 6.50 / base 8.00) then v4 (4.25 / 6.85 / 8.50).

    Built through rating's real storage — an inclining-block version with two
    `rate_tiers` rows, exactly as a tenant's would be — so the split under test
    walks a real version timeline and not a fixture's idea of one.

    `v3_to`/`v4_from` move the reprice DAY without touching the prices, which is
    what the OQ-155 cases need: the same two frozen versions, repricing on a
    month edge (WE-10's Apr 1) or INSIDE a stated period (the PO's Feb 15).
    """
    # ⚠ AMENDED 2026-10-01 (billing red triage, `DEF-BIL-8326`) — THREE FACTS
    # THIS FIXTURE NEVER STATED, EACH NOW REQUIRED BY A RULING, AND NO FIGURE
    # MOVES. Every case built on it was refusing before the code under test ran:
    #
    #   (1) THE PLAN'S START. `make_plan` dates a plan from the versions it
    #       binds, and it ran BEFORE they existed, so the plan started on the
    #       fixture epoch 2026-01-01 and R1 refused the Nov-2025 theft months
    #       with "no plan version in force on 2025-11-01" (`BR-RAT-890`,
    #       `rating/0024`'s rule). The plan is now dated AFTER its versions, so
    #       it starts on v3's own 2025-01-01.
    #   (2) THE SIZE AXIS. Water is banded and the meter is the smallest
    #       ratified band, `W-58`; a schedule version stating no sizes prices no
    #       size (`DEF-2816`, the PO's chosen reading), so R3 refused with
    #       "connection size 'W-58' has no row". `state_size_axis` writes the
    #       platform's ratified ladder with no minimum — membership, no price.
    #   (3) THE BASE. `base_charge=` on the version is RETIRED and unread since
    #       `DEF-BIL-7170` (PO 2026-09-28: *"we will never take default value
    #       from plan $8.0 - that is retired"*). WE-10's base CHANGES between
    #       the versions — 8.00 then 8.50 — so ONE charge code cannot carry it.
    #       Each version NAMES its own base code (`base_charge_code`, CR-120,
    #       PO 2026-09-19: *"plan → rate schedule -> charge code → base
    #       charges"*), at the same frozen figure it always stated. The retired
    #       column is still written with the same figure so the fixture reads
    #       as WE-10 does; nothing prices from it.
    from tests.test_us_met_helpers import state_plan_start, state_size_axis
    from apps.tenancy import models as tenancy_models

    plan = make_plan(tenant, name="Water Only", services=("water",), dated=False)
    from apps.rating import selectors as rating_selectors

    water = tenancy_models.Service.objects.get(code="water")
    versions = {}
    for row in rating_selectors.plan_rate_schedules(plan.id):
        for label, base, t1, t2, start, end in (
            ("v3", "8.000000", "4.000000", "6.500000", V3_FROM, v3_to),
            ("v4", "8.500000", "4.250000", "6.850000", v4_from, None),
        ):
            base_code, _created = rating_models.Charge.objects.get_or_create(
                tenant=tenant,
                code=f"BASE-W-{label.upper()}",
                defaults=dict(
                    name=f"Water base ({label})",
                    charge_type="recurring",
                    service=water,
                    amount_rule="flat",
                    amount=Decimal(base),
                    is_base=True,
                ),
            )
            version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=row["tariff"],
                model="tiered",
                base_charge=Decimal(base),
                base_charge_code=base_code,
                uom="kgal",
                currency="USD",
                effective_from=start,
                effective_to=end,
            )
            state_size_axis(version, "water")
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=Decimal("5"),
                unit_price=Decimal(t1),
            )
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=2,
                from_qty=Decimal("5"),
                to_qty=None,
                unit_price=Decimal(t2),
            )
            versions[label] = version
    state_plan_start(plan)
    return plan, versions


def a_water_unit(actor, tenant, plan, *, asset_no="W-8001", label="Unit W", read_days=(), reads=()):
    """A metered water unit on the plan, with one 6 kgal read per stated month.

    `reads` is the OQ-155 half: explicit `(day, consumption)` pairs, because a
    period that reprices mid-way is read on the boundary day and on the period
    end, and the two halves need not have consumed the same amount.
    """
    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")
    unit = make_unit(actor, premises["id"], label=label, services=["water"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service="water", uom="kgal")
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    for index, day in enumerate(read_days):
        commit_read(
            actor,
            asset["id"],
            day=day.isoformat(),
            value=str(1000 + 6 * (index + 1)),
            prior_value=str(1000 + 6 * index),
            consumption="6.000000",
            unit="kgal",
        )
    register = Decimal(1000 + 6 * len(read_days))
    for day, consumption in reads:
        prior, register = register, register + Decimal(consumption)
        commit_read(
            actor,
            asset["id"],
            day=day.isoformat(),
            value=str(register),
            prior_value=str(prior),
            consumption=str(Decimal(consumption)),
            unit="kgal",
        )
    return unit


def a_bill_level_tax(tenant, plan, *, rate="0.082500", name="State of Texas"):
    """One percent tax on the PLAN (BR-BIL-069 / PO 2026-08-11: tax is per BILL).

    Seeded only where a test needs to prove that the tax pass runs ONCE over the
    whole back-bill. With no tax rule the tax total is 0.00 and "one pass or
    several" is unfalsifiable — the difference is a cent, and a cent that never
    shows up is a green test proving nothing.
    """
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=name, authority=name, level="state"
    )
    rating_models.Tax.objects.create(
        tenant=tenant, jurisdiction=jurisdiction, name=name, kind="percent", rate=Decimal(rate)
    )
    rating_models.PlanTaxRule.objects.create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )
    return jurisdiction


def a_run(tenant, cycle, key="2026-backbill"):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=MONTHLY_2026[0][0],
        period_end=MONTHLY_2026[-1][1],
        idempotency_key=key,
    )


def a_cycle(tenant, code="BB-A"):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields (metering 0021 dropped the date pair).
        start_day=MONTHLY_2026[0][0].day,
        days_to_complete=1,
    )


def _amounts(invoice, kind):
    return sorted(line.amount for line in invoice.lines.all() if line.kind == kind)  # noqa: E501


def test_us_bil_013_tc1__each_month_prices_on_its_own_tariff_version(brazos, dana):
    """WE-10: Jan–Mar on v3, Apr–Jun on v4 — ONE bill, six period-labeled groups.

    THE SILENT-OVERCHARGE CASE. If every group were gathered at the run date
    (or at the window's end, or at `date.today()`), all six months would price
    on v4 and the usage lines would read 28.10 six times instead of three. The
    bill would foot, the tax would be right, and the customer would be charged
    2026 prices for January water. That mutation was executed and this test
    goes RED on it — see the file's Lifecycle trailer.
    """
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, read_days=[end for _start, end in MONTHLY_2026])
        account = an_account(brazos, unit["id"], "A-13001")

        prepared = backbill.prepare_back_bill(
            account_id=account.id, sub_periods=MONTHLY_2026, reason_code=REASON
        )

        # Six groups, one per unbilled month, each labeled with its own window.
        assert prepared.group_count == 6
        assert [(g.period_start, g.period_end) for g in prepared.groups] == MONTHLY_2026
        # THE RULE: the version stamped per group is the one in force THEN.
        assert [g.tariff_version_ids["water"] for g in prepared.groups] == [
            str(versions["v3"].id),
            str(versions["v3"].id),
            str(versions["v3"].id),
            str(versions["v4"].id),
            str(versions["v4"].id),
            str(versions["v4"].id),
        ]
        # And the service date each group prices on is its OWN first day.
        assert [g.service_date for g in prepared.groups] == [s for s, _e in MONTHLY_2026]

        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

        # THE FROZEN FIGURES (WE-10, water half): three months at v3's prices
        # and three at v4's, on ONE bill. The multiset is decisive — a group
        # priced on the wrong version cannot produce these amounts, because
        # every one of v3's and v4's four figures differs.
        assert _amounts(invoice, "usage") == sorted(V3_TIERS * 3 + V4_TIERS * 3)
        assert _amounts(invoice, "base") == sorted([V3_BASE] * 3 + [V4_BASE] * 3)
        # …and they compose the frozen MONTH figures: 3 x 26.50 + 3 x 28.10.
        assert sum(_amounts(invoice, "usage")) == 3 * V3_USAGE + 3 * V4_USAGE
        assert sum(_amounts(invoice, "base")) == 3 * V3_BASE + 3 * V4_BASE
        assert invoice.bill_type == "backbill"


def test_us_bil_013_tc2__one_bill_one_taxable_base_with_the_groups_labelled(brazos, dana):
    """Totals + the period labels — TC-2's "one bill, groups labelled".

    The taxable subtotal is the SUM of the six groups' rounded lines, which is
    what B4.2 taxes ONCE. Six separate bills (or six tax passes) would be the
    other design and would move WE-10's frozen tax by a cent.
    """
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-8002", read_days=[e for _s, e in MONTHLY_2026]
        )
        account = an_account(brazos, unit["id"], "A-13002")
        prepared = backbill.prepare_back_bill(
            account_id=account.id, sub_periods=MONTHLY_2026, reason_code=REASON
        )
        invoice = backbill.calculate_back_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="BB-B"), key="bb-2")
        )

    expected = 3 * (V3_USAGE + V3_BASE) + 3 * (V4_USAGE + V4_BASE)  # 213.30
    assert invoice.subtotal == expected
    assert invoice.total == expected + invoice.tax_total
    # ONE invoice for the whole window, dated across it.
    assert (invoice.period_start, invoice.period_end) == (MONTHLY_2026[0][0], MONTHLY_2026[-1][1])
    assert billing_models.Invoice.objects.count() == 1

    # THE PERIOD LABELS. US-BIL-013 §5 asks for them per LINE; stage 6 still
    # writes ONE period on every line, so that half of the gap stands and the
    # evidence lives in the payload BR-BIL-030 locks at issue — asserted here so
    # the gap is visible rather than merely described.
    #
    # ⚠ THE OTHER HALF CLOSED ON 2026-08-19 (DEF-276), and this file is where it
    # shows. Until then `rating_seam.RatedLine` carried no version id and
    # `invoice_lines.tariff_version_id` was NULL on every line ever issued, so
    # this group record was the ONLY place a 2033 reprint could learn which
    # prices applied to which month. The lines now carry it themselves — see the
    # inverted assertion at the end of this test. The payload record is kept
    # because it also carries the group WINDOW and the estimator (OQ-191), which
    # `invoice_lines` still cannot express.
    groups = invoice.bill_payload["back_bill"]["groups"]
    assert [(g["period_start"], g["period_end"]) for g in groups] == [
        (s.isoformat(), e.isoformat()) for s, e in MONTHLY_2026
    ]
    assert [g["tariff_version_ids"]["water"] for g in groups][:3] == [str(versions["v3"].id)] * 3
    assert [g["tariff_version_ids"]["water"] for g in groups][3:] == [str(versions["v4"].id)] * 3
    assert invoice.bill_payload["back_bill"]["reason_code"] == REASON
    # ── INVERTED 2026-10-01, NOT DELETED (`DEF-BIL-8561`, `53416f25e`) ──────
    # This read *"the remaining line-level gap, asserted as it IS, not as §5
    # wants it: every line still carries the WHOLE window rather than its
    # group's month"* and pinned `{(Jan 1, Jun 30)}`. It pinned the gap so that
    # closing it would be deliberate, and it was: `DEF-BIL-8561` (2026-10-01)
    # makes a catch-up price each month in its own engine call and store each
    # line with ITS month — US-BIL-013 §5's ask. The strongest form now is
    # WHICH month carries WHICH version: Jan–Mar on v3, Apr–Jun on v4.
    priced_months: dict = {}
    for line in invoice.lines.all():
        assert MONTHLY_2026[0][0] <= line.period_start <= line.period_end <= MONTHLY_2026[-1][1]
        if line.kind in ("usage", "base"):
            priced_months.setdefault((line.period_start, line.period_end), set()).add(
                str(line.tariff_version_id)
            )
    assert sorted(priced_months) == MONTHLY_2026
    for month in MONTHLY_2026[:3]:
        assert priced_months[month] == {str(versions["v3"].id)}, month
    for month in MONTHLY_2026[3:]:
        assert priced_months[month] == {str(versions["v4"].id)}, month
    # ── INVERTED 2026-08-19 WITH DEF-276, NOT DELETED ────────────────────────
    # This assertion read `== {None}` and it was RIGHT: it pinned the defect as
    # it was, so that closing it would have to be a deliberate change rather
    # than a silent one. It has now been closed deliberately, and the strongest
    # form of the new assertion is not "not null" but WHICH VERSION — a back
    # bill spanning a rate change is the case a single version id per invoice
    # could never have expressed, and it is exactly what US-BIL-013 TC-6 asks to
    # be checkable. Six months, two water versions, one bill.
    water_versions = {
        str(line.tariff_version_id)
        for line in invoice.lines.all()
        if line.kind in ("usage", "base") and line.tariff_version_id is not None
    }
    assert water_versions == {str(versions["v3"].id), str(versions["v4"].id)}
    # And the payload's per-group record and the lines now agree — the same two
    # ids, reached by two independent routes.
    assert water_versions == {g["tariff_version_ids"]["water"] for g in groups}
    # A tax line names no rate schedule (BR-BIL-069 gives it a `tax_id` instead).
    assert {line.tariff_version_id for line in invoice.lines.filter(kind="tax")} <= {None}


def test_us_bil_013_tc3__prepare_writes_nothing_and_carries_the_approval_mode(brazos, dana):
    """TC-3: draft + preview first, approval before ISSUE — nothing money-bearing early.

    Two halves, and only one of them is this lane's. The half that IS: a
    prepare pass writes no invoice, no line and no run row, so a clerk can look
    at a six-month impact preview without committing anything. The half that is
    NOT: the System-Admin gate itself (BR-BIL-014 / US-BIL-017) exists nowhere
    in this codebase, so this asserts the approval MODE the tenant configured
    and states plainly that nothing enforces it — a test that pretended
    otherwise would be the "comment claiming a guarantee" law 1 names.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-8003", read_days=[e for _s, e in MONTHLY_2026]
        )
        account = an_account(brazos, unit["id"], "A-13003")

        prepared = backbill.prepare_back_bill(
            account_id=account.id, sub_periods=MONTHLY_2026, reason_code=REASON
        )

        assert billing_models.Invoice.objects.count() == 0
        assert billing_models.InvoiceLine.objects.count() == 0
        assert prepared.approval_mode == "all"  # BR-BIL-014 v1, OQ-072 CLOSED
        assert prepared.cap_months == 12  # BR-BIL-018 seeded default, OQ-071


def test_us_bil_013_tc4__a_span_beyond_the_tenant_cap_is_refused_by_name(brazos, dana):
    """TC-4 (negative): 14 months, no theft → refused, and the message cites the setting."""
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8004")
        account = an_account(brazos, unit["id"], "A-13004")
        fourteen = [
            (date(2025, 1, 1), date(2025, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
        assert backbill.months_spanned(date(2025, 1, 1), date(2026, 2, 28)) == 14

        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(
                account_id=account.id, sub_periods=fourteen, reason_code=REASON
            )

    assert raised.value.reason == backbill.BACKBILL_OVER_CAP
    assert "14 months" in str(raised.value)
    assert "back_bill_cap_months" in str(raised.value)  # names the setting, TC-4


def test_us_bil_013_tc5__the_same_span_flagged_theft_is_allowed(brazos, dana):
    """TC-5: theft cases are EXEMPT from the cap (OQ-071) — and only from the cap."""
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(brazos)
        # DEF-BIL-8326 (2026-10-01): the meter is READ in both months. Never
        # read, it has no multiplier since R3 + R4 (e998f92b1, BR-MET-056: "an
        # absent factor is NOT 1"), so prepare refused before the cap question
        # this case asks. Its subject is the theft exemption, not the reads.
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-8005", read_days=[date(2025, 1, 31), date(2026, 2, 28)]
        )
        account = an_account(brazos, unit["id"], "A-13005")
        fourteen = [
            (date(2025, 1, 1), date(2025, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]

        prepared = backbill.prepare_back_bill(
            account_id=account.id,
            sub_periods=fourteen,
            reason_code="theft-restated",
            theft=True,
        )

        assert prepared.theft is True
        assert prepared.group_count == 2
        # Both months are inside v3's window, so both price on v3 — a theft
        # case does not escape BR-RAT-007 either.
        assert {g.tariff_version_ids["water"] for g in prepared.groups} == {str(versions["v3"].id)}
        # Exempt from the CAP, not from the reason code or the approval mode.
        assert prepared.reason_code == "theft-restated"
        assert prepared.approval_mode == "all"


def test_us_bil_013_tc6__a_group_that_straddles_a_version_boundary_is_refused(brazos, dana):
    """TC-6 (negative): the guard that would catch a broken split.

    Two things are proved. First, the version timeline is found exactly — the
    only boundary in Jan–Jun 2026 is **Apr 1**, discovered by bisection through
    rating's own `pricing_inputs` and not by reading rating's storage. Second,
    a group asserted across that boundary REFUSES rather than pricing six
    months at one version: this is the guard that fires if a future change to
    the splitting ever misses a boundary.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8006")
        an_account(brazos, unit["id"], "A-13006")
        from apps.rating import selectors as rating_selectors

        tariffs = rating_selectors.plan_rate_schedules(plan.id)

        assert backbill.version_boundaries(
            tariffs[0]["tariff"], period_start=date(2026, 1, 1), period_end=date(2026, 6, 30)
        ) == (V4_FROM,)

        with pytest.raises(Exception) as raised:
            backbill._assert_one_version_per_group(tariffs, date(2026, 1, 1), date(2026, 6, 30))

    assert raised.value.reason == backbill.BACKBILL_SPLIT_BROKEN
    assert "changes tariff version inside the group" in str(raised.value)


def test_us_bil_013_tc6b__a_boundary_inside_a_stated_period_splits_by_days(brazos, dana):
    """OQ-155 CLOSED — the PO's ruling of 2026-08-12, verbatim: *"Split by days"*.

    THE PO'S OWN WORKED EXAMPLE, and it is asserted here figure for figure. A
    February back-bill group of 6 kgal on WE-10's water tariff, which reprices
    on **Feb 15** — v3 (T1 $4.00 / T2 $6.50 / base $8.00) for the first 14 days
    and v4 (4.25 / 6.85 / 8.50) for the last 14 — with 3 kgal read in each half.

    It is NOT priced whole on one version (that charges half of February at
    prices that had been superseded, or at prices that did not yet exist), and
    it is NOT refused. It splits into two DAY-WEIGHTED segments of 14/28, each
    priced at the version in force on ITS days, exactly as B4.3's calendar-day
    proration (❄️ FROZEN) already prorates a partial period:

        v3 half — base 8.00 x 14/28 = **4.00**; the 5 kgal first block scales
                  with the period to 2.5 kgal, so 2.5 x 4.00 = **10.00** and
                  0.5 x 6.50 = **3.25**.
        v4 half — base 8.50 x 14/28 = **4.25**; 2.5 x 4.25 = 10.625 -> **10.63**
                  and 0.5 x 6.85 = 3.425 -> **3.43**.
        group   — **35.56**.

    THE GROUP TOTAL IS 35.56 AND NOT THE 35.55 WRITTEN INTO OQ-155's OPTION (a),
    and the difference is not a defect in either: BR-RAT-003 (B4.4, finance-
    signed) rounds PER LINE, half-up, so 10.625 and 3.425 each round up on their
    own line. The OQ's illustration summed the half's usage before rounding
    (10.625 + 3.425 = 14.05) where the engine emits one line per tier and rounds
    each (10.63 + 3.43 = 14.06). The ruled RULE is implemented; the one-cent
    difference is the signed rounding law and is REPORTED, never hand-adjusted.
    """
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(
            brazos, v3_to=date(2026, 2, 14), v4_from=date(2026, 2, 15)
        )
        unit = a_water_unit(
            dana,
            brazos,
            plan,
            asset_no="W-8007",
            reads=[(date(2026, 2, 14), "3.000000"), (date(2026, 2, 28), "3.000000")],
        )
        account = an_account(brazos, unit["id"], "A-13007")

        prepared = backbill.prepare_back_bill(
            account_id=account.id,
            sub_periods=[(date(2026, 2, 1), date(2026, 2, 28))],
            reason_code=REASON,
        )

        # ONE stated sub-period, TWO day-weighted segments.
        assert prepared.group_count == 2
        assert [(g.period_start, g.period_end) for g in prepared.groups] == [
            (date(2026, 2, 1), date(2026, 2, 14)),
            (date(2026, 2, 15), date(2026, 2, 28)),
        ]
        # Each segment prices on the version in force on ITS days…
        assert [g.tariff_version_ids["water"] for g in prepared.groups] == [
            str(versions["v3"].id),
            str(versions["v4"].id),
        ]
        assert [g.service_date for g in prepared.groups] == [
            date(2026, 2, 1),
            date(2026, 2, 15),
        ]
        # …and it is weighted by DAYS: 14 of the stated period's 28, both sides.
        assert [(g.days, g.cycle_days) for g in prepared.groups] == [(14, 28), (14, 28)]

        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

    # THE RULED FIGURES. A whole-period v3 pricing would read 20.00 / 6.50 /
    # 8.00 and a whole-period v4 pricing 21.25 / 6.85 / 8.50; neither can
    # produce this multiset, so the assertion is decisive about the split.
    assert _amounts(invoice, "base") == [Decimal("4.00"), Decimal("4.25")]
    assert _amounts(invoice, "usage") == [
        Decimal("3.25"),
        Decimal("3.43"),
        Decimal("10.00"),
        Decimal("10.63"),
    ]
    assert invoice.subtotal == Decimal("35.56")
    # ONE bill for the stated period, labelled with both segments (BR-BIL-030).
    assert (invoice.period_start, invoice.period_end) == (date(2026, 2, 1), date(2026, 2, 28))
    groups = invoice.bill_payload["back_bill"]["groups"]
    assert [(g["days"], g["cycle_days"]) for g in groups] == [(14, 28), (14, 28)]


def test_us_bil_013_tc6c__unequal_segments_still_tax_the_bill_exactly_once(brazos, dana):
    """The OTHER half of OQ-155: segments of UNEQUAL length, taxed as ONE bill.

    The PO's February example splits 14/14 and both halves share one proration
    factor. Nothing guarantees that. A single Jan 1 – Jun 30 sub-period across
    WE-10's real Apr 1 reprice splits **90/181** and **91/181** — two different
    factors on one bill — which is the case OQ-155's engineering half said could
    not be expressed, because `price_bill` takes ONE `BillingPeriod` per call.

    Priced by days, with 6 kgal read in each segment:

        v3 90/181 — base 8.00 x 90/181 = **3.98**; first block 5 x 90/181 =
                    2.4862 kgal at 4.00 = **9.94**; 3.5138 kgal at 6.50 = **22.84**
        v4 91/181 — base 8.50 x 91/181 = **4.27**; 2.5138 kgal at 4.25 = **10.68**;
                    3.4862 kgal at 6.85 = **23.88**
        subtotal  — **75.59**

    THE ASSERTION THAT MATTERS IS THE TAX. B4.2 taxes Σ(rounded taxable lines)
    ONCE for the whole bill: 8.25% x 75.59 = 6.2362 -> **6.24**. Taxing each
    segment separately and summing gives 8.25% x 36.76 -> 3.03 plus 8.25% x
    38.83 -> 3.20 = **6.23**. One cent, on every back-bill that crosses a
    reprice, forever — which is the same cent WE-10's frozen 26.36 turns on.
    """
    with tenant_ctx(brazos):
        plan, versions = a_two_version_water_plan(brazos)
        a_bill_level_tax(brazos, plan)
        unit = a_water_unit(
            dana,
            brazos,
            plan,
            asset_no="W-8013",
            reads=[(date(2026, 3, 31), "6.000000"), (date(2026, 6, 30), "6.000000")],
        )
        account = an_account(brazos, unit["id"], "A-13013")

        prepared = backbill.prepare_back_bill(
            account_id=account.id,
            sub_periods=[(date(2026, 1, 1), date(2026, 6, 30))],
            reason_code=REASON,
        )

        assert [(g.period_start, g.period_end) for g in prepared.groups] == [
            (date(2026, 1, 1), date(2026, 3, 31)),
            (V4_FROM, date(2026, 6, 30)),
        ]
        assert [(g.days, g.cycle_days) for g in prepared.groups] == [(90, 181), (91, 181)]
        assert [g.tariff_version_ids["water"] for g in prepared.groups] == [
            str(versions["v3"].id),
            str(versions["v4"].id),
        ]

        invoice = backbill.calculate_back_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="BB-D"), key="bb-4")
        )

    assert _amounts(invoice, "base") == [Decimal("3.98"), Decimal("4.27")]
    assert _amounts(invoice, "usage") == [
        Decimal("9.94"),
        Decimal("10.68"),
        Decimal("22.84"),
        Decimal("23.88"),
    ]
    assert invoice.subtotal == Decimal("75.59")
    # ONE tax pass over the whole bill — not one per proration factor.
    assert invoice.tax_total == Decimal("6.24")
    assert invoice.tax_total != Decimal("6.23")
    assert invoice.total == Decimal("81.83")
    assert billing_models.Invoice.objects.count() == 1


def test_us_bil_013_tc6d__a_segment_with_no_read_is_day_weighted_and_marked_estimated(brazos, dana):
    """OQ-191 CLOSED — PO 2026-08-12, verbatim: *"B is correct; and if required
    give option C also as backup ; I will make B default and C as option for
    user"*.

    ⚠ **THIS CASE USED TO ASSERT A REFUSAL AND THE RULING SUPERSEDED IT.** The
    refusal was a faithful reading of *"split by days"* — that ruling prorates
    MONEY, and its example STATED 3 kgal per half rather than deriving them —
    and it would have made back-billing fail in exactly the case it exists for,
    because a six-month catch-up will almost never have a read on the reprice
    day. It survives as the LAST RESORT and is asserted by `tc6e`.

    Same February that reprices on Feb 15, read only on the 28th. Neither half
    has a read measuring ITS OWN days — the 28th's read measures the whole month
    — so the month's **6 kgal** is day-weighted **14/28 × 6 = 3 kgal each side**
    and **both segments are marked ESTIMATED**, because they are.

    THE MONEY IS `tc6b`'s TO THE CENT (**35.56**), and that is the point: the
    ruling decides where the 3 kgal comes FROM, never what it costs. What
    differs between the two bills is one word on the customer's document, and
    that word is asserted in
    `tests/test_po_20260812_backbill_segment_estimate.py`.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(
            brazos, v3_to=date(2026, 2, 14), v4_from=date(2026, 2, 15)
        )
        unit = a_water_unit(
            dana, brazos, plan, asset_no="W-8014", reads=[(date(2026, 2, 28), "6.000000")]
        )
        account = an_account(brazos, unit["id"], "A-13014")
        prepared = backbill.prepare_back_bill(
            account_id=account.id,
            sub_periods=[(date(2026, 2, 1), date(2026, 2, 28))],
            reason_code=REASON,
        )

        assert prepared.group_count == 2
        assert prepared.estimate_source == backbill.ESTIMATE_DAY_WEIGHTED
        assert prepared.estimated_segment_count == 2
        # A QUANTITY, and it carries its unit (CLAUDE.md rule 3).
        assert [(e.quantity, e.unit) for e in prepared.estimates] == [
            (Decimal("3.000000"), "kgal"),
            (Decimal("3.000000"), "kgal"),
        ]

        invoice = backbill.calculate_back_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, code="BB-E"), key="bb-5")
        )

    assert _amounts(invoice, "base") == [Decimal("4.00"), Decimal("4.25")]
    assert _amounts(invoice, "usage") == [
        Decimal("3.25"),
        Decimal("3.43"),
        Decimal("10.00"),
        Decimal("10.63"),
    ]
    assert invoice.subtotal == Decimal("35.56")
    # …and the bill SAYS so, per group, in the payload BR-BIL-030 locks at issue.
    groups = invoice.bill_payload["back_bill"]["groups"]
    assert [s["estimated"] for g in groups for s in g["services"]] == [True, True]


def test_us_bil_013_tc6e__the_refusal_survives_when_nothing_was_measured_at_all(brazos, dana):
    """The LAST RESORT, kept: *"refusal remains only where neither estimate can
    be produced"* (PO 2026-08-12, OQ-191).

    The same split February with nothing read in it (amended 2026-10-01: this
    said "the meter never read", which since R3 + R4 refuses earlier, on the
    absent multiplier — see the fixture comment below). There is no period
    quantity to day-weight and metering has nothing to work from, so the
    back-bill refuses at PREPARE — before a number is spent or a draft written —
    and the message names the SEGMENT rather than the month, for the reason the
    original refusal did: on a six-month catch-up, "no usable read for water"
    sends a clerk through six months of history.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(
            brazos, v3_to=date(2026, 2, 14), v4_from=date(2026, 2, 15)
        )
        # DEF-BIL-8326 (2026-10-01): read ONCE, in January, and never in the
        # split February. Never read at all, the meter has no multiplier since
        # R3 + R4 (e998f92b1, BR-MET-056: "an absent factor is NOT 1") and the
        # ruled path refused for THAT before the segment question this case
        # asks. February is still the period nothing measured.
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8015", read_days=[date(2026, 1, 10)])
        account = an_account(brazos, unit["id"], "A-13015")

        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(
                account_id=account.id,
                sub_periods=[(date(2026, 2, 1), date(2026, 2, 28))],
                reason_code=REASON,
            )

    assert raised.value.reason == backbill.BACKBILL_NO_ESTIMATE
    assert "2026-02-01..2026-02-14" in str(raised.value)
    assert billing_models.Invoice.objects.count() == 0


def test_us_bil_013_tc7__a_back_bill_never_crosses_a_tenant_boundary(brazos, dana, lonestar):
    """TC-7 (isolation): another tenant's account is ABSENT, not forbidden.

    The RLS-level proof belongs to the isolation suite (which needs Postgres);
    what is proved here is the queryset scoping every read in this path goes
    through — customers' `account_or_404`, which answers unknown, malformed and
    cross-tenant identically (HR-1) so no id can be probed.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8008")
        account = an_account(brazos, unit["id"], "A-13008")

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(
                account_id=account.id, sub_periods=MONTHLY_2026, reason_code=REASON
            )
    assert raised.value.__class__.__name__ == "NotFoundError"


def test_us_bil_013_tc8__a_back_bill_without_a_reason_code_is_refused(brazos, dana):
    """BR-BIL-018 "reason-coded". Charging for a past period is somebody's decision."""
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8009")
        account = an_account(brazos, unit["id"], "A-13009")

        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(
                account_id=account.id, sub_periods=MONTHLY_2026, reason_code="  "
            )
    assert raised.value.reason == backbill.BACKBILL_NO_REASON_CODE


def test_us_bil_013_tc9__sub_periods_are_required_and_never_defaulted(brazos, dana):
    """A whole-window single group would reset tiers ONCE — BR-RAT-002.

    Worked, on this fixture: 6 kgal x 6 months = 36 kgal in one period puts 31
    kgal in the top block (5 x 4.00 + 31 x 6.50 = **221.50**) where six monthly
    groups put 1 kgal there six times (6 x 26.50 = **159.00**). A default would
    have overcharged by 62.50 on a bill nobody would question.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8010")
        account = an_account(brazos, unit["id"], "A-13010")

        with pytest.raises(Exception) as raised:
            backbill.prepare_back_bill(account_id=account.id, sub_periods=[], reason_code=REASON)
    assert raised.value.reason == backbill.BACKBILL_NO_SUB_PERIODS


def test_us_bil_013_tc10__a_month_with_no_read_is_measured_by_the_next_read_and_marked(
    brazos, dana
):
    """⚠ AMENDED 2026-09-30 — `DEF-BIL-8324`, PO ruling *"A for catch-up estimate"*
    (BR-BIL-018). This asserted that a month with no read STOPPED the back-bill.

    The ruling prices a stretch nobody read instead, and the reading comes
    FIRST: April's read counts up from February's, so it measured March too and
    is shared by days (March 31/61, April 30/61), both marked ESTIMATED — the
    missing month is still named, on the bill, as an estimate. The refusal
    survives only where no read measured it and metering has no history
    (`test_def_bil_8324_catch_up_never_read_stretch.py`).
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        # Reads for every month EXCEPT March.
        days = [e for s, e in MONTHLY_2026 if s.month != 3]
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8011", read_days=days)
        account = an_account(brazos, unit["id"], "A-13011")
        prepared = backbill.prepare_back_bill(
            account_id=account.id, sub_periods=MONTHLY_2026, reason_code=REASON
        )

    estimated = {row.period_start for row in prepared.estimates}
    assert estimated == {date(2026, 3, 1), date(2026, 4, 1)}


def test_us_bil_013_tc11__the_single_account_flow_refuses_to_produce_a_back_bill(brazos, dana):
    """BR-BIL-018 says a back-bill goes "via the single-account flow" — with ITS rules.

    The failure this prevents is a clerk picking "Catch-up (missed cycles)" on
    S30's ordinary path: one period, one service date, one version, six months
    of history at today's prices.
    """
    with tenant_ctx(brazos):
        plan, _versions = a_two_version_water_plan(brazos)
        unit = a_water_unit(dana, brazos, plan, asset_no="W-8012")
        account = an_account(brazos, unit["id"], "A-13012")

        with pytest.raises(Exception) as raised:
            single.prepare_single_bill(
                account_id=account.id,
                period_start=MONTHLY_2026[0][0],
                period_end=MONTHLY_2026[-1][1],
                service_date=MONTHLY_2026[-1][1],
                bill_type="backbill",
            )
    assert "apps.billing.backbill.prepare_back_bill" in str(raised.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-013@f0a3c21 (EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md · B2 §2 + Addendum r10)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane)
# gates: ruff✔ black✔ · 14 passed
# RED PROOF EXECUTED 2026-08-15 for the OQ-155 ruling (PO 2026-08-12, "Split by
#         days"). tc6b was REWRITTEN from pinning the refusal to pinning the
#         ruling and tc6c was added; both were run against the unchanged
#         `backbill.py` FIRST and both went RED on the stub they were written to
#         remove. The run's own output, pasted:
#           `2 failed, 11 deselected in 17.53s`
#           FAILED tc6b — `NotImplementedError: OQ-155: a tariff version changes
#           on 2026-02-15, INSIDE the stated sub-period 2026-02-01 → 2026-02-28.
#           Neither the base charge nor the tier ladder for a split billing
#           period is ruled, and price_bill takes one period per call`
#           FAILED tc6c — the same refusal on `2026-04-01, INSIDE the stated
#           sub-period 2026-01-01 → 2026-06-30`.
#         Then implemented; `14 passed` (tc6d added with them: it pins that
#         the split day-weights the base and the ladder and never invents the
#         usage for a segment the meter did not cover). tc6c's tax assertion is the guard on the
#         one-tax-pass shape: 8.25% over the whole 75.59 bill is **6.24** where
#         taxing the 90/181 and 91/181 segments apart and summing is **6.23**.
# RED PROOF EXECUTED 2026-08-11 (the lines below are the run's own output,
#         pasted, not predicted). THE SILENT-OVERCHARGE MUTATION: in
#         `apps/billing/backbill.prepare_back_bill`, the per-group gather's
#         `service_date=start` was replaced with `service_date=period_end` —
#         every month priced at the window's LATEST version, which is what a
#         careless implementation does and what this story exists to prevent.
#         Result: `2 failed, 10 passed in 23.14s`.
#           FAILED tc1 — `assert _amounts(invoice, "usage") == sorted(V3_TIERS *
#           3 + V4_TIERS * 3)` / `At index 0 diff: Decimal('6.850000') !=
#           Decimal('6.50')` — January's top-tier kgal priced at APRIL's 6.85
#           instead of 6.50, on a bill that foots perfectly.
#           FAILED tc2 — `assert Decimal('219.60') == Decimal('213.30')`: the
#           whole six-month overcharge in one figure, **$6.30** on this
#           fixture's water alone (~3%), invisible without this assertion.
#         Patch reverted; `12 passed in 25.91s`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
