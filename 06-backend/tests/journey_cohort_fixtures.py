# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 (2026-08-19) — *"we have to ensure all fixtures are working"*.
#           50 activated journeys had no fixture cohort; this module is the
#           SHARED cohort the largest group of them asserts over (the
#           money-triples flat ride), built once and registered per journey in
#           08-qa/01-e2e/stack/seed_journey_fixture.py.
# Rules:    CLAUDE.md rule 1 (every write inside tenant context; RLS FORCE) ·
#           rule 2 (NUMERIC + CHAR(3); never float) · rule 3 (explicit unit on
#           every consumption) · rule 4 (nothing here updates an issued row) ·
#           rule 5 (journal lines only via the posting service — this module
#           never posts; the ISSUE path does, through its own seam) · rule 6
#           (the bill run is idempotency-keyed) · rule 7 (all writes go through
#           audited services or the established test-fixture builders).
# Golden:   NO FIGURE IS INVENTED HERE. Every money figure is cited to the row
#           of 08-qa/01-e2e/expected/money-triples.csv it comes from (generated
#           from frozen B4 rules by 10-scripts/04-e2e-expected-gen.py) or to
#           US-BIL-008 §4's workbook authority set. The cohort's issued bill is
#           ASSERTED against the dataset row at seed time — a cohort that
#           prices anything else REFUSES to report success.
# Tests:    tests/test_cr014_journey_cohorts.py (red-proved on 2026-08-22 by
#           breaking the tier price and by moving the service date into the
#           signed July window — both quoted in the lane report).
# ───────────────────────────────────────────────────────
"""The CR-014 shared journey cohorts — the flat money ride, seeded for real.

WHY AUGUST AND NOT JULY, AND WHY THAT IS A RECORDED DECISION (2026-08-22)
-------------------------------------------------------------------------
Most of the T4/T5/T7 fixture paragraphs pin the flat money-triples bill
(97.41) to a JULY run on brazos-bend. But July on brazos-bend is FINANCE
territory: J19's month-close journey asserts the July trial-balance window
foots at the signed LE-1 figure **553.69** (whole book **598.69**), and the PO
closed OQ-218 with *"no reason to disturb a signed figure to test a feature
September can already test"* — test data is shaped to fit signed figures,
never the other way round. An ISSUED bill posts its journal entry at the
bill's `service_date` (apps/billing/posting_seam.py), so ANY real bill issued
for a period ending inside July moves 553.69 and restates the signed book.

So this cohort bills **August 2026** (period Aug 1–31, service date Aug 31,
bill date Sep 1 → due Sep 22 at the 21 due-days the journeys state). Every
journal entry it causes lands on/after 2026-08-31 — outside both signed
windows (July, and the whole-book window that ends at July's close). The
journeys whose paragraphs said July carry a dated fixture amendment pointing
here; the conflict itself is DEF'd in the register (see the CR-014 progress
record in 12-governance/11-change-requests.md).

WHY THE ACCOUNT IS ACC-2042 AND NOT ACC-1042
--------------------------------------------
ACC-1042 is the SIGNED LE-1/LE-6 cast: billed **247.87** (WE-1) at 500 Main St
in the fixture July, asserted by the ledger test suite and by J19. Several
journey paragraphs ALSO pinned the 97.41 flat bill to ACC-1042 — one account,
two contradictory July bills. The signed book wins; the flat ride gets its own
account, **ACC-2042**, at the premises T5-15 names (Brazos Bend Apartments,
Unit 4B, meter MTR-0451). Filed in the defect register rather than papered
over.

EVERY FIGURE, CITED
-------------------
money-triples row ``flat,cycle,full``: taxable **89.00** · tax **8.41** ·
total **97.41** — from usage 700 kWh × $0.11 = 77.00 plus base $12.00
(04-e2e-expected-gen.py, ``shape_lines("flat")``), taxed by the four WE-1
authorities (US-BIL-008 §4: TX State 6.25% · Travis County 1% · City
franchise 2% · PUC 0.2%), rounded half-up 2dp PER AUTHORITY:
5.56 + 0.89 + 1.78 + 0.18 = **8.41**.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

# ── The dataset row this cohort exists to make true ─────────────────────────
#: money-triples row `flat,cycle,full` (08-qa/01-e2e/expected/money-triples.csv)
FLAT_TAXABLE = Decimal("89.00")
FLAT_TAX = Decimal("8.41")
FLAT_TOTAL = Decimal("97.41")
#: the flat shape's line definitions (10-scripts/04-e2e-expected-gen.py)
FLAT_USAGE_QTY = Decimal("700.000000")  # kWh — explicit unit, CLAUDE.md rule 3
FLAT_UNIT_PRICE = Decimal("0.110000")
FLAT_BASE = Decimal("12.000000")
#: US-BIL-008 §4 — the Brazos Bend workbook authority set. Four separate
#: authorities on purpose: the engine must emit FOUR lines, never one 9.45%.
FLAT_AUTHORITIES: tuple[tuple[str, Decimal], ...] = (
    ("TX State", Decimal("0.0625")),
    ("Travis County", Decimal("0.0100")),
    ("City franchise", Decimal("0.0200")),
    ("PUC", Decimal("0.0020")),
)
#: per-authority tax on 89.00, rounded half-up 2dp per line (B4):
FLAT_TAX_LINES = (Decimal("5.56"), Decimal("0.89"), Decimal("1.78"), Decimal("0.18"))

# ── The period — OUTSIDE the signed July window, see module docstring ───────
AUG_START = date(2026, 8, 1)
AUG_END = date(2026, 8, 31)
AUG_SERVICE_DATE = date(2026, 8, 31)
AUG_BILL_DATE = date(2026, 9, 1)
DUE_DAYS = 21  # J24's own line: "bill date Aug 1 → due Aug 22 (due-days 21)"
AUG_ISSUED_AT = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

#: The signed July window this cohort MUST NOT touch (LE-1; OQ-218 ruling).
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)

# ── The cast ────────────────────────────────────────────────────────────────
CYCLE_CODE = "08-E2E"
PLAN_NAME = "E2E Flat Residential"
PLAN_CODE = "e2e-flat-residential"
PREMISES_ADDRESS = "Brazos Bend Apartments"  # T5-15's own name
UNIT_OCCUPIED = "4B"
UNIT_VACANT = "4C"  # T5-15: vacant sibling
UNIT_SECOND = "4D"  # T7-11's second billed account lives here
ACCOUNT_PRIMARY = "ACC-2042"  # NOT ACC-1042 — see module docstring
ACCOUNT_SECOND = "ACC-1101"  # T7-11's cast
METER_PRIMARY = "MTR-0451"  # T5-12 / T5-16: the replacement meter on 4B
METER_RETIRED = "MTR-0299"  # T5-16: retired 2026-06-30, terminal
METER_SECOND = "MTR-0452"
#: T5-12 (amended 2026-08-22): MTR-0451's prior committed read. The paragraph
#: said 2026-06-14, before the meter's own T5-16 install date of Jul 1; the
#: value (45,210) is the load-bearing part and is kept.
PRIOR_READ_VALUE = Decimal("45210")
PRIOR_READ_DAY = "2026-07-01"
BILLING_READ_VALUE = Decimal("45910")  # 45,210 + 700
BILLING_READ_DAY = "2026-08-28"
RETIRE_DATE = date(2026, 6, 30)  # T5-16's own date

RUN_IDEMPOTENCY_KEY = "2026-08|E2E-FLAT"  # CLAUDE.md rule 6


class CohortCannotSeed(Exception):
    """The cohort cannot be produced or verified — with the reason, always."""


def _actor_user(actor: Any):
    """The underlying users row, whichever shape of actor arrived."""
    return getattr(actor, "user", actor)


# ── Authorities ─────────────────────────────────────────────────────────────


def ensure_flat_authorities(tenant, actor) -> dict[str, Any]:
    """The four WE-1 authorities as REAL tax rows, each with its 2200 account.

    Jurisdiction + tax row follow the shape every billing test builds
    (test_br_bil_069's `a_tax_authority`); the liability account is minted
    through the REAL `apps.ledger.services.create_tax_authority_account`
    because B5 line 74 ❄️ says *tenant authorities mint their own* and no other
    path exists. Idempotent: an authority already present is reused untouched.

    The rows are inert until a plan BINDS them (`plan_tax_rules` shape 1), so
    creating them changes no other plan's pricing — that scoping is why the
    demo tenant's own two Texas rates are left exactly as seeded.
    """
    from apps.ledger import models as ledger_models
    from apps.ledger import services as ledger_services
    from apps.rating import models as rating_models

    built: dict[str, Any] = {}
    for name, rate in FLAT_AUTHORITIES:
        jurisdiction = rating_models.TaxJurisdiction.objects.filter(
            tenant=tenant, name=f"E2E {name}"
        ).first()
        if jurisdiction is None:
            jurisdiction = rating_models.TaxJurisdiction.objects.create(
                tenant=tenant, name=f"E2E {name}", authority=name
            )
        tax = rating_models.Tax.objects.filter(tenant=tenant, jurisdiction=jurisdiction).first()
        if tax is None:
            account_name = f"Tax payable — E2E {name}"
            account = ledger_models.LedgerAccount.objects.filter(
                tenant=tenant, name=account_name
            ).first()
            if account is None:
                # code=None → the product NUMBERS it (PO 2026-08-12, OQ-147).
                account = ledger_services.create_tax_authority_account(
                    name=account_name, actor=_actor_user(actor)
                )
            tax = rating_models.Tax.objects.create(
                tenant=tenant,
                jurisdiction=jurisdiction,
                name=f"E2E {name}",
                kind="percent",
                rate=rate,
                liability_gl_account_id=account.id,
            )
        built[name] = tax
    return built


# ── Plan ────────────────────────────────────────────────────────────────────


def ensure_priced_plan(tenant, actor, *, name, code, unit_price, base, budget_billing=False):
    """One PUBLISHED electric plan: a single 0→∞ tier at `unit_price` + `base`.

    Built the way `tests/test_us_bil_001_prepare.a_priced_plan` builds every
    plan the billing suite prices — the price is a tier (BR-RAT-032), the base
    is the schedule version's (the plan states none, so the schedule's figure
    is the one number a human typed — apps/billing/gather._base_charge_for).
    Published because BR-RAT-030 makes only published plans assignable.
    The four authorities are bound to THIS plan alone (plan_tax_rules shape 1).

    ⚠ **Parameterised on 2026-08-22 for CR-014 group 3 and NOT otherwise
    changed.** `ensure_flat_plan` below passes the same two figures it always
    passed, so the shared cohort still prices the dataset row — which
    `test_cr014_tc1` proves rather than this comment claiming it (hard-won law
    1). The extensions need a SECOND and a THIRD published plan (T4-01's
    change target, T4-02/T4-03's commercial plan) and duplicating this body per
    plan would put the tier price in three places (hard-won law 5).
    """
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors
    from tests.test_us_met_helpers import make_plan, state_size_axis

    plan = make_plan(tenant, name=name, code=code, services=("electric",))
    if budget_billing and not plan.budget_billing:
        # BR-RAT-043 — the plan flag budget eligibility reads. A fixture that
        # enrolled an account whose plan does not OFFER budget billing would be
        # seeding past `budget.eligibility`, not through it.
        plan.budget_billing = True
        plan.save(update_fields=["budget_billing"])

    for row in rating_selectors.plan_rate_schedules(plan.id):
        tariff = row["tariff"]
        version = rating_models.TariffVersion.objects.filter(
            tenant=tenant, tariff=tariff
        ).first()
        if version is None:
            version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=tariff,
                model="flat",
                base_charge=base,
                uom="kWh",
                currency="USD",
                effective_from=date(2026, 1, 1),
            )
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=unit_price,
            )
        # BR-RAT-120 / DEF-2816 — the version says which connection sizes it
        # serves. Without it a BANDED service refuses every account at R3 by
        # name, which is the reading the PO chose on 2026-08-28. The rows carry
        # no minimum bill and move no money; see `state_size_axis`.
        state_size_axis(version, tariff.service.code)
        # ⚠ `DEF-BIL-9100` — THE BASE ON THE OBJECT A BILL READS. Since
        # `DEF-BIL-7170` (2026-09-28) the version's `base_charge` above is never
        # a source: the base is the `is_base` charge code BOUND to the schedule
        # (`BR-RAT-1025`), and since `18e1069f2` (2026-09-30) a schedule with
        # none bills `$0.00` with a warning — so WE-1 issued at 210.00. The SAME
        # figure, one code per plan, NAMED on the version (`base_charge_code`)
        # so several cohort plans with different bases on one tenant cannot be
        # read for one another (`DEF-468`'s ambiguity).
        if version.base_charge_code_id is None:
            base_code, _ = rating_models.Charge.objects.get_or_create(
                tenant=tenant,
                code=f"BASE-{code.upper()}"[:40],
                defaults=dict(
                    name=f"{name} base"[:120],
                    charge_type="recurring",
                    amount_rule="flat",
                    amount=base,
                    service=tariff.service,
                    is_base=True,
                ),
            )
            version.base_charge_code = base_code
            version.save(update_fields=["base_charge_code"])
    authorities = ensure_flat_authorities(tenant, actor)
    for authority_name, _rate in FLAT_AUTHORITIES:
        tax = authorities[authority_name]
        rating_models.PlanTaxRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, jurisdiction=tax.jurisdiction, tax=None
        )
    return plan


def ensure_flat_plan(tenant, actor):
    """The money-triples flat plan: one 0→∞ tier at $0.11/kWh + $12.00 base."""
    return ensure_priced_plan(
        tenant,
        actor,
        name=PLAN_NAME,
        code=PLAN_CODE,
        unit_price=FLAT_UNIT_PRICE,
        base=FLAT_BASE,
    )


# ── World: premises, units, meters, accounts, cycle, reads ──────────────────


def ensure_flat_world(tenant, actor) -> dict[str, Any]:
    """The T5-15 / T5-12 / T5-16 world, through the real services.

    Premises and units through `metering.services`; meters through
    `assets.services.create_asset`; the plan assignment through the REAL
    `assign_unit_plan` (the S15 act — same posture as seed_j23); accounts by
    the established test-cast pattern (pinned numbers, ORM — the same shape
    `tests.ledger_le_fixtures.make_accounts` uses for the signed cast).
    """
    from apps.assets import models as asset_models
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services
    from tests.test_us_met_helpers import make_premises, make_unit
    from tests.test_us_met_reads_helpers import a_meter, commit_read

    world: dict[str, Any] = {}

    premises = None
    existing_unit = metering_models.Unit.objects.filter(
        tenant=tenant, label=UNIT_OCCUPIED, premises__address_line=PREMISES_ADDRESS
    ).first()
    if existing_unit is not None:
        premises = {"id": str(existing_unit.premises_id)}
    if premises is None:
        premises = make_premises(
            actor, address_line=PREMISES_ADDRESS, services_available=["electric"]
        )
    world["premises_id"] = premises["id"]

    def unit_named(label):
        row = metering_models.Unit.objects.filter(
            tenant=tenant, premises_id=premises["id"], label=label
        ).first()
        if row is not None:
            return {"id": str(row.id)}
        return make_unit(actor, premises["id"], label=label, services=["electric"])

    unit_4b = unit_named(UNIT_OCCUPIED)
    unit_named(UNIT_VACANT)  # T5-15: vacant sibling — exists, no account
    unit_4d = unit_named(UNIT_SECOND)
    world["unit_4b_id"] = unit_4b["id"]
    world["unit_4d_id"] = unit_4d["id"]

    def meter_named(asset_no, unit_id, install_date):
        row = asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
        if row is not None:
            return {"id": str(row.id)}
        return a_meter(actor, asset_no=asset_no, unit_id=unit_id)

    meter_451 = meter_named(METER_PRIMARY, unit_4b["id"], "2026-07-01")
    meter_452 = meter_named(METER_SECOND, unit_4d["id"], "2026-07-01")
    world["meter_451_id"] = meter_451["id"]
    world["meter_452_id"] = meter_452["id"]

    # T5-16: MTR-0299 retired 2026-06-30 (US-AST-008, terminal), replaced by
    # MTR-0451 — through the REAL retire service, so the terminal transition,
    # the audit row and the replacement link are the product's own.
    retired = asset_models.Asset.objects.filter(tenant=tenant, asset_no=METER_RETIRED).first()
    if retired is None:
        from apps.assets import services as asset_services

        spare = asset_services.create_asset(
            actor,
            {
                "type": "meter",
                "asset_no": METER_RETIRED,
                "service": "electric",
                "unit": "kWh",
                "read_method": "walk_by",
                "multiplier": "1",
                "register_digits": 5,
                "install_date": "2026-01-05",
                "status": "active",
            },
        )
        asset_services.retire_asset(
            actor,
            spare["id"],
            {
                "reason": "replaced",
                "retire_date": RETIRE_DATE.isoformat(),
                "replaced_by": METER_PRIMARY,
            },
        )

    # Cycle — a DEFINITION (BR-MET-077); the window is DERIVED from start day +
    # days to complete (W5-T2), and billing reads the derived pair.
    cycle, _ = metering_models.Cycle.objects.get_or_create(
        tenant=tenant,
        code=CYCLE_CODE,
        defaults={
            # W5-T2 — the RULED fields. `window_start`/`window_end` were dropped
            # by metering 0021 and the window is derived from these two; August
            # is what AUG_START/AUG_END named, so the same window comes out.
            "frequency": "Monthly",
            "start_day": AUG_START.day,
            "days_to_complete": (AUG_END - AUG_START).days + 1,
            "due_days": DUE_DAYS,
        },
    )
    if cycle.due_days != DUE_DAYS:
        cycle.due_days = DUE_DAYS
        cycle.save(update_fields=["due_days"])
    world["cycle"] = cycle
    metering_models.ServicePoint.objects.filter(
        tenant=tenant, unit_id__in=[unit_4b["id"], unit_4d["id"]]
    ).update(cycle=cycle)

    # The plan, married to the units through the REAL S15 act.
    plan = ensure_flat_plan(tenant, actor)
    world["plan"] = plan
    for unit_id in (unit_4b["id"], unit_4d["id"]):
        row = metering_models.Unit.objects.get(tenant=tenant, pk=unit_id)
        if row.rate_plan_id is None:
            metering_services.assign_unit_plan(
                actor,
                unit_id,
                {
                    "plan_id": str(plan.id),
                    "effective_from": date(2026, 7, 1).isoformat(),
                    "reason": "CR-014 journey cohort (journey_cohort_fixtures.py)",
                },
            )

    # Accounts — pinned numbers, the make_accounts pattern. get_or_create so a
    # re-boot mints nothing twice.
    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customer_models.AccountType.objects.first()
    for key, account_no, unit_id in (
        ("account_primary", ACCOUNT_PRIMARY, unit_4b["id"]),
        ("account_second", ACCOUNT_SECOND, unit_4d["id"]),
    ):
        account = customer_models.Account.objects.filter(
            tenant=tenant, account_no=account_no
        ).first()
        if account is None:
            account = customer_models.Account.objects.create(
                tenant=tenant,
                unit_id=unit_id,
                account_no=account_no,
                status=status,
                account_type=account_type,
            )
        world[key] = account

    # Reads: T5-12's prior committed value, then the August billing read.
    def ensure_read(asset_id, day, value, prior, consumption):
        from apps.metering.models import MeterRead
        from tests.test_us_met_reads_helpers import at

        if MeterRead.objects.filter(
            tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
        ).exists():
            return
        commit_read(
            actor,
            asset_id,
            day=day,
            value=str(value),
            prior_value=str(prior) if prior is not None else None,
            consumption=str(consumption) if consumption is not None else None,
            unit="kWh",
        )

    for meter in (meter_451, meter_452):
        ensure_read(meter["id"], PRIOR_READ_DAY, PRIOR_READ_VALUE, None, None)
        ensure_read(
            meter["id"], BILLING_READ_DAY, BILLING_READ_VALUE, PRIOR_READ_VALUE, FLAT_USAGE_QTY
        )

    return world


# ── The run: prepare → calculate → release → issue, asserted ────────────────


def run_flat_august_run(tenant, actor, world) -> dict[str, Any]:
    """The five-phase run over the cohort cycle, issued, and PROVED.

    Refuses to report success unless the primary account's issued bill totals
    exactly the dataset row (97.41 = 89.00 + 8.41) with the four per-authority
    tax lines — a cohort that prices anything else is a broken fixture and a
    broken fixture that reports success is DEF-108 with extra steps.
    """
    from apps.billing import issue as billing_issue
    from apps.billing import models as billing_models
    from apps.billing import release as billing_release
    from apps.billing import runs as billing_runs
    from apps.billing import templates_service

    cycle = world["cycle"]
    primary = world["account_primary"]

    bill_run = billing_models.BillRun.objects.filter(
        tenant=tenant, idempotency_key=RUN_IDEMPOTENCY_KEY
    ).first()
    if bill_run is None:
        bill_run = billing_models.BillRun.objects.create(
            tenant=tenant,
            cycle=cycle,
            period_start=AUG_START,
            period_end=AUG_END,
            bill_date=AUG_BILL_DATE,
            idempotency_key=RUN_IDEMPOTENCY_KEY,
        )

    issued_already = billing_models.Invoice.objects.filter(
        tenant=tenant, bill_run=bill_run, status="issued"
    )
    if not issued_already.exists():
        prepared = billing_runs.prepare_run(
            cycle_id=cycle.id,
            period_start=AUG_START,
            period_end=AUG_END,
            service_date=AUG_SERVICE_DATE,
        )
        if not prepared.ready:
            blocked = "; ".join(
                f"{problem.account_no}: {problem.detail}" for problem in prepared.blocked
            )
            raise CohortCannotSeed(
                f"prepare_run found no ready account on cycle {CYCLE_CODE} — "
                f"blocked: {blocked or '(none listed)'}"
            )
        calculated = billing_runs.calculate_run(prepared, bill_run=bill_run)
        if calculated.breaks:
            details = "; ".join(
                f"{item.account_no} @{item.stage}: {item.detail}" for item in calculated.breaks
            )
            raise CohortCannotSeed(f"calculate_run broke: {details}")

        summary = billing_release.summary_for(bill_run)
        owner = _actor_user(actor)
        billing_release.authorise_release(
            bill_run=bill_run,
            summary=summary,
            confirmations=billing_release.Confirmations(
                compliance=True,
                email_mandate=True,
                sms_mandate=True,
                autopay_mandate=True,
                final=True,
            ),
            confirmed_by=getattr(owner, "pk", owner),
            confirmed_at=AUG_ISSUED_AT,
            actor=actor,
        )
        template, version = templates_service.resolve_for(consumer_category=None)
        billing_issue.issue_run(
            bill_run,
            issued_at=AUG_ISSUED_AT,
            template_id=template.pk,
            template_version=version.version_no,
            actor=actor,
        )

    invoice = (
        billing_models.Invoice.objects.filter(
            tenant=tenant, bill_run=bill_run, account=primary, status="issued"
        )
        .order_by("-created_at")
        .first()
    )
    if invoice is None:
        raise CohortCannotSeed(
            f"no issued invoice for {ACCOUNT_PRIMARY} on run {RUN_IDEMPOTENCY_KEY} "
            "after the issue pass — read the issue breaks above."
        )

    # ── THE ASSERTION THAT MAKES THIS A FIXTURE AND NOT A HOPE ──────────────
    total = Decimal(invoice.total).quantize(Decimal("0.01"))
    if total != FLAT_TOTAL:
        raise CohortCannotSeed(
            f"the issued bill totals {total}, not the dataset row's {FLAT_TOTAL} "
            "(money-triples `flat,cycle,full`). The cohort is WRONG and must not "
            "be reported as seeded."
        )
    tax_lines = sorted(
        Decimal(line.amount).quantize(Decimal("0.01"))
        for line in invoice.lines.all()
        if line.kind == "tax"
    )
    if tax_lines != sorted(FLAT_TAX_LINES):
        raise CohortCannotSeed(
            f"tax lines {tax_lines} != the four per-authority lines "
            f"{sorted(FLAT_TAX_LINES)} (US-BIL-008 §4 on a {FLAT_TAXABLE} base)."
        )
    return {
        "bill_run_id": str(bill_run.pk),
        "invoice_no": getattr(invoice, "invoice_no", None) or str(invoice.pk),
        "total": str(total),
        "due_date": str(getattr(invoice, "due_date", None)),
        "tax_lines": [str(v) for v in tax_lines],
    }


def ensure_flat_cohort(tenant, actor) -> dict[str, Any]:
    """World + run + proof, in one call. Idempotent end to end."""
    world = ensure_flat_world(tenant, actor)
    result = run_flat_august_run(tenant, actor, world)
    result["account_primary"] = ACCOUNT_PRIMARY
    result["account_second"] = ACCOUNT_SECOND
    return result


# ── The role cast (T5-25 / T5-26 / T6-09's actors) ──────────────────────────


def ensure_role_cast(tenant, actor) -> dict[str, str]:
    """One active System Admin (the owner) + the two sample staff roles.

    Uses identity's OWN sample seam (`apps.identity.sample_data`), which mints
    the billing clerk and executive through `add_user` — invited, uncredentialed,
    temp password discarded. The journey paragraphs name Priya/Marcus/Dana;
    those are persona names, and the product's own sample cast (Sam Reyes,
    Avery Cole, plus the provisioning owner) carries the same three roles. The
    ROLES are what the journeys assert; the actual names are reported.
    """
    from apps.identity import models as identity_models
    from apps.identity import sample_data as identity_sample

    identity_sample.seed_sample_records(actor)
    cast: dict[str, str] = {}
    for membership in identity_models.TenantMembership.objects.filter(
        tenant=tenant
    ).select_related("user", "role"):
        cast.setdefault(membership.role.code, membership.user.full_name or membership.user.email)
    return cast



# ── CR-014 GROUP 3 · the flat-cohort EXTENSIONS (W11 lane, 2026-08-22) ──────
#
# The CR's own sizing rule is that the COHORT is the unit of work, so these
# are not twenty-one cohorts: they are the shared flat ride plus one more act
# each. Everything below builds on `ensure_flat_cohort` and adds only what its
# journey's own **Fixture.** paragraph names.
#
# ⚠ THREE STANDING CONSTRAINTS, and each one changed what could be seeded:
#
# 1. **DEF-556 / OQ-218.** An issued bill posts its journal entry at its
#    SERVICE DATE, and June 30 → July 31 is the finance-signed LE-1 window
#    (whole book 598.69, July 553.69). So NO extension may issue a bill whose
#    service date falls on or before 2026-07-31. Every paragraph that asks for
#    a July-dated bill, an already-assessed late fee, or an "overdue at seed
#    time" balance is therefore either moved into August/September with a dated
#    amendment, or REFUSED by name. It is never quietly back-dated.
# 2. **Each extension that bills gets its OWN cycle and its OWN idempotency
#    key.** The shared August run is idempotent on `2026-08|E2E-FLAT`, so once
#    it has issued, an account added afterwards would never be billed — a
#    fixture whose content depended on seeder ORDER is a fixture that is right
#    on a fresh boot and wrong on a re-boot. Separate cycles make order
#    irrelevant.
# 3. **A seeder that cannot honestly satisfy its journey REFUSES by name.**
#    `CohortCannotSeed` with the missing artefact named is the deliverable in
#    that case; printing ✔ over a half-seeded world is DEF-108's false green,
#    which is the entire reason CR-014 exists.

#: T4-01's change target — a second PUBLISHED, service-compatible electric
#: plan. Its price is deliberately NOT a workbook figure: T4-01's own paragraph
#: says *"Split-group dollar values are engine-computed per 00-e2e-design.md §5"*,
#: so a typed total here would invent a figure the journey does not assert.
SECOND_PLAN_NAME = "E2E Flat Residential v2-shape"
SECOND_PLAN_CODE = "e2e-flat-residential-v2"
SECOND_PLAN_PRICE = Decimal("0.130000")
SECOND_PLAN_BASE = Decimal("13.000000")

#: T4-02 / T4-03's commercial plan. Same reasoning: engine-computed figures.
COMMERCIAL_PLAN_NAME = "E2E Small Commercial"
COMMERCIAL_PLAN_CODE = "e2e-small-commercial"
COMMERCIAL_PLAN_PRICE = Decimal("0.150000")
COMMERCIAL_PLAN_BASE = Decimal("20.000000")

#: T4-02's `plan_deposit_rules` pair, quoted from its Fixture paragraph:
#: *"deposit held $150.00 (fixture plan_deposit_rules Residential; Small
#: Commercial category amount $400.00 exists in the same fixture)"*.
RESIDENTIAL_DEPOSIT = Decimal("150.000000")
COMMERCIAL_DEPOSIT = Decimal("400.000000")

#: T4-12's evidence set, verbatim from its paragraph.
EXEMPT_ACCOUNT = "ACC-2049"  # paragraph says ACC-1049 — see the amendment note
EXEMPT_CERT_REF = "TX-EX-88121"
EXEMPT_CERT_EXPIRY = date(2026, 7, 31)

#: T4-15's swap cast (paragraph: meter M-2201 on unit 104, ACC-1044 active).
SWAP_UNIT = "104"
SWAP_ACCOUNT = "ACC-2044"
SWAP_METER_OLD = "M-2201"

#: T4-16's reconciliation group (paragraph: master M-MASTER-12, children
#: SM-8801 + SM-8802, SM-8801 moves alone to Vega Apts unit 105).
MASTER_METER = "M-MASTER-12"
SUB_METER_MOVED = "SM-8801"
SUB_METER_STAYS = "SM-8802"
MASTER_UNIT = "MB-1"
MOVE_TARGET_UNIT = "105"
#: BR-MET-025's mismatch tolerance is a tenant SETTING (`mismatch_default_pct`,
#: seeded default 3) — T4-16's *"loss tolerance tenant-set; the 3% is a sample"*.
MISMATCH_TOLERANCE_PCT = Decimal("3")

#: T4-03's error-correction cast — an OCCUPIED unit carrying the WRONG plan.
WRONG_PLAN_UNIT = "106"
WRONG_PLAN_ACCOUNT = "ACC-2046"
WRONG_PLAN_METER = "MTR-0461"
WRONG_PLAN_CYCLE = "08-E2E-T403"
WRONG_PLAN_RUN_KEY = "2026-08|E2E-T403"

#: T5-14's cutover defect — Active account, no plan snapshot anywhere.
NO_PLAN_UNIT = "12C"
NO_PLAN_ACCOUNT = "ACC-3055"
NO_PLAN_METER = "MTR-3055"
NO_PLAN_CYCLE = "08-E2E-T514"

#: T5-19's DRAFT run — computed lines pre-issue, plus the TAMPER charge code.
DRAFT_UNIT = "4E"
DRAFT_ACCOUNT = "ACC-2519"
DRAFT_METER = "MTR-0519"
DRAFT_CYCLE = "08-E2E-T519"
DRAFT_RUN_KEY = "2026-08|E2E-T519"
TAMPER_CODE = "TAMPER"
#: NO AMOUNT IS DECLARED HERE. T5-19's paragraph quotes the billing workbook's
#: WE-11 **$500.00**; the PO ruled the platform default is **$250.00** on
#: 2026-08-10, over that very figure (DEF-563). `ensure_tamper_charge` reads the
#: ruled number from `seed_demo.CHARGE_CODES` and never overwrites a tenant's
#: own row, so this module holds no fourth copy of a contested figure.

#: T4-12's exempt account and T4-21/T7-15's budget accounts each get a cycle so
#: the journey's own run has somewhere to run.
EXEMPT_UNIT = "4F"
EXEMPT_METER = "MTR-0549"
EXEMPT_CYCLE = "08-E2E-T412"

#: T4-21 — WE-8: trailing-12 actuals $2,904 → computed level **$242**.
BUDGET_PLAN_NAME = "E2E Flat Residential (budget)"
BUDGET_PLAN_CODE = "e2e-flat-residential-budget"
WE8_TRAILING_TOTAL = Decimal("2904.00")
WE8_LEVEL = Decimal("242")
BUDGET_BAND_ACCOUNT = "ACC-2047"
BUDGET_BAND_UNIT = "4G"
BUDGET_BAND_METER = "MTR-0547"
#: T7-15 — money-triples `flat,budget`: level **97**, variance **-0.41** after
#: one 97.41 bill; `last_leveled_at` 2026-05-01, settle_up_month 4, cadence 6.
T715_ACCOUNT = "ACC-2140"
T715_UNIT = "4H"
T715_METER = "MTR-0540"
T715_LEVEL = Decimal("97")
T715_VARIANCE = Decimal("-0.41")
T715_ACTUAL = FLAT_TOTAL  # 97.41 — the same dataset row, by the CSV's own note
T715_LEVELLED_AT = date(2026, 5, 1)
T715_SETTLE_UP_MONTH = 4
T715_RELEVEL_CADENCE = 6
#: The twelve months whose actuals sum to WE-8's 2,904. 2,904 / 12 = 242.00
#: exactly, so twelve equal months reproduce the workbook's level with no
#: rounding of our own — the AVERAGE is the signed figure, not the shape.
WE8_MONTHLY = Decimal("242.00")


# ── Extension primitives ────────────────────────────────────────────────────


def _premises_id(tenant, actor) -> str:
    """The cohort premises, created if the flat world has not been built yet."""
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_premises

    row = metering_models.Premises.objects.filter(
        tenant=tenant, address_line=PREMISES_ADDRESS
    ).first()
    if row is not None:
        return str(row.id)
    return make_premises(
        actor, address_line=PREMISES_ADDRESS, services_available=["electric"]
    )["id"]


def _unit(tenant, actor, label: str) -> str:
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_unit

    premises_id = _premises_id(tenant, actor)
    row = metering_models.Unit.objects.filter(
        tenant=tenant, premises_id=premises_id, label=label
    ).first()
    if row is not None:
        return str(row.id)
    return make_unit(actor, premises_id, label=label, services=["electric"])["id"]


def _meter(tenant, actor, asset_no: str, unit_id: str) -> str:
    from apps.assets import models as asset_models
    from tests.test_us_met_reads_helpers import a_meter

    row = asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
    if row is not None:
        return str(row.id)
    return a_meter(actor, asset_no=asset_no, unit_id=unit_id)["id"]


def _account(tenant, unit_id: str, account_no: str, **fields):
    """One account on a unit, the `make_accounts` pinned-number pattern.

    `fields` carries the customer-data columns a journey's paragraph names
    (T4-12's exemption evidence, T4-02's deposit held). They are account
    ATTRIBUTES, not issued financial rows, so setting them on an existing row
    is not a hard-rule-4 update — and a fixture that skipped them on a re-boot
    would be a different world on the second run than on the first.
    """
    from apps.customers import models as customer_models

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account = customer_models.Account.objects.filter(
        tenant=tenant, account_no=account_no
    ).first()
    if account is None:
        account = customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit_id,
            account_no=account_no,
            status=status,
            account_type=_account_type(fields.pop("account_type_code", None)),
            **fields,
        )
        return account
    fields.pop("account_type_code", None)
    changed = [name for name, value in fields.items() if getattr(account, name) != value]
    if changed:
        for name in changed:
            setattr(account, name, fields[name])
        account.save(update_fields=[*changed, "updated_at"])
    return account


def _account_type(code: str | None):
    from apps.customers import models as customer_models

    if code is None:
        return customer_models.AccountType.objects.first()
    row = customer_models.AccountType.objects.filter(code=code).first()
    if row is None:
        raise CohortCannotSeed(
            f"the platform account-type catalogue has no `{code}` row, so the "
            "category this journey changes between does not exist. Re-run "
            "`manage.py seed_demo` (it seeds the platform catalogues)."
        )
    return row


def _cycle(tenant, code: str, unit_ids: list[str]):
    """A cycle DEFINITION (BR-MET-077) with the journeys' 21 due-days, and the
    named units' service points attached to it."""
    from apps.metering import models as metering_models

    cycle, _ = metering_models.Cycle.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            # W5-T2 — the RULED fields. `window_start`/`window_end` were dropped
            # by metering 0021 and the window is derived from these two; August
            # is what AUG_START/AUG_END named, so the same window comes out.
            "frequency": "Monthly",
            "start_day": AUG_START.day,
            "days_to_complete": (AUG_END - AUG_START).days + 1,
            "due_days": DUE_DAYS,
        },
    )
    if cycle.due_days != DUE_DAYS:
        cycle.due_days = DUE_DAYS
        cycle.save(update_fields=["due_days"])
    if unit_ids:
        metering_models.ServicePoint.objects.filter(
            tenant=tenant, unit_id__in=unit_ids
        ).update(cycle=cycle)
    return cycle


def _assign_plan(tenant, actor, unit_id: str, plan, *, reason: str):
    """The REAL S15 act (`assign_unit_plan`) — same posture as the shared world."""
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services

    row = metering_models.Unit.objects.get(tenant=tenant, pk=unit_id)
    if row.rate_plan_id == plan.id:
        return
    metering_services.assign_unit_plan(
        actor,
        unit_id,
        {
            "plan_id": str(plan.id),
            "effective_from": date(2026, 7, 1).isoformat(),
            "reason": reason,
        },
    )


def _reads(tenant, actor, asset_id: str):
    """The cohort's own two committed reads: prior head, then the 700 kWh
    billing read. CLAUDE.md rule 3 — the unit is explicit on both."""
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    for day, value, prior, consumption in (
        (PRIOR_READ_DAY, PRIOR_READ_VALUE, None, None),
        (BILLING_READ_DAY, BILLING_READ_VALUE, PRIOR_READ_VALUE, FLAT_USAGE_QTY),
    ):
        if MeterRead.objects.filter(
            tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
        ).exists():
            continue
        commit_read(
            actor,
            asset_id,
            day=day,
            value=str(value),
            prior_value=str(prior) if prior is not None else None,
            consumption=str(consumption) if consumption is not None else None,
            unit="kWh",
        )


def _billable_unit(tenant, actor, *, label, meter_no, account_no, plan, cycle_code,
                   account_fields=None, reads=True):
    """unit → meter → plan → reads → account → cycle, in that order.

    One call is the whole pre-state a bill run needs for one more account, and
    every hop goes through the module that owns it (metering for the premises
    and the plan assignment, assets for the meter, metering again for the
    committed reads). `plan=None` is T5-14's cutover defect and is deliberate,
    not an omission — see `seed_t5_14`.
    """
    unit_id = _unit(tenant, actor, label)
    meter_id = _meter(tenant, actor, meter_no, unit_id)
    if plan is not None:
        _assign_plan(tenant, actor, unit_id, plan, reason=f"CR-014 group 3 fixture ({label})")
    if reads:
        _reads(tenant, actor, meter_id)
    account = _account(tenant, unit_id, account_no, **(account_fields or {}))
    cycle = _cycle(tenant, cycle_code, [unit_id]) if cycle_code else None
    return {
        "unit_id": unit_id,
        "meter_id": meter_id,
        "account": account,
        "cycle": cycle,
    }


def _prepare(cycle, *, period_start=AUG_START, period_end=AUG_END, service_date=AUG_SERVICE_DATE):
    """Phase 1 over one cycle and ONE window.

    The window is an argument rather than the module's August constants because
    three journeys need a SECOND and THIRD month on the same account — T4-19's
    two due dates a fortnight apart, T7-14's three cycles of trailing average.
    August stays the default so every group-1/3 caller is unchanged.
    """
    from apps.billing import runs as billing_runs

    return billing_runs.prepare_run(
        cycle_id=cycle.id,
        period_start=period_start,
        period_end=period_end,
        service_date=service_date,
    )


def _run(
    tenant,
    actor,
    *,
    cycle,
    idempotency_key,
    issue: bool,
    period_start=AUG_START,
    period_end=AUG_END,
    service_date=AUG_SERVICE_DATE,
    bill_date=AUG_BILL_DATE,
    issued_at=AUG_ISSUED_AT,
):
    """prepare → calculate (→ release → issue), over ONE extension cycle.

    ⚠ **THE WINDOW IS AN ARGUMENT, AND EVERY DEFAULT IS AUGUST** — the month
    DEF-556 put this whole cohort in, outside the finance-signed
    2026-06-30 → 2026-07-31 window. A caller that moves the window moves it
    FORWARD (September, October) and never back; nothing in this module may
    issue a bill whose service date lands in the signed month, because an
    issued bill posts its journal entry at its service date and would restate
    LE-1's 553.69.

    Returns the run's invoices. `issue=False` stops at phase 2, which is what
    T5-19 asserts over: a DRAFT is not money (BR-BIL-004), and the journey's
    whole point is that no hand-typed amount can reach one.

    No money figure is asserted here — the extensions' totals are engine-
    computed per 00-e2e-design.md §5, and the ONE cohort with a signed figure
    (97.41) is asserted by `run_flat_august_run`, not by this.
    """
    from apps.billing import issue as billing_issue
    from apps.billing import models as billing_models
    from apps.billing import release as billing_release
    from apps.billing import runs as billing_runs
    from apps.billing import templates_service

    bill_run = billing_models.BillRun.objects.filter(
        tenant=tenant, idempotency_key=idempotency_key
    ).first()
    if bill_run is None:
        bill_run = billing_models.BillRun.objects.create(
            tenant=tenant,
            cycle=cycle,
            period_start=period_start,
            period_end=period_end,
            bill_date=bill_date,
            idempotency_key=idempotency_key,
        )

    wanted_status = "issued" if issue else "draft"
    existing = billing_models.Invoice.objects.filter(
        tenant=tenant, bill_run=bill_run, status=wanted_status
    )
    if not existing.exists():
        prepared = _prepare(
            cycle,
            period_start=period_start,
            period_end=period_end,
            service_date=service_date,
        )
        if not prepared.ready:
            blocked = "; ".join(
                f"{problem.account_no}: {problem.detail}" for problem in prepared.blocked
            )
            raise CohortCannotSeed(
                f"prepare_run found no ready account on cycle {cycle.code} — "
                f"blocked: {blocked or '(none listed)'}"
            )
        calculated = billing_runs.calculate_run(prepared, bill_run=bill_run)
        if calculated.breaks:
            details = "; ".join(
                f"{item.account_no} @{item.stage}: {item.detail}" for item in calculated.breaks
            )
            raise CohortCannotSeed(f"calculate_run broke on {cycle.code}: {details}")
        if issue:
            summary = billing_release.summary_for(bill_run)
            owner = _actor_user(actor)
            billing_release.authorise_release(
                bill_run=bill_run,
                summary=summary,
                confirmations=billing_release.Confirmations(
                    compliance=True,
                    email_mandate=True,
                    sms_mandate=True,
                    autopay_mandate=True,
                    final=True,
                ),
                confirmed_by=getattr(owner, "pk", owner),
                confirmed_at=issued_at,
                actor=actor,
            )
            template, version = templates_service.resolve_for(consumer_category=None)
            billing_issue.issue_run(
                bill_run,
                issued_at=issued_at,
                template_id=template.pk,
                template_version=version.version_no,
                actor=actor,
            )

    invoices = list(
        billing_models.Invoice.objects.filter(
            tenant=tenant, bill_run=bill_run, status=wanted_status
        ).order_by("created_at")
    )
    if not invoices:
        raise CohortCannotSeed(
            f"no {wanted_status} invoice on run {idempotency_key} after the run — "
            "the fixture this journey asserts over does not exist, so nothing here "
            "may report success."
        )
    return invoices


# ── T4-01 · the change target ───────────────────────────────────────────────


def ensure_second_plan(tenant, actor):
    """T4-01's *"target plan … (published, service-compatible per BR-RAT-030)"*."""
    return ensure_priced_plan(
        tenant,
        actor,
        name=SECOND_PLAN_NAME,
        code=SECOND_PLAN_CODE,
        unit_price=SECOND_PLAN_PRICE,
        base=SECOND_PLAN_BASE,
    )


def ensure_commercial_plan(tenant, actor):
    """T4-02 / T4-03's *"Small Commercial"* plan — published, electric."""
    return ensure_priced_plan(
        tenant,
        actor,
        name=COMMERCIAL_PLAN_NAME,
        code=COMMERCIAL_PLAN_CODE,
        unit_price=COMMERCIAL_PLAN_PRICE,
        base=COMMERCIAL_PLAN_BASE,
    )


# ── T4-02 · the deposit rules, and the deposit that must NOT move ───────────


def ensure_deposit_rules(tenant, actor) -> dict[str, Any]:
    """`plan_deposit_rules`: Residential **150.00**, Small Commercial **400.00**.

    T4-02's whole assertion is an ABSENCE — the deposit held stays 150.00 when
    the account moves to the 400.00 category (BR-CUS-062, the OBVIOUS behaviour
    the PO ruled OUT for v1). An absence can only be asserted where the OTHER
    figure exists to be tempted by, so both rows are seeded and the account's
    `deposit_on_file` is the residential one.

    ⚠ **The HELD deposit is seeded too, and that was missing until 2026-08-22.**
    The rules are what a NEW account would be charged; `accounts.deposit_on_file`
    is what this one already holds, and it is the figure the journey watches for
    movement. With the rules alone, step 2's *"deposit held remains $150.00"*
    reads 0.00 before and 0.00 after — unchanged, so the journey PASSES, over an
    account that never held a deposit. That is DEF-108's false green in one
    column, which is why the account position is part of this fixture and not an
    afterthought.
    """
    from apps.customers import models as customer_models
    from apps.rating import models as rating_models

    ensure_flat_world(tenant, actor)
    account = customer_models.Account.objects.filter(
        tenant=tenant, account_no=ACCOUNT_PRIMARY
    ).first()
    if account is None:
        raise CohortCannotSeed(
            f"{ACCOUNT_PRIMARY} does not exist, so there is no account holding the 150.00 "
            "this journey asserts does not move. Seeding the deposit RULES without the "
            "held position would leave the journey comparing 0.00 to 0.00 and passing."
        )
    if Decimal(account.deposit_on_file) != RESIDENTIAL_DEPOSIT:
        account.deposit_on_file = RESIDENTIAL_DEPOSIT
        account.deposit_received_on = date(2026, 7, 1)  # BR-CUS-050 — held, dated
        account.save(update_fields=["deposit_on_file", "deposit_received_on", "updated_at"])

    flat = ensure_flat_plan(tenant, actor)
    commercial = ensure_commercial_plan(tenant, actor)
    residential_type = _account_type("residential")
    commercial_type = _account_type("commercial")
    for plan, account_type, amount in (
        (flat, residential_type, RESIDENTIAL_DEPOSIT),
        (commercial, commercial_type, COMMERCIAL_DEPOSIT),
    ):
        rating_models.PlanDepositRule.objects.get_or_create(
            tenant=tenant,
            rate_plan=plan,
            account_type_id=account_type.id,
            defaults={"amount": amount, "currency": "USD"},
        )
    return {
        "residential": RESIDENTIAL_DEPOSIT,
        "commercial": COMMERCIAL_DEPOSIT,
        "commercial_plan": commercial,
        "account_no": ACCOUNT_PRIMARY,
        "deposit_on_file": str(Decimal(account.deposit_on_file).quantize(Decimal("0.01"))),
    }


# ── T4-15 · the swap pre-state · T4-16 · the reconciliation group ───────────


def ensure_swap_pre_state(tenant, actor) -> dict[str, Any]:
    """T4-15's x-state: unit 104, ACC-2044 active, meter M-2201 (multiplier 1)
    with a committed read. The SWAP itself — final read on M-2201, initial read
    on M-3407 — is the journey's own act (steps 1–2), so seeding it would leave
    the journey asserting over its own answer."""
    plan = ensure_flat_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=SWAP_UNIT,
        meter_no=SWAP_METER_OLD,
        account_no=SWAP_ACCOUNT,
        plan=plan,
        cycle_code=None,  # the swap journey runs its OWN cycle
    )
    return {
        "unit_id": built["unit_id"],
        "meter_id": built["meter_id"],
        "account_no": SWAP_ACCOUNT,
    }


def ensure_master_group(tenant, actor) -> dict[str, Any]:
    """T4-16's x-state: master M-MASTER-12 with children SM-8801 + SM-8802.

    Both children go on the master's own unit through the REAL `create_asset`,
    so BR-AST-003's parent requirement is the SERVICE's refusal rather than
    this fixture's assumption. The unit is deliberately attached to NO billing
    cycle: `core/sample_fixture.sub_meter_plan` records that a sub-meter lands
    on its unit's existing service point and that `billing_reads_for_unit`
    takes the latest head ACROSS the point's assets, so a sub-metered unit
    inside a billed cycle would quietly change which read priced the bill.
    """
    from apps.assets import models as asset_models
    from apps.assets import services as asset_services

    master_unit = _unit(tenant, actor, MASTER_UNIT)
    target_unit = _unit(tenant, actor, MOVE_TARGET_UNIT)
    master_id = _meter(tenant, actor, MASTER_METER, master_unit)

    for asset_no in (SUB_METER_MOVED, SUB_METER_STAYS):
        if asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).exists():
            continue
        asset_services.create_asset(
            actor,
            {
                "asset_no": asset_no,
                "type": "sub_meter",
                "service": "electric",
                "unit": "kWh",  # BR-AST-009 / rule 3 — explicit, never inferred
                "meter_type": "sub_meter",
                "read_method": "walk_by",
                "multiplier": "1",
                "parent_asset_no": MASTER_METER,  # BR-AST-003
                "unit_id": master_unit,
                "install_date": "2026-01-05",
            },
        )

    children = sorted(
        asset_models.Asset.objects.filter(
            tenant=tenant, parent_asset_id=master_id
        ).values_list("asset_no", flat=True)
    )
    if children != sorted([SUB_METER_MOVED, SUB_METER_STAYS]):
        raise CohortCannotSeed(
            f"{MASTER_METER}'s children are {children}, not "
            f"{sorted([SUB_METER_MOVED, SUB_METER_STAYS])} — the Σ-subs group this "
            "journey recomputes does not exist, so nothing here may report success."
        )
    return {
        "master": MASTER_METER,
        "children": children,
        "target_unit_id": target_unit,
        "tolerance_pct": MISMATCH_TOLERANCE_PCT,
    }


# ── T4-03 · the wrongly-planned occupied unit, and its issued wrong bill ────


def ensure_wrong_plan_cohort(tenant, actor) -> dict[str, Any]:
    """T4-03's x-state: an OCCUPIED unit carrying the WRONG plan, plus the
    wrongly-priced ISSUED bill its step 4 routes to the J6 correction door.

    ⚠ **Fixture amendment 2026-08-22 (DEF-556).** The paragraph asks for
    *"June's bill … issued and wrong-plan-priced"*. June is inside the
    finance-signed LE-1 book (cutover 2026-06-30 → July 31), and an issued bill
    posts its journal entry at its service date, so a June bill restates a
    signed figure. The wrongly-priced issued bill is therefore **August's**, on
    its own cycle and its own account — the journey's assertion is that an
    issued wrong-plan bill exists and can only be corrected through J6, and the
    month it was issued in is not what it asserts.
    """
    ensure_flat_plan(tenant, actor)
    commercial = ensure_commercial_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=WRONG_PLAN_UNIT,
        meter_no=WRONG_PLAN_METER,
        account_no=WRONG_PLAN_ACCOUNT,
        plan=commercial,  # THE ERROR the journey corrects
        cycle_code=WRONG_PLAN_CYCLE,
    )
    invoices = _run(
        tenant,
        actor,
        cycle=built["cycle"],
        idempotency_key=WRONG_PLAN_RUN_KEY,
        issue=True,
    )
    invoice = invoices[0]
    return {
        "account_no": WRONG_PLAN_ACCOUNT,
        "unit_id": built["unit_id"],
        "wrong_plan": COMMERCIAL_PLAN_NAME,
        "correct_plan": PLAN_NAME,
        "invoice_no": getattr(invoice, "invoice_no", None) or str(invoice.pk),
        "invoice_total": str(Decimal(invoice.total).quantize(Decimal("0.01"))),
    }


# ── T4-12 · the tax-exempt account with an expiring certificate ─────────────


def ensure_expiring_exemption(tenant, actor) -> dict[str, Any]:
    """T4-12's x-state: a tax-exempt account, cert TX-EX-88121, expiry
    2026-07-31 — and a cycle its Aug run has somewhere to run.

    The expiry is DERIVED state (BR-CUS-063's CL-6 ruling: expired → warning,
    never auto-untag), so nothing here flips a flag as the date passes; the
    stored expiry IS the fixture. `prepare_run` is called read-only to prove
    the account is actually billable, because a journey whose step 2 is *"the
    Aug cycle bill run executes"* over an account no run can reach would report
    zero tax lines for the wrong reason — an empty answer, not an exempt one.

    ⚠ Fixture amendment 2026-08-22 (DEF-556): the paragraph's ACC-1049 belongs
    to the signed cast's numbering; this cohort's accounts live in the ACC-2xxx
    range so the two Julys cannot collide. Cert ref, expiry and the exemption
    itself — the load-bearing parts — are the paragraph's own.
    """
    plan = ensure_flat_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=EXEMPT_UNIT,
        meter_no=EXEMPT_METER,
        account_no=EXEMPT_ACCOUNT,
        plan=plan,
        cycle_code=EXEMPT_CYCLE,
        account_fields={
            "tax_exempt": True,
            "tax_exempt_ref": EXEMPT_CERT_REF,
            "tax_exempt_expires": EXEMPT_CERT_EXPIRY,
        },
    )
    prepared = _prepare(built["cycle"])
    ready = {data.account_no for data in prepared.ready}
    if EXEMPT_ACCOUNT not in ready:
        blocked = "; ".join(
            f"{problem.account_no}: {problem.detail}" for problem in prepared.blocked
        )
        raise CohortCannotSeed(
            f"{EXEMPT_ACCOUNT} is not READY on cycle {EXEMPT_CYCLE}, so this journey's "
            "Aug run would report zero tax lines because it billed NOTHING, not "
            f"because the account is exempt. blocked: {blocked or '(none listed)'}"
        )
    return {
        "account_no": EXEMPT_ACCOUNT,
        "cert_ref": EXEMPT_CERT_REF,
        "expires": EXEMPT_CERT_EXPIRY.isoformat(),
        "cycle": EXEMPT_CYCLE,
    }


# ── T5-14 · the account with no plan snapshot ───────────────────────────────


def ensure_no_plan_account(tenant, actor) -> dict[str, Any]:
    """T5-14's cutover DEFECT: Active account on a unit with NO plan.

    And then it PROVES the defect is the one the journey walks: `prepare_run`
    must place this account in `blocked` carrying `unit_has_no_plan`
    (apps/billing/gather.GATHER_NO_PLAN). Seeding the state without checking
    the refusal is how a journey asserting *"the run surfaces it as an
    exception"* passes over an empty exception list.
    """
    from apps.billing import gather as billing_gather

    built = _billable_unit(
        tenant,
        actor,
        label=NO_PLAN_UNIT,
        meter_no=NO_PLAN_METER,
        account_no=NO_PLAN_ACCOUNT,
        plan=None,  # THE defect — BR-MET-040 makes this unreachable by activation
        cycle_code=NO_PLAN_CYCLE,
    )
    prepared = _prepare(built["cycle"])
    reasons = {
        problem.reason
        for problem in prepared.blocked
        if problem.account_no == NO_PLAN_ACCOUNT
    }
    if billing_gather.GATHER_NO_PLAN not in reasons:
        raise CohortCannotSeed(
            f"{NO_PLAN_ACCOUNT} did not block with `{billing_gather.GATHER_NO_PLAN}` — "
            f"prepare_run reported {sorted(reasons) or 'nothing at all'} for it. The "
            "refusal this journey exists to walk is not happening, so the fixture is "
            "not the fixture."
        )
    if any(data.account_no == NO_PLAN_ACCOUNT for data in prepared.ready):
        raise CohortCannotSeed(
            f"{NO_PLAN_ACCOUNT} reached `ready` — billing found a price for an account "
            "with no snapshot, which is exactly what BR-CUS-014 sc.6 forbids."
        )
    return {
        "account_no": NO_PLAN_ACCOUNT,
        "cycle": NO_PLAN_CYCLE,
        "blocked_reason": billing_gather.GATHER_NO_PLAN,
    }


# ── T5-19 · the DRAFT run, and the TAMPER charge code ───────────────────────


def ensure_tamper_charge(tenant, actor):
    """T5-19's *"charge code TAMPER … configured"* — BR-BIL-019's whole point:
    even theft money enters as a CONFIGURED code, never a hand-typed amount.

    ⚠ **THE AMOUNT IS $250.00, NOT THE PARAGRAPH'S $500.00, AND THAT IS A PO
    RULING — DEF-563 (found 2026-08-22 by this fixture's own test).** Two
    ratified sources disagreed: EP-RAT-03 §4 said **$250.00** and the billing
    workbook's WE-11 said **$500.00**. The **PO ruled $250.00 on 2026-08-10**
    and made it a PLATFORM default; `seed_demo`'s own comment records that the
    workbook's 500.00 *"is not a second default — it is the WE-11 worked
    example and stays there"*. T5-19's Fixture paragraph quotes the workbook
    figure, so it predates the ruling.

    **A fixture may not settle that by overwriting the ruled figure.** A tenant
    that already carries TAMPER is left EXACTLY as seeded — the platform's
    number is the product's, not this file's — and where the code is absent it
    is created from `seed_demo.CHARGE_CODES`, imported rather than retyped, so
    the fixture can never become a third source (hard-won law 5). The journey's
    assertion is that no door lets a human type a dollar; WHICH configured
    amount the code carries is not what it tests, and the paragraph carries the
    dated amendment saying so.
    """
    from apps.rating import models as rating_models
    from apps.tenancy.management.commands import seed_demo

    charge = rating_models.Charge.objects.filter(tenant=tenant, code=TAMPER_CODE).first()
    if charge is not None:
        if charge.amount is None:
            raise CohortCannotSeed(
                f"the tenant's `{TAMPER_CODE}` charge code carries NO amount, so it is not a "
                "CONFIGURED code and BR-BIL-019's 'money enters by a code' has nothing to "
                "enter by. Seed the platform charge codes (`manage.py seed_demo --tenant "
                "<subdomain>`) before this cohort."
            )
        return charge

    platform = next(
        (row for row in seed_demo.CHARGE_CODES if row["code"] == TAMPER_CODE),
        None,
    )
    if platform is None:
        raise CohortCannotSeed(
            f"the platform charge-code fixture no longer carries `{TAMPER_CODE}`, so this "
            "fixture has no ruled amount to create it from and will not invent one."
        )
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=TAMPER_CODE,
        name=platform["name"],
        charge_type=platform["charge_type"],
        amount_rule=platform["amount_rule"],
        amount=Decimal(platform["amount"]),
    )


def ensure_draft_cohort(tenant, actor) -> dict[str, Any]:
    """T5-19's x-state: a DRAFT run whose computed lines total the dataset row,
    plus the TAMPER code. Nothing is released and nothing is issued — the
    journey walks the draft UI, every wizard and the API looking for a door
    that lets a human type a dollar, and a draft is where that door would be.

    ⚠ Fixture amendment 2026-08-22 (DEF-556): the paragraph pins the draft to
    ACC-1042 and RUN-2607-A, a July run on the signed cast's account. The
    account and the run id move; the **97.41 computed total** the journey reads
    off the draft is the load-bearing part and is unchanged.
    """
    plan = ensure_flat_plan(tenant, actor)
    charge = ensure_tamper_charge(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=DRAFT_UNIT,
        meter_no=DRAFT_METER,
        account_no=DRAFT_ACCOUNT,
        plan=plan,
        cycle_code=DRAFT_CYCLE,
    )
    invoices = _run(
        tenant, actor, cycle=built["cycle"], idempotency_key=DRAFT_RUN_KEY, issue=False
    )
    invoice = invoices[0]
    total = Decimal(invoice.total).quantize(Decimal("0.01"))
    if total != FLAT_TOTAL:
        raise CohortCannotSeed(
            f"the DRAFT totals {total}, not the dataset row's {FLAT_TOTAL} "
            "(money-triples `flat,cycle,full`). T5-19 reads that figure off the "
            "draft, so a draft priced at anything else is the wrong fixture."
        )
    if invoice.status != "draft":
        raise CohortCannotSeed(
            f"the run's invoice is `{invoice.status}`, not `draft` — T5-19 asserts "
            "over a PRE-ISSUE draft and an issued bill is a different assertion."
        )
    return {
        "account_no": DRAFT_ACCOUNT,
        "draft_total": str(total),
        "charge_code": charge.code,
        "charge_amount": str(Decimal(charge.amount).quantize(Decimal("0.01"))),
    }


# ── T4-21 / T7-15 · budget billing ──────────────────────────────────────────


def ensure_budget_plan(tenant, actor):
    """A published flat plan carrying BR-RAT-043's budget flag — what
    `budget.eligibility` reads before an account may enrol."""
    return ensure_priced_plan(
        tenant,
        actor,
        name=BUDGET_PLAN_NAME,
        code=BUDGET_PLAN_CODE,
        unit_price=FLAT_UNIT_PRICE,
        base=FLAT_BASE,
        budget_billing=True,
    )


def _budget_settings(actor, **changes):
    """Write the S69 budget parameters through the REAL settings service."""
    from apps.tenancy import services as tenancy_services

    return tenancy_services.save_settings_family(actor, "budget-billing", changes)


def ensure_budget_band_account(tenant, actor) -> dict[str, Any]:
    """T4-21's x-state: ACC-2047 enrolled, computed level **$242** (WE-8).

    The level is COMPUTED by `budget_service.enroll` from the trailing actuals,
    not typed: twelve months of 242.00 sum to WE-8's **2,904**, and the
    workbook's level is that average. If the engine ever computes anything else
    from those actuals this refuses, which is the only way a fixture can hold a
    signed figure without becoming a second copy of it (hard-won law 5).

    ⚠ Fixture amendment 2026-08-22 (DEF-556): ACC-1047 → ACC-2047, the ACC-2xxx
    range this cohort's accounts live in. The **$242** level, the $2,904
    trailing total and the ±30% band are the paragraph's own and are unmoved.
    """
    from apps.billing import budget_service

    plan = ensure_budget_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=BUDGET_BAND_UNIT,
        meter_no=BUDGET_BAND_METER,
        account_no=BUDGET_BAND_ACCOUNT,
        plan=plan,
        cycle_code=None,
    )
    account = built["account"]
    status = budget_service.status_for(account.id)
    if status is None:
        trailing = tuple(WE8_MONTHLY for _ in range(12))
        if sum(trailing) != WE8_TRAILING_TOTAL:
            raise CohortCannotSeed(
                f"the trailing actuals sum to {sum(trailing)}, not WE-8's "
                f"{WE8_TRAILING_TOTAL} — the level this journey overrides would not "
                "be the workbook's."
            )
            
        status = budget_service.enroll(
            actor=actor,
            account_id=account.id,
            trailing_actuals=trailing,
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=date(2026, 8, 1),
        )
    level = Decimal(status.level).quantize(Decimal("1"))
    if level != WE8_LEVEL:
        raise CohortCannotSeed(
            f"the engine computed level {level} from WE-8's {WE8_TRAILING_TOTAL} "
            f"trailing actuals, not the workbook's {WE8_LEVEL}. The band this journey "
            "enforces is ±30% OF THAT NUMBER, so a different level is a different test."
        )
    return {
        "account_no": BUDGET_BAND_ACCOUNT,
        "level": str(level),
        "trailing_total": str(WE8_TRAILING_TOTAL),
    }


def ensure_budget_params_account(tenant, actor) -> dict[str, Any]:
    """T7-15's x-state: settle_up_month **4**, relevel cadence **6**, and
    ACC-2140 enrolled at level **97** with variance **-0.41** after one bill.

    The variance is PRODUCED, not typed: `record_bill` puts the money-triples
    `flat,budget` actual (97.41) against the level (97) and the engine's own
    arithmetic leaves -0.41 — the CSV's own note. A typed variance would be a
    second copy of a derived figure and would go stale silently.

    ⚠ Fixture amendment 2026-08-22: ACC-1140 → ACC-2140 (the cohort's range).
    NOT SEEDED, and named rather than faked: the paragraph's *"April 2026
    settle-up already billed (its line issued)"*. An issued settle-up line
    dated April 2026 sits before the LE-1 cutover (2026-06-30), so it would
    post a journal entry into the signed book — DEF-556 exactly. The journey's
    step is that changing `settle_up_month` does not disturb an already-issued
    settle-up; that assertion needs a settle-up bill this cohort cannot lawfully
    issue, so it is reported here instead of being back-dated.
    """
    from apps.billing import budget_service

    plan = ensure_budget_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=T715_UNIT,
        meter_no=T715_METER,
        account_no=T715_ACCOUNT,
        plan=plan,
        cycle_code=None,
    )
    account = built["account"]

    _budget_settings(
        actor,
        settle_up_month=T715_SETTLE_UP_MONTH,
        relevel_cadence_months=T715_RELEVEL_CADENCE,
    )

    status = budget_service.status_for(account.id)
    if status is None:
        # Twelve months of the level itself → compute_level returns 97 exactly,
        # which is the money-triples `flat,budget` level. No figure is typed
        # into the status row; the engine computes it, as it does in production.
        status = budget_service.enroll(
            actor=actor,
            account_id=account.id,
            trailing_actuals=tuple(T715_LEVEL for _ in range(12)),
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=T715_LEVELLED_AT,
        )
        budget_service.record_bill(
            account_id=account.id,
            actual=T715_ACTUAL,
            on_date=date(2026, 9, 1),
            bill_type="cycle",
            actor=actor,
        )
        status = budget_service.status_for(account.id)

    level = Decimal(status.level).quantize(Decimal("1"))
    variance = Decimal(status.variance_balance).quantize(Decimal("0.01"))
    if level != T715_LEVEL or variance != T715_VARIANCE:
        raise CohortCannotSeed(
            f"budget status is level {level} / variance {variance}, not the "
            f"money-triples `flat,budget` row's {T715_LEVEL} / {T715_VARIANCE}. The "
            "running variance is what T7-15 asserts a settings save may never touch, "
            "so a different one is a different test."
        )
    if status.settle_up_month != T715_SETTLE_UP_MONTH:
        raise CohortCannotSeed(
            f"the enrolled status carries settle_up_month {status.settle_up_month}, "
            f"not the seeded {T715_SETTLE_UP_MONTH} — the parameter this journey "
            "changes is not the one the account is on."
        )
    return {
        "account_no": T715_ACCOUNT,
        "level": str(level),
        "variance": str(variance),
        "settle_up_month": status.settle_up_month,
        "relevel_cadence_months": T715_RELEVEL_CADENCE,
        "last_leveled_at": str(status.last_leveled_at),
    }


# ── CR-014 GROUP 4 · the SECOND-TENANT cohorts (W11 lane, 2026-08-22) ───────
#
# Group 4's journeys need a tenant that is NOT brazos-bend: a fresh signup
# whose currency is still settable, and a second tenant for the cross-tenant
# refusals. Two things make this its own group rather than another extension:
#
# 1. **A second tenant is PROVISIONED, never constructed.** Everything these
#    journeys assert about a new tenant — the trial subscription, the owner and
#    their System Admin membership, the seeded chart of accounts, the number
#    series, the enabled services — is provisioning's OUTPUT. A fixture that
#    inserted a `tenants` row and hand-built the rest would seed a world no
#    signup ever produces, and the journeys would pass over it. So this calls
#    `apps.tenancy.services.provision_tenant`, the same service S114 commits,
#    which is idempotent on the subdomain (a replay returns the existing tenant
#    untouched — CLAUDE.md rule 6 for free).
# 2. **Every write lands in the NEW tenant's context.** `app.tenant_id` is set
#    per tenant and RLS is FORCE (hard rule 1), so a second-tenant cohort built
#    inside brazos-bend's context would be refused by the database — correctly.
#    `_in_tenant` below is the only place this module switches context, and it
#    switches it explicitly rather than by leaving one unset.
#
# ⚠ **THE SUBDOMAINS ARE HYPHENATED, EXACTLY AS THE JOURNEYS WRITE THEM.**
# BR-TEN-011's grammar allows `[a-z0-9-]`, so `maple-creek` is a lawful
# subdomain and there is no reason to flatten it the way `brazosbend` is
# flattened. Where a journey names a tenant, that name is used.

MAPLE_CREEK_SUBDOMAIN = "maple-creek"
MAPLE_CREEK_NAME = "Maple Creek Utilities"  # T7-09's own name
#: T4-22 states this address verbatim; T7-09 names the persona "Joel Tremblay".
#: One tenant has ONE owner, so the EMAIL is T4-22's (it is the only one either
#: paragraph pins) and the NAME is T7-09's persona — the same posture T5-15 took
#: with Priya: the ROLE is what the journeys assert, the person is a persona.
MAPLE_CREEK_OWNER_EMAIL = "pat@maplecreek.example"
MAPLE_CREEK_OWNER_NAME = "Joel Tremblay"
#: T4-22's cast: maple-creek's FIRST bill prices the money-triples row, so its
#: world is the flat plan cloned — *"fixture rates cloned from the Brazos Bend
#: flat plan so money-triples apply"* (T7-09).
MAPLE_CREEK_ACCOUNT = "ACC-MC-1001"
MAPLE_CREEK_UNIT = "MC-1"
MAPLE_CREEK_METER = "MTR-MC-0001"

LAKEVIEW_SUBDOMAIN = "lakeview-mud"
LAKEVIEW_NAME = "Lakeview MUD"
LAKEVIEW_OWNER_EMAIL = "admin@lakeviewmud.example"
LAKEVIEW_OWNER_NAME = "Lakeview MUD System Admin"
#: T5-22's own cast: *"Premises PRM-031 'Harbor Tower'"*, 40 floors.
HARBOR_TOWER = "Harbor Tower"
HARBOR_TOWER_REF = "PRM-031"
#: T5-21's own counts: one file of 12,481 rows, and the same content split
#: 10,000 + 2,481. The cap they cross is `assets.services.IMPORT_ROW_CAP`
#: (BR-AST-034), read from the code rather than retyped here.
CUTOVER_ROWS = 12_481
CUTOVER_SPLIT_FIRST = 10_000
CUTOVER_SPLIT_SECOND = CUTOVER_ROWS - CUTOVER_SPLIT_FIRST  # 2,481

#: Generated fixture files live here. They are BUILT, never committed: 12,481
#: rows of CSV is a megabyte of derived data, and a derived file in git is the
#: second source hard-won law 5 forbids.
GENERATED_DIR = "08-qa/01-e2e/fixtures/generated"

SECOND_TENANT_PASSWORD = "E2E!fixture!passw0rd"  # a fixture tenant's own, never a real one


def _in_tenant(tenant_id):
    from core import tenancy as core_tenancy

    return core_tenancy.tenant_context(tenant_id)


def tenant_actor(tenant):
    """The tenant's OWNER, carrying their own membership role.

    The same posture `seed_journey_fixture.tenant_and_actor` takes for
    brazos-bend, and for the same reason: `require_role` reads `actor.role`,
    the role lives on `TenantMembership`, and a fixture that attached
    `role="system_admin"` by hand would be seeding PAST every guard instead of
    through it. If a service refuses this actor, the refusal is real.
    """
    from types import SimpleNamespace

    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
    if user is None:
        raise CohortCannotSeed(
            f"tenant `{tenant.subdomain}` has no user — provisioning creates the owner "
            "(BR-TEN-001); if that failed, the fix is there and not here."
        )
    membership = (
        identity_models.TenantMembership.objects.filter(tenant=tenant, user=user)
        .select_related("role")
        .first()
    )
    if membership is None:
        raise CohortCannotSeed(
            f"{user.email} holds no TenantMembership in `{tenant.subdomain}`, so no role — "
            "every guarded service would refuse this actor."
        )
    return SimpleNamespace(
        id=user.id, pk=user.id, user=user, email=user.email, role=membership.role.code
    )


def ensure_second_tenant(*, subdomain, name, owner_email, owner_name, services=("electric",)):
    """Provision one fixture tenant through the REAL signup service.

    `provision_tenant` is idempotent on the subdomain: a replay with the same
    subdomain and owner email returns the EXISTING tenant unchanged, and
    deliberately mints no session on that path. So a re-booted stack re-runs
    this and writes nothing twice.

    ⚠ **`state` IS DELIBERATELY OMITTED, and that is a real limitation rather
    than an oversight.** T7-09 places Maple Creek in **Saskatchewan**, and
    signup validates `state` against `selectors.us_state_code` — a US-state
    lookup with no Canadian provinces in it. Passing "Saskatchewan" would be
    refused `signup.state_unknown`, which is the product correctly reporting
    that it models US states only. The tenant is therefore provisioned with no
    state, and the journey's Saskatchewan/America-Regina detail is REPORTED as
    unseedable rather than faked into a US state that would render on a bill.
    """
    from apps.tenancy import models as tenancy_models
    from apps.tenancy import services as tenancy_services

    tenancy_services.provision_tenant(
        {
            "name": name,
            "subdomain": subdomain,
            "services": list(services),
            # The signup DEFAULT. T4-22/T7-09 are about SETTING the currency
            # while no financial record exists, so a fixture that arrived
            # already on CAD would have performed the journey's own step 1.
            "currency": "USD",
            "plan": "growth",
            "load_defaults": True,
            "owner": {
                "full_name": owner_name,
                "email": owner_email,
                "password": SECOND_TENANT_PASSWORD,
                "phone": None,
            },
        }
    )
    tenant = tenancy_models.Tenant.objects.filter(subdomain=subdomain).first()
    if tenant is None:
        raise CohortCannotSeed(
            f"provisioning reported success and no tenant `{subdomain}` exists — nothing "
            "downstream of this may report success either."
        )
    return tenant


def _assert_no_financial_records(tenant) -> dict[str, int]:
    """T7-09's *"zero financial records at start"*, PROVED not assumed.

    This is the whole precondition of a currency-lock journey: the currency is
    settable only while nothing financial exists, so a fixture that left an
    issued bill behind would make step 1 fail for a reason the journey never
    describes — and a fixture that never checked would not know.
    """
    from apps.billing import models as billing_models
    from apps.payments import models as payment_models

    counts = {
        "issued_invoices": billing_models.Invoice.objects.filter(
            tenant=tenant, status="issued"
        ).count(),
        "payments": payment_models.Payment.objects.filter(tenant=tenant).count(),
    }
    if any(counts.values()):
        raise CohortCannotSeed(
            f"the fixture tenant already holds {counts} — the currency-lock journeys need "
            "ZERO financial records at start, because the lock is what having one CAUSES. "
            "A cohort that pre-locked the currency tests nothing."
        )
    return counts


def ensure_maple_creek_cohort(_calling_tenant=None, _calling_actor=None) -> dict[str, Any]:
    """T4-22 + T7-09 — one fresh tenant, priced but unbilled.

    ⚠ **THE TWO IGNORED ARGUMENTS ARE THE POINT (DEF-570, 2026-08-22).** Every
    group-3/4 builder is reached from `seed_journey_fixture._extension`, which
    calls `builder(tenant, actor)` — the CALLING tenant and its actor. A
    second-tenant builder uses neither (it provisions and enters its own
    tenant, hard rule 1), and when this was authored as `ensure_…(actor)` all
    four second-tenant seeders raised `TypeError: … takes 1 positional argument
    but 2 were given` on a booted stack while their tests, which call this
    function directly, stayed green. So the seam's shape is honoured here and
    the arguments are named for what they are rather than dropped.
    `tests/test_cr014_seeder_contract.py` holds every builder to it.

    Both journeys are the currency lifecycle: set the currency while nothing
    financial exists, then issue the first bill and find it LOCKED. So the
    fixture must supply everything the first bill needs and issue NOTHING.

    *"fixture rates cloned from the Brazos Bend flat plan so money-triples
    apply"* (T7-09) is honoured by building the SAME plan this module builds
    for brazos-bend — same tier price, same base, same four authorities —
    through the same function, so the two can never drift into pricing
    differently. T4-22's *"maple-creek's first bill uses the money-triples row
    `flat,cycle,full`: 97.41"* then follows from the plan rather than from a
    figure typed into a second tenant.
    """
    tenant = ensure_second_tenant(
        subdomain=MAPLE_CREEK_SUBDOMAIN,
        name=MAPLE_CREEK_NAME,
        owner_email=MAPLE_CREEK_OWNER_EMAIL,
        owner_name=MAPLE_CREEK_OWNER_NAME,
    )
    with _in_tenant(tenant.id):
        owner = tenant_actor(tenant)
        plan = ensure_flat_plan(tenant, owner)
        built = _billable_unit(
            tenant,
            owner,
            label=MAPLE_CREEK_UNIT,
            meter_no=MAPLE_CREEK_METER,
            account_no=MAPLE_CREEK_ACCOUNT,
            plan=plan,
            cycle_code=CYCLE_CODE,
        )
        prepared = _prepare(built["cycle"])
        ready = {data.account_no for data in prepared.ready}
        if MAPLE_CREEK_ACCOUNT not in ready:
            blocked = "; ".join(
                f"{problem.account_no}: {problem.detail}" for problem in prepared.blocked
            )
            raise CohortCannotSeed(
                f"{MAPLE_CREEK_ACCOUNT} is not READY on {tenant.subdomain}, so this tenant's "
                "FIRST bill — the one that locks the currency — could not be produced. "
                f"blocked: {blocked or '(none listed)'}"
            )
        counts = _assert_no_financial_records(tenant)

    return {
        "tenant": tenant.subdomain,
        "tenant_id": str(tenant.id),
        "currency": tenant.currency,
        "owner": MAPLE_CREEK_OWNER_EMAIL,
        "account_no": MAPLE_CREEK_ACCOUNT,
        "plan": plan.code,
        "cycle": CYCLE_CODE,
        "financial_records": counts,
    }


def ensure_lakeview_cohort(_calling_tenant=None, _calling_actor=None) -> dict[str, Any]:
    """T5-21 + T5-22 — the large-tenant cohort and its Harbor Tower premises.

    Both journeys are REFUSALS at a cap, so what they need is a tenant with the
    right SHAPE, never 12,481 real assets: T5-21's rows are rejected AT UPLOAD
    (`assets.services.IMPORT_ROW_CAP`, BR-AST-034) and never reach the table,
    and T5-22's 3,200 units are refused before a single unit is created.
    Seeding the rows would be seeding the state the product exists to prevent.
    """
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_premises

    tenant = ensure_second_tenant(
        subdomain=LAKEVIEW_SUBDOMAIN,
        name=LAKEVIEW_NAME,
        owner_email=LAKEVIEW_OWNER_EMAIL,
        owner_name=LAKEVIEW_OWNER_NAME,
        services=("water",),  # a MUD sells water — BR-MET service gating is real
    )
    with _in_tenant(tenant.id):
        owner = tenant_actor(tenant)
        premises = metering_models.Premises.objects.filter(
            tenant=tenant, address_line=HARBOR_TOWER
        ).first()
        if premises is None:
            make_premises(owner, address_line=HARBOR_TOWER, services_available=["water"])
            premises = metering_models.Premises.objects.get(
                tenant=tenant, address_line=HARBOR_TOWER
            )
        units = metering_models.Unit.objects.filter(tenant=tenant, premises=premises).count()

    return {
        "tenant": tenant.subdomain,
        "premises": HARBOR_TOWER,
        "premises_ref": HARBOR_TOWER_REF,
        "units_on_premises": units,
    }


def _cutover_csv(rows: int, first_asset: int) -> str:
    """`rows` asset-import rows in the published template's own columns.

    The header is `apps.assets.services.IMPORT_COLUMNS`' first alias for each
    target, so the file is the contract the importer publishes rather than a
    guess at it. Content is deterministic — the same call always writes the
    same bytes — because a fixture that changed between boots is a fixture
    whose failures cannot be reproduced.
    """
    header = "asset #,type,service,uom,multiplier,register digits,install date,status\n"
    body = "".join(
        f"MTR-LV-{first_asset + i:06d},meter,water,gal,1,5,2026-01-05,active\n"
        for i in range(rows)
    )
    return header + body


def ensure_import_cap_csvs(repo_root) -> dict[str, Any]:
    """T5-21's three files — the over-cap one and the two that split it.

    ⚠ **GENERATED, NOT COMMITTED.** 12,481 rows is a megabyte of derived data,
    and a derived file in git drifts from its generator within a day
    (hard-won law 5). The directory carries its own `.gitignore`.

    The split is asserted to REJOIN: 10,000 + 2,481 rows of body must equal the
    single file's body exactly, or T5-21's *"same content, split"* is not what
    the fixture holds and the journey's second half proves nothing.
    """
    import pathlib

    from apps.assets import services as asset_services

    if CUTOVER_SPLIT_FIRST != asset_services.IMPORT_ROW_CAP:
        raise CohortCannotSeed(
            f"the split's first file is {CUTOVER_SPLIT_FIRST} rows and the importer's cap is "
            f"{asset_services.IMPORT_ROW_CAP} (BR-AST-034). T5-21's second half is that a "
            "file AT the cap is accepted, so a split that does not sit exactly on the cap "
            "tests a different boundary."
        )
    if CUTOVER_ROWS <= asset_services.IMPORT_ROW_CAP:
        raise CohortCannotSeed(
            f"the whole file is {CUTOVER_ROWS} rows and the cap is "
            f"{asset_services.IMPORT_ROW_CAP} — it would be ACCEPTED, and the refusal this "
            "journey walks would never happen."
        )

    directory = pathlib.Path(repo_root) / GENERATED_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".gitignore").write_text(
        "# CR-014: generated journey fixture data. Derived from\n"
        "# 06-backend/tests/journey_cohort_fixtures.py — never committed (law 5).\n"
        "*\n",
        encoding="utf-8",
    )

    whole = _cutover_csv(CUTOVER_ROWS, 1)
    part_one = _cutover_csv(CUTOVER_SPLIT_FIRST, 1)
    part_two = _cutover_csv(CUTOVER_SPLIT_SECOND, CUTOVER_SPLIT_FIRST + 1)
    body = lambda text: text.split("\n", 1)[1]  # noqa: E731 — drop the header
    if body(part_one) + body(part_two) != body(whole):
        raise CohortCannotSeed(
            "the two split files do not rejoin into the whole one, so they are not "
            "*'the same content split'* and T5-21's second half asserts nothing."
        )

    written = {}
    for filename, text in (
        ("assets-cutover.csv", whole),
        ("assets-cutover-1.csv", part_one),
        ("assets-cutover-2.csv", part_two),
    ):
        path = directory / filename
        path.write_text(text, encoding="utf-8")
        written[filename] = {"rows": text.count("\n") - 1, "bytes": len(text)}
    return {"directory": str(directory), "files": written, "cap": asset_services.IMPORT_ROW_CAP}



# ── CR-014 ROUND 3 · the group-3 remainders, and what they cost ─────────────
#
# The round-2 record itemised eleven group-3 journeys with no seeder. Two of
# them were labelled *"honest remaining work"* — T4-19 and T7-14 — meaning
# nothing blocked them and nobody had reached them. They are built here.
#
# ⚠ **T4-19 REQUIRED AN AUTHORING DECISION, and it is written down rather than
# taken silently.** Its paragraph pins bill A due **Jul 20** and bill B due
# **Fri Aug 14** — both inside or adjacent to the finance-signed window, so an
# issued bill on either date posts a journal entry into LE-1's July (DEF-556).
# The journey does not assert the DATES; it asserts the WEEKDAY SHAPE, because
# the whole subject is that five CALENDAR days and five BUSINESS days from the
# same due date land on different boundaries, and only a Friday due date makes
# the two visibly differ. So the pair moves **+70 days — ten whole weeks —
# which preserves every weekday exactly**: Mon Jul 20 → **Mon Sep 28**, Fri Aug
# 14 → **Fri Oct 23**, and the mode switch the journey performs at Sat Aug 1
# lands at Sat Oct 10, still between the two. A shift of one month would have
# moved Friday to a Monday and quietly deleted the journey's subject.

T419_ACCOUNT = "ACC-2419"
T419_UNIT = "4M"
T419_METER = "MTR-0419"
T419_CYCLE = "08-E2E-T419"
#: Ten whole weeks — the ONLY shift that preserves a weekday. See the note above.
T419_SHIFT_DAYS = 70
T419_A_PERIOD = (AUG_START, AUG_END)
T419_A_SERVICE_DATE = AUG_SERVICE_DATE
T419_A_BILL_DATE = date(2026, 9, 7)  # Monday
T419_A_DUE = date(2026, 9, 28)  # Monday — the paragraph's Mon Jul 20 + 70 days
T419_B_PERIOD = (date(2026, 9, 1), date(2026, 9, 30))
T419_B_SERVICE_DATE = date(2026, 9, 30)
T419_B_BILL_DATE = date(2026, 10, 2)  # Friday
T419_B_DUE = date(2026, 10, 23)  # Friday — the paragraph's Fri Aug 14 + 70 days
T419_A_KEY = "2026-08|E2E-T419-A"
T419_B_KEY = "2026-09|E2E-T419-B"
T419_ISSUED_A = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)
T419_ISSUED_B = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
T419_GRACE_DAYS = 5  # BR-BIL-008's default, which is also the paragraph's figure
T419_GRACE_MODE = "calendar"  # pre-change; switching it is the journey's step 2

# ── T7-14 · the guardrail cohort: a trailing average and a draft over it ────
T714_ACCOUNT = "ACC-1130"
T714_SIBLING = "ACC-1131"
T714_UNIT = "4N"
T714_SIBLING_UNIT = "4P"
T714_METER = "MTR-0530"
T714_SIBLING_METER = "MTR-0531"
T714_CYCLE = "08-E2E-T714"
#: Three ISSUED cycles, so the trailing average is PRODUCED and never typed.
#:
#: ⚠ **AUGUST, SEPTEMBER, NOVEMBER — OCTOBER IS SKIPPED, AND SKIPPING IT IS THE
#: WHOLE POINT (DEF-576, 2026-08-22).** This cohort first billed Aug/Sep/OCT and
#: broke `seed_j19` on the demo stack: OQ-333's applied ruling moves the LE-1
#: book to **October 2026** when July is taken, and the seeder verifies the
#: destination month is EMPTY before posting a line. Two issued bills dated
#: Oct 31 made it refuse — *"the fixture month October 2026 already holds 2
#: posted entries … those entries are somebody else's book"* — which is the
#: refusal working exactly as designed, on a collision this cohort caused.
#:
#: **THE FIXTURE-MONTH CALENDAR ON brazos-bend, which every future cohort must
#: read before choosing a month to ISSUE in:**
#:
#:   · **Jun 30 – Jul 31 2026** — the finance-signed LE-1 window (DEF-556).
#:     Nothing may post here. Ever.
#:   · **Aug 2026** — the CR-014 flat cohort's issued bill, and shared freely:
#:     several cohorts bill August and that is fine.
#:   · **Sep 2026** — where OQ-218's ruling parks LE-4's 500.00 accrual.
#:   · **Oct 2026** — RESERVED for the LE-1 book when OQ-333's shift fires.
#:     An issued bill here makes J19 refuse.
#:   · **Nov 2026** — free, and the LAST month a read can be dated in: the
#:     `meter_reads` partition window ends 2026-11-30 (see T714_BACKBILL_MONTHS).
T714_CYCLE_MONTHS = (
    (date(2026, 8, 1), date(2026, 8, 31), date(2026, 8, 31), date(2026, 9, 1)),
    (date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 30), date(2026, 10, 1)),
    (date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 30), date(2026, 12, 1)),
)
#: The three UNBILLED months the back-bill draft covers — a catch-up over
#: history, which is what a back-bill IS (BR-BIL-018).
#:
#: ⚠ **THEY ARE BEFORE THE ISSUED THREE, NOT AFTER, AND THE REASON IS A HARD
#: LIMIT OF THE DATABASE.** The first version of this cohort put them at Nov
#: 2026 – Jan 2027 and could not commit the reads they need:
#: `IntegrityError: no partition of relation "meter_reads" found for row.
#: DETAIL: Partition key of the failing row contains (read_at) =
#: (2026-12-28 00:00:00+00)`. `meter_reads` is RANGE-partitioned monthly and
#: metering 0003 bootstrapped a FIXED window — 24 months back, 3 ahead — which
#: on this schema ends at **2026-11-30**; the create-ahead job that renews it
#: (DEF-029's fix) needs a scheduler this product does not yet run (DEF-042's
#: own finding). So **no fixture anywhere may date a read past the last
#: partition**, and this one does not.
#:
#: A DRAFT posts no journal entry (BR-BIL-004 — "a draft is not money"), so
#: unlike an issued bill these months may sit before the flat cohort's August
#: and inside the calendar year the LE-1 book lives in: nothing is posted, so
#: nothing is restated. DEF-556 constrains ISSUED bills, not drafts.
T714_BACKBILL_MONTHS = (
    (date(2026, 4, 1), date(2026, 4, 30)),
    (date(2026, 5, 1), date(2026, 5, 31)),
    (date(2026, 6, 1), date(2026, 6, 30)),
)
#: The read chain starts before the back-billed months and runs to the last
#: issued cycle: Mar 31 head, then the 28th of every month through November.
T714_READ_HEAD = "2026-03-31"
T714_READ_MONTHS = 8  # Mar 31 head → the 28th of every month through November
T714_BACKBILL_REASON = "cutover-catchup"
T714_GUARDRAIL_PCT = "200"  # r10 #6 / BR-BIL-029's own default

# ── T5-04 · the THIRD tenant, and why it cannot be maple-creek ──────────────
#
# T5-04's paragraph calls its tenant B **maple-ridge**; T7-09's calls the CAD
# tenant **maple-creek**. The round-2 record read that as a naming conflict to
# resolve. It is not one, and the reason is structural: **T4-22/T7-09 need a
# tenant with ZERO financial records** (the currency lock is what having one
# CAUSES — `_assert_no_financial_records` refuses otherwise) while **T5-04
# needs its tenant B to CARRY a named bill** for the sweep to fail to reach.
# One tenant cannot be both. The two names describe two tenants, so both names
# are honoured and neither journey is bent to the other.
MAPLE_RIDGE_SUBDOMAIN = "maple-ridge"
MAPLE_RIDGE_NAME = "Maple Ridge Water & Power"
MAPLE_RIDGE_ACCOUNT = "ACC-9001"
MAPLE_RIDGE_UNIT = "MR-1"
MAPLE_RIDGE_METER = "MTR-MR-9001"
MAPLE_RIDGE_CYCLE = "08-E2E-MR"
MAPLE_RIDGE_RUN_KEY = "2026-08|E2E-MAPLE-RIDGE"
MAPLE_RIDGE_CURRENCY = "CAD"  # T5-04: "the T7 CAD sample tenant"


def _read_series(tenant, actor, asset_id, series) -> None:
    """Commit a chain of reads, each carrying its prior value and its unit.

    `_reads` above is the two-read shape the flat cohort needs. T4-19 bills two
    months and T7-14 bills three and then back-bills three more, so those need
    a CHAIN — and a chain is where a fixture quietly goes wrong: a read with no
    prior value prices a month against zero. Every entry here states its own
    prior explicitly (CLAUDE.md rule 3 for the unit; BR-MET-019 for the prior).
    """
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    prior = None
    for day, value in series:
        if not MeterRead.objects.filter(
            tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
        ).exists():
            commit_read(
                actor,
                asset_id,
                day=day,
                value=str(value),
                prior_value=str(prior) if prior is not None else None,
                consumption=str(value - prior) if prior is not None else None,
                unit="kWh",
            )
        prior = value


def _monthly_series(first_day: str, months: int, *, start_value=PRIOR_READ_VALUE):
    """`months` + 1 reads, 700 kWh apart, on the 28th of each month.

    The first entry is the opening HEAD (no consumption of its own); each later
    one adds exactly the dataset row's 700 kWh, so every month prices at the
    money-triples `flat,cycle` figures rather than at something this file chose.
    """
    series = [(first_day, start_value)]
    day = date.fromisoformat(first_day)
    value = start_value
    for _ in range(months):
        index = day.month  # next month, same 28th
        year, month = (day.year + index // 12, index % 12 + 1)
        day = date(year, month, 28)
        value = value + FLAT_USAGE_QTY.quantize(Decimal("1"))
        series.append((day.isoformat(), value))
    return tuple(series)


def _billing_settings(actor, **changes):
    """S66 Billing defaults through the REAL settings service (BR-TEN-024)."""
    from apps.tenancy import services as tenancy_services

    return tenancy_services.save_settings_family(actor, "billing-defaults", changes)


def ensure_grace_pre_state(tenant, actor) -> dict[str, Any]:
    """T4-19 — two ISSUED bills, one due a MONDAY and one due a FRIDAY.

    The journey's subject is that a grace window counted in calendar days and
    the same window counted in business days land on different dates, and that
    switching the mode never re-evaluates a determination already made. So the
    fixture is exactly two things: the tenant's grace config BEFORE the switch
    (5 days, calendar — both BR-BIL-008 defaults, written explicitly so a
    stack whose settings were edited by another journey still starts here), and
    two issued bills whose due dates carry the paragraph's weekday shape.

    ⚠ The due dates are NOT typed onto the invoices. They are produced by
    BR-BIL-024 — bill date + the cycle's due-days — and this refuses unless the
    engine's answer is the Monday and the Friday the journey needs. A fixture
    that wrote a due date would be asserting its own arithmetic.
    """
    plan = ensure_flat_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=T419_UNIT,
        meter_no=T419_METER,
        account_no=T419_ACCOUNT,
        plan=plan,
        cycle_code=T419_CYCLE,
        reads=False,
    )
    _read_series(tenant, actor, built["meter_id"], _monthly_series("2026-07-31", 2))

    settings_after = _billing_settings(
        actor, late_grace_days=T419_GRACE_DAYS, late_grace_mode=T419_GRACE_MODE
    )

    bills = {}
    for label, (period, service_date, bill_date, key, issued_at, wanted_due) in {
        "A": (T419_A_PERIOD, T419_A_SERVICE_DATE, T419_A_BILL_DATE, T419_A_KEY, T419_ISSUED_A, T419_A_DUE),
        "B": (T419_B_PERIOD, T419_B_SERVICE_DATE, T419_B_BILL_DATE, T419_B_KEY, T419_ISSUED_B, T419_B_DUE),
    }.items():
        invoices = _run(
            tenant,
            actor,
            cycle=built["cycle"],
            idempotency_key=key,
            issue=True,
            period_start=period[0],
            period_end=period[1],
            service_date=service_date,
            bill_date=bill_date,
            issued_at=issued_at,
        )
        invoice = invoices[0]
        due = getattr(invoice, "due_date", None)
        if due != wanted_due:
            raise CohortCannotSeed(
                f"bill {label} came out due {due}, not {wanted_due} "
                f"({wanted_due:%A}). BR-BIL-024 makes the due date bill date + the cycle's "
                f"due-days ({DUE_DAYS}); this fixture's whole subject is the WEEKDAY the "
                "grace clock counts from, so a due date on the wrong day of the week is a "
                "different journey and must not report success."
            )
        bills[label] = invoice

    return {
        "account_no": T419_ACCOUNT,
        "cycle": T419_CYCLE,
        "grace_days": settings_after.get("late_grace_days"),
        "grace_mode": settings_after.get("late_grace_mode"),
        "bill_a": getattr(bills["A"], "invoice_no", None) or str(bills["A"].pk),
        "bill_a_due": str(T419_A_DUE),
        "bill_a_weekday": f"{T419_A_DUE:%A}",
        "bill_b": getattr(bills["B"], "invoice_no", None) or str(bills["B"].pk),
        "bill_b_due": str(T419_B_DUE),
        "bill_b_weekday": f"{T419_B_DUE:%A}",
        "shift_days": T419_SHIFT_DAYS,
    }


def money_triples_row(shape: str, bill_type: str, payment: str) -> dict[str, str]:
    """One row of `08-qa/01-e2e/expected/money-triples.csv`, read not retyped.

    The dataset is the journeys' own expectation file. `flat,backbill,full`
    states taxable **267.00**, tax **25.23**, total **292.23** — T7-14's own
    figures — and reading them keeps hard-won law 5: one source, derived
    everywhere. A copy here would be a fifth place the number lives.
    """
    import csv
    import pathlib

    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "08-qa"
        / "01-e2e"
        / "expected"
        / "money-triples.csv"
    )
    if not path.is_file():
        raise CohortCannotSeed(
            f"{path} is missing — the journeys' expectation dataset is the only source for "
            "these figures and this file may not substitute one."
        )
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (row["shape"], row["bill_type"], row["payment"]) == (shape, bill_type, payment):
                return row
    raise CohortCannotSeed(
        f"money-triples.csv has no `{shape},{bill_type},{payment}` row — the figure this "
        "cohort must reproduce is not stated anywhere, and inventing one is exactly what "
        "a fixture may never do."
    )


def ensure_guardrail_cohort(tenant, actor) -> dict[str, Any]:
    """T7-14 — a trailing average that was BILLED, and a draft that clears it.

    Three parts, and the first is the one a fixture usually fakes:

      · **the trailing average is produced, never typed.** Three consecutive
        cycles are issued at the money-triples `flat,cycle` figure, so
        97.41 is what the account HAS been billed rather than a number written
        into a column. A guardrail journey over a typed average would compare
        the engine's draft against this file's opinion.
      · **the draft is a real one-time back-bill** through
        `apps.billing.one_time.create` — the S31.2 door a clerk uses — over
        three months the account has never been billed for. A draft posts no
        journal entry, so DEF-556 does not reach it.
      · **the sibling** carries the identical situation and is deliberately
        NOT drafted here: T7-14 runs it AFTER the settings change, and a
        pre-existing draft would have performed the journey's step 4.

    ⚠ **WHAT THIS COHORT CANNOT GIVE THE JOURNEY, stated rather than implied:**
    the guardrail FLAG. `apps/billing/decisions.py` refuses its own `overcharge`
    case in its own words — *"BR-BIL-029's guardrail compares a draft against
    the account's trailing average, which no selector computes"* — and
    `apps/billing/release.py` records that the flag *"has no store
    (BR-BIL-054)"*. So steps 1, 2, 4 and 5 of this journey drive a surface that
    does not exist yet. The FIXTURE is real and complete; the journey's flag
    assertions are not runnable, and the seeder says so out loud.
    """
    from apps.billing import models as billing_models
    from apps.billing import one_time

    plan = ensure_flat_plan(tenant, actor)
    built = {}
    for account_no, label, meter_no in (
        (T714_ACCOUNT, T714_UNIT, T714_METER),
        (T714_SIBLING, T714_SIBLING_UNIT, T714_SIBLING_METER),
    ):
        made = _billable_unit(
            tenant,
            actor,
            label=label,
            meter_no=meter_no,
            account_no=account_no,
            plan=plan,
            cycle_code=T714_CYCLE,
            reads=False,
        )
        _read_series(
            tenant,
            actor,
            made["meter_id"],
            _monthly_series(T714_READ_HEAD, T714_READ_MONTHS),
        )
        built[account_no] = made

    cycle = built[T714_ACCOUNT]["cycle"]
    issued: list[str] = []
    for period_start, period_end, service_date, bill_date in T714_CYCLE_MONTHS:
        invoices = _run(
            tenant,
            actor,
            cycle=cycle,
            idempotency_key=f"{period_start:%Y-%m}|E2E-T714",
            issue=True,
            period_start=period_start,
            period_end=period_end,
            service_date=service_date,
            bill_date=bill_date,
            issued_at=datetime(bill_date.year, bill_date.month, bill_date.day, 9, 0, tzinfo=timezone.utc),
        )
        for invoice in invoices:
            if invoice.account_id == built[T714_ACCOUNT]["account"].id:
                total = Decimal(invoice.total).quantize(Decimal("0.01"))
                if total != FLAT_TOTAL:
                    raise CohortCannotSeed(
                        f"the {period_start:%B} cycle billed {total} on {T714_ACCOUNT}, not the "
                        f"money-triples `flat,cycle` {FLAT_TOTAL}. The trailing average this "
                        "journey measures a draft against would be wrong, so nothing here may "
                        "report success."
                    )
                issued.append(f"{period_start:%b}: {getattr(invoice, 'invoice_no', invoice.pk)} = {total}")

    expected = money_triples_row("flat", "backbill", "full")
    draft = billing_models.Invoice.objects.filter(
        tenant=tenant,
        account=built[T714_ACCOUNT]["account"],
        status="draft",
        bill_type="backbill",
    ).first()
    if draft is None:
        body = one_time.create(
            one_time.OneTimeRequest(
                account_id=str(built[T714_ACCOUNT]["account"].id),
                kind="backbill",
                sub_periods=T714_BACKBILL_MONTHS,
                reason_code=T714_BACKBILL_REASON,
                # The DRAFT's own bill date, in the cohort's own month. Nothing
                # is posted from a draft, so this dates a document and not money.
                bill_date=AUG_BILL_DATE,
            ),
            run_by=_actor_user(actor),
            actor=actor,
        )
        draft = billing_models.Invoice.objects.get(pk=body["invoice_id"])

    draft_total = Decimal(draft.total).quantize(Decimal("0.01"))
    if draft_total != Decimal(expected["total"]):
        raise CohortCannotSeed(
            f"the back-bill draft totals {draft_total}; the journeys' own dataset row "
            f"`flat,backbill,full` states {expected['total']} (taxable {expected['taxable']} + "
            f"tax {expected['tax']}). T7-14's ratio — above 200% of the 97.41 trailing "
            "average and below 350% — is quoted from that row, so a draft at a different "
            "figure is a different journey. Not reporting success: the difference belongs in "
            "the defect register, not in a fixture that rounds it away."
        )

    guardrail = _billing_settings(actor, overcharge_guardrail_pct=T714_GUARDRAIL_PCT)
    return {
        "account_no": T714_ACCOUNT,
        "sibling_no": T714_SIBLING,
        "issued": issued,
        "trailing_average": str(FLAT_TOTAL),
        "draft_no": getattr(draft, "invoice_no", None) or str(draft.pk),
        "draft_total": str(draft_total),
        "draft_months": f"{T714_BACKBILL_MONTHS[0][0]} → {T714_BACKBILL_MONTHS[-1][1]}",
        "guardrail_pct": str(guardrail.get("overcharge_guardrail_pct")),
        "ratio": f"{(draft_total / FLAT_TOTAL * 100).quantize(Decimal('0.1'))}%",
    }


def ensure_maple_ridge_cohort(_calling_tenant=None, _calling_actor=None) -> dict[str, Any]:
    """T5-04 — tenant B: a SECOND tenant that carries a named, issued bill.

    The sweep journey needs foreign rows to fail to reach. An empty tenant B
    would let every probe return "not found" for the honest reason that nothing
    exists, and the journey would pass over a world where RLS was switched off.
    So this tenant is billed, and the bill is real.

    **CAD, and it is set the lawful way.** The tenant is provisioned USD (the
    signup default) and moved to CAD through `save_regional_settings` BEFORE
    the first bill exists — which is the only door BR-TEN-042 leaves open, and
    is the same lock T4-22 exists to walk into. Setting it afterwards would be
    refused `settings.regional.currency_locked`, correctly.

    **The owner's EMAIL is deliberately brazos-bend's own.** T5-04 step 6 is
    that Dana's address also exists as a user in tenant B — a DIFFERENT user
    row per BR-IDN-029 — and her tenant-A password fails on B's subdomain.
    Provisioning tenant B with the same email is what makes that step real
    rather than hypothetical, and it is also the sharpest possible probe of
    per-tenant identity: if provisioning refused it, BR-IDN-029 would be wrong.
    """
    from apps.customers import models as customer_models
    from apps.identity import models as identity_models
    from apps.tenancy import models as tenancy_models
    from apps.tenancy import services as tenancy_services

    home = tenancy_models.Tenant.objects.filter(subdomain="brazosbend").first()
    if home is None:
        raise CohortCannotSeed(
            "no `brazosbend` tenant — T5-04 is a CROSS-tenant journey and needs tenant A "
            "before tenant B means anything. Run `manage.py seed_demo` first."
        )
    with _in_tenant(home.id):
        dana = identity_models.User.objects.filter(tenant=home).order_by("created_at").first()
    if dana is None:
        raise CohortCannotSeed(
            "tenant A has no user, so there is no address to also exist in tenant B — "
            "step 6 of this journey would be untestable (see DEF-566 for why a test "
            "tenant can arrive without an owner)."
        )

    tenant = ensure_second_tenant(
        subdomain=MAPLE_RIDGE_SUBDOMAIN,
        name=MAPLE_RIDGE_NAME,
        owner_email=dana.email,
        owner_name="Maple Ridge System Admin",
    )
    with _in_tenant(tenant.id):
        owner = tenant_actor(tenant)
        if tenant.currency != MAPLE_RIDGE_CURRENCY:
            tenancy_services.save_regional_settings(owner, {"currency": MAPLE_RIDGE_CURRENCY})
            tenant.refresh_from_db()
        plan = ensure_flat_plan(tenant, owner)
        built = _billable_unit(
            tenant,
            owner,
            label=MAPLE_RIDGE_UNIT,
            meter_no=MAPLE_RIDGE_METER,
            account_no=MAPLE_RIDGE_ACCOUNT,
            plan=plan,
            cycle_code=MAPLE_RIDGE_CYCLE,
        )
        invoices = _run(
            tenant,
            owner,
            cycle=built["cycle"],
            idempotency_key=MAPLE_RIDGE_RUN_KEY,
            issue=True,
        )
        invoice = invoices[0]
        foreign = {
            "account_id": str(built["account"].id),
            "account_no": MAPLE_RIDGE_ACCOUNT,
            "invoice_id": str(invoice.pk),
            "invoice_no": getattr(invoice, "invoice_no", None) or str(invoice.pk),
            "total": str(Decimal(invoice.total).quantize(Decimal("0.01"))),
            "currency": invoice.currency,
        }
        second_user = identity_models.User.objects.filter(tenant=tenant, email=dana.email).first()
        accounts = customer_models.Account.objects.filter(tenant=tenant).count()

    if second_user is None:
        raise CohortCannotSeed(
            f"tenant B has no user with tenant A's address {dana.email} — BR-IDN-029 says the "
            "same address is a DIFFERENT user per tenant, and step 6 of this journey is "
            "exactly that. Provisioning either refused it or wrote a different address; "
            "either way the step is untestable and this may not report success."
        )
    if str(second_user.pk) == str(dana.pk):
        raise CohortCannotSeed(
            "tenant A's user and tenant B's user are the SAME ROW. BR-IDN-029 requires two "
            "rows for one address; one shared row would mean a session on A is a session on "
            "B, which is the leak this journey sweeps for."
        )
    if invoice.currency != MAPLE_RIDGE_CURRENCY:
        raise CohortCannotSeed(
            f"tenant B's bill is in {invoice.currency}, not {MAPLE_RIDGE_CURRENCY}. T5-04 "
            "calls it the CAD sample tenant, and a USD bill would make the two tenants "
            "indistinguishable in exactly the field a leak would show up in."
        )
    return {
        "tenant": MAPLE_RIDGE_SUBDOMAIN,
        "tenant_id": str(tenant.id),
        "currency": tenant.currency,
        "shared_email": dana.email,
        "user_a": str(dana.pk),
        "user_a_tenant": str(home.id),
        "user_b": str(second_user.pk),
        "accounts": accounts,
        **foreign,
    }


# ── CR-014 ROUND 3 · the four journeys that need a cohort of their OWN ──────
#
# Round 2 grouped these with the flat-cohort extensions and was wrong: each
# needs a different PLAN, not the shared one plus an act. They are built here
# over the same primitives rather than in a module of their own — the premises,
# the unit/meter/account chain, the cycle and the five-phase run are identical,
# and only the tariff differs.

# ── T4-11 · the WE-1-shaped taxed bill ──────────────────────────────────────
#
# WE-1's bill is **usage+base 221.90 · taxes 20.97 · late 5.00 = 247.87**
# (EP-PAY-01 §4, EP-PAY-02 §4, the payments pre-session model §PE-2). This
# cohort reproduces the first two and **cannot** reproduce the third — see
# `ensure_we1_taxed_bill`'s docstring, which names it rather than rounding it
# away.
#
# The taxable base is produced by a plan built FOR it: base **11.90** + 2,100
# kWh at **$0.10** = 221.90. That is the same practice the flat cohort already
# uses (0.11 + 12.00 → 89.00): the workbook states the MONEY and the fixture
# chooses inputs that produce it. What it is NOT is WE-1's line composition —
# the signed documents state WE-1's usage+base as one figure, never the eleven
# lines the tax-line suite's docstring mentions, so a fixture inventing eleven
# services would be inventing law rather than reproducing it. Stated here
# because a reader who knows WE-1 as a five-service bill must not mistake this
# for one.
WE1_ACCOUNT = "ACC-2411"  # paragraph says ACC-1042 — see the amendment note
WE1_UNIT = "4Q"
WE1_METER = "MTR-0411"
WE1_CYCLE = "08-E2E-T411"
WE1_RUN_KEY = "2026-08|E2E-T411"
WE1_PLAN_NAME = "E2E WE-1 Residential"
WE1_PLAN_CODE = "e2e-we1-residential"
WE1_UNIT_PRICE = Decimal("0.100000")
WE1_BASE = Decimal("11.900000")
WE1_USAGE_QTY = Decimal("2100.000000")  # kWh — CLAUDE.md rule 3
WE1_TAXABLE = Decimal("221.90")
WE1_TAX = Decimal("20.97")
WE1_TOTAL = Decimal("242.87")  # 221.90 + 20.97. The 5.00 late line: see below.
WE1_LATE_LINE = Decimal("5.00")
#: WE-1's four authority figures on a 221.90 base (T4-11 step 2 quotes them:
#: *"State 13.87 · County 2.22 · City 4.44 · PUC 0.44"*). Same four rates the
#: flat cohort's 89.00 base carries — 6.25% · 2% · 1% · 0.2%.
WE1_TAX_LINES = (Decimal("13.87"), Decimal("4.44"), Decimal("2.22"), Decimal("0.44"))
WE1_PRIOR_READ = Decimal("10000")
WE1_PRIOR_DAY = "2026-07-31"
WE1_BILLING_DAY = "2026-08-28"


def ensure_we1_plan(tenant, actor):
    return ensure_priced_plan(
        tenant,
        actor,
        name=WE1_PLAN_NAME,
        code=WE1_PLAN_CODE,
        unit_price=WE1_UNIT_PRICE,
        base=WE1_BASE,
    )


def ensure_we1_taxed_bill(tenant, actor) -> dict[str, Any]:
    """T4-11 — an ISSUED, TAXED bill the exemption must never restate.

    The journey's subject is BR-BIL-004 through a tax lens: setting an account
    tax-exempt changes the NEXT bill and never the issued one. So the fixture
    is one issued bill carrying real per-authority tax lines, and the exemption
    itself is step 1 — the journey's act — and is deliberately not seeded.

    ⚠ **THE $5.00 LATE LINE OF WE-1 IS NOT HERE, AND IT CANNOT BE.** WE-1's
    247.87 is *usage+base 221.90 · taxes 20.97 · late 5.00*. **No path in this
    product assesses a late fee onto a bill.** `apps/billing/late_fee.py` is a
    pure calculation whose own trailer says so — *"`assess_late_fee` has no
    production caller at all (S31.2/US-BIL-002 unbuilt)"* — and nothing
    anywhere writes a LATE line. So this cohort issues **242.87**, the two
    components that exist, and refuses to pretend the third. Every figure T4-11
    actually asserts — taxable 221.90, tax 20.97, and the four authority
    amounts — is present and proved. What is missing is named on the journey's
    own paragraph as an amendment, which is the difference between a fixture
    that is short and a fixture that lies.
    """
    plan = ensure_we1_plan(tenant, actor)
    built = _billable_unit(
        tenant,
        actor,
        label=WE1_UNIT,
        meter_no=WE1_METER,
        account_no=WE1_ACCOUNT,
        plan=plan,
        cycle_code=WE1_CYCLE,
        reads=False,
    )
    _read_series(
        tenant,
        actor,
        built["meter_id"],
        ((WE1_PRIOR_DAY, WE1_PRIOR_READ), (WE1_BILLING_DAY, WE1_PRIOR_READ + WE1_USAGE_QTY)),
    )
    invoices = _run(
        tenant,
        actor,
        cycle=built["cycle"],
        idempotency_key=WE1_RUN_KEY,
        issue=True,
    )
    invoice = invoices[0]
    total = Decimal(invoice.total).quantize(Decimal("0.01"))
    taxable = Decimal(invoice.subtotal).quantize(Decimal("0.01"))
    tax = Decimal(invoice.tax_total).quantize(Decimal("0.01"))
    if (taxable, tax, total) != (WE1_TAXABLE, WE1_TAX, WE1_TOTAL):
        raise CohortCannotSeed(
            f"the issued bill is taxable {taxable} / tax {tax} / total {total}; WE-1's "
            f"figures are {WE1_TAXABLE} / {WE1_TAX} / {WE1_TOTAL} (247.87 less the 5.00 "
            "late line no path in this product can create). T4-11 step 2 asserts the tax "
            "figure is byte-identical after the exemption is set, so a fixture at a "
            "different figure asserts a different thing."
        )
    tax_lines = sorted(
        Decimal(line.amount).quantize(Decimal("0.01"))
        for line in invoice.lines.all()
        if line.kind == "tax"
    )
    if tax_lines != sorted(WE1_TAX_LINES):
        raise CohortCannotSeed(
            f"tax lines {tax_lines} != WE-1's four authority figures {sorted(WE1_TAX_LINES)} "
            "(State 13.87 · County 2.22 · City 4.44 · PUC 0.44). T4-11 step 2 quotes them "
            "one by one, so an aggregate that happens to sum right is not enough."
        )
    return {
        "account_no": WE1_ACCOUNT,
        "cycle": WE1_CYCLE,
        "invoice_no": getattr(invoice, "invoice_no", None) or str(invoice.pk),
        "invoice_id": str(invoice.pk),
        "taxable": str(taxable),
        "tax": str(tax),
        "total": str(total),
        "tax_lines": [str(value) for value in tax_lines],
        "missing_late_line": str(WE1_LATE_LINE),
        "exempt_at_seed": bool(getattr(built["account"], "tax_exempt", False)),
    }


# ── T4-07 · the rate-version cohort (WE-10) ─────────────────────────────────
#
# WE-10's frozen figures, from T4-07's own paragraph: **Jan–Mar $45.10/mo**
# (26.50 usage + 8.00 base + 10.60 sewer) · **Apr–Jun $47.84/mo** (28.10 + 8.50
# + 11.24), six unbilled months, back-billed to taxable **278.82** → tax
# **26.36** → total **305.18**.
#
# Two things about the modelling, both decisions and both stated:
#
#   · **The sewer charge is a PERCENT OF WATER, not a volumetric rate.** 10.60
#     is exactly 40% of 26.50 and 11.24 is exactly 40% of 28.10, in both
#     versions — so the workbook is describing r6.1's `percent_of_service`
#     model (BR-RAT-015), which this schema carries as `percent` +
#     `basis_service`. Pricing sewer per-kgal would produce the same two
#     numbers from a rule the workbook does not describe, and would need a
#     sewer METER that does not exist on a real sewer connection.
#   · **The water unit price is derived from the workbook, never invented:**
#     26.50 ÷ 6 kgal and 28.10 ÷ 6 kgal, carried at the six decimal places
#     rule 2 allows. The seeder asserts that the stored price times 6 kgal
#     finalizes back to the workbook figure through the product's own money
#     rule, so a typo in the sixth decimal is a refusal rather than a bill that
#     is three cents wrong for six months.
def _month_end_day(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]


T407_PREMISES = "Brazos Bend Water Yard"
T407_UNIT = "W-1"
T407_ACCOUNT = "ACC-2407"
T407_METER = "MTR-0407"
T407_PLAN_NAME = "E2E Water Residential (WE-10)"
T407_PLAN_CODE = "e2e-water-we10"
T407_CYCLE = "08-E2E-T407"
T407_MONTHLY_KGAL = Decimal("6")
T407_V3 = {
    "label": "v3",
    "effective_from": date(2026, 1, 1),
    "effective_to": date(2026, 3, 31),
    "base": Decimal("8.00"),
    "usage": Decimal("26.50"),
    "sewer": Decimal("10.60"),
    "monthly": Decimal("45.10"),
}
T407_V4 = {
    "label": "v4",
    "effective_from": date(2026, 4, 1),
    "effective_to": None,
    "base": Decimal("8.50"),
    "usage": Decimal("28.10"),
    "sewer": Decimal("11.24"),
    "monthly": Decimal("47.84"),
}
T407_VERSIONS = (T407_V3, T407_V4)
#: 40%, in both versions — 10.60/26.50 and 11.24/28.10. Derived below rather
#: than typed, so a version whose sewer figure is not a clean percentage of its
#: own usage figure refuses instead of silently rounding.
T407_UNBILLED_MONTHS = tuple(
    (date(2026, month, 1), date(2026, month, _month_end_day(2026, month)))
    for month in range(1, 7)
)
T407_READ_HEAD_DAY = "2025-12-31"


def ensure_services_enabled(tenant, actor, *codes: str) -> list[str]:
    """Enable the tenant services a multi-service cohort needs — the S65 act.

    ⚠ **THIS IS NOT A CONVENIENCE, IT IS A GATE THE PRODUCT ENFORCES.** Signup
    enables the services the payload named (brazos-bend: electric + water) and
    leaves the other eight `enabled=false`; BR-MET-003 then refuses a premises
    that offers a service the tenant does not sell —
    `ValidationError: VAL-005 (metering.service_not_enabled)`, which is exactly
    what T4-07's water/sewer premises hit on its first run. WE-10's monthly
    figure has a SEWER component and WE-12's has sewer and trash, so those
    services must genuinely be turned on before either cohort is a world the
    product would accept.

    It goes through `tenancy.services.update_tenant_service` — the S65 toggle,
    which seeds the service's UoMs and revenue account as a side effect —
    rather than flipping the column, because a `tenant_services` row with
    `enabled=true` and no UoM prices nothing and renders as though it did.
    """
    from apps.tenancy import models as tenancy_models
    from apps.tenancy import services as tenancy_services

    turned_on: list[str] = []
    for code in codes:
        row = (
            tenancy_models.TenantService.objects.filter(tenant=tenant, service__code=code)
            .select_related("service")
            .first()
        )
        if row is not None and row.enabled:
            continue
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})
        turned_on.append(code)
    still_off = [
        row.service.code
        for row in tenancy_models.TenantService.objects.filter(
            tenant=tenant, service__code__in=list(codes)
        ).select_related("service")
        if not row.enabled
    ]
    if still_off:
        raise CohortCannotSeed(
            f"the tenant still does not sell {still_off} after the S65 toggle ran, so a "
            "premises offering it is refused BR-MET-003 and the cohort cannot exist."
        )
    return turned_on


def _premises_for(tenant, actor, address: str, services: list[str]) -> str:
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_premises

    row = metering_models.Premises.objects.filter(tenant=tenant, address_line=address).first()
    if row is not None:
        return str(row.id)
    return make_premises(actor, address_line=address, services_available=services)["id"]


def _unit_on(tenant, actor, premises_id: str, label: str, services: list[str]) -> str:
    from apps.metering import models as metering_models
    from tests.test_us_met_helpers import make_unit

    row = metering_models.Unit.objects.filter(
        tenant=tenant, premises_id=premises_id, label=label
    ).first()
    if row is not None:
        return str(row.id)
    return make_unit(actor, premises_id, label=label, services=services)["id"]


def ensure_rate_version_cohort(tenant, actor) -> dict[str, Any]:
    """T4-07 — a water tariff with TWO dated versions and six unbilled months.

    The journey's subject is BR-RAT-007: history bills on the version in force
    on its SERVICE date, never on today's rates. So the fixture is exactly two
    things — a version chain whose windows do not overlap, and six months of
    committed reads nobody has billed — and everything the journey does with
    them (publishing, back-billing, correcting March, running April) is its own
    act.

    ⚠ **v4 IS SEEDED, and the journey's step 1 publishes it — which makes step
    1 a REPLAY, not a first publication.** The paragraph states v4 as fixture
    state (*"v4 published Apr 1"*) and step 1 as the publishing act; both
    cannot be first. Seeding it is the reading that keeps the paragraph's
    *"per-version monthly figures"* checkable at seed time, and the alternative
    — seeding v3 alone — would leave half the fixture's own figures with
    nothing to verify them against. Recorded as an amendment on the journey
    rather than resolved silently.
    """
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models
    from tests.test_us_met_helpers import make_plan
    from tests.test_us_met_reads_helpers import a_meter

    enabled = ensure_services_enabled(tenant, actor, "water", "sewer")
    plan = make_plan(tenant, name=T407_PLAN_NAME, code=T407_PLAN_CODE, services=("water", "sewer"))
    water = tenancy_models.Service.objects.get(code="water")
    schedules = {row["service_code"]: row["tariff"] for row in rating_selectors.plan_rate_schedules(plan.id)}
    for code in ("water", "sewer"):
        if code not in schedules:
            raise CohortCannotSeed(
                f"the plan has no `{code}` rate schedule — WE-10's monthly figure is water "
                "usage + base + sewer, and a plan missing one of them prices a different bill."
            )

    versions: dict[str, dict[str, Any]] = {}
    for spec in T407_VERSIONS:
        unit_price = (spec["usage"] / T407_MONTHLY_KGAL).quantize(Decimal("0.000001"))
        percent = (spec["sewer"] / spec["usage"]).quantize(Decimal("0.000001"))
        water_version = rating_models.TariffVersion.objects.filter(
            tenant=tenant, tariff=schedules["water"], effective_from=spec["effective_from"]
        ).first()
        if water_version is None:
            water_version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=schedules["water"],
                model="tiered",
                base_charge=spec["base"],
                uom="kgal",
                currency="USD",
                effective_from=spec["effective_from"],
                effective_to=spec["effective_to"],
            )
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=water_version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=unit_price,
            )
        sewer_version = rating_models.TariffVersion.objects.filter(
            tenant=tenant, tariff=schedules["sewer"], effective_from=spec["effective_from"]
        ).first()
        if sewer_version is None:
            sewer_version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=schedules["sewer"],
                model="percent_of_service",
                base_charge=Decimal("0"),
                percent=percent,
                basis_service=water,
                currency="USD",
                effective_from=spec["effective_from"],
                effective_to=spec["effective_to"],
            )
        # ── The check that makes these figures the WORKBOOK's and not this
        # file's: the stored price, times the workbook's own 6 kgal, finalized
        # by the product's own money rule, must come back to the workbook's
        # usage figure — and base + usage + sewer must come back to its monthly
        # total. A typo in the sixth decimal is then a refusal, not a bill that
        # is three cents wrong for six months.
        from core import money as rating_money

        priced = rating_money.finalize(unit_price * T407_MONTHLY_KGAL)
        sewer_amount = rating_money.finalize(percent * spec["usage"])
        monthly = rating_money.finalize(spec["base"] + priced + sewer_amount)
        if (priced, sewer_amount, monthly) != (spec["usage"], spec["sewer"], spec["monthly"]):
            raise CohortCannotSeed(
                f"{spec['label']} prices {T407_MONTHLY_KGAL} kgal at {priced} + sewer "
                f"{sewer_amount} + base {spec['base']} = {monthly}; WE-10 states "
                f"{spec['usage']} + {spec['sewer']} + {spec['base']} = {spec['monthly']}. The "
                "stored rate does not produce the frozen workbook figure, so the version "
                "chain this journey prices history against is wrong."
            )
        versions[spec["label"]] = {
            "water_version_id": str(water_version.id),
            "sewer_version_id": str(sewer_version.id),
            "unit_price": str(unit_price),
            "percent": str(percent),
            "base": str(spec["base"]),
            "monthly": str(spec["monthly"]),
            "effective_from": str(spec["effective_from"]),
            "effective_to": str(spec["effective_to"]) if spec["effective_to"] else "(current)",
        }

    # Windows must not overlap — B2 §2's EXCLUDE gist, which migration 0001
    # never materialized (the model says so). Asserted here because a fixture
    # whose two versions overlap resolves ambiguously and the journey's whole
    # subject is WHICH version a service date lands on.
    if T407_V3["effective_to"] >= T407_V4["effective_from"]:
        raise CohortCannotSeed(
            f"v3 runs to {T407_V3['effective_to']} and v4 starts {T407_V4['effective_from']} — "
            "the windows overlap, so a service date in the overlap resolves to two versions "
            "and BR-RAT-007 has no answer."
        )

    premises_id = _premises_for(tenant, actor, T407_PREMISES, ["water", "sewer"])
    unit_id = _unit_on(tenant, actor, premises_id, T407_UNIT, ["water", "sewer"])
    from apps.assets import models as asset_models

    meter = asset_models.Asset.objects.filter(tenant=tenant, asset_no=T407_METER).first()
    meter_id = (
        str(meter.id)
        if meter is not None
        else a_meter(actor, asset_no=T407_METER, unit_id=unit_id, service="water", uom="kgal")["id"]
    )
    _assign_plan(tenant, actor, unit_id, plan, reason="CR-014 T4-07 rate-version cohort")
    series = [(T407_READ_HEAD_DAY, Decimal("0"))]
    for index, (_start, end) in enumerate(T407_UNBILLED_MONTHS, start=1):
        series.append((end.isoformat(), T407_MONTHLY_KGAL * index))
    _read_series_uom(tenant, actor, meter_id, tuple(series), unit="kgal")
    account = _account(tenant, unit_id, T407_ACCOUNT)
    _cycle(tenant, T407_CYCLE, [unit_id])

    from apps.billing import models as billing_models

    billed = billing_models.Invoice.objects.filter(tenant=tenant, account=account).count()
    if billed:
        raise CohortCannotSeed(
            f"{T407_ACCOUNT} already carries {billed} invoice(s) — WE-10's six months are "
            "UNBILLED by construction, and a back-bill over a month that was already billed "
            "is a different journey (and a duplicate charge)."
        )
    return {
        "account_no": T407_ACCOUNT,
        "plan": plan.code,
        "versions": versions,
        "unbilled_months": f"{T407_UNBILLED_MONTHS[0][0]} → {T407_UNBILLED_MONTHS[-1][1]}",
        "monthly_kgal": str(T407_MONTHLY_KGAL),
        "services_turned_on": enabled,
        "reads": len(series),
        "issued_invoices": billed,
    }


def _read_series_uom(tenant, actor, asset_id, series, *, unit: str) -> None:
    """`_read_series` for a service whose unit is not kWh (CLAUDE.md rule 3).

    The unit is an ARGUMENT with no default on purpose: a water read committed
    as kWh would bill 6 of something at a price per something else, and rule 3
    exists because that is invisible in every downstream figure.
    """
    from apps.metering.models import MeterRead
    from tests.test_us_met_reads_helpers import at, commit_read

    prior = None
    for day, value in series:
        if not MeterRead.objects.filter(
            tenant=tenant, asset_id=asset_id, read_at=at(day), channel="total"
        ).exists():
            commit_read(
                actor,
                asset_id,
                day=day,
                value=str(value),
                prior_value=str(prior) if prior is not None else None,
                consumption=str(value - prior) if prior is not None else None,
                unit=unit,
            )
        prior = value


# ── T4-04 · the WE-12 multi-service world (vacation hold) ───────────────────
#
# WE-12, from T4-04's own step 2: usage bills through the hold date — **TOU
# 60/95/160 → 13.20 + 13.30 + 14.40 · water 3.1 kgal → 12.40 · sewer 4.96** —
# while **bases and flat services continue the full month — elec 12.00 + water
# 8.00 + trash 18.00**. Taxable **96.26** → tax **9.10** → total **105.36**.
#
# ⚠ **THE HOLD, THE INTERIM READ AND THE BILL ARE THE JOURNEY'S ACTS, NOT THIS
# FIXTURE'S.** What a fixture owes T4-04 is the WORLD those acts happen in: an
# account on a four-service plan whose rates produce WE-12's line amounts, with
# a meter per service and the reads the hold date cuts. Seeding the held status
# or the issued bill would leave the journey asserting over its own answer.
#
# ⚠ **AND THE DATES MOVE +1 MONTH (DEF-556).** The paragraph holds from Jul 16
# and bills a July cycle; a July-dated issue posts its journal entry inside the
# finance-signed LE-1 window. The hold moves to **Aug 16** with its interim read
# on **Aug 15** and the return on **Sep 10** — the same shape, one month later,
# and the WE-12 figures are untouched because they are quantities and rates.
T404_PREMISES = "Brazos Bend Mixed Services"
T404_UNIT = "MS-1"
T404_ACCOUNT = "ACC-2046"  # paragraph says ACC-1046 — the cohort's ACC-2xxx range
T404_CYCLE = "08-E2E-T404"
T404_PLAN_NAME = "E2E Residential Standard (WE-12)"
T404_PLAN_CODE = "e2e-residential-we12"
T404_SERVICES = ("electric", "water", "sewer", "trash")
T404_METERS = {"electric": "MTR-0404E", "water": "MTR-0404W"}
T404_HOLD_FROM = date(2026, 8, 16)
T404_INTERIM_READ_DAY = "2026-08-15"
T404_HOLD_TO = date(2026, 9, 10)
T404_PRIOR_READ_DAY = "2026-07-31"
#: WE-12's TOU quantities and prices. `channel` is REQUIRED on every window
#: since BR-RAT-067 (PO 2026-08-16, *"make the rate wizard say which register is
#: which"*) — before it, rating matched price to measurement by RANK and billed
#: one demo schedule 38% high. A fixture omitting it stores a row the engine
#: refuses by name.
T404_TOU = (
    ("On-peak", "tou_on", Decimal("60"), Decimal("0.220000"), "14:00", "20:00", Decimal("13.20")),
    ("Mid-peak", "tou_mid", Decimal("95"), Decimal("0.140000"), "06:00", "14:00", Decimal("13.30")),
    ("Off-peak", "tou_off", Decimal("160"), Decimal("0.090000"), "20:00", "06:00", Decimal("14.40")),
)
T404_ELECTRIC_BASE = Decimal("12.00")
T404_WATER_KGAL = Decimal("3.1")
T404_WATER_PRICE = Decimal("4.000000")
T404_WATER_USAGE = Decimal("12.40")
T404_WATER_BASE = Decimal("8.00")
T404_SEWER_PERCENT = Decimal("0.400000")  # 4.96 / 12.40 — the same 40% WE-10 carries
T404_SEWER_AMOUNT = Decimal("4.96")
T404_TRASH_BASE = Decimal("18.00")
T404_TAXABLE = Decimal("96.26")
T404_TAX = Decimal("9.10")
T404_TOTAL = Decimal("105.36")


def ensure_we12_world(tenant, actor) -> dict[str, Any]:
    """T4-04 — a four-service account whose rates produce WE-12's figures.

    Every rate is CHECKED against the workbook line it must produce, through
    `core.money.finalize` — the product's own money rule — and the checked sum
    is WE-12's taxable 96.26 and its 105.36 total. That is the strongest claim
    a fixture can make without performing the journey's own bill run: the
    inputs demonstrably price WE-12, and whether the ENGINE agrees is what
    T4-04 step 2 exists to find out.
    """
    from apps.assets import models as asset_models
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models
    from core import money
    from tests.test_us_met_helpers import make_plan
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    turned_on = ensure_services_enabled(tenant, actor, *T404_SERVICES)
    plan = make_plan(tenant, name=T404_PLAN_NAME, code=T404_PLAN_CODE, services=T404_SERVICES)
    tariffs = {
        row["service_code"]: row["tariff"] for row in rating_selectors.plan_rate_schedules(plan.id)
    }
    missing = [code for code in T404_SERVICES if code not in tariffs]
    if missing:
        raise CohortCannotSeed(
            f"the plan has no rate schedule for {missing}; WE-12's 105.36 is the sum of all "
            f"{len(T404_SERVICES)} services and a plan short of one prices a different bill."
        )
    water_service = tenancy_models.Service.objects.get(code="water")

    def a_version(service_code, *, model, **fields):
        existing = rating_models.TariffVersion.objects.filter(
            tenant=tenant, tariff=tariffs[service_code], effective_from=date(2026, 1, 1)
        ).first()
        if existing is not None:
            return existing
        return rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=tariffs[service_code],
            model=model,
            currency="USD",
            effective_from=date(2026, 1, 1),
            **fields,
        )

    electric = a_version(
        "electric", model="time_of_use", base_charge=T404_ELECTRIC_BASE, uom="kWh"
    )
    for label, channel, _qty, price, start, end, _amount in T404_TOU:
        rating_models.TimeOfUseWindow.objects.get_or_create(
            tenant=tenant,
            tariff_version=electric,
            label=label,
            day_type="weekday",
            defaults={
                "start_time": start,
                "end_time": end,
                "unit_price": price,
                "channel": channel,
            },
        )
    water = a_version("water", model="tiered", base_charge=T404_WATER_BASE, uom="kgal")
    if not rating_models.RateTier.objects.filter(tenant=tenant, tariff_version=water).exists():
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=water,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=T404_WATER_PRICE,
        )
    a_version(
        "sewer",
        model="percent_of_service",
        base_charge=Decimal("0"),
        percent=T404_SEWER_PERCENT,
        basis_service=water_service,
    )
    a_version("trash", model="flat", base_charge=T404_TRASH_BASE)

    # ── The workbook check: every stored rate against the line it must make ──
    lines: list[tuple[str, Decimal, Decimal]] = []
    for label, _channel, qty, price, _start, _end, amount in T404_TOU:
        lines.append((label, money.finalize(qty * price), amount))
    lines.append(
        ("water usage", money.finalize(T404_WATER_KGAL * T404_WATER_PRICE), T404_WATER_USAGE)
    )
    lines.append(
        ("sewer", money.finalize(T404_SEWER_PERCENT * T404_WATER_USAGE), T404_SEWER_AMOUNT)
    )
    lines.append(("electric base", T404_ELECTRIC_BASE, T404_ELECTRIC_BASE))
    lines.append(("water base", T404_WATER_BASE, T404_WATER_BASE))
    lines.append(("trash", T404_TRASH_BASE, T404_TRASH_BASE))
    wrong = [f"{name}: rate makes {made}, WE-12 states {stated}" for name, made, stated in lines if made != stated]
    if wrong:
        raise CohortCannotSeed(
            "the stored rates do not price WE-12's lines — " + "; ".join(wrong) + ". The "
            "cohort would bill a different bill and T4-04's 105.36 would be unreachable."
        )
    taxable = money.finalize(sum(made for _name, made, _stated in lines))
    if taxable != T404_TAXABLE:
        raise CohortCannotSeed(
            f"WE-12's lines sum to {taxable}, not the workbook's taxable {T404_TAXABLE}."
        )

    premises_id = _premises_for(tenant, actor, T404_PREMISES, list(T404_SERVICES))
    unit_id = _unit_on(tenant, actor, premises_id, T404_UNIT, list(T404_SERVICES))
    meters: dict[str, str] = {}
    for service_code, asset_no in T404_METERS.items():
        row = asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).first()
        meters[service_code] = (
            str(row.id)
            if row is not None
            else a_meter(
                actor,
                asset_no=asset_no,
                unit_id=unit_id,
                service=service_code,
                uom="kWh" if service_code == "electric" else "kgal",
            )["id"]
        )
    _assign_plan(tenant, actor, unit_id, plan, reason="CR-014 T4-04 WE-12 cohort")

    # The electric meter carries THREE TOU channels; the prior head on each is
    # what makes the interim read a consumption rather than a first reading.
    from apps.metering.models import MeterRead

    for _label, channel, qty, _price, _start, _end, _amount in T404_TOU:
        for day, value, prior, consumption in (
            (T404_PRIOR_READ_DAY, Decimal("0"), None, None),
            (T404_INTERIM_READ_DAY, qty, Decimal("0"), qty),
        ):
            if MeterRead.objects.filter(
                tenant=tenant, asset_id=meters["electric"], read_at=at(day), channel=channel
            ).exists():
                continue
            commit_read(
                actor,
                meters["electric"],
                day=day,
                value=str(value),
                channel=channel,
                prior_value=str(prior) if prior is not None else None,
                consumption=str(consumption) if consumption is not None else None,
                unit="kWh",
            )
    _read_series_uom(
        tenant,
        actor,
        meters["water"],
        ((T404_PRIOR_READ_DAY, Decimal("0")), (T404_INTERIM_READ_DAY, T404_WATER_KGAL)),
        unit="kgal",
    )

    account = _account(tenant, unit_id, T404_ACCOUNT)
    _cycle(tenant, T404_CYCLE, [unit_id])
    status_code = getattr(getattr(account, "status", None), "code", None)
    if status_code != "active":
        raise CohortCannotSeed(
            f"{T404_ACCOUNT} is `{status_code}`, not active — T4-04 step 1 moves it Active → "
            "Vacation hold, and an account already held has nothing to transition."
        )
    return {
        "account_no": T404_ACCOUNT,
        "plan": plan.code,
        "services": list(T404_SERVICES),
        "services_turned_on": turned_on,
        "meters": {code: asset_no for code, asset_no in T404_METERS.items()},
        "cycle": T404_CYCLE,
        "status_at_seed": status_code,
        "hold_from": str(T404_HOLD_FROM),
        "hold_to": str(T404_HOLD_TO),
        "interim_read_day": T404_INTERIM_READ_DAY,
        "checked_lines": [f"{name}={made}" for name, made, _stated in lines],
        "taxable": str(taxable),
        "tax": str(T404_TAX),
        "total": str(T404_TOTAL),
    }


# ── T5-18 · the Commercial-TOU-demand meter with a skipped site ─────────────
#
# T5-18's subject is BR-MET-062: **a demand value is never estimated.** kWh
# channels estimate from their own trailing histories; `demand` is REFUSED, and
# the meter goes to the field-visit list. So the cohort is a demand-metered
# commercial account with a HISTORY on every channel and NOTHING for the cycle
# under test — the reader skipped the site.
#
# ⚠ **WHAT THE PRODUCT CANNOT EXPRESS, AND IT IS THE PARAGRAPH'S OWN PHRASE:**
# *"required channels total · tou_on · tou_mid · tou_off · demand
# (BR-MET-049)"*. **BR-MET-049's plan-driven completeness is NOT BUILT** —
# `apps/metering/selectors.py` serves `missing: null` with its own stated
# reason, *"BR-MET-049 plan-driven completeness not built (US-MET-018)"*, and
# `apps/metering/api.py` repeats it. There is nowhere to record that this plan
# REQUIRES the demand channel, so T5-18 step 2 (*"completeness stays incomplete
# so billing is gated"*) has no surface. Step 1's demand refusal, step 3's
# absent Estimate action and step 4's direct-write refusal are all real and all
# reachable — `apps/metering/estimation.py` carries
# `REASON_DEMAND_CHANNEL = "demand_never_estimated"` and refuses by name.
T518_PREMISES = "Brazos Bend Commercial Park"
T518_UNIT = "COM-1"
T518_ACCOUNT = "ACC-2077"
T518_METER = "MTR-0713"
T518_CYCLE = "08-E2E-T518"
T518_PLAN_NAME = "E2E Commercial TOU Demand"
T518_PLAN_CODE = "e2e-commercial-tou-demand"
#: The five registers the paragraph names. `demand` is the one that may never
#: be estimated; the other four are kWh and estimate from their own history.
T518_KWH_CHANNELS = ("total", "tou_on", "tou_mid", "tou_off")
T518_DEMAND_CHANNEL = "demand"
T518_DEMAND_RATE_PER_KW = Decimal("14.500000")
#: `demand_rate_config` carries BOTH halves of a demand tariff and both are
#: NOT NULL: the kW charge and the energy rate the same structure prices kWh
#: at. A fixture that set only the kW half is refused by the database, which is
#: the schema saying a demand tariff is not a demand charge on its own.
T518_ENERGY_RATE_PER_KWH = Decimal("0.095000")
T518_TOU = (
    ("On-peak", "tou_on", Decimal("0.220000"), "14:00", "20:00"),
    ("Mid-peak", "tou_mid", Decimal("0.140000"), "06:00", "14:00"),
    ("Off-peak", "tou_off", Decimal("0.090000"), "20:00", "06:00"),
)
T518_BASE = Decimal("35.000000")
#: Two committed months of history per channel — enough for the trailing
#: average the kWh estimate uses, and enough to make the demand register a real
#: one rather than a column that never carried a value.
T518_HISTORY = (
    ("2026-06-30", {"total": Decimal("4200"), "tou_on": Decimal("900"), "tou_mid": Decimal("1400"), "tou_off": Decimal("1900"), "demand": Decimal("39.4")}),
    ("2026-07-31", {"total": Decimal("8500"), "tou_on": Decimal("1830"), "tou_mid": Decimal("2840"), "tou_off": Decimal("3830"), "demand": Decimal("41.1")}),
)
#: The cycle under test. NOTHING is read for it — that absence IS the fixture.
T518_MISSING_PERIOD = (AUG_START, AUG_END)


def ensure_demand_meter_cohort(tenant, actor) -> dict[str, Any]:
    """T5-18 — a demand meter with history and a skipped cycle.

    Two properties, and the second is the one a journey cannot check for
    itself: the kWh channels have enough history for an estimate to be
    POSSIBLE (or step 1's *"kWh channels estimate independently"* would fail
    for the wrong reason), and the cycle under test has **no read at all** on
    any channel (or there is nothing missing to refuse an estimate for).
    """
    from apps.assets import models as asset_models
    from apps.metering.models import MeterRead
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors
    from tests.test_us_met_helpers import make_plan
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    plan = make_plan(tenant, name=T518_PLAN_NAME, code=T518_PLAN_CODE, services=("electric",))
    tariff = next(
        row["tariff"]
        for row in rating_selectors.plan_rate_schedules(plan.id)
        if row["service_code"] == "electric"
    )
    version = rating_models.TariffVersion.objects.filter(
        tenant=tenant, tariff=tariff, effective_from=date(2026, 1, 1)
    ).first()
    if version is None:
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=tariff,
            model="demand",
            base_charge=T518_BASE,
            uom="kWh",
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
    for label, channel, price, start, end in T518_TOU:
        rating_models.TimeOfUseWindow.objects.get_or_create(
            tenant=tenant,
            tariff_version=version,
            label=label,
            day_type="weekday",
            defaults={
                "start_time": start,
                "end_time": end,
                "unit_price": price,
                "channel": channel,
            },
        )
    demand_config = rating_models.DemandRateConfig.objects.filter(
        tenant=tenant, tariff_version=version
    ).first()
    if demand_config is None:
        demand_config = rating_models.DemandRateConfig.objects.create(
            tenant=tenant,
            tariff_version=version,
            demand_rate_per_kw=T518_DEMAND_RATE_PER_KW,
            energy_rate_per_kwh=T518_ENERGY_RATE_PER_KWH,
            peak_window_label="15-min monthly",
        )

    premises_id = _premises_for(tenant, actor, T518_PREMISES, ["electric"])
    unit_id = _unit_on(tenant, actor, premises_id, T518_UNIT, ["electric"])
    row = asset_models.Asset.objects.filter(tenant=tenant, asset_no=T518_METER).first()
    meter_id = (
        str(row.id)
        if row is not None
        else a_meter(actor, asset_no=T518_METER, unit_id=unit_id, service="electric", uom="kWh")["id"]
    )
    _assign_plan(tenant, actor, unit_id, plan, reason="CR-014 T5-18 demand cohort")

    prior: dict[str, Decimal] = {}
    for day, values in T518_HISTORY:
        for channel, value in values.items():
            if MeterRead.objects.filter(
                tenant=tenant, asset_id=meter_id, read_at=at(day), channel=channel
            ).exists():
                prior[channel] = value
                continue
            previous = prior.get(channel)
            commit_read(
                actor,
                meter_id,
                day=day,
                value=str(value),
                channel=channel,
                prior_value=str(previous) if previous is not None else None,
                consumption=(
                    str(value - previous)
                    if previous is not None and channel != T518_DEMAND_CHANNEL
                    else None
                ),
                # CLAUDE.md rule 3 — and the demand register is kW, not kWh.
                # A peak recorded as kWh would price a demand charge off an
                # energy number, which is the one mistake a demand journey is
                # about.
                unit="kW" if channel == T518_DEMAND_CHANNEL else "kWh",
            )
            prior[channel] = value

    account = _account(tenant, unit_id, T518_ACCOUNT)
    _cycle(tenant, T518_CYCLE, [unit_id])

    start, end = T518_MISSING_PERIOD
    in_cycle = MeterRead.objects.filter(
        tenant=tenant, asset_id=meter_id, read_at__gte=at(start.isoformat()), read_at__lte=at(end.isoformat())
    ).count()
    if in_cycle:
        raise CohortCannotSeed(
            f"{T518_METER} already carries {in_cycle} read(s) in {start} → {end}. T5-18's "
            "whole premise is that the reader SKIPPED the site: with a read present there is "
            "nothing missing, no estimate is attempted, and the demand refusal this journey "
            "exists to prove is never reached."
        )
    # ⚠ TWO CHECKS, NOT ONE, AND THE FIRST WAS ADDED BECAUSE THE SECOND CANNOT
    # SEE ITS OWN SHRINKING. `expected` is derived from `T518_HISTORY`, so a
    # cohort cut down to a single month agrees with itself perfectly and reports
    # success — the estimate would then have one actual to average and step 1's
    # trailing-3 method would be exercised on a history it was never meant to
    # run on. The MINIMUM is stated against the rule instead (BR-MET-026 allows
    # a shorter history, so this is a property of the FIXTURE's intent).
    if len(T518_HISTORY) < 2:
        raise CohortCannotSeed(
            f"the cohort declares {len(T518_HISTORY)} month(s) of history; T5-18 step 1 has "
            "the kWh channels estimating from a TRAILING AVERAGE, which needs more than one "
            "actual to be an average at all."
        )
    history = MeterRead.objects.filter(tenant=tenant, asset_id=meter_id).count()
    expected = len(T518_HISTORY) * (len(T518_KWH_CHANNELS) + 1)
    if history < expected:
        raise CohortCannotSeed(
            f"the meter carries {history} committed reads and the cohort needs {expected} "
            f"({len(T518_HISTORY)} months × {len(T518_KWH_CHANNELS) + 1} channels). Without "
            "trailing history the kWh estimate fails for lack of data and step 1's "
            "*'kWh channels estimate independently'* would be red for the wrong reason."
        )
    return {
        "account_no": T518_ACCOUNT,
        "meter": T518_METER,
        "plan": plan.code,
        "cycle": T518_CYCLE,
        "kwh_channels": list(T518_KWH_CHANNELS),
        "demand_channel": T518_DEMAND_CHANNEL,
        "demand_rate_per_kw": str(demand_config.demand_rate_per_kw),
        "energy_rate_per_kwh": str(demand_config.energy_rate_per_kwh),
        "history_rows": history,
        "reads_in_cycle": in_cycle,
        "missing_period": f"{start} → {end}",
        "account_id": str(account.id),
    }


# ── CR-014 GROUP 6 · the finance-period family (T5-08 · T5-09 · T6-09) ──────
#
# All three want the same two facts: **2026-06 CLOSED with a recorded export
# batch, 2026-07 the earliest OPEN period.** T5-08 exports an open period and is
# refused; T5-09 posts a receipt dated inside the closed month and watches it
# auto-forward; T6-09 walks the same state under three roles.
#
# ⚠ **CLOSING JUNE IS NOT A NEUTRAL ACT ON THIS TENANT, AND THE ORDER MATTERS.**
# LE-1's book opens with a cutover entry dated **2026-06-30** — inside the
# window this cohort closes — and `apps/ledger/posting.py` auto-forwards an
# entry whose date lands in a closed period (BR-TEN-038). So a stack that
# closed June BEFORE `seed_j19` posted the book would push LE-1's opening entry
# into July and the signed 598.69 footing would move. The builder therefore
# REFUSES to close June until the book is posted somewhere, and says which
# month it found it in. Nothing about that ordering is enforced by the seeder
# registry, which is exactly why it is checked here rather than assumed.
FINANCE_CLOSED_PERIOD = (date(2026, 6, 1), date(2026, 6, 30))
FINANCE_OPEN_PERIOD = (date(2026, 7, 1), date(2026, 7, 31))
FINANCE_CLOSE_REASON = (
    "CR-014 journey fixture (T5-08 / T5-09 / T6-09): June is closed with its checklist "
    "state snapshotted, which is what BR-LED-018's WARN+CONFIRM records"
)
FINANCE_CLOSED_AT = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)
FINANCE_EXPORT_AT = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
#: **`csv`, and the choice is not cosmetic.** BR-LED-004 names four targets
#: (`qbo`, `xero`, `csv`, `iif`) and the service refuses anything else by name —
#: `'quickbooks' is not one of ('qbo', 'xero', 'csv', 'iif')`, which is what
#: this cohort's first run hit. Of the four, `qbo` and `xero` address accounts
#: by an export REF and refuse ATOMICALLY when any account in the window has
#: none: `these accounts have no qbo_ref … 1200 · Accounts receivable, 3000 ·
#: Opening balance clearing`. Stamping those refs is the S57 mapping act that
#: **J19's own fixture already performs**, and doing it a second time here
#: would be a second copy of that decision (hard-won law 5). `csv` addresses
#: accounts by code+name and needs none — and none of T5-08, T5-09 or T6-09
#: names a target, so the one that needs no borrowed act is the honest choice.
FINANCE_EXPORT_TARGET = "csv"
#: T6-09's LE-4 accrual pair — *"DR 1210 Unbilled AR 500.00 / CR 4100 Electric
#: Revenue 500.00"*. POSTING it is the journey's own act (its whole point is
#: that the unbalanced 500.00/480.00 variant is refused), so the fixture only
#: guarantees the two accounts the journey posts BETWEEN exist.
FINANCE_LE4_ACCOUNTS = (("1210", "asset"), ("4100", "revenue"))


def ensure_finance_period_cohort(tenant, actor) -> dict[str, Any]:
    """T5-08 / T5-09 / T6-09 — one closed month, one open month, one batch.

    What ARRIVES: June 2026 closed through the real `close_period` (checklist
    recomputed at close, incomplete items snapshotted beside the reason — the
    BR-LED-018 receipt), a recorded `export_batches` row for that window, July
    2026 open and carrying posted entries, the three-role cast, and the two GL
    accounts T6-09's LE-4 pair posts between.

    What does NOT, and is named on each journey's paragraph instead:

      · **T6-09's deposit batch DEP-0642 "reconciled with one wrong match"** —
        a wrong match is a payment allocated to the wrong account and then
        found; seeding one means writing a KNOWN-BAD allocation, which is a
        money row this fixture has no rule to justify. Left to the journey.
      · **T6-09's remittance filing confirmation #TX-88231 and its 1.2 MB
        receipt PDF** — there is no document store anywhere in `apps/` (the
        same absence T5-28 is refused for), so a filing receipt has nowhere to
        be attached.
      · **The batch NUMBER `EXP-2606-01`.** `export_batches.batch_no` is
        allocated from the tenant's `export_batch` series, and tenancy seeds no
        default format for it — the model says so — so the recorded batch may
        carry a NULL number. The batch is real; its label is the product's, not
        this file's, and a made-up `EXP-2606-01` would be a number no series
        issued.
    """
    from apps.ledger import close as ledger_close
    from apps.ledger import exports as ledger_exports
    from apps.ledger import models as ledger_models

    closed_start, closed_end = FINANCE_CLOSED_PERIOD
    open_start, open_end = FINANCE_OPEN_PERIOD

    # ── The ordering guard, and it protects a SIGNED figure ─────────────────
    anchor = ledger_models.JournalEntry.objects.filter(
        tenant=tenant, status=ledger_models.JE_POSTED, posting_key="invoice|WE-1|issued"
    ).first()
    already_closed = ledger_close.is_period_closed(closed_start, closed_end)
    if anchor is None and not already_closed:
        raise CohortCannotSeed(
            f"the LE-1 book is not posted on this tenant and {closed_start:%B %Y} is not yet "
            "closed. Closing it first would leave LE-1's own opening cutover entry (dated "
            f"{closed_end}) unpostable: the posting service REFUSES a closed-period entry_date "
            "(DEF-3202), so the seed would fail outright and the finance-signed 598.69 footing "
            "would never be built. Seed J19 first — the seeder registry does not enforce this "
            "order, which is why it is checked here. ⚠ CORRECTED 2026-09-02: this said the "
            "entry would be AUTO-FORWARDED into July and the footing would move. That was true "
            "of BR-TEN-038 as a rule and was never true of this path — post() did no period "
            "check at all, so the entry would have landed IN the closed month. Either way the "
            "guard below is what protects the figure, and it is unchanged."
        )

    checklist = ledger_close.close_checklist(period_start=closed_start, period_end=closed_end)
    if not already_closed:
        ledger_close.close_period(
            actor,
            period_start=closed_start,
            period_end=closed_end,
            closed_at=FINANCE_CLOSED_AT,
            # A reason is REQUIRED whenever any checklist item is incomplete or
            # unknown, and several are (their registers are other modules').
            # BR-LED-018 makes that a WARN, never a lockout.
            reason=FINANCE_CLOSE_REASON,
        )
    if not ledger_close.is_period_closed(closed_start, closed_end):
        raise CohortCannotSeed(
            f"{closed_start} … {closed_end} is still open after close_period returned. All "
            "three journeys assert over a CLOSED month, and a fixture that reported success "
            "here would leave them asserting over an open one."
        )
    if ledger_close.is_period_closed(open_start, open_end):
        raise CohortCannotSeed(
            f"{open_start} … {open_end} is CLOSED, and T5-08's whole subject is exporting an "
            "OPEN period and being refused (BR-LED-017). With July closed the refusal never "
            "happens and the journey passes over the wrong state."
        )

    batch = ledger_exports.overlapping_batch(
        period_start=closed_start, period_end=closed_end, target=FINANCE_EXPORT_TARGET
    )
    if batch is None:
        recorded = ledger_exports.create_export_batch(
            actor,
            period_start=closed_start,
            period_end=closed_end,
            target=FINANCE_EXPORT_TARGET,
            created_at=FINANCE_EXPORT_AT,
        )
    else:
        recorded = ledger_exports.batch_dict(batch) if hasattr(batch, "pk") else dict(batch)

    posted_in_open = ledger_models.JournalEntry.objects.filter(
        tenant=tenant,
        status=ledger_models.JE_POSTED,
        entry_date__gte=open_start,
        entry_date__lte=open_end,
    ).count()
    if not posted_in_open:
        raise CohortCannotSeed(
            f"{open_start:%B %Y} holds no posted entries, so *'2026-07 OPEN (run RUN-2607-A "
            "issued; payments still arriving)'* is not true of this stack. T5-09's receipt "
            "arrives into an empty month and T6-09's executive reads a blank period — both "
            "would pass over nothing."
        )

    from tests import ledger_le_fixtures as le

    le4_accounts = {
        code: str(le.gl(tenant, code, type_).id) for code, type_ in FINANCE_LE4_ACCOUNTS
    }
    # ⚠ THE THREE-ROLE CAST IS **NOT** BUILT HERE, AND T6-09 IS THE ONLY ONE OF
    # THE THREE THAT NEEDS IT. `ensure_role_cast` goes through
    # `identity.sample_data`, which refuses on a tenant with no ACTIVE System
    # Admin — *"an invitation from nobody would corrupt the trail"* (BR-IDN-011)
    # — and under the shared pytest harness a provisioned tenant HAS no owner
    # (DEF-566: `test_us_ten_helpers.identity_seam` stubs the real seam). On a
    # booted stack the owner is real and the cast builds, so `seed_t6_09` calls
    # it there. Putting it here would make T5-08 and T5-09 — which need no roles
    # at all — unbuildable in the suite for a reason neither journey describes.
    return {
        "closed_period": f"{closed_start} → {closed_end}",
        "open_period": f"{open_start} → {open_end}",
        "close_reason": FINANCE_CLOSE_REASON,
        "checklist": {item.code: item.state for item in checklist["items"]},
        "batch_no": recorded.get("batch_no"),
        "batch_id": recorded.get("batch_id") or recorded.get("id"),
        "batch_target": FINANCE_EXPORT_TARGET,
        "batch_debits": str(recorded.get("total_debits")),
        "batch_credits": str(recorded.get("total_credits")),
        "posted_in_open_period": posted_in_open,
        "le1_book_month": f"{anchor.entry_date:%B %Y}" if anchor is not None else "(already closed before this pass)",
        "le4_accounts": le4_accounts,
    }


# ── CR-014 GROUP 5 · the notification-queue cohorts (T5-23 · T7-16 · T7-17) ──
#
# These three are the first cohorts in this CR whose COUNTS are the fixture:
# **340 accounts**, **680 queued rows**, **2,000 queued email rows**. A journey
# about a dispatcher draining 2,000 rows at batch size 500 asserts four
# hand-offs; over 12 rows it asserts one, passes, and proves nothing about
# batching at all.
#
# ⚠ **"QUEUED-AND-HELD" IS THE JOURNEYS' PROSE AND NOT THE `held` COLUMN, AND
# CONFUSING THE TWO WOULD SEED THE WRONG WORLD.** `outbound_messages.held` is
# BR-PAY-018's PAPER SUPPRESSION — the account's address is known to be bad —
# and a held row is skipped by every cycle forever until an address
# verification releases it. Quiet hours are something else entirely: the rows
# stay `status=queued` and unheld, and `dispatcher._within_send_window` simply
# declines to dispatch while the tenant's local clock is outside 08:00–21:00.
# A fixture that set `held=True` would seed 680 permanently-suppressed rows
# that no window change could ever release, and T7-16's whole subject is
# moving the window and watching them go.
#
# ⚠ **THE SMS HALF CARRIES NO ADDRESS, AND THE PRODUCT IS RIGHT ABOUT THAT.**
# `customers.selectors.delivery_recipients_for_account` answers SMS with
# `recipient_not_resolvable` — always — because the mobile-consent column
# (`accounts.sms_reminders`) is PROPOSED-SCHEMA and does not exist: *"nobody has
# asked this customer whether they consent to texts"*. So of the 680 rows, the
# 340 email rows carry addresses and the 340 SMS rows carry a stated reason.
# The COUNT the journeys assert is exact; half of it is unaddressed, by a rule,
# and that is written on the journeys rather than papered over with invented
# phone numbers.
QUEUE_PREMISES = "Brazos Bend Reminder Estate"
QUEUE_ACCOUNT_COUNT = 340  # T5-23 / T7-16's own number
QUEUE_CHANNELS = ("email", "sms")
QUEUE_TIMEZONE = "America/Chicago"  # both journeys name it
#: 22:15 on the TENANT's clock, which is what BR-NOT-009 counts. On 2026-08-12
#: America/Chicago is CDT (UTC−5), so 22:15 local is 03:15 UTC the next day —
#: written as UTC because that is what the column stores (BR-TEN-020), and
#: derived here rather than typed as "03:15" with no explanation.
QUEUE_FIRED_AT_LOCAL = "2026-08-12 22:15"
QUEUE_SOURCE_TYPE = "notice"
#: A queue row must say WHAT will render it — the template code or a pin —
#: or `queue_document` refuses: *"the dispatcher has a recipient and a channel
#: and no idea what to put in the envelope"*. `dunning` is the seeded
#: notification template a payment reminder renders from
#: (`notifications/seed_templates.py`), read by NAME rather than invented.
QUEUE_TEMPLATE_CODE = "dunning"

#: ⚠ **WHAT THE JOURNEYS ASK FOR IS NOT WHAT THE QUEUE HOLDS, AND THE DIFFERENCE
#: IS A SIGNED RULE (`DEF-2467`, 2026-08-30).** T5-23 and T7-16 say *"channels:
#: email + SMS"*, and that is still exactly what this fixture ASKS for. But
#: `QUEUE_SOURCE_TYPE` is `notice`, and the PO ruled on 2026-08-29 that print is
#: the floor on every customer document rather than on bills alone. `BR-NOT-024`
#: was amended to six source kinds, so `queue_document` now adds a `pdf_print`
#: row to every one of these writes: **340 accounts hold 1,020 rows, not 680**,
#: and the journeys' own number is the pre-ruling one.
#:
#: **DERIVED, NEVER RE-TYPED — that is the whole point of the constant.** A
#: second hand-copied list is how `DEF-738` put a tax out of reach of half the
#: platform's customer types, and it is why this cohort sat red: the floor moved,
#: the fixture did not, and a count described as *"this cohort's whole content"*
#: quietly described a world with one fewer channel. Ask the rule. If the floor
#: widens again this follows it, and if somebody narrows it back the arithmetic
#: moves on its own.
#:
#: The import is local for the same reason every other `apps` import in this file
#: is: this module is imported by fixtures that run before Django is configured.
def _queue_row_channels() -> tuple[str, ...]:
    from apps.notifications import services as notification_services

    return tuple(
        dict.fromkeys(
            (
                *QUEUE_CHANNELS,
                *notification_services.CHANNEL_FLOOR_BY_SOURCE.get(QUEUE_SOURCE_TYPE, ()),
            )
        )
    )

T717_TEMPLATE_CODE = "staff_bulk_summary"
#: T7-17's drop and the seeded batch size it drains at. 2,000 ÷ 500 = FOUR
#: hand-offs, which is what makes its step 4 (*"changes the size to 200 after
#: the 2nd hand-off"*) observable at all.
T717_QUEUE_ROWS = 2000
T717_BATCH_SIZE = 500  # notifications.models.SEEDED_BATCH_SIZE — asserted, not written


#: A fixed uuid5 namespace for this cohort's synthetic source ids. Fixed, not
#: random, for the reason the function below states.
QUEUE_NAMESPACE = __import__("uuid").UUID("c0140000-0000-5000-8000-000000000014")


def _reminder_source_id(label: str):
    """A deterministic source id, so a re-boot re-queues nothing (rule 6).

    `outbound_messages` is unique on the source ref × channel (hard rule 6), so
    a random uuid per pass would mint a SECOND 680 rows on every boot and the
    count the journeys assert would drift upward forever.
    """
    import uuid

    return uuid.uuid5(QUEUE_NAMESPACE, label)


def ensure_unit_series_ahead_of_the_data(tenant, actor) -> dict[str, Any]:
    """Advance the `unit` number series past the highest unit that exists.

    ⚠ **THIS IS A WORKAROUND FOR DEF-577, AND IT IS NOT COSMETIC.** On the demo
    tenant the `unit` series stood at **next_number 102** while units up to
    **U-00420** already existed, so the next unit created through the real
    service raised `IntegrityError: duplicate key value violates unique
    constraint "uq_units_tenant_unit_no" … (unit_no)=(U-00102) already exists`
    — measured, while seeding this cohort's 340th account. Some path creates
    units without allocating from the series, and every later creation through
    S16 collides until the counter catches up past them one failure at a time.
    Filed as DEF-577; not this lane's to fix.

    The repair goes through `tenancy.services.save_number_series`, which is the
    S63 act an admin would perform and is **forward-only by rule** (BR-TEN-035:
    issued numbers are never renumbered). A fixture that reached for the column
    would be doing by hand what the product already exposes correctly.
    """
    import re

    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models
    from apps.tenancy import services as tenancy_services

    row = tenancy_models.NumberSeries.objects.filter(tenant=tenant, series="unit").first()
    if row is None:
        return {"series": None, "advanced_to": None, "reason": "no `unit` series on this tenant"}
    highest = 0
    for unit_no in metering_models.Unit.objects.filter(tenant=tenant).values_list(
        "unit_no", flat=True
    ):
        match = re.search(r"(\d+)\s*$", unit_no or "")
        if match:
            highest = max(highest, int(match.group(1)))
    if row.next_number > highest:
        return {"series": "unit", "advanced_to": None, "highest_existing": highest}
    tenancy_services.save_number_series(actor, "unit", next_number=highest + 1)
    return {"series": "unit", "advanced_to": highest + 1, "highest_existing": highest}


def ensure_reminder_queue_cohort(tenant, actor) -> dict[str, Any]:
    """T5-23 / T7-16 — 340 accounts and the 680 rows a bulk reminder queues.

    The accounts carry EMAIL CONTACTS because otherwise the rows would be
    unaddressed and `dispatcher._selectable` would skip them for a reason
    neither journey describes — the quiet-hours hold would then be invisible
    behind a missing-address hold, and a window change would release nothing.
    """
    import uuid

    from apps.customers import models as customer_models
    from apps.notifications import models as notification_models
    from apps.notifications import services as notification_services
    from apps.tenancy import services as tenancy_services

    notification_services.seed_notification_settings(actor)
    settings_row = notification_models.NotificationSettings.objects.get(tenant=tenant)
    tenancy_services.save_regional_settings(actor, {"timezone": QUEUE_TIMEZONE})

    series = ensure_unit_series_ahead_of_the_data(tenant, actor)
    premises_id = _premises_for(tenant, actor, QUEUE_PREMISES, ["electric"])
    accounts: list[Any] = []
    for index in range(1, QUEUE_ACCOUNT_COUNT + 1):
        label = f"RM-{index:03d}"
        account_no = f"ACC-5{index:03d}"
        unit_id = _unit_on(tenant, actor, premises_id, label, ["electric"])
        account = _account(tenant, unit_id, account_no)
        customer_models.Contact.objects.get_or_create(
            tenant=tenant,
            account=account,
            email=f"{account_no.lower()}@brazosbend.example",
            defaults={"full_name": f"Reminder Cohort {index:03d}", "is_primary": True},
        )
        accounts.append(account)

    queued = 0
    for account in accounts:
        notification_services.queue_document(
            source_type=QUEUE_SOURCE_TYPE,
            source_id=_reminder_source_id(f"reminder:{account.account_no}"),
            channels=QUEUE_CHANNELS,
            template=notification_services.TemplatePin(code=QUEUE_TEMPLATE_CODE),
            account_id=str(account.id),
            actor=actor,
            job="CR-014 T5-23/T7-16 fixture",
        )
        queued += 1

    rows = notification_models.OutboundMessage.objects.filter(
        tenant=tenant, source_type=QUEUE_SOURCE_TYPE
    )
    total = rows.count()
    row_channels = _queue_row_channels()
    expected = QUEUE_ACCOUNT_COUNT * len(row_channels)
    if total != expected:
        raise CohortCannotSeed(
            f"the queue holds {total} rows for {QUEUE_ACCOUNT_COUNT} accounts on "
            f"{len(row_channels)} channels ({', '.join(row_channels)} — "
            f"{len(row_channels) - len(QUEUE_CHANNELS)} added by BR-NOT-024's print floor); "
            f"the journeys' own text says {QUEUE_ACCOUNT_COUNT * len(QUEUE_CHANNELS)} and the "
            f"rule makes it {expected}. A "
            "count is this cohort's whole content — a queue journey over the wrong number "
            "asserts nothing about batching or about quiet hours."
        )
    addressed = rows.filter(recipient_address__isnull=False).count()
    held = rows.filter(held=True).count()
    if held:
        raise CohortCannotSeed(
            f"{held} of the queued rows carry `held=True`. That column is BR-PAY-018's PAPER "
            "SUPPRESSION (the address is known bad) and a held row is skipped by every cycle "
            "until an address verification releases it — a WINDOW change never can. T7-16's "
            "whole subject is moving the quiet-hours window and watching these rows go, so a "
            "held row would make its assertion permanently false."
        )
    return {
        "accounts": len(accounts),
        "queued_documents": queued,
        "rows": total,
        "addressed_rows": addressed,
        "unaddressed_rows": total - addressed,
        "channels": list(row_channels),
        "channels_asked_for": list(QUEUE_CHANNELS),
        "timezone": QUEUE_TIMEZONE,
        "quiet_hours": f"{settings_row.quiet_hours_start:%H:%M}–{settings_row.quiet_hours_end:%H:%M}",
        "batch_size": settings_row.dispatch_batch_size,
        "fired_at_local": QUEUE_FIRED_AT_LOCAL,
        "held_rows": held,
        "unit_series": series,
    }


def ensure_dispatch_drop_cohort(tenant, actor) -> dict[str, Any]:
    """T7-17 — 2,000 QUEUED EMAIL rows, and a batch size that divides them.

    2,000 ÷ 500 = four hand-offs. That division is the fixture: the journey
    changes the size to 200 *after the second hand-off*, and over a drop that
    fits in one batch there is no second hand-off to change anything after.

    The rows ride the reminder cohort's accounts, which already carry email
    contacts — an unaddressed row is never selected by a cycle
    (`dispatcher._selectable`), so 2,000 unaddressed rows would drain in ZERO
    hand-offs and the journey would assert over an empty batch loop.
    """
    from apps.notifications import models as notification_models
    from apps.notifications import services as notification_services

    base = ensure_reminder_queue_cohort(tenant, actor)
    from apps.customers import models as customer_models

    accounts = list(
        customer_models.Account.objects.filter(
            tenant=tenant, account_no__startswith="ACC-5"
        ).order_by("account_no")
    )
    if not accounts:
        raise CohortCannotSeed("the reminder cohort's accounts are missing after seeding it.")

    existing = notification_models.OutboundMessage.objects.filter(
        tenant=tenant, source_type="report", channel="email"
    ).count()
    for index in range(existing, T717_QUEUE_ROWS):
        account = accounts[index % len(accounts)]
        notification_services.queue_document(
            source_type="report",
            source_id=_reminder_source_id(f"drop:{index:05d}"),
            channels=("email",),
            template=notification_services.TemplatePin(code=T717_TEMPLATE_CODE),
            account_id=str(account.id),
            actor=actor,
            job="CR-014 T7-17 fixture",
        )
    drop = notification_models.OutboundMessage.objects.filter(
        tenant=tenant, source_type="report", channel="email"
    )
    total = drop.count()
    if total != T717_QUEUE_ROWS:
        raise CohortCannotSeed(
            f"the drop holds {total} email rows and T7-17 states {T717_QUEUE_ROWS}. The "
            f"number is the fixture: {T717_QUEUE_ROWS} ÷ {T717_BATCH_SIZE} is FOUR hand-offs, "
            "and the journey changes the batch size after the second one."
        )
    addressed = drop.filter(recipient_address__isnull=False).count()
    if not addressed:
        raise CohortCannotSeed(
            "not one of the dropped rows carries a recipient address, and "
            "`dispatcher._selectable` never claims an unaddressed row — the drop would drain "
            "in ZERO hand-offs and the journey would assert over an empty batch loop."
        )
    return {
        **base,
        "drop_rows": total,
        "drop_addressed": addressed,
        "batches_at_seeded_size": -(-total // int(base["batch_size"])),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-014 (12-governance/11-change-requests.md) · W11 lane 2026-08-22
# generated: 2026-08-22
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: tests/test_cr014_journey_cohorts.py (red-proved) · golden 33/33 ·
#        seed_journey_fixture.py --check / --journey output quoted in the report
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
