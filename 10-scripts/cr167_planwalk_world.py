# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 4 task 10 — the plans FULL WEB WALK
#          (`05-prototype/plans-2026-10-03/web-walk.md`). The walk's
#          back-office half: the world it stands on (Utility A's services,
#          deposit and class-priced late-fee codes, accounts, meters, reads;
#          Utility B), the water schedule's new version (phase 5), billing's
#          one-version lookup (phase 7) and the REAL bill runs (phase 8).
#          Every PLAN is created, viewed and edited through the screen by
#          `cr167_planwalk.mjs`; nothing here writes a plan except `assign`,
#          which puts walk units on plans the screen already made.
#          Shape copied from `cr166_discwalk_world.py`.
# ───────────────────────────────────────────────────────
"""cr167_planwalk_world — the plans walk's world and its bill runs, on PostgreSQL.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/cr167_planwalk_world.py setup

Run after `manage.py migrate` + `manage.py seed_demo` (Brazos Bend = Utility A).

``setup`` (idempotent):
  * water, sewer, trash and fire switched on (the Settings act), THEN the
    product's own `load_sample_data` — so every one of the four services has
    the sample schedule the plan form offers (water inclining tiers, sewer as a
    % of water, trash per cart, fire capacity by line size), the base codes
    `BASE-W` / `BASE-S` / `BASE-T` / `BASE-FIRE`, the two taxes and the
    discounts (the taxes and discounts walks' worlds stand on the same seed);
    the eight customer classes are the seed's;
  * three charge codes the walk's plans name, through `services.create_charge`
    (the Charge codes screen's write), the walk's own figures, never signed law:
      - `DEPOSIT`  Security deposit, refundable, by CLASS — Residential
        $150.00, Commercial $300.00;
      - `DEP-SIZE` Security deposit by meter size, refundable, water — 5/8"
        $150.00, 2" $600.00 (the PO's worked figures, `OQ-RAT-12786`);
      - `LATE-CL`  Late fee by class, penalty — Residential 1.5 % (min $5.00),
        Commercial 2 % (min $10.00);
  * Utility B (`riverbend`, owner `ops@riverbend.example`) with no plans of
    the walk's (it is provisioned with the product's defaults).

``assign <plan code>`` (after the screen made the plan): two premises on
Pecan Walk Way, each with a unit on water + sewer and a 5/8" water meter read
monthly 10/31/2026 … 01/31/2027 (100, 108, 116, 124 kgal → 8 kgal a month);
one account each (Ruth Alvarez inside the city, Carl Jensen OUTSIDE it —
residential; the plan's 25 % surcharge reaches Carl's water and sewer) — and a
THIRD unit with no account (vacant, on the plan but in no cycle, for the Units
tab's occupancy filter). Each account's deposit is REQUIRED (the plan's
figure), not taken today. For a
commercial plan code, one account (Riverside Café — commercial). All on cycle
`PLANWALK` (start day 1, bill day 31). Prints the accounts.

``schedule_v2 <tariff name> <from> <factor>`` — phase 5: a new version of the
named rate schedule from <from>, every tier price × <factor>, through
`services.create_rate_schedule_version` (the rate-schedule screen's write).

``lookup <plan code> <day>…`` — phase 7: what billing is handed for the plan on
each day — `plan_versioning.version_on` and R1's candidates
(`resolution_catalogue.plan_version_facts`) that cover the day.

``vacant <plan code> <number> [size]`` — the RE-WALK's (2.494.0 → 2.495.2)
deposit size pick (`DEF-CUS-9521`): a vacant unit on the plan with NO meter
(or a meter of ``size``, e.g. ``W-58``), in no cycle, for the screen to open an
account on.

``run <start> <end>`` / ``preview <start> <end>`` — a real cycle run (issued /
rolled back), printing every walk account's bill lines. ``bills`` — every
issued bill of every walk account.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

CYCLE_CODE = os.environ.get("PLANWALK_CYCLE", "PLANWALK")
STREET = "Pecan Walk Way"
#: key, display name, class, street number, plan role
ACCOUNTS = {
    "res": (
        ("PW-RUTH", "Ruth Alvarez", "residential", "11"),
        ("PW-CARL", "Carl Jensen", "residential", "13"),
    ),
    "com": (("PW-CAFE", "Riverside Cafe", "commercial", "31"),),
}
VACANT = {"res": "15", "com": "33"}
READS = (("2026-10-31", "100"), ("2026-11-30", "108"), ("2026-12-31", "116"), ("2027-01-31", "124"))
UNIT_LABEL = "Main"

UTILITY_B = {
    "name": "Riverbend Water",
    "subdomain": "riverbend",
    "state": "Iowa",
    "services": ["water"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {
        "full_name": "Rae Lindqvist",
        "email": "ops@riverbend.example",
        "password": "S3cure!passw0rd",  # walk fixture credential — never prod
        "phone": "+1 (641) 555-0110",
    },
}

CODES = (
    {
        "code": "DEPOSIT", "name": "Security deposit", "charge_type": "refundable",
        "amount_rule": "flat", "is_base": False, "effective_from": "2026-08-01",
        "size_amounts": [
            {"size_class": "All sizes", "customer_class": "residential", "amount": "150.00"},
            {"size_class": "All sizes", "customer_class": "commercial", "amount": "300.00"},
        ],
    },
    {
        "code": "DEP-SIZE", "name": "Security deposit by meter size", "charge_type": "refundable",
        "service": "water", "amount_rule": "flat", "is_base": False, "effective_from": "2026-08-01",
        "size_amounts": [
            {"size_class": "W-58", "amount": "150.00"},
            {"size_class": "W-2", "amount": "600.00"},
        ],
    },
    {
        "code": "LATE-CL", "name": "Late fee by class", "charge_type": "penalty",
        "amount_rule": "percent_with_minimum", "is_base": False, "effective_from": "2026-08-01",
        "class_terms": [
            {"customer_class": "residential", "percent": "0.015", "min_amount": "5.00"},
            {"customer_class": "commercial", "percent": "0.02", "min_amount": "10.00"},
        ],
    },
)


def _sjf():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _ctx():
    from core import tenancy as core_tenancy

    tenant, actor = _sjf().tenant_and_actor()
    return tenant, actor, lambda: core_tenancy.tenant_context(tenant.id)


def setup() -> None:
    from django.core.management import call_command

    from apps.rating import models as rm
    from apps.rating import services as rsvc
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc
    from tests.journey_cohort_fixtures import ensure_services_enabled

    if not tm.Tenant.objects.filter(subdomain=UTILITY_B["subdomain"]).exists():
        from core import jobs as core_jobs

        previous = core_jobs._dispatcher  # noqa: SLF001 — a developer database has no broker
        core_jobs.set_job_dispatcher(lambda _record: None)
        try:
            made = tsvc.provision_tenant({**UTILITY_B, "owner": dict(UTILITY_B["owner"])})
        finally:
            core_jobs.set_job_dispatcher(previous)
        print("Utility B provisioned:", made.get("subdomain", made.get("id")))
    else:
        print("Utility B exists")
    tenant, actor, ctx = _ctx()
    with ctx(), transaction.atomic():
        print("services on:", ensure_services_enabled(tenant, actor, "water", "sewer", "trash", "fire"))
    with ctx():
        sampled = rm.RatePlan.objects.filter(tenant=tenant, code="SCW-RES").exists()
    if not sampled:
        call_command("load_sample_data", tenant="brazosbend")
    with ctx(), transaction.atomic():
        for spec in CODES:
            if rm.Charge.objects.filter(tenant=tenant, code=spec["code"]).exists():
                print("exists", spec["code"])
                continue
            rsvc.create_charge(actor, dict(spec))
            print("created", spec["code"])
    facts()


def facts() -> None:
    """What the plan form will offer Utility A — printed for the report."""
    from apps.rating import plan_reads

    _tenant, _actor, ctx = _ctx()
    with ctx():
        options = plan_reads.form_options()
    print("CLASSES", [c["label"] for c in options["customer_classes"]])
    print("SERVICES", [s["value"] for s in options["services"]])
    for row in options["schedules"]:
        base = row.get("base") or {}
        print("SCHEDULE", row["service"], row["ref"]["name"], "v", row["ref"]["version"], row["ref"]["effective_from"],
              "base", base.get("state"), base.get("codes"), [s.get("size_label") for s in base.get("by_size") or []])
    for key in ("charge_codes", "taxes", "deposit_codes", "discounts"):
        print(key.upper(), [(r["ref"]["code"], r["ref"]["name"], r.get("priced_by")) for r in options[key]])


def _cycle(tenant, code=None):
    from apps.metering import models as mm

    cycle, _ = mm.Cycle.objects.get_or_create(
        tenant=tenant, code=code or CYCLE_CODE,
        defaults={"name": "Plans walk", "frequency": "Monthly", "start_day": 1, "days_to_complete": 30,
                  "bill_day": 28, "due_days": 21, "first_run_date": date(2026, 11, 1)},
    )
    return cycle


def assign(plan_code: str) -> None:
    from apps.assets import models as am
    from apps.customers import models as cm
    from apps.customers import services as csvc
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import models as rm
    from tests.journey_cohort_fixtures import _premises_for, _unit_on
    from tests.test_us_met_reads_helpers import a_meter, at, commit_read

    role = "com" if "COM" in plan_code.upper() else "res"
    tenant, actor, ctx = _ctx()
    with ctx(), transaction.atomic():
        plan = rm.RatePlan.objects.get(tenant=tenant, code=plan_code)
        cycle = _cycle(tenant)
        services = ["water", "sewer"]
        homes = [(key, name, kind, number) for key, name, kind, number in ACCOUNTS[role]]
        homes.append((None, None, None, VACANT[role]))
        for key, display, kind, number in homes:
            street = f"{number} {STREET}"
            premises_id = _premises_for(tenant, actor, street, services)
            unit_id = _unit_on(tenant, actor, premises_id, UNIT_LABEL, services)
            unit = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
            if unit.rate_plan_id is None:
                msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-11-01"})
            mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=cycle)
            if key is None:
                # A vacant unit is on the plan (the Units tab's Vacant filter)
                # but in no cycle: a unit in a cycle with no account blocks
                # the run (`unit_has_no_billable_account`), rightly.
                mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=None)
                print("VACANT", street, unit.unit_no)
                continue
            # The residential plan surcharges outside the city (25 %), so every
            # billed premises states which side it is on (BR-RAT-101) — the
            # run refuses a premises that does not. Ruth (11) inside, Carl (13)
            # OUTSIDE, the café (31) inside. Through the S14 edit's service.
            premises = mm.Premises.objects.get(tenant=tenant, pk=premises_id)
            inside = number != "13"
            if premises.inside_city_limits is not inside:
                msvc.update_premises(actor, premises_id, {"inside_city_limits": inside})
            meter_no = f"W-{key}"
            meter = am.Asset.objects.filter(tenant=tenant, asset_no=meter_no).first()
            meter_id = str(meter.id) if meter else a_meter(
                actor, asset_no=meter_no, service="water", uom="kgal", unit_id=unit_id, size_class="W-58"
            )["id"]
            prior = None
            for day, value in READS:
                if not mm.MeterRead.objects.filter(tenant=tenant, asset_id=meter_id, read_at=at(day), channel="total").exists():
                    commit_read(actor, meter_id, day=day, value=value, prior_value=prior,
                                consumption=None if prior is None else str(Decimal(value) - Decimal(prior)), unit="kgal")
                prior = value
            if not cm.Account.objects.filter(tenant=tenant, unit_id=unit_id).exists():
                slug = display.lower().replace(" ", ".")
                created = csvc.create_account(actor, {
                    "unit_id": str(unit_id), "account_type": kind, "opened_at": "2026-11-01",
                    "contact": {"full_name": display, "phone": "+1 (641) 555-0171", "email": f"{slug}@planwalk.example"},
                    "customer": {"display_name": display, "kind": "person" if kind == "residential" else "company",
                                 "identity": {"phone": "+1 (641) 555-0171"} if kind == "residential" else {"tax_id": "42-1234567"}},
                    "addresses": [{"kind": "mailing", "line1": street, "city": "Ottumwa", "state": "IA"}],
                    # The plan asks a deposit (DEP-SIZE 5/8" $150.00 on the
                    # residential plan, DEPOSIT Commercial $300.00): REQUIRED,
                    # not taken today — it is billed on the account's first
                    # bill, which is what phase 8 checks is never billed twice.
                    "deposit": {"decision": "required", "amount": "150.00" if kind == "residential" else "300.00",
                                "due_on": "2026-11-01"},
                })
                csvc.activate_account(actor, created["id"], None)
    accounts()


def vacant(plan_code: str, number: str, size_class: str = "") -> None:
    """RE-WALK (2.494.0, the deposit size pick, `DEF-CUS-9521`): a vacant
    unit ``<number> Pecan Walk Way`` on water + sewer, on ``<plan code>`` from
    11/01/2026, in no cycle and with NO account — and with NO meter unless a
    size is named (``W-58`` fits a 5/8" water meter, the *meter fitted* case).
    The screen then opens the account on it (New account or Move-in), which is
    what the walk checks; nothing here writes a deposit."""
    from apps.assets import models as am
    from apps.metering import models as mm
    from apps.metering import services as msvc
    from apps.rating import models as rm
    from tests.journey_cohort_fixtures import _premises_for, _unit_on
    from tests.test_us_met_reads_helpers import a_meter

    tenant, actor, ctx = _ctx()
    with ctx(), transaction.atomic():
        plan = rm.RatePlan.objects.get(tenant=tenant, code=plan_code)
        services = ["water", "sewer"]
        street = f"{number} {STREET}"
        premises_id = _premises_for(tenant, actor, street, services)
        unit_id = _unit_on(tenant, actor, premises_id, UNIT_LABEL, services)
        unit = mm.Unit.objects.get(tenant=tenant, pk=unit_id)
        if unit.rate_plan_id is None:
            msvc.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id), "effective_from": "2026-11-01"})
        mm.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_id).update(cycle=None)
        if size_class:
            meter_no = f"W-PW-{number}"
            if not am.Asset.objects.filter(tenant=tenant, asset_no=meter_no).exists():
                a_meter(actor, asset_no=meter_no, service="water", uom="kgal", unit_id=unit_id, size_class=size_class)
        print("VACANT", street, unit.unit_no, "meter", size_class or "none")


def accounts() -> None:
    from apps.customers import models as cm

    tenant, _actor, ctx = _ctx()
    out = {}
    with ctx():
        for role, rows in ACCOUNTS.items():
            for key, display, kind, number in rows:
                acct = cm.Account.objects.filter(
                    tenant=tenant, unit__premises__address_line=f"{number} {STREET}", unit__label=UNIT_LABEL
                ).first()
                if acct is not None:
                    out[key] = {"id": str(acct.id), "number": acct.account_no, "name": display, "class": kind,
                                "plan": getattr(acct.unit.rate_plan, "code", None), "unit": acct.unit.unit_no}
    print("ACCOUNTS " + json.dumps(out))


def schedule_v2(name: str, start: str, factor: str) -> None:
    from apps.rating import models as rm
    from apps.rating import selectors as rsel
    from apps.rating import services as rsvc

    tenant, actor, ctx = _ctx()
    with ctx(), transaction.atomic():
        tariff = rm.Tariff.objects.get(tenant=tenant, name=name)
        latest = rsel.latest_version(tariff)
        if latest.effective_from and latest.effective_from >= date.fromisoformat(start):
            # The first run of this command (2026-10-03) filed v2 WITHOUT the
            # schedule's size rows, and January's bills for 5/8" meters were
            # rightly refused (R3: no row for W-58). Corrected once, here, over
            # the same window — `BR-RAT-1016` verb 2 — with the rows carried.
            if not rm.RateSizeRow.objects.filter(tariff_version=latest).exists():
                prior = rm.TariffVersion.objects.filter(tariff=tariff, effective_from__lt=latest.effective_from).order_by("-effective_from").first()
                rows = [{"size_class": r.size_class, "minimum_bill": str(r.minimum_bill)}
                        for r in rm.RateSizeRow.objects.filter(tariff_version=prior)]
                tiers = list(rm.RateTier.objects.filter(tariff_version=latest).order_by("seq"))
                print(rsvc.correct_rate_schedule_version(actor, tariff.id, latest.id, {
                    "reason": "Size rows carried from v1 (left off by the walk's own filing)",
                    "name": tariff.name, "service": tariff.service.code, "model": latest.model, "uom": latest.uom,
                    "currency": latest.currency,
                    "structure": {"tiers": [{"from_qty": str(t.from_qty), "to_qty": None if t.to_qty is None else str(t.to_qty),
                                             "unit_price": str(t.unit_price)} for t in tiers]},
                    "size_rows": rows,
                }))
            else:
                print("exists", latest.effective_from)
            return
        tiers = list(rm.RateTier.objects.filter(tariff_version=latest).order_by("seq"))
        size_rows = [{"size_class": r.size_class, "minimum_bill": str(r.minimum_bill)}
                     for r in rm.RateSizeRow.objects.filter(tariff_version=latest)]
        payload = {
            "reason": "Water rates rise with the new year (plans walk)",
            "model": latest.model,
            "uom": latest.uom,
            "name": tariff.name,
            "service": tariff.service.code,
            "currency": latest.currency,
            "effective_from": start,
            "structure": {"tiers": [
                {"from_qty": str(t.from_qty), "to_qty": None if t.to_qty is None else str(t.to_qty),
                 "unit_price": str((t.unit_price * Decimal(factor)).quantize(Decimal("0.0001")))}
                for t in tiers
            ]},
            # The schedule's size axis travels: without it every sized meter's
            # bill is refused from the new date (R3).
            "size_rows": size_rows,
        }
        print(json.dumps(payload))
        print(rsvc.create_rate_schedule_version(actor, tariff.id, payload))


def lookup(plan_code: str, *days: str) -> None:
    from apps.rating import models as rm
    from apps.rating import plan_versioning, resolution_catalogue

    tenant, _actor, ctx = _ctx()
    with ctx():
        plan = rm.RatePlan.objects.get(tenant=tenant, code=plan_code)
        facts = resolution_catalogue.plan_version_facts(plan.id)
        for day in days:
            on = date.fromisoformat(day)
            version = plan_versioning.version_on(plan.id, on)
            covering = [
                f"v{c.version} {c.effective_from}..{c.effective_to}" for c in facts
                if (c.effective_from is None or c.effective_from <= on) and (c.effective_to is None or c.effective_to >= on)
            ]
            terms = plan_versioning.terms_on(plan, on)
            print(f"LOOKUP {plan_code} {day} version_on=v{getattr(version, 'version_no', None)} "
                  f"candidates={len(covering)} {covering} minimum={terms.get('minimum_bill_amount')}")


def _template():
    from apps.billing import template_models as tpl
    from core import tenancy as core_tenancy

    row = (
        tpl.BillTemplateVersion.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), status=tpl.VERSION_PUBLISHED,
            template__template_type=tpl.TYPE_BILL,
        ).order_by("template__name", "-version_no").first()
    )
    return row.template_id, int(row.version_no)


class _Rollback(Exception):
    pass


def run(start: str, end: str, *, preview: bool = False) -> None:
    from apps.billing import decisions, issue, runs
    from apps.metering import models as mm

    period_start, period_end = date.fromisoformat(start), date.fromisoformat(end)
    tenant, actor, ctx = _ctx()
    with ctx(), transaction.atomic():
        cycle = mm.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)
        template_id, template_version = _template()
        user = getattr(actor, "user", None)
        bill_run = runs.create_run(
            cycle_id=cycle.id, period_start=period_start, period_end=period_end, bill_date=period_end,
            due_days=21, label=f"Plans walk {end}", template_id=template_id, run_by=user,
        )
        prepared = runs.prepare_run(cycle_id=cycle.id, period_start=period_start, period_end=period_end,
                                    service_date=period_end)
        for row in getattr(prepared, "blocked", []) or []:
            print("  BLOCKED:", {k: getattr(row, k, None) for k in ("account_id", "account_no", "reason", "detail", "message", "code")})
        for row in prepared.decisions:
            print("  decision asked:", row.account_id, row.reason)
            if row.reason == "base_only_billing":
                decisions.record_decision(bill_run=bill_run, account_id=str(row.account_id),
                                          case="base_only_billing", choice="include")
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=bill_run), bill_run=bill_run)
        from apps.billing import models as bm

        for model in (bm.BillRunExclusion, bm.BillRunBreak):
            for row in model.objects.filter(bill_run=bill_run):
                fields = {f.name: getattr(row, f.name) for f in model._meta.fields
                          if f.name not in ("tenant", "bill_run", "created_at", "updated_at")}
                print(f"  {model.__name__}: {fields}")
        if preview:
            print(f"PREVIEW {start}..{end} (rolled back, nothing kept):")
            bills(period_end=period_end)
            raise _Rollback
        issue.issue_run(bill_run, issued_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
                        template_id=template_id, template_version=template_version,
                        require_release=False, actor=user)
        runs.record_run_outcome(bill_run, actor=user)
        print(f"run {bill_run.run_no or bill_run.pk} {start}..{end}")
    bills(period_end=period_end)


def bills(period_end: date | None = None) -> None:
    from apps.billing import models as bm
    from apps.customers import models as cm

    tenant, _actor, ctx = _ctx()
    with ctx():
        for role, rows in ACCOUNTS.items():
            for key, _display, _kind, number in rows:
                acct = cm.Account.objects.filter(
                    tenant=tenant, unit__premises__address_line=f"{number} {STREET}", unit__label=UNIT_LABEL
                ).first()
                if acct is None:
                    continue
                invoices = bm.Invoice.objects.filter(account=acct)
                if period_end is not None:
                    invoices = invoices.filter(period_end=period_end)
                for inv in invoices.order_by("period_end", "created_at"):
                    lines = list(bm.InvoiceLine.objects.filter(invoice=inv).order_by("kind", "id"))
                    print(f"BILL {key} {acct.account_no} {inv.invoice_no or inv.pk} id={inv.pk} · "
                          f"{inv.period_start}..{inv.period_end} · {inv.status} · total {Decimal(inv.total):.2f}")
                    for line in lines:
                        print(f"   {line.kind:<12} {line.description!s:<48} qty={line.quantity} {Decimal(line.amount):.4f}")


def recycle(code: str, *keys: str) -> None:
    """Move the named walk accounts' service points to cycle <code> (made like
    `PLANWALK`). Used ONCE on 2026-10-03 and said so in the walk report: the
    first January run (`RUN-0004`) refused Ruth's and Carl's bills because this
    script's first `schedule_v2` filed water v2 without the schedule's size
    rows (R3, rightly); BR-BIL-005 then refuses a second run over the same
    cycle and period, so their January is billed on its own cycle."""
    from apps.customers import models as cm
    from apps.metering import models as mm

    tenant, _actor, ctx = _ctx()
    numbers = {k: n for rows in ACCOUNTS.values() for k, _d, _c, n in rows}
    with ctx(), transaction.atomic():
        cycle = _cycle(tenant, code)
        for key in keys:
            acct = cm.Account.objects.get(tenant=tenant, unit__premises__address_line=f"{numbers[key]} {STREET}", unit__label=UNIT_LABEL)
            moved = mm.ServicePoint.objects.filter(tenant=tenant, unit_id=acct.unit_id).update(cycle=cycle)
            print("RECYCLED", key, acct.account_no, "→", code, moved)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if command == "setup":
        setup()
    elif command == "facts":
        facts()
    elif command == "assign":
        assign(sys.argv[2])
    elif command == "recycle":
        recycle(sys.argv[2], *sys.argv[3:])
    elif command == "vacant":
        vacant(*sys.argv[2:])
    elif command == "accounts":
        accounts()
    elif command == "schedule_v2":
        schedule_v2(*sys.argv[2:])
    elif command == "lookup":
        lookup(sys.argv[2], *sys.argv[3:])
    elif command == "run":
        run(sys.argv[2], sys.argv[3])
    elif command == "preview":
        try:
            run(sys.argv[2], sys.argv[3], preview=True)
        except _Rollback:
            pass
    elif command == "bills":
        bills()
    else:
        raise SystemExit(f"unknown command {command}")
