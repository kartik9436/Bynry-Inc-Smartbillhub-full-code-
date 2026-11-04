"""CR-166-BRC10 round 1 task 2 — REPRODUCE the four discount lifecycle facts the
PO ruled on 2026-10-03 (decision log *"GO ON THE DISCOUNTS REDESIGN"*), on
PostgreSQL 16, through the product's OWN services. It changes no product code.

The four facts, as the decision row states today's behaviour:
  (a) an approved discount does not go live on its start date without Activate;
  (b) an account whose plan does not carry the discount can still be enrolled
      and discounted, and removing a discount from a plan stops nobody;
  (c) an Automatic discount enrolls nobody;
  (d) after Retire, already-enrolled accounts keep the discount.

Each is asked of the code rather than assumed, and the script prints what the
code answers — including where the answer is NOT what the row says. Two reads
are asked on purpose for "discounted": `discount_rules_for_account` (the R6
door every enrolment-facing read uses) and `selectors.billable_discount_rules`
(what `billing/gather.py::_discounts_for` hands the bill run, which also applies
the plan's binding, BR-RAT-110). They can disagree, and that disagreement is a
finding.

⚠ EVERYTHING RUNS INSIDE ONE TRANSACTION THAT IS ROLLED BACK AT THE END, so the
scratch database is left exactly as it was seeded (the before-walk reads it).

RUN IT (scratch database seeded with `migrate`, `seed_demo`,
`load_sample_data --tenant brazosbend`):

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_discr1 JOBS_EAGER=false \\
      python ../10-scripts/cr166_discount_lifecycle_facts.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402
from core.permissions import SYSTEM_ADMIN  # noqa: E402

SUBDOMAIN = os.environ.get("SEED_TENANT", "brazosbend")


class Actor:
    def __init__(self, user_id):
        self.id = self.pk = user_id
        self.role = SYSTEM_ADMIN
        self.roles = (SYSTEM_ADMIN,)
        self.is_authenticated = True


class Rollback(Exception):
    pass


def say(*parts):
    print(*parts, flush=True)


def main() -> int:
    tenant = Tenant.objects.get(subdomain=SUBDOMAIN)
    say("database:", connection.settings_dict["NAME"], "· vendor:", connection.vendor,
        "· server:", connection.cursor().connection.info.server_version)
    with core_tenancy.tenant_context(str(tenant.id)):
        from apps.identity.models import User
        from apps.rating import discount_services as ds
        from apps.rating import discount_pricing as dp
        from apps.rating import discounts as dm
        from apps.rating import models as rm
        from apps.rating import seams as rseams
        from apps.rating import selectors, services
        from apps.customers import models as cm

        owner = User.objects.filter(email__iexact="dana@brazosbendutilities.com").first()
        actor = Actor(owner.id if owner else None)
        today = rseams.tenant_today()
        say("tenant today:", today)
        sixty = (dp.BillLine(service="water", kind="base", amount=Decimal("60.00")),)

        plan_res = rm.RatePlan.objects.get(tenant_id=tenant.id, code="SCW-RES")
        unit_ids = list(
            rm.UnitPlanAssignment.objects.filter(
                tenant_id=tenant.id, rate_plan=plan_res, assigned_to__isnull=True
            ).values_list("unit_id", flat=True)
        )
        accounts = list(
            cm.Account.objects.filter(tenant_id=tenant.id, unit_id__in=unit_ids).order_by("account_no")
        )
        say(f"plan {plan_res.code} '{plan_res.name}': {len(unit_ids)} units, {len(accounts)} accounts on them")
        acct = accounts[0]
        say("probe account:", acct.account_no)

        def code_of(d):
            return dm.Discount.objects.get(tenant_id=tenant.id, code=d)

        def bound_codes(plan):
            return sorted(
                dm.PlanDiscountRule.objects.filter(tenant_id=tenant.id, rate_plan=plan)
                .values_list("discount__code", flat=True)
            )

        try:
            with transaction.atomic():
                # ── (a) approved, start date passed, not live ─────────────────
                say("\n══ (a) an approved discount does not go live on its start date without Activate")
                start = today - timedelta(days=10)
                row = ds.create_discount(actor, {
                    "code": "FACTA", "name": "Fact A discount",
                    "discount_type": dm.DISCOUNT_PERCENTAGE, "value": "10",
                    "applies_to": dm.SCOPE_WHOLE_BILL,
                    "enrolment_mode": dm.ENROLMENT_APPLY_AND_APPROVE,
                    "verification_method": dm.VERIFY_AUTOMATIC,
                    "proof_required": False, "proof_before_first_reduction": False,
                    "budget_cap": "500", "effective_from": str(start),
                })
                facta = code_of("FACTA")
                ver = dm.DiscountVersion.objects.get(discount=facta, version_no=1)
                ds.submit_discount_version(actor, ver.id)
                ds.approve_discount_version(actor, ver.id)
                ver.refresh_from_db()
                facta.refresh_from_db()
                say(f"  start date {start} (10 days before today {today}); submitted and approved")
                say(f"  version status = {ver.status!r} · discount status = {facta.status!r}")
                say(f"  active_version(today) = {ds.active_version(facta, today)}")
                try:
                    ds.enrol_account(actor, facta.id, acct.id)
                    say("  enrol_account: ACCEPTED")
                except Exception as exc:  # noqa: BLE001
                    say(f"  enrol_account: REFUSED {type(exc).__name__} {getattr(exc, 'message_key', exc)}")
                ds.activate_discount_version(actor, ver.id)
                ver.refresh_from_db()
                say(f"  after Activate: version status = {ver.status!r} · active_version(today) = v{ds.active_version(facta, today).version_no}")

                # ── (b) off-plan enrolment; removal from a plan ───────────────
                say("\n══ (b) an account whose plan does not carry the discount; removing a discount from a plan")
                senior = code_of("SENIOR")
                say(f"  {plan_res.code} carries: {bound_codes(plan_res)} — SENIOR is not among them")
                enr = ds.enrol_account(actor, senior.id, acct.id, enrolled_on=date(2026, 8, 1))
                say(f"  enrol_account(SENIOR, {acct.account_no}) → ACCEPTED, verification {enr['verification_status']!r}")
                ds.verify_enrolment(actor, enr["id"], proof_kind=None, verified_on=date(2026, 8, 1))
                day = date(2026, 9, 15)
                r6 = ds.discount_rules_for_account(acct.id, day)
                say(f"  discount_rules_for_account on {day}: {[r.code for r in r6]}")
                out = ds.price_account_discounts(acct.id, sixty, day)
                say(f"  price_account_discounts on a $60.00 bill: {[(a.code, str(a.amount)) for a in out.applied]} → pays {out.subtotal_after}")
                billable = selectors.billable_discount_rules(acct.id, plan_res.id, day)
                say(f"  billable_discount_rules (what the BILL RUN reads): {[r['code'] for r in billable]}")
                say(f"  SENIOR's 'Enrolled' count on its list row / detail: {selectors.discount_enrolled_count(senior)}")

                autopay = code_of("AUTOPAY")
                enr2 = ds.enrol_account(actor, autopay.id, acct.id, enrolled_on=date(2026, 8, 1))
                billable = selectors.billable_discount_rules(acct.id, plan_res.id, day)
                say(f"  enrolled {acct.account_no} in AUTOPAY (bound to {plan_res.code}); bill run reads: {[r['code'] for r in billable]}")
                keep = [c for c in bound_codes(plan_res) if c != "AUTOPAY"]
                try:
                    with transaction.atomic():
                        services.update_plan(actor, plan_res.id, {
                            "discounts": [{"discount": c} for c in keep],
                            "reason": "Fact (b): take AUTOPAY off the plan.",
                        })
                    say("  update_plan without AUTOPAY: ACCEPTED")
                except NotImplementedError as exc:
                    say(f"  update_plan without AUTOPAY: REFUSED NotImplementedError: {exc}")
                say(f"  after the attempt {plan_res.code} carries: {bound_codes(plan_res)}")
                still = dm.DiscountEnrolment.objects.get(pk=enr2["id"])
                say(f"  the AUTOPAY enrolment is still open: ended_on={still.ended_on}")

                # ── (c) Automatic enrolls nobody ──────────────────────────────
                say("\n══ (c) an Automatic discount enrolls nobody")
                for code in ("AUTOPAY", "PAPERLESS", "MUNICIPAL"):
                    d = code_of(code)
                    v = ds.active_version(d, today)
                    say(f"  {code}: mode {v.enrolment_mode!r} · offered to {selectors.discount_offered_unit_count(d)} units · "
                        f"enrolled (sample data, before this script) "
                        f"{dm.DiscountEnrolment.objects.filter(discount=d, ended_on__isnull=True).exclude(pk__in=[enr2['id']]).count()}")
                on_plan = cm.Account.objects.filter(tenant_id=tenant.id, unit_id__in=unit_ids)
                say(f"  accounts on {plan_res.code} with autopay on: {on_plan.filter(autopay=True).count()} · paperless on: {on_plan.filter(paperless=True).count()}")
                ds.create_discount(actor, {
                    "code": "FACTC", "name": "Fact C everyone",
                    "discount_type": dm.DISCOUNT_FIXED_AMOUNT, "value": "1", "currency": "USD",
                    "applies_to": dm.SCOPE_WHOLE_BILL,
                    "enrolment_mode": dm.ENROLMENT_AUTOMATIC,
                    "verification_method": dm.VERIFY_AUTOMATIC,
                    "proof_required": False, "proof_before_first_reduction": False,
                    "budget_cap": "500", "effective_from": str(start),
                })
                factc = code_of("FACTC")
                vc = dm.DiscountVersion.objects.get(discount=factc, version_no=1)
                ds.submit_discount_version(actor, vc.id)
                ds.approve_discount_version(actor, vc.id)
                ds.activate_discount_version(actor, vc.id)
                ds.attach_discount_to_plan(actor, plan_res.id, factc.id)
                say(f"  new Automatic FACTC created, approved, activated and attached to {plan_res.code}: "
                    f"enrollments = {dm.DiscountEnrolment.objects.filter(discount=factc).count()} of {len(accounts)} accounts")

                # ── (d) Retire ────────────────────────────────────────────────
                say("\n══ (d) after Retire, already-enrolled accounts keep the discount")
                muni = code_of("MUNICIPAL")
                muni_enr = dm.DiscountEnrolment.objects.filter(discount=muni, ended_on__isnull=True).select_related("account").first()
                macct = muni_enr.account
                mplan = rm.UnitPlanAssignment.objects.get(unit_id=macct.unit_id, assigned_to__isnull=True).rate_plan_id
                for when in (date(2026, 9, 15),):
                    say(f"  before Retire, MUNICIPAL on {macct.account_no} ({when}): R6 {[r.code for r in ds.discount_rules_for_account(macct.id, when)]} · "
                        f"bill run {[r['code'] for r in selectors.billable_discount_rules(macct.id, mplan, when)]}")
                ds.retire_discount(actor, muni.id)
                muni.refresh_from_db()
                muni_enr.refresh_from_db()
                say(f"  retire_discount(MUNICIPAL) took no date; discount status = {muni.status!r}; enrolment ended_on = {muni_enr.ended_on}")
                say(f"  Enrolled count still shown: {selectors.discount_enrolled_count(muni)}")
                for when in (date(2026, 8, 15), date(2026, 9, 15), date(2026, 12, 15)):
                    say(f"  after Retire, on {when}: R6 {[r.code for r in ds.discount_rules_for_account(macct.id, when)]} · "
                        f"bill run {[r['code'] for r in selectors.billable_discount_rules(macct.id, mplan, when)]}")
                try:
                    ds.enrol_account(actor, muni.id, acct.id)
                    say("  new enrolment after Retire: ACCEPTED")
                except Exception as exc:  # noqa: BLE001
                    say(f"  new enrolment after Retire: REFUSED {getattr(exc, 'message_key', exc)}")
                raise Rollback
        except Rollback:
            say("\n(rolled back — the scratch database is unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
