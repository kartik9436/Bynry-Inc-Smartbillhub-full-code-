# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-060 · US-CWP-062 · US-CWP-063 · US-CWP-065 · US-CWP-066
#          (EP-CWP-11) — the customer portal's Requests hub, Stop or restart,
#          Track your request, Dispute a bill and Ask a question.
#          Screens CWP-046 · CWP-052 · CWP-051 · CWP-055 · CWP-054.
# Rules:   BR-CWP-076 (every portal row carries channel `customer_portal`) ·
#          BR-CWP-078 (transitions plus customer-visible notes, never an
#          internal routing comment) · BR-CWP-081 (both figures, and the
#          cheaper option NAMED) · BR-CWP-029 (a credential attaches to
#          somebody already on file) · hard rule 1 (every read and write names
#          its tenant EXPLICITLY — this runs as a superuser with RLS skipped)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-i-requests-and-disputes.mjs
# ───────────────────────────────────────────────────────
"""THE STATE WAVE I's SCREENS ARE NORMALLY IN — WHICH IS NOT THE STATE
`seed_portal_demo` LEAVES THEM IN.

WHY THIS FILE EXISTS, AND THE MEASUREMENT THAT MADE IT NECESSARY
----------------------------------------------------------------
Five of wave I's seven screens are built. Run the walkthrough against a plain
`seed_portal_demo` database and **four of the five draw an empty branch**:

  * `CWP-046` — no request has ever been raised through the portal, so the
    OPEN REQUESTS panel is the *nothing here yet* sentence and the table,
    its four columns, its status chip and its row icon are never drawn;
  * `CWP-051` — there is no `SR-` number to open, so the screen cannot be
    reached at all;
  * `CWP-055` — `1408 Elm St · A` carries **zero invoices**, so there is no
    bill number to put in the address and the screen 404s;
  * `CWP-054` — the *Which bill* control has an empty option list.

⚠ **AND THE FIFTH IS THE ONE THAT MATTERS MOST, BECAUSE IT LOOKS FINE.**
`CWP-052` renders. It draws its form, its consequence box and its commit
button, and it says — honestly — that it cannot work the comparison out. That
comparison is the entire screen (`US-CWP-062` §7: *"the recommendation must be
computed, not hardcoded"*) and `BR-CWP-081` is this wave's own exit test.
**Measured on 2026-09-06 over every account on the demo tenant: 0 of 73 can
produce a verdict.** Ten are refused a standing charge; the other sixty-three
have neither a connection fee nor a deposit, so the closing side is unknown.
A walkthrough that asserted only what that screen draws today would have
reported it clean — hard-won law 7's *"a check that cannot fail"*, and the
briefing's own warning that `DEF-WRK-4121` shipped a dispatcher that could not
raise a work order on any non-empty list because every test used the empty one.

WHAT IS PLANTED, AND WHY EACH FIGURE IS THE ONE IT IS
-----------------------------------------------------
**The money is the wave I demo script's own** (`10-execution-plan.md`, the
section headed *Wave I — Requests, disputes and a question*), so the
walkthrough asserts the plan's specification rather than arithmetic this file
invented:

    standing charge      $18.50 a month   (water 8.00 + sewer 6.50 + trash 4.00)
    connection fee      $185.00           already seeded, not touched
    deposit             $150.00           already seeded, not touched
    ─────────────────────────────────────────────────────────────────────────
    stop 1 Nov → 1 Apr   5 × 18.50 = $92.50  against $335.00 → STOPPING cheaper
    stop 1 Nov → 1 Jun'28 19 × 18.50 = $351.50 against $335.00 → CLOSING cheaper
    stop 1 Nov → 1 Nov'27 12 × 18.50 = $222.00 — does NOT cross (DEF-CWP-3608)

⚠ **THE STANDING CHARGE IS PLANTED BY REMOVING A DUPLICATE, NOT BY INVENTING
ONE — AND THE REMOVAL IS THE PRODUCT'S OWN PRESCRIBED REMEDY.** Pine Hill's
portal quote plan states a base charge in TWO places for all three services:
the charge code says one figure and `plan_services.base_charge` says `8.000000`.
`BR-RAT-088` (PO 2026-08-20, *"the CHARGE CODE owns the base amount; a plan
displays it, never defines it"*) makes that a migration artefact, and
`billing.gather._base_charge_for` refuses the whole figure rather than picking
one — correctly, because picking is how `DEF-154` made every bill charge
`$0.00`. Its refusal sentence names the repair in words:

    "Clear the figure on the plan's services (S9) so the charge code is the
     only place it lives; the run continues for every other account."

So that is what this does. **The guard is right and the DATA is wrong**, which
is `DEF-CWP-4199`.

⚠ **WHAT THIS FIXTURE DELIBERATELY DOES NOT DO: it does not repair the demo
seed.** The disagreement is a defect of `seed_portal_demo` and it is filed as
one. Repairing it here would hide it from the next lane and leave the shipped
fixture producing a portal nobody can quote a price on.

THE REQUEST, AND EVERY STEP OF ITS HISTORY
-------------------------------------------
One move-out request raised through the portal's OWN door
(`service_request_service.create_from_portal` — a row this file wrote itself
would prove nothing about the door the product uses), then walked forward by a
clerk through the same service the staff app calls:

    submitted            create_from_portal, channel forced to customer_portal
    → under_review       transition(actor, "pick_up")
    → more_info          transition(actor, "request_info", reason=…)
    + an INTERNAL note   "route to Tuesday crew, low priority"   ← must NOT show
    + a CUSTOMER note    "We need proof of address and your landlord's consent."
    + two required documents, neither verified                   ← "two documents"

⚠ **THE INTERNAL NOTE IS THE POINT OF THE WHOLE SCREEN** (`BR-CWP-078`,
`US-CWP-063` TC-2). A fixture without it makes `CWP-051`'s central assertion
vacuous: *"the routing note is absent"* passes trivially over a request that
never had one.

⚠ **THE LINK BETWEEN A LOGIN AND ITS REQUESTS IS A TELEPHONE NUMBER**
(`OQ-CWP-1680`). A portal service request carries no account by rule
(`BR-CWP-026`), so `customers_seam.my_requests` matches on tenant + channel +
a phone one of this login's accounts holds. The applicant phone planted below
and the account's primary contact phone are therefore THE SAME STRING on
purpose; change one and `CWP-046` silently lists nothing.

IDEMPOTENT
----------
Every row it writes is named — the `i-requests@example.test` credential, bills
prefixed `BL-I-`, and requests found by their planted `what_they_said` — and a
replay reuses or rebuilds them. It touches nothing a person created.

RUN IT
------
    10-scripts/proof-db.sh clone cwpi --export       # then export what it prints
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    python3 06-backend/manage.py seed_portal_demo
    python3 10-scripts/render-checks/cr068-i-fixture.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "06-backend",
)
sys.path.insert(0, BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from core.tenancy import tenant_context  # noqa: E402

# ── the login ───────────────────────────────────────────────────────────────
EMAIL = "i-requests@example.test"
PASSWORD = "Elm-Street-1408"
ELM_ST = "1408 Elm St"
UNIT_LABEL = "A"

#: ⚠ **THE SAME STRING IN TWO PLACES ON PURPOSE.** See the block above: this is
#: the only join between a login and the requests it raised.
PHONE = "(512) 555-0134"
APPLICANT = "Maria Alvarez"

# ── the demo script's own money ─────────────────────────────────────────────
#: water + sewer + trash, summing to the demo script's $18.50 a month.
BASE_CHARGES = {"water": Decimal("8.00"), "sewer": Decimal("6.50"), "trash": Decimal("4.00")}
STANDING_MONTHLY = Decimal("18.50")

#: The queried bill and one that is NOT queried — the demo script's step 7
#: turns on the second one still ageing while the first is held.
QUERIED_BILL = "BL-I-2608-0141"
QUERIED_TOTAL = Decimal("142.18")
OTHER_BILL = "BL-I-2609-0152"
OTHER_TOTAL = Decimal("88.40")

# ── the request, and every step of its history ──────────────────────────────
WHAT_THEY_SAID = "Moving out on 17 September."
ROUTING_NOTE = "route to Tuesday crew, low priority"
CUSTOMER_NOTE = "We need proof of address and your landlord's consent."
INFO_REASON = "Proof of address and landlord's consent needed."
DOCUMENTS = (
    ("Proof of address", "A tenancy agreement or a deed"),
    ("Landlord's consent", "You are not the owner"),
)


def _tenant():
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Tenant.objects.get(subdomain="pine-hill")


def _actor(tenant):
    """Pine Hill's provisioned owner, as a real user id.

    `transition` and `add_note` are role-guarded — a clerk moving a request is
    a decision a named person made and the audit row has to say who. Reusing
    the seeder's own owner keeps every write attributable to the user that
    planted the tenant rather than to an invented id.
    """
    from apps.portal import sample_data

    return sample_data._owner_actor(tenant.id, sample_data.PINE_HILL["signup"]["owner"]["email"])


def _account(tenant):
    """The account at `1408 Elm St · A`, found through the PREMISES.

    ⚠ **NEVER BY ACCOUNT NUMBER** (`DEF-CWP-4174`): `AC-2026-00052` comes off a
    counter and moves whenever the estate ahead of it changes size, so every
    document that hard-codes one cannot enrol anybody on a fresh database.
    """
    from apps.customers import models as customers_models
    from apps.metering import models as metering_models

    unit = (
        metering_models.Unit.objects.filter(
            tenant_id=tenant.id, premises__address_line=ELM_ST, label=UNIT_LABEL
        )
        .select_related("premises")
        .first()
    )
    if unit is None:
        raise SystemExit(
            f"no {ELM_ST} · {UNIT_LABEL} on pine-hill — `manage.py seed_portal_demo` did not run"
        )
    account = customers_models.Account.objects.filter(
        tenant_id=tenant.id, unit_id=unit.id
    ).first()
    if account is None:
        raise SystemExit(f"nobody holds an account at {ELM_ST} · {UNIT_LABEL}")
    return account


def plant_the_standing_charge(tenant, account) -> Decimal | None:
    """Make the plan quotable, by REMOVING the duplicate the product refuses on.

    Returns the monthly standing charge the product now resolves, or `None`
    when it still cannot say — which is a finding rather than an exception, so
    the caller prints it and the walkthrough records a known gap.
    """
    from apps.portal.seams import rating_seam
    from apps.rating import models as rating_models

    plan_id = rating_seam.current_plan_id(tenant.id, account.unit_id)

    # 1 · the CHARGE CODE owns the base (BR-RAT-088), so the figures go there.
    for code, amount in BASE_CHARGES.items():
        rows = rating_models.Charge.objects.filter(
            tenant_id=tenant.id, is_base=True, deleted_at__isnull=True, service__code=code
        )
        for row in rows:
            row.amount = amount
            row.save(update_fields=["amount"])

    # 2 · and the PLAN must stop stating one, or the two disagree and the whole
    #     figure is refused — the repair `_base_charge_for`'s own sentence asks
    #     for. Only this plan's rows; another plan is another lane's fixture.
    cleared = []
    for row in rating_models.PlanService.objects.filter(
        tenant_id=tenant.id, rate_plan_id=plan_id
    ).select_related("service"):
        if row.base_charge is not None:
            cleared.append(f"{row.service.code}={row.base_charge}")
            row.base_charge = None
            row.save(update_fields=["base_charge"])

    from apps.portal.seams import customers_seam

    codes = [r["code"] for r in customers_seam.services_held(tenant.id, account.pk)]
    account_type = getattr(account, "account_type", None)
    answer = rating_seam.standing_charge_monthly(
        tenant.id,
        rate_plan_id=plan_id,
        service_codes=codes,
        customer_class=getattr(account_type, "code", None),
        on=date.today(),
    )
    print(f"  plan base charges cleared : {', '.join(cleared) or '(none were set)'}")
    print(f"  standing charge resolves  : {answer['amount']} ({answer['unavailable'] or 'ok'})")
    return answer["amount"]


def plant_the_phone(tenant, account) -> str:
    """The account's primary contact carries `PHONE`, because that string is the
    only join between this login and the requests below."""
    from apps.customers import models as customers_models

    contact = customers_models.Contact.objects.filter(
        tenant_id=tenant.id, account_id=account.id, deleted_at__isnull=True, is_primary=True
    ).first()
    if contact is None:
        contact = customers_models.Contact.objects.create(
            tenant=tenant, account=account, name=APPLICANT, phone=PHONE, is_primary=True
        )
        print(f"  primary contact created   : {PHONE}")
    elif contact.phone != PHONE:
        contact.phone = PHONE
        contact.save(update_fields=["phone"])
        print(f"  primary contact phone set : {PHONE}")
    else:
        print(f"  primary contact phone     : {PHONE} (already)")
    return PHONE


def plant_the_bills(tenant, account) -> list[str]:
    """Two ISSUED bills — one to query and one that is not queried."""
    from apps.billing import models as billing_models

    wanted = (
        (QUERIED_BILL, QUERIED_TOTAL, date(2026, 8, 31), date(2026, 9, 18)),
        (OTHER_BILL, OTHER_TOTAL, date(2026, 9, 30), date(2026, 10, 18)),
    )
    made = []
    for number, total, issued_on, due_on in wanted:
        existing = billing_models.Invoice.objects.filter(
            tenant_id=tenant.id, invoice_no=number
        ).first()
        if existing is not None:
            made.append(number)
            continue
        billing_models.Invoice.objects.create(
            tenant=tenant,
            account=account,
            invoice_no=number,
            status=billing_models.INVOICE_ISSUED,
            service_date=issued_on,
            period_start=issued_on.replace(day=1),
            period_end=issued_on,
            due_date=due_on,
            subtotal=total,
            tax_total=Decimal("0"),
            total=total,
            issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
        )
        made.append(number)
    print(f"  bills on the account      : {', '.join(made)}")
    return made


def plant_the_request(tenant, actor):
    """One move-out request, raised through the portal's own door and then
    walked forward by a clerk exactly as the staff app would walk it."""
    from apps.customers import models as customers_models
    from apps.customers import service_request_service as writes

    existing = customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant.id,
        channel="customer_portal",
        applicant_phone=PHONE,
        what_they_said=WHAT_THEY_SAID,
    ).first()
    if existing is not None:
        print(f"  request                   : {existing.request_no} (already, left alone)")
        return existing

    request = writes.create_from_portal(
        {
            "applicant_kind": "person",
            "applicant_name": APPLICANT,
            "applicant_phone": PHONE,
            "address_as_given": f"{ELM_ST} · {UNIT_LABEL}",
            "what_they_said": WHAT_THEY_SAID,
            "requested_start": date(2026, 9, 17).isoformat(),
        }
    )
    writes.transition(actor, request.id, "pick_up")
    writes.transition(actor, request.id, "request_info", reason=INFO_REASON)
    # ⚠ THE ONE THE CUSTOMER MUST NEVER SEE (BR-CWP-078, US-CWP-063 TC-2).
    writes.add_note(actor, request.id, note=ROUTING_NOTE)
    # ⚠ …and the one they must (the flag BR-CWP-078's second clause names).
    writes.note_from_portal(request.id, note=CUSTOMER_NOTE, customer_visible=True)

    for name, why in DOCUMENTS:
        customers_models.ServiceRequestDocument.objects.create(
            tenant=tenant,
            request_id=request.id,
            doc_type=name,
            required_flag=True,
        )
    fresh = writes.request_row(request.id)
    print(f"  request                   : {fresh.request_no} state={fresh.state}")
    print(f"     internal note          : {ROUTING_NOTE!r} (must be ABSENT from CWP-051)")
    print(f"     customer note          : {CUSTOMER_NOTE!r}")
    print(f"     documents wanted       : {len(DOCUMENTS)}")
    return fresh


def clear_previous_queries(tenant) -> int:
    """Delete the QUERIES this walkthrough itself raised on earlier runs.

    ⚠ **BECAUSE A SECOND QUERY ON ONE BILL IS CORRECTLY REFUSED**
    (`US-CWP-065` TC-9): `open_query_on_bill` matches on
    `customers_seam.DISPUTE_MARKER` and answers *"you have already queried this
    bill"* with a 409. That is the product working. It also means a replay of
    the walkthrough would meet the refusal at step 7 and never exercise the
    happy path — so the run would prove the refusal twice and the write never.
    **Clearing here is what lets the walkthrough prove BOTH in one run**: the
    first query is accepted, and a second on the same bill is refused by name.

    Only rows this fixture's own login raised, matched on the marker AND the
    planted phone. It never touches a request a person created.
    """
    from apps.customers import models as customers_models
    from apps.portal.seams import customers_seam

    doomed = customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant.id,
        channel="customer_portal",
        applicant_phone=PHONE,
        what_they_said__startswith=customers_seam.DISPUTE_MARKER,
    )
    ids = [str(row.pk) for row in doomed]
    if ids:
        customers_models.ServiceRequestEvent.objects.filter(
            tenant_id=tenant.id, request_id__in=ids
        ).delete()
        customers_models.ServiceRequestDocument.objects.filter(
            tenant_id=tenant.id, request_id__in=ids
        ).delete()
        doomed.delete()
    print(f"  earlier portal queries    : {len(ids)} cleared, so step 7 starts un-queried")
    return len(ids)


def enrol(tenant, account) -> None:
    from apps.portal import credentials, models as portal_models

    existing = credentials.credential_by_email(tenant.id, EMAIL)
    if existing is not None:
        print(f"  {EMAIL} already enrolled — left alone")
        return
    credentials.create_credential(
        tenant.id,
        account=account,
        email=EMAIL,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    print(f"  {EMAIL} enrolled on {account.account_no}")


def main() -> None:
    tenant = _tenant()
    actor = _actor(tenant)
    # ⚠ **EVERY FILTER NAMES `tenant_id` AND HAS TO** (hard rule 1). This runs
    # as `smartbillhub`, which is `rolsuper=t`, so `FORCE RLS` is skipped for
    # every query in this process and an unscoped queryset would silently reach
    # another of the three seeded tenants.
    with tenant_context(tenant.id):
        account = _account(tenant)
        print(f"cr068-i fixture · pine-hill · {account.account_no} ({ELM_ST} · {UNIT_LABEL})")
        monthly = plant_the_standing_charge(tenant, account)
        plant_the_phone(tenant, account)
        plant_the_bills(tenant, account)
        request = plant_the_request(tenant, actor)
        clear_previous_queries(tenant)
        enrol(tenant, account)

    print()
    if monthly is None:
        print(
            "  ⚠ THE STANDING CHARGE IS STILL UNRESOLVED. CWP-052 will draw its "
            "'we cannot work this out' branch and the walkthrough will record a "
            "known gap rather than assert a verdict. That is DEF-CWP-4199."
        )
    elif monthly != STANDING_MONTHLY:
        print(
            f"  ⚠ THE STANDING CHARGE IS {monthly}, NOT THE DEMO SCRIPT'S "
            f"{STANDING_MONTHLY}. The walkthrough asserts the ARITHMETIC and the "
            "VERDICT against whatever the screen prints, so it will still run — "
            "but the demo script's own $92.50 / $351.50 will not appear."
        )
    else:
        print(f"  standing charge is the demo script's ${STANDING_MONTHLY} a month")
    print(f"  sign in as {EMAIL}, password {PASSWORD}")
    print(f"  the request to open is {request.request_no}")
    print(f"  the bill to query is {QUERIED_BILL}")


main()
