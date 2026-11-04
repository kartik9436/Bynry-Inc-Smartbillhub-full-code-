# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001/002/003 (EP-RAT-01 plans — rate_plans + plan_* rule tables) ·
#           US-RAT-004/005/006/007 (EP-RAT-02 schedules — tariffs/versions/tiers/
#           TOU/seasons/capacity/demand) · US-RAT-008/009 (EP-RAT-03 charges +
#           taxes/jurisdictions) · US-RAT-010/011 (EP-RAT-04 versioning + bulk —
#           rate_change_batches/log) · US-RAT-014 (EP-RAT-06 capacity_rates
#           consumer) · unit_plan_assignments hosted here per B2 r16 #6 owner map
#           (rating-owned, written via the customers seam)   Screens: S9–S13
# Rules:    BR-RAT-012/024/025/026/027/030 (plan bundle) · BR-RAT-039 (staff-
#           assignment only — no self-serve columns shipped) · BR-RAT-043
#           (discounts = negative charge rules; budget_billing plan flag;
#           ADVISORY rate_plans.eligibility jsonb — US-RAT-002 §5) ·
#           BR-RAT-031 (save-draft resumable — tariff_versions.effective_from
#           NULLABLE = the draft + one-open-draft partial unique) ·
#           BR-RAT-019/021/031/032/033/034 (schedule structures) · BR-RAT-014
#           (demand capture) · BR-RAT-015 (percent-of-service) · BR-RAT-018/022
#           (capacity) · BR-RAT-035/036/041/042 (charges/taxes forms) ·
#           BR-TEN-037 (tenant-entered jurisdictions, r16 #2 RLS) ·
#           BR-RAT-007/017/037/040 (versioning + append-only change log) ·
#           BR-CUS-010/011/013 (unit plan assignment snapshots, r5 #13)
# Tests:    06-backend/tests/test_w1_models.py (constraint halves on the migrated
#           sqlite test DB; RLS assertions live in the G5 isolation suite) ·
#           test_us_rat_schedules.py (draft storage) · test_us_rat_plans.py
#           (eligibility round-trip)
# Impacts:  rating engine (EP-RAT-05/06, W3) · customers plan-assignment seam ·
#           billing GL stamp (invoice_lines.tariff_version_id) · metering
#           units.rate_plan_id FK
# ───────────────────────────────────────────────────────
"""rating models — tables owned per B2 r16 owner map (Plans & Rates).

Schema law implemented here (signed): B2 §2 rating DDL as REDLINED by Addendum
r16 (never raw §2/§3 — r16 #8): r5 #2/#4/#6–#11/#14/#16–#18 (Plans & Rates
bundle), r6.0 (rate_plans split from the platform subscription_plans),
r6.1 (percent-of-service), r6.2 (demand_rate_config), r6.3 (plan GL), r6.5
(taxes completion + tax_jurisdictions tenant-scoped, r16 #2), r6.6 (charges
completion), r6.7 (rate_tiers.season_id + change_spec), r16 #3 (service_type
enum role → 10-service catalog FK) — plus the story-§5 PROPOSED-SCHEMA columns
carried verbatim (W0 precedent: PROPOSED shapes ship flagged, never invented).

Deliberate deviations, each REPORTED in the lane build report (E2 protocol —
reported, not resolved here):
- r6.0 lists `available_for_new_signup`; BR-RAT-039 as-modified (STATUS
  AUTHORITY) rules "no self-serve columns shipped" → column omitted.
- r6.5 lists a `taxes.percent` column beside base `taxes.rate`; the story §5
  maps the percent form onto `rate` → `rate` kept, duplicate not added.
- r6.7 adds `rate_tiers.season_id` while the base UNIQUE (tariff_version, seq)
  stands; per-season tier sets collide with that unique → base law kept
  verbatim, wrinkle reported.

SCHEMA-GAP FIX 2026-08-09 (migration 0003) — two ratified rules had no storage:
- BR-RAT-031 "save-draft resumable": B2 §2 has `tariff_versions.effective_from`
  NOT NULL, so a half-built structure could not be stored at all. The column is
  now NULLABLE and a NULL effective_from IS the draft; `uq_tariff_versions_one_
  draft` (PARTIAL, WHERE effective_from IS NULL) allows exactly one per tariff.
  B2 §2's EXCLUDE gist window constraint was never materialized by migration
  0001 (no btree_gist extension) — so there was no DB constraint to make
  partial; the app-side half (services._guard_window) reads activated versions
  only. REPORTED, not resolved here.
- BR-RAT-043 / US-RAT-002 §5 "eligibility … stored on the plan": added as
  `rate_plans.eligibility` jsonb, ADVISORY ONLY (never gates assignment).
Deferred FKs (B11 F-3 pass — target tables land in later waves): account_types/
account_subtypes (customers, W2) and ledger_accounts (ledger, W5) are plain
uuid columns here; the FK constraints land with the owning module's wave.

Monetary/rate columns are NUMERIC(18,6) + CHAR(3) currency (DB-3); PKs are
uuidv7-style (DB-2, app-side shim per O-1 residue). Enum-ish value sets are
TextFields per the W0 pattern (r5 #20 enum→lookup direction; value sets in
comments). RLS: every table below gets ENABLE+FORCE via migration
0003_rls_w1_policies (SQL in 06-backend/db/rls_rating_w1.sql).
"""

from datetime import timedelta
from typing import Any

from django.db import models

from core.money_fields import money_field, percent_field, rate_field
from django.db.models import Q
from django.db.models.functions import Lower

from apps.rating.constants import KINDS, PRICE_HISTORY_EPOCH
from apps.rating.plan_versioning import (
    AllVersionsManager,
    BindingVersionMixin,
    PlanBindingManager,
)
from apps.rating.pricing.percent_basis import PERCENT_BASIS_USAGE
from core.dbfields import uuid7_pk

_ONE_DAY = timedelta(days=1)


class RatePlan(models.Model):
    """Customer-facing utility plan bundle (r6.0 `rate_plans` — the PO-ruled
    rename away from the platform SKU table; BR-RAT-025 D4). Staff-assignment
    only in v1 (BR-RAT-039 as-modified: no self-serve/zone columns)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # r6.0: unique per tenant, case-insensitive
    name = models.TextField()  # unique per tenant (US-RAT-002 TC-7)
    description = models.TextField(null=True, blank=True)
    # D5 targeting — DEFERRED FK → customers account_types/account_subtypes (W2; B11 F-3)
    #: ── THE CUSTOMER CLASSES THIS PLAN IS FOR (DEF-RAT-5768, PO 2026-09-19) ─
    #: ⚠ **THIS WAS `account_type_id = models.UUIDField(...)`, ONE CLASS, AND
    #: IT IS `rating/0038` THAT REPLACED IT. DO NOT PUT THE SINGLE COLUMN
    #: BACK.** Walking step 1 of the plan wizard in the beta the PO asked for
    #: *"Customer class - multi select drop down"*, and on being shown that
    #: this is a schema change and that every plan already written has to mean
    #: something under the new rule, ruled, verbatim: ***"your understanding is
    #: correct - we have all option anyway in drop down list - that is
    #: default"***.
    #:
    #: **THE MIGRATION IS STATED AND IS NOT A GUESS:** a plan holding ONE class
    #: becomes a list of one; a plan holding NULL becomes `[]`; and **`[]`
    #: means EVERY class**, which is the default the PO names.
    #:
    #: ⚠ **NULL AND `[]` BOTH MEAN EVERY CLASS**, the same reading
    #: `charges.applies_to_customer_classes` has carried since `DEF-273`.
    #: Building a second, different shape for one question is how a product
    #: ends up holding two answers to it — which it already did, for weeks,
    #: because the charge code had a list and the plan had a scalar.
    #:
    #: ⚠ **IDS, NOT CODES, AND THIS IS THE ONE PLACE IT DELIBERATELY DIFFERS
    #: FROM ITS SIBLING.** `applies_to_customer_classes` stores platform
    #: `account_types.code` strings; this stores the uuids the plan's own
    #: column always held. Two reasons, and the second is the load-bearing one:
    #: every reader of this column already takes a uuid, so a key change would
    #: be a second migration of MEANING on top of a migration of CARDINALITY;
    #: and `account_types` is becoming TENANT-OWNED (`rating/seams.py`
    #: `account_type_id_by_code` says so in its own docstring), after which a
    #: code is no longer unique across utilities and a stored code would be
    #: ambiguous. The SEMANTICS are matched exactly; the key is not.
    #:
    #: ⚠ **NOTHING PRICES A BILL FROM THIS AND THAT WAS CHECKED, NOT ASSUMED.**
    #: `resolution.py` and `resolution_catalogue.py` name no `rate_plans`
    #: class column at all — R1 resolves the plan in force from the ACCOUNT's
    #: assignment — so this column narrows a screen's pickers and the plan
    #: list's filter, and moves no money either way.
    account_type_ids = models.JSONField(null=True, blank=True, default=list)
    account_subtype_id = models.UUIDField(null=True, blank=True)
    #: ── THE OUTSIDE-CITY SURCHARGE (BR-RAT-102, PO ruling 2026-08-21) ──────
    #: PO verbatim: *"We can have it on plan itself - Plan will decide whether
    #: to apply and then how much."*
    #:
    #: It lives on the PLAN because a surcharge is a property of the DEAL, not
    #: of the pricing math — two plans at one utility may surcharge differently,
    #: which a tenant-wide scalar cannot express, and putting it on the rate
    #: SCHEDULE would make the same schedule mean different money depending on
    #: who referenced it. This is BR-RAT-096's binding principle applied to
    #: money: the plan is where the product composes.
    #:
    #: ⚠ **NULL OR `1` MEANS THIS PLAN DOES NOT SURCHARGE, AND THAT IS NOT THE
    #: SAME AS "INSIDE CITY".** `resolution.money_factor` short-circuits on a
    #: factor of 1 and never consults the premises at all, so a utility that
    #: does not price by jurisdiction can never be refused by R5. A plan that
    #: DOES state a factor, over a premises whose `inside_city_limits` is None,
    #: STOPS THE BILL — the factor changes every line, so a guess there is a
    #: wrong bill rather than a partial one.
    #:
    #: ⚠ **`charges.outside_city_applies` IS NOT SUPERSEDED — IT IS THE OTHER
    #: HALF.** This says WHAT the factor is; that column says whether a given
    #: charge is subject to it, and R4 already honours it. Two questions, two
    #: answers, same two-gate shape as BR-RAT-096.
    #:
    #: `rate_field` (6 places) rather than `money_field` (4): this is a
    #: MULTIPLIER, and BR-RAT-092 puts rates at six because a rate is multiplied
    #: by something before it becomes money — truncating one moves the bill,
    #: where truncating an amount only moves itself.
    outside_city_factor = rate_field(null=True, blank=True)
    status = models.TextField(default="draft")  # draft | published | archived (BR-RAT-030)
    version = models.IntegerField(default=1)  # +1 per content change (BR-RAT-037)
    minimum_bill_amount = models.DecimalField(  # plan floor, mode B (r5 #18 / BR-RAT-028)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    budget_billing = models.BooleanField(
        default=False
    )  # BR-RAT-043 plan flag (mechanics EP-BIL-06)
    eligibility = models.JSONField(  # US-RAT-002 §5 "Eligibility checkboxes … stored on the
        null=True, blank=True  # plan" — ADVISORY ONLY (BR-RAT-043): read/written by the plan
    )  # service and carried in the plan audit before/after; it NEVER gates assignment.
    #: ── THE LATE-FEE CHARGE CODE THIS PLAN CHARGES ON (BR-RAT-1011, `CR-078`,
    #: PO ruling 2026-09-07) ────────────────────────────────────────────────
    #: PO verbatim: *"this is wrong - you ahve to take late fees form charge
    #: code mentione din the plan - if plan doent provide you that charge code
    #: then you have to put zero on late payment. - Logic aplplied ot Minimum
    #: late fee $5- - you can link these defaults in Charge code - we have a
    #: charge code for late payment"*.
    #:
    #: ⚠ **NULL MEANS ZERO, NOT "USE THE DEFAULT".** This is the whole of the
    #: ruling and it reverses the reading every other nullable column on this
    #: model carries. `minimum_bill_amount` NULL falls back to the tenant's;
    #: `PlanPenaltyRule.late_fee_pct` NULL falls back to the tenant's. This one
    #: does not fall back to anything: a plan naming no late-fee charge code
    #: charges **$0.00** in late fees, deliberately and visibly.
    #:
    #: WHY A COLUMN AND NOT A LOOKUP OF `code='LATE'`: BR-RAT-035 makes charge
    #: amounts seeds a tenant edits, and B12's no-hard-coded-values law makes
    #: `LATE` a seed name rather than a vocabulary. A utility that calls theirs
    #: `LATEPAY` is one row away, not a fork away — and matching on the string
    #: would fail SILENTLY for them, which is the exact shape of DEF-CUS-3653.
    #:
    #: ⚠ **THE ORDER THIS COLUMN ARRIVED IN IS PART OF THE RULE.** Switching the
    #: engine before this column was populated would have turned every late fee
    #: on every live tenant to $0.00, silently, on real bills — nothing raises,
    #: nothing logs, and a customer simply is not charged. So `rating/0026`
    #: adds it, `rating/0027` fills it with the tenant's `LATE` code on every
    #: plan of every tenant, and only then does the resolution path read it
    #: (`selectors.plan_late_fee_terms`). The CR row states the sequence as part
    #: of the change rather than as an implementation detail.
    #:
    #: `PROTECT`, like every other charge reference here: a charge code a plan
    #: charges late fees on may not be deleted out from under it.
    late_fee_charge = models.ForeignKey(
        "rating.Charge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="late_fee_charge_id",
        related_name="late_fee_for_plans",
    )
    effective_from = models.DateField(null=True, blank=True)  # US-RAT-002 §5 PROPOSED-SCHEMA
    effective_to = models.DateField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    #: ── `BR-RAT-1066` · THE HEAD (`rating/0062`) ──────────────────────────
    #: The version a dateless read falls back to when no version's window
    #: covers the day: the latest-starting published version, or a draft
    #: plan's v1. The four term columns above (`minimum_bill_amount`,
    #: `outside_city_factor`, `budget_billing`, `late_fee_charge`) are THE
    #: HEAD'S terms, kept equal to the head row's copy on every write
    #: (`apps.rating.plan_versioning` says why). `SET_NULL` because the only
    #: path deleting a version is `delete_plan`, which then deletes the plan.
    head_version = models.ForeignKey(
        "rating.PlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="head_version_id",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rate_plans"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_rate_plans_tenant_code_ci"
            ),
            models.UniqueConstraint(fields=["tenant", "name"], name="uq_rate_plans_tenant_name"),
        ]


class Tariff(models.Model):
    """Rate schedule identity (B2 `tariffs` — 'a Plan in the UI' note superseded
    by the r6.0 split: tariffs are the pricing-formula side). One service, one
    model per version (BR-RAT-031)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()
    service = models.ForeignKey(  # r16 #3: catalog FK replaces the service_type enum role
        "tenancy.Service", on_delete=models.PROTECT, db_column="service_id"
    )
    # US-RAT-005 §5 PROPOSED-SCHEMA: informational targeting; DEFERRED FK → account_types (W2)
    account_type_id = models.UUIDField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tariffs"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name", "service"], name="uq_tariffs_tenant_name_service"
            ),
        ]


class TariffVersion(models.Model):
    """Effective-dated pricing (DB-5): history bills on its version, never the
    current one (BR-RAT-007).

    `effective_from` is NULLABLE and **NULL IS THE DRAFT** (BR-RAT-031
    "save-draft resumable"): a half-built structure hangs off a dateless
    version row exactly like a dated one, so reopening the wizard just reloads
    it. Activation stamps the date on that same row after the completeness gate
    (BR-RAT-031: complete structure + effective_from). One open draft per
    tariff is the partial unique below; every dated version stays outside it.

    ⚠ **NON-OVERLAP OF THE DATED WINDOWS IS NOW A REAL DATABASE CONSTRAINT
    (`DEF-RAT-8000`). THIS PARAGRAPH SAID IT WAS NOT, FROM 2026-08-19 UNTIL
    2026-09-29.** It read: *"B2 §2's EXCLUDE gist constraint, which migration
    0001 never materialized (btree_gist is not installed; the app-side half is
    services._guard_window) — REPORTED, not invented here."* True when written,
    and it stayed true for six weeks while `services._apply_batch_to_schedule`
    carried a comment asserting the opposite. Ottumwa Water Works reached four
    versions of one sewer schedule in force on 2026-10-29 in the gap.

    `rating/0045` installs `btree_gist`, `rating/0046` closes the windows that
    were left open (and REFUSES, naming the rows, where it would have to
    guess), and `rating/0047` adds

        ex_tariff_versions_no_overlap
        EXCLUDE USING gist (tenant_id WITH =, tariff_id WITH =,
                            daterange(effective_from,
                                      COALESCE(effective_to + 1,
                                               'infinity'::date)) WITH &&)
        WHERE (effective_from IS NOT NULL AND superseded_by_version_id IS NULL)
        DEFERRABLE INITIALLY DEFERRED

    **It is NOT declared here in `Meta`** — the repo's one other exclusion
    constraint (`integrations/0001`) is raw vendor-branched DDL for the same
    reason: `django.contrib.postgres` is not in `INSTALLED_APPS` and its DDL
    does not parse on SQLite. `rating/0047`'s docstring is the authority on the
    three ways the predicate differs from B2 §2's literal text (drafts,
    corrections, and `effective_to` being INCLUSIVE where `daterange` is not).

    ⚠ **SQLITE HAS NONE OF IT**, so the whole test suite runs without this
    guarantee (hard-won law 14). `services._guard_window` and
    `services._close_open_windows_before` are the app-side half and are what
    every test actually exercises; the constraint itself is asserted in
    `tests/test_def_rat_8000_no_overlap_pg.py`, which skips by name off
    PostgreSQL rather than passing vacuously."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff = models.ForeignKey(Tariff, on_delete=models.PROTECT, db_column="tariff_id")
    # flat|tiered|time_of_use|demand|seasonal|capacity (r5 #16) + percent_of_service (r6.1)
    model = models.TextField()
    #: ⚠ NULLABLE SINCE 2026-08-19 (DEF-277), AND THE NULL MEANS SOMETHING.
    #: CR-013 part 1, verbatim: *"Blank base = size not served"*. Until this
    #: date the column was NOT NULL with `default=0`, so an omitted base, a size
    #: the utility refuses to serve and a deliberate "served, and free" all
    #: stored `0.000000` and were indistinguishable once written — and a bill
    #: then printed `$0.00` for a size that has no price at all.
    #:
    #: NULL = no base was stated; the bill REFUSES rather than charging zero
    #: (`apps.billing.gather._base_charge_for`). `0` = stated, and free.
    #:
    #: **The rows already in the database keep their `0` and keep billing
    #: `$0.00`** — PO ruling 2026-08-19, verbatim *"print $0.00"*. The migration
    #: deliberately converts nothing: every historic zero is either "not served"
    #: or "free", the data does not say which, and a migration that guessed
    #: would put a refusal or a price on a bill on the strength of a guess.
    base_charge = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: ── `CR-120-BRC06` · `BR-RAT-1025` — THE SCHEDULE NAMES ITS BASE CHARGE
    #: CODE. IT STILL HOLDS NO FIGURE (PO ruling 2026-09-19).
    #:
    #: PO verbatim: *"no this is not correct ; So: plan → rate schedule ->
    #: charge code → base charges - this is correct"*, correcting the order of
    #: their own sentence of 2026-08-31 (*"plan -> charges code -> base
    #: scharges"*). And on why this reverses nothing: *"we are not bindng base
    #: charges in rate schedule - you were taking it default; now we are making
    #: it explicit it is a same rule - change is default -> expliciate"*.
    #:
    #: ⚠ **READ THIS BESIDE THE COLUMN ABOVE, BECAUSE THEY ARE OPPOSITES AND
    #: THEY SIT SIDE BY SIDE.** `base_charge` is a RETIRED DECIMAL — a figure
    #: the schedule used to hold, which `BR-RAT-088` retired on 2026-08-20 and
    #: which `RateScheduleWizard` has had no control for since. It stays
    #: retired, it is read at exactly one place (`resolution
    #: ._legacy_schedule_base`, R4's fallback for a tenant provisioned before
    #: the ruling), and **nothing may repurpose it.** This column is a
    #: POINTER. The schedule says WHICH code owns its service's base; the code
    #: still says what that base is WORTH, per customer class and per
    #: connection size. *"base will come from base"* — the PO, the same day.
    #:
    #: **NULL IS THE FALLBACK AND IT IS THE DESIGN, NOT AN OVERSIGHT.** A
    #: schedule that names nothing resolves its base exactly as it does today:
    #: the `is_base` charge code for the service, narrowed by the account's
    #: customer class and its connection size (`resolution.resolve_base_charge`
    #: · `selectors.base_charge_from_charge_code`). **Every schedule that
    #: exists on the day this column ships stores NULL, so no bill moves** —
    #: which is the claim the ruling rests on and is proved rather than
    #: asserted in `tests/test_cr120_schedule_names_base_charge_code.py`, over
    #: all 47 ready accounts of the shipped fixture.
    #:
    #: The two-tier shape — NAMED first, inferred second — is
    #: `PlanWizard.lateFeeSourceCharge`'s, deliberately: *"Two places a plan can
    #: name it, and the order matters"* (`BR-RAT-1011` / `CR-078`, PO
    #: 2026-09-07). One pattern for two bindings rather than two that happen to
    #: agree.
    #:
    #: ⚠ **NOT a gate at billing time, and a gate at ACTIVATION time.** A bound
    #: code that could not price this schedule's service — not `is_base`, a
    #: different service, inactive, or scoped to a customer class this schedule
    #: excludes — is refused by `services._guard_bound_base_charge_code` when
    #: somebody activates the version. That is where the refusal belongs: a
    #: settings screen with the cure in its own sentence, rather than an
    #: exception tab on the day the money is due (`DEF-2923`'s reasoning, one
    #: column across).
    base_charge_code = models.ForeignKey(
        "rating.Charge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="base_charge_code_id",
        related_name="base_for_tariff_versions",
    )
    #: ⚠ RETIRED FROM BILLING 2026-10-01 (`DEF-RAT-8737`, PO option A). Not
    #: read by any pricing path and refused by the API when stated; the minimum
    #: is `RateSizeRow.minimum_bill`. A row still holding a figure after
    #: `rating/0053` is one that had no size row to move onto — the clerk's list.
    minimum_bill = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    uom = models.TextField(null=True, blank=True)  # US-RAT-005 §5 PROPOSED-SCHEMA; BR-RAT-038 gate
    percent = models.DecimalField(  # r6.1 percent-of-service (BR-RAT-015)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    basis_service = models.ForeignKey(  # r6.1: e.g. sewer = % of water usage-charge $
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="basis_service_id",
        related_name="basis_for_tariff_versions",
    )
    #: **A PERCENTAGE OF WHAT, EXACTLY** — `CR-130-BRC07` · `BR-RAT-1030`, PO
    #: ruling 2026-09-22. `'usage'` takes the percentage of the basis service's
    #: metered QUANTITY and prices the result on this schedule's own rate;
    #: `'charge'` takes the percentage of that service's usage-charge DOLLARS
    #: and needs no rate at all.
    #:
    #: The PO's two figures, verbatim: *"if water charge is $100, and %age is
    #: 80% then sewer cahrge will be $80"* and *"if Water usage will be 100
    #: gallan %age is 80% then sewer uage will be 80 gallan = sewer charge will
    #: be 80 X { flat rate or tiered rate}"*.
    #:
    #: ⚠ **EVERY ROW THAT EXISTED BEFORE THIS COLUMN IS WRITTEN `usage` BY NAME
    #: IN `0043_cr130_percent_basis.py`, NEVER LEFT TO THE DEFAULT.** The
    #: database default is there so an INSERT racing the migration cannot land
    #: a NULL; the explicit backfill is what makes the schedules already in
    #: force SAY `usage` rather than merely behave like it. A schedule that
    #: silently changed basis would move real money on a real customer, ❄️
    #: `GT-17`'s $36.00 among them.
    #:
    #: ⚠ **NOT A CHOICES FIELD, FOR THE REASON `billing_basis` IS NOT ONE
    #: EITHER.** The allowed pair is stated ONCE, in `PERCENT_BASES` below, and
    #: read from there by the validator, the selector and the plugin — so there
    #: is one statement of the vocabulary rather than a `choices` list and a
    #: constant that can drift apart.
    percent_basis = models.TextField(default=PERCENT_BASIS_USAGE)
    effective_from = models.DateField(  # NULL = the resumable DRAFT (BR-RAT-031)
        null=True, blank=True
    )
    effective_to = models.DateField(null=True, blank=True)  # null = current
    approved_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set); metadata only,
        "identity.User",  # never a gate (BR-RAT-031 as-modified)
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="approved_by",
    )
    regulator_ref = models.TextField(null=True, blank=True)  # US-RAT-005 §5 PROPOSED-SCHEMA
    #: BR-RAT-082 (PO ruling 2026-08-20) — THE REGULATOR SIGNS OUTSIDE THE
    #: PRODUCT AND WE RECORD IT. PO verbatim: *"this is correct; it is system of
    #: record so we can collect the details and keep it."* The rule names FIVE
    #: things to capture — *"filing reference (`PUC #W-2025-1184`), authority,
    #: submitted date, approved date, approver name"* — and only the filing
    #: reference had a column (`regulator_ref`, above). These four are the rest.
    #:
    #: ⚠ **NONE OF THEM IS A GATE, AND THAT IS THE WHOLE RULE.** BR-RAT-031
    #: as-modified removed the in-system board-approval workflow; `approved_by`
    #: above stays optional INTERNAL metadata. The regulator's sign-off is *"a
    #: date and a docket number typed in, not a workflow step"*, so nothing here
    #: is read by activation, by the engine, or by any refusal. A lane that
    #: makes one of these required has rebuilt the workflow the PO removed.
    #:
    #: `regulator_approver` is TEXT, not a `User` FK: the person who signs is a
    #: commissioner at the PUC, not a user of this product. `approved_by` is the
    #: internal Owner/Admin and is a different fact about a different person.
    filing_authority = models.TextField(null=True, blank=True)
    filed_on = models.DateField(null=True, blank=True)  # "submitted date"
    regulator_approved_on = models.DateField(null=True, blank=True)  # "approved date"
    regulator_approver = models.TextField(null=True, blank=True)  # "approver name"
    #: DEF-369 · **THE LABEL A DOCKET REFERENCES, STORED.**
    #:
    #: Until this column existed, `v3` was an ORDINAL: the screen counted the
    #: position of a row in the server's own effective-date order. That is
    #: stable right up to the day a version is back-dated into the chain, and
    #: then the `v3` a utility filed with its regulator and the `v3` the product
    #: prints are two different versions of the rate. A filing is referenced by
    #: its label for decades; a position is not a label.
    #:
    #: NULL is the honest answer for every version written before this column,
    #: and for every version a utility never labelled — the screen falls back to
    #: the derived ordinal AND SAYS IT IS DERIVED rather than promoting a
    #: position to an identifier. Free TEXT, not an integer: real filings read
    #: `v3`, `2027-A`, `Sheet 4 Rev 2`.
    #:
    #: ⚠ NOT UNIQUE AND NOT A GATE, for BR-RAT-082's reason (one column up):
    #: the regulator's paperwork is recorded, never enforced. A utility that
    #: files two sheets under one label has a filing problem, not a data-entry
    #: refusal, and the product is the system of record for what they did.
    version_label = models.TextField(null=True, blank=True)
    #: DEF-367 · WHO FILED IT — and it is a different person from `approved_by`.
    #:
    #: BR-RAT-083 splits them: anyone drafts, an Owner/Admin activates. So the
    #: `BY` column of a Versions & filings table cannot be filled from
    #: `approved_by`, and a regulator asking *"who filed this"* is asking about
    #: this column. Stamped from the acting user by `_write_version`, on every
    #: path that writes a version — nobody types it, so it cannot be wrong.
    #:
    #: Metadata, never a gate — same standing as `approved_by` (BR-RAT-031
    #: as-modified). NULL for every version written before this column existed
    #: and for anything a system job writes; the screen names the absence.
    submitted_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="submitted_by",
        related_name="submitted_tariff_versions",
    )
    #: DEF-280 · THE AUTHORED CHANGE NOTE, kept WITH the version it describes.
    #:
    #: BR-RAT-037 already requires a reason on every change to a published
    #: object, and `create_rate_schedule_version` has always refused without
    #: one — it just wrote that sentence to `rate_change_log` and nowhere the
    #: version could be read from. §10 is explicit that the `CHANGE` column of a
    #: filings table is *"AUTHORED by the person filing the version, not derived
    #: from a diff"*, and the sentence was authored: it was simply stored where
    #: the filing record cannot see it.
    #:
    #: So this is a COPY of BR-RAT-037's reason, not a second question asked of
    #: the user. The `rate_change_log` row stays exactly as it was (it is the
    #: cross-object history and carries plan changes too); this is the same
    #: words on the row a regulator reads. NULL for a first version — there was
    #: no change to describe — and for every version written before this column.
    change_reason = models.TextField(null=True, blank=True)
    #: ── DEF-RAT-5715 · BR-RAT-104 REACHES A RATE SCHEDULE ─────────────────
    #:
    #: **A CORRECTION IS NOT A RATE CHANGE, AND THE DIFFERENCE IS THE WINDOW.**
    #: A rate CHANGE is already a new row with a NEW window (BR-RAT-037,
    #: `create_rate_schedule_version`). A CORRECTION restates the SAME window,
    #: because the figure recorded for that period was **wrong** — which is the
    #: PO's own distinction, verbatim: *"it is not a new rate or it is not a
    #: change in rate - it is just an error handling"*.
    #:
    #: These four columns are `Tax`'s, deliberately verbatim rather than
    #: re-invented. CR-013 part 4's words are generic — *"in-place edits of an
    #: ACTIVE VERSION are refused outright … a historic typo is fixed by a
    #: documented correction version with a reason"* — and the 2026-08-21 build
    #: satisfied them on the tax and not on the tariff version. Two shapes for
    #: one signed rule is how the two start answering differently.
    #:
    #: The corrected row is **never rewritten and never deleted**: it keeps its
    #: rate, its dates and its audit trail for ever. It stops pricing because
    #: `in_force_version` skips a superseded row, not because anything about it
    #: changed — which is what keeps a bill issued under it reproducible
    #: (BR-RAT-007, BR-RAT-017, hard rule 4).
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
    #: Free text, for `Tax.correction_reason`'s stated reason: part 4 says
    #: *"with a reason"* and says nothing about a taxonomy.
    #: ⚠ It is NOT `change_reason`. That one answers *why the price moved*; this
    #: one answers *what was typed wrongly*, and a screen that showed one where
    #: the other belongs would put a filing note on a typo.
    correction_reason = models.TextField(null=True, blank=True)
    #: WHO FILED THE CORRECTION — stamped from the acting user on the one path
    #: that writes one, so nobody types it and it cannot be wrong. NOT read back
    #: out of `audit_log`: that table is pruned on a retention schedule (hard
    #: rule 4's 2026-09-02 narrowing), so a rate history sourced from there
    #: would lose its `BY` column silently. `submitted_by` above established
    #: both the shape and the reason (DEF-367).
    corrected_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="corrected_by",
        related_name="corrected_tariff_versions",
    )
    notify_customers = models.BooleanField(default=False)  # capture-only v1 (US-RAT-005 §5)
    publish_public = models.BooleanField(default=False)  # capture-only v1 (no A1 screen)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tariff_versions"
        indexes = [
            # B2 §4 ix_tariff_versions_lookup — reprice by service_date window join
            models.Index(
                fields=["tenant", "tariff", "effective_from", "effective_to"],
                name="ix_tariff_versions_lookup",
            ),
        ]
        constraints = [
            # BR-RAT-031: ONE open draft per tariff. PARTIAL by design — the
            # predicate keeps every dated (activated) version out of this
            # unique, so history is untouched.
            models.UniqueConstraint(
                fields=["tariff"],
                condition=Q(effective_from__isnull=True),
                name="uq_tariff_versions_one_draft",
            ),
        ]


class ChargeCodeAmount(models.Model):
    """BR-RAT-088 · §B3 — the per-size amount table, and the ONE place a base
    charge is editable.

    ⚠ **READ THIS BEFORE YOU WRITE A ROW HERE: A CHARGE CODE STATES A FLAT
    `charges.amount` **OR** A TABLE OF THESE ROWS, AND NEVER BOTH. WRITING ONE
    WITHOUT CLEARING THE OTHER STOPS EVERY BILL ON THAT SERVICE.**

    CR-013 part 2 gives a code ONE basis, and both halves of the product enforce
    it: `services._validate_charge` refuses the save
    (`rating.charges.amount_and_size_table`), and — the half that costs money —
    `resolution.resolve_charge_codes` and `selectors.base_charge_from_charge_
    code` refuse **the BILL**, on billing day, for every account on that
    service. Not a wrong figure: a refused account.

    **This is not hypothetical and it is why the warning is at the top.** The
    brief for `DEF-6440` read *"seed `charge_code_amounts` so every size class of
    every service has a base amount … this is wrong TODAY on services that
    otherwise work"*. Followed literally, on the two services that DID work, it
    would have added a per-size table beside the flat `$8.00` on `BASE-W` and
    the flat `$12.00` on `BASE-E` and taken the whole demo utility's billing
    down — a table that reads as an obvious improvement, and an outage. The
    premise was also wrong: the empty table never billed `$0.00`, because the
    flat column was answering. `seed_sample_base_charge_codes` therefore omits
    `amount` entirely on a laddered code, and says so at the line that does it.

    **So the two are alternatives, not layers.** To move a code from flat to
    per-size, state the table and drop the scalar in the SAME write; to move it
    back, the reverse. `apps/rating/base_size_amounts.py` is the seeded ladder
    and carries the arithmetic.

    ⚠ **AND WHATEVER THE SMALLEST SIZE STATES SHOULD EQUAL WHAT THE PLAN
    STATES — BUT FOR A DISPLAY REASON FROM 2026-09-28, NOT A BILLING ONE
    (`DEF-BIL-7170`).** This read *"`gather._base_charge_for` REFUSES an
    account by name when the code and the plan disagree … A ladder whose first
    rung is not the plan's figure does not mis-bill; it stops the bill."* The
    PO retired the plan's figure that day — *"we will never take default value
    from plan $8.0 - that is retired"* — so a disagreement stops nothing. What
    it still does is put a figure on the plan's screen that no bill charges,
    because `plan_services.base_charge` is still written and still shown
    (`BR-RAT-120`).

    ⚠ **"EDITABLE" BECAME TRUE ON 2026-08-28 AND NOT BEFORE (`BR-RAT-690`,
    closing `DEF-2190`).** This class, its migration and four readers shipped on
    2026-08-21 with **no writer at any layer** — `rating.services.CHARGE_FIELDS`
    carried no `size_amounts` key, so `POST /charges` refused the field by name
    and only a test could put a row here. The sentence above described the
    design and the code did not implement it, which is hard-won law 1 exactly.
    `_validate_size_amounts` and `_write_size_amounts` are the writer; CHG-02
    step 2 is the screen.

    **This is where the base charge lives** (PO ruling 2026-08-20, closing B1
    and OQ-238 against two CONFIRMED rules). BR-RAT-080's test decides it: a base
    is charged because a connection EXISTS, so it is a THING, so it is a charge
    code. `tariff_versions.base_charge` and the plan's own base both stop being
    sources — §A3's *"one source, two surfaces"*: the rate matrix DISPLAYS this
    value, attributed (`$12.00 · from BASE-W`), and cannot edit it.

    **Why the failure this prevents is worth a table.** §A3 worked it: with a
    base on two objects, a 5/8" residential water account carrying `$12.00` in
    both is billed `$24.00` — **`$23,069.50` per month across 1,247
    connections** — *"and no test catches it, because both rows are individually
    correct and only the rule makes the total wrong."*

    `size_class` is `service_size_classes.code` as TEXT, not an FK, and that is
    deliberate: the engine already keys its size rows by the connection-size
    string, `service_size_classes` is a tenancy-framework lookup owned by metering
    (BR-TEN-031), and a cross-module FK is a reviewed interface (B2 §2) that
    this row does not need. A size Settings RETIRES must not vanish from a
    schedule that already priced it — CR-013's own reading of *"tie it
    correctly"* — and a text key is what makes that possible.

    ⚠ **IT IS `NUMERIC(18,4)`, AND THE PARAGRAPH THAT SAID OTHERWISE WAS TRUE
    FOR ONE DAY (`DEF-2280`, corrected 2026-08-28).** This block used to read
    *"`NUMERIC(18,6)` … and NOT four places … whether 'store 4' means this
    column or the input is **OQ-285, OPEN**"*. **OQ-285 CLOSED the next day** to
    `BR-RAT-089` — PO verbatim, *"you can stone in table 4 decimal places but
    deplay on screen is 2 decimal places"*, i.e. the COLUMN — and `BR-RAT-092`
    widened it to every finance field. Migration `rating.0013` narrowed this
    column on 2026-08-21 and left the paragraph behind, so the file stated both
    answers two lines apart: this block said six, and the field below it is
    `money_field()`, which is four. **Nothing was ever stored wrong** — every
    value `(18,4)` holds, `(18,6)` holds identically — but a money model that
    contradicts itself about its own precision is read by whoever gets to it
    first. The field is the truth; this is now the record of how it got there.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    charge = models.ForeignKey(
        "rating.Charge", on_delete=models.PROTECT, db_column="charge_id", related_name="amounts"
    )
    #: `service_size_classes.code` — see the class docstring for why it is text.
    #: (The LIST was renamed from `meter_size_classes` by BR-TEN-170 on
    #: 2026-08-27; the hosted TABLE still carries the old name — DEF-970.)
    size_class = models.TextField()
    #: NULL IS NOT ZERO. CR-013 part 1's *"blank base = size not served"*
    #: (DEF-277) reaches this column unchanged: a row that exists with a NULL
    #: amount says the utility does not serve this size, and R4 refuses rather
    #: than billing $0.00 for it. A stored 0.00 is a PRICE and bills zero.
    #:
    #: BR-RAT-092 / OQ-286 — an AMOUNT, so FOUR places, taken from the one place
    #: that rule lives. First adopter of `core.money_fields` because this table
    #: is EMPTY: narrowing costs nothing here and proves the path before the
    #: other 55 columns follow.
    amount = money_field(null=True, blank=True)
    #: ── THE SECOND NARROWING DIMENSION (CR-087 A1 / PRB-01, 2026-09-08) ─────
    #: `account_types.code`, as TEXT. Until this column existed a $45.00
    #: residential connection fee and an $85.00 commercial one were THE SAME
    #: ROW: the table was unique on (tenant, charge, size_class) and carried no
    #: customer class at all, so a utility could narrow WHO a code reached
    #: (`charges.applies_to_customer_classes`) and never WHAT each of them paid.
    #:
    #: ⚠ **WHY A CODE AND NOT A UUID.** `plan_deposit_rules` keys its class with
    #: `account_type_id`, so that precedent exists and this deliberately does not
    #: follow it. The resolver decides: `resolution.AccountFacts.customer_class`
    #: is a code string and `charges.applies_to_customer_classes` is a JSON list
    #: of code strings, and R4 narrows by comparing those two. A UUID here would
    #: make the row beside it on the same object narrow by a different key and
    #: force an id→code lookup on the hot path.
    #:
    #: ⚠ **NULL IS NOT A CLASS, IT IS EVERY CLASS** — the same reading
    #: `applies_to_customer_classes` already takes, and what makes this additive:
    #: every row written before this column keeps pricing exactly what it priced.
    #:
    #: ⚠ **AND A CLASS-SPECIFIC ROW WINS OVER THE EVERY-CLASS ROW.** That rule
    #: lives in `resolution_catalogue`, where the per-account catalogue is built;
    #: it is not expressible here, and a reader who assumes the database resolves
    #: it will write a second resolution somewhere else.
    customer_class = models.TextField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    #: ── DATED, AND NEVER DELETED (CR-156-BRC10, PO 2026-10-01) ──────────────
    #: PO verbatim: *"why are you detleting it and not killing it"*, then
    #: *"logical kill"*; and on the flat amount, *"A past bill reads the row in
    #: force on its dates."* A price row is in force on `effective_from ≤ day ≤
    #: effective_to` (`effective_to` NULL = no end). An edit never deletes a
    #: row: a changed or removed price is CLOSED — `effective_to` = the day
    #: before the new price starts — and stamped `killed_at`; the new price is a
    #: NEW row. **A killed row still prices its own dates** — that is the whole
    #: point: *"what was CART-64 on 09/01?"* is answered from this table.
    #:
    #: ⚠ **NO READER QUERIES THIS TABLE DIRECTLY.** `apps/rating/charge_prices.py`
    #: is the one lookup and the one writer, and gate `G<n>` (see
    #: `10-scripts/gates/`) fails any other `ChargeCodeAmount.objects`.
    #:
    #: The Python default is `PRICE_HISTORY_EPOCH`, the same date the backfill
    #: gave every row that existed before dates did: a row written with no stated
    #: start has always applied. The saving path never relies on it — `Effective
    #: from` is required on every Add and Edit that moves a price.
    effective_from = models.DateField(default=PRICE_HISTORY_EPOCH)
    effective_to = models.DateField(null=True, blank=True)
    #: The *killed* mark: set when a later edit closed this row. NULL = the row
    #: is the code's current statement for its (size, class). Never cleared.
    killed_at = models.DateTimeField(null=True, blank=True)
    #: ── A PENALTY'S TERMS PER CUSTOMER CLASS (DEF-RAT-8753, rating/0054) ────
    #: The PO-approved mock-up (images 31, 61, 67, 77) prices `LATE` by class:
    #: 1.50% with a $5.00 minimum for Residential, 2.00% with a $10.00 minimum
    #: for Commercial. `charges.percent` / `charges.min_amount` are ONE value
    #: per code, so the per-class terms live here, on *All sizes* rows that
    #: name a class — dated and logically killed exactly like an amount row.
    #: A row is EITHER an amount row (`amount`) OR a terms row (`percent`,
    #: `min_amount` NULL = no floor); `ck_charge_code_amounts_amount_or_terms`
    #: refuses both. `percent` is a FRACTION (0.015 = 1.50%), as on `charges`.
    #: Percentages store 6 places, money 4 (CLAUDE.md hard rule 2).
    percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    min_amount = money_field(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "charge_code_amounts"
        #: ⚠ **TWO CONSTRAINTS, AND ONE WOULD NOT WORK.** PostgreSQL treats
        #: NULLs as DISTINCT in a unique index, so a single constraint over
        #: (tenant, charge, size_class, customer_class) would let TWO every-class
        #: rows exist for one size — precisely the duplicate the old three-column
        #: key refused. The pair below is what actually refuses: one partial
        #: index for the named classes, one for the unnamed.
        #:
        #: ⚠ **AND BOTH ARE AMONG *LIVE* ROWS ONLY (CR-156-BRC10).** A killed
        #: row is kept, so uniqueness over every row would refuse the new price
        #: an edit writes beside the one it closed (decision log 2026-10-01,
        #: judgment (a)). The no-overlap guarantee across ALL rows — killed ones
        #: included, because they still price their dates — is the PostgreSQL
        #: exclusion constraint `ex_charge_code_amounts_no_overlap`
        #: (`rating/0052`), which Django cannot express and SQLite cannot hold.
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "charge", "size_class", "customer_class"],
                condition=models.Q(customer_class__isnull=False, killed_at__isnull=True),
                name="uq_charge_code_amounts_size_and_class",
            ),
            models.UniqueConstraint(
                fields=["tenant", "charge", "size_class"],
                condition=models.Q(customer_class__isnull=True, killed_at__isnull=True),
                name="uq_charge_code_amounts_tenant_charge_size",
            ),
            #: A window may end at most ONE day before it starts — the EMPTY
            #: range the writer leaves when a price is superseded before it
            #: began. Anything earlier would make `daterange` raise inside the
            #: exclusion constraint instead of refusing by name (`rating/0052`).
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from") - _ONE_DAY),
                name="ck_charge_code_amounts_window",
            ),
            #: DEF-RAT-8753 — an amount row or a terms row, never both.
            models.CheckConstraint(
                condition=Q(percent__isnull=True) | Q(amount__isnull=True),
                name="ck_charge_code_amounts_amount_or_terms",
            ),
        ]


class RateSizeRow(models.Model):
    """DEF-360 · the SCHEDULE's half of the size axis — minimum bill per size.

    r10's rate matrix is `size · base · min · t1 · t2 · t3`, and **three** of
    those vary by size, not one. The base is the charge code's (above). The
    minimum bill and the tier rates are the schedule's own usage math, and
    neither had a size dimension: `tariff_versions.minimum_bill` was a scalar
    and `rate_tiers` had no size at all.

    **The 2" water row is what settles it.** Every other size prices tiers at
    `3.20 / 4.80 / 7.20`; 2" prices them at `3.45 / 5.10 / 7.70`. A per-size tier
    cannot be derived from a base, a multiplier, or anything else — it can only
    come from a row on the schedule, which is why the schedule needs this axis
    for reasons that have nothing to do with the base.

    ⚠ **§B3's own table list omitted this.** It planned `charge_code_amounts`
    and *"+minimum bill per size"* and said nothing about tier rates, so building
    §B3 exactly as written still could not price the 2" row. §B3 is corrected in
    the same commit as this model (DEF-360).

    A schedule with no rows here prices every size the same way it always has —
    `tariff_versions.minimum_bill` remains the fallback — so this table is
    additive and no existing schedule changes behaviour by its arrival.

    ⚠ **SUPERSEDED 2026-10-01 — THIS TABLE IS NOW THE ONLY MINIMUM BILLING
    READS, AND THERE IS NO FALLBACK** (`DEF-RAT-8737`, PO option A: *"A ·
    Minimum per size - this is correct"*). The paragraph above was true when
    written and is kept so a reader grepping it learns what happened:
    `tariff_versions.minimum_bill` is no longer billed, `rating/0053` moved
    every stated figure onto its version's rows that had none, and
    `selectors._size_minimum` publishes this row's `minimum_bill` for the
    connection's size — a size with no row, or a row with no figure, is not
    topped up.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.ForeignKey(
        "rating.TariffVersion",
        on_delete=models.PROTECT,
        db_column="tariff_version_id",
        related_name="size_rows",
    )
    size_class = models.TextField()
    #: NULL = this size has no minimum bill (electric draws an em-dash for every
    #: size in r10's matrix). Absent is not zero, here as everywhere in this CR.
    minimum_bill = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rate_size_rows"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "tariff_version", "size_class"],
                name="uq_rate_size_rows_tenant_version_size",
            )
        ]


class RateSeason(models.Model):
    """Seasonal price-set windows inside a schedule (r5 #2, D3; BR-RAT-034
    coverage validation is the wizard/service's law)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.ForeignKey(
        TariffVersion, on_delete=models.PROTECT, db_column="tariff_version_id"
    )
    label = models.TextField()  # 'Summer' / 'Winter'
    start_month = models.IntegerField()
    start_day = models.IntegerField()
    end_month = models.IntegerField()
    end_day = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rate_seasons"


class RateTier(models.Model):
    """Inclining-block rows (B2 `rate_tiers`; flat = single 0→∞ row per
    BR-RAT-032). r6.7 adds season_id for seasonal tier sets — the base UNIQUE
    (tariff_version, seq) is kept VERBATIM; the season/seq collision is
    reported, not resolved (module docstring)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.ForeignKey(
        TariffVersion, on_delete=models.PROTECT, db_column="tariff_version_id"
    )
    season = models.ForeignKey(  # r6.7 (seasonal tier sets)
        RateSeason, on_delete=models.PROTECT, null=True, blank=True, db_column="season_id"
    )
    #: DEF-360 · the third per-size column of r10's rate matrix.
    #:
    #: **NULL means "every size", and that is the common case** — Residential
    #: Water prices 5/8", 3/4", 1" and 1.5" at the same `3.20 / 4.80 / 7.20`.
    #: Only 2" differs (`3.45 / 5.10 / 7.70`), and a per-size tier cannot be
    #: derived from a base or a multiplier: it can only come from a row here.
    #:
    #: Nullable is what makes this additive — every tier written before this
    #: column existed reads as "every size" and prices exactly as it did.
    #: Resolution reads the size-specific set when one exists and falls back to
    #: the NULL set otherwise, so a schedule states the exception, not the rule.
    size_class = models.TextField(null=True, blank=True)
    seq = models.IntegerField()
    from_qty = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    to_qty = models.DecimalField(  # null = ∞ (only the last tier — BR-RAT-032)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rate_tiers"
        constraints = [
            models.UniqueConstraint(
                fields=["tariff_version", "seq"], name="uq_rate_tiers_version_seq"
            ),
        ]


#: METERING's TOU register vocabulary (B2 r8 / BR-MET-059). A meter on a
#: time-of-use tariff reports one number per register per period; these are the
#: only three names a `meter_reads` row can carry, so they are the only three a
#: window may point at. Defined once, here, beside the column that stores it.
TOU_CHANNELS: tuple[str, ...] = ("tou_on", "tou_mid", "tou_off")


class TimeOfUseWindow(models.Model):
    """TOU Option B window rows (B2 + r5 #17: season_id + day_type; BR-RAT-021/
    033 — coverage validation is the wizard/service's law).

    `channel` IS THE JOIN BETWEEN A PRICE AND A MEASUREMENT, and it exists
    because the PO ruled on 2026-08-16 that the utility states it: *"make the
    rate wizard say which register is which"* (OQ-236 → BR-RAT-067).

    Before this column a window carried only a LABEL the tenant typed — "On-peak",
    "Peak", "Punta" — and a measurement carried only metering's CHANNEL, with no
    column on either side naming the other; rating matched them by PRICE RANK
    (BR-RAT-064, now SUPERSEDED and deleted from the tree). That was a defensible
    reading of a signed rule and it still decided a customer's bill: the demo
    tenant's own summer schedule bills **88.60** joined correctly and **122.40**
    joined the wrong way round — a 38% overcharge on a document that looks
    perfectly ordinary.

    NULL is a REFUSAL, never a default. Windows configured before 2026-08-16
    carry NULL and the engine refuses them BY NAME (BR-RAT-067 clause 1) rather
    than ranking silently or pricing the window at 0.00. Migration 0005 does not
    backfill them, deliberately — see its docstring.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.ForeignKey(
        TariffVersion, on_delete=models.PROTECT, db_column="tariff_version_id"
    )
    season = models.ForeignKey(
        RateSeason, on_delete=models.PROTECT, null=True, blank=True, db_column="season_id"
    )
    label = models.TextField()  # On-peak / Mid-peak / Off-peak / All day
    day_type = models.TextField(default="weekday")  # weekday | weekend | holiday (r5 #17)
    start_time = models.TimeField()  # may wrap midnight (BR-RAT-033)
    end_time = models.TimeField()
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    # BR-RAT-067: which metered register this window's quantity is measured on.
    # NULLABLE only so rows written before 2026-08-16 remain readable; every
    # write path since requires it and the engine refuses without it.
    channel = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "time_of_use_windows"
        constraints = [
            # The DB is the last line, not the only one: services._validate_tou
            # rejects an unknown channel with a field error the wizard renders.
            # This constraint is what stops a shell, a fixture or a future
            # importer from storing "onpeak" and having it refuse at RUN time
            # instead of at write time.
            models.CheckConstraint(
                condition=models.Q(channel__isnull=True) | models.Q(channel__in=TOU_CHANNELS),
                name="ck_time_of_use_windows_channel",
            ),
        ]


class CapacityRate(models.Model):
    """Capacity model: tenant-defined unit label + rate (r5 #4; BR-RAT-018/
    019/022 — GT-15 consumer)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.ForeignKey(
        TariffVersion, on_delete=models.PROTECT, db_column="tariff_version_id"
    )
    unit_label = models.TextField()  # TENANT-DEFINED ('panel', 'kW block' — BR-RAT-022)
    rate_per_unit = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "capacity_rates"


class DemandRateConfig(models.Model):
    """Demand structure capture (r6.2; BR-RAT-014 — engine treats demand qty as
    an input; PF-penalty fields are capture-only until the B4 demand addendum
    ratifies, US-RAT-007 §5)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tariff_version = models.OneToOneField(
        TariffVersion, on_delete=models.PROTECT, db_column="tariff_version_id"
    )
    energy_rate_per_kwh = models.DecimalField(max_digits=18, decimal_places=6)
    demand_rate_per_kw = models.DecimalField(max_digits=18, decimal_places=6)
    peak_window_label = models.TextField(null=True, blank=True)  # '15-min monthly'
    peak_window_start = models.TimeField(null=True, blank=True)
    peak_window_end = models.TimeField(null=True, blank=True)
    ratchet_enabled = models.BooleanField(default=False)  # r6.2 DEFAULT false
    ratchet_pct = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    pf_penalty_enabled = models.BooleanField(default=False)  # capture-only (BR-RAT-014)
    pf_penalty_rate_per_kw = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "demand_rate_config"


class ChargeQuerySet(models.QuerySet):
    """`Charge.objects` — one routing on top of Django's queryset.

    ⚠ **`.update(amount=x)` IS ROUTED TO THE PRICE TABLE (CR-156-BRC10).** The
    column is `legacy_amount` now, so a bulk `update(amount=…)` would raise
    `FieldError`; it is instead handed, code by code, to the same door
    `Charge.amount = x; save()` uses (`charge_prices.write_flat_amount_
    directly` — the flat every-class price from `PRICE_HISTORY_EPOCH`). Seeds
    and tests build catalogues this way; a clerk's edit never does
    (`services.update_charge` states its own dates). The column itself is never
    written."""

    def update(self, **kwargs: Any) -> int:
        if "amount" not in kwargs:
            return super().update(**kwargs)
        amount = kwargs.pop("amount")
        from apps.rating import charge_prices

        rows = list(self)
        for row in rows:
            charge_prices.write_flat_amount_directly(row, amount)
        if kwargs:
            return super().update(**kwargs)
        return len(rows)

    def delete(self) -> Any:
        """Deleting a CODE takes its price rows with it, exactly as
        `services.delete_charge` does through `charge_prices.remove_all`.

        Before CR-156-BRC10 a flat amount was a column ON the code and went
        with it; it is a row in `charge_code_amounts` now, whose PROTECT
        foreign key would otherwise refuse every delete of a flat-priced code
        that worked the day before. This is a code being removed, never an
        edit — an edit still never deletes a price row (`save_prices`). The
        guards on deleting a code that was USED (BR-RAT-035) live in
        `services.delete_charge` and are unchanged."""
        ids = list(self.values_list("id", flat=True))
        if ids:
            ChargeCodeAmount.objects.filter(charge_id__in=ids).delete()
        return super().delete()

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> Any:
        """`bulk_create` skips `save()`, so a pending flat amount set through
        `Charge(amount=…)` would be dropped silently — it is routed here
        instead, after the rows exist, exactly as `save()` routes it."""
        objs = list(objs)
        created = super().bulk_create(objs, *args, **kwargs)
        pending = [obj for obj in objs if getattr(obj, "_pending_flat_set", False)]
        if pending:
            from apps.rating import charge_prices

            for obj in pending:
                amount = obj._pending_flat_amount
                obj._pending_flat_set = False
                obj._pending_flat_amount = None
                charge_prices.write_flat_amount_directly(obj, amount)
        return created


class Charge(models.Model):
    """Tenant charge-code catalog (B2 `charges` + r6.6 completion; BR-RAT-035).
    Amounts are seeds, never constants (B4 §NSF)."""

    objects = ChargeQuerySet.as_manager()

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    charge_type = models.TextField(null=True, blank=True)  # r6.6 one_time|recurring|penalty
    #   (S12 additionally offers 'refundable' — value set is lookup-bound, BR-TEN-036 direction)
    service = models.ForeignKey(  # r6.6 scope: NULL = any service
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    amount_rule = models.TextField(null=True, blank=True)  # r6.6: flat | percent |
    #   percent_with_minimum | formula (reserved value — visible-but-disabled, BR-RAT-041)
    #: ── `charges.amount` IS RETIRED AS A STORE (CR-156-BRC10, PO 2026-10-01) ──
    #: PO verbatim, option A: *"The old field on the charge code is no longer
    #: written; today's values move into rows once."* The column is KEPT (no
    #: data is destroyed, and `rating/0051` moved every value into an *All
    #: sizes* row of `charge_code_amounts` and cleared it) and is renamed in
    #: Python so that nothing can read it by accident: `charge.amount` is now
    #: the property below, which REFUSES a read loudly and routes a write to the
    #: price table. `legacy_amount` is read by exactly two places — the
    #: migration that moved it and `charge_prices` — and gate `G<n>` fails any
    #: third.
    legacy_amount = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True, db_column="amount"
    )
    percent = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    min_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)  # r6.6
    gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger_accounts
    #   (W5; B11 F-3 names charges→ledger_accounts in the deferred-FK pass)
    #: BR-RAT-088 · §A3 — this code IS its service's base charge.
    #:
    #: **Declared, never inferred from the code string.** The engine needs to
    #: know which of a plan's charge codes is the base so R4 can resolve it, and
    #: the tempting shortcut is to match `BASE-<service>` by name. That is a
    #: hard-coded vocabulary (B12 §No hard-coded values): it breaks the moment a
    #: tenant names theirs `SERVICE-CHG`, and it breaks silently — the bill is
    #: produced, just without a base.
    #:
    #: It also gives §A3's activation gate its input: *"activating a rate
    #: schedule whose service has no active base charge code — where the plan
    #: expects one — is refused, naming the service."*
    #:
    #: Default False, so every existing row is unchanged and a tenant declares
    #: its base explicitly. Nothing is guessed on migration.
    #: ── WHICH CUSTOMERS THIS CODE PRICES (BR-RAT-108, PO ruling 2026-08-21) ──
    #: The PO asked how ONE base charge is derived from many: *"based on Asset
    #: and Account type you will have select 1 base charge out of so many
    #: charges … then you need to derive which base rate to select."* Three
    #: dimensions narrow it — SERVICE (`service_id`), METER SIZE
    #: (`ChargeCodeAmount.size_class`) and ACCOUNT TYPE. The first two existed;
    #: this is the third, and without it Silver Creek's own data cannot be
    #: expressed: water base is **$8.00 residential** and **$15.00 commercial**,
    #: one service and two amounts, where a charge code is per TENANT.
    #:
    #: `resolution.ChargeCode.customer_classes` has expected this since R4 was
    #: written and had no column behind it (DEF-483) — the rule read as
    #: implementable because the ENGINE could express it and the TABLE could not.
    #:
    #: Same shape as `Tax.applies_to_customer_classes` deliberately: a JSON list
    #: of PLATFORM `account_types.code` values, and **NULL or `[]` means EVERY
    #: CLASS**. An INCLUSION list rather than an exclusion one, for DEF-273's
    #: reason — it fails safe, because a class nobody listed is simply not in it,
    #: where an exclusion list silently widens every time a tenant adds a class.
    #:
    #: ⚠ **THIS DOES NOT MAKE TWO MATCHING BASE CODES LEGAL.** It makes them
    #: SEPARABLE. `resolve_base_charge` refuses when two survive the narrowing
    #: (DEF-468) — before this column, the only way to have two base codes for
    #: one service was ambiguity; now it is how a utility prices two classes.
    applies_to_customer_classes = models.JSONField(null=True, blank=True)
    is_base = models.BooleanField(default=False)
    #: ── KIND (CR-156-BRC10, PO 2026-10-01) ─────────────────────────────────
    #: *"can we have 3 kinds base charges, plan charges and others , we will
    #: have them from setting - so in setting we will not make any change we
    #: will make changes we we configure them in charge codes"*. `base` | `plan`
    #: | `other` (`constants.KINDS`). NULL = a code minted on Settings and not
    #: yet configured here — Settings is unchanged by the ruling, so its card
    #: writes no kind. `base` agrees with `is_base` (the declared flag stays the
    #: billing truth, BR-RAT-088); `services._validate_charge` keeps the two in
    #: step.
    kind = models.TextField(null=True, blank=True, choices=[(k, k) for k in KINDS])
    taxable_default = models.BooleanField(default=False)  # r6.6; B4.2 bound (fees never taxed)
    auto_apply = models.BooleanField(default=False)  # r6.6
    waivable = models.BooleanField(default=False)  # r6.6 (staff-waivable, S12)
    separate_line = models.BooleanField(default=False)  # r6.6
    #: 🔒 HUMAN-REVIEW-PENDING (❄️ B4/B5 late fee, finance RE-SIGN owed) — PO
    #: ruling 2026-10-06 11 (a): *"Put grace on the late-fee code. When Type is
    #: Penalty, the form asks Grace days (default 5) and Calendar / Business
    #: days, and billing uses the code's grace."* Read only for a PENALTY code;
    #: NULL = the tenant's Billing-defaults grace (`tenant_settings
    #: .late_grace_days/mode`), which is also what `rating/0066` seeded every
    #: existing penalty code with, so no late-fee date moved on deploy. The
    #: arithmetic is unchanged (BR-BIL-008 0–30, BR-BIL-002 modes, GT-8).
    grace_days = models.IntegerField(null=True, blank=True)
    grace_mode = models.TextField(null=True, blank=True)  # calendar | business
    #: 🔒 PO rulings 2026-10-06 (`DEF-CUS-9819`) — THE UTILITY'S APPLICATION
    #: FEE. At most ONE live code per tenant carries it (partial unique index
    #: below), and only a ONE-TIME code may (`services._validate_charge`).
    #: Every new service request — staff capture, the counter, a portal Start
    #: service application — gets this code's line at its live price
    #: (`customers.service_request_service.add_application_fee_line`). A utility
    #: that charges nothing prices the code at $0.00 (PO: *"we wil ahve
    #: application fees as zero and pprovide option to waive off"*).
    is_application_fee = models.BooleanField(default=False)
    #: 🔒 HUMAN-REVIEW-PENDING · `DEF-PAY-10698` (PO 2026-10-30, *"Do not
    #: hardcode check NSF Account> Unit> Plan> Charge code"*) — THIS CODE IS A
    #: RETURNED-PAYMENT (NSF) FEE. A bounce charges the code of this kind that
    #: the account's PLAN lists (`selectors.plan_nsf_charge`), priced like any
    #: other code. DECLARED, never inferred from the code string — the reason
    #: `is_base` gives (a utility may call its code `RET-CHK`). Not unique per
    #: tenant: two plans may list two NSF codes at two prices; one plan listing
    #: two is refused at the bounce as ambiguous, never resolved by order.
    is_nsf_fee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "charges"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_charges_tenant_code"),
            models.CheckConstraint(
                condition=Q(grace_days__isnull=True)
                | Q(grace_days__gte=0, grace_days__lte=30),
                name="ck_charges_grace_days_range",
            ),
            models.CheckConstraint(
                condition=Q(grace_mode__isnull=True) | Q(grace_mode__in=("calendar", "business")),
                name="ck_charges_grace_mode",
            ),
            # DEF-CUS-9819 — ONE application fee per utility among live codes.
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(is_application_fee=True, deleted_at__isnull=True),
                name="ux_charges_one_application_fee",
            ),
        ]

    # ── THE RETIRED `amount` ATTRIBUTE (CR-156-BRC10) ──────────────────────
    #: A flat amount handed to the constructor or assigned before `save()`,
    #: waiting to become an *All sizes* row. Never persisted on this row.
    _pending_flat_amount: Any = None
    _pending_flat_set: bool = False

    @property
    def amount(self) -> Any:
        """REFUSED — the flat amount lives in `charge_code_amounts` now.

        Raises rather than answering `None`, because a `None` here reads as
        *"this code states no amount"* and a reader that missed the move would
        refuse a bill (or quote nothing) on a code that is priced. Read
        `charge_prices.flat_amount(charge, on_date)` instead.

        ⚠ Deliberately NOT an `AttributeError`: `getattr(charge, "amount",
        None)` would swallow it and answer `None` silently, which is exactly
        the failure this exists to make loud.
        """
        raise RetiredChargeAmount(
            "charges.amount is no longer read (CR-156-BRC10). A flat amount is an "
            "'All sizes' row in charge_code_amounts, dated; read it through "
            "apps.rating.charge_prices.flat_amount(charge, on_date)."
        )

    @amount.setter
    def amount(self, value: Any) -> None:
        """A write is ROUTED, never stored: `save()` hands it to the price
        writer as the code's flat amount from `PRICE_HISTORY_EPOCH` — the
        meaning a direct catalogue write has always had (*this is the price*).
        The saving path for a clerk (`services.update_charge`) never comes here;
        it states its own dates. This door exists for seeds and tests that
        build a catalogue row in one call."""
        self._pending_flat_amount = value
        self._pending_flat_set = True

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """The instance form of `ChargeQuerySet.delete` — the code's price
        rows go with the code (see there)."""
        if self.pk is not None:
            ChargeCodeAmount.objects.filter(charge_id=self.pk).delete()
        return super().delete(*args, **kwargs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `save(update_fields=["amount", …])` names the retired attribute: it
        # is routed below, never written, so it leaves the column list (and a
        # list that was ONLY `amount` writes no column at all).
        fields = kwargs.get("update_fields")
        if fields is not None and "amount" in fields:
            rest = [field for field in fields if field != "amount"]
            if not rest:
                if self._pending_flat_set:
                    pending = self._pending_flat_amount
                    self._pending_flat_set = False
                    self._pending_flat_amount = None
                    from apps.rating import charge_prices

                    charge_prices.write_flat_amount_directly(self, pending)
                return
            kwargs["update_fields"] = rest
        super().save(*args, **kwargs)
        if self._pending_flat_set:
            pending = self._pending_flat_amount
            self._pending_flat_set = False
            self._pending_flat_amount = None
            from apps.rating import charge_prices

            charge_prices.write_flat_amount_directly(self, pending)


class RetiredChargeAmount(RuntimeError):
    """`charges.amount` was read after `CR-156-BRC10` retired it as a store."""


class TaxJurisdiction(models.Model):
    """TENANT-scoped jurisdiction registry (r6.5 / r16 #2 — supersedes the B2
    §1 platform-global note; BR-TEN-037: tenant-entered, RLS FORCE)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()
    authority = models.TextField(null=True, blank=True)  # US-RAT-009 §5
    level = models.TextField(null=True, blank=True)  # federal|state|county|city|special_district
    reference_no = models.TextField(null=True, blank=True)  # permit / reference #
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tax_jurisdictions"


class TaxAuthorityAccount(models.Model):
    """🔒 THE ACCOUNTS THIS UTILITY HOLDS WITH ITS TAX AUTHORITIES — the list
    *Settings › Accounting › Authority accounts* (CR-165-BRC10 §7 item 1).

    PO 2026-10-02, verbatim (decision log *"GO ON THE TAXES & FEES REDESIGN"*):
    *"Due and Your account - It should be drop down - Your account can come from
    settings we ahve configure accounts sections"*. No such list existed — the
    number the authority knows the utility by was typed again on every tax as
    free text (`taxes.remit_reference`), so a typo on one of three State taxes
    (`32-1180544` for `32-1180455`) filed one return under the wrong account with
    nothing flagging it. Typed once here, picked on every tax.

    ⚠ **NOT A GL ACCOUNT.** `taxes.liability_gl_account_id` is the utility's own
    ledger account the collected tax sits in (CR-008: edited only in Settings ›
    Accounting). This is the utility's account number WITH THE AUTHORITY — a
    filing fact, not a posting one — and nothing in the ledger reads it.

    `jurisdiction` is OPTIONAL: an authority account may be recorded before any
    tax names that authority, and the wizard filters by it only where it is
    stated. `active=False` hides a row from the picker and never breaks a tax
    that already points at it (PROTECT on the tax side; nothing is deleted).

    Rating owns it because rating owns `tax_jurisdictions` and `taxes`, the only
    two tables it describes; the screen that edits it lives in Settings ›
    Accounting. Tenant-scoped, RLS `FORCE` (`rating/0056`). **Nothing seeds it**
    — the PO's instruction was a list the utility configures.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    authority_name = models.TextField()
    account_number = models.TextField()
    jurisdiction = models.ForeignKey(
        TaxJurisdiction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="jurisdiction_id",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tax_authority_accounts"
        constraints = [
            # One row per (authority, number) per tenant, case-insensitively —
            # the same number typed twice under one authority is the duplicate
            # this list exists to stop.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("authority_name"),
                Lower("account_number"),
                name="uq_tax_authority_accounts_tenant_name_number_ci",
            ),
        ]


class Tax(models.Model):
    """Tax/fee config (B2 `taxes` + r6.5 completion; BR-RAT-036/042). The
    percent form's rate lives on base `rate` (r6.5's duplicate `percent`
    column NOT added — reported, module docstring)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    jurisdiction = models.ForeignKey(
        TaxJurisdiction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="jurisdiction_id",
    )
    name = models.TextField()
    kind = models.TextField(null=True, blank=True)  # r6.5: percent | flat | per_unit
    rate = models.DecimalField(  # percent form, fraction (0.0625); B4.2 base rules
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    base_includes_usage = models.BooleanField(default=True)  # US-RAT-009 §5 PROPOSED-SCHEMA;
    base_includes_base = models.BooleanField(default=True)  # fees/tax-on-tax NOT representable
    flat_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    flat_frequency = models.TextField(null=True, blank=True)  # r6.5: per_bill | per_service
    per_unit_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    per_unit_uom = models.TextField(null=True, blank=True)  # explicit unit (CLAUDE.md #3)
    #: ── THE FOURTH COMPUTATION FORM (BR-RAT-036 as amended, DEF-386) ─────────
    #: CR-013 part 4 names FOUR forms and BR-RAT-036 ratified THREE, so a rate
    #: charged PER METER — the shape a state regulatory fee usually takes — had
    #: nowhere to live and billed nothing. A `$1.25` per-meter fee on a duplex
    #: with two meters is `$2.50`, and until this column existed it was `$0.00`.
    #:
    #: **It is NOT `per_unit` with a different unit.** `per_unit_amount` prices
    #: BILLED USAGE — a quantity that varies with consumption and carries a UoM
    #: (hard rule 3). This prices a COUNT OF ASSETS, which has no UoM because a
    #: meter is not a measure of anything; it is the same distinction BR-RAT-090
    #: draws for an unmetered service's cart count. Storing one as the other
    #: would multiply a fee by kilowatt-hours.
    #:
    #: PO ruling 2026-08-21, option C, verbatim: *"Per-meter now (it's a small
    #: change), stacking later — because that one needs care to avoid a tax that
    #: taxes itself in a circle."* The stacking half is DEF-381, deferred with
    #: its reason; nothing here compounds.
    per_meter_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    applies_above_units = models.DecimalField(  # r6.5 MARGINAL threshold (BR-RAT-042, OQ-054)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    applies_to_services = models.JSONField(  # r6.5 services[] — JSON list of catalog codes
        null=True, blank=True  # (array type is an Eng disposition; reported)
    )
    #: ── THE TWO QUALIFIERS THE RULED TEXAS RATES NEED (DEF-273, 2026-08-18) ──
    #: Until today `taxes` carried exactly two qualifiers — `applies_to_services`
    #: and `applies_above_units` — so r10's own tax table could not be seeded:
    #: *"Commercial + Industrial ONLY — residential exempt"* and *"Inside city
    #: limits"* had nowhere to live. Seeding the State Utility Tax without the
    #: first would have charged **6.25 % to every residential customer r10
    #: exempts**; seeding the City Franchise Fee without the second would have
    #: charged **1.50 % to the 61 outside-city accounts r10 exempts**. Both are
    #: the failure CLAUDE.md hard rule 2 exists to prevent, so the model gained
    #: the columns before anything was seeded (PO ruling 2026-08-18, DEF-254/273).
    #:
    #: `applies_to_customer_classes` — JSON list of PLATFORM `account_types.code`
    #: values (residential | commercial | industrial | government), the SAME
    #: array-type disposition `applies_to_services` already takes. NULL or []
    #: means EVERY class, which is what r10 draws for Bexar County (*"Customer
    #: class · All · No residential exemption at county level"*). It is an
    #: INCLUSION list rather than an exemption list because that is the form
    #: r10's own column takes (*"Comm, Industrial only"*), and because an
    #: inclusion list fails safe: an unrecognised class is simply not in it.
    #:
    #: ⚠ **THIS IS A SCOPE, NOT CR-013 PART 4's EXEMPTION OBJECT, AND THE TWO
    #: MUST NOT BE CONFLATED.** Part 4 (2026-08-18) specifies exemptions as
    #: *"categories with certificate requirements"* with a detail tab of
    #: *"Exemptions (categories, accounts holding each, certificate expiry)"* —
    #: an ACCOUNT-side object with a certificate and an expiry date, which no
    #: array on this row can carry. What this column expresses is r10's
    #: *applicability* column (*"Comm, Industrial only"*), which is a statement
    #: about who the rate reaches at all, not about a customer who holds a
    #: certificate. The exemption-category table is NOT built here and is named
    #: in the lane's write-back so it becomes a story rather than a surprise.
    applies_to_customer_classes = models.JSONField(null=True, blank=True)
    #: `premises_scope_kind` / `premises_scope_value` — the premises GEOGRAPHY a
    #: tax is confined to. **THE VOCABULARY IS THE PO'S OWN**, from CR-013 part 4
    #: (2026-08-18, `TAXES-FEES-BUSINESS-SPEC.md`, TAX-02 step 1 verbatim): *"how
    #: the system decides a premise is in scope (city limits, county, state,
    #: taxing district, explicit premise list)"* — five mechanisms, and the same
    #: spec adds *"Overlapping jurisdictions expected — each attaches
    #: independently"*, so nothing here resolves a winner between two scopes: a
    #: premises inside a city AND inside a county attracts both taxes.
    #:
    #: r10 states the mechanism in its own words on the tax detail drawer —
    #: *"Inside Bexar County — Premise flag selects it at billing time"* — and
    #: CR-013 part 4 repeats it downstream (*"premise city-limit flags drive
    #: attachment and are audit-logged on the premise"*). THAT FLAG DOES NOT
    #: EXIST YET: `premises` carries `city`, `state` and `postal_code` and no
    #: `inside_city_limits` column, and `premises` belongs to metering. So
    #: `city_limits` resolves off the flag WHEN IT ARRIVES and off the recorded
    #: city name until then, and the other four mechanisms resolve only where the
    #: premises record can answer them.
    #:
    #: NULL kind = the tax applies everywhere in the tenant. A kind whose fact
    #: this premises cannot answer — no value typed, no column to read, an
    #: explicit premise list that does not exist yet — means the tax DOES NOT
    #: APPLY (hard-won law 3 — defaults fail closed). Under-charging is
    #: recoverable; over-charging a real customer is a refund and a support call.
    premises_scope_kind = models.TextField(null=True, blank=True)
    premises_scope_value = models.TextField(null=True, blank=True)
    #: ── THE FIELDS TAX-02 IS SPECIFIED TO COLLECT AND HAD NOWHERE TO PUT ────
    #: DEF-385 (2026-08-21). CR-013 part 4 step 1 asks for *"code, bill label,
    #: tax type, authority"*, step 2 for *"rounding matched to the authority's
    #: rule"* and step 3 for *"filing frequency and due-date rule, method and
    #: payment reference, mandatory liability GL, collection allowance with its
    #: own GL, interest/penalty accrual, and who gets the filing reminder"*.
    #: `taxes` carried the authority (through `jurisdiction`), the liability GL,
    #: `remit_to`, `filing_frequency` and `filing_form` — and nothing else on
    #: that list, so TAX-02 rendered eight named absences where controls belong.
    #:
    #: ⚠ **THE COLLECTION ALLOWANCE IS THE ONE THAT COSTS MONEY.** A utility
    #: that keeps `0.5%` of what it remits and cannot record it under-reports
    #: its own income: on `$2,400.00` of sales tax collected in a quarter the
    #: allowance is **`$12.00`** the utility is entitled to keep, and with no
    #: column it was remitted away silently.
    #:
    #: ⚠ **AND THE REMITTANCE WORKSHEET THAT CONSUMES THEM IS STILL UNBUILT.**
    #: DEF-385's own suggested fix says to add the columns *with* the worksheet
    #: — *"a field with no reader is the other half of this same defect"*. What
    #: ships here is the WRITER and the READ-BACK (TAX-02 collects each field and
    #: `tax_row` serves it), so a utility can record what its authority requires
    #: and see it again; the Finance worksheet that files a return against them
    #: is named in the lane's write-back and is NOT pretended to exist.
    #:
    #: `code` — the tenant's own short identifier, r10's first landing column.
    #: Unique per tenant **where stated**, so the rows that predate this column
    #: are untouched and a tenant adopts codes at its own pace.
    code = models.TextField(null=True, blank=True)
    #: `bill_label` — what a CUSTOMER reads on the bill, which is not always the
    #: name staff know the tax by. NULL means "use `name`"; nothing is copied on
    #: migration, because a copied default cannot later be told from a choice.
    bill_label = models.TextField(null=True, blank=True)
    #: `tax_type` — the CLASSIFICATION (sales tax, franchise fee, regulatory
    #: fee, utility tax, environmental fee, other). **NOT `kind`**, which is the
    #: COMPUTATION form (percent / flat / per unit / per meter) and is r10's
    #: *Basis* column. Two different questions that read alike: a franchise fee
    #: and a sales tax are both `percent`, and an authority's filing rules
    #: follow the type, never the arithmetic.
    tax_type = models.TextField(null=True, blank=True)
    #: ── ROUNDING: STORED, AND DELIBERATELY NOT YET HONOURED (OQ-309) ────────
    #: Part 4 step 2: *"rounding matched to the authority's rule"*. B4's money
    #: rounding is ❄️ FROZEN and finance-signed, and the engine rounds every tax
    #: line by it. A column that silently overrode a frozen rule would move
    #: signed figures without a re-sign, so this stores the authority's stated
    #: rule and **the engine does not read it**: `NULL` means "B4's rule", which
    #: is what every row carries and what every bill has always used.
    #: **Worked, so the size of the open question is visible:** a taxable base
    #: of `$99.20` at `6.25%` is `$6.2000000` and every rule agrees on `$6.20`;
    #: a base of `$99.28` is `$6.2050000`, where B4's HALF-UP gives **`$6.21`**
    #: and an authority mandating round-half-EVEN gives **`$6.20`** — one cent
    #: per bill per authority, in the direction a regulator audits. Whether a
    #: per-authority rule may override a frozen B4 figure is a FINANCE question
    #: and is `OQ-309`, not this lane's to choose.
    rounding_rule = models.TextField(null=True, blank=True)
    #: ── DISCOUNT TREATMENT — STATUTORY, PER AUTHORITY (DEF-382) ─────────────
    #: Part 4 step 2, verbatim: *"discount treatment — before or after
    #: discounts, stated per tax because it's statutory"*. It was noticed twice
    #: in docstrings (`discounts.py`, `discount_services.py`, both naming
    #: `taxes.discount_treatment` as EP-RAT-13's unbuilt column) and never
    #: became a row anybody tracked — hard-won law 1, a comment is a note and
    #: never a plan.
    #:
    #: `before` (the default, and today's behaviour to the digit) means the
    #: discount lands BEFORE the tax, so the authority levies on the reduced
    #: subtotal. `after` means the authority levies on the full tariff amount
    #: and the discount never reaches the tax base.
    #: **Worked, and this is the figure DEF-382 protects:** a `$1.00` PAPERLESS
    #: credit on a Bexar County bill leaves the county's line at **`$3.78`**
    #: under `before` and at **`$3.80`** under `after` — the pair
    #: `apps/rating/resolution.py` already carries in its own docstring, which
    #: until now was one authority's rule applied to every authority.
    #:
    #: ⚠ **THE DEFAULT IS `after` SINCE 2026-08-27, BY PO RULING (DEF-652).**
    #: It read `default="before"` from 2026-08-21 to 2026-08-28, chosen then so
    #: that no existing figure moved. That was the right call on the day the
    #: column landed and it is the wrong call now, because the PO has since
    #: answered the question the default was standing in for. Verbatim: *"Does
    #: a discount come off before or after tax? Tax the full amount before
    #: discount — The utility remits tax on the full service value; the
    #: discount is the utility's cost, not the tax authority's. - what does the
    #: tax law in the US say - lets go with it"*, confirming an earlier *"this
    #: is correct - A $62.14 bill with a 25% senior discount of $15.54 — is the
    #: 6.85% tax charged on $62.14 ($4.26)"*.
    #:
    #: **Worked, and this is the figure that moved:** a `$62.14` bill with a 25%
    #: senior discount of `$15.54` was taxed at 6.85% on the REDUCED `$46.60`
    #: and charged **`$3.19`**; it is now taxed on the FULL `$62.14` and charged
    #: **`$4.26`** — **`$1.07` more per discounted bill per cycle**, on every
    #: discounted account of every tenant.
    #:
    #: ⚠ **A DEFAULT IS UNAVOIDABLE HERE, WHICH IS THE WHOLE ARGUMENT.** The
    #: column is NOT NULL and every path that builds a `Tax` — `create_tax`, the
    #: fixture seeder, the sample-data seeder, `seed_demo`, every test —
    #: inherits it. So the choice was never *"one global answer or none"*; it
    #: was *"which global answer does a row carry when nobody has stated one"*,
    #: and carrying the OPPOSITE of the only ruling we have is the defect.
    #:
    #: **BR-RAT-106 IS NOT WEAKENED AND THE COLUMN IS NOT COLLAPSED.** The
    #: treatment stays statutory and PER TAX: `before` is still lawful, still
    #: storable, still bounded by `ck_taxes_discount_treatment`, and still
    #: settable per authority on TAX-02's *Discounts* control. An authority that
    #: levies on the discounted amount is one select away, and
    #: `tests/test_def_652_tax_on_the_full_service_value.py` fails if a later
    #: reading turns this column into a constant.
    #:
    #: **A NULL still answers `before` in `selectors.taxable_subtotal_for`, and
    #: that is deliberate.** A NULL there is not a row's answer — no row can
    #: hold one — it is a SEAM that published nothing, and a wiring gap must
    #: keep behaving as it always has rather than quietly acquiring a new money
    #: rule. Every real row states its answer.
    discount_treatment = models.TextField(default="after")
    #: `due_date_rule` — HOW the filing due date is derived, not a date: r10's
    #: *"20th of following month"*. Free text until the remittance worksheet
    #: needs to compute from it; storing a structured rule with no evaluator
    #: would be the same "field with no reader" in a costume.
    due_date_rule = models.TextField(null=True, blank=True)
    #: `remit_method` / `remit_reference` — part 4 step 3's *"method and payment
    #: reference"*. The reference is the utility's account number WITH the
    #: authority (r10's *"TX Taxpayer #1-74-1234567-8"*), which is what a filing
    #: clerk needs and what nothing could store.
    remit_method = models.TextField(null=True, blank=True)
    remit_reference = models.TextField(null=True, blank=True)
    #: `collection_allowance_percent` — `percent_field` (6 places), never
    #: `money_field` (4): BR-RAT-092 splits AMOUNT from PERCENT and a percent
    #: **stored as a fraction** needs two more places than the percent it
    #: expresses (OQ-286). Texas' 0.5% timely-filing discount is `0.005000`
    #: here, the same convention `rate` already uses — one convention for
    #: fractions across this table, so no reader has to ask which is which.
    collection_allowance_percent = percent_field(null=True, blank=True)
    #: Its OWN GL, and it is not the liability account. The allowance is the
    #: utility's INCOME (it keeps it), where the collected tax is somebody
    #: else's money — part 4's sharpest sentence. DEFERRED FK → ledger, exactly
    #: as `liability_gl_account_id` beside it.
    collection_allowance_gl_account_id = models.UUIDField(null=True, blank=True)
    #: `interest_penalty_percent` / `interest_penalty_basis` — part 4 step 3's
    #: *"interest/penalty accrual"*, what the AUTHORITY charges the utility for
    #: filing late. Two columns because a rate without its period is not a rate
    #: (the same reasoning CLAUDE.md hard rule 3 applies to consumption): `1.5%`
    #: is `0.015000` with basis `monthly`, and read as annual it is twelve times
    #: too small.
    interest_penalty_percent = percent_field(null=True, blank=True)
    interest_penalty_basis = models.TextField(null=True, blank=True)
    #: `filing_reminder_recipient` — part 4 step 3's *"who gets the filing
    #: reminder"*. An address, not a user FK: at a 1–2 staff utility the person
    #: who files is often not a product user at all (the outside bookkeeper),
    #: and an FK would have made that unrepresentable.
    filing_reminder_recipient = models.TextField(null=True, blank=True)
    #: ── THE LIFECYCLE FACT THE FOUR STATUSES ARE DERIVED FROM (DEF-387) ─────
    #: CR-013 part 4's landing shows **Active / Draft / Scheduled / Expired**
    #: and step 4 offers *"Draft / Save & schedule / Activate"*. `tax_row`
    #: derived status from `deleted_at` alone.
    #:
    #: **Three of the four come from facts already stored** — a future
    #: `effective_from` is *scheduled*, a past `effective_to` is *expired*,
    #: neither is *active* — and they are DERIVED in `selectors.tax_status`, not
    #: stored, because that is what `selectors.schedule_state` does for a rate
    #: schedule and four objects with four status vocabularies must at least
    #: agree on where a status comes from.
    #:
    #: **The fourth cannot be derived, and that is why this column exists.**
    #: A DRAFT is a tax nobody has put into force yet, and no date says so: the
    #: five ruled Texas rates are seeded with NO `effective_from` at all and are
    #: pricing real bills today, so reading "undated" as "draft" — which is what
    #: DEF-387's suggested fix proposed — would print **Draft** over the State
    #: Utility Tax while it charges 6.25%. A screen that lies about which taxes
    #: are live is worse than a screen with two statuses.
    #:
    #: So the fact is STORED — and it is stored as a flag that DEFAULTS TO NOT
    #: A DRAFT, which is the whole design and is hard-won law 3 applied to a
    #: money column: *the unsafe option must be the one you type.*
    #:
    #: ⚠ **THE FIRST ATTEMPT WAS AN `activated_at` TIMESTAMP AND IT WAS WRONG,
    #: IN THE DIRECTION THAT STOPS BILLS.** Nullable, backfilled on migration,
    #: draft = NULL — which reads beautifully and fails the moment ANY code path
    #: creates a `Tax` without going through `create_tax`. The fixture seeder,
    #: the sample-data seeder and every test build rows with
    #: `models.Tax.objects.create(...)`, so each would have minted a silent
    #: DRAFT that never prices: **the ruled Texas rates would have stopped
    #: charging on the next tenant provisioned**, with nothing red anywhere.
    #: Four tests caught it (`Tax Texas State` billing `$0.00` instead of
    #: `$6.25`), which is the only reason it is written down here rather than
    #: shipped.
    #:
    #: A boolean defaulting to `False` inverts that: every row any path creates
    #: is IN FORCE exactly as it is today, no backfill is needed at all, and the
    #: only way to get a draft is to ask for one. `create_tax(as_draft=True)`
    #: is the ask.
    is_draft = models.BooleanField(default=False)
    #: ── THE CORRECTION CHAIN (DEF-384) ──────────────────────────────────────
    #: Part 4, shared rules: *"in-place edits of an active version are refused
    #: outright, even for Owner/Admin, because rate history is an audit
    #: artefact; a historic typo is fixed by a documented correction version
    #: with a reason."*
    #:
    #: `taxes` is already one row per rate with its own window (BR-RAT-037 — a
    #: rate CHANGE is a new row), so a correction needs no second table: it is
    #: a new row that **restates the same statutory window** and points back at
    #: the row it corrects, while the corrected row is marked superseded and
    #: stops pricing. That is what distinguishes a CORRECTION (same window, the
    #: figure was wrong) from a CHANGE (new window, the figure changed) — and
    #: the two must not be conflated, because a change leaves history intact and
    #: a correction says history was mis-recorded.
    #:
    #: The corrected row is **never rewritten in its money fields and never
    #: deleted**: it keeps its rate, its dates and its audit trail for ever, so
    #: *"every rate with statutory date, citation, and amount collected under
    #: each — the primary audit artefact"* stays readable.
    corrects = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
        db_column="corrects_tax_id",
    )
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supersedes",
        db_column="superseded_by_tax_id",
    )
    #: The reason, in the operator's own words, REQUIRED on every correction.
    #: Part 4 says *"with a reason"* and says nothing about a taxonomy, so this
    #: is free text rather than an invented code list — billing's
    #: `correction_reasons` map is BR-BIL-041's and classing a TAX correction
    #: against it is a rule nobody has written. Named in the write-back rather
    #: than guessed.
    correction_reason = models.TextField(null=True, blank=True)
    #: WHO FILED THE CORRECTION — the `BY` column of the tax's own Audit tab.
    #:
    #: ⚠ **IT IS A COLUMN AND NOT AN `audit_log` LOOKUP, AND THAT IS THE POINT.**
    #: `DefinitionDetailPage`'s own §10 note and the source-as-text guard in
    #: `DefinitionDetail.test.tsx` both forbid filling this tab from a filtered
    #: audit query: an audit row is an actor + action + timestamp that the
    #: engine never reads, and a version row is *"a priced state that bills can
    #: still resolve to"*. They answer different questions and have different
    #: owners, so the version's own actor lives on the version. The tax
    #: conformance file `CR-087-p036-tax-audit.md` §7 says the same thing from
    #: the screen's side, and hard rule 4's own narrowing warns why: a value
    #: that lives ONLY in `audit_log` is pruned on a retention schedule, so a
    #: rate history read from there would lose its `BY` column silently.
    #:
    #: Stamped from the acting user by `correct_tax`, on the one path that
    #: writes a correction — nobody types it, so it cannot be wrong. The shape
    #: is `TariffVersion.submitted_by`'s, verbatim (DEF-367): a cross-module FK
    #: into the reviewed interface set, `PROTECT` because a rate history
    #: outlives any employee, and NULL for every row written before this column
    #: existed — the screen names that absence rather than inventing a person.
    corrected_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="corrected_by",
        related_name="corrected_taxes",
    )
    #: ── 🔒 THE TAX CHAIN — WHICH ROWS ARE VERSIONS OF ONE TAX (CR-165-BRC10) ─
    #: `taxes` is one row per rate with its own window (BR-RAT-037), and until
    #: this column nothing said which rows were the SAME TAX. So the billing
    #: lookup could not tell two VERSIONS of one tax (exactly one must price on
    #: any date) from two DIFFERENT TAXES of one authority (both must price), and
    #: it refused both (`DEF-RAT-9280`). A State sales tax at 6.25% and a State
    #: utility tax at 2% on a $60.00 bill are **$3.75 + $1.20**; before this the
    #: account was refused.
    #:
    #: `chain_id` is the FIRST version's id, shared by every later version — a
    #: new rate from a date (`follows`) and a correction (`corrects`) alike.
    #: NULL is never stored: `save()` fills it with the row's own id and, on
    #: PostgreSQL, a BEFORE INSERT trigger does the same for any path that
    #: bypasses `save()` (`rating/0056`). The billing lookup returns EXACTLY ONE
    #: row per chain for a date, and `ex_taxes_chain_no_overlap` refuses two live
    #: rows of one chain whose windows overlap (`DEF-RAT-9281`).
    chain_id = models.UUIDField(null=True, blank=True, db_index=True)
    #: 1-based position of this row in its chain — the *v1 / v2* the list and
    #: the details header draw. Stamped by the service that writes the row
    #: (`create_tax` 1, `new_tax_rate` / `correct_tax` the chain's max + 1);
    #: never recomputed, so a version number a clerk once read never changes.
    version_no = models.PositiveIntegerField(default=1)
    #: The row this one REPLACES FROM A DATE (`new_tax_rate`, `DEF-RAT-9283`).
    #: The mirror of `corrects`: a correction restates the SAME window, a new
    #: rate starts a NEW one the day after the old one ends.
    follows = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="followed_by",
        db_column="follows_tax_id",
    )
    #: *Account with the authority* — picked from Settings › Accounting ›
    #: Authority accounts (`TaxAuthorityAccount`). Optional; PROTECT so an
    #: account a tax files under is retired (`active=False`), never deleted.
    authority_account = models.ForeignKey(
        TaxAuthorityAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="authority_account_id",
        related_name="taxes",
    )
    liability_gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger (W5)
    remit_to = models.TextField(null=True, blank=True)  # US-RAT-009 §5 PROPOSED-SCHEMA
    filing_frequency = models.TextField(null=True, blank=True)  # r6.5 (monthly|quarterly|annual)
    filing_form = models.TextField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)  # r6.5; new row per change
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "taxes"
        constraints = [
            # DEF-273 — a scope can only be resolved against a premises column
            # that exists. Bounded in the DB as well as in `_validate_tax` so an
            # importer or a fixture cannot store a scope nothing can evaluate;
            # `time_of_use_windows.channel` (rating 0006) is the same shape.
            models.CheckConstraint(
                condition=models.Q(("premises_scope_kind__isnull", True))
                | models.Q(
                    (
                        "premises_scope_kind__in",
                        ("city_limits", "county", "state", "taxing_district", "premise_list"),
                    )
                ),
                name="ck_taxes_premises_scope_kind",
            ),
            # DEF-382 — the statutory answer is one of exactly two, bounded in
            # the DB as well as in `_validate_tax` so an importer or a fixture
            # cannot store a third value the engine would have to guess at.
            # Same shape as `ck_taxes_premises_scope_kind` above.
            models.CheckConstraint(
                condition=models.Q(("discount_treatment__in", ("before", "after"))),
                name="ck_taxes_discount_treatment",
            ),
            # DEF-385 — r10's first landing column, unique per tenant
            # case-insensitively (BR-TEN-030). ⚠ `uq_taxes_tenant_code_ci`
            # STOOD HERE AND IS DROPPED BY `rating/0056` (`DEF-RAT-9276`):
            # every version of a tax shares its code (CR-165 §7 item 6), so the
            # rule is now *one code names one CHAIN*, which a unique index
            # cannot express. On PostgreSQL it is the exclusion
            # `ex_taxes_code_one_chain` (same tenant, same lower(code),
            # different chain → refused); `_validate_tax` refuses the same thing
            # at the field on every database.
            # DEF-384 — a correction restates a window; it never corrects
            # itself. Cheap to state, and the one shape that would make
            # `superseded_by`/`corrects` a cycle of length one.
            models.CheckConstraint(
                condition=models.Q(("corrects__isnull", True))
                | ~models.Q(("corrects", models.F("id"))),
                name="ck_taxes_corrects_not_self",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """A row nobody linked to a chain STARTS one (CR-165-BRC10).

        Every path that builds a `Tax` — `create_tax`, the fixture and sample
        seeders, `seed_demo`, every test — goes through here, so a new row is
        its own chain (v1) unless the service writing it said otherwise. The
        PostgreSQL trigger in `rating/0056` covers the paths that do not.
        """
        if self.chain_id is None:
            # A correction or a new rate written by hand (a fixture, a test)
            # joins the chain of the row it corrects or follows; anything else
            # starts its own.
            parent_id = self.corrects_id or self.follows_id
            parent_chain = (
                type(self)._base_manager.filter(pk=parent_id)
                .values_list("chain_id", flat=True)
                .first()
                if parent_id is not None
                else None
            )
            self.chain_id = parent_chain or self.id
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "chain_id" not in update_fields:
                kwargs["update_fields"] = [*update_fields, "chain_id"]
        super().save(*args, **kwargs)


class TaxExemptionCategory(models.Model):
    """CR-013 part 4's EXEMPTION OBJECT — the half `applies_to_customer_classes`
    is not, and the model's own docstring has warned about the conflation since
    DEF-273 (2026-08-18). DEF-383.

    Part 4 step 2 asks for *"exemption categories with certificate
    requirements"*, and the detail tab for *"Exemptions — categories, accounts
    holding each, certificate expiry"*. Neither is expressible as an array on
    `taxes`, and the difference is not a matter of shape:

      * `taxes.applies_to_customer_classes` answers **"who does this rate reach
        at all"** — r10's *"Comm, Industrial only · Residential exempt"*. It is
        a property of the RATE, it is the same for every account in the class,
        and nothing about it expires.
      * an EXEMPTION is a property of ONE ACCOUNT: a church holds a certificate,
        the certificate has a number and an expiry date, and when it expires the
        tax comes back. `BR-RAT-006` has said *exemption is account-level* since
        long before there was anywhere to put one.

    Collapsing the second into the first would exempt every account of a class
    for ever on one customer's paperwork, and would make *"expired certificates
    reinstate the tax on the next run"* a rule with nothing to expire.

    A CATEGORY belongs to ONE tax: an authority's exemption categories are that
    authority's statute (Texas' religious exemption is not Bexar County's), so
    there is no shared catalogue to keep in step across authorities.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    tax = models.ForeignKey(
        Tax, on_delete=models.PROTECT, related_name="exemption_categories", db_column="tax_id"
    )
    code = models.TextField()  # BR-TEN-030: unique per tax, case-insensitive
    name = models.TextField()
    #: Does holding this category require a certificate on file? Part 4's words
    #: are *"categories with certificate requirements"* — plural requirements,
    #: and some categories have none (a federal agency is exempt by being one).
    #: `True` is the default because the ordinary case is a document, and a
    #: category that silently needed no paperwork would be the easier mistake to
    #: make in the direction that loses an audit.
    requires_certificate = models.BooleanField(default=True)
    #: What the operator must see before granting it — *"proof of 501(c)(3)"*.
    #: Free text: what an authority accepts is the authority's rule, not ours.
    certificate_requirement = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tax_exemption_categories"
        constraints = [
            models.UniqueConstraint(
                models.F("tax"), Lower("code"), name="uq_tax_exemption_categories_tax_code_ci"
            ),
        ]


class TaxExemptionCertificate(models.Model):
    """ONE ACCOUNT'S claim to ONE exemption category, with its expiry. DEF-383.

    ⚠ **THE EXPIRY IS THE POINT, AND THE RULE ABOUT IT IS THE OPPOSITE OF THIS
    PRODUCT'S USUAL POSTURE.** CR-013 part 4, shared rules, verbatim: *"Expired
    exemption certificates reinstate the tax on the next run with no exception
    raised — it's expected behaviour."* Everywhere else a bill run stops and
    names what changed underneath it. Here it must NOT: an expiry is a date
    passing, not a fault, and a utility with two staff cannot triage an
    exception queue that fills up every January. That rule is stated here, in
    the epic and in a test, because it is exactly the kind of thing a later lane
    "fixes" into an exception.

    **Worked:** an account holding a religious exemption against a 6.25% state
    tax on a `$196.37` taxable bill pays `$0.00` tax while the certificate is
    live and **`$12.27`** on the first run after it expires — with no exception,
    no hold, and the reinstatement visible on the bill because the line is back.

    `account_id` is a **UUID, not an FK**: `accounts` is the CUSTOMERS module's
    table (B2 §2) and rating may not add a cross-module FK outside the reviewed
    interface set. The id is validated through the customers seam on write and
    the certificate simply does not match on read if the account is not this
    tenant's — RLS makes that structurally true rather than a check to remember.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    category = models.ForeignKey(
        TaxExemptionCategory,
        on_delete=models.PROTECT,
        related_name="certificates",
        db_column="category_id",
    )
    account_id = models.UUIDField()  # DEFERRED FK → customers.accounts (B2 §2)
    #: The authority's own number for the document — what a filing clerk quotes
    #: when the authority asks why a customer was not taxed.
    certificate_ref = models.TextField(null=True, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    #: ⚠ NULLABLE, AND NULL MEANS "DOES NOT EXPIRE" — not "unknown". Some
    #: exemptions are permanent (a municipality does not renew being a
    #: municipality), and forcing a date would have made somebody invent one.
    #: The read that matters (`certificate_is_live`) treats NULL as live, which
    #: is the only reading under which a permanent exemption works at all.
    expires_on = models.DateField(null=True, blank=True)
    #: Who recorded it and when — this is the evidence half of an audit, and the
    #: `audit_log` row is the other half.
    verified_by_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → identity.users
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #: Revocation, not deletion: an authority that later disallows a claim has
    #: to be able to show WHEN the utility stopped honouring it.
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tax_exemption_certificates"
        constraints = [
            # One live claim per account per category. Partial on `revoked_at`
            # so a revoked certificate can be replaced by a new one — which is
            # the ordinary renewal path, not an edge case.
            models.UniqueConstraint(
                fields=["category", "account_id"],
                condition=models.Q(("revoked_at__isnull", True)),
                name="uq_tax_exemption_certificates_category_account_live",
            ),
        ]


class PlanService(BindingVersionMixin, models.Model):
    """rate_plan × service base-charge row (r5 #6 + r6.3 GL; BR-RAT-012/027/028
    — plan total base is DERIVED Σ, never stored)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
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
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    #: NULLABLE SINCE 2026-08-19 (DEF-277) — the same distinction as
    #: `TariffVersion.base_charge` above, on the column BR-RAT-012/027 actually
    #: put the base charge on. A plan that states NO base for a service now says
    #: so. ⚠ **AND WHAT HAPPENS NEXT CHANGED ON 2026-09-28 (`DEF-BIL-7170`):**
    #: this said *"`gather._base_charge_for` lets the schedule's figure
    #: answer"*, and it now lets the CHARGE CODE answer and reads neither this
    #: column nor the schedule's. The distinction this comment is about — a
    #: stated zero against no statement at all — is unchanged and still matters
    #: on the charge code. Before DEF-277 it stated a zero nobody had typed,
    #: which is how DEF-154 could
    #: print $0.00 on every bill for days without anyone being able to see
    #: whether the zero was a decision.
    base_charge = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: BR-RAT-102 — this service is NOT surcharged even when the plan states a
    #: factor and the premises is outside the city. R5 reads it as
    #: `outside_city_exempt_services`, and design §A4 S2 is the worked case: the
    #: sewer base is *"flat everywhere"* and stays $8.00 while every other line
    #: moves. It lives on the plan's SERVICE LINE because the plan is what lists
    #: its services — a tenant-wide exempt list could not say "exempt on the
    #: senior plan, surcharged on the standard one".
    outside_city_exempt = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default="USD")
    #: ⚠ **`minimum_amount` WAS HERE AND IS GONE — PO ruling 2026-09-10,
    #: migrations `0030` (move) + `0031` (remove).** Verbatim: *"set it in rates
    #: and use it in plans - thats it - this is rule"*. `BR-RAT-028` mode (A) —
    #: the per-service minimum — is NOT deleted as a capability and still applies
    #: before the plan floor; what moved is the SOURCE, onto
    #: `TariffVersion.minimum_bill`, which the rate schedule wizard already wrote
    #: and which `pricing_inputs` already published to billing and nothing read
    #: (`DEF-2446` — *"nothing signed says what a schedule that ALSO carries one
    #: means"*; that ruling is the missing signature). A plan now SHOWS the
    #: figure, read through from its attached schedule, on the wizard's review
    #: step and on the plan's page. Named here rather than deleted silently,
    #: because the column is cited from `BR-RAT-028`'s field map, from
    #: `gather._tariff_config_for` and from four test files.
    gl_account_id = models.UUIDField(null=True, blank=True)  # r6.3 — DEFERRED FK → ledger (W5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = PlanBindingManager()
    all_versions = AllVersionsManager()

    class Meta:
        db_table = "plan_services"
        constraints = [
            # `BR-RAT-1066` — one row per service PER VERSION (was per plan).
            models.UniqueConstraint(
                fields=["plan_version", "service"], name="uq_plan_services_version_service"
            ),
        ]


class PlanRateSchedule(BindingVersionMixin, models.Model):
    """rate_plan × service → one tariff (r5 #7; D2: one active schedule per
    service per plan)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
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
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    tariff = models.ForeignKey(Tariff, on_delete=models.PROTECT, db_column="tariff_id")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = PlanBindingManager()
    all_versions = AllVersionsManager()

    class Meta:
        db_table = "plan_rate_schedules"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "service"],
                name="uq_plan_rate_schedules_version_service",
            ),
        ]


class PlanDepositRule(models.Model):
    """rate_plan × account_type fixed deposit $ (r5 #8; BR-RAT-020/023)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
    account_type_id = models.UUIDField()  # DEFERRED FK → customers account_types (W2; B11 F-3)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_deposit_rules"
        constraints = [
            models.UniqueConstraint(
                fields=["rate_plan", "account_type_id"], name="uq_plan_deposit_rules"
            ),
        ]


class PlanChargeRule(BindingVersionMixin, models.Model):
    """rate_plan × charge attachment (r5 #9, D7). Discounts are rows with
    NEGATIVE amount_override (BR-RAT-043) — no sign check by design."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
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
    charge = models.ForeignKey(Charge, on_delete=models.PROTECT, db_column="charge_id")
    amount_override = models.DecimalField(  # NULL = catalog default
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    recurrence = models.TextField(default="event")  # once | recurring | event (r5 #9)
    taxable = models.BooleanField(default=False)  # per-attachment flag; B4.2 still bounds
    #: ── `CR-167-BRC10` ruling 9 · WHICH TABLE OF THE PLAN THIS ROW IS ON ──
    #: `charge` — the Charges table (a fee the plan makes available);
    #: `deposit` — the Billing step's Deposits table: a `refundable` code the
    #: plan names as ITS deposit (`BR-RAT-023` as amended 2026-10-03), read by
    #: `selectors.deposit_rule_for` by customer class. A role and not the
    #: code's type, because a refundable code a plan already lists as a CHARGE
    #: must not start being asked as a deposit by itself (no figure moves).
    role = models.TextField(default="charge")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanBindingManager()
    all_versions = AllVersionsManager()

    class Meta:
        db_table = "plan_charge_rules"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "charge"], name="uq_plan_charge_rules_version_charge"
            ),
            models.CheckConstraint(
                condition=Q(role__in=("charge", "deposit")), name="ck_plan_charge_rules_role"
            ),
        ]


class PlanPenaltyRule(models.Model):
    """One optional penalty-override row per plan (r5 #10, D6): every NULL
    falls back to the tenant default (tenant_settings late-fee columns)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.OneToOneField(  # plan UNIQUE (r5 #10)
        RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id"
    )
    late_fee_min = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    late_fee_pct = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    grace_days = models.IntegerField(null=True, blank=True)  # 0–30 (BR-BIL-008)
    grace_mode = models.TextField(null=True, blank=True)  # calendar | business
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_penalty_rules"


class PlanTaxRule(BindingVersionMixin, models.Model):
    """ONE ROW OF THE PLAN'S TAX SET, IN ONE OF EXACTLY TWO SHAPES — and the
    check constraint below is what keeps them two.

    **Shape 1 — a JURISDICTION BINDING** (`jurisdiction` set, `tax` NULL; r5
    #11, D8, BR-RAT-096): the plan carries THIS AUTHORITY, and every tax the
    authority levies comes with it, resolved at pricing time by
    `selectors.plan_tax_rules` (`_authority_tax`). The authority's own taxes
    are NEVER materialised as rows here — they stay derivable, so a correction
    the authority files reaches every plan that binds it without a data fix.

    **Shape 2 — an EXPLICIT TAX ATTACHMENT** (`tax` set, `jurisdiction` NULL;
    BR-RAT-113, PO 2026-08-21 closing CR-021): *"staff need to pick up and
    attach taxes and fees on the plan."* The plan carries THIS ONE tax/fee row
    from the catalogue, beyond whatever its bound jurisdictions bring.

    ⚠ **ADD-ONLY, AND THE SCHEMA IS WHAT ENFORCES IT.** BR-RAT-113, verbatim:
    *"a plan may attach taxes and fees beyond what its jurisdiction brings, and
    a jurisdiction-mandated tax stays on the bill whether or not anyone ticked
    it."* There is NO row shape that can express "omit a tax my jurisdiction
    levies" — a mandated tax is never a row, so no row's deletion can remove
    it. Whether staff may DETACH a mandated tax is explicitly NOT ruled
    (BR-RAT-113: *"a separate question, raised with a worked figure rather
    than assumed in either direction"*), so no such door is built.

    `rate_override` NULL = jurisdiction rate; the write AND read paths are
    closed by BR-RAT-094 (a plan chooses WHETHER a tax applies, never at WHAT
    rate) — the column survives only so no stored figure is destroyed.
    Account `tax_exempt` still zeroes (B4.2).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
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
    jurisdiction = models.ForeignKey(
        TaxJurisdiction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="jurisdiction_id",
    )
    #: BR-RAT-113 — the explicitly attached catalogue row. PROTECT, because an
    #: attached tax prices live bills; taxes are deactivated (`deleted_at`),
    #: never hard-deleted, so the lock only fires on a raw table wipe.
    tax = models.ForeignKey(
        Tax, on_delete=models.PROTECT, null=True, blank=True, db_column="tax_id"
    )
    rate_override = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    objects = PlanBindingManager()
    all_versions = AllVersionsManager()

    class Meta:
        db_table = "plan_tax_rules"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "jurisdiction"],
                name="uq_plan_tax_rules_version_jurisdiction",
            ),
            models.UniqueConstraint(
                fields=["plan_version", "tax"], name="uq_plan_tax_rules_version_tax"
            ),
            # Exactly one source per row: a row is a jurisdiction binding OR a
            # tax attachment, never both and never neither (BR-RAT-113).
            models.CheckConstraint(
                condition=(
                    models.Q(jurisdiction__isnull=False, tax__isnull=True)
                    | models.Q(jurisdiction__isnull=True, tax__isnull=False)
                ),
                name="ck_plan_tax_rules_one_source",
            ),
        ]


class PlanVersion(models.Model):
    """ONE VERSION OF A PLAN, AS A FILING RECORD — BR-RAT-111.

    CR-013 part 5 calls the plan *"the contract boundary: the plan version is
    what makes a bill explicable months later"*, and PLN-02 asks for *"Versions
    with component-level diff and the re-priced account count"*. Until this
    table existed a plan version was an INTEGER (`rate_plans.version`) that
    `BR-RAT-037` incremented: the product could say a plan was on v3 and could
    not say what v1 held, who filed it, or why. The authored reason went to
    `rate_change_log`, which is a compliance trail keyed by `entity_id` — a
    place the plan could not read from, so PLN-02's Versions tab printed one row
    and stated its own absence in the CHANGE column.

    ⚠ **THE COLUMN SET IS COPIED FROM `tariff_versions` (migration 0019,
    DEF-367 · DEF-280) — MINUS THE DOCKET, AND THAT SUBTRACTION IS A RULING.**
    `09-screen-inventory.md` §10, verbatim: *"Do not normalise the other four up
    to seven columns — a discount has no docket."* Neither does a plan. So
    `version_label` — the schedule's filed `PUC #W-2025-1184` — is NOT on this
    table, and adding it would make the concept the PO ruled against storable.
    What IS copied:
      · `change_reason`  DEF-280 — BR-RAT-037's authored words, on the row that
        is read rather than in a table the object cannot reach.
      · `submitted_by`   DEF-367 — WHO. The cross-module FK to `identity.User`
        that the reviewed interface set (B2 §2) already carries for
        `approved_by`, `PROTECT` because a filing record outlives an employee,
        served as `{id, name}` through `seams.user_display_names` — the shape
        `apps/audit/selectors` has always used. A second shape for one fact is
        how two screens start disagreeing about a person's name. ⚠ It is NOT a
        `BY` COLUMN on the screen (§10 again); PLN-02 prints it under the
        version number, so the plan's table stays the ruled four columns wide.

    ⚠ **`snapshot` IS THE CONTENT AND `plan_versions` IS INERT.** Nothing that
    prices a bill reads this table: `resolution` and `billing/gather` are
    untouched. WHICH version prices an account already assigned at an older one
    is `OQ-323` and is unruled — `unit_plan_assignments.plan_version` has stored
    that number since W1 with no consumer at all, and putting content behind it
    without a ruling would answer a money question by accident.

    ⚠ **THERE IS NO `effective_from`, DELIBERATELY.** Part 5 step 8 describes
    *"Draft / Submit / Activate"*, which would make a plan version PEND the way
    a rate-schedule version does; that reading is `OQ-324` — ⚠ CLOSED 2026-10-03 as (B) by the
    PO-approved plans drawing (`BR-RAT-1066`); the columns arrive with `rating/0062`. A date column added
    before the ruling makes the unruled reading storable, which is the mistake
    `plan_discount_rules`' absent value column was written to avoid.

    ⚠ **APPEND-ONLY** — hard rule 4's spirit. A version row is never updated and
    never deleted (the one exception is `delete_plan`, which only reaches a plan
    with zero accounts that was never billed). Corrections are new versions.

    ⚠ **NAME COLLISION, STATED SO THE NEXT AGENT DOES NOT WALK INTO IT.**
    `apps/rating/resolution.py` ALREADY defines a dataclass called `PlanVersion`
    — R1's *resolved plan*, an in-memory answer to "what does this account's plan
    say today" — and a field called `plan_versions` that holds a tuple of them.
    It has nothing to do with this table and never reads it. So a grep for either
    name returns the pricing chain, and two assertions written that way each
    reported R1 as guilty of consulting a table it has never heard of. **To ask
    whether something reads THIS model, search for an ORM access** —
    `models.PlanVersion` or `PlanVersion.objects` — which is the only form that
    can only mean the table. The names were not merged because each is right in
    its own module: `plan_versions` is the DB name this table must have, beside
    `tariff_versions`, and renaming R1's dataclass is another lane's file.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
    #: The counter this row records, matching `rate_plans.version` at the moment
    #: it was written. UNIQUE per plan — two rows claiming v2 would make the
    #: history unreadable in exactly the way the integer alone already was.
    version_no = models.IntegerField()
    #: BR-RAT-037's REQUIRED reason, on the row it describes rather than only in
    #: `rate_change_log`. NULL on the version a plan is CREATED with, because
    #: BR-RAT-037 asks for a reason when a published plan CHANGES and there is
    #: nothing yet to give a reason about.
    change_reason = models.TextField(null=True, blank=True)
    #: WHO. Nullable because `_actor_user_id` can answer None (a system path),
    #: and a version written by the product is a different fact from one written
    #: by a person — the screen renders the difference.
    submitted_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="submitted_by",
        related_name="submitted_plan_versions",
    )
    #: The whole of `plan_detail` minus the counter and the live account count —
    #: `_plan_snapshot`'s output, the SAME blob `rate_change_log.after` carries,
    #: so the diff computed from these rows and the diff computed from that
    #: table can never disagree.
    snapshot = models.JSONField()
    #: ── `OQ-RAT-12409` OPTION A · BR-RAT-1016 REACHES THE PLAN ─────────────
    #:
    #: **PO ruling 2026-09-18, verbatim:** *"The plan correction — A, B or C -
    #: option A pls"*. These are `taxes`' four columns and `tariff_versions`'
    #: four columns, copied a third time deliberately rather than re-invented:
    #: `BR-RAT-1016` rules that the three verbs are the SAME for every priced
    #: object, and a third shape for the third object is a cost paid by every
    #: future reader of this module.
    #:
    #: ⚠ **WHAT A PLAN CORRECTION RESTATES IS THE `version_no`, NOT A WINDOW.**
    #: For a tax and for a rate-schedule version, the property that makes a
    #: correction a correction is that the effective WINDOW is copied from the
    #: row being corrected and never read from the payload. A plan version has
    #: no window — `OQ-324` records that omission as deliberate (⚠ CLOSED (B) 2026-10-03, BR-RAT-1066) — so the
    #: equivalent invariant is the COUNTER: `correct_plan_version` copies
    #: `version_no` from the row it corrects and never reads one from a
    #: payload, and `rate_plans.version` does not move. Without that property a
    #: "correction" is a version bump wearing a correction's clothes.
    #:
    #: ⚠ **AND THE COUNTER IS WHY THIS MATTERS MORE HERE THAN ANYWHERE ELSE.**
    #: `unit_plan_assignments.plan_version` snapshots the number at assignment
    #: (`BR-CUS-013`) and those rows outlive the plan, so a version minted for a
    #: typo is a number they point at for ever. On the seeded estate that is 75
    #: units on `SCW-RES`, all of them recorded against `plan_version = 1`.
    #:
    #: The corrected row is **never rewritten and never deleted**: it keeps its
    #: snapshot, its reason, its submitter and its timestamp for ever. It stops
    #: being the current statement of that version because `superseded_by` says
    #: so, not because anything on it changed (hard rule 4).
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
    #: ⚠ It is NOT `change_reason`. That one answers *why the plan changed* and
    #: is `BR-RAT-037`'s filing note; this one answers *what was recorded
    #: wrongly*, and a screen that showed one where the other belongs would file
    #: a typo as a plan change — which is the whole defect (`DEF-RAT-5710`).
    correction_reason = models.TextField(null=True, blank=True)
    #: ── `BR-RAT-1066` · THE VERSION'S WINDOW, STATUS AND TERMS (`rating/0062`)
    #: `OQ-324` CLOSED (B) 2026-10-03 by the PO-approved drawing (image 41:
    #: *"v1 · 09/01/2026 – 12/31/2026 · gets an end date; v2 · new ·
    #: 01/01/2027 – No end"*). `status`: `draft` (a draft plan's v1, or a
    #: *Save new version* not yet published) · `published` (can price) ·
    #: `history` (a filing row that prices nothing). Two `published`,
    #: un-superseded versions of one plan never share a date —
    #: `ex_plan_versions_no_overlap` (`rating/0064`). A correction COPIES the
    #: window of the version it corrects (`BR-RAT-1016`).
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    status = models.TextField(default="published")
    minimum_bill_amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    outside_city_factor = rate_field(null=True, blank=True)
    budget_billing = models.BooleanField(default=False)
    late_fee_charge = models.ForeignKey(
        "rating.Charge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="late_fee_charge_id",
        related_name="late_fee_for_plan_versions",
    )
    #: WHO FILED THE CORRECTION. `submitted_by` above is who filed the VERSION,
    #: and on a correction row the two are usually the same person — but not
    #: always, and `taxes`/`tariff_versions`/`discount_versions` all carry both.
    #: Stamped from the acting user on the one path that writes a correction, so
    #: nobody types it and it cannot be wrong. NOT read back out of `audit_log`,
    #: which is pruned on a retention schedule (hard rule 4's 2026-09-02
    #: narrowing) — a filing record sourcing its authors from there would lose
    #: them on the pruning run with nothing raising (`DEF-367`).
    corrected_by = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="corrected_by",
        related_name="corrected_plan_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plan_versions"
        indexes = [
            models.Index(fields=["tenant", "rate_plan"], name="ix_plan_versions_plan"),
        ]
        constraints = [
            # ⚠ **PARTIAL, AND THE PREDICATE IS THE WHOLE OF `OQ-RAT-12409`'s
            # OPTION A.** One row per version number is exactly right for the
            # filing a version STATES, and exactly what a correction must be
            # able to break: a correction is a second row carrying the SAME
            # `version_no`. Keeping the unique over non-corrections preserves
            # the guarantee the table was built for — two rows can never both
            # claim to be version 3's original filing — while letting any number
            # of corrections restate it. Every row on disk before migration 0036
            # reads `corrects IS NULL`, so the partial key covers all of them
            # unchanged and no data moves (the arithmetic is in the migration).
            models.UniqueConstraint(
                fields=["rate_plan", "version_no"],
                condition=Q(corrects__isnull=True),
                name="uq_plan_versions_plan_version_no",
            ),
            # A correction restates another row; it never corrects itself. The
            # one shape that would make `corrects`/`superseded_by` a cycle of
            # length one, stated verbatim from `taxes`' own
            # `ck_taxes_corrects_not_self` and `discount_versions`' copy of it.
            models.CheckConstraint(
                condition=Q(corrects__isnull=True) | ~Q(corrects=models.F("id")),
                name="ck_plan_versions_corrects_not_self",
            ),
            models.CheckConstraint(
                condition=Q(status__in=("draft", "published", "history")),
                name="ck_plan_versions_status",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_from__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="ck_plan_versions_window",
            ),
            # One unpublished new version per plan at a time (`rating.plans.
            # one_draft_version`); a draft plan's v1 is that one draft.
            models.UniqueConstraint(
                fields=["rate_plan"],
                condition=Q(status="draft"),
                name="uq_plan_versions_one_draft",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.rate_plan_id} v{self.version_no}"


class RateChangeBatch(models.Model):
    """One bulk rate update = one batch (r5 #14, D9; BR-RAT-040: one reason +
    one effective date + one actor, atomic apply, never re-run). Append-only."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    reason = models.TextField()  # NOT NULL — compliance (r5 #14)
    change_spec = models.JSONField(null=True, blank=True)  # r6.7 bulk parameters
    actor = models.ForeignKey(  # ⚠ cross-module → identity (reviewed set)
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_user_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rate_change_batches"


class RateChangeLog(models.Model):
    """Per-entity compliance trail (r5 #14; BR-RAT-037): before/after jsonb,
    reason NOT NULL, actor. APPEND-ONLY — corrections are new rows."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(
        RateChangeBatch, on_delete=models.PROTECT, null=True, blank=True, db_column="batch_id"
    )
    entity_type = models.TextField()  # plan | schedule | charge | tax (S9 History filter set)
    entity_id = models.UUIDField()
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField()  # NOT NULL — compliance (r5 #14)
    actor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_user_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rate_change_log"
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="ix_rate_change_log_tenant"),
        ]


class UnitPlanAssignment(models.Model):
    """Unit ↔ plan history with plan_version SNAPSHOT (r5 #13; BR-CUS-010/011/
    013). Rating-owned per r16 #6, WRITTEN via the customers seam (r16 #7
    interface register); the ledger reads this. APPEND-ONLY."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    unit = models.ForeignKey(  # ⚠ cross-module → metering units (reviewed set, B2 §2)
        "metering.Unit", on_delete=models.PROTECT, db_column="unit_id"
    )
    rate_plan = models.ForeignKey(RatePlan, on_delete=models.PROTECT, db_column="rate_plan_id")
    plan_version = models.IntegerField()  # SNAPSHOT at assignment — never mutated (BR-CUS-013)
    assigned_from = models.DateField()
    assigned_to = models.DateField(null=True, blank=True)  # null = current
    source = models.TextField()  # new_connection|move_in|change_plan|bulk_update|import (r9 #8)
    actor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_user_id"
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unit_plan_assignments"
        indexes = [
            models.Index(fields=["tenant", "unit"], name="ix_unit_plan_assign_unit"),
        ]
        constraints = [
            # One CURRENT plan per unit (BR-CUS-010 current-row semantics; J2 step 3).
            models.UniqueConstraint(
                fields=["unit"],
                condition=Q(assigned_to__isnull=True),
                name="uq_unit_plan_assignments_current",
            ),
        ]


# ── CR-013 part 3 · the DISCOUNT object ─────────────────────────────────────
# Six tables — `discounts`, `discount_versions`, `plan_discount_rules`,
# `discount_enrolments`, `discount_enrolment_documents`, `discount_grants` —
# live in `apps/rating/discounts.py` rather than in this file. They are rating's
# tables and they register into this app (`Meta.app_label` is `rating` by module
# location), so the import below is what makes them exist for the app registry
# and for `makemigrations`; deleting it silently un-defines six tables.
#
# WHY A SEPARATE MODULE AND NOT 500 MORE LINES HERE: the discount object carries
# the whole of CR-013 part 3 — five types, five scopes, three caps, a floor,
# stacking precedence, verification, recertification, a budget and an approval
# chain — and each of those is a rule that has to be quoted where it is stored.
# One file per bounded object keeps that prose beside its columns, and it keeps
# this file's Trace header answerable about what it covers.
#
# ⚠ **AND IT IS WHY `DEF-RAT-5094` WAS FILED AGAINST THIS FILE AND BELONGS IN
# THAT ONE.** That row reported `makemigrations --check` red over
# `ck_discount_versions_scope` and named `apps/rating/models.py DiscountVersion`
# — but `DiscountVersion` is not here, and a lane opening this file to look at
# the constraint finds nothing. It read the red as a harmless SPELLING
# difference, and so did `DEF-GOV-5506`; it was a CONTENT difference — five
# permitted values in the table against seven in the model — and one `psql`
# query separates the two readings. Fixed by `rating/0040`
# (`DEF-RAT-5814`); the constraint and the whole story are in `discounts.py`,
# beside the declaration.
# Imported for its SIDE EFFECT — importing the module is what registers its
# models — so it is not a star-import: nothing in this file's namespace is
# rebound, and a reader of `apps.rating.discounts.Discount` is looking at the
# file that documents it.
from apps.rating import discounts  # noqa: E402,F401  (registers six models)

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-001@5f478ea (story+rules snapshot — EP-RAT-01..04 W1 schema half + r16 owner map)
# generated: 2026-08-09 by story-coder v1 (W1 SCHEMA lane — models+migrations only); amended 2026-08-09 by story-coder v1 (rating SCHEMA-GAP lane — BR-RAT-031 draft storage + US-RAT-002 §5 eligibility, migration 0004) · AMENDED 2026-08-16 by the register lane (BR-RAT-067: `TimeOfUseWindow.channel` + `ck_time_of_use_windows_channel`; migration 0006)
# checklist: A✔ B=deferred(table-half only — service/API TCs land with each story lane; the two gap columns DO carry TC tests in test_us_rat_schedules.py/test_us_rat_plans.py) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff✔ py_compile✔ pytest tests/test_w1_models.py✔ · suite -m 'not golden and not isolation' 580 passed / 8 skipped (566 baseline + 14 gap tests)✔ · migrate✔ makemigrations --check clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · black: 3 PRE-EXISTING nits flagged in this file + migrations 0001/0002 (budget_billing/max_amount lines, untouched by this lane) — my edits are black-clean, the pre-existing lines were NOT reformatted (churn outside the gap) · mypy NOT INSTALLED in this environment — recorded, not skipped silently
# exceptions: BR-RAT-039 vs r6.0 available_for_new_signup (column omitted per rule — REPORTED) · r6.5 percent-vs-rate duplicate not added (REPORTED) · r6.7 season_id vs base rate_tiers unique kept verbatim (REPORTED) · deferred FKs (account_types/subtypes W2, ledger_accounts W5 — B11 F-3) as plain uuid columns · taxes.applies_to_services as JSON list (array-type Eng disposition — REPORTED) · account_capacities/account_types NOT built (customers-owned per r16 #6) · holiday_calendars NOT rebuilt (hosted by tenancy W0 disposition vs r16 #6 rating-owner proposal — flagged there) · B2 §2's EXCLUDE gist no-overlap constraint on tariff_versions was never materialized by migration 0001 (btree_gist absent), so there was NO DB constraint to make partial for drafts — nothing dropped, overlap stays app-side in services._guard_window; REPORTED, not resolved (ledger row for 0004 names it for the human reviewer)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
