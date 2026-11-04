# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 of 5 — DISCOUNTS). No US-ID is cited:
#           the CR-013 epics are not authored yet, and citing an ID that does
#           not exist is what G2 refuses. The authority is the CR text itself,
#           quoted verbatim below and in 12-governance/11-change-requests.md.
#           Screens: DIS-01 landing · the discount detail shell · DIS-02 wizard
#           — NONE of which this commit builds (backend-only slice).
# Rules:    BR-RAT-068 (overlay, never a rate) · BR-RAT-069 (available ≠
#           granted) · BR-RAT-070 (a plan may not override a discount's value)
#           · BR-RAT-071 (R6 before R7; discount treatment is per tax) ·
#           BR-RAT-072 (four statuses, one of them set by a BILL RUN) ·
#           BR-RAT-073 (stacking precedence is data) · BR-RAT-074 (the bill
#           floor) · BR-RAT-075 (caps + budget + exhaustion) · BR-RAT-076
#           (verification, proof, recertification, the contradiction gate) ·
#           BR-RAT-077 (second approval — tenant setting, $10,000 default) ·
#           BR-RAT-078 (enrolments survive versioning; deletion refused) ·
#           BR-RAT-079 (income and medical proof are restricted)
# Tests:    06-backend/tests/test_cr013_discounts.py
# Impacts:  apps/rating/discount_pricing.py (R6 math) ·
#           apps/rating/discount_services.py (writes) ·
#           apps/rating/resolution.resolve_discounts (R6 — the integration
#           point, deliberately NOT edited here; see discount_pricing.py) ·
#           apps/billing (a discount line on an issued bill — unbuilt)
# ───────────────────────────────────────────────────────
"""The DISCOUNT object, its versions, its plan availability and its enrolments.

WHAT WAS MISSING, MEASURED THREE WAYS ON 2026-08-19
---------------------------------------------------
`\\dt *discount*` on the live database returned **0 rows**; a grep for a
Discount model across every `models.py` in `apps/` returned **no match**; and
r10 draws **five** discounts on Plans & Rates → Discounts with nothing behind
them. So this is not a seeding gap — the product could not express a discount
at all, and `apps/rating/resolution.resolve_discounts` says so in as many
words, returning `modelled=False` rather than an empty list.

THE FIVE SENTENCES THIS SCHEMA IS SHAPED BY, EACH QUOTED
---------------------------------------------------------
1. **An OVERLAY, never a cloned rate.** r10's own detail copy: *"An overlay,
   not a cloned rate: it references the plan's normal schedules and reduces the
   subtotal by a percentage before taxes. Removing a customer from the program
   restores full price with no rate change."* Hence there is no rate, no tier
   and no schedule anywhere below — only a value and what it applies to.
2. **AVAILABLE, NOT GRANTED** (CR-013 part 3, *Downstream*): *"plan attachment
   makes a discount available, not granted; Accounts holds enrolment"*. Hence
   TWO tables: `plan_discount_rules` (availability) and `discount_enrolments`
   (the grant). Built as one plan-level flag instead, a plan carrying SENIOR
   would discount **every account on it** — 842 wrong bills on the Residential
   Standard plan alone.
3. **A PLAN MAY NOT OVERRIDE A DISCOUNT'S VALUE.** PO ruling 2026-08-19,
   verbatim: *"no plan cannot override prices."* r10 draws a per-plan value
   override (`SMARTBillHub.dc.html:10805`) and the ruling deletes it. So
   `plan_discount_rules` **carries no value column**, and that absence is the
   ruling — see the class docstring.
4. **BEFORE TAXES, BUT THE TAX DECIDES ITS OWN BASE.** The chain puts R6 before
   R7. CR-013 part 4 then says discount treatment is *statutory and per tax* —
   some authorities levy on the pre-discount amount. So this module stores **no
   global "taxes computed on the discounted amount" flag**, even though r10's
   DIS-02 step 2 draws that checkbox: the answer belongs on `taxes`
   (EP-RAT-13's `discount_treatment` column, unbuilt). Storing it here would
   hard-code one answer for every authority in the product.
5. **THE BILL SHOWS BOTH NUMBERS** (part 3): *"the bill shows the full tariff
   amount and the reduction as its own line, so subsidy granted is
   reportable."* A discount is never a smaller number on the tariff line — it
   is its own line, which is why `discount_grants` exists as an append-only
   record of subsidy given rather than as a subtraction nobody can report on.

VERSIONING, AND THE ONE THING THAT DOES **NOT** VERSION
--------------------------------------------------------
`Discount` is the identity (code, name, programme owner, funding source);
`DiscountVersion` is the dated, approvable content (type, value, scope, caps,
floor, precedence, eligibility, verification, budget). That is the same split
`Tariff`/`TariffVersion` already uses, and it is what makes CR-013's promise —
*"any bill stays reproducible from the pricing in force for its service
period"* — expressible: `discount_grants.discount_version_id` stamps the
version that priced each reduction.

**Enrolments point at the DISCOUNT, never at a version.** Part 3's shared
rules: *"enrolments survive versioning"*. An enrolment FK to a version would
end every enrolment the day a value changed — r10's SENIOR went v1 −10% → v2
−15% on Jan 1 2026 and its 72 accounts did not re-enrol.

MONEY, TENANCY, IMMUTABILITY
-----------------------------
Every money column is `NUMERIC(18,6)` with a `CHAR(3)` currency beside it
(hard rule 2); nothing here is a float or an integer of cents. Every table is
tenant-scoped and gets ENABLE + FORCE row-level security in the SAME migration
that creates it (hard rule 1, `db/rls_rating_discounts.sql`). `DiscountGrant`
is **append-only** — a subsidy already applied to an issued bill is never
updated or deleted (hard rule 4); a correction is a new row with the opposite
sign, which is why `amount` is signed rather than a magnitude.
"""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.rating.plan_versioning import (
    AllVersionsManager,
    BindingVersionMixin,
    PlanBindingManager,
)
from core.dbfields import uuid7_pk

# ── value sets (comment-documented, W0 TextField pattern) ───────────────────

#: CR-013 part 3, DIS-01: *"Status (Active/Draft/Retired/Suspended-funding-
#: exhausted)"*. FOUR, and the fourth carries money semantics: a discount that
#: has spent its budget is neither Active nor Retired, and the difference
#: decides whether next month's bill is reduced. Part 3 pairs it with *"Run
#: bills … raises an exception when budget is exhausted mid-run"* — this is
#: **the one status in the product a BILL RUN can set**. ⚖️ The "raises" half
#: is SUPERSEDED (2026-10-04, `BR-RAT-075`): a spent budget gives $0.00 and the
#: bill goes out — PO *"we cannot stop the billing"*.
DISCOUNT_DRAFT = "draft"
DISCOUNT_ACTIVE = "active"
DISCOUNT_RETIRED = "retired"
DISCOUNT_SUSPENDED_FUNDING = "suspended_funding_exhausted"
DISCOUNT_STATUSES = (
    DISCOUNT_DRAFT,
    DISCOUNT_ACTIVE,
    DISCOUNT_RETIRED,
    DISCOUNT_SUSPENDED_FUNDING,
)

#: CR-013 part 3, DIS-01: *"Types: Percentage / Fixed amount / Rate override /
#: Charge waiver / Usage allowance."* All five are storable from this migration
#: — widening an enum later is the avoidable second migration, the same reason
#: `rating 0007` gave for `premises_scope_kind`. Only three can be PRICED
#: today; see `DISCOUNT_TYPES_PRICEABLE`.
DISCOUNT_PERCENTAGE = "percentage"
DISCOUNT_FIXED_AMOUNT = "fixed_amount"
DISCOUNT_RATE_OVERRIDE = "rate_override"
DISCOUNT_CHARGE_WAIVER = "charge_waiver"
DISCOUNT_USAGE_ALLOWANCE = "usage_allowance"
DISCOUNT_TYPES = (
    DISCOUNT_PERCENTAGE,
    DISCOUNT_FIXED_AMOUNT,
    DISCOUNT_RATE_OVERRIDE,
    DISCOUNT_CHARGE_WAIVER,
    DISCOUNT_USAGE_ALLOWANCE,
)
#: The subset an activation may use today, named so the gap is a fact in the
#: code rather than a paragraph in a report (hard-won law 1). A discount that
#: cannot be priced must REFUSE at activation rather than reach a bill run and
#: be silently skipped.
#:
#: ⚠ **THE TWO EXCLUSIONS ARE UNCHANGED AND THEIR REASON CHANGED ON 2026-08-31
#: — `BR-RAT-962`.** This comment used to say both were blocked on `OQ-291` and
#: `OQ-292`. **Both questions are now CLOSED** (PO rulings of that date,
#: `BR-RAT-960` and `BR-RAT-961`) and neither type became priceable, so a reader
#: who checks the questions and finds them answered would conclude this tuple is
#: simply stale. It is not. Hard-won law 1 is *a comment claiming a guarantee is
#: not the guarantee*; this is the same failure aimed at a REASON, which decays
#: exactly as silently.
#:
#: **`usage_allowance` — the reason is the STEP, and it is arithmetic.** This
#: tuple gates `discount_pricing._raw_reduction`, which is **R6: a subtraction of
#: MONEY from a subtotal**. An allowance deducts **UNITS** before R3b's tier
#: walk. Admitting it here would price a `2 kgal` allowance as **`$2.00` off**
#: where the ruled arithmetic makes it **`$14.40`** — `$12.40` on one bill, in
#: the customer's disfavour, on a discount the utility believes it granted. The
#: real remaining blocker is `DEF-438`: the R1–R7 chain has no production caller,
#: so `resolution.allowance_deducted_quantity` is reachable only through the
#: ruled cutover's step 5, gated on its step 4 (`CR-052` task 20).
#:
#: **`rate_override` — the reason is that there is nothing left to price.**
#: `BR-RAT-961` ruled a subsidy is the standard schedule plus a discount line, so
#: the type's one stated use is gone, and `BR-RAT-068` (*an overlay, never a
#: rate*) forbade the shape from 2026-08-19 anyway.
#:
#: **WIDENING THIS TUPLE IS A MONEY CHANGE.** It is not the tidy-up a closed
#: question invites.
DISCOUNT_TYPES_PRICEABLE = (
    DISCOUNT_PERCENTAGE,
    DISCOUNT_FIXED_AMOUNT,
    DISCOUNT_CHARGE_WAIVER,
)

#: DIS-02 step 2: *"scope (whole bill / one service / usage only / base only /
#: named codes)"*. r10's own select offers three of the five (`Subtotal before
#: taxes`, `Base charges only`, `Usage charges only`); the CR text governs and
#: carries all five.
SCOPE_WHOLE_BILL = "whole_bill"
SCOPE_ONE_SERVICE = "one_service"
SCOPE_USAGE_ONLY = "usage_only"
SCOPE_BASE_ONLY = "base_only"
SCOPE_NAMED_CODES = "named_codes"
#: ⚠ **`CR-091-BRC01` — THE SCOPE GAINS A PAIR AND WIDENS NOTHING.** PO ruling
#: 2026-09-10, verbatim: *"Add a new choice. - one or more services from drop
#: down; All services or sepecific services; this is correct"*, answering
#: *"when we create discount - we will ahve to take 1 or more utility
#: services"*.
#:
#: ⚠ **`one_service` IS NOT WIDENED, AND THAT IS THE WHOLE POINT OF ADDING TWO
#: VALUES RATHER THAN CHANGING ONE.** Every discount already saved keeps
#: exactly the meaning it had and no migration reinterprets a stored row. The
#: enum value is literally named for the singular, so widening it would leave a
#: name that lies about its own contents.
#:
#: ⚠ **`all_services` IS NOT A DUPLICATE OF `whole_bill`, AND THE DIFFERENCE IS
#: ARITHMETIC THAT ALREADY EXISTED.** `whole_bill` is the ONE scope that runs
#: against the REDUCING subtotal — `price_discounts` says so at both call sites
#: — while every other scope takes the UNDISCOUNTED sum of the lines it selects
#: (`_scoped_base`'s own docstring). So on a bill carrying two stacked
#: discounts they give different figures, deliberately, and `all_services` adds
#: no new arithmetic at all: it is `_scoped_base`'s existing fall-through made
#: explicit and given a name a clerk can choose.
SCOPE_ALL_SERVICES = "all_services"
SCOPE_SPECIFIC_SERVICES = "specific_services"
DISCOUNT_SCOPES = (
    SCOPE_WHOLE_BILL,
    SCOPE_ONE_SERVICE,
    SCOPE_USAGE_ONLY,
    SCOPE_BASE_ONLY,
    SCOPE_NAMED_CODES,
    SCOPE_ALL_SERVICES,
    SCOPE_SPECIFIC_SERVICES,
)

#: DIS-02 step 3: *"automatic vs apply-and-approve"*. The distinction is a
#: named validation gate, not a label — part 3: *"automatic enrolment with
#: mandatory proof (contradictory)"*.
ENROLMENT_AUTOMATIC = "automatic"
ENROLMENT_APPLY_AND_APPROVE = "apply_and_approve"
ENROLMENT_MODES = (ENROLMENT_AUTOMATIC, ENROLMENT_APPLY_AND_APPROVE)

#: r10's DIS-02 step 3 `Verification` select, verbatim and in its own order:
#: *"One-time proof at enrolment / Annual recertification / Agency file ·
#: monthly / Automatic"*.
VERIFY_ONE_TIME_PROOF = "one_time_proof"
VERIFY_ANNUAL_RECERT = "annual_recertification"
VERIFY_AGENCY_FILE_MONTHLY = "agency_file_monthly"
VERIFY_AUTOMATIC = "automatic"
VERIFICATION_METHODS = (
    VERIFY_ONE_TIME_PROOF,
    VERIFY_ANNUAL_RECERT,
    VERIFY_AGENCY_FILE_MONTHLY,
    VERIFY_AUTOMATIC,
)

#: r10's DIS-02 step 3 `On expiry` select, verbatim: *"Notify 60 days ahead,
#: then drop / Drop silently / Never expires"*. This is the POLICY and it lives
#: on the version. What actually happened to one customer is on the ENROLMENT
#: (`ended_on` + `end_reason`) — a mirrored copy on both would be free to drift,
#: and the enrolment is the row an auditor reads.
LAPSE_NOTIFY_THEN_DROP = "notify_then_drop"
LAPSE_DROP_SILENTLY = "drop_silently"
LAPSE_NEVER_EXPIRES = "never_expires"
LAPSE_BEHAVIOURS = (LAPSE_NOTIFY_THEN_DROP, LAPSE_DROP_SILENTLY, LAPSE_NEVER_EXPIRES)

#: DIS-02 step 4: *"budget cap and exhaustion behaviour"*.
EXHAUSTION_SUSPEND = "suspend"  # sets the discount to suspended_funding_exhausted
EXHAUSTION_REFUSE_NEW = "refuse_new_enrolment"  # existing enrolments keep billing
EXHAUSTION_CONTINUE = "continue_over_budget"  # the utility knowingly overspends
EXHAUSTION_BEHAVIOURS = (EXHAUSTION_SUSPEND, EXHAUSTION_REFUSE_NEW, EXHAUSTION_CONTINUE)
BUDGET_PERIOD_MONTHLY = "monthly"
BUDGET_PERIOD_ANNUAL = "annual"
BUDGET_PERIOD_LIFETIME = "lifetime"
BUDGET_PERIODS = (BUDGET_PERIOD_MONTHLY, BUDGET_PERIOD_ANNUAL, BUDGET_PERIOD_LIFETIME)

#: The version lifecycle, design §A7 drawn as a state machine. `scheduled` is
#: approved-but-not-yet-effective; `superseded` is what a later version does to
#: an earlier one. Submitting FREEZES a version (§A7.2) — editing a pending
#: version returns it to `draft` and clears the approval, because an approval
#: covers what was shown.
VERSION_DRAFT = "draft"
VERSION_PENDING_APPROVAL = "pending_approval"
VERSION_SCHEDULED = "scheduled"
VERSION_ACTIVE = "active"
VERSION_SUPERSEDED = "superseded"
VERSION_REJECTED = "rejected"
VERSION_STATUSES = (
    VERSION_DRAFT,
    VERSION_PENDING_APPROVAL,
    VERSION_SCHEDULED,
    VERSION_ACTIVE,
    VERSION_SUPERSEDED,
    VERSION_REJECTED,
)

#: The enrolment's own verification state — what is true about THIS customer,
#: as against the version's verification POLICY above.
VERIFICATION_NOT_REQUIRED = "not_required"
VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_EXPIRED = "expired"
VERIFICATION_REJECTED = "rejected"
VERIFICATION_STATUSES = (
    VERIFICATION_NOT_REQUIRED,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
    VERIFICATION_EXPIRED,
    VERIFICATION_REJECTED,
)

#: Part 3: *"income and medical proof restricted by role and excluded from
#: general document lists"* (BR-RAT-079). A privacy rule with a storage
#: consequence: the KIND decides the restriction, so a clerk browsing for a
#: meter photo cannot be shown a medical certification by a list that forgot to
#: filter. `DiscountEnrolmentDocument.restricted` is DERIVED from this set by
#: the write service and never accepted from a caller.
PROOF_KINDS = (
    "government_id",
    "birth_certificate",
    "veteran_id",
    "disability_award",
    "income_statement",
    "tax_return",
    "programme_award_letter",
    "medical_certification",
    "agency_file",
    "utility_record",
)
#: The two families part 3 names by hand. Kept as a set rather than a flag on
#: each kind so that adding a kind cannot silently add an UNrestricted one.
RESTRICTED_PROOF_KINDS = (
    "income_statement",
    "tax_return",
    "disability_award",
    "medical_certification",
)


class Discount(models.Model):
    """The discount's IDENTITY — the half that does not change when the value
    does (CR-013 part 3; r10 `PLN-01.discounts`).

    Code and name are split the way part 2 split them for charge codes and part
    5 for plans: `name` is the **customer-facing bill line label** (*"the bill
    line label"*, DIS-02 step 1), because part 3 requires the reduction to
    print as its own line and something has to print on it.

    `status` is the FOUR-value set, and `suspended_funding_exhausted` is the one
    a bill run may set — see `DISCOUNT_STATUSES`.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # unique per tenant, case-insensitive (SENIOR, CAP, …)
    name = models.TextField()  # the customer-facing bill line label (DIS-02 step 1)
    #: DIS-02 step 1: *"programme owner, funding source"*. r10's SENIOR detail
    #: renders the second as *"Funding · Rate-payer funded · Reported in the
    #: annual assistance-program filing"* — free text, because the set of
    #: funding sources is a utility's own (rate-payer, city general fund, a
    #: state grant, a named foundation) and a closed list would be invented.
    programme_owner = models.TextField(null=True, blank=True)
    funding_source = models.TextField(null=True, blank=True)
    #: r10's DIS-02 step 4 checkbox, verbatim: *"Report in the annual
    #: assistance-program filing"*. A compliance flag, not a billing one.
    report_in_assistance_filing = models.BooleanField(default=False)
    status = models.TextField(default=DISCOUNT_DRAFT)  # DISCOUNT_STATUSES
    #: Set by the bill run when a budget is exhausted and the version's
    #: exhaustion behaviour is `suspend` — stored so the screen can say WHEN,
    #: and so re-funding is a visible act rather than a status flipping back.
    funding_exhausted_at = models.DateTimeField(null=True, blank=True)
    #: ⚖️ **THE DATED RETIRE — PO ruling 2026-10-03 (4), `CR-166-BRC10`.** The
    #: LAST day anybody gets this discount, enrolled accounts included; nothing
    #: changes before it. NULL = not retiring. Stored on the discount as well as
    #: written onto the version windows (`retire_discount`) because the windows
    #: are what PRICE and this is what a screen and a new enrolment ASK:
    #: *is it retiring, and from when*. Pricing never reads it — the windows
    #: already say it by date, which is the whole fix for `DEF-RAT-9296`'s
    #: backwards stop (the old code skipped a retired discount by its CURRENT
    #: status, so a re-bill of August lost a discount it was owed).
    retire_on = models.DateField(null=True, blank=True)
    #: WHERE THIS DISCOUNT POSTS — CR-066 table 3, PO 2026-09-02: *"Please
    #: apply these - Table 3 - discounts."*
    #:
    #: A DEFERRED-FK uuid (B11 F-3), the same shape `charges.gl_account_id`,
    #: `taxes.liability_gl_account_id` and `reason_codes.default_gl_account_id`
    #: already have: the row is the LEDGER's, so the ledger validates ownership
    #: and liveness through `seams.ledger_account_is_live` and no cross-module
    #: FK constraint is minted here (B2 §2 — the reviewed interface set is not
    #: something a lane extends on its own).
    #:
    #: ⚠ **THIS CHANGES NO POSTING, AND SAYING SO IS THE POINT.** A discount
    #: line already resolves `4760 Customer discounts (contra-revenue)` BY
    #: DESIGNATION at issue (`apps/billing/issue.py`, `kind == "discount"`),
    #: under CR-061's ruling of 2026-09-01 — *"no, you cannot file discount
    #: under revenue"*. What this column adds is the tenant's ability to SEE
    #: that answer on Settings → Accounting and to override it, which is what
    #: every other mapping on that screen already offers. NULL means *nobody
    #: has overridden it*; the designation still answers.
    gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger_accounts
    #: BR-TEN-057 — the sample-data tag on the OWNING row, written only by this
    #: module's own service on the sample path.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discounts"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_discounts_tenant_code_ci"
            ),
            models.CheckConstraint(
                condition=Q(status__in=DISCOUNT_STATUSES), name="ck_discounts_status"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.code} ({self.status})"


class DiscountVersion(models.Model):
    """The dated, approvable CONTENT of a discount — what it is worth, what it
    touches, who qualifies, what it costs and who signed it off.

    ⚠ **THE VALUE'S UNIT DEPENDS ON `discount_type`, AND THAT IS WHY THERE IS
    ONE COLUMN AND NOT TWO.** For `percentage` the value is a PERCENT (r10's
    SENIOR stores `15`, and the bill shows `−15%`); for `fixed_amount` it is
    MONEY in `currency` (CAP stores `25.000000` USD, shown `−$25.00/mo`). Two
    columns would let a row carry both and mean neither, and the sign is not
    stored at all: a discount always reduces, so the magnitude is stored
    positive and the arithmetic subtracts — a stored `−15` and a subtraction
    would add.

    **Precision.** `NUMERIC(18,6)` for both, per hard rule 2 and CR-013's
    *"rates stored to 6 decimals, rounded at line level"* — AUTOPAY's `−0.5%`
    is exactly why: a percent that is not a whole number is ordinary here.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, db_column="discount_id")
    version_no = models.IntegerField(default=1)
    status = models.TextField(default=VERSION_DRAFT)  # VERSION_STATUSES

    # ── what it is worth ────────────────────────────────────────────────────
    discount_type = models.TextField()  # DISCOUNT_TYPES
    value = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")  # hard rule 2 pairing
    applies_to = models.TextField(default=SCOPE_WHOLE_BILL)  # DISCOUNT_SCOPES
    #: Set only when `applies_to = one_service` — r10's *"Per-service credit"*
    #: type on DIS-02 step 1 is this scope, not a fourth type.
    applies_to_service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="applies_to_service_id",
    )
    #: Set only when `applies_to = named_codes`: a JSON list of charge-code
    #: strings. Validated against this tenant's own `charges` at save — a code
    #: nobody has defined is a discount that silently reduces nothing.
    applies_to_charge_codes = models.JSONField(null=True, blank=True)
    #: ⚠ **`CR-091-BRC01` — SET ONLY WHEN `applies_to = specific_services`: a
    #: JSON LIST OF SERVICE CODES.**
    #:
    #: ⚠ **THE SHAPE IS COPIED FROM THE TAX AND NOT INVENTED.** `Tax.
    #: applies_to_services` has been *"a JSON list of catalog codes"* since the
    #: models lane's array disposition, validated against the tenant's enabled
    #: services on the way in and served as a list on two selectors. A second
    #: spelling of one idea is how a product acquires four different chips, so
    #: this carries the same NAME, the same TYPE and the same validation.
    #:
    #: ⚠ **AN EMPTY LIST IS A REFUSAL HERE AND MEANS *EVERYWHERE* ON A TAX, AND
    #: THE TWO MUST NOT BE HARMONISED.** A tax has no `All services` choice on
    #: screen, so its empty list is the only way to say *every service*; a
    #: discount HAS that choice, so an empty list stops being an expression of
    #: intent and becomes an unfinished form (PO ruling 2026-09-10). A screen
    #: that kept the tax's reading would silently apply a discount to every
    #: service on a form the clerk had not finished.
    applies_to_services = models.JSONField(null=True, blank=True)

    # ── caps, the floor, and stacking ───────────────────────────────────────
    #: DIS-02 step 2: *"caps per bill, per year, lifetime"*. NULL = uncapped,
    #: which is a decision the operator can see, not an absent one.
    cap_per_bill = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    cap_per_year = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    cap_lifetime = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: DIS-02 step 2: *"a floor so bills don't reach zero unless allowed"*.
    #: The default is **0.000000** and that is the whole of the "unless
    #: allowed": a discount may take a bill to zero but never below it, because
    #: a negative bill is a CREDIT — a different object, with a different
    #: ledger posting, that no discount may mint. A programme that must leave
    #: the customer paying something types a positive figure here.
    bill_floor_amount = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    #: Part 3: *"stacking precedence, explicit, because percentage-of-usage
    #: after a usage allowance gives a different number than the reverse"*.
    #: **Order is DATA, not code order** — lowest number applies first. Silver
    #: Creek runs SENIOR, CAP, PAPERLESS and AUTOPAY on the same accounts, so
    #: this is live from day one and not a future concern.
    stacking_precedence = models.IntegerField(default=100)
    stacks_with_others = models.BooleanField(default=True)  # r10 DIS-02 step 2 checkbox
    #: r10's SENIOR detail, verbatim: *"Stacking · Not with CAP credit · One
    #: assistance program per account — the larger applies."* Two discounts
    #: sharing a group are mutually exclusive on one account and the LARGER
    #: reduction wins. NULL = not in any exclusivity group.
    exclusivity_group = models.TextField(null=True, blank=True)

    # ── who qualifies, and how it is proved ─────────────────────────────────
    #: The DIS-02 step 3 rule builder's output — conditions combined with
    #: AND/OR. Stored as authored so the plain-language read-back is rendered
    #: from the same document that is evaluated, never from a second copy.
    #: ⚠ **ADVISORY IN THIS SLICE**: no code evaluates it, exactly as
    #: `rate_plans.eligibility` is advisory (BR-RAT-043). Enrolment is a staff
    #: act with a recorded verification; automatic evaluation is EP-RAT-12's
    #: remainder and is named rather than half-built.
    eligibility_rule = models.JSONField(null=True, blank=True)
    #: The plain-English sentence the landing renders — r10's `Age 65+`,
    #: `Program enrolment`, `E-bill on`, `Autopay enrolled`, `Veteran ID`.
    eligibility_summary = models.TextField(null=True, blank=True)
    #: `CR-166-BRC10` — WHO QUALIFIES, as a CODE of this utility's own
    #: `discount_list_values` row (`list_code = 'eligibility'`), which carries
    #: whether the system checks it or the customer shows proof (PO 2026-10-03,
    #: *"Who qualifies * - drop down"*). A plain text column holding a code, NOT
    #: a foreign key: a version is history (BR-RAT-037) and a utility renaming or
    #: retiring a list value must not rewrite or block a version that priced
    #: bills. `eligibility_summary` above stays as the label the code had when it
    #: was saved, so an old version still reads in words.
    eligibility_code = models.TextField(null=True, blank=True)
    enrolment_mode = models.TextField(default=ENROLMENT_APPLY_AND_APPROVE)  # ENROLMENT_MODES
    verification_method = models.TextField(default=VERIFY_ONE_TIME_PROOF)  # VERIFICATION_METHODS
    proof_required = models.BooleanField(default=False)
    #: The accepted document kinds (a subset of `PROOF_KINDS`). NULL = the
    #: programme states none, which is only coherent with `proof_required`
    #: false — the write service refuses the other combination.
    accepted_proof_kinds = models.JSONField(null=True, blank=True)
    #: DIS-02 step 3: *"whether proof precedes the first reduction"*. TRUE
    #: means an unverified enrolment reduces nothing; FALSE means the reduction
    #: starts and the proof is chased. A money rule, so it is stored, not
    #: assumed.
    proof_before_first_reduction = models.BooleanField(default=True)
    recertification_months = models.IntegerField(null=True, blank=True)  # NULL = never
    recertification_notice_days = models.IntegerField(default=60)  # r10: "notified 60 days ahead"
    recertification_grace_days = models.IntegerField(default=0)
    lapse_behaviour = models.TextField(default=LAPSE_NOTIFY_THEN_DROP)  # LAPSE_BEHAVIOURS

    # ── effective dating ────────────────────────────────────────────────────
    #: NULL = this version is a DRAFT and has no window — the same convention
    #: `tariff_versions.effective_from` uses (BR-RAT-031), so a half-built
    #: discount is storable and resumable rather than lost.
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)  # NULL = open-ended

    # ── budget, and what happens when it runs out ───────────────────────────
    budget_cap = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    budget_period = models.TextField(default=BUDGET_PERIOD_ANNUAL)  # BUDGET_PERIODS
    exhaustion_behaviour = models.TextField(default=EXHAUSTION_SUSPEND)  # EXHAUSTION_BEHAVIOURS

    # ── approval (design §A7, PO rulings 4 and 5 of 2026-08-19) ─────────────
    submitted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="submitted_by_user_id",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    #: Computed at SUBMIT from the tenant's own threshold and this version's
    #: budget cap, and STORED — not recomputed at approval. §A7.6: an approver
    #: must see the numbers the submitter saw, and a threshold the tenant edits
    #: between submit and approve would otherwise move the requirement under a
    #: signature. **A version with NO budget cap always stores TRUE** (PO
    #: ruling 2026-08-19: unbounded is the largest commitment there is).
    second_approval_required = models.BooleanField(default=False)
    #: The threshold in force at submit, stored beside the flag for the same
    #: reason: the row must be able to say WHY the second approval was asked
    #: for, months later, without reading today's settings.
    second_approval_threshold = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="approved_by_user_id",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    second_approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="second_approved_by_user_id",
    )
    second_approved_at = models.DateTimeField(null=True, blank=True)
    #: PO ruling 2026-08-19, verbatim *"yes allow it"*: a submitter MAY approve
    #: their own filing — Silver Creek has 1–2 staff and a second person is
    #: often nobody. The gate is unchanged; the fact is RECORDED so an auditor
    #: sees it rather than having to infer it by comparing two user ids.
    self_approved = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)

    # ── BR-RAT-1016 · CORRECTING A VERSION THAT IS ALREADY IN FORCE ─────────
    #
    # `CR-013` part 4's shared rules, quoted where they were written: *"a
    # historic typo is fixed by a documented correction version with a
    # reason."* Built for TAXES in `BR-RAT-104` and generalised to every priced
    # object by the PO's ruling of 2026-09-17 (*"please fix all these"*).
    #
    # ⚠ **A CORRECTION KEEPS THE WINDOW; A CHANGE GETS A NEW ONE.** A discount
    # whose value CHANGES is already a new version with new dates
    # (`create_discount_version`, and `BR-RAT-037`'s discipline). A CORRECTION
    # says the figure recorded for a period that has already run was wrong, so
    # it restates **the same `effective_from`/`effective_to`**, copied from the
    # corrected row and never taken from the payload. Without that property a
    # "correction" is a backdated change wearing a correction's clothes, and it
    # silently rewrites which bills the old figure was ever right for.
    #
    # The corrected row is never rewritten and never deleted: it goes to
    # `superseded` and keeps its value, its dates and its approval trail for
    # ever, which is what makes a discount's own version table readable as
    # history rather than as a current state.
    corrects = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
        db_column="corrects_version_id",
    )
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supersedes",
        db_column="superseded_by_version_id",
    )
    #: The reason in the operator's own words, REQUIRED on every correction.
    #: Free text, for `Tax.correction_reason`'s recorded reason: part 4 says
    #: *"with a reason"* and says nothing about a taxonomy, and billing's
    #: `correction_reasons` map is `BR-BIL-041`'s — classing a DISCOUNT
    #: correction against it is a rule nobody has written.
    correction_reason = models.TextField(null=True, blank=True)
    #: WHO FILED THE CORRECTION, on the version's OWN row.
    #:
    #: ⚠ **NOT AN `audit_log` LOOKUP, for hard rule 4's own reason:** `audit_log`
    #: is pruned on a retention schedule, so a version history that sourced its
    #: authors from there would lose them on the pruning run, silently. The
    #: shape is `Tax.corrected_by`'s and `TariffVersion.submitted_by`'s,
    #: verbatim (`DEF-367`) — stamped by the one path that writes a correction,
    #: so nobody types it and it cannot be wrong.
    corrected_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrected_discount_versions",
        db_column="corrected_by_user_id",
    )
    #: The reason this version exists — r10's version table renders it
    #: (*"Raised from −10% to −15%"*, *"Program created"*). Required on every
    #: version after the first, matching the rate-change reason discipline
    #: (BR-RAT-037).
    change_reason = models.TextField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discount_versions"
        indexes = [
            models.Index(fields=["tenant", "discount"], name="ix_discount_versions_discount"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["discount", "version_no"], name="uq_discount_versions_discount_no"
            ),
            #: At most ONE draft per discount, so "resume the half-built one" is
            #: unambiguous — the partial-unique shape BR-RAT-031 established for
            #: `tariff_versions`.
            #:
            #: ⚠ **THE RULE IS RIGHT AND HAD NO HANDLER, SO A DISCOUNT COULD BE
            #: EDITED EXACTLY ONCE — `DEF-RAT-5817`.** The second *Save new
            #: version* hit this index as a raw 500 and the edit door then
            #: stayed shut for ever, because nothing listed the blocking draft
            #: and nothing could discard it. `create_discount_version` refuses
            #: it in words now; `discount_version_chain` serves it and
            #: `discard_discount_version_draft` removes it. Do not relax this
            #: index to "fix" that — the sentence and the way out are the fix.
            models.UniqueConstraint(
                fields=["discount"],
                condition=Q(status=VERSION_DRAFT),
                name="uq_discount_versions_one_draft",
            ),
            models.CheckConstraint(
                condition=Q(status__in=VERSION_STATUSES), name="ck_discount_versions_status"
            ),
            #: `BR-RAT-1016` — a correction restates a window; it never
            #: corrects itself. The one shape that would make
            #: `corrects`/`superseded_by` a cycle of length one, stated
            #: verbatim from `taxes`' own `ck_taxes_corrects_not_self`.
            models.CheckConstraint(
                condition=Q(corrects__isnull=True) | ~Q(corrects=models.F("id")),
                name="ck_discount_versions_corrects_not_self",
            ),
            models.CheckConstraint(
                condition=Q(discount_type__in=DISCOUNT_TYPES),
                name="ck_discount_versions_type",
            ),
            #: ⚠ **THE TABLE LISTED FIVE OF THESE AND THE MODEL SEVEN, FOR NINE
            #: DAYS — `DEF-RAT-5814`.** `rating/0009` baked the original five
            #: into its `AddConstraint` as a literal, `CR-091-BRC01` added
            #: `all_services` and `specific_services` to the tuple above, and no
            #: migration followed — so two of the seven choices DIS-02 offers
            #: were a guaranteed `IntegrityError` and reached the clerk as
            #: *"Something went wrong on our side."* `rating/0040` widened it.
            #: **The migration's literal is deliberately NOT an import of this
            #: tuple**: the autodetector executes migration files, so an import
            #: would compare the model with itself and `makemigrations --check`
            #: could never notice the next divergence.
            models.CheckConstraint(
                condition=Q(applies_to__in=DISCOUNT_SCOPES), name="ck_discount_versions_scope"
            ),
            #: A value is a magnitude. A negative one would be an INCREASE
            #: wearing a discount's name, and the arithmetic subtracts.
            models.CheckConstraint(
                condition=Q(value__gte=0), name="ck_discount_versions_value_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(bill_floor_amount__gte=0),
                name="ck_discount_versions_floor_non_negative",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.discount_id} v{self.version_no} ({self.status})"


#: `CR-166-BRC10` — the three per-utility lists the New discount form draws as
#: dropdowns (PO 2026-10-03: *"Program owner - make this drop down"*,
#: *"Exclusivity group - can you make this drop down"*, *"Who qualifies * -
#: drop down"*). Editable on Settings › Reference data, seeded with the drawn
#: values (`apps/rating/discount_lists.py`).
LIST_PROGRAM_OWNER = "program_owner"
LIST_EXCLUSIVITY_GROUP = "exclusivity_group"
LIST_ELIGIBILITY = "eligibility"
DISCOUNT_LIST_CODES = (LIST_PROGRAM_OWNER, LIST_EXCLUSIVITY_GROUP, LIST_ELIGIBILITY)

#: Who qualifies comes in TWO groups (the drawing's own headings): *The system
#: checks* and *The customer shows proof*. Ruling 3 (2026-10-03): only a
#: `system` value may be Automatic.
CHECKED_BY_SYSTEM = "system"
CHECKED_BY_PROOF = "proof"
CHECKED_BY = (CHECKED_BY_SYSTEM, CHECKED_BY_PROOF)

#: The four conditions the product can evaluate itself — ruling 3's own list
#: (*"Everyone on the plan · Autopay is on · Paperless billing is on ·
#: Government or municipal account"*). A `system` list value carries exactly
#: one of these; a utility can RENAME the value but never invent a fifth check,
#: because a check the product cannot run would enrol nobody and say nothing.
CHECK_EVERYONE = "everyone"
CHECK_AUTOPAY = "autopay"
CHECK_PAPERLESS = "paperless"
CHECK_GOVERNMENT = "government"
CHECK_KEYS = (CHECK_EVERYONE, CHECK_AUTOPAY, CHECK_PAPERLESS, CHECK_GOVERNMENT)

#: The exclusivity group's *None* — a list row so the dropdown shows it, and
#: STORED as NULL on the version, because `discount_pricing` treats any non-null
#: group as a group and two discounts in a group called "none" would exclude
#: each other.
EXCLUSIVITY_NONE = "none"


class DiscountListValue(models.Model):
    """One choice in one of a utility's three discount dropdowns (`CR-166-BRC10`).

    ⚠ **A ROW IS A UTILITY'S OWN, AND NOTHING PRICES FROM IT.** A discount
    stores the CODE (`Discount.programme_owner`, `DiscountVersion.
    exclusivity_group`, `DiscountVersion.eligibility_code`), never a foreign
    key, so renaming a label re-labels every discount at once and retiring a
    value blocks no version that already priced bills. The one row that DECIDES
    something is a `system` eligibility value's `check_key`, which the
    automatic-enrolment job reads (ruling 3).

    RLS FORCE on PostgreSQL (`rating/0061`), hard rule 1.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    list_code = models.TextField()  # DISCOUNT_LIST_CODES
    code = models.TextField()
    label = models.TextField()
    #: Eligibility only: `system` or `proof`. NULL on the other two lists.
    checked_by = models.TextField(null=True, blank=True)
    #: Eligibility + `system` only: which of the four checks it runs.
    check_key = models.TextField(null=True, blank=True)
    #: Seeded from the drawing (BR-TEN-036): deactivatable, never deletable.
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discount_list_values"
        indexes = [
            models.Index(fields=["tenant", "list_code"], name="ix_discount_list_values_list"),
        ]
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"),
                models.F("list_code"),
                Lower("code"),
                name="uq_discount_list_values_code_ci",
            ),
            models.CheckConstraint(
                condition=Q(list_code__in=DISCOUNT_LIST_CODES),
                name="ck_discount_list_values_list",
            ),
            models.CheckConstraint(
                condition=Q(checked_by__isnull=True) | Q(checked_by__in=CHECKED_BY),
                name="ck_discount_list_values_checked_by",
            ),
            models.CheckConstraint(
                condition=Q(check_key__isnull=True) | Q(check_key__in=CHECK_KEYS),
                name="ck_discount_list_values_check_key",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.list_code}:{self.code}"


class PlanDiscountRule(BindingVersionMixin, models.Model):
    """`rate_plan × discount` — **AVAILABILITY, and nothing else.**

    ⚠ **THIS TABLE DELIBERATELY HAS NO VALUE COLUMN, AND THE ABSENCE IS THE
    RULING.** r10 draws a per-plan discount-value override
    (`SMARTBillHub.dc.html:10805`, and step 8 generates the sentence *"Override
    · {code} · discount value replaced with {value}"*). The PO ruled on
    2026-08-19, verbatim: **"no plan cannot override prices."** So a value
    column here is not merely unused — adding one would re-open the largest
    fork in CR-013 by making the forbidden thing storable.

    ⚠ **AND ATTACHING A DISCOUNT HERE DISCOUNTS NOBODY** (BR-RAT-069). Part 3:
    *"plan attachment makes a discount available, not granted."* A bill run
    reads `DiscountEnrolment`, never this table. Reading this table instead
    would reduce every bill on the plan — 842 of them on Residential Standard —
    and every one of those bills would be wrong by the discount.

    `PROTECT` on both FKs, because part 5's *"deletion refused once billed or
    ever enrolled"* is wider than a cascade can express.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(
        "rating.RatePlan", on_delete=models.PROTECT, db_column="rate_plan_id"
    )
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, db_column="discount_id")
    #: ── `BR-RAT-1066` · THE VERSION THIS ROW BELONGS TO (`rating/0062`) ──
    #: A plan version OWNS its bindings (`OQ-324` CLOSED (B), 2026-10-03). The
    #: default manager returns only the rows of the version a read on the day
    #: sees (`plan_versioning`); `all_versions` returns every row. NOT NULL from
    #: `rating/0064`; a writer that names no version gets the plan's head
    #: (`BindingVersionMixin`).
    plan_version = models.ForeignKey(
        "rating.PlanVersion",
        on_delete=models.PROTECT,
        db_column="plan_version_id",
        related_name="+",
    )
    #: The window during which this PLAN offers it — narrower than, never wider
    #: than, the discount's own effective window. NULL = for as long as the
    #: discount itself is available.
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = PlanBindingManager()
    all_versions = AllVersionsManager()

    class Meta:
        db_table = "plan_discount_rules"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "discount"],
                name="uq_plan_discount_rules_version_discount",
            ),
        ]


class DiscountEnrolment(models.Model):
    """THE GRANT — the row design §A9 names as one of two things the account
    must carry and does not.

    §A9, verbatim: *"Without this table, either nobody gets a discount or
    everybody on the plan does — and the second is a wrong bill for every
    account on it."*

    ⚠ **CROSS-MODULE FK TO `customers.Account`, IN THE REVIEWED SET (B2 §2).**
    The table is RATING-owned because the discount object it grants is rating's
    and because the bill run reads it while pricing — the same disposition
    `unit_plan_assignments` carries (rating-owned per B2 r16 #6, written via the
    customers seam). Rating never writes an `accounts` row.

    ⚠ **THE FK IS TO `Discount`, NOT TO `DiscountVersion`,** and that is part
    3's shared rule: *"enrolments survive versioning"*. r10's SENIOR went v1
    −10% → v2 −15% on Jan 1 2026 and its 72 accounts did not re-enrol; an
    enrolment tied to a version would have ended all 72 that morning.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, db_column="discount_id")
    account = models.ForeignKey(  # ⚠ cross-module → customers accounts (reviewed set, B2 §2)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    enrolled_on = models.DateField()
    enrolled_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="enrolled_by_user_id",
    )
    #: NULL = the enrolment is CURRENT. The partial unique below is what makes
    #: "one open enrolment per account per discount" a database fact rather
    #: than a service-layer hope.
    ended_on = models.DateField(null=True, blank=True)
    #: withdrawn | lapsed_recertification | discount_retired | ineligible |
    #: budget_exhausted — free-text-with-a-vocabulary, because the reason a
    #: subsidy stopped is read by a human in a dispute.
    end_reason = models.TextField(null=True, blank=True)

    verification_status = models.TextField(default=VERIFICATION_PENDING)  # VERIFICATION_STATUSES
    verified_on = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="verified_by_user_id",
    )
    #: Computed from the version's `recertification_months` at verification.
    #: NULL = nothing to recertify (a one-time proof, or an automatic
    #: programme). The *"expiring in 30 days"* filter part 3 asks for on the
    #: detail view reads exactly this column.
    recertification_due_on = models.DateField(null=True, blank=True)

    #: **Lifetime subsidy to date**, part 3's own words on the Enrolled-accounts
    #: tab. A denormalised running total of `discount_grants.amount` for this
    #: enrolment, written in the SAME transaction as the grant row it counts,
    #: and asserted equal to `SUM(grants)` by
    #: `test_cr013_discounts.py::test_lifetime_subsidy_equals_sum_of_grants` so
    #: the drift a counter invites goes RED rather than quiet.
    lifetime_subsidy_amount = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discount_enrolments"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_discount_enrol_account"),
            models.Index(fields=["tenant", "discount"], name="ix_discount_enrol_discount"),
            models.Index(
                fields=["tenant", "recertification_due_on"], name="ix_discount_enrol_recert"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "discount"],
                condition=Q(ended_on__isnull=True),
                name="uq_discount_enrolments_current",
            ),
            models.CheckConstraint(
                condition=Q(verification_status__in=VERIFICATION_STATUSES),
                name="ck_discount_enrolments_verification_status",
            ),
        ]


class DiscountEnrolmentDocument(models.Model):
    """The PROOF behind one enrolment (part 3: *"accepted proof documents"*).

    ⚠ **`restricted` IS DERIVED FROM `kind`, NEVER SUPPLIED BY A CALLER**
    (BR-RAT-079). Part 3: *"income and medical proof restricted by role and
    excluded from general document lists"* — a medical certification must not
    appear in the same list a clerk browses for a meter photo. Deriving it
    means a new restricted kind cannot be added as an unrestricted document by
    an endpoint that forgot the flag.

    This table records that a document EXISTS, its kind and its reference. The
    BYTES are the documents surface's problem and are not stored here; the
    upload flow is DIS-02 step 3's frontend and is out of this slice.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    enrolment = models.ForeignKey(
        DiscountEnrolment, on_delete=models.PROTECT, db_column="enrolment_id"
    )
    kind = models.TextField()  # PROOF_KINDS
    reference = models.TextField(null=True, blank=True)  # the documents-surface handle
    received_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    restricted = models.BooleanField(default=False)  # DERIVED from `kind`
    uploaded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="uploaded_by_user_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "discount_enrolment_documents"
        indexes = [
            models.Index(fields=["tenant", "enrolment"], name="ix_discount_docs_enrolment"),
        ]


class DiscountGrant(models.Model):
    """One reduction actually given — **APPEND-ONLY** (hard rule 4).

    This is what makes part 3's *"subsidy granted is reportable"* and its
    Budget-&-usage tab (*"granted vs budget, denials by cap or funding"*)
    answerable, and it is why budget consumption is a SUM over rows rather than
    a counter somebody decrements: a counter cannot say which bill spent the
    money, and finance is asked exactly that question at filing time.

    `discount_version` is stamped so a past reduction re-prices to the identical
    figure from the version in force for its service period — design §A0's
    compliance promise, the same stamp DEF-276 found missing from
    `invoice_lines.tariff_version_id`.

    A correction is a NEW ROW with the opposite sign (hard rule 4), which is why
    `amount` is signed: an ordinary grant is POSITIVE (the subsidy given) and a
    reversal is NEGATIVE, so the sum over rows is always the net subsidy.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    enrolment = models.ForeignKey(
        DiscountEnrolment, on_delete=models.PROTECT, db_column="enrolment_id"
    )
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, db_column="discount_id")
    discount_version = models.ForeignKey(
        DiscountVersion, on_delete=models.PROTECT, db_column="discount_version_id"
    )
    #: DEFERRED FK → billing `invoices` (B11 F-3 pass). Billing is another
    #: lane's territory this session and R6 is not yet wired into the bill run,
    #: so the column is a plain uuid and the constraint lands with the wiring.
    #: NULL until a bill carries it — a grant recorded from a preview or a
    #: back-fill has no invoice and must still be reportable.
    invoice_id = models.UUIDField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # signed; + = subsidy given
    currency = models.CharField(max_length=3, default="USD")
    granted_at = models.DateTimeField(auto_now_add=True)
    #: 🔒 `DEF-2430` (rating/0065) — **THE GRANT THIS ROW REVERSES**, on a
    #: reversal row only. A corrected bill's grants are reversed by NEW rows of
    #: the opposite sign (hard rule 4), each pointing at the row it cancels, so
    #: the sum over rows is the net subsidy and *"which correction gave this
    #: back"* has an answer. The reversal keeps the ORIGINAL bill's
    #: `invoice_id` and period, so it lands in the same cap year as the money
    #: it cancels. Unique where set: a grant can be reversed once, so a
    #: replayed correction cannot give the cap headroom back twice (rule 6).
    reverses_grant = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="reverses_grant_id",
    )

    class Meta:
        db_table = "discount_grants"
        indexes = [
            models.Index(fields=["tenant", "discount"], name="ix_discount_grants_discount"),
            models.Index(fields=["tenant", "enrolment"], name="ix_discount_grants_enrolment"),
        ]
        constraints = [
            #: IDEMPOTENCY (hard rule 6): re-running a bill for the same period
            #: cannot double-count a subsidy. A correction row is a different
            #: `invoice_id`, so it is not blocked by this.
            models.UniqueConstraint(
                fields=["enrolment", "discount_version", "period_start", "period_end"],
                condition=Q(invoice_id__isnull=True),
                name="uq_discount_grants_period_no_invoice",
            ),
            # IDEMPOTENCY (hard rule 6) at ISSUE: one grant per enrolment per
            # bill, so issuing (or replaying the issue of) one bill cannot count
            # a subsidy twice. Reversal rows carry the same bill's id and are
            # excluded here (rating/0065) — they are policed by the next one.
            models.UniqueConstraint(
                fields=["enrolment", "invoice_id"],
                condition=Q(invoice_id__isnull=False, reverses_grant__isnull=True),
                name="uq_discount_grants_enrolment_invoice",
            ),
            # …and at CORRECTION: a grant is reversed at most once.
            models.UniqueConstraint(
                fields=["reverses_grant"],
                condition=Q(reverses_grant__isnull=False),
                name="uq_discount_grants_reverses_grant",
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 of 5 VERBATIM (12-governance/11-change-requests.md) + CR-013 parts 4/5 for the tax-base and plan-composition rules + 04-docs/05-modules/06-rating/08-cr013-design.md §A2/§A7/§A8/§A9 + 07-r10-plans-rates-readout.md §3/§4 + the six PO rulings of 2026-08-19 (12-governance/02-decision-log.md) + CLAUDE.md hard rules 1/2/4/6/7
# generated: 2026-08-19 by the CR-013 EP-RAT-12 lane (discounts — the object, its versions, its plan availability and its enrolments)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — DIS-01/DIS-02 endpoints are a separate story) E=deferred(no-frontend-half — DIS-01 landing, the detail view and the DIS-02 wizard are explicitly out of this slice) F✔ G✔ H=deferred(PO 2026-08-09 — migration + money math flagged HUMAN-REVIEW-PENDING with ledger rows)
# gates: ruff✔ black✔ py_compile✔ · makemigrations --check clean✔ · migrate applies on a fresh database✔ · pytest tests/test_cr013_discounts.py 47 passed✔ · tests/test_us_ten_019_sample_records.py + test_cr010_silent_seed_gaps.py 43 passed✔ · golden-verify 33 PASS/0 FAIL (unchanged)✔ · run_gates G2/G3/G4/G5/G6/G7/G11 PASS on this file's slice; the other run_gates FAILs are PRE-EXISTING and named in the lane report, none of them this lane's
# exceptions: `rate_override` and `usage_allowance` are STORABLE but not PRICEABLE (DISCOUNT_TYPES_PRICEABLE) — both need engine work in EP-RAT-15 and activation refuses them by name rather than letting them reach a bill run and be skipped · r10's DIS-02 step-2 checkbox *"Taxes computed on the discounted amount"* is deliberately NOT a column here: CR-013 part 4 makes discount treatment statutory and PER TAX, so it belongs on `taxes.discount_treatment` (EP-RAT-13, unbuilt) and one global flag would hard-code one authority's answer for all of them · `plan_discount_rules` deliberately carries NO value column (PO ruling 2026-08-19 *"no plan cannot override prices"*) although r10 draws one · `eligibility_rule` is ADVISORY — nothing evaluates it, the same posture BR-RAT-043 gives `rate_plans.eligibility`; automatic eligibility evaluation is EP-RAT-12's remainder · `invoice_id` is a plain uuid (deferred FK → billing, B11 F-3) because R6 is not wired into the bill run and apps/billing belongs to another lane this session
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
