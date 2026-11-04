# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS), the sample half.
# Rules:    BR-RAT-068..BR-RAT-079 · BR-TEN-056 (the sample set) · BR-TEN-057
#           (`is_sample` on the OWNING row, written by this module's own
#           service) · BR-TEN-063 (idempotent, audited) · BR-TEN-012 (a
#           fixture never overwrites a tenant's own configuration)
# Tests:    06-backend/tests/test_cr013_discounts.py
# Impacts:  apps/rating/sample_data.seed_sample_records (the caller) ·
#           the DIS-01 landing, once it exists, renders exactly these five
# ───────────────────────────────────────────────────────
"""r10's five discounts, seeded — SENIOR · CAP · PAPERLESS · AUTOPAY · MILITARY.

WHY THE SEED IS PART OF THE STORY AND NOT A NICETY. The PO's standing position,
verbatim: *"once sample and defaults are available we can make changes later;
but without default sample functionalities ill not work"*. A schema with no rows
is a screen with an empty state, and an empty state is indistinguishable from a
feature that does not work.

EVERY FIGURE HERE IS r10's, READ OUT OF THE DRAWING
----------------------------------------------------
`05-prototype/r10-2026-08-16/SMARTBillHub.dc.html:814-818`, the DIS-01 table,
columns `Code · Discount · Type · Value · Eligibility · Verification · Plans ·
Enrolled · Status`:

    SENIOR     Senior discount        % of subtotal  −15%        Age 65+
                                                                 Annual recert   Active
    CAP        CAP / low-income       Fixed credit   −$25.00/mo  Program enrolment
                                                                 Agency file · monthly  Active
    PAPERLESS  Paperless billing      Fixed          −$1.00/mo   E-bill on
                                                                 Automatic       Active
    AUTOPAY    Autopay discount       % of subtotal  −0.5%       Autopay enrolled
                                                                 Automatic       Active
    MILITARY   Veteran discount       % of subtotal  −10%        Veteran ID
                                                                 One-time proof  **Draft**

**MILITARY seeds as a DRAFT** because that is what r10 draws — a `pill warn`,
`— plans`, `— enrolled`. It is also the only one of the five that exercises the
draft path on a screen, which is worth having in a fixture.

⚠ THREE FIGURES ARE NOT r10's, AND EACH IS MARKED WHERE IT IS SET
------------------------------------------------------------------
r10 draws no precedence, no budget and no floor, and the object requires the
first of those to be deterministic. So:

* **`stacking_precedence`** is seeded 10/20/30/40/50 in the order r10 LISTS the
  five. It is a FIXTURE, not a rule — part 3 makes precedence data the utility
  sets, and the seed states an order because an order must exist for a run to
  be repeatable. No signed document names one.
* **`budget_cap`** is seeded only where the design's §A8 states a figure the PO
  was shown — SENIOR ≈$12,312/yr and CAP ≈$11,400/yr, PAPERLESS ≈$7,332 and
  AUTOPAY ≈$2,383 — because those four numbers are what the second-approval
  ruling was made against, and a fixture that contradicts them would make the
  ruling untestable. MILITARY has none, which is the case the PO's ruling calls
  out: **no budget cap always requires the second approval**.
* **`bill_floor_amount`** is 0 on all five — the model default, meaning a
  discount may take a bill to zero but never below it. No programme in r10
  states a floor.

⚠ AND ONE RELATIONSHIP IS r10's, DRAWN IN THE SENIOR DETAIL: *"Stacking · Not
with CAP credit · One assistance program per account — the larger applies."*
SENIOR and CAP are seeded into the exclusivity group `assistance`, which is
what makes that sentence a behaviour rather than a caption.

WHAT THIS SEED DELIBERATELY DOES NOT DO
-----------------------------------------
* **It enrols nobody.** r10 shows 72 · 38 · 611 · 418 enrolled accounts, and
  those are a screenshot's numbers, not a fixture's: enrolling accounts in a
  subsidy is a money act on real customer rows, and a sample loader that
  quietly discounted 611 accounts would be the exact *available-vs-granted*
  failure BR-RAT-069 exists to prevent. The tables and services are here; a
  demo enrolment is a deliberate act, and a fixture lane that wants one calls
  `discount_services.enrol_account` on a NAMED account.
* **It attaches nothing to a plan** unless the sample plans exist, and then
  only PAPERLESS and AUTOPAY, which r10 shows on the Residential Standard plan
  (`SMARTBillHub.dc.html:1092-1093`). SENIOR belongs to the Senior/Low-income
  plan, which **is not seeded** — that is OQ-240, still open, and this fixture
  does not close it by inventing the plan.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from apps.rating import discount_lists, discount_services
from apps.rating import discounts as discount_models
from apps.rating import seams
from core import sample_fixture as core_fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.rating")

#: r10's effective date, drawn on every Plans & Rates tab: *"effective Aug 1,
#: 2026"*. Used for all five so the fixture's own dates agree with the drawing.
SAMPLE_EFFECTIVE_FROM = date(2026, 8, 1)

#: **THE MUNICIPAL DISCOUNT'S OWN DATE, AND IT IS NOT r10's — `CR-062` addendum
#: J2 (`DEF-3285`).**
#:
#: ⚠ **THE DATE IS WHAT MAKES THE DISCOUNT VISIBLE OR INVISIBLE, AND IT WAS
#: MEASURED.** `discount_services.discount_rules_for_account` resolves the
#: version in force AT THE BILL'S SERVICE DATE (`BR-RAT-007`'s pivot) and
#: requires `enrolled_on <= that date`. This fixture bills **June and July
#: 2026**, so a discount effective 1 August is in force on no bill the demo
#: issues: the enrolment shows on screen, the programme shows on the plan, and
#: every document is full price. Measured on PostgreSQL 16 — the municipal
#: building's June bill carried **no discount line at all** under r10's date.
#:
#: **So it takes `PLAN_EFFECTIVE_FROM`'s date — the seeded plans' own — because
#: a demonstration that cannot be seen demonstrates nothing.** The five r10
#: discounts keep `SAMPLE_EFFECTIVE_FROM` above: their date is drawn in r10 and
#: none of them is enrolled, so it costs nothing and moves no figure.
MUNICIPAL_EFFECTIVE_FROM = core_fixture.PERIODS[0]["start"]

#: The five, in r10's own row order. `precedence` is a fixture choice (see the
#: module docstring); every other figure is r10's or design §A8's.
SAMPLE_DISCOUNTS: tuple[dict[str, Any], ...] = (
    {
        "code": "SENIOR",
        "name": "Senior discount",
        "programme_owner": "Customer service",
        "funding_source": "Rate-payer funded",  # r10 SENIOR detail, verbatim
        "report_in_assistance_filing": True,  # r10: "Reported in the annual filing"
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": Decimal("15"),
        "applies_to": discount_models.SCOPE_WHOLE_BILL,  # r10: "Subtotal · before taxes"
        "eligibility_summary": "Age 65+",
        "enrolment_mode": discount_models.ENROLMENT_APPLY_AND_APPROVE,
        "verification_method": discount_models.VERIFY_ANNUAL_RECERT,
        "proof_required": True,
        "accepted_proof_kinds": ["government_id", "birth_certificate"],
        "recertification_months": 12,
        "recertification_notice_days": 60,  # r10: "customer notified 60 days ahead"
        "lapse_behaviour": discount_models.LAPSE_NOTIFY_THEN_DROP,
        "exclusivity_group": "assistance",  # r10: "Not with CAP credit"
        "stacking_precedence": 10,
        "budget_cap": Decimal("12312"),  # design §A8's own figure for SENIOR
        "budget_period": discount_models.BUDGET_PERIOD_ANNUAL,
        "activate": True,
    },
    {
        "code": "CAP",
        "name": "CAP / low-income credit",
        "programme_owner": "City assistance programme",
        "funding_source": "City programme",
        "report_in_assistance_filing": True,
        "discount_type": discount_models.DISCOUNT_FIXED_AMOUNT,
        "value": Decimal("25"),
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
        "eligibility_summary": "Program enrolment",
        "enrolment_mode": discount_models.ENROLMENT_APPLY_AND_APPROVE,
        "verification_method": discount_models.VERIFY_AGENCY_FILE_MONTHLY,
        "proof_required": True,
        "accepted_proof_kinds": ["programme_award_letter", "agency_file"],
        "recertification_months": 1,  # "Agency file · monthly"
        "lapse_behaviour": discount_models.LAPSE_NOTIFY_THEN_DROP,
        "exclusivity_group": "assistance",
        "stacking_precedence": 20,
        "budget_cap": Decimal("11400"),  # design §A8's own figure for CAP
        "budget_period": discount_models.BUDGET_PERIOD_ANNUAL,
        "activate": True,
    },
    {
        "code": "PAPERLESS",
        "name": "Paperless billing",
        "programme_owner": "Billing",
        "funding_source": "Rate-payer funded",
        "discount_type": discount_models.DISCOUNT_FIXED_AMOUNT,
        "value": Decimal("1"),
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
        "eligibility_summary": "E-bill on",
        # ⚠ AUTOMATIC AND THEREFORE NO PROOF. The pair is a NAMED VALIDATION
        # GATE — part 3 calls automatic-enrolment-with-mandatory-proof
        # "contradictory" and `_validate_version` refuses it — so this fixture
        # is also the positive case that proves the gate is not simply always on.
        "enrolment_mode": discount_models.ENROLMENT_AUTOMATIC,
        "verification_method": discount_models.VERIFY_AUTOMATIC,
        "proof_required": False,
        "proof_before_first_reduction": False,
        "lapse_behaviour": discount_models.LAPSE_NEVER_EXPIRES,
        "stacking_precedence": 30,
        "budget_cap": Decimal("7332"),  # design §A8
        "budget_period": discount_models.BUDGET_PERIOD_ANNUAL,
        "activate": True,
    },
    {
        "code": "AUTOPAY",
        "name": "Autopay discount",
        "programme_owner": "Billing",
        "funding_source": "Rate-payer funded",
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": Decimal("0.5"),  # ⚠ NOT a whole number — this is why 6dp
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
        "eligibility_summary": "Autopay enrolled",
        "enrolment_mode": discount_models.ENROLMENT_AUTOMATIC,
        "verification_method": discount_models.VERIFY_AUTOMATIC,
        "proof_required": False,
        "proof_before_first_reduction": False,
        "lapse_behaviour": discount_models.LAPSE_NEVER_EXPIRES,
        "stacking_precedence": 40,
        "budget_cap": Decimal("2383"),  # design §A8
        "budget_period": discount_models.BUDGET_PERIOD_ANNUAL,
        "activate": True,
    },
    {
        "code": "MILITARY",
        "name": "Veteran discount",
        "programme_owner": "Customer service",
        "funding_source": "Rate-payer funded",
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": Decimal("10"),
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
        "eligibility_summary": "Veteran ID",
        "enrolment_mode": discount_models.ENROLMENT_APPLY_AND_APPROVE,
        "verification_method": discount_models.VERIFY_ONE_TIME_PROOF,
        "proof_required": True,
        "accepted_proof_kinds": ["veteran_id"],
        "recertification_months": None,  # one-time proof: nothing to recertify
        "lapse_behaviour": discount_models.LAPSE_NEVER_EXPIRES,
        "stacking_precedence": 50,
        # ⚠ NO BUDGET CAP, and that is the case PO ruling 5 of 2026-08-19 calls
        # out by hand: a discount with no budget always requires the second
        # approval, because unbounded is the largest commitment there is.
        "budget_cap": None,
        # r10 draws MILITARY as `pill warn` / Draft, with `—` plans and `—`
        # enrolled. Seeded that way rather than activated.
        "activate": False,
    },
    # ── CR-062 ADDENDUM J2 · THE SIXTH DISCOUNT (PO 2026-09-02) ─────────────
    # **PO verbatim, both halves of it in one line:** *"What is the government
    # discount called? Municipal account - yes; What rate? 20% off the bill
    # before taxes - yes"*.
    #
    # **NOT r10's.** The five above are read out of the DIS-01 table; this one
    # is a ruling made today, and it is marked as such so a later reader does
    # not go looking for it in the drawing.
    #
    # ⚠ **`SCOPE_WHOLE_BILL` IS *"20% off the bill BEFORE TAXES"* SAID IN THE
    # MODEL'S OWN WORDS**, and it is the same value SENIOR carries for r10's
    # *"Subtotal · before taxes"*. `BR-RAT-071` takes the reduction before tax
    # is computed, so the PO's sentence is delivered by the engine rather than
    # by a note here.
    #
    # ⚠ **AUTOMATIC, AND THAT IS AN ARGUMENT RATHER THAN A CONVENIENCE.** The
    # eligibility is the ACCOUNT TYPE — a fact the utility already records on
    # the account and can see — so there is nothing for a customer to prove and
    # no document to expire. `proof_required` with `ENROLMENT_AUTOMATIC` is a
    # combination `_validate_version` refuses outright as contradictory, and
    # asking a public works department for a government ID to prove it is a
    # government would be that contradiction wearing a policy's clothes.
    #
    # ⚠ **NO BUDGET CAP, AND THE CONSEQUENCE IS DELIBERATE.** Design §A8 states
    # four programme costs and none of them is this one, and inventing a fifth
    # would be inventing a figure (spec rule 7). `BR-RAT-077` then says an
    # uncapped discount ALWAYS requires the second approval — which is the
    # honest position for a subsidy nobody has budgeted, and it is warn-and-
    # allow at activation (PO 2026-08-21, *"We will show message and not refuse
    # it"*), so the seed still lands.
    #
    # **Worked, and asserted in `tests/test_cr062_j_addendum.py`:** the seeded
    # government building's water + sewer + trash subtotal is **$157.50**; 20%
    # of it is **$31.50**, and the account pays **$126.00** before taxes.
    # ⚠ $129.70 / $25.94 / $103.76 until `CR-081` (2026-09-08) moved the sewer
    # line from $26.20 to $54.00. The discount and its 20% did not move.
    {
        "code": "MUNICIPAL",
        "name": "Municipal account",
        "programme_owner": "Customer service",
        "funding_source": "Rate-payer funded",
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": Decimal("20"),
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
        "eligibility_summary": "Government account",
        "enrolment_mode": discount_models.ENROLMENT_AUTOMATIC,
        "verification_method": discount_models.VERIFY_AUTOMATIC,
        "proof_required": False,
        "proof_before_first_reduction": False,
        "lapse_behaviour": discount_models.LAPSE_NEVER_EXPIRES,
        "stacking_precedence": 60,
        "budget_cap": None,
        "activate": True,
    },
)

#: The two r10 shows attached to Residential Standard
#: (`SMARTBillHub.dc.html:1092-1093`). SENIOR is NOT here: r10 attaches it to
#: Senior / Low-income, a plan this repo does not seed (OQ-240, open).
#:
#: ⚠ **`MUNICIPAL` JOINED ON 2026-09-02 (`CR-062` addendum J2) AND IT IS NOT
#: DECORATION — WITHOUT IT THE ENROLMENT BELOW REACHES NO BILL.** `BR-RAT-110`
#: is *"both gates, not one replacing the other"*: the plan's binding says which
#: discounts it OFFERS and the enrolment GRANTS, and
#: `selectors.billable_discount_rules` drops an enrolment the plan does not bind
#: — *"enrolled but not offered by THIS plan — dropped, not guessed"*. So a
#: municipal account enrolled in a discount no plan carries would show an
#: enrolment on screen and a full-price bill, which is a worse demo than no
#: enrolment at all.
SAMPLE_PLAN_ATTACHMENTS = ("PAPERLESS", "AUTOPAY", "MUNICIPAL")


def seed_sample_discounts(actor: Any) -> int:
    """The five, written through this module's OWN audited services.

    Idempotent by natural key (BR-TEN-063): each code is looked up first, so a
    second load writes nothing and returns 0. Nothing is overwritten — a tenant
    who has edited SENIOR keeps their edit (BR-TEN-012), because the check is
    *does this code exist*, never *does it match the fixture*.

    Returns the number of discounts created.
    """
    tenant_id = core_tenancy.current_tenant_id()
    existing = set(
        discount_models.Discount.objects.filter(tenant_id=tenant_id).values_list("code", flat=True)
    )
    created = 0
    for entry in SAMPLE_DISCOUNTS:
        if entry["code"] in existing:
            continue
        payload = {key: value for key, value in entry.items() if key != "activate"}
        # `CR-166-BRC10` — the three dropdowns store CODES of this utility's own
        # list values. The fixture's words are mapped exactly as `rating/0060`
        # maps an existing utility's (`discount_lists.map_or_add`), so a fresh
        # sample tenant and a migrated one carry the same values — including the
        # PO ruling 2026-10-03 (*"A Keep them excluding each other, so the
        # customer gets one of the two"*): `assistance` becomes the utility's own
        # shared group *Assistance programs*, never a drawn one.
        payload["program_owner"] = discount_lists.map_or_add(
            discount_models.LIST_PROGRAM_OWNER, payload.pop("programme_owner", None)
        )
        if payload.get("exclusivity_group"):
            payload["exclusivity_group"] = discount_lists.map_or_add(
                discount_models.LIST_EXCLUSIVITY_GROUP, payload["exclusivity_group"]
            )
        payload["eligibility"] = discount_lists.map_or_add(
            discount_models.LIST_ELIGIBILITY, payload.get("eligibility_summary")
        )
        # CR-062 addendum J2 / DEF-3285 — MUNICIPAL is the one seeded discount
        # that is ENROLLED, so it is the one whose date has to cover a billed
        # period. See `MUNICIPAL_EFFECTIVE_FROM`.
        payload["effective_from"] = (
            MUNICIPAL_EFFECTIVE_FROM if entry["code"] == "MUNICIPAL" else SAMPLE_EFFECTIVE_FROM
        )
        row = discount_services.create_discount(actor, payload)
        created += 1
        version = (
            discount_models.DiscountVersion.objects.filter(
                tenant_id=tenant_id, discount_id=row["id"]
            )
            .order_by("-version_no")
            .first()
        )
        if entry["activate"]:
            # Through the real submit → approve → activate path, not by setting
            # a status: spec rule 4, *"a fixture built by direct insert proves
            # the tables exist and proves nothing about the product."* This also
            # exercises the second-approval computation on every seeded row.
            discount_services.submit_discount_version(actor, version.id)
            # PO ruling 2026-10-03 (1): approval is the LAST act — the version
            # is live from its start date; there is no Activate any more.
            discount_services.approve_discount_version(actor, version.id)
        # BR-TEN-057: the sample tag is stamped by this module's own function on
        # the sample path and by nothing else.
        discount_models.Discount.objects.filter(tenant_id=tenant_id, pk=row["id"]).update(
            is_sample=True
        )
        discount_models.DiscountVersion.objects.filter(
            tenant_id=tenant_id, discount_id=row["id"]
        ).update(is_sample=True)

    _attach_sample_plan_discounts(actor)
    return created


def _attach_sample_plan_discounts(actor: Any) -> None:
    """Make PAPERLESS and AUTOPAY AVAILABLE on the seeded residential plan.

    ⚠ **AVAILABLE, NOT GRANTED** (BR-RAT-069). This attaches nothing to any
    account and discounts nobody's bill; it is what r10 draws on PLN-02's
    Discounts tab, and the accounts column there is filled by ENROLMENTS,
    which this fixture does not create.
    """
    from apps.rating import sample_data

    plan_id = sample_data.residential_plan_id()
    if not plan_id:
        return
    tenant_id = core_tenancy.current_tenant_id()
    for code in SAMPLE_PLAN_ATTACHMENTS:
        discount = discount_models.Discount.objects.filter(tenant_id=tenant_id, code=code).first()
        if discount is None:
            continue
        discount_services.attach_discount_to_plan(actor, plan_id, discount.id)
        discount_models.PlanDiscountRule.objects.filter(
            tenant_id=tenant_id, rate_plan_id=plan_id, discount=discount
        ).update(is_sample=True)


#: The ONE account this fixture enrols, by unit number — `CR-062` addendum J2.
#:
#: ⚠ **THE REASON THE FIXTURE ENROLLED NOBODY IS GOOD AND IS NOT WITHDRAWN; IT
#: IS NARROWED TO THIS ONE SEAT.** The module docstring's *"enrolling accounts
#: in a subsidy is a money act on real customer rows"* still holds for every
#: other account, and `r10`'s 72 / 38 / 611 / 418 are still a screenshot's
#: numbers rather than a fixture's. What changed is a ruling: the Product Owner
#: named a Municipal discount for government accounts on 2026-09-02, and a
#: discount nobody is enrolled in cannot be shown to reduce a bill — the whole
#: point of `BR-RAT-069`'s available-versus-granted distinction is that only the
#: second one is visible on a document.
#:
#: **The seat is a DEMONSTRATION and is obviously one**: a fictional township on
#: this fixture's own invented streets, carrying the `municipal` consumer
#: category. It is never a real party, and `seams.sample_account_id_for_unit`
#: filters on `is_sample` so this seeder cannot reach one even by accident.
SAMPLE_ENROLMENTS: tuple[tuple[str, int], ...] = (
    ("MUNICIPAL", core_fixture.CASE_GOVERNMENT_ACCOUNT),
)


def seed_sample_enrolments(actor: Any) -> int:
    """The Municipal discount, granted to the one seeded government building.

    **THE FIRST SEEDED ENROLMENT THIS FIXTURE HAS EVER CARRIED** (`CR-062`
    addendum J2). PO ruling 2026-09-02, verbatim: *"What is the government
    discount called? Municipal account - yes; What rate? 20% off the bill before
    taxes - yes"*.

    **Worked, and asserted in `tests/test_cr062_j_addendum.py`:** the building's
    water + sewer + trash subtotal is **`$129.70`**, the reduction is
    **`$25.94`**, and it pays **`$103.76`** before taxes.

    ⚠ **A SEPARATE BLOCK FROM `seed_sample_discounts`, AND THE POSITION IS THE
    WHOLE REASON.** An enrolment needs an ACCOUNT, and rating's own block runs
    before customers' — it must, because a plan has to exist before customers
    can attach an agreement to one. So this runs as its own sample block AFTER
    the Accounts block and BEFORE the first bill run, which is the only window
    in which the reduction can appear on the June document a person opens.

    Idempotent (`BR-TEN-063`): `enrol_account` returns the existing open
    enrolment rather than creating a second one, and a missing account or an
    unseeded discount is a NAMED no-op rather than a failure that would take the
    whole plant down with it (`BR-TEN-060`).

    Returns the number of enrolments created.
    """
    tenant_id = core_tenancy.current_tenant_id()
    by_unit = {row["unit_index"]: row["unit_no"] for row in core_fixture.units_flat()}
    created = 0
    for code, unit_index in SAMPLE_ENROLMENTS:
        discount = discount_models.Discount.objects.filter(
            tenant_id=tenant_id, code=code
        ).first()
        if discount is None:
            logger.info(
                "sample data (CR-062 J2): discount %s is not on file, so the seeded "
                "municipal account is enrolled in nothing and its bill is full price",
                code,
            )
            continue
        unit_no = by_unit.get(unit_index)
        account_id = seams.sample_account_id_for_unit(unit_no) if unit_no else None
        if account_id is None:
            # BR-TEN-060's posture — an unloaded thing is a NAMED line, never a
            # silence. The Accounts block can legitimately come up short (it
            # says so itself), and one missing seat must not fail the plant.
            logger.info(
                "sample data (CR-062 J2): no sample account occupies unit %s, so the "
                "Municipal discount has nothing to be granted to — the discount is "
                "still AVAILABLE on the plan (BR-RAT-069) and nobody's bill moves",
                unit_no,
            )
            continue
        before = discount_models.DiscountEnrolment.objects.filter(
            tenant_id=tenant_id, discount=discount, account_id=account_id
        ).count()
        # ⚠ **THE ENROLMENT DATE IS PART OF THE SAME FACT AS THE DISCOUNT'S
        # (`DEF-3285`).** `discount_rules_for_account` filters
        # `enrolled_on <= service date`, so an enrolment dated "today" — which
        # is mid-August for this fixture's clock — reaches neither of the two
        # billed months and the demo's every document is full price.
        row = discount_services.enrol_account(
            actor, discount.id, account_id, enrolled_on=MUNICIPAL_EFFECTIVE_FROM
        )
        if before == 0:
            created += 1
        # BR-TEN-057: the sample tag is stamped by this module's own function on
        # the sample path and by nothing else.
        discount_models.DiscountEnrolment.objects.filter(
            tenant_id=tenant_id, pk=row["id"]
        ).update(is_sample=True)
    return created


def sample_enrolment_count() -> int:
    """Counted OUT OF THE DATABASE — CR-010's rule, so a stale literal can never
    describe this fixture (the PO's own instruction of 2026-08-19)."""
    return discount_models.DiscountEnrolment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), is_sample=True
    ).count()


def remove_sample_enrolments() -> dict[str, Any]:
    """`BR-TEN-061`/`066` — the enrolments this module seeded, removed.

    A HARD delete keyed on `is_sample`, which `BR-TEN-057` puts on the OWNING
    row: an enrolment a clerk made by hand carries no tag and is never touched.
    """
    removed, _ = discount_models.DiscountEnrolment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), is_sample=True
    ).delete()
    return {"removed": int(removed or 0), "retained": []}


def sample_discount_count() -> int:
    """Counted OUT OF THE DATABASE — CR-010's rule, and the PO's instruction of
    2026-08-19 about the stale catalogue figure: *"we have increase this number
    check out seed data"*."""
    return discount_models.Discount.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), is_sample=True
    ).count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: r10 `SMARTBillHub.dc.html:814-818` (DIS-01 rows), `:1092-1093` (PLN-02 discounts tab), `:10549-10557` (the SENIOR detail read-out) + CR-013 part 3 VERBATIM + 08-cr013-design.md §A8's four programme-cost figures + BR-TEN-012/056/057/063 + the PO's standing sample-data position (*"without default sample functionalities ill not work"*)
# generated: 2026-08-19 by the CR-013 EP-RAT-12 lane (discounts — the seed)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half — DIS-01 renders these once it exists) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ · pytest tests/test_cr013_discounts.py 47 passed✔ (five seed, idempotent second load writes 0, nobody enrolled) · tests/test_cr010_silent_seed_gaps.py + test_us_ten_019_sample_records.py 43 passed✔ — the orchestrator's own path still runs · golden-verify 33 PASS/0 FAIL✔
# exceptions: `stacking_precedence` 10/20/30/40/50 is a FIXTURE choice, not a signed figure — r10 draws no order and part 3 makes precedence data the utility sets · budget caps are design §A8's four figures, seeded so the second-approval ruling is testable; MILITARY has none, deliberately, because that is the PO's named "always requires the second approval" case · NO ACCOUNT IS ENROLLED — r10's 72/38/611/418 are a screenshot's numbers and enrolling real accounts in a subsidy is a money act, so the fixture stops at availability · SENIOR is not attached to any plan because r10 attaches it to Senior / Low-income, which this repo does not seed (OQ-240, open)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
