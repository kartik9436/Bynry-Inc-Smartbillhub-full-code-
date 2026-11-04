# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-013 (back-bill: an arbitrary past period, each sub-period
#           priced on ITS OWN tariff version — this file is the OQ-191 half of
#           it) · US-TEN-009 (the S71 Finance-controls card the choice lives on)
#           Screens: S30 · S31 · S71
# Rules:    BR-BIL-018 (back-bills; AMENDED 2026-08-12 — a split segment with no
#           read of its own gets a day-weighted usage estimate BY DEFAULT,
#           marked estimated, with the metering estimate as a tenant option) ·
#           BR-RAT-004 (split by days; TC-4c) · BR-MET-026 (estimates are
#           METERING's, under metering's own rules — option C) · BR-BIL-015 (the
#           refusal, which survives as the last resort) · BR-RAT-002 (tiers
#           scale with the prorated period) · BR-RAT-003 (rounding is PER LINE) ·
#           CLAUDE.md rule 3 (a quantity carries its unit)
# Golden:   GT-26 (= WE-10, ❄️ FROZEN 2026-08-08) — WE-10's water tariff is the
#           fixture, v3 (4.00 / 6.50 / base 8.00) and v4 (4.25 / 6.85 / 8.50).
# ───────────────────────────────────────────────────────
"""OQ-191 CLOSED — a split back-bill segment that nobody read.

**PO verbatim, 2026-08-12:** *"B is correct; and if required give option C also
as backup ; I will make B default and C as option for user"*.

**THE WORKED CASE, WHICH IS THE PO'S OWN.** A tariff changes **15 Feb**. The
period is **1–28 Feb**, **6 kgal**, and the meter was read on the 1st and the
28th and **not on the 15th**. Split by days (OQ-155) cuts it into 1–14 Feb and
15–28 Feb, and NEITHER half has a read that measures ITS OWN days: the 28th's
read measures the whole month. So each segment gets **14/28 × 6 = 3 kgal**, and
**both are marked ESTIMATED**, because they are.

**THIS SUPERSEDES WHAT SHIPPED HOURS EARLIER.** `apps/billing/backbill.py`
REFUSED such a segment by name (BR-BIL-015). That refusal was a faithful reading
of *"split by days"* — the ruling prorates MONEY, and the question's example
STATED 3 kgal per half rather than deriving them — and it would have made
back-billing fail in exactly the case it exists for, because a six-month
catch-up will almost never have a read on the reprice day. **The refusal is not
gone: it is the last resort**, for when neither estimate can be produced.

WHAT THIS FILE PROVES, and the third one is the one that matters:

  1. the choice is a **tenant setting** on S71, defaulting to day-weighted;
  2. the day weight produces a **QUANTITY carrying its unit** (rule 3), and
     WE-10's frozen February figures come out of it — **35.56**, the same group
     total two real reads produce, because the ruling changes where the 3 kgal
     comes FROM and not what it costs;
  3. **a CONSUMER sees the word.** The rendered bill says *"water: estimated
     read"*. A flag nothing reads is dead (hard-won law 2), so the assertion is
     on the document a customer holds, not on a field somebody set.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, documents, models as billing_models
from apps.metering import selectors as metering_selectors
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_bil_013_backbill import (
    REASON,
    _amounts,
    a_cycle,
    a_run,
    a_two_version_water_plan,
    a_water_unit,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FINANCE_CONTROLS = "finance-controls"
KEY = "back_bill_segment_estimate_source"

#: The PO's own example, verbatim: reprice on 15 Feb, period 1–28 Feb.
FEB = (date(2026, 2, 1), date(2026, 2, 28))
V3_TO = date(2026, 2, 14)
V4_FROM = date(2026, 2, 15)
SEGMENTS = [(date(2026, 2, 1), date(2026, 2, 14)), (date(2026, 2, 15), date(2026, 2, 28))]

#: 14/28 × 6 kgal. NUMERIC(18,6), and it carries its unit everywhere it goes.
HALF = Decimal("3.000000")
KGAL = "kgal"

#: WE-10's February group, day-weighted 14/28 each side — the figures OQ-155
#: already froze into `tc6b`, reached here from an ESTIMATE instead of from two
#: reads. That they are identical is the point: the ruling decides where the
#: 3 kgal comes FROM, never what it costs.
GROUP_TOTAL = Decimal("35.56")
BASES = [Decimal("4.00"), Decimal("4.25")]
USAGES = [Decimal("3.25"), Decimal("3.43"), Decimal("10.00"), Decimal("10.63")]


def prepared_february(brazos, dana, *, asset_no="W-8101", account_no="A-13101", reads=None):
    """The PO's case: WE-10's water tariff repricing on 15 Feb over a 1–28 Feb
    sub-period, with 6 kgal read on the 28th and nothing on the cut day.

    `reads` overrides that — `[]` for a meter nobody read at all, or a pair of
    real half-month reads for the negative case.
    """
    plan, _versions = a_two_version_water_plan(brazos, v3_to=V3_TO, v4_from=V4_FROM)
    unit = a_water_unit(
        dana,
        brazos,
        plan,
        asset_no=asset_no,
        reads=[(date(2026, 2, 28), "6.000000")] if reads is None else reads,
    )
    account = an_account(brazos, unit["id"], account_no)
    return backbill.prepare_back_bill(account_id=account.id, sub_periods=[FEB], reason_code=REASON)


# ═══════════════════════════════════════════════════════════════════════════
# 1 — THE CHOICE IS THE TENANT'S, AND ITS DEFAULT IS THE PO'S DEFAULT
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_estimate_source_is_a_tenant_setting_defaulting_to_day_weighted(brazos):
    """*"I will make B default and C as option for user"* — B is the seeded value.

    On S71 Finance controls, beside the two BR-BIL-018 parameters it belongs
    with (`back_bill_cap_months`, `back_bill_theft_exempt`). One mechanism, not
    a second one invented for this ruling.
    """
    with tenant_ctx(brazos):
        page = tenancy_selectors.settings_family(FINANCE_CONTROLS)
    assert page[KEY] == backbill.ESTIMATE_DAY_WEIGHTED == "day_weighted"


def test_po_20260812__the_two_sources_are_one_vocabulary_not_two(brazos):
    """Tenancy's choice list and billing's are THE SAME two strings.

    Mirrored rather than imported (tenancy owns no billing knowledge — the
    `ALLOCATION_CLASS_SEQUENCE` precedent), so a test asserts the copies are
    equal. A tenant saving `"metering"` against an engine that spells it
    something else would silently keep day-weighting while the screen said
    otherwise.
    """
    from apps.tenancy import settings_families

    assert tuple(settings_families.BACK_BILL_SEGMENT_ESTIMATE_SOURCES) == tuple(
        backbill.SEGMENT_ESTIMATE_SOURCES
    )


@pytest.mark.parametrize(
    "bad,why",
    [
        ("prorate", "a source no ruling names"),
        ("Day_Weighted", "the vocabulary is exact, not case-folded"),
        ("refuse", "refusing is the LAST RESORT, never a configurable policy"),
        (None, "unset is not a third behaviour"),
    ],
)
def test_po_20260812__a_source_outside_the_ruled_pair_is_refused(brazos, dana, bad, why):
    """Two options were ruled, B and C. A third value here would decide where a
    customer's billed usage comes from, which is the PO's decision and not a
    free-text field's."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: bad})
        assert (
            tenancy_selectors.settings_family(FINANCE_CONTROLS)[KEY]
            == backbill.ESTIMATE_DAY_WEIGHTED
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2 — THE DEFAULT (option B): day-weight the usage, and SAY it is an estimate
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_default_day_weights_the_period_into_each_segment(brazos, dana):
    """**THE PO'S OWN FIGURE: 14/28 × 6 kgal = 3 kgal EACH SIDE.**

    And it is a QUANTITY, so it carries `kgal` (CLAUDE.md rule 3). Nothing here
    assumes a unit: the unit is the one the period's own read arrived with.
    """
    with tenant_ctx(brazos):
        prepared = prepared_february(brazos, dana)

        assert prepared.estimate_source == backbill.ESTIMATE_DAY_WEIGHTED
        assert prepared.group_count == 2
        assert [(g.period_start, g.period_end) for g in prepared.groups] == SEGMENTS
        # BOTH halves are estimated — neither read measures its own 14 days.
        assert prepared.estimated_segment_count == 2
        assert [(e.period_start, e.period_end) for e in prepared.estimates] == SEGMENTS
        assert [e.quantity for e in prepared.estimates] == [HALF, HALF]
        assert [e.unit for e in prepared.estimates] == [KGAL, KGAL]
        assert [(e.days, e.cycle_days) for e in prepared.estimates] == [(14, 28), (14, 28)]
        assert {e.source for e in prepared.estimates} == {backbill.ESTIMATE_DAY_WEIGHTED}
        assert {e.service_code for e in prepared.estimates} == {"water"}


def test_po_20260812__the_estimated_segments_price_to_we10s_frozen_february(brazos, dana):
    """The ruling changes where the 3 kgal comes FROM, never what it costs.

    v3 half — base 8.00 × 14/28 = **4.00**; the 5 kgal first block scales with
              the period to 2.5 kgal, so 2.5 × 4.00 = **10.00** and 0.5 × 6.50 =
              **3.25**.
    v4 half — base **4.25**; 2.5 × 4.25 = 10.625 → **10.63** and 0.5 × 6.85 =
              3.425 → **3.43**.
    group   — **35.56**, which is `tc6b`'s figure to the cent, reached from an
              estimate instead of from two real reads.
    """
    with tenant_ctx(brazos):
        prepared = prepared_february(brazos, dana, asset_no="W-8102", account_no="A-13102")
        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

    assert _amounts(invoice, "base") == BASES
    assert _amounts(invoice, "usage") == USAGES
    assert invoice.subtotal == GROUP_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# 3 — THE ONE THAT MATTERS: A CONSUMER SEES THE WORD "ESTIMATED"
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_customers_own_bill_says_estimated_read(brazos, dana):
    """**THE WIRING TEST (hard-won law 2).**

    A flag nothing reads is dead. So this asserts the DOCUMENT — the thing the
    customer is handed — and not the field: `documents.render_invoice` prints
    *"estimated read"* beside the service where an ordinary bill prints
    *"read"*, and the rendered HTML body carries it.

    An estimate presented as a reading is the defect this whole product is
    careful about. If the flag ever stopped travelling from the day-weighting to
    the payload to the layout, this goes RED on the customer's own page rather
    than on an internal attribute.
    """
    with tenant_ctx(brazos):
        prepared = prepared_february(brazos, dana, asset_no="W-8103", account_no="A-13103")
        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

        document = documents.render_invoice(
            invoice, template_version=documents.BUILT_IN_LAYOUT_VERSION
        )

    states = {(field.label, field.value) for field in document.services}
    # ⚠ `("water", …)` UNTIL `DEF-2852` (2026-08-31). Stage 6 now freezes the
    # catalogue's display name into `bill_payload["services"]` — the stamp that
    # stopped the charge blocks being headed with a service's UUID — and the
    # band reads that name rather than the raw code (B14 rules 31 and 32).
    assert states == {("Water", "estimated read")}
    assert "estimated read" in document.body


def test_po_20260812__an_ordinary_read_still_prints_as_a_read(brazos, dana):
    """The negative half of the same assertion, without which the one above
    proves only that the layout can spell the word.

    The SAME February, the SAME split — but read on the 14th and the 28th, so
    each segment measures its own days. Nothing is estimated and the document
    says *"read"*.
    """
    with tenant_ctx(brazos):
        prepared = prepared_february(
            brazos,
            dana,
            asset_no="W-8104",
            account_no="A-13104",
            reads=[(date(2026, 2, 14), "3.000000"), (date(2026, 2, 28), "3.000000")],
        )
        assert prepared.estimated_segment_count == 0
        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

        document = documents.render_invoice(
            invoice, template_version=documents.BUILT_IN_LAYOUT_VERSION
        )

    assert {(f.label, f.value) for f in document.services} == {("Water", "read")}
    assert "estimated read" not in document.body
    # …and it prices to the same 35.56, which is what makes the two documents
    # comparable at all: the DIFFERENCE between them is the word, not the money.
    assert invoice.subtotal == GROUP_TOTAL


def test_po_20260812__the_run_report_names_every_estimated_segment(brazos, dana):
    """The other consumer: the run's report, before and after the draft exists.

    BEFORE — `PreparedBackBill` is the S30 impact preview a clerk approves from,
    and it states which segments will be estimated, with the figure, the unit
    and the day weight. A clerk who cannot see that on the preview approves a
    bill whose usage was derived without being told.

    AFTER — the same record is frozen into `bill_payload` (BR-BIL-030 locks it
    at issue), because a reprint in 2033 must be able to show WHICH of a
    back-bill's segments were estimated and on what weight.
    """
    with tenant_ctx(brazos):
        prepared = prepared_february(brazos, dana, asset_no="W-8105", account_no="A-13105")
        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

    back_bill = invoice.bill_payload["back_bill"]
    assert back_bill["estimate_source"] == backbill.ESTIMATE_DAY_WEIGHTED
    assert [
        (e["period_start"], e["period_end"], e["service_code"], e["quantity"], e["unit"])
        for e in back_bill["estimates"]
    ] == [
        ("2026-02-01", "2026-02-14", "water", "3.000000", KGAL),
        ("2026-02-15", "2026-02-28", "water", "3.000000", KGAL),
    ]
    # …and each GROUP's own service record says the quantity was estimated.
    for group in back_bill["groups"]:
        assert [(s["code"], s["estimated"], s["unit"]) for s in group["services"]] == [
            ("water", True, KGAL)
        ]


# ═══════════════════════════════════════════════════════════════════════════
# 4 — THE OPTION (C): ask METERING, under METERING's own rules (BR-MET-026)
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__option_c_asks_metering_and_bills_metering_s_answer(brazos, dana, monkeypatch):
    """*"give option C also as backup"* — and the seam is WIRED, not described.

    Estimates are metering's (BR-MET-026), which is why this is the better
    answer wherever it can be had. The contract billing asks for is a READ-ONLY
    question — `apps.metering.selectors.back_bill_segment_estimate` — and
    metering does not publish it today (see the next test). Here it is stood up,
    answering **4 kgal** where the day weight would answer 3, and the BILL moves.

    That is the proof that the seam is called at all: if billing quietly
    day-weighted regardless of the setting, stubbing this function would change
    nothing and every assertion below would fail.
    """
    calls: list[dict] = []

    # AMENDED 2026-10-01 (billing red triage): `asset_id` — the seam is asked
    # per METER since `b10541b9d` / `7d75bd7d2` (2026-09-30, one line set per
    # meter), and metering's published signature carries it.
    def a_metering_estimate(unit_id, *, service_code, period_start, period_end, asset_id=None):
        calls.append(
            {
                "unit_id": str(unit_id),
                "service_code": service_code,
                "period_start": period_start,
                "period_end": period_end,
            }
        )
        return {
            "estimated": True,
            "consumption": "4.000000",
            "unit": KGAL,
            "method": "trailing_3_avg",
            "consecutive_no": 1,
            "reason": None,
        }

    monkeypatch.setattr(
        metering_selectors,
        backbill.METERING_ESTIMATE_ATTRIBUTE,
        a_metering_estimate,
        raising=False,
    )
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            dana, FINANCE_CONTROLS, {KEY: backbill.ESTIMATE_METERING}
        )
        prepared = prepared_february(brazos, dana, asset_no="W-8106", account_no="A-13106")

        assert prepared.estimate_source == backbill.ESTIMATE_METERING
        assert [e.quantity for e in prepared.estimates] == [Decimal("4.000000")] * 2
        assert {e.source for e in prepared.estimates} == {backbill.ESTIMATE_METERING}
        assert {e.fallback_reason for e in prepared.estimates} == {None}
        # It was asked about EACH SEGMENT's own window, not about the month.
        assert [(c["period_start"], c["period_end"]) for c in calls] == SEGMENTS
        assert {c["service_code"] for c in calls} == {"water"}

        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

    # 4 kgal at 14/28: v3 2.5 × 4.00 = 10.00 and 1.5 × 6.50 = 9.75; v4 2.5 ×
    # 4.25 = 10.625 → 10.63 and 1.5 × 6.85 = 10.275 → 10.28; bases 4.00 + 4.25.
    assert _amounts(invoice, "usage") == [
        Decimal("9.75"),
        Decimal("10.00"),
        Decimal("10.28"),
        Decimal("10.63"),
    ]
    assert invoice.subtotal == Decimal("48.91")
    assert invoice.subtotal != GROUP_TOTAL  # decisive: metering's number, not ours


def test_po_20260812__option_c_falls_back_to_the_day_weight_and_names_the_seam(
    brazos, dana, monkeypatch
):
    """Metering publishes no such read TODAY, and this states that rather than faking it.

    The seam is documented and resolved at call time (the `settings_seam.py`
    idiom). While it is dark, option C produces the PO's ruled DEFAULT — the day
    weight — and RECORDS which estimator answered and why the other did not.
    That is not a silent substitution: `source` says `day_weighted`,
    `fallback_reason` names the missing contract, and both ride onto the bill's
    locked payload.

    Falling back rather than refusing is the ruling itself: refusal survives
    only where NEITHER estimate can be produced.

    ⚠ AMENDED 2026-10-01 (billing red triage): metering PUBLISHES the seam now
    (`7d75bd7d2`, 2026-09-30, `DEF-BIL-8324`, PO *"A for catch-up estimate"*),
    so "dark today" is no longer true of this deployment and the real seam
    answered `no_history`. The unpublished branch still exists and is still
    what a deployment without it meets, so the case removes the seam and asks
    the same question.
    """
    monkeypatch.delattr(metering_selectors, backbill.METERING_ESTIMATE_ATTRIBUTE)
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            dana, FINANCE_CONTROLS, {KEY: backbill.ESTIMATE_METERING}
        )
        prepared = prepared_february(brazos, dana, asset_no="W-8107", account_no="A-13107")

        assert prepared.estimate_source == backbill.ESTIMATE_METERING
        assert [e.quantity for e in prepared.estimates] == [HALF, HALF]
        assert {e.source for e in prepared.estimates} == {backbill.ESTIMATE_DAY_WEIGHTED}
        assert {e.fallback_reason for e in prepared.estimates} == {
            backbill.ESTIMATE_METERING_NOT_PUBLISHED
        }
        invoice = backbill.calculate_back_bill(prepared, bill_run=a_run(brazos, a_cycle(brazos)))

    assert invoice.subtotal == GROUP_TOTAL
    reported = invoice.bill_payload["back_bill"]["estimates"]
    assert {e["fallback_reason"] for e in reported} == {backbill.ESTIMATE_METERING_NOT_PUBLISHED}


def test_po_20260812__a_metering_refusal_is_carried_by_name_not_swallowed(
    brazos, dana, monkeypatch
):
    """Metering's own refusals (BR-MET-026/027/062) reach the report verbatim.

    "no history — field visit" is a fact a clerk must be able to read off the
    bill's record; a fallback that reported only "metering said no" would send
    them to a screen that does not exist.
    """

    # AMENDED 2026-10-01 (billing red triage): `asset_id` — the seam is asked
    # per METER since `b10541b9d` / `7d75bd7d2` (2026-09-30, one line set per
    # meter), and metering's published signature carries it.
    def no_history(unit_id, *, service_code, period_start, period_end, asset_id=None):
        return {"estimated": False, "consumption": None, "unit": None, "reason": "no_history"}

    monkeypatch.setattr(
        metering_selectors, backbill.METERING_ESTIMATE_ATTRIBUTE, no_history, raising=False
    )
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            dana, FINANCE_CONTROLS, {KEY: backbill.ESTIMATE_METERING}
        )
        prepared = prepared_february(brazos, dana, asset_no="W-8108", account_no="A-13108")

        assert [e.quantity for e in prepared.estimates] == [HALF, HALF]
        assert {e.source for e in prepared.estimates} == {backbill.ESTIMATE_DAY_WEIGHTED}
        assert {e.fallback_reason for e in prepared.estimates} == {"no_history"}


# ═══════════════════════════════════════════════════════════════════════════
# 5 — THE REFUSAL SURVIVES, as the behaviour when NEITHER can be produced
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__with_nothing_measured_at_all_the_segment_is_still_refused(brazos, dana):
    """*"refusal remains only where neither estimate can be produced"*.

    The same February split, with the meter never read. There is no period
    quantity to weight and metering has nothing to work from either, so this
    REFUSES by name and the message names the SEGMENT — not the month — for the
    reason the original refusal did: on a six-month catch-up, "no usable read"
    sends a clerk through six months of history.

    Nothing is billed. A back-bill that quietly charged $0.00 of water for a
    period nobody measured would be the worst of the three outcomes.
    """
    with tenant_ctx(brazos):
        with pytest.raises(Exception) as raised:
            # AMENDED 2026-10-01 (billing red triage, as `test_us_bil_013`
            # tc6e): read ONCE in January and never in February. A meter never
            # read at all has no multiplier since R3 + R4 (`e998f92b1`,
            # BR-MET-056) and refuses on THAT before the segment question.
            prepared_february(
                brazos,
                dana,
                asset_no="W-8109",
                account_no="A-13109",
                reads=[(date(2026, 1, 10), "6.000000")],
            )

    assert raised.value.reason == backbill.BACKBILL_NO_ESTIMATE
    assert "2026-02-01..2026-02-14" in str(raised.value)
    assert billing_models.Invoice.objects.count() == 0
