# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (Check: every check on every account) · US-BIL-038 TC-2
#           (price at the period end)
# Rules:    BR-BIL-1052 · BR-BIL-1053 · BR-BIL-1055 🔒 · BR-BIL-1040 · CLAUDE.md
#           rule 3 · decision log 2026-09-30 *"A PROBLEM NEVER STOPS THE
#           CHECKING"* (disputed reading is a tag; a unitless reading takes its
#           meter's recorded unit)
# Plan:     15-bulk-bill-run-build-plan.md B7, B8, B10–B13, B15, B16, B21 · T1
# Defects:  DEF-BIL-8205, 8206, 8207, 8209, 8210, 8211, 8214
# ───────────────────────────────────────────────────────
"""The bulk bill run's CHECK engine — one test per rule, written red first.

PO ruling 2026-09-30, verbatim: *"please start and ensure between step 1 and 2
for given account you runs allc heck sand dont stop at first problem"*.

The fixture is three metered accounts on one cycle (`A-00101`, `A-00106`,
`A-00102` — the story's TC-4 three), each with a committed June read, priced on
a published plan. Individual tests break one of them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import runs
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.rating import models as rating_models

from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
#: The typed bill date — the day AFTER the period ends, exactly the PO's shape
#: for BR-BIL-1055 (period ends Sep 30, bill date Oct 1), moved to June.
BILL_DATE = date(2026, 7, 1)


def a_cycle(tenant, code="06-BBR"):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        bill_day=1,
        due_days=21,
    )


def three_accounts(tenant, actor):
    """`A-00101`, `A-00106`, `A-00102` — ordered by account number as the run
    walks them, so `A-00106` is NOT the middle one alphabetically; the
    'middle' of the story is whichever the test breaks."""
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    accounts = {}
    for no, asset in (("A-00101", "M-9101"), ("A-00102", "M-9102"), ("A-00106", "M-9106")):
        unit = a_billed_unit(actor, tenant, cycle, plan, asset_no=asset, label=f"Unit {no}")
        accounts[no] = an_account(tenant, unit["id"], no)
    return cycle, plan, accounts


def prepare(cycle, **extra):
    return runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=BILL_DATE,
        **extra,
    )


#: Two warnings THIS FIXTURE carries on every account and that no test here is
#: about: its plan states no `is_base` charge code (so the base bills $0.00,
#: PO 2026-09-30) and customers holds no service agreements for it. Each is
#: asserted on its own in the B11 case.
FIXTURE_WARNINGS = frozenset({"base_not_set", "no_service_agreements"})


def codes_for(prepared, account, ignore=FIXTURE_WARNINGS):
    return sorted({f.code for f in prepared.findings.get(str(account.id), ())} - set(ignore))


def reads_without_unit(monkeypatch, unit_id, *, meter_unit=None):
    """A test double AT metering's published reads seam: the named unit's
    reading comes back with its quantity and NO unit (and, optionally, the
    meter's own recorded unit beside it — the ruling's fallback)."""
    real = metering_selectors.billing_reads_for_unit

    def double(unit, **kwargs):
        rows = real(unit, **kwargs)
        if str(unit) == str(unit_id):
            rows = [
                (
                    {**row, "unit": None, "meter_unit": meter_unit}
                    if row.get("consumption") is not None
                    else row
                )
                for row in rows
            ]
        return rows

    monkeypatch.setattr(metering_selectors, "billing_reads_for_unit", double)


# ══════════════════════════════════════════════════════════════════════════
# B7 · one account never stops the others (BR-BIL-1052, DEF-BIL-8206/8207)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-21
def test_b7__three_accounts_middle_broken__the_other_two_are_ready(brazos, dana, monkeypatch):
    """US-BIL-037 TC-4 / TC-2: a reading with no unit — and no unit on its
    meter either — blocks ONLY its account. Before 2026-09-30 it raised a plain
    `BillingRuleError` out of the prepare loop and no account was checked."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        reads_without_unit(monkeypatch, accounts["A-00102"].unit_id, meter_unit=None)
        prepared = prepare(cycle)

    assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00106"]
    assert [p.account_no for p in prepared.blocked] == ["A-00102"]
    assert prepared.blocked[0].reason == "reading_and_meter_have_no_unit"
    assert prepared.blocked[0].service_code == "electric"


# BULK-CHG-23 · BULK-CHG-44
def test_b3__a_unitless_reading_takes_its_meters_recorded_unit_with_a_warning(
    brazos, dana, monkeypatch
):
    """PO ruling 2026-09-30, item 2: the unit RECORDED ON THE METER is used and
    the clerk sees a warning — the account stays ready and prices in kWh."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        reads_without_unit(monkeypatch, accounts["A-00102"].unit_id, meter_unit="kWh")
        prepared = prepare(cycle)

    ready = {d.account_no: d for d in prepared.ready}
    assert sorted(ready) == ["A-00101", "A-00102", "A-00106"]
    assert ready["A-00102"].readings[0].consumption.unit == "kWh"
    # PO 2026-09-30 (rows 45–46): a DECISION with the meter unit SUGGESTED —
    # never applied to a bill until accepted (TC-A3 in test_bbr_check_store).
    assert codes_for(prepared, accounts["A-00102"]) == ["reading_has_no_unit"]
    [row] = [p for p in prepared.decisions if p.account_no == "A-00102"]
    assert row.reason == "reading_has_no_unit"
    assert codes_for(prepared, accounts["A-00101"]) == []


def test_b3__metering_publishes_the_meters_unit_only_when_the_read_has_none(brazos, dana):
    """The fallback's SOURCE is metering's own reads row (`meter_unit`), read
    from the asset's recorded unit of measure — never a default."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        unit_id = accounts["A-00102"].unit_id
        rows = metering_selectors.billing_reads_for_unit(
            unit_id, period_start=PERIOD_START, period_end=PERIOD_END
        )
        assert rows[0]["unit"] == "kWh"
        assert rows[0].get("meter_unit") is None
        # A LATER read stored with no unit (a committed read is immutable on
        # PostgreSQL — BR-MET-053's trigger — so it is a new row, not an edit).
        meter = (
            metering_models.MeterRead.objects.filter(
                tenant=brazos, asset__service_point__unit_id=unit_id
            )
            .first()
            .asset_id
        )
        commit_read(
            dana,
            meter,
            day="2026-06-29",
            value="14300",
            prior_value="14212",
            consumption="88.000000",
            unit="",
        )
        rows = metering_selectors.billing_reads_for_unit(
            unit_id, period_start=PERIOD_START, period_end=PERIOD_END
        )
    assert not rows[0]["unit"]
    assert rows[0]["meter_unit"] == "kWh"


# BULK-CHG-21 · BULK-CHG-24
def test_b7__an_unexpected_error_blocks_only_that_account_with_a_support_reference(
    brazos, dana, monkeypatch
):
    """US-BIL-037 TC-3: a plain RuntimeError for one account (test double)."""
    from apps.billing import gather

    real = gather.gather_account

    def double(**kwargs):
        if kwargs["account"].account_no == "A-00102":
            raise RuntimeError("boom")
        return real(**kwargs)

    monkeypatch.setattr(gather, "gather_account", double)
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle)

    assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00106"]
    [problem] = prepared.blocked
    assert problem.reason == "check_failed_unexpectedly"
    findings = prepared.findings[str(accounts["A-00102"].id)]
    [failed] = [f for f in findings if f.code == "check_failed_unexpectedly"]
    assert failed.support_ref and failed.support_ref.startswith("SBH-")
    assert "boom" not in problem.detail  # an internal message never reaches a clerk


# ══════════════════════════════════════════════════════════════════════════
# B8 · every problem on an account, in one pass (the PO's worked example)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-22 · BULK-CHG-44
def test_b8__no_plan_and_a_disputed_reading_and_a_bounced_payment_are_three_tags(
    brazos, dana, monkeypatch
):
    """US-BIL-037 TC-1 — *"an account with no plan AND a disputed reading AND a
    bounced payment shows all three, under three tags"*. The bounced payment
    has no stored source today (`bill_run_checks.UNAVAILABLE`), so it arrives
    through a test double AT the payments seam; the point proved is that the
    engine records every fact it is given and stops at none."""
    from apps.payments import bill_run_checks

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        premises = make_premises(dana, address_line="105 Bluestem Ln")
        unit = make_unit(dana, premises["id"], label="Unit 105", services=["electric"])
        asset = a_meter(dana, asset_no="M-9105", unit_id=unit["id"])
        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(
            cycle=cycle
        )
        commit_read(
            dana,
            asset["id"],
            day="2026-06-28",
            value="500",
            prior_value="400",
            consumption="100.000000",
            unit="kWh",
        )
        broken = an_account(brazos, unit["id"], "A-00105")

        def disputes(unit_id):
            if str(unit_id) != str(unit["id"]):
                return []
            return [
                {
                    "meter": "M-9105",
                    "usage_display": "100 kWh",
                    "read_at": "2026-06-28",
                    "dispute_reason": "customer says the meter is wrong",
                }
            ]

        monkeypatch.setattr(metering_selectors, "dispute_holds_for_unit", disputes, raising=False)
        real_facts = bill_run_checks.payment_facts_for_accounts

        def facts(account_ids, **kwargs):
            out = real_facts(account_ids, **kwargs)
            if str(broken.id) in {str(a) for a in account_ids}:
                out.setdefault(str(broken.id), []).append(
                    {"code": "bounced_payment_not_reversed", "params": {"payment_no": "PMT-1"}}
                )
            return out

        monkeypatch.setattr(bill_run_checks, "payment_facts_for_accounts", facts)
        prepared = prepare(cycle, payment_window=(BILL_DATE, date(2026, 7, 22)))

    assert codes_for(prepared, broken) == [
        "account_held_by_disputed_read",
        "bounced_payment_not_reversed",
        "unit_has_no_plan",
    ]
    assert "A-00105" in {p.account_no for p in prepared.blocked}
    # The legacy single-problem list still carries ONE row per blocked account.
    assert [p.account_no for p in prepared.blocked].count("A-00105") == 1
    assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00102", "A-00106"]


# BULK-CHG-22
def test_b8__each_service_is_checked_on_its_own(brazos, dana, monkeypatch):
    """A tariff refusal on ONE service no longer hides a refusal on another:
    the engine re-gathers without the refused service and records the next."""
    from apps.billing import gather

    real = gather._tariffs_for_plan

    def double(plan_id, unit_id, service_date, scope_services, **kwargs):
        wanted = scope_services if scope_services is not None else ("electric", "water")
        for code in ("electric", "water"):
            if code in wanted:
                raise gather.GatherProblem(
                    (
                        gather.GATHER_NO_TARIFF
                        if code == "electric"
                        else gather.GATHER_SIZE_UNRESOLVED
                    ),
                    f"{code} refused",
                    service_code=code,
                )
        return real(plan_id, unit_id, service_date, scope_services, **kwargs)

    monkeypatch.setattr(gather, "_tariffs_for_plan", double)
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle)

    for account in accounts.values():
        assert codes_for(prepared, account) == [
            "connection_size_unresolved_for_sized_schedule",
            "plan_has_no_tariff_for_service",
        ]


# ══════════════════════════════════════════════════════════════════════════
# B16 🔒 · the price version in force at the PERIOD END (BR-BIL-1055)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-29
def test_b16__the_bulk_run_prices_at_the_period_end_not_the_bill_date(brazos, dana):
    """US-BIL-038 TC-2 / DEF-BIL-8214. $3.25 until the day after the period
    ends, $3.50 from it; period ends Jun 30, bill date Jul 1 → **$3.25**. The
    bill date is still the run's document date (`service_date`)."""
    from apps.billing import selectors as billing_selectors
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos, price="3.250000")
        # The $3.25 version ends the day the period ends (`effective_to` is
        # INCLUSIVE); the $3.50 version starts the next day — the bill date.
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(effective_to=PERIOD_END)
        for row in rating_selectors.plan_rate_schedules(plan.id):
            version = rating_models.TariffVersion.objects.create(
                tenant=brazos,
                tariff=row["tariff"],
                model="flat",
                base_charge=Decimal("18.500000"),
                uom="kWh",
                currency="USD",
                effective_from=BILL_DATE,
            )
            rating_models.RateTier.objects.create(
                tenant=brazos,
                tariff_version=version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=Decimal("3.500000"),
            )
            from tests.test_us_met_helpers import state_size_axis

            state_size_axis(version, row["service_code"])
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-9201", label="Unit 201")
        an_account(brazos, unit["id"], "A-00201")
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=BILL_DATE,
            label="June 2026 · BBR",
        )
        prepared = billing_selectors.prepared_for(run)

    assert [(p.reason, p.detail) for p in prepared.blocked] == []
    [data] = prepared.ready
    assert data.tariffs[0].unit_price == Decimal("3.250000")
    assert prepared.service_date == BILL_DATE  # the document date is unchanged
    assert prepared.price_date == PERIOD_END


# ══════════════════════════════════════════════════════════════════════════
# B12 · Payments & balances — the facts with a stored source
# ══════════════════════════════════════════════════════════════════════════
def test_b12__a_payment_posted_after_the_period_ended_is_a_decision(brazos, dana):
    """US-BIL-037 TC-10: `$120.00` posted the day after the period ends and on
    the bill date → *Paid after cut-off*, a decision; the account stays ready."""
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=accounts["A-00106"],
            amount=Decimal("120.000000"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc),
        )
        payment_models.Payment.objects.create(  # inside the period — no finding
            tenant=brazos,
            account=accounts["A-00101"],
            amount=Decimal("50.000000"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 6, 20, 15, 0, tzinfo=timezone.utc),
        )
        prepared = prepare(cycle, payment_window=(BILL_DATE, date(2026, 7, 22)))

    assert codes_for(prepared, accounts["A-00106"]) == ["paid_after_cutoff"]
    # Inside the period: never *paid after cut-off*. Allocated to no bill it is
    # a credit balance, which is never *unmatched payment* (PO option B).
    assert codes_for(prepared, accounts["A-00101"]) == []
    assert "A-00106" in {d.account_no for d in prepared.ready}
    [row] = [d for d in prepared.decisions if d.account_no == "A-00106"]
    assert row.reason == "paid_after_cutoff"


def test_b12__in_collections_and_deposit_not_paid_are_warnings(brazos, dana):
    from apps.payments.collections_models import AccountCollectionState

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        AccountCollectionState.objects.create(
            tenant=brazos, account=accounts["A-00101"], tier="friendly"
        )
        a = accounts["A-00102"]
        type(a).objects.filter(pk=a.pk).update(
            deposit_assessed=Decimal("150.0000"), deposit_on_file=Decimal("0")
        )
        prepared = prepare(cycle, payment_window=(BILL_DATE, date(2026, 7, 22)))

    assert codes_for(prepared, accounts["A-00101"]) == ["in_collections"]
    assert codes_for(prepared, accounts["A-00102"]) == ["deposit_not_paid"]
    assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00102", "A-00106"]


def test_b12__a_fact_with_no_source_is_declared_absent_not_counted():
    from apps.payments import bill_run_checks

    absent = {row["code"] for row in bill_run_checks.UNAVAILABLE}
    # DEF-BIL-8240/8241 (2026-09-30): unmatched payment and level pay off track
    # are served now (tests/test_bbr_payment_checks.py); these two are not.
    assert absent == {"bounced_payment_not_reversed", "credit_covers_bill"}


# ══════════════════════════════════════════════════════════════════════════
# B11 · warnings reach the findings, not only the drafts (DEF-BIL-8210)
# ══════════════════════════════════════════════════════════════════════════
def test_b11__a_draft_warning_is_on_the_findings_and_the_account_stays_ready(
    brazos, dana, monkeypatch
):
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(customer_selectors, "billed_service_codes_for", lambda account, **kw: None)
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle)

    for account in accounts.values():
        assert "no_service_agreements" in codes_for(prepared, account, ignore=())
    assert len(prepared.ready) == 3
    assert "no_service_agreements" in {w.reason for w in prepared.warnings}


# ══════════════════════════════════════════════════════════════════════════
# B15 · re-check named accounts only
# ══════════════════════════════════════════════════════════════════════════
def test_b15__a_recheck_examines_only_the_named_accounts(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle, only_accounts=[str(accounts["A-00106"].id)])

    assert [d.account_no for d in prepared.ready] == ["A-00106"]
    assert prepared.blocked == ()  # no run-shape rows on a partial pass


# ══════════════════════════════════════════════════════════════════════════
# B10 · the taxonomy covers every code and every label exists (DEF-BIL-8209)
# ══════════════════════════════════════════════════════════════════════════
def _engine_codes() -> set[str]:
    from apps.billing import bill_warnings, check_taxonomy, decisions, gather, read_analysis

    codes = set()
    for module, prefixes in (
        (gather, ("GATHER_",)),
        (runs, ("RUN_", "ANCHOR_", "CALC_", "PRICING_", "READ_")),
        (read_analysis, ("CASE_",)),
    ):
        for name in dir(module):
            if (
                name.startswith(prefixes)
                and not name.startswith("RUN_STATUS_")
                and isinstance(getattr(module, name), str)
            ):
                codes.add(getattr(module, name))
    codes.add(gather.UNCONNECTED_PLAN_SERVICE)
    codes |= set(decisions.CHOICES_BY_CASE) | set(decisions.UNSUPPORTED_CASES)
    codes |= {"service_not_connected", "missing_read", "base_only_billing", "billing_continuity"}
    codes |= set(check_taxonomy.PAYMENT_CODES)
    codes |= {check_taxonomy.CHECK_FAILED, check_taxonomy.CHECK_REFUSED}
    codes |= set(check_taxonomy.WARNING_CODE_BY_KEY.values())
    codes.add(check_taxonomy.WARN_UNIT_FROM_METER)
    assert bill_warnings.BASE_NOT_SET in check_taxonomy.WARNING_CODE_BY_KEY
    return codes


# BULK-CHG-36 · BULK-CHG-46
def test_b10__every_code_the_engine_raises_has_a_category_tag_and_severity():
    from apps.billing import check_taxonomy

    missing = sorted(code for code in _engine_codes() if code not in check_taxonomy.TAGS)
    assert missing == []
    assert len(check_taxonomy.CATEGORIES) == 9
    for tag in check_taxonomy.TAGS.values():
        assert tag.category in check_taxonomy.CATEGORIES
        assert tag.severity in (*check_taxonomy.SEVERITIES, None)


# BULK-CHG-36
def test_b10__every_tag_and_category_has_a_label_in_all_eleven_catalogues():
    import json
    import pathlib

    from apps.billing import check_taxonomy

    root = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    catalogues = sorted(root.glob("*.json"))
    assert len(catalogues) == 11
    wanted = {tag.label_key for tag in check_taxonomy.TAGS.values()}
    wanted |= {check_taxonomy.CATEGORY_KEY.format(category=c) for c in check_taxonomy.CATEGORIES}
    for path in catalogues:
        keys = set(json.loads(path.read_text(encoding="utf-8")))
        assert sorted(wanted - keys) == [], path.name
