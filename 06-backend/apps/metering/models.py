# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (premises list) · US-MET-002 (units list) · US-MET-003
#           (guided add — premise/unit/meter/plan panels) · US-MET-004 (bulk
#           create paths) · US-MET-005 (routes/cycles ops tabs) · US-MET-006
#           (Settings → Routes & Cycles config + route memberships)
#           Screens: S14, S15, S16, S26, S27, S8
# Rules:    BR-MET-001/002/003 (premise/unit identity) · BR-MET-034 (premises
#           types = Reference data, never a hardcoded enum) · BR-MET-036
#           (occupancy DERIVED — deliberately NO stored column) · BR-MET-037
#           (delete guards — service law) · BR-MET-006/007 (meter + default-plan
#           panels; binding per BR-CUS-014) · BR-MET-008/009/010 (routes/cycles
#           config) · BR-MET-033 (membership selection + optional walk order —
#           supersedes sequence ranges) · BR-TEN-036 (lookup shape)
#           US-MET-016 (supersede & correction flow — the `read_corrections`
#           linkage a BILLED read's correction hands to J6; BR-MET-053/054)
#           AMENDED 2026-08-11 (tenant custom-fields lane): r17.2
#           `custom_data` on premises · units · service_points (BR-TEN-046;
#           never a money input, BR-TEN-048/DB-17).
# Tests:    06-backend/tests/test_w1_models.py (constraint halves on the migrated
#           sqlite test DB; RLS assertions live in the G5 isolation suite)
# Impacts:  assets (service_points FK target) · customers accounts.unit_id (W2) ·
#           rating unit_plan_assignments.unit_id · reads lane (W2 — meter_reads
#           deliberately NOT built here, r16 #4)
# ───────────────────────────────────────────────────────
"""metering models — W1 tables owned per B2 r16 owner map (product: Meter Reads).

Schema law implemented here (signed): B2 §2 metering DDL (premises, units,
routes, cycles, service_points, read_schedules) as REDLINED by r16 (never raw
§2/§3 — r16 #8): r16 #3 (service_type enum role → 10-service catalog FK) plus
the story-§5 PROPOSED-SCHEMA columns carried verbatim (EP-MET-01/02 field
maps; BR-MET-033 route_memberships replaces the superseded sequence-range
columns — OQ-041 closure). `premises_types` is a metering-hosted Reference-data
lookup (BR-MET-034 seeds; BR-TEN-036 shape) — hosting disposition flagged in
the build report, owner map has no row for it.

W2 READS LANE (2026-08-10) — the four tables the W1 header called "deliberately
NOT built" now exist at the bottom of this file: `read_validation_settings`
(B2 r5 #15), `read_import_batches`, `read_import_rows` (both US-MET-007..010
§5 PROPOSED-SCHEMA) and `meter_reads`, built to the CHANNEL END-STATE (B2 r8 /
DB-6 — one record per register per date, supersede chain, per-channel
estimation), never the superseded r7/base body. `units` still has NO occupancy
or status column: occupancy derives from the active account (BR-MET-036 — a
settable column would violate the rule), unit status is computed display only
(US-MET-002 §5).

Money-free module — reads carry QUANTITIES only (consumption + explicit unit,
CLAUDE.md rule 3); nothing here prices anything. PKs uuidv7-style (DB-2) except
`meter_reads`, whose PK includes its partition key (B2 §2 verbatim). Enum-ish
value sets are TextFields per the W0 pattern (r5 #20). RLS: W1 tables get
ENABLE+FORCE via 0002_rls_w1_policies (SQL in db/rls_metering_w1.sql), the W2
reads tables via 0004_rls_w2_reads_policies.
"""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.dbfields import uuid7, uuid7_pk


class PremisesType(models.Model):
    """Premises-types Reference-data list (BR-MET-034: seeded Apartment complex ·
    Commercial building · Single-family · Mixed-use · Mobile-home park, tenant-
    extensible; BR-TEN-036 lookup shape). Seeding rides the tenant fixture
    seeding lane (BR-TEN-012), not this migration."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    is_system = models.BooleanField(default=False)  # seeded rows deactivatable, never deletable
    active = models.BooleanField(default=True)
    #: `CR-162-BRC10` (Q1, reframed by the PO 2026-10-02: *"when we say
    #: premises type has account type - master or regular attached … then when
    #: you create account dont you want to use this field when you are creating
    #: accounts"*) — the ACCOUNT TYPE a premises of this type takes: `master`
    #: or `regular`, the same two words as `accounts.kind`. Named
    #: `account_kind` and not `account_type` because `accounts.account_type` is
    #: already the CLASS lookup (residential, commercial …), a different fact.
    #: Every account-creation door reads it when an owner's master account is
    #: opened, so changing it moves only what is created afterwards. Seeded
    #: rows are answered by `metering/0066` and the seed; a type a utility ADDS
    #: must answer it (no default — the Settings door refuses a blank). `NULL`
    #: only on a utility's own row from before 0066, which falls back to
    #: counting homes (2.442.0's rule) until somebody answers it.
    account_kind = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "premises_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_premises_types_tenant_code_ci"
            ),
        ]


class UnitType(models.Model):
    """Unit-types Reference-data list — CR-010 A-section item 4 (PO 2026-08-17:
    *"this is correct"* on "Premise & unit types (one card, two levels)"),
    BR-MET-084.

    Until 2026-08-18 the vocabulary was the UNIT_TYPES 5-tuple in services.py
    (US-MET-002 §5's option set) — a closed enum no tenant could extend and no
    screen could show. The ruling turns it into the same shape premises types
    have had since BR-MET-034: seeded `is_system` rows (deactivatable, never
    deletable — BR-TEN-036), tenant-extensible, served on the S8 card beside
    premises types (r10 SET-04's one "Premise & unit types" surface = the two
    cards of the PREMISES group).

    `units.unit_type` stays a TEXT code, not an FK: the column predates this
    table, importers and sample data write the legacy codes, and validation
    resolves against this table FIRST with the legacy tuple as fallback
    (`_validate_unit` in services.py). Because there is no PROTECT to lean on,
    the lookup handler itself enforces BR-TEN-030 (code frozen once used) and
    BR-TEN-034 (a used row is not deletable) by live count over units.

    Seeding rides the reference seam (SEED_UNIT_TYPES is the single ratified
    source; the platform fixture deliberately carries no entries — the DEF-026
    premises_types posture)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    is_system = models.BooleanField(default=False)  # seeded rows deactivatable, never deletable
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "unit_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_unit_types_tenant_code_ci"
            ),
        ]


class PremisesOwner(models.Model):
    """The party that OWNS a premises — a typed record, not a name in a box.

    **BR-MET-150, from the PO ruling of 2026-08-27**, verbatim: *"category is
    okay, no richer text"*, answering: is an owner a typed party record —
    owner-occupier · landlord · property manager · HOA · builder, with contact
    details, linked to the customer they already are — or richer free text?

    **Why this table exists at all.** Three of the five seeded occupancy states
    name an OWNER as the party who pays — *owner-billed*, *landlord-billed
    between tenants*, and the owner side of *tenant-billed*. So the product
    already decides who to bill by looking at a box that held a typed NAME. A
    typed record is what makes that decision resolvable.

    ⚠ **THERE IS NO DESCRIPTION OR NOTES COLUMN, AND ITS ABSENCE IS HALF THE
    RULING.** *"no richer text"* rejected the option of keeping the free-text
    box and making it longer — which was cheaper and would have left the product
    routing money at somebody it still could not identify. A notes column here
    would re-introduce exactly that, one row lower down. Do not add one.

    ⚠ **`category` IS REQUIRED AND `customer` IS NOT**, and both are the
    ruling's own words. A record with no category is the free-text box again. A
    record with no customer is a real state: *"a builder holding a site before
    handover may not be [a customer], so the link is optional and its absence is
    a stated fact rather than a gap."*

    ⚠ **`customer` IS A CROSS-MODULE FK, metering → customers.** The direction
    already exists in B2 §2's reviewed set (this module FKs `customers.Account`
    twice); the COLUMN is new and its review row is B2 addendum r21, OWED at the
    next sitting. It is a POINTER and never a write — the customer's name and
    number are read through `apps.metering.seams`, like every other cross-module
    read in this module.

    **`source_owner_manager` is provenance, not a duplicate.** It records the
    free-text string this record was matched FROM (BR-MET-151), so an auditor
    asking *"which of the twelve names became this party?"* gets an answer. It
    is written once, at match time, and never edited.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: BR-TEN-150 — tenancy HOSTS the vocabulary, metering OWNS its content
    #: (BR-TEN-031), the same split `area`, `occupancy_statuses` and
    #: `meter_size_classes` already take. NOT NULL: the type is the point.
    category = models.ForeignKey(
        "tenancy.PremisesOwnerCategory",
        on_delete=models.PROTECT,
        db_column="category_id",
        related_name="owners",
    )
    name = models.TextField()
    #: The ruling's *"contact details, so there is a way to reach whoever is
    #: named when a unit is vacant or a bill bounces"*. All three OPTIONAL —
    #: refusing to record a party at all because nobody has their phone number
    #: would be worse than recording them without one. Whether the category that
    #: PAYS must carry at least one of them is `OQ-503`.
    contact_name = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    #: See the class docstring: optional by ruling, cross-module by B2 r21.
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="customer_id",
        related_name="+",
    )
    #: BR-MET-151 clause 4 — the free-text string this record was matched from.
    #: NULL on an owner created from scratch, which is a different fact from an
    #: empty string and is why there is no default.
    source_owner_manager = models.TextField(null=True, blank=True)
    #: ── THE OWNER'S MASTER ACCOUNT (BR-MET-400, PO ruling 2026-08-27) ─────
    #: **PO verbatim:** *"so premises owner is master accountin system. you
    #: ahve to showall details form account - Bascially Premises -> owner =
    #: Master account - it can be existing master account also"*.
    #:
    #: ⚠ **THIS IS "THE ONE MISSING LINK" THE RULING NAMES BY NAME.** The
    #: decision log of 2026-08-27 measured the chain and found every hop built
    #: except this one: *"Today nothing joins a `premises_owners` row to an
    #: `accounts` row of kind `master`."* Without it `BR-MET-105`'s
    #: $30.50/month empty-unit accrual and a move-out shortfall have no posting
    #: target at all — which is `DEF-650`, filed critical, and which the
    #: move-out wizard states in its own shipped copy: *"Owner is free text on
    #: the premise record, not an account. That limits where a shortfall can be
    #: sent."*
    #:
    #: **DECLARED, NEVER INFERRED.** This column replaces `BR-CUS-171`'s
    #: GEOMETRIC derivation — the `kind='master'` account anchored on one of the
    #: premises' common areas. Decision 4 of the same ruling retires that path
    #: rather than keeping it as a fallback, *"because a fallback that disagrees
    #: with the declared owner would silently bill a different party"*.
    #:
    #: ⚠ **NULLABLE, AND THE NULL IS A REAL STATE RATHER THAN A GAP.** Two
    #: honest reasons, both stated so nobody "tidies" the column to NOT NULL:
    #:   1. Every owner row on every tenant predates this column, exactly as
    #:      `Premises.owner` records for itself one class up.
    #:   2. **WHEN the owner's account comes into existence, and whether it is
    #:      `master` or `regular`, is `OQ-790` and is NOT decided.** The ruling
    #:      says the owner RECORD always exists and that master-ness is DERIVED
    #:      from whether anyone else occupies the premises (`OCC-O` against
    #:      `OCC-T`) — and at premises creation no unit is occupied yet, so the
    #:      kind cannot be derived. Guessing it decides who is billed.
    #:
    #: PROTECT, never CASCADE: an account twelve addresses are billed through
    #: must refuse deletion and say so.
    master_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="master_account_id",
        related_name="+",
    )

    #: IS-1 deactivate-first, like every other tenant-owned party row.
    active = models.BooleanField(default=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row, written only by this
    #: module's own service on the sample path. BR-TEN-061 deletes on it.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "premises_owners"
        constraints = [
            #: One party per NAME per tenant, case-insensitively — which is the
            #: ruling's *"the same landlord across twelve addresses is one party
            #: rather than twelve unrelated strings"* made structural. Without
            #: it, matching twelve premises one at a time creates twelve parties
            #: and the whole point of the table is lost by accident.
            models.UniqueConstraint(
                models.F("tenant"), Lower("name"), name="uq_premises_owners_tenant_name_ci"
            ),
        ]


class Premises(models.Model):
    """Physical property (B2 `premises` + US-MET-001/003 §5 PROPOSED-SCHEMA
    columns: premise_no, type lookup, services_available, owner_manager,
    external_ref, status)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    premise_no = models.TextField(null=True, blank=True)  # tenant numbering series (EP-TEN-08)
    name = models.TextField(null=True, blank=True)  # B2 base
    address_line = models.TextField()  # PII-adjacent; required
    city = models.TextField(null=True, blank=True)
    state = models.TextField(null=True, blank=True)
    postal_code = models.TextField(null=True, blank=True)
    #: ── THE JURISDICTION FLAG (BR-RAT-101, PO ruling 2026-08-21) ───────────
    #: PO verbatim: *"On premises we will add this flag and during billing we
    #: will consider Account -> Unit -> Premises to consider it."*
    #:
    #: It lives HERE and not on the account because design §A1 keeps the two
    #: selectors on different objects: *"the premise's jurisdiction flag (inside
    #: / outside city) and the account's customer class select which rows
    #: fire."* A house does not move between city limits when its tenant
    #: changes, and putting the flag on the account would let two accounts at
    #: one address disagree about where that address is.
    #:
    #: ⚠ **NULLABLE, AND `None` IS A THIRD STATE — NOT A DEFAULT.** `True`
    #: inside, `False` outside, `None` NOBODY RECORDED IT. `rating.resolution
    #: .money_factor` refuses on `None` rather than assuming, and that is the
    #: only safe direction: assuming INSIDE under-charges a customer the
    #: utility may be entitled to surcharge, and assuming OUTSIDE over-charges
    #: one who never agreed to it. Either default would be a silent pricing
    #: decision made on data nobody entered. Do not give this a `default=`.
    #:
    #: ⚠ **THESE TWO LINES WERE STALE FOR SIX DAYS AND ARE CORRECTED HERE
    #: (2026-08-27).** They read *"The FACTOR this flag selects is not ruled yet
    #: (`OQ-308`) … Nothing prices off this column until it is."* `OQ-308` was
    #: CLOSED by the PO on 2026-08-21 — *"We can have it on plan itself - Plan
    #: will decide whether to apply and then how much"* (BR-RAT-102) — and
    #: `gather._jurisdiction_factor_for` has priced off this column since that
    #: day. From 2026-08-27 the sample estate exercises it: two of the 44 seeded
    #: premises are outside the city on a plan stating `1.5`.
    #: ⚠ **AND IT IS WRITABLE FROM A SCREEN** (CR-039 wave C task 10, closing
    #: `DEF-517`): `services._validate_premises` accepts the three states and
    #: `JurisdictionField` draws them. Changing it applies FORWARD ONLY —
    #: `OQ-423`, stated in `update_premises`'s docstring, never implied.
    inside_city_limits = models.BooleanField(null=True, blank=True)
    premises_type = models.ForeignKey(  # BR-MET-034 Reference-data lookup
        PremisesType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="premises_type_id",
    )
    services_available = models.JSONField(  # ⊆ tenant-enabled (BR-MET-003); list of
        null=True, blank=True  # service catalog codes (array-type Eng disposition — reported)
    )
    #: BR-MET-071 (PO ruling 2026-08-16, CR-006): *"we wil tag them to
    #: premises"*. The `areas` list shipped with CR-004 as a vocabulary that
    #: NOTHING pointed at — so "filter premises by area" could not be written,
    #: which is exactly what SET-06 step 2 asks for. This is that link.
    #:
    #: ⚠ cross-module FK metering→tenancy (the reviewed set, B2 §2), the same
    #: direction `service_points.service_id` already takes. Tenancy HOSTS the
    #: table; metering OWNS its content (BR-TEN-031), so the FK points at the
    #: host and the meaning stays here.
    #:
    #: NULLABLE, deliberately: every premises in every tenant predates the
    #: column, and a required area would make an untouched row unsaveable —
    #: the same failure OQ-250 records for a pad minimum. A premises tagged to
    #: a SUB-area is by construction inside that sub-area's parent, so ONE
    #: column answers both levels of BR-MET-072's filter.
    area = models.ForeignKey(
        "tenancy.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="area_id",
    )
    #: ── THE FREE-TEXT OWNER NAME (BR-MET-151) ─────────────────────────────
    #: ⚠ **THIS COLUMN IS NO LONGER THE ANSWER TO "who owns this?", AND IT IS
    #: DELIBERATELY NOT DROPPED.** PO ruling 2026-08-27, verbatim: *"category is
    #: okay, no richer text"* — an owner is a TYPED PARTY RECORD (`owner` below,
    #: BR-MET-150), not a name in a box. This column stays for three stated
    #: reasons, all of them in BR-MET-151:
    #:   1. It is what an UNMATCHED premises still has. `metering 0040`
    #:      backfills nothing, because guessing which string is which party is
    #:      exactly what the ruling forbade; a premises is *unmatched* when this
    #:      column holds text and `owner_id` is NULL, and that is a COMPUTED
    #:      state rather than a second column that could disagree.
    #:   2. It is what `customers.services.open_account` reads for the default
    #:      payer (PO 2026-08-22: *"payer = the premises' owner/manager"*).
    #:      Whether the typed owner supersedes it is `OQ-500` and is NOT
    #:      decided — dropping this column would silently change who a new
    #:      account bills.
    #:   3. It is the provenance of a match, stamped onto the owner row as
    #:      `premises_owners.source_owner_manager`.
    #: Retiring it is `OQ-501`, and `OQ-500` has to be settled first.
    owner_manager = models.TextField(null=True, blank=True)
    #: ── THE TYPED OWNER (BR-MET-150, PO ruling 2026-08-27) ─────────────────
    #: The pointer half of *"a link to the customer they already are"* and of
    #: *"the same landlord across twelve addresses is one party rather than
    #: twelve unrelated strings"*: MANY premises point at ONE owner row.
    #:
    #: NULLABLE, and the NULL is a real state rather than a gap — *no typed
    #: owner has been recorded for this address*. Every premises in every tenant
    #: predates this column (BR-MET-151: the migration writes no owner row), so
    #: a required FK would make an untouched row unsaveable, which is the same
    #: failure `area` records above.
    #:
    #: PROTECT, never CASCADE: deleting an owner that twelve addresses point at
    #: must refuse and say so, never silently untype twelve premises.
    owner = models.ForeignKey(
        "metering.PremisesOwner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="owner_id",
        related_name="premises_set",
    )
    #: ── 2026-09-22 · `BR-MET-1181` — THE PREMISES NAMES ITS MASTER ACCOUNT ──
    #: **PO ruling, verbatim:** *"why you are point is at owner id - why not
    #: directly at master accoutn Id - it will solev the problem … owner IDs are
    #: not required hence no screens or fucntionality for it"*.
    #:
    #: ⚠ **IT IS NOT A NEW IDEA. IT IS `OQ-790`'s OWN MECHANISM, NAMED BY THE
    #: SAME PERSON TWENTY-SIX DAYS EARLIER** — *"you ahev to call master account
    #: creation logic by passing the details and generate account number using
    #: Setting -> numbering and use this number to write premsies"*. **This
    #: column is the *"use this number to write premsies"* half**, and what
    #: stopped it being built was the owner-record hop above, not a missing
    #: ruling.
    #:
    #: ⚠ **THREE COLUMNS CAN ANSWER *who is the master account for this
    #: address*, AND THE ORDER IS RULED RATHER THAN LEFT TO A FUNCTION'S
    #: READING ORDER** (decision log 2026-09-22):
    #:   1. **THIS COLUMN** — the declaration. It wins whenever it is set.
    #:   2. `premises_owners.master_account_id` — the PRE-RULING declaration,
    #:      for rows written before today. Still read; still written wherever a
    #:      typed owner exists, so nothing that reads it starts answering less.
    #:   3. `accounts.premises_id` — *which premises this account covers*,
    #:      **never** *who owns this premises*. It is never promoted to answer
    #:      this one, and no code path writes it into this column. Both master
    #:      and regular accounts carry it, so promoting it would make every
    #:      tenant at an address a candidate owner of it.
    #:
    #: **`BR-MET-400`'s *declared, never inferred* SURVIVES AND IS NARROWED,
    #: NOT WEAKENED.** That rule retired the hallway derivation *"because a
    #: fallback that disagrees with the declared owner would silently bill a
    #: different party"*. This is a SHORTER CHAIN between the same two ends —
    #: premises and account — and it is still a read of a DECLARED column. What
    #: is narrowed is only WHICH declaration is read first.
    #:
    #: ⚠ **WHICH OF THE TWO ANSWERED IS SERVED ON EVERY READ**
    #: (`master_account_source`), and that is `BR-MET-1162`'s shape rather than
    #: a nicety: a unit may carry its own point or fall back to its building's,
    #: and the rule makes every screen showing a point say which of the two it
    #: is showing. Two declarations that can disagree owe a reader the same
    #: sentence, for the same reason — here it decides who is billed.
    #:
    #: ⚠ **NULLABLE, AND THE NULL IS A REAL STATE.** Every premises in every
    #: tenant predates this column and nothing backfills it: a row written
    #: before today declares nothing here and is answered by the owner record,
    #: which is precedence 2 doing its job. A backfill would be this module
    #: asserting a declaration nobody made.
    #:
    #: PROTECT, never CASCADE: an account twelve addresses are billed through
    #: must refuse deletion and say so — `premises_owners.master_account`'s own
    #: reasoning, one table over, about the identical fact.
    master_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="master_account_id",
        related_name="+",
    )
    #: ⛔ **THE UTILITY'S OWN PREMISE REFERENCE — AND SINCE CR-046 IT IS A
    #: MATCH KEY, NOT JUST A NOTE (BR-MET-403).**
    #: It was a GIS ref nothing read. Under the PO ruling of 2026-08-27 a
    #: premise NUMBER is issued by the tenant's `premises` series and is never
    #: taken from an uploaded file, so a migrating utility's own id has exactly
    #: one place to live and exactly one job: to make a corrected re-run of the
    #: SAME file update the rows it created instead of duplicating them.
    #: See the unique constraint below for the worked figure that decided it.
    external_ref = models.TextField(null=True, blank=True)  # the utility's own / GIS ref
    #: ── CR-028 AST-W5 (§10-D6 RULED 2026-08-22): the premises' coordinates ──
    #: A meter is where its premises is (B16 §4.6), so the map's geography
    #: lives HERE, not on the asset. NUMERIC(9,6), NULLABLE — NULL means
    #: "never geocoded", a real state the AST-03 map renders as no marker;
    #: no default, because 0,0 would draw the fleet in the Gulf of Guinea.
    #: Two writers only: the deterministic sample seed (no network) and the
    #: `geocode_premises` command (apps/metering/geocode.py — the §10-D6
    #: geocoder selection, recorded there with its worked address). A set
    #: value is never overwritten by either.
    #: ⚠ The map's AREA facts read the EXISTING `area` FK above (BR-MET-071)
    #: — B16 §6's proposed `premises_geo.area TEXT` was NOT added, because it
    #: would duplicate a column this model already carries (the same
    #: "reconcile, not duplicate" note §6 itself makes for test_frequency).
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.TextField(default="active")  # draft | pending | active | inactive
    #: ── CR-069 wave M · `OQ-INT-1471`, RULED 2026-09-04, option (b) ────────
    #: PO, verbatim: *"(b) type it, marked unchecked"*. When the city's address
    #: service cannot answer, a clerk still creates the property by typing the
    #: address — and THIS is the mark. It is cleared by the nightly parcel
    #: check when the city confirms the address (wave Q, on the Runbooks side
    #: of `BR-INT-054`).
    #:
    #: ⚠ **WHAT IT MEANS: THE CITY HAS NOT CONFIRMED THIS ADDRESS** — which is
    #: WIDER than the one case every document described until `DEF-INT-4266`.
    #: It is set on three of the four paths through the create form: the City
    #: was unreachable and the clerk typed the address (`OQ-INT-1471`'s ruled
    #: branch, and the case that made the column necessary); the clerk typed
    #: an address without searching at all; and the clerk saw the candidates
    #: and typed her own anyway. It is NOT set on the fourth — a candidate
    #: picked from the City's own list, re-checked live at the write. All
    #: three marked cases are the same fact, and the conservative reading is
    #: the correct one: an address the City never confirmed is exactly what
    #: the question warned about, whether the City was down or nobody looked.
    #:
    #: ⚠ **THE MARK IS THE WHOLE RULING, WHICH IS WHY IT IS A COLUMN AND NOT A
    #: KEY IN `custom_data`.** The danger `OQ-INT-1471` named is that a
    #: property written against a parcel the City may have split since *"looks
    #: identical on screen to the good case"*. A mark nothing renders is
    #: hard-won law 2, not compliance — so it is served by
    #: `selectors.premises_detail_dict` and drawn wherever a premises is read.
    #:
    #: `False`, never `None`: a premises created any other way was not typed
    #: past an unreachable city, and a third state would invite a screen to
    #: guess what *unknown* meant.
    gis_unchecked = models.BooleanField(default=False)
    #: ── CR-089 wave A · WHO CONFIRMED THE PLACEMENT, AND WHEN ──────────────
    #: PO ruling 2026-09-08 (decision log, *Premises & Units, second round*):
    #: the flag above *"becomes **Checked against GIS**, with who and when"*.
    #:
    #: ⚠ **THE FLAG ALONE COULD NOT ANSWER THAT, AND IT IS WORTH SAYING WHY IT
    #: IS TWO COLUMNS AND NOT A READ OF `audit_log`.** The audit trail does hold
    #: the row that flipped it — and `audit_log` is **pruned on a retention
    #: schedule** (CLAUDE.md hard rule 4 says so in terms, and whether any row is
    #: exempt is `OQ-1340`, OPEN). A screen that named a person out of a table
    #: that will be swept would print *Checked · D. Whitfield, 8 Sep 2026*
    #: today and *Checked · —* after the sweep, with nothing anywhere saying a
    #: fact had decayed. A fact a screen must state is a fact the row must hold.
    #:
    #: **NEITHER IS AN ADDRESS AND `G85` IS UNMOVED BY THEM.** They say who
    #: looked and when, not where anything is.
    #:
    #: Both NULL on all 673 existing properties, and that is the honest state:
    #: `gis_unchecked` has been `false` on every one of them since it was added,
    #: because `false` is its DEFAULT and no person has ever checked one. So a
    #: screen reads the PAIR — `gis_unchecked=false` with no `gis_checked_at` is
    #: *Not checked yet*, exactly like `gis_unchecked=true` — and neither is
    #: drawn as *Checked* on the strength of a default nobody chose (hard-won
    #: law 3: the unsafe reading must be the one somebody types).
    gis_checked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="gis_checked_by",
        related_name="+",
    )
    gis_checked_at = models.DateTimeField(null=True, blank=True)
    #: ── 2026-09-17 · `BR-MET-1173` — THE CITY'S PARCEL ID, IN ITS OWN COLUMN ──
    #: The City of Ann Arbor publishes an ArcGIS Feature Service of qualified
    #: addresses and the utility wants it as the source of addresses. `PIN` is
    #: the City's parcel key; this is where it lives.
    #:
    #: ⚠ **NOT `external_ref`, AND THE REASON IS A COLLISION THAT WOULD HAVE
    #: LANDED ON A REAL MIGRATING UTILITY.** `external_ref` above is
    #: `BR-MET-403`'s **import match key** — the id the utility's PREVIOUS
    #: software printed on every work order — and it carries
    #: `uq_premises_tenant_external_ref_ci`, one value per tenant,
    #: case-insensitively. A migrated utility already has values there. Writing
    #: the City's parcel key into the same column would be refused by that index
    #: on the first run, and would reach the clerk as *the parcel is already on
    #: another property* about a property that has no parcel at all. *What our
    #: old system called this* and *what the City calls this* are two facts.
    #:
    #: ⚠ **`CR-069` WAVE M'S ADDRESS SEARCH DID EXACTLY THAT** — it writes
    #: `"external_ref": candidate.get("parcel")` in
    #: `apps/integrations/seams/metering.py` — and it is corrected in the same
    #: commit as this column, not left for somebody to find.
    #:
    #: **STORED AS THE CITY GIVES IT, COMPARED CASE-INSENSITIVELY.** No unique
    #: index: `BR-INT-073`'s *two premises on one parcel* is a real thing a City
    #: does (a duplex split into two properties on one lot) and is a QUEUED
    #: DIFFERENCE for a person to judge, never a write the database refuses.
    gis_parcel_id = models.TextField(null=True, blank=True)
    #: ⚠ **WHAT THE KEY USED TO BE, AND WHEN IT CHANGED** (`BR-MET-1173`).
    #: A City splits, merges, annexes and renumbers parcels; ruling 7 of
    #: 2026-09-17 says we re-derive the new key by ADDRESS matching when the old
    #: one stops resolving. **A wrong key means faithfully copying the wrong
    #: parcel's data forever**, quietly, and this pair is the only way anybody
    #: finds out why six months later.
    #:
    #: It is on the ROW and not only in `audit_log` for `gis_checked_by`'s own
    #: reason one screen up: `audit_log` is pruned on a retention schedule
    #: (hard rule 4; `OQ-1340` asks whether any row is exempt and is OPEN), and
    #: this is a fact about the row's IDENTITY rather than an action somebody
    #: took. Both NULL until a key is actually REPLACED — a first key being
    #: stored is not a change.
    gis_parcel_id_was = models.TextField(null=True, blank=True)
    gis_key_changed_at = models.DateTimeField(null=True, blank=True)
    #: The City's own `Status` for this address record. ⚠ **STORED AS GIVEN AND
    #: NEVER FILTERED** — we do not know their vocabulary, we are not the ones
    #: who decide what *RETIRED* or *PROVISIONAL* means to them, and a row we
    #: dropped because we did not recognise its status is a row nobody can see
    #: we dropped. Ruling 10 of 2026-09-17: *"it is city problem our job is the
    #: keep parcel ID updated"*.
    gis_status = models.TextField(null=True, blank=True)
    #: **THE CITY CONFIRMED THIS ROW, AND WHEN.** Distinct from `gis_unchecked`
    #: above, which is about how the row was CREATED (a clerk typed past an
    #: unreachable City). This is about the last time a reconciliation run
    #: actually found this premises in the City's layer. ⚠ **A run with mode
    #: `preview` NEVER STAMPS THESE** — a preview that left a trail would be a
    #: write, and `BR-INT-074` says a preview writes nothing at all.
    gis_verified = models.BooleanField(default=False)
    gis_verified_at = models.DateTimeField(null=True, blank=True)
    #: r17.2 — tenant-defined VALUES for the `custom_field` definitions tenancy
    #: owns. A column on the OWNING row rather than a shared value table: a
    #: shared table would be written by customers, metering AND assets, which
    #: DB-16/§2 forbids as a cross-module write, and this rides BR-AUD-003's
    #: whole-row before/after with no new audit code. DB-17: no money path may
    #: read it except `apps/billing/custom_snapshot.py` (G6 enforces).
    custom_data = models.JSONField(default=dict, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # config → soft delete (IS-1)

    class Meta:
        db_table = "premises"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "premise_no"], name="uq_premises_tenant_premise_no"
            ),
            # ── CR-046 C5 · BR-MET-403 — UNIQUE PER TENANT, CASE-INSENSITIVELY,
            # PARTIAL. The `uq_assets_tenant_external_ref_ci` posture (BR-AST-049)
            # on the same fact one table along, which is itself
            # `customers.external_ref`'s (BR-CUS-054).
            #
            # **The worked figure.** A utility loads 428 premises. `premise_no`
            # is blank throughout under the 2026-08-27 ruling, so we issue
            # `P-00001 … P-00428`. They find nine rows with the wrong postal
            # code and re-cut the SAME file. Their file holds no SMARTBillHub
            # number — it never did — so under number-only matching all 428 rows
            # read as NEW: 428 second premises, `P-00429 … P-00856`, two records
            # for every address and no way to tell the sets apart. With this
            # key: 428 matches, 9 updates, 419 no-ops.
            #
            # CASE-INSENSITIVE because `GIS-118` and `gis-118` are one property
            # in every legacy export. PARTIAL because a premises created by the
            # PRM-02 form has no legacy reference at all and N of those coexist.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_premises_tenant_external_ref_ci",
            ),
        ]


class Unit(models.Model):
    """Metered space (B2 `units` + US-MET-002/003 §5 PROPOSED-SCHEMA columns).
    NO occupancy column — derived from the active account (BR-MET-036); NO
    stored unit status (computed display only)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    premises = models.ForeignKey(Premises, on_delete=models.PROTECT, db_column="premises_id")
    unit_no = models.TextField(null=True, blank=True)  # tenant numbering series
    label = models.TextField()  # 'Unit A', '200'
    #: ⛔ **CR-046 C5 · `BR-MET-404` — THE UTILITY'S OWN UNIT REFERENCE.**
    #: New 2026-08-27. Under the ruling of that day a unit NUMBER is issued by
    #: the tenant's `unit` series and never read off a file, so the id the
    #: utility's previous software printed on every work order had nowhere to
    #: go and would have been LOST at import. This is where it goes.
    #: ⚠ It is NOT the unit's identity — see the two constraints below: this
    #: table's mandatory identity is `(premises, label)`. It is a MATCH KEY for
    #: a re-run, which is a different job.
    external_ref = models.TextField(null=True, blank=True)  # the LEGACY id
    unit_type = models.TextField(null=True, blank=True)  # residential | residential_submetered |
    #   commercial | commercial_master | common_area (US-MET-002 §5 option set)
    floor_label = models.TextField(null=True, blank=True)
    square_feet = models.IntegerField(null=True, blank=True)
    #: ── CR-089 wave A · `BR-MET-1162` (PO ruling 2026-09-08) — THE UNIT'S OWN
    #: MAP POINT, AND IT NARROWS A SIGNED RULE RATHER THAN SLIPPING PAST ONE.
    #: PO verbatim: *"youa re correct address is on premsies/property - but GIS
    #: data for unit might change and hence we have to have parcel ID and GIs
    #: details on Unit also"*, confirming the reading put back to them: *"The
    #: address half stands. The coordinate half narrows: a unit may carry its
    #: own point and parcel, and where it does, that is the truth for that
    #: unit. Where it does not, it uses its building's."*
    #:
    #: ⚠ **THE ADDRESS HALF OF `BR-MET-1161` IS UNTOUCHED AND THIS TABLE STILL
    #: DECLARES NO ADDRESS COLUMN.** A unit refines a premises by LABEL. What
    #: is allowed to differ is a POINT ON A MAP, for the case the rule was
    #: never written for — a cabin in a park, a pad, a wing of a campus, where
    #: the site office is somewhere the unit is not.
    #:
    #: **THE FALLBACK IS PART OF THE RULE, NOT AN IMPLEMENTATION DETAIL.** NULL
    #: here means *read the building's*, and every screen that draws a point
    #: says WHICH of the two it is showing (`selectors.unit_point`). Nothing
    #: backfills these: all 1,109 units carry none today and that stays correct
    #: — a unit's own point is opt-in by design, and making it required would
    #: mark every existing unit incomplete overnight for no gain (the decision
    #: log of 2026-09-08 records that as deliberately NOT decided the other way).
    #:
    #: ⚠ **`G85` COUNTS `lat`/`lng` AS ADDRESS-SHAPED AND WENT RED ON THE COMMIT
    #: THAT ADDED THESE TWO LINES — that is the guard working.** Its allow list
    #: moves in this same commit with the ruling quoted beside it, and CLAUDE.md
    #: hard rule 8 is stamped in the same commit, never before the code
    #: (hard-won law 1).
    #:
    #: NUMERIC(9,6), the same declaration and the same WGS 84 decimal-degree
    #: frame as `premises.lat`/`lng` above — one frame for one fact, so a pin
    #: read from a unit and a pin read from its building are comparable numbers.
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    #: ── 2026-09-17 · `BR-MET-1173` — THE CITY'S ADDRESS-POINT ID ────────────
    #: The City publishes a parcel key (`PIN`) **per lot** and an address-point
    #: key (`FULLPIN`) **per address point, i.e. per unit**. A four-flat shares
    #: one `PIN` across four `FULLPIN`s, which is exactly the premises/unit
    #: split this product already has — so the parcel key goes on `Premises`
    #: above and the point key goes here.
    #:
    #: ⚠ **NOT `external_ref`, FOR `Premises`' REASON ONE TABLE ALONG.**
    #: `unit.external_ref` is `BR-MET-404`'s LEGACY id — its own comment says
    #: so — under `uq_units_tenant_external_ref_ci`. A migrated utility already
    #: has values there.
    #:
    #: ⚠ **AND THIS IS NOT AN ADDRESS, WHICH IS THE ONLY REASON IT MAY SIT ON A
    #: UNIT AT ALL.** `BR-MET-1161`'s address half is untouched: this table
    #: still declares NO address column and a unit still refines a premises by
    #: LABEL. `BR-MET-1162` let a unit carry its own POINT; this carries the
    #: City's NAME for that point. `G85`'s `HOME_FIELDS` is deliberately NOT
    #: widened for it — see `BR-MET-1174`. A parcel or point id identifies a
    #: record in somebody else's register; nothing derives an address from it.
    gis_point_id = models.TextField(null=True, blank=True)
    #: What the point key used to be, and when it changed — `Premises`' pair,
    #: for the same reason and on the same ruling (`BR-MET-1173`).
    gis_point_id_was = models.TextField(null=True, blank=True)
    gis_key_changed_at = models.DateTimeField(null=True, blank=True)
    #: The City's own `Status` for this address point. Stored as given, never
    #: filtered — `Premises.gis_status`' reasoning applies unchanged.
    gis_status = models.TextField(null=True, blank=True)
    #: The City confirmed this unit, and when. A `preview` run never stamps it.
    gis_verified = models.BooleanField(default=False)
    gis_verified_at = models.DateTimeField(null=True, blank=True)
    # ⚠ cross-module FK → rating (reviewed set, B2 §2); binding semantics per
    # BR-CUS-014 / BR-MET-007.
    #
    # POINTS AT A **PLAN**, NOT A RATE SCHEDULE — PO ruling 2026-08-11.
    # It used to be `default_tariff_id → rating.Tariff`, i.e. ONE service's
    # prices. That could not hold what the product says a unit holds: the S16
    # panel reads "default plan", the change-plan flow picks a plan, and
    # `unit_plan_assignments` stores a `rate_plan_id`. A house on electric +
    # water + trash is on ONE plan; a tariff column could record only one of
    # its three services, so the assignment history was unwritable (its FK
    # would have failed) and the column was the single artefact in the product
    # disagreeing with every other. The plan resolves to a schedule per service
    # through `plan_rate_schedules`.
    rate_plan = models.ForeignKey(
        "rating.RatePlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="rate_plan_id",
    )
    plan_effective_from = models.DateField(null=True, blank=True)  # US-MET-003 §5
    plan_locked = models.BooleanField(default=False)  # gate changes behind permission
    vacant_standby_auto = models.BooleanField(default=False)
    #: BR-MET-101 (PO ruling 2026-08-21, option A of three): "A COMMON AREA IS
    #: A UNIT WITH A FLAG. A MASTER ACCOUNT IS AN ACCOUNT WHOSE PAYER IS THE
    #: OWNER. NEITHER NEEDS A NEW TABLE." This column is that flag. The ruling's
    #: accepted cost — "'unit' now means two things to a reader ... so the flag
    #: must be visible everywhere it matters, and the flag is what separates a
    #: common area from a vacant unit billed to the owner (BR-MET-094), which
    #: would otherwise be the same row" — is why every serialiser serves it and
    #: the screens draw it (r10's vocabulary: "Common", "3 + common").
    #: `unit_type` may ALSO read `common_area` (US-MET-002 §5's five types);
    #: the FLAG is the queryable fact and migration 0016 backfilled it from
    #: rows already typed that way.
    is_common_area = models.BooleanField(default=False)
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Premises
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "units"
        constraints = [
            # ⛔ **THIS ONE IS THE UNIT'S IDENTITY, AND CR-046 C3 ASKED THE
            # QUESTION OUTRIGHT: *is a unit identified by its number, or by its
            # label within a premises?* THE DATABASE ANSWERS IT HERE.**
            # `label` is NOT NULL and `premises` is NOT NULL, so every unit that
            # exists has this key and no two units can share it. That makes the
            # composite the identity — the one an import must match on for a row
            # that quotes no number, and the one a second insert of the same
            # unit would collide with. Decision log 2026-08-27, "THE UNIT'S
            # IDENTITY IS ITS LABEL WITHIN ITS PREMISES".
            models.UniqueConstraint(
                fields=["tenant", "premises", "label"], name="uq_units_tenant_premises_label"
            ),
            # ⚠ **AND THIS ONE IS UNIQUE *WHEN PRESENT*, WHICH IS NOT THE SAME
            # THING.** `unit_no` is NULLABLE, and Postgres does not collide
            # NULLs — so N units may carry no number at all and still be lawful
            # rows. A column that can be absent cannot be an identity; it is the
            # strongest STATEMENT an operator can make when they do quote one,
            # which is why the import matches on it FIRST and falls back to the
            # composite above.
            models.UniqueConstraint(fields=["tenant", "unit_no"], name="uq_units_tenant_unit_no"),
            # ── CR-046 C5 · BR-MET-404 — the same partial, case-insensitive
            # posture as `premises.external_ref` above and for the same reason:
            # a corrected re-run of a migration file must update its own rows.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_units_tenant_external_ref_ci",
            ),
        ]


class Cycle(models.Model):
    """Billing cycle (B2 `cycles` + US-MET-006 §5 PROPOSED-SCHEMA window/bill
    columns; BR-MET-009 — window/date validation is the config service's law).

    ⚠ **A CYCLE IS A DEFINITION, NOT A SCHEDULE (BR-MET-077, PO ruling
    2026-08-16).** Verbatim: *"here we are defining the defiantion of cycles
    and how many Routes (Premises and Units -> accounts in it) ; this is group
    by defination, here you define it"* — and then, closing the follow-up:
    *"you can capture the defaults , but allow suer to override it during
    actual run"*.

    So this table now holds TWO generations of columns and they are not the
    same kind of thing:

    ⚠ **THAT SECOND GENERATION IS GONE ENTIRELY — metering 0021 (RC-W5-T2)
    DROPPED FIVE OF ITS SIX COLUMNS AND metering 0023 (RC-W6) TOOK THE SIXTH.**
    `window_start` / `window_end` were one particular period's calendar dates
    from the 2026-08-08 modal; `read_day_from` / `read_day_to` were the
    day-of-month pair `start_day` + `days_to_complete` supersede; `due_day` was a
    day-of-month the due fact billing reads (`due_days`, a COUNT) never needed;
    and `bill_date` waited for OQ-344 to rule what replaced it (see the note
    where it stood).

    * `bill_day` is a **DAY-OF-MONTH DEFAULT**, 1–31: "this cycle normally bills
      on the 5th". The RUN prefills from it and the staff member may change it
      there; an override applies to that run and does NOT rewrite it (D9). Since
      OQ-344 (2026-08-23) it is also what a run with NO typed bill date resolves
      through — *"the bill day, in the month after the period ends"* — which is
      what let `bill_date`, the sixth and last legacy column, be dropped.

    **NO MONEY COLUMN EVER (BR-MET-078).** r10 SET-07.3 draws a *Late /
    penalty date* select; the PO removed it — *"you dont need late fees in
    this. so dont have anything related to money when you create route and
    cycles."* Grace lives once, on Billing defaults (BR-BIL-002/008). A
    `late_day` here would be a second screen that appears to decide when a fee
    starts, which is the whole failure the ruling avoided.

    ── CR-029 · THREE FIELDS ABOUT TIME, AND ONE GENERATION (D2) ─────────────
    PO, verbatim (pre-CR, 2026-08-23): *"routes and cycles are grouping only -
    so we will not tag late fees , etc - we can capture start day, frequency,
    monthly, weekly daily, biweekly, once in two months , quaterly etc and days
    to complete it ; give business names to frequence - 1 word."*

    So a cycle now captures **start day · frequency · days to complete**, and
    **the reading window is DERIVED, never stored** (B17 §2; the upgraded
    prototype says it as product copy on SET-07D — *"Derived, not stored"*).
    `apps/metering/schedule.py` owns that arithmetic.

    **AND THERE IS NOW ONE GENERATION.** `services._sync_cycle_schedule` used
    to keep both in step on every write; the S27 export, `apps/reports/
    dashboard_regions.py` ("closes in N days") and the read-staging context all
    read the derived window now, so there is nothing left to keep in step. A
    client that still SENDS the legacy day pair is understood — the ruled fields
    are derived from it — and nothing stores it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # '08-A'
    name = models.TextField(null=True, blank=True)  # BR-MET-077 · r10 SET-07.1
    #: BR-MET-077, **amended by CR-029** — one of the EIGHT business words in
    #: `schedule.FREQUENCIES` (Daily · Weekly · Fortnightly · Monthly ·
    #: Bimonthly · Quarterly · Semiannual · Annual). CR-006's three lowercase
    #: values (`monthly` · `bi_monthly` · `quarterly`) were mapped onto them by
    #: migration 0019 and are still ACCEPTED on write, mapped by
    #: `schedule.business_frequency` so an unmigrated client is understood.
    #: `read_schedules.frequency` is the SAME fact for the generation seed and
    #: is left alone here; RC-W2 retires that table.
    frequency = models.TextField(null=True, blank=True)
    #: CR-029 — *"start day"*. Day-of-month (1–31) for Monthly and slower; the
    #: weekday anchor for Weekly/Fortnightly; n/a for Daily (B17 §2's table).
    start_day = models.IntegerField(null=True, blank=True)
    #: CR-029 — *"days to complete it"*. **start day + N days IS the read
    #: window**, INCLUSIVE: a window opening on the 1st with 5 days to complete
    #: runs 1st–5th. This is what retires the legacy from–to day pair.
    days_to_complete = models.IntegerField(null=True, blank=True)
    #: **STAYS (D9).** The PO, verbatim 2026-08-23: *"when we configure Cycle we
    #: are provideing default values; mostly it wil remain as it is but user can
    #: over ride them during billing"* — so the bill day is a cycle DEFAULT and
    #: the RUN overrides it (`bill_runs.bill_date`). This SUPERSEDES the
    #: upgraded prototype's own footnote *"Bill and due dates belong to the run,
    #: not the cycle"*, which three screens carry and which is now wrong.
    bill_day = models.IntegerField(null=True, blank=True)  # ≥ the derived close day
    #: BR-MET-076 — draft | active | inactive. A DRAFT cycle is invisible to a
    #: bill run: it stamps no service point and `units_in_cycle` never sees it.
    status = models.TextField(default="active")
    #: r10 SET-07.4 *"First run Oct 1, 2026"* — the date the definition starts
    #: applying. Nothing already issued changes (hard rule 4).
    first_run_date = models.DateField(null=True, blank=True)
    # ⚠ **`bill_date` IS GONE — metering 0023, and it was the SIXTH AND LAST of
    # the legacy columns.** RC-W5-T2 dropped five and could not drop this one:
    # `apps/billing/issue.py::_due_terms_for` read it as the fallback bill date
    # for a run where the clerk typed none, and **no ruling said what replaced
    # it**. D9 kept `bill_day` — a DAY-OF-MONTH — and turning a day-of-month
    # into one run's bill DATE means choosing a month; the three candidate
    # readings sat up to a month apart and each started the late-fee clock
    # (BR-BIL-001) on a different day.
    #
    # OQ-344 closed it on 2026-08-23, PO verbatim: *"I'd say B - these are
    # defualt - user can override"* — **the bill day, in the month AFTER the
    # period ends**. Worked: bill day 5, due days 21, period 1–31 Aug → bills
    # 5 Sep, due 26 Sep. `apps/billing/runs.default_bill_date` is that
    # arithmetic and nothing reads a stored date any more.
    #: **STAYS (D9)** — the cycle's DEFAULT due-days, overridable by the run
    #: (`bill_runs.due_days`, CR-029 W1-T3). BR-BIL-024: due = bill date + this.
    due_days = models.IntegerField(null=True, blank=True)  # due date = bill_date + due_days
    #: MQ-033 (`CR-192-BRC10`, `BR-MET-1212`) — the read FORMAT this cycle's
    #: routes use unless a route names its own; NULL falls through to the
    #: service default (*"route → cycle → service"*). Only a PUBLISHED format
    #: is pointed at (`read_formats.set_pointer`); `metering/0080`.
    read_format = models.ForeignKey(
        "metering.ReadFormat",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="read_format_id",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cycles"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_cycles_tenant_code"),
        ]


class Route(models.Model):
    """Read route (B2 `routes` + US-MET-005/006 §5 PROPOSED-SCHEMA columns).
    Membership = route_memberships selection (BR-MET-033); the superseded
    sequence-range columns are deliberately absent (OQ-041 closure)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField(null=True, blank=True)
    route_type = models.TextField(null=True, blank=True)  # walk | drive | ami (ami via B7 seam)
    feeder_ref = models.TextField(null=True, blank=True)  # AMI-only ('F-01')
    #: BR-MET-073 (CR-006 SET-06 step 1) — ⚠ cross-module FK → tenancy.
    #: THE SERVICE IS WHAT MAKES THE REST OF THIS CR COHERENT: without it,
    #: *"a route can belong to only one cycle per service"* and *"premises
    #: already on another route for the same service"* have no field to be
    #: true of. NULLABLE because every route shipped before this column, and
    #: a route with no service is the legacy ALL-SERVICES route — which is why
    #: `RouteMembership` below carries TWO partial unique constraints and not
    #: one.
    service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    #: BR-MET-073 — the area/sub-area the route covers (⚠ cross-module →
    #: tenancy, same direction as `service` above). This is the route's OWN
    #: tag; it is NOT how membership is computed. Membership is the explicit
    #: premises selection of step 2, so a premises outside the route's area
    #: can still be on it — which happens in real utilities and is why the
    #: area is a label here and a FILTER there.
    area = models.ForeignKey(
        "tenancy.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="area_id",
    )
    notes = models.TextField(null=True, blank=True)  # r10 SET-06.1 "Gate codes, dogs, parking…"
    assigned_to = models.ForeignKey(  # ⚠ cross-module → identity; NULL = "System (auto-pull)"
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="assigned_to",
    )
    cycle = models.ForeignKey(  # BR-MET-010: one cycle per route at a time
        Cycle, on_delete=models.PROTECT, null=True, blank=True, db_column="cycle_id"
    )
    #: BR-MET-076 — draft | active | inactive (deactivate-first, IS-1).
    #: DRAFT is the third value CR-006 adds and it means "has never run": a
    #: draft route stamps no service point, so Reads and Billing cannot see
    #: it. INACTIVE still means "used to run and no longer does" and keeps
    #: every stamp it made — collapsing the two would either resurrect retired
    #: routes or erase history.
    status = models.TextField(default="active")
    #: CR-161-BRC10 W4 — the utility's OWN fields on a route (PO 2026-10-02,
    #: Part 2 row 12: *"Add / edit route · Route page"*). Typed on the route
    #: wizard (`ROUTE_FORM`), shown on the route page (`ROUTE_PAGE`). Captured
    #: and shown only — no read run, walk order or bill reads it (BR-TEN-048).
    #: `metering/0067`.
    custom_data = models.JSONField(default=dict, blank=True)
    #: MQ-033 (`CR-192-BRC10`, `BR-MET-1212`) — *"A route can override its
    #: cycle, and a cycle its service."* NULL falls through to the cycle's.
    #: Only a PUBLISHED format is pointed at; `metering/0080`.
    read_format = models.ForeignKey(
        "metering.ReadFormat",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="read_format_id",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # reserved for true delete

    class Meta:
        db_table = "routes"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_routes_tenant_code"),
        ]


class RouteMembership(models.Model):
    """Route membership by SELECTION with optional walk order (BR-MET-033 —
    US-MET-006 §5 verbatim shape: tenant_id, route_id, unit_id, walk_order
    NULL). walk_order unique within a route when set.

    ⚠ **A UNIT IS ON ≤1 ROUTE *PER SERVICE*, NOT ≤1 ROUTE (BR-MET-074).**
    The original constraint was `unique(tenant, unit)`, written when a route
    had no service. CR-006 gives a route one, and a house on water AND
    electric is legitimately read by two different crews on two different
    routes — so the old constraint made the product's own multi-service story
    unrepresentable.

    **WHY TWO CONSTRAINTS AND NOT ONE.** SQL treats NULLs as DISTINCT, so a
    single `unique(tenant, unit, service)` would happily let two legacy
    all-services routes (service NULL) both hold the same unit — the exact
    thing the original constraint existed to stop. So:

      * `service` SET      → unique over (tenant, unit, service)
      * `service` NULL     → unique over (tenant, unit)

    `service` is DENORMALIZED from `route.service` and stamped by
    `services._set_route_membership` on every write, because a constraint
    cannot reach through an FK to another table's column. It is therefore a
    copy, and the one rule about a copy is that exactly one place writes it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, db_column="unit_id")
    #: BR-MET-074 — stamped from `route.service`; see the class docstring.
    service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    walk_order = models.IntegerField(null=True, blank=True)  # optional (BR-MET-033)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "route_memberships"
        constraints = [
            # BR-MET-074: ≤1 route per service…
            models.UniqueConstraint(
                fields=["tenant", "unit", "service"],
                condition=Q(service__isnull=False),
                name="uq_route_memberships_unit_service",
            ),
            # …and ≤1 all-services route, because NULLs are SQL-distinct.
            models.UniqueConstraint(
                fields=["tenant", "unit"],
                condition=Q(service__isnull=True),
                name="uq_route_memberships_unit_no_service",
            ),
            # walk order, when set, unique within the route.
            models.UniqueConstraint(
                fields=["route", "walk_order"],
                condition=Q(walk_order__isnull=False),
                name="uq_route_memberships_walk_order",
            ),
        ]


class RoutePremisesMembership(models.Model):
    """`CR-131-BRC07` — **WHICH PREMISES A HUMAN PUT ON THIS ROUTE.** The whole
    of what a route stores about who is on it.

    PO ruling 2026-09-22, verbatim: *"thi sis correct - The routes design —
    storing 726 unit rows instead of 6 premises, and the route going stale the
    moment anything changes … route should not be status - it is dynamically
    derive the details of units, assets meter acocount swithin it"*, and, in
    full the message before: *"deriving the units, assets and accounts is a
    danalmic process … when we need details of route or cycle - it should be
    deived at that time"*.

    **SIX ROWS, NOT 726.** A clerk editing `RT-006` at Ottumwa Water Works
    picked 6 premises carrying 726 units, and `route_memberships` tried to
    store one row per UNIT: step 3 drew *"No meters yet"* because the picker's
    URL reached 37,994 characters against a 4–8 KB limit, and step 4 sat on
    *"Working…"* for ever behind 726 `update_or_create` statements in one
    transaction holding the route row locked. Both are arithmetic on the same
    mistake — **the route materialised what it could ask for.**

    ⚠ **THE STALENESS IS THE BUG AND THE REST IS ITS SHADOW.** A per-unit
    membership is a PHOTOGRAPH: add a unit, fit a meter, move a tenant in, and
    none of it reaches the route until somebody re-opens the wizard and saves.
    Nobody will. Patching the URL to a POST would have made step 3 load and
    left a route that is wrong a week later.

    WHY A PREMISES SET IS STORED AT ALL, WHEN EVERYTHING ELSE IS DERIVED
    -------------------------------------------------------------------
    Because it is an ARBITRARY SET and not a rule. `routes.area` cannot say
    *these 6 of the area's 40*, and no tag in the product can. B17 §5 keeps
    exactly two jobs for stored rows — **explicit human choices** and
    **immutable history** — and this is the first of them at the grain a human
    actually works in. Units, meters and accounts are the second kind of thing
    and are asked for, never kept: `apps.metering.derivation` answers them.

    THE TWO CONSTRAINTS ARE `BR-MET-074`'s, LIFTED ONE GRAIN UP
    ----------------------------------------------------------
    A PREMISES is on ≤1 route **per service**. `service` is DENORMALIZED from
    `route.service` and stamped by `services._set_route_membership`, because a
    constraint cannot reach through an FK to another table's column — the same
    copy `route_memberships` already carried, with the same one rule about a
    copy: exactly one place writes it.

    ⚠ **TWO CONSTRAINTS AND NOT ONE, FOR THE REASON THE UNIT TABLE RECORDS:**
    SQL treats NULLs as DISTINCT, so a single `unique(tenant, premises,
    service)` would let two legacy all-services routes (service NULL) both hold
    the same premises — the exact thing the constraint exists to stop.

      * `service` SET  → unique over (tenant, premises, service)
      * `service` NULL → unique over (tenant, premises)

    ⚠ **IT CARRIES NO `walk_order`, AND THAT IS DELIBERATE.** The walk order is
    `route_premises_orders` — PO ruling 2026-08-23 *"Per premises"*, re-affirmed
    2026-09-22 *"a is okay"* — and a row there exists BECAUSE a human placed
    that stop, so *"on the route with no position"* is the ABSENCE of a row
    rather than a null in one. Two tables at the same grain answering two
    different questions is not duplication; putting the position here would
    make *on the route* and *third stop* one fact, which they are not.

    ⚠ **`route_memberships` IS NOT DROPPED IN THE SAME BREATH.** A column — or a
    table — is retired after its readers move, never in the migration that
    supersedes it, which is the discipline `RoutePremisesOrder` records about
    the column it replaced. `CR-131-BRC07` step 8 owns the retirement.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    premises = models.ForeignKey(Premises, on_delete=models.PROTECT, db_column="premises_id")
    #: BR-MET-074 — stamped from `route.service`; see the class docstring.
    service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "route_premises_memberships"
        constraints = [
            # BR-MET-074 at premises grain: ≤1 route per service…
            models.UniqueConstraint(
                fields=["tenant", "premises", "service"],
                condition=Q(service__isnull=False),
                name="uq_route_premises_members_service",
            ),
            # …and ≤1 all-services route, because NULLs are SQL-distinct.
            models.UniqueConstraint(
                fields=["tenant", "premises"],
                condition=Q(service__isnull=True),
                name="uq_route_premises_members_no_service",
            ),
        ]


class RouteMeterExclusion(models.Model):
    """BR-MET-075 — a meter that is on a member premises but NOT read on this
    route. r10 SET-06.3: *"All are included by default — untick any that
    should be read elsewhere"*; CR-006: *"Excluded meters remain on the
    premise but off the route."*

    **AN EXCLUSION IS A ROW HERE, NEVER A CHANGE TO THE ASSET.** Unticking the
    fire line on the drive-by route must not delete the meter, un-meter the
    premises, move its service point or change what it bills — it must change
    ONE thing, which crew sheet it appears on. Storing the negative keeps
    every one of those properties true by construction, and it keeps the
    default correct as membership grows: a premises added tomorrow brings its
    meters IN without anyone re-ticking them, because inclusion is the absence
    of a row.

    Consequence the wizard states out loud (*"151 of 153"*): a route's meter
    count is `meters on member units − exclusions`, and both halves are shown
    so an exclusion is never invisible.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    #: ⚠ cross-module FK metering→assets (the reviewed set, B2 §2) — the same
    #: direction `meter_reads.asset_id` already takes.
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, db_column="asset_id")
    #: CR-029 (B17 §6) — *"`route_meter_exclusions.reason` — two words, shown in
    #: place"*. SET-06D's Assets tab renders the exclusions explaining themselves
    #: where they sit: *"MTR-W2262 excluded · premise demolished"*. Without a
    #: column the reason lives in whoever unticked the box, and the next staff
    #: member re-ticks it. NULLABLE, because every exclusion made before this
    #: column has no reason to backfill and inventing one would be worse than
    #: the blank the screen draws.
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "route_meter_exclusions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "route", "asset"], name="uq_route_meter_exclusions"
            ),
        ]


class RouteService(models.Model):
    """CR-029 D10 — **a route serves a SERVICE SET**, not one service.

    PO, verbatim 2026-08-23: *"yes it will be multi service"*. The upgraded
    prototype draws RT-001 as **"Water + Electric"**, and until this table there
    was no field that sentence could be true of: `routes.service_id` is one FK.

    ⚠ **`routes.service_id` IS KEPT AND IS ALSO COPIED IN HERE** — the choice
    migration 0020 states and argues in its docstring. The head column stays
    because `route_memberships.service` denormalizes from it and BR-MET-074's
    two partial unique constraints key on it; moving membership off it is
    **RC-W4's** run-time resolution (D4), not a schema change that rides this
    wave. So the set is the new truth for what a route READS, and the head is a
    transitional projection of the set's first member.

    ⚠ **THE CONSEQUENCE, STATED RATHER THAN HIDDEN (hard-won law 1).** While the
    head is a single service, a "Water + Electric" route enforces per-service
    membership uniqueness for WATER only — so the same unit could also join an
    electric route and be read twice. No constraint here can close that: the fix
    is D4's derived membership, and this lane has REPORTED it rather than
    inventing a rule the PO has not been asked about.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    #: ⚠ cross-module FK → tenancy (the reviewed set, B2 §2) — the same edge
    #: `routes.service_id` and `route_memberships.service_id` already take.
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "route_services"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "route", "service"], name="uq_route_services"
            ),
        ]


class RoutePremisesOrder(models.Model):
    """CR-029 D11 — **the walking order is PER PREMISES**: one stop, many meters.

    PO, verbatim 2026-08-23: *"Per premises"*. The Premises tab's per-unit
    numbering (0142/0143 on 1408 Elm) is the wrong reading of the screenshot;
    Cedar Ct's three units sharing 0145 is the right one — a reader walks to an
    ADDRESS and reads everything there.

    ⚠ **`route_memberships.walk_order` IS SUPERSEDED AND HAS NEVER BEEN
    WRITTEN.** B17 §5 gap G5: it exists, it carries a uniqueness constraint, and
    it has **no writer** — no screen shows it and no route sheet consumes it. So
    this table is not a migration of a working feature; it is the first home the
    walk order has ever had at the grain the PO ruled. The old column stays
    until RC-W5 for the reason every legacy column in this CR stays: a column is
    dropped after its readers move, not in the migration that supersedes it.

    THE FIRST WRITER IS RC-W3-T3's drag-to-reorder. This wave gives the sequence
    a home and the two constraints a route SHEET depends on; the screen that
    fills it lands with the route detail.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    premises = models.ForeignKey(Premises, on_delete=models.PROTECT, db_column="premises_id")
    #: The stop number. NOT NULL — a row here exists BECAUSE a human placed this
    #: stop, so "on the route with no position" is the ABSENCE of a row, not a
    #: null in one. That is the same shape `route_meter_exclusions` uses for
    #: inclusion (BR-MET-075: the default is the absence of a row).
    walk_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "route_premises_orders"
        constraints = [
            # One stop, one position on this route.
            models.UniqueConstraint(
                fields=["tenant", "route", "premises"], name="uq_route_premises_orders_stop"
            ),
            # …and one position, one stop — because a printed route sheet with
            # two number 3s is a sheet a reader cannot follow.
            models.UniqueConstraint(
                fields=["route", "walk_order"], name="uq_route_premises_orders_walk_order"
            ),
        ]


#: CR-029 D1 — the two results a closed read window may carry, from the PO's own
#: screenshot (SET-06D.audit's Read history) and B17 §7 W2-T1's worked row
#: *"196 · 196 · Complete"*. Two values, and a third would be a status
#: vocabulary nobody ruled. Title case because this CR's business words are the
#: PO's own — the same reason `schedule.FREQUENCIES` reads `Monthly` and not
#: `monthly`.
READ_WINDOW_RESULTS: tuple[str, ...] = ("Complete", "Incomplete")


class ReadWindow(models.Model):
    """CR-029 D1 — **a read window is a first-class, CLOSABLE record.**

    PO ruling 2026-08-23: *"D1 - yes"*. B17 §6: *"Read windows become
    first-class closable records (window · reader · collected · expected ·
    skips · result) replacing the writerless `read_schedules`"*, and SET-06D's
    Audit tab is the acceptance shape — **Window · Read on · Reader · Collected
    · Expected · Result**.

    WHAT IT REPLACES, AND WHY THE REPLACEMENT IS NOT A RENAME. `read_schedules`
    holds a cycle, a frequency and a `last_generated_period` bookmark: it is a
    GENERATOR's state, it has never had a writer, and it has zero rows (B17 §5
    gap G1). This table holds the opposite kind of fact — what actually happened
    on one route in one window, closed and countable. RC-W2 retires the old
    table; this wave does not delete it, because a table is dropped after its
    story is written, not before.

    THE GRAIN IS THE ROUTE, because the Read history that renders these rows is
    a ROUTE's (SET-06D.audit) — *"this route was read on the 4th, 196 of 196"*.
    `cycle` rides along because the window's dates DERIVE from the cycle's
    schedule (`apps/metering/schedule.py`), and a window whose cycle later moves
    still knows which calendar produced it.

    THE COUNTS ARE NULLABLE AND THE RESULT IS NULLABLE **while the window is
    open**. A window that has not closed has not counted anything, and a 0 there
    would read as "nothing collected" — the same false claim `route_dict`
    already refuses to make for `collected` (BR-MET-011).

    NO MONEY, EVER (BR-MET-078, hardened by this CR). A read window counts
    meters; the amount they bill to is the bill run's business.

    ⚠ **NO WRITER LANDS IN THIS WAVE, AND THAT IS THE RULED SPLIT.** B17 §7
    W2-T1: *"Closing a window writes the W1-T4 record"*. What W1-T4 owes is that
    every fact on the screenshot has a column behind it and that nothing beyond
    the screenshot was invented — asserted in both directions by
    `tests/test_cr029_rcw1_route_model.py`.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, db_column="route_id")
    cycle = models.ForeignKey(
        Cycle, on_delete=models.PROTECT, null=True, blank=True, db_column="cycle_id"
    )
    #: The WINDOW column of the Read history — the derived period this record
    #: closes. Stored on the RECORD (not derived at read time) because a closed
    #: window is history: changing the cycle's schedule tomorrow must not restate
    #: which days a crew walked last month (the FROM-NEXT rule, SET-07D).
    period_start = models.DateField()
    period_end = models.DateField()
    #: READ ON — the day the route was actually walked. NULL while open.
    read_on = models.DateField(null=True, blank=True)
    # ⚠ **THERE IS NO `reader` COLUMN, AND ITS ABSENCE IS A RULING (OQ-343).**
    # This table carried `reader` — a cross-module FK to identity recording WHO
    # WALKED a closed window, taken verbatim from the PO's SET-06D.audit
    # screenshot (*"Aug 2026 · Aug 3 · M. Chen · 196 · 196 · Complete"*). D6 had
    # ruled *"not required"* against reader ASSIGNMENT, and whether that reached
    # this HISTORICAL fact was genuinely unclear, so RC-W3c built the column and
    # left the screen column out rather than guess.
    #
    # The PO ruled it on 2026-08-23, verbatim: *"B: no reader anywhere, correct
    # the screenshot and drop the stored name"*. So the Read history is
    # **Window · Read on · Collected · Expected · Result**, the PO's own
    # screenshot is corrected rather than followed, and the column is dropped by
    # metering 0022 — the product does not keep data no screen shows.
    #
    # ⚠ **`routes.assigned_to` IS NOT TOUCHED AND MUST NOT BE.** It predates
    # CR-029, D6 explicitly preserved the ops tab's existing read-only reader
    # display, and the PO was not asked about it. Removing it would be a defect,
    # not thoroughness.
    collected_count = models.IntegerField(null=True, blank=True)
    expected_count = models.IntegerField(null=True, blank=True)
    #: SKIPS — meters the crew could not read (locked gate, dog, no access). A
    #: skip is neither collected nor missing-by-accident, and the Read history
    #: shows it as its own number so "196 of 200" is never silently "196 of 196".
    skip_count = models.IntegerField(null=True, blank=True)
    #: RESULT — one of `READ_WINDOW_RESULTS`. NULL while the window is open.
    result = models.TextField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_windows"
        constraints = [
            # One record per route per window. This is what makes closing a
            # window IDEMPOTENT for RC-W2's engine (CLAUDE.md rule 6's posture):
            # a second close finds the row rather than writing a second history.
            models.UniqueConstraint(
                fields=["tenant", "route", "period_start"], name="uq_read_windows_route_period"
            ),
            models.CheckConstraint(
                condition=Q(result__isnull=True) | Q(result__in=READ_WINDOW_RESULTS),
                name="ck_read_windows_result",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "route", "period_start"], name="ix_read_windows_route"),
        ]


class ServicePoint(models.Model):
    """One metered service at a unit (B2 `service_points`; r16 #3 catalog FK).
    Route/cycle stamps follow membership (BR-MET-033 drives route_id)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, db_column="unit_id")
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    route = models.ForeignKey(
        Route, on_delete=models.PROTECT, null=True, blank=True, db_column="route_id"
    )
    cycle = models.ForeignKey(
        Cycle, on_delete=models.PROTECT, null=True, blank=True, db_column="cycle_id"
    )
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Premises
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "service_points"
        indexes = [
            models.Index(fields=["tenant", "unit"], name="ix_service_points_tenant_unit"),
        ]


class ReadSchedule(models.Model):
    """Cycle-instance generation seed (B2 `read_schedules` + US-MET-006 §5
    PROPOSED-SCHEMA bookkeeping column).

    ⚠ **RETIRED BY CR-029 RC-W2-T1 (D1). DO NOT GIVE IT A WRITER.** It was the
    state of a generator this design does not have: `frequency` duplicates
    `cycles.frequency` and `last_generated_period` is a bookmark for a job that
    walks the calendar in the background. The ruled model derives a cycle's next
    windows ON DEMAND from start day · frequency · days-to-complete · first run
    (`apps/metering/period_engine.py`), so there is no generation to bookmark and
    nothing here can go stale — because nothing here is read.

    It has had **no writer and zero rows** since it was created (B17 §5 gap G1).
    What replaced it is `ReadWindow` above, which holds the opposite kind of
    fact: what actually happened on one route in one window, closed and
    countable.

    **STILL PRESENT ON PURPOSE.** `services.delete_cycle` clears any row before
    deleting a cycle (the FK is PROTECT), and a table is dropped after its story
    is written, not before — RC-W5 drops it (B17 §7 W5-T2).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, db_column="cycle_id")
    frequency = models.TextField()  # 'monthly' (B2; full set UNKNOWN — value stays free text)
    last_generated_period = models.DateField(null=True, blank=True)  # generation bookkeeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_schedules"


# ── W2 reads lane ──────────────────────────────────────────────────────────
# Vocabularies. TextFields per the W0 pattern (r5 #20) — the CONFIRMED value
# sets live here as module constants so a typo is one grep from its law, not a
# magic string at a call site.

# B2 r8 / BR-MET-059 (PO RD-1 Option B) — extensible by adding a value, never
# by changing the schema. A flat meter uses `total` only.
CHANNELS: tuple[str, ...] = (
    "total",
    "tou_on",
    "tou_mid",
    "tou_off",
    "export",
    "demand",
    "generation",
)
CHANNEL_TOTAL = "total"
#: BR-AST-029 (US-AST-011/012): the net meter's EXPORT record — energy fed back
#: to the grid, which is NOT consumption and is never added to it.
#:
#: ⚠ WHY THERE IS NO `read_type` COLUMN, although both assets stories name one.
#: EP-AST-05 was written against B2 addendum **r7** (`meter_reads.read_type`
#: enum consumption|export, UNIQUE (asset, read_at, read_type)). B2 addendum
#: **r8** SUPERSEDES r7 in the database brief's own words — *"`meter_reads.
#: read_type` (r7) GENERALIZES to `channel`: enum total | tou_on | tou_mid |
#: tou_off | export | demand"* — and BR-MET-059 (PO RD-1 Option B) says the same
#: from the rules side: *"Generalizes the A-6 read_type decision"*. EP-MET-03
#: §US-MET-017 spells out the consequence: *"the channel model generalizes J2's
#: read_type note per BR-MET-059"*.
#:
#: So the two-RECORD model BR-AST-029 requires is implemented exactly — a net
#: cycle is one `total` record and one `export` record sharing a `read_at`,
#: unique on (asset, read_at, channel), corrections by supersede — and the
#: r7 COLUMN is deliberately not built, because r8 replaced it. `read_type` is
#: still served on every read payload as a DERIVED field (see
#: selectors.read_type_of) so the US-AST-012 TC-3 contract keeps its pinned
#: field name. This is implementing the later signed law, not choosing between
#: two open options — and it is written down here because the next agent
#: reading EP-AST-05 alone would otherwise add the column.
CHANNEL_EXPORT = "export"
#: BR-RAT-014's measurement: the MAX-DEMAND register. Named 2026-08-16 when the
#: demand pricing engine landed — it is in `CHANNELS` above and had no constant,
#: so every reader spelled it as a literal.
#:
#: ✅ **ITS UNIT IS THE REGISTER'S OWN — `kW` (BR-MET-143, PO 2026-08-27,
#: closing OQ-391 and DEF-797).** This note said *"its unit is the meter's own
#: (kW), which is NOT the unit of the energy register beside it (kWh)"*, and the
#: parenthesis was a claim the code did not keep: `_post_row` stamped
#: `unit=asset.unit` for EVERY channel, so a peak on an electric meter was
#: stored **kWh** while `rate_schedules.demand_rate_per_kw` priced it per kW —
#: hard-won law 1, a comment claiming a guarantee that was not the guarantee.
#: The unit is now recorded PER REGISTER (`register_units.register_unit`), so
#: the sentence is finally true: kWh on the energy register, kW on this one.
#:
#: ⚠ **AND IT IS A MAXIMUM, NOT A RUNNING TOTAL** — `register_units.
#: MAXIMUM_REGISTERS`. BR-MET-051's *"manual demand-register value at cycle
#: read"* is its billable quantity; BR-MET-019's delta is not, and running that
#: delta over two peaks is the other half of DEF-797 (412 kW billed as 14 kWh,
#: $154.00 against $4,532.00).
CHANNEL_DEMAND = "demand"
#: **BR-MET-135 (PO 2026-08-26, CR-038 W6) — A DEVICE'S PRODUCED QUANTITY.**
#:
#: PO verbatim, asked which register a device's figure should land in:
#: *"please add generation"*. It completes BR-MET-124, where the same PO put
#: device readings IN scope: *"It is not out of scope we will ahve to accept
#: the reading if it comes; curently we are onboarding solar based utility and
#: they will need it"*. The driving case is a solar inverter's 612 kWh in a
#: month.
#:
#: ⚠ **`generation` IS NOT `export`, AND THE TWO MUST NEVER BE COLLAPSED.**
#: They are different equipment answering different questions:
#:
#:   · `export`     — a NET METER's grid-push register (BR-AST-029). It is
#:                    measured at the meter, it is lawful ONLY on an asset with
#:                    `net_metering` on, and it says how much energy went OUT to
#:                    the utility.
#:   · `generation` — a DEVICE's own production (`asset_types.category ==
#:                    behind_the_meter` — a PV inverter, a generator). It is
#:                    measured behind the meter, on equipment that has no
#:                    register in the meter sense, and it says how much energy
#:                    the site MADE. Most of it is usually consumed on site and
#:                    never crosses the meter at all.
#:
#: A site can have both, and adding them double-counts the exported half.
#: ⚠ **AND NEITHER IS EVER SUMMED WITH CONSUMPTION** — BR-MET-135 says so of
#: `generation` in as many words, and it is the same law CHANNEL_EXPORT carries.
#: `selectors._channel_quantities` keeps consumption's "everything else" bucket
#: exclusive of both; see its exclude list.
#:
#: **A NEW VALUE, NOT A SCHEMA CHANGE.** The list above is deliberately
#: extensible (B2 r8 / BR-MET-059, PO RD-1 option B) — adding a register means
#: adding a string here, and `meter_reads.channel` is a TextField for exactly
#: this reason.
CHANNEL_GENERATION = "generation"
#: The registers that are NOT consumption. Anything summed as "usage" must
#: exclude every one of them, and a new non-consumption register joins this
#: tuple in the same commit it joins CHANNELS.
NON_CONSUMPTION_CHANNELS: tuple[str, ...] = (CHANNEL_EXPORT, CHANNEL_GENERATION)
TOU_WINDOW_CHANNELS: tuple[str, ...] = ("tou_on", "tou_mid", "tou_off")

# B2 `meter_source` enum (US-MET-007 §5: too coarse for the six UI options, so
# `source_detail` carries the full value alongside it).
#
# ⚠ **NEITHER OF THESE IS THE READ METHOD ANY MORE — CR-038 W3, 2026-08-26.**
# BR-MET-123 (PO 2026-08-26), verbatim: *"we are only selectiing the soruce and
# accepting the CSV or excel file; thats is the scope right now; there is no
# integration yet; but it should not stop us from tagging the soruce and
# accepting the CSV or excel file"*. The SOURCE is a TAG chosen at upload, and
# its vocabulary is the tenant's own `read_methods` reference list (BR-AST-043,
# assets-owned, tenant-extensible). See `read_method` on ReadImportBatch /
# ReadImportRow / MeterRead below.
#
# ⚠ **THAT LIST IS EIGHT WORDS SINCE 2026-08-27, NOT THE FIVE THIS COMMENT USED
# TO NAME** — BR-MET-142 (PO ruling closing OQ-392) added Drive-by, Self-read
# and Field visit. **The consequence for the tuple below is the interesting
# one:** `SOURCE_DETAILS`' six legacy words now ALL translate, each to a method
# of the same name, so `legacy_read_method` guesses nothing and a row that said
# `drive_by` serves `drive_by` instead of *not stated*.
#
# The two tuples here are kept for exactly two reasons and no third:
#   1. HISTORY. Rows already on file carry these values, and hard rule 4 says a
#      committed read is never rewritten. `read_import.legacy_read_method`
#      derives a METHOD from them AT SERVE TIME; the stored words stay as they
#      were written (`selectors.read_dict` serves both, and says which is which
#      through `read_method_origin`).
#   2. 🔒 BR-MET-018's file+tags idempotency key hashes `source_kind` and
#      `source_detail` (read_import.IDEMPOTENCY_TAG_FIELDS). That key is a
#      CLAUDE.md sensitive path whose mechanics are the OQ-044 closure's, so
#      CR-038 W3 does NOT add the new tag to it — see the boundary note on
#      IDEMPOTENCY_TAG_FIELDS. REPORTED to the Eng-Lead.
#
# ⚠ **FOUR, NOT THREE, SINCE `BR-CWP-074` (PO 2026-09-04, built 2026-10-17
# under `DEF-CWP-10175`) — AND THAT SUPERSEDES B2 `meter_source`'s THREE.**
# PO verbatim: *"you will also ahve to flag that this reading is reacievd from
# Cosnumer"*. `customer` is the PROVENANCE flag on every reading a customer
# sends through the portal, clean or flagged. It is NOT `manual`: manual means
# a person the utility SENT. Its one writer is `customer_reads.py`; the staff
# upload's `SOURCE_KINDS` deliberately does not carry it.
READ_SOURCES: tuple[str, ...] = ("ami", "manual", "import", "customer")
SOURCE_DETAILS: tuple[str, ...] = (
    "walk_by",
    "drive_by",
    "self_read",
    "field_visit",
    "ami_itron",
    "ami_sensus",
)

#: The tenant-owned reference list the read METHOD is resolved against
#: (BR-AST-043 — `read_methods`, seeded AMI · AMR · walk-by · Manual · Mobile ·
#: Drive-by · Self-read · Field visit, the last three added 2026-08-27 by
#: BR-MET-142).
#: A CODE, not a table: metering never imports the assets models, it asks
#: `seams.assets_lookup_index(READ_METHOD_LIST_CODE)`. There is deliberately no
#: `READ_METHODS = (...)` tuple anywhere in this module — the allowed set is
#: DATA (BR-TEN-036), and a hardcoded copy here is the thing BR-AST-043 removed
#: from apps/assets/services.py in the first place.
READ_METHOD_LIST_CODE = "read_methods"

# BR-MET-021 A5 vocabulary + the BR-MET-052 catalog additions, both carried as
# the same PROPOSED-SCHEMA enum extension the rule names. `rollover` is this
# lane's ONE addition beyond those two lists: BR-MET-015/OQ-009 require a wrap
# to be "flagged for review" and name no flag for it — recorded as an Eng
# disposition in the build report rather than folded into an existing status.
READ_STATUSES: tuple[str, ...] = (
    "ok",
    "high",
    "low",
    "zero",
    "missing",
    "estimated",
    "days_threshold",
    "factor_flag",
    "mismatch",
    "negative_usage",
    "retired_meter",
    "vacant_unit",
    "tou_sum_sanity",
    "out_of_window",
    "rollover",
    "duplicate",
    "unknown_meter",
    "export_not_net",  # BR-AST-029 — an export record on a non-net asset
    # CR-038 W2 (2026-08-26): the mixed-cycle pair — both WARNING-tier
    # (BR-MET-122: never a hard refusal), so neither joins
    # selectors.UNBILLABLE_READ_STATUSES.
    "cycle_membership",  # BR-MET-122 — meter not in the batch's tagged cycle
    "service_coherence",  # row's stated service ≠ the meter's real service
    # BR-MET-126 (CR-038 W1b, 2026-08-26) — a BILLED read whose stored prior
    # went stale when the reading before it was corrected. The cascade may not
    # rewrite a billed row (rule 3 of BR-MET-126: "the system does not act
    # alone"), so it FLAGS it; this status is what lets the existing
    # needs_attention `flagged` count surface the recommendation with no new
    # counting machinery. Same Eng-disposition posture as `rollover` above:
    # a lane addition beyond the A5 list, REPORTED for vocabulary ratification
    # (HUMAN-REVIEW-PENDING — CR-038 W1b lane report / central ledger row).
    # Applied to ACTUAL reads only: a billed ESTIMATE keeps `estimated`,
    # because _standing_estimates and the BR-MET-029 true-up count standing
    # estimates BY that status and the flag must not break the arithmetic it
    # warns about (its recommendation lives in rule_outcomes alone).
    "stale_prior",
)

# BR-MET-053 lifecycle: staged → ok/flagged/estimated → committed → BILLED
# (locked). `status` above holds the ok/flagged/estimated half (one primary
# status per BR-MET-021); this column holds the committed→billed half. They
# are two different facts and US-MET-016 §5 maps both onto `status`, which
# cannot hold "high" and "billed" at once — Eng disposition, REPORTED.
READ_LIFECYCLES: tuple[str, ...] = ("committed", "billed")

# US-MET-008 §5 disposition set (per staged row).
DISPOSITIONS: tuple[str, ...] = (
    "accept",
    "accept_with_flag",
    "override",
    "estimate",
    "reject",
    "field_visit",
    "skip",
)
# Dispositions that produce a posted read at commit (US-MET-010 §1).
POSTING_DISPOSITIONS: frozenset[str] = frozenset({"accept", "accept_with_flag", "override"})

BATCH_STATUSES: tuple[str, ...] = ("staged", "validated", "posted", "discarded")
SOURCE_KINDS: tuple[str, ...] = ("csv", "manual", "ami_replay")

#: **BR-MET-128 (PO 2026-08-26, CR-038 W9 task 1) — AN EVENT READ RECORDS ITS
#: EVENT AND ITS USER.** PO verbatim: *"it will be as per event - bascially we
#: will ahve to create an record in reading that such reading ahs been
#: colelcted - and it is generated due to that event; + plus the user"*. One
#: context value per wizard event — the five lifecycle events, exactly as the
#: rule confirms them. The USER half of the rule rides the existing
#: `imported_by` (an event batch's `uploaded_by` is the acting user and
#: `_post_row` stamps it onto the read); only the EVENT had no column, so
#: `event_context` below is the minimal addition. `transfer` is deliberately
#: ONE value serving BOTH accounts: BR-MET-128's own clause — *"The transfer
#: case stores ONE read serving both accounts, its event `transfer`"* — the
#: same committed row closes one account's period and opens the next.
#:
#: ⚠ **EIGHT SINCE 2026-10-17, NOT FIVE (`DEF-WRK-10184`).** PO ruling of that
#: day (decision log *"WHERE A USER ENTERS A METER READING"*, gap 7): a field
#: job's readings are *"saved with the job's real event type, not always
#: `new_connect`"*. Three of the jobs a technician reads a meter on have no
#: lifecycle event among the five, so they are APPENDED (nothing renumbered,
#: nothing removed): **`reconnect`** (service restored), **`meter_read`** (a
#: check or meter-read visit — and the neutral answer for a job raised for no
#: lifecycle reason, never `new_connect`), **`exchange`** (a meter exchange).
#: There is NO database CHECK on `event_context` (migration 0035 adds a bare
#: text column), so no migration is needed; the mapping from a job to its event
#: lives in ONE place, `apps/work/seams/metering_seam.FIELD_READ_EVENT_BY_SOURCE`.
EVENT_CONTEXTS: tuple[str, ...] = (
    "move_in",
    "move_out",
    "transfer",
    "disconnect",
    "new_connect",
    "reconnect",
    "meter_read",
    "exchange",
)


class ReadValidationSettings(models.Model):
    """Tenant validation + estimation config (B2 r5 #15 — an APPROVED table,
    not PROPOSED-SCHEMA; metering-owned per r16 #11).

    BR-MET-020: **no threshold value is ever hardcoded**. The column defaults
    below are the PO-RATIFIED SEEDED DEFAULTS of B2 r5 #15 / the OQ-002 and
    OQ-003 closures — they apply when a ROW IS CREATED, and the engine never
    falls back to them when the row is ABSENT (US-MET-011 TC-9: a tenant with
    no config row fails safe — threshold rules are skipped and reported, never
    substituted). Seeding a row is provisioning's job; `services.
    ensure_read_validation_settings()` is the entry point it calls.

    The four columns marked S64-extension are US-MET-011 §5 PROPOSED-SCHEMA
    additions beyond r5 #15's list (zero scope, mismatch default, TOU sum
    tolerance) — each carries the value its CONFIRMED rule states."""

    id = uuid7_pk()
    tenant = models.OneToOneField("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    # High usage — OQ-002 closure: ratio AND absolute floor must BOTH breach.
    high_pct = models.DecimalField(max_digits=18, decimal_places=6, default=200)
    high_abs_kwh = models.DecimalField(max_digits=18, decimal_places=6, default=50)
    high_abs_kgal = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    low_pct = models.DecimalField(max_digits=18, decimal_places=6, default=25)
    # S64-card extension (US-MET-011 §5): active_non_vacant | all | off.
    zero_scope = models.TextField(default="active_non_vacant")
    # Read-interval day bounds — seeded 25–35 flag / 20–45 hard (r5 #15).
    days_flag_min = models.IntegerField(default=25)
    days_flag_max = models.IntegerField(default=35)
    days_hard_min = models.IntegerField(default=20)
    days_hard_max = models.IntegerField(default=45)
    # S64-card extensions (US-MET-011 §5): BR-MET-025 default tolerance and the
    # BR-MET-052 ±1% TOU sum-sanity tolerance as config, not a constant.
    mismatch_default_pct = models.DecimalField(max_digits=18, decimal_places=6, default=3)
    tou_sum_tolerance_pct = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    # Estimation (OQ-003 closure — BR-MET-026/027 defaults, tenant-changeable).
    est_method = models.TextField(default="trailing_3_daily_avg")
    est_max_consecutive = models.IntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_validation_settings"


class ReadValidationServiceSettings(models.Model):
    """One utility service's VEE thresholds for one tenant — CR-038 Amendment 1
    (PO 2026-08-26, verbatim: *"we will ahev to set these rules in settings and
    take it from there, we will provide default value to start with on all
    these rules"*), scoped **per (tenant, service)**.

    The row the engine resolves FIRST: `validation.resolve_config` prefers this
    row for the read's service, falls back to the legacy tenant-wide
    `ReadValidationSettings` row for **electric and water only** (the two
    services whose figures OQ-002 actually ratified — its floors are kWh/kgal),
    and for any other service with no row here the threshold rules are SKIPPED
    AND REPORTED, never defaulted (BR-MET-020 / US-MET-011 TC-9 fail-safe,
    unchanged).

    **Deliberately NO column defaults on the threshold columns.** The parent
    row's column defaults are lawful because ONE ratified figure set exists for
    it; here the ratified figures differ per service (electric 50 kWh vs water
    1 kgal) and for eight services NO figure is ratified at all (CR-038 A1
    Open 5). A column default would bake one service's number into every
    service's row creation — the exact guess BR-MET-020 forbids. Seeding is the
    explicit job of `services.ensure_read_validation_settings()`, which writes
    only the PO-ratified electric/water figures; a tenant CREATES any other
    service's row itself through S64 with its own figures.

    The floor is **unit-aware** (CLAUDE.md rule 3): `high_abs_value` is
    meaningless without `high_abs_unit`, so they are one fact in two columns —
    the service's own unit (kWh, kgal, ccf…), compared case-insensitively and
    converted only through the tenant's configured factor (OQ-004: never a
    silent conversion).

    Estimation parameters stay TENANT-WIDE on `ReadValidationSettings` (CR-038
    A1 scopes "the service-shaped values"; est_method/est_max_consecutive are
    not service-shaped and did not move). The legacy `high_abs_kwh`/
    `high_abs_kgal` columns there stay lawful containers for the fallback.

    DecimalField(18,6): percentages stored to 6dp (CLAUDE.md hard rule 2,
    PO re-sign 2026-08-22), displayed 2dp; no money lives here.

    ⚠ **`rule_enabled` (BR-MET-136, PO 2026-08-26) is the one column here that
    is NOT a threshold** — it is the per-rule ON/OFF switch, and its own
    docstring below argues the JSONB-map-vs-boolean-columns choice and why
    absent-means-enabled is what makes "default all enabled" cost nothing."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    # FK, not a text code: metering's durable rows (ServicePoint, Route, Cycle)
    # all reference the platform catalog this way; text codes are batch TAGS.
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    # High usage — OQ-002 shape: ratio AND absolute floor must BOTH breach.
    high_pct = models.DecimalField(max_digits=18, decimal_places=6)
    high_abs_value = models.DecimalField(max_digits=18, decimal_places=6)
    high_abs_unit = models.TextField()  # the service's OWN unit — rule 3
    low_pct = models.DecimalField(max_digits=18, decimal_places=6)
    zero_scope = models.TextField()  # active_non_vacant | all | off
    # Read-interval day bounds (flag window must sit inside the hard window —
    # service-enforced on every write, mirrored on the S64 form).
    days_flag_min = models.IntegerField()
    days_flag_max = models.IntegerField()
    days_hard_min = models.IntegerField()
    days_hard_max = models.IntegerField()
    mismatch_pct = models.DecimalField(max_digits=18, decimal_places=6)
    tou_sum_tolerance_pct = models.DecimalField(max_digits=18, decimal_places=6)
    # ── BR-MET-136 (PO 2026-08-26, CR-038) — THE PER-RULE ENABLED SWITCH ────
    #: `{rule_name: bool}` — the CHOICES this tenant made for this service.
    #: **A rule absent from the map is ENABLED**, so `{}` means "every rule
    #: runs" and that is the column's default.
    #:
    #: WHY A JSONB MAP AND NOT ONE BOOLEAN COLUMN PER RULE
    #: ---------------------------------------------------
    #: Both shapes were on the table and each is better at one thing:
    #:
    #:   * **One boolean column per rule** is introspectable — `\d
    #:     read_validation_service_settings` lists the whole vocabulary, a DBA
    #:     can index it, and a typo in a rule name is a database error rather
    #:     than a key nobody reads. Its cost is that it FREEZES THE RULE LIST
    #:     INTO DDL: this engine gained four rules on 2026-08-26 alone
    #:     (`plan_registers`, `cycle_membership`, `service_coherence`,
    #:     `generation_channel`), so that shape is a migration per future rule,
    #:     each one a 🔒 sensitive-path review, forever.
    #:   * **A JSONB map** costs one migration total, and — the deciding
    #:     argument — it makes BR-MET-136 clause 2 FREE. The rule is *"the
    #:     default is ALL ENABLED, for every service, at provisioning AND on
    #:     backfill … no state in which an existing tenant silently acquires a
    #:     disabled rule."* With absent-means-enabled, the empty map every
    #:     existing row gets from the column default IS that guarantee, with no
    #:     data pass to write, get wrong, or half-run. Sixteen boolean columns
    #:     would need sixteen `default=True` declarations, and a
    #:     seventeenth rule added with `default=False` by a slip is exactly the
    #:     silent acquisition the clause forbids.
    #:
    #: The map's cost — that a rule name here is just a string — is paid at the
    #: two doors that write it: `services.save_read_validation_service` refuses
    #: an unknown name and refuses an integrity rule BY NAME (clause 4), and
    #: `validation.rule_switches` forces every integrity rule back on whatever
    #: this column says, so a row written by a shell or a fixture cannot
    #: disable "the meter must exist" either.
    #:
    #: NOT a threshold, so BR-MET-020's no-default law does not reach it: that
    #: law forbids GUESSING A FIGURE the PO has not ratified. The PO ratified
    #: this default in words — *"you ahve to keep default - all enabled"*.
    rule_enabled = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_validation_service_settings"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "service"],
                name="uq_read_validation_service_settings",
            ),
        ]

    @property
    def mismatch_default_pct(self):  # noqa: ANN201 — engine-name alias
        """The engine asks `_threshold(config, "mismatch_default_pct")`
        (BR-MET-025's name on the tenant-wide row); this row spells the same
        figure `mismatch_pct` per CR-038 A1. One alias here beats teaching the
        engine two names for one rule."""
        return self.mismatch_pct


class ReadImportBatch(models.Model):
    """S28 staged read batch + its permanent compliance stamp (US-MET-007/010
    §5 PROPOSED-SCHEMA, carried verbatim).

    BR-MET-012: upload/entry creates a batch and NOTHING else — no `meter_reads`
    row exists before the step-5 commit, and a discarded batch is retained for
    audit while never appearing in Reads.

    🔒 `tag_fingerprint` is the file+tags IDEMPOTENCY key (BR-MET-018, OQ-044
    closure option b) — see services.read_batch_idempotency_key(), which is the
    single place the key is computed and is flagged HUMAN-REVIEW-PENDING."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch_no = models.TextField(null=True, blank=True)  # tenant series (EP-TEN-08 style)
    source_kind = models.TextField(default="csv")  # csv | manual | ami_replay
    source_detail = models.TextField(null=True, blank=True)  # the six S28 options
    #: **THE READ METHOD — the stage-1 TAG (BR-MET-123, CR-038 W3).**
    #:
    #: One of the tenant's `read_methods` codes (BR-AST-043), NOT a member of
    #: SOURCE_DETAILS above. NULLABLE because BR-MET-014 makes every batch tag
    #: optional: a clerk who states no method gets NULL, which reads as "not
    #: stated". It is never defaulted to `manual` — a method nobody chose is a
    #: method nobody can be held to, and the same argument already governs the
    #: channel on a staged row.
    read_method = models.TextField(null=True, blank=True)
    #: **THE WRITE MODE — the stage-1 PREMISE (CR-038 W7 task 3 / R2).**
    #:
    #: PO 2026-08-26, verbatim: *"we need insert, insert update, repalce option
    #: in step 1 of wirzard"*, and on WHERE (CR-036 (g)): *"you need at step 1
    #: or 2 itself - this is important decision how you will process the data
    #: and upload it"*.
    #:
    #: One of `write_modes.READ_WRITE_MODES`. ⚠ **NOT NULLABLE and defaulted to
    #: `insert`, which is the opposite posture from `read_method` above** — and
    #: deliberately. A tag that nobody stated reads as "not stated" and harms
    #: nothing; a *premise* that nobody stated has to be SOMETHING, because the
    #: commit acts on it. `insert` is the only one of the two that cannot
    #: touch a reading already on file, so a clerk who never sees the control
    #: gets the mode that writes nothing over anything (hard-won law 3 — the
    #: unsafe option must be the one you type).
    #:
    #: ⚠ Every existing batch backfills to `insert`, which is what they all
    #: were: until this column existed, a committed duplicate was an ERROR and
    #: `insert` is the mode that keeps it one. The backfill states history
    #: rather than reinterpreting it. 🔒 migration 0036 — HUMAN-REVIEW-PENDING.
    write_mode = models.TextField(default="insert")
    period_month = models.DateField(null=True, blank=True)  # reading month (1st of month)
    cycle = models.ForeignKey(
        Cycle, on_delete=models.PROTECT, null=True, blank=True, db_column="cycle_id"
    )
    route = models.ForeignKey(  # NULL = all routes in the cycle (US-MET-007 §5)
        Route, on_delete=models.PROTECT, null=True, blank=True, db_column="route_id"
    )
    service = models.TextField(null=True, blank=True)  # NULL = All (batch tag)
    file_name = models.TextField(null=True, blank=True)
    file_hash = models.TextField(null=True, blank=True)  # SHA-256 hex, computed server-side
    tag_fingerprint = models.TextField(null=True, blank=True)  # 🔒 file+tags key half
    uploaded_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="uploaded_by"
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)  # UTC; rendered in tenant TZ
    session_ref = models.TextField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    certified_by_uploader = models.BooleanField(default=False)  # required to post
    #: BR-MET-128 (CR-038 W9 task 1) — the lifecycle event this batch collects
    #: for, one of EVENT_CONTEXTS, NULL for every ordinary import/manual batch.
    #: Written ONLY by `services.commit_event_reads` while the batch is STAGED
    #: (a staged batch is mutable; a posted one is not — BR-MET-017), and
    #: copied onto every committed read by `_post_row`, so the read is stamped
    #: AT INSERT and the append-only law (rule 4 / BR-MET-016) is never bent by
    #: an after-the-fact UPDATE. HUMAN-REVIEW-PENDING — migration 0032; ledger
    #: row owed by the W9 lane report (this lane may not edit 12-governance/).
    event_context = models.TextField(null=True, blank=True)
    cosigned_by = models.ForeignKey(  # OQ-042 closure (tenant toggle, SysAdmin/Executive)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="cosigned_by",
        related_name="cosigned_read_batches",
    )
    #: WHEN the co-sign was given (CR-038 W7 task 5). ⚠ It lands with the first
    #: WRITER this column has ever had: `cosigned_by` shipped with migration
    #: 0003, has been SERVED by `read_batch_dict` ever since and nothing wrote
    #: it — hard-won law 2, and the gap CR-038's coverage map names. A co-sign
    #: with no timestamp is a signature with no date, which is not a signature
    #: an auditor can use. 🔒 migration 0036 — HUMAN-REVIEW-PENDING.
    cosigned_at = models.DateTimeField(null=True, blank=True)
    counts = models.JSONField(null=True, blank=True)  # denormalized composition (must reconcile)
    status = models.TextField(default="staged")  # staged | validated | posted | discarded
    posted_at = models.DateTimeField(null=True, blank=True)
    #: DEF-MET-8106 — what the post did (posted, held and why, superseded, the
    #: usage rebuild's job), kept so a post run as a BACKGROUND JOB can hand its
    #: receipt to the screen after the request that started it has answered.
    #: NULL until the batch posts. 🔒 migration 0064 — HUMAN-REVIEW-PENDING.
    post_receipt = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_import_batches"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "batch_no"],
                condition=Q(batch_no__isnull=False),
                name="uq_read_import_batches_no",
            ),
            # 🔒 DB-12 "file+tags imports": the structural half of BR-MET-018.
            # Scoped to POSTED batches because the OQ-044 closure blocks the
            # COMMIT, not the staging — a clerk may re-open the wizard on the
            # same file; only a second POST is the double-post this prevents.
            models.UniqueConstraint(
                fields=["tenant", "file_hash", "tag_fingerprint"],
                condition=Q(status="posted", file_hash__isnull=False),
                name="uq_read_import_batches_idempotency",
            ),
        ]


class ReadImportRow(models.Model):
    """One staged row — one register per date (US-MET-007/008 §5 PROPOSED-SCHEMA).

    Append-only WITHIN the batch; BR-MET-054 allows hard delete of staged and
    rejected rows only, and never of a committed `meter_reads` row. `raw_value`
    preserves the file's original when a clerk overrides (US-MET-008 §5)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(ReadImportBatch, on_delete=models.PROTECT, db_column="batch_id")
    row_no = models.IntegerField()
    #: **CR-054 W1 task 7 — THE GENERATED SHEET'S ROW KEY, VERBATIM.**
    #:
    #: `<cycle code>|<channel code>|<meter number>`, stamped by
    #: `apps/metering/reading_sheet.py` on every row it writes and carried back
    #: through `read_import` unchanged. It exists so a row whose meter no longer
    #: matches the row it was generated for is caught BY NAME — CR-054 task 7,
    #: verbatim: *"row 412 was M-4021, now M-4099 — was the meter replaced?"*.
    #:
    #: NULL on every row of a hand-built file, the blank published template and
    #: the manual grid; `validation._row_key_outcome` reads NULL as "there is no
    #: key to judge" and never as a mismatch.
    #:
    #: **It is STORED rather than judged at parse time because the engine runs
    #: from these rows, not from the file** — `services.validate_read_batch`
    #: re-reads `ReadImportRow` and has no `ParsedRow` in hand, so a key that
    #: lived only in the parser would be gone before any rule could see it.
    row_key = models.TextField(null=True, blank=True)
    meter_no_raw = models.TextField(null=True, blank=True)  # as typed/uploaded, never coerced
    asset = models.ForeignKey(  # resolved meter; NULL = unknown-meter error
        "assets.Asset", on_delete=models.PROTECT, null=True, blank=True, db_column="asset_id"
    )
    read_at_raw = models.TextField(null=True, blank=True)  # kept when the date will not parse
    read_at = models.DateTimeField(null=True, blank=True)
    channel = models.TextField(default=CHANNEL_TOTAL)  # BR-MET-059 (absent → total)
    value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    raw_value = models.DecimalField(  # original when `value` was overridden
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    service = models.TextField(null=True, blank=True)  # row override beats the batch tag
    #: **BR-MET-014's OVERRIDE HALF, FINALLY BUILT (CR-038 W3, 2026-08-26).**
    #:
    #: The rule, VERBATIM: *"Batch tags (month/cycle/route/service/source)
    #: inherit to every row unless a row-level column overrides; effective tags
    #: recorded on batch + rows"*. It says SOURCE, it has said so since
    #: 2026-08-08, and until this column existed no row could carry one — so a
    #: cycle read half by AMI and half on foot could not say so. The rule was
    #: UNBUILT, not undecided.
    #:
    #: Written at stage time as `parsed.read_method or batch.read_method`, so a
    #: row that states nothing inherits and a row that states its own wins. An
    #: UNRECOGNISED value is stored VERBATIM with an error outcome attached
    #: (BR-MET-032 validate-then-accept) — never snapped to the batch tag,
    #: because a silently corrected method is a lie about who collected the
    #: reading.
    read_method = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    demand_reset_noted = models.BooleanField(default=False)  # BR-MET-051, demand channel only
    rule_outcomes = models.JSONField(null=True, blank=True)  # list of {rule, severity, detail}
    severity = models.TextField(default="ok")  # ok | warning | error (worst outcome)
    disposition = models.TextField(null=True, blank=True)
    disposition_reason = models.TextField(null=True, blank=True)
    disposed_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="disposed_by"
    )
    # Set at commit. A bare uuid, not an FK: `meter_reads` is partitioned and
    # its PK is composite (tenant_id, read_at, id), so `id` alone carries no
    # unique index for an FK to reference — same posture as superseded_by_id.
    meter_read_id = models.UUIDField(null=True, blank=True)
    #: CR-161-BRC10 W4 — the utility's OWN reading fields as they arrived on
    #: this row (the manual entry's form, or one CSV column per field), already
    #: checked by tenancy's validator at stage time. Carried onto
    #: `meter_reads.custom_data` by `_post_row`, the same path `read_method`
    #: travels — STAGED here because validation and commit run from these rows,
    #: never from the file. `metering/0067`.
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_import_rows"
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_no"], name="uq_read_import_rows"),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="ix_read_import_rows_batch"),
        ]


class MeterRead(models.Model):
    """A committed register read — B2 §2 `meter_reads` as REDLINED by r8 (the
    CHANNEL end-state, DB-6), never the superseded r7/base body.

    Four structural laws, each one signed:
    1. **One record per register per date** (BR-MET-059/B2 r8): the row is keyed
       (asset, read_at, channel). `total` is the flat meter's single channel.
       ⚠ **SUPERSEDED FOR THE SAME-DAY PAIR, 2026-10-04 (BR-MET-1189,
       DEF-WRK-9642):** a second reading of one register on one date is KEPT,
       and `counted_reading` names the one that counts — the highest of those
       approved and validated. The key is no longer unique.
    2. **Append-only** (CLAUDE.md rule 4 spirit, BR-MET-016/024/053): a
       correction is a NEW row; the ONLY UPDATE ever permitted on a committed
       row sets `superseded_by_id` + `superseded_at` (B2 r8). The uniqueness of
       (asset, read_at, channel) therefore holds over LINEAGE HEADS only — a
       full unique would forbid the supersede the same addendum mandates.
       That partial-unique reading is the only way both r8 clauses are true at
       once; it is an Eng disposition and is REPORTED.
    3. **Quantities carry their unit** (CLAUDE.md rule 3): `unit` is NOT NULL
       and is stamped from the asset's own UoM — never inferred from service.
    4. **Partitioned monthly on read_at** (DB-7/NFR-24, BR-MET-055): the PK
       includes the partition key exactly as B2 §2 writes it. Migration 0003
       builds the real partitioned parent on Postgres; the sqlite test DB keeps
       a plain table so shape tests run (recorded, never faked).

    `superseded_by_id` is a bare uuid, NOT a self-FK: a partitioned table can
    carry no unique index on `id` alone, so B2 r8's "(self-ref)" cannot be a
    database constraint here. Service law enforces it; the isolation suite
    proves the tenant half."""

    pk = models.CompositePrimaryKey("tenant_id", "read_at", "id")  # includes the partition key
    id = models.UUIDField(default=uuid7, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    asset = models.ForeignKey(  # B2 `meter_id → meters`, superseded by the ONE registry (r4/r16 #3)
        "assets.Asset", on_delete=models.PROTECT, db_column="asset_id"
    )
    account = models.ForeignKey(  # ⚠ cross-module metering→customers (B2 §2 reviewed set)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
    )
    read_at = models.DateTimeField()  # partition key; stamped 00:00Z of the read DATE (see below)
    channel = models.TextField(default=CHANNEL_TOTAL)  # B2 r8
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    prior_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    current_value = models.DecimalField(  # NULL on an estimate (BR-MET-028: consumption only)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    multiplier = models.DecimalField(  # the factor USED, stored so S29 shows the math (BR-MET-056)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    consumption = models.DecimalField(  # (current − prior) × multiplier; unrounded (B4.4)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    unit = models.TextField()  # EXPLICIT, always (CLAUDE.md rule 3) — never inferred
    source = models.TextField()  # ami | manual | import | customer (B2 meter_source + BR-CWP-074)
    source_detail = models.TextField(null=True, blank=True)  # the six S28 options
    #: **HOW THIS READING WAS COLLECTED — the method, carried onto the read
    #: (BR-MET-123 · CR-038 W3, 2026-08-26).**
    #:
    #: One of the tenant's `read_methods` codes. This is the fact the product
    #: could not state before: `source` above holds three words (ami · manual ·
    #: import) of which `import` is a TRANSPORT rather than a method, and AMR
    #: and Mobile — two of the PO's five — had nowhere to land at all.
    #:
    #: NULL on a row that predates this column, on an ESTIMATE (nobody
    #: collected it) and on a batch whose clerk stated no method. NULL is
    #: honest and is NOT back-filled: hard rule 4 forbids rewriting a committed
    #: read, and three of the six legacy `source_detail` words name no PO
    #: method, so a backfill would have to guess. `read_import.
    #: legacy_read_method` derives what CAN be derived AT SERVE TIME and
    #: `selectors.read_dict` reports `read_method_origin` so a screen can tell
    #: `recorded` from `derived` from `not_stated`.
    read_method = models.TextField(null=True, blank=True)
    status = models.TextField(default="ok")  # one primary status (BR-MET-021)
    lifecycle = models.TextField(default="committed")  # BR-MET-053 committed → billed(locked)
    days_since_prior = models.IntegerField(null=True, blank=True)
    rule_outcomes = models.JSONField(null=True, blank=True)  # self-describing (BR-MET-022/056)
    import_batch = models.ForeignKey(  # BR-MET-017: every read links to its batch
        ReadImportBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="import_batch_id",
    )
    #: **BR-MET-079 — WHICH ROUTE THIS METER WAS ON WHEN IT WAS READ (DEF-233).**
    #:
    #: An IMMUTABLE provenance stamp, taken once at collection and never
    #: rewritten. It exists because every other way of asking "was this route
    #: ever read?" goes through a link a later edit can clear:
    #:
    #:   · `service_points.route_id` is UNSTAMPED the moment a membership moves,
    #:     so a route emptied of members reported ZERO history and deleted
    #:     cleanly — the seeded Route 1 refused deletion naming 135 reads and
    #:     was destroyed an hour later by moving its premises away first.
    #:   · `read_import_batches.route_id` was the documented answer and is not
    #:     one HERE: on the shipped fixture every `meter_reads.import_batch_id`
    #:     is NULL and `read_import_batches` holds ZERO rows, so that half of
    #:     the guard could never fire. Hard-won law 1 — the docstring claiming
    #:     the guarantee was not the guarantee.
    #:
    #: So the read carries its own route. A membership edit cannot reach it, and
    #: it still answers "this route was read" a year after the premises moved.
    #: NULL is honest and means one of three things — the read predates this
    #: column, its asset had no service point, or that point carried no route —
    #: never "no route history"; `route_read_history_count` therefore UNIONS
    #: this with the older sources rather than replacing them.
    #:
    #: PROTECT is defence in depth, not the mechanism: the service guard refuses
    #: the delete first, with a sentence naming the count. If PROTECT is what
    #: fires, a code path bypassed that guard and should be found.
    route = models.ForeignKey(
        Route,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="route_id",
        related_name="reads_collected",
    )
    imported_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="imported_by",
        related_name="imported_reads",
    )
    #: **BR-MET-128 — the EVENT that generated this read (CR-038 W9 task 1).**
    #: One of EVENT_CONTEXTS, NULL for every read no lifecycle event collected.
    #: Stamped AT INSERT from the event batch (`_post_row`) or the estimation
    #: door (`estimate_missing_read`), NEVER by a later UPDATE — a committed
    #: row's only lawful update stays the supersede pair (B2 r8, law 2 above).
    #: The USER half of BR-MET-128 is `imported_by` below: an event batch's
    #: `uploaded_by` IS the acting user, and both render on the read detail
    #: (`selectors.read_dict`). HUMAN-REVIEW-PENDING — migration 0032 (🔒
    #: migration ordering); the G7 ledger row is owed by the W9 lane report,
    #: which may not edit 12-governance/ from this worktree.
    event_context = models.TextField(null=True, blank=True)
    # BR-MET-015: the disposition that let a flagged row post, carried onto the read.
    disposition = models.TextField(null=True, blank=True)
    disposition_reason = models.TextField(null=True, blank=True)
    # US-MET-012 §5 fix actions from S25 (value changes still go through supersede).
    fix_disposition = models.TextField(null=True, blank=True)
    fix_reason = models.TextField(null=True, blank=True)
    fixed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="fixed_by",
        related_name="fixed_reads",
    )
    # Supersede chain (B2 r8 — the ONLY UPDATE a committed row ever accepts).
    superseded_by_id = models.UUIDField(null=True, blank=True)  # bare uuid — see the docstring
    superseded_at = models.DateTimeField(null=True, blank=True)
    supersede_reason = models.TextField(null=True, blank=True)
    # Estimation (US-MET-014 §5 PROPOSED-SCHEMA).
    estimation_method = models.TextField(null=True, blank=True)
    consecutive_estimate_no = models.IntegerField(null=True, blank=True)
    # US-MET-015 §5 `trues_up_read_ids uuid[]`: a JSON list of uuid strings.
    # Same Eng disposition as premises.services_available — this repo's sqlite
    # test DB has no array type, and B2 r17.3 excludes meter_reads from its
    # jsonb work for archival cost, not for shape. REPORTED.
    trues_up_read_ids = models.JSONField(null=True, blank=True)
    # Dispute markers (US-MET-013 §5, OQ-043 closure v1 record+flag+hold).
    disputed_at = models.DateTimeField(null=True, blank=True)
    dispute_reason = models.TextField(null=True, blank=True)
    disputed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="disputed_by",
        related_name="disputed_reads",
    )
    dispute_cleared_at = models.DateTimeField(null=True, blank=True)
    dispute_cleared_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="dispute_cleared_by",
        related_name="cleared_read_disputes",
    )
    demand_reset_noted = models.BooleanField(default=False)  # BR-MET-051
    #: CR-161-BRC10 W4 — the utility's OWN reading fields (PO 2026-10-02, Part 2
    #: row 11: *"Manual reading entry · Reading import (column mapping) ·
    #: Reading detail / reading history · Never used in the bill calculation"*).
    #: WRITTEN AT INSERT ONLY, by `_post_row` from the staged row, and carried
    #: onto a correction's replacement so a fixed value does not lose its
    #: answers. **No consumption, estimation, VEE or billing path reads it** —
    #: G6 / DB-17 is ABSOLUTE for `apps/rating/` and guarded for billing.
    #: Never on a detached archive partition (see `metering/0067`).
    custom_data = models.JSONField(default=dict, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meter_reads"
        # ⚠ **`uq_meter_reads_head` IS DROPPED — BR-MET-1189 (PO 2026-10-04,
        # DEF-WRK-9642, migration 0074).** It was B2 r8's UNIQUE (asset,
        # read_at, channel) over lineage heads, and it is what made a second
        # reading of one register on one date impossible to store. PO
        # verbatim: *"take the reading records in register and use date and
        # highest consumption reading if it is apprved and validated"*. The
        # same columns stay INDEXED (non-unique, heads only) because
        # `counted_reading.only_counted` probes exactly that key once per row.
        constraints: list = []
        indexes = [
            models.Index(
                fields=["tenant", "asset", "channel", "read_at"],
                condition=Q(superseded_by_id__isnull=True),
                name="ix_meter_reads_head_key",
            ),
            models.Index(
                fields=["tenant", "account", "read_at"], name="ix_meter_reads_acct_period"
            ),
            models.Index(
                fields=["tenant", "asset", "channel"], name="ix_meter_reads_asset_channel"
            ),
        ]


#: US-MET-016 §5 correction-linkage states. `open` is what metering creates;
#: billing moves it on when the credit note / rebill lands (J6 step 1). Metering
#: never sets `applied` — it does not know what billing did.
CORRECTION_STATUSES: tuple[str, ...] = ("open", "applied", "cancelled")


class ReadCorrection(models.Model):
    """US-MET-016 §5 PROPOSED-SCHEMA `read_corrections` — the row J6 step 1 consumes.

    BR-MET-053's last clause is the whole reason this table exists: *"billed-read
    error = supersede + automatic J6 correction path — read fix and money fix
    travel together"*. A superseding row on its own fixes the read and leaves an
    issued invoice priced from a number nothing points at any more. This row is
    the handoff: it names the read pair AND the invoice, so billing can raise the
    credit note against the same event metering recorded.

    **Metering never touches the invoice** (US-MET-016 §1, J6 step 1 contract:
    "original invoice UNTOUCHED"). It records a reference and stops. Whether a
    credit note, a rebill or a class-D no-op follows is BR-BIL-041's question and
    billing's story.

    `invoice_id` is a BARE UUID, not a ForeignKey — the same disposition
    `meter_reads.superseded_by_id` and `read_import_rows.meter_read_id` already
    carry, and for a second reason on top: a metering→billing FK would add a
    migration-ordering edge between two modules that migrate independently, for
    a reference billing itself must resolve anyway. The id is VALIDATED at write
    time through the billing seam (services.correct_billed_read), so a dangling
    reference cannot be created; it just is not enforced by the database.

    Append-only in practice: metering only ever INSERTs here.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The lineage head that was billed, and the new head that replaces it. Bare
    #: uuids because `meter_reads` is partitioned and carries no unique index on
    #: `id` alone — an FK has nothing to reference (see MeterRead's docstring).
    superseded_read_id = models.UUIDField()
    superseding_read_id = models.UUIDField()
    #: ⚠ cross-module ref → billing (B2 §2 reviewed interface set).
    invoice_id = models.UUIDField()
    invoice_no = models.TextField(null=True, blank=True)  # as read at open time, for the trail
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, db_column="asset_id")
    channel = models.TextField(default=CHANNEL_TOTAL)
    reason = models.TextField()  # required — no correction without one (TC-7)
    status = models.TextField(default="open")
    opened_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="opened_by"
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_corrections"
        constraints = [
            # One correction per (superseded read, invoice): re-running the same
            # correction is a duplicate, not a second event.
            models.UniqueConstraint(
                fields=["tenant", "superseded_read_id", "invoice_id"],
                name="uq_read_corrections_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "invoice_id"], name="ix_read_corrections_invoice"),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-023 · THE RECORDED IMPORT RUN (P3) — GENERALISED FROM ReadImportBatch
# ═══════════════════════════════════════════════════════════════════════════
#
# Design B15 §5 states the finding these five tables answer, and it is worth
# repeating where the tables live rather than only where they were argued:
#
#   *"A STAGED IMPORT ALREADY EXISTS IN THIS PRODUCT, AND IT IS NOT THE ONE ON
#   SCREEN."*
#
# `ReadImportBatch` / `ReadImportRow` (above) implement exactly this shape for
# meter reads — file name, SERVER-COMPUTED SHA-256, a denormalised `counts`
# JSON that must reconcile, a status ladder, uploader, session ref, IP, a
# cosigner, and a uniqueness constraint scoped to COMMITTED batches so
# re-opening the wizard on the same file is allowed but a second commit is not.
# **These tables are that shape plus `target`, `write_mode` and `mapping`, and
# they are deliberately NOT a second invention:** two staged imports is how two
# screens start disagreeing about what a run is.
#
# ⚠ **AND THE SITUATION IS WORSE THAN B15 §5 SAYS, MEASURED 2026-08-21: THERE
# ARE ALREADY THREE.** The design names `read_import_batches` and stops. The
# product also carries `assets.asset_import_batches` (`POST /assets/imports` +
# `/{id}/commit`) and `customers.account_import_batches` (`POST
# /accounts/imports` + `/{id}/commit`), each with its own row table, its own
# status vocabulary and its own commit verb — and `POST /premises/imports`
# makes a fourth path with no table at all. So this generalisation is the
# FIFTH shape in the tree today, and it is only a consolidation once the
# others are migrated onto it. **That migration is not this commit and must
# not be attempted inside one**; it is stated here so the next reader is not
# told a tidier story than the code tells. B15 §13's *"do not touch —
# generalise beside it, migrate later"* is the instruction, and "later" now
# has three tables in it, not one.
#
# ⚠ `read_import_batches` IS NOT TOUCHED and must not be. Migrating reads onto
# this generalisation is a later change with its own blast radius (B15 §13:
# *"do not touch — generalise beside it, migrate later"*), and reads carry a
# finance-signed rule set (`ReadValidationSettings`) that import rules
# deliberately do not — see `ImportRule` below.

#: `import_runs.target` — WHICH table a run loads. One runner, several targets
#: (BR-MET-086: *"import units will be similar to import premises"* — the same
#: five stages parameterised, never a second wizard).
#: CR-028 AST-W3 (BR-MET-096, exercised as written — *"two dict entries and a
#: model each"*): the three assets targets join the vocabulary. Their rows are
#: WRITTEN by `apps.assets.services` through the metering seam — the runner
#: stages and judges here; the owning module's service is the sole writer
#: (B2 r4 · B16 §4.7).
IMPORT_TARGETS = (
    "premises",
    "units",
    "assets_meters",
    "assets_submeters",
    "assets_devices",
    # CR-030 W1 — the sixth. `import_runs.TARGETS` and this vocabulary are
    # two lists in two modules and nothing asserts they agree, which is the
    # same family as DEF-614: a target registered in one and not the other
    # is refused at extract with no hint that the rest of it is wired.
    "accounts",
)

#: `import_runs.source_kind` — r10's stage-1 four cards. Only `file` is built
#: (B15 §4.1: the other three are *"out of scope for CR-023 unless the PO says
#: otherwise"*), and the vocabulary carries all four so a run recorded later
#: needs no migration to say where its data came from.
IMPORT_SOURCE_KINDS = ("file", "sftp", "api", "manual")

#: `import_runs.status` — B15 §5. `extracted → transformed → validated` are
#: stages 1–3 and **write nothing outside these tables**; `loaded`,
#: `rolled_back` and `failed` belong to stages 4–5 (P5–P7, unbuilt).
IMPORT_RUN_STATUSES = (
    "extracted",
    "transformed",
    "validated",
    "loaded",
    "failed",
    "rolled_back",
)

#: `import_runs.write_mode` — the STEP-1 premise (CR-036 (g), not r10's stage-4
#: segmented control any more). NOTHING SETS IT in stages 1–3.
#: CR-042 — TWO modes (BR-MET-210). `replace` is WITHDRAWN and lives in
#: `import_runs.WITHDRAWN_WRITE_MODES`; the COLUMN still accepts whatever is
#: already stored, because historical runs carry it and hard rule 4 is not the
#: only reason to leave written history alone.
IMPORT_WRITE_MODES = ("insert", "upsert")

#: `import_run_rows.outcome`. `staged` is the stage-1 state — every row that
#: entered the file is stored, which is the property `ReadImportRow` defends
#: too: a row that entered always appears in the report.
IMPORT_ROW_OUTCOMES = ("staged", "loaded", "rejected", "flagged", "skipped", "duplicate")

#: BR-MET-090 — SEVERITY AND ACTION ARE TWO COLUMNS, DELIBERATELY. r10's own
#: table proves why: *"Premise type exists in the lookup table · **Warning** · 2
#: · **Default to Residential**"* is a warning that PERFORMS A WRITE the
#: operator never asked for.
IMPORT_RULE_SEVERITIES = ("error", "warning", "pass", "off")
IMPORT_RULE_ACTIONS = ("reject_row", "skip_on_load", "default_to", "flag_only")

#: `import_run_progress.stage` / `.state` — CR-026's live gauge (the table at
#: the bottom of this file). The three stages that can go to a worker are the
#: three that were measured over a request timeout (77.9s / 50.8s / 101.5s at
#: 50,000 rows); extract is batched and answers in 6.8s, and the dry run in
#: 1.9s, so neither is ever deferred and neither reports progress.
IMPORT_PROGRESS_STAGES = ("transform", "validate", "load")
#: `queued` (handed to a worker, not started) → `running` → `done` | `failed`.
#: Deliberately NOT the `jobs` vocabulary re-used: a job that succeeded and a
#: stage that finished are different facts, and the day they disagree the
#: screen must be able to say which one it is showing.
IMPORT_PROGRESS_STATES = ("queued", "running", "done", "failed")

#: BR-MET-090's three tiers. 1 STRUCTURAL (the database or a hard rule refuses
#: it — never configurable, no severity switch, no off switch) · 2 PLATFORM
#: (shipped for every tenant, re-configurable within a stated floor) · 3 TENANT
#: (the utility's own).
IMPORT_RULE_TIERS = (1, 2, 3)


class ImportRun(models.Model):
    """One recorded ETL run — B15 §5/§13, CR-023.

    **THE SAFETY PROPERTY OF THE WHOLE DESIGN LIVES HERE:** stages 1, 2 and 3
    write `import_runs`, `import_run_rows` and `import_rule_results` **and
    nothing else**. r10 prints the promise under its own title — *"Five stages ·
    nothing is written until you commit at stage four"* — and B15 §16's TC-1
    asserts it by counting rows in `premises`, `units` and `service_points`
    before and after. Every other guarantee in this design rests on that one,
    which is why the load half is a separate phase in a separate commit.

    ⚠ **`file_hash` IS COMPUTED SERVER-SIDE, FROM THE BYTES** (TC-2). A client
    -supplied hash proves nothing: it attests to what the client says it sent.
    The receipt prints this value, so it must be ours.

    ⚠ **`mapping` CANNOT CARRY A COLUMN MAP TODAY — see `mapping_spec`.**
    `tenancy.ImportMapping` is `code · name · is_system · active` and has no
    column for a mapping, so *"Save mapping as template"* cannot round-trip
    through it. The run therefore stores its OWN mapping in `mapping_spec` and
    records `mapping` as the template it was started from, which is what the
    receipt's `MAPPING USED` line names.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `RUN-2812`. Allocated from the EP-TEN-08 `import_run` series, which
    #: CR-005 already added to the catalog (`core.numbering.IMPORT_RUN`,
    #: default `RUN-{0000}`) and nothing had ever allocated from. A missing
    #: series row is REPORTED as a warning and left NULL, never faked.
    run_no = models.TextField(null=True, blank=True)
    target = models.TextField()  # IMPORT_TARGETS
    source_kind = models.TextField(default="file")  # IMPORT_SOURCE_KINDS
    file_name = models.TextField(null=True, blank=True)
    file_hash = models.TextField(null=True, blank=True)  # SHA-256 hex, SERVER-computed
    file_bytes = models.IntegerField(null=True, blank=True)  # the receipt's `96 KB`
    #: r10 stage 1 prints `UTF-8 · comma (detected)` as ONE field, so it is
    #: stored as one: it is a statement about how the file was read, not two
    #: independent settings anything branches on.
    encoding_delimiter = models.TextField(null=True, blank=True)
    mapping = models.ForeignKey(  # ⚠ cross-module FK metering→tenancy (B2 §2
        "tenancy.ImportMapping",  # reviewed set — the direction `premises.area`
        on_delete=models.PROTECT,  # already takes). Tenancy HOSTS the row;
        null=True,  # this run OWNS the fact that it used it.
        blank=True,
        db_column="mapping_id",
    )
    #: THE MAPPING AS CONFIGURED, on this run, at stage 2 — `{source column:
    #: {target, transform}}` plus the three row-handling choices. Stored on the
    #: RUN because a run must be able to say what it actually did even after
    #: the template it started from is edited or retired: the same instinct as
    #: the locked-at-issue invoice snapshot and as `ImportRuleResult` below.
    mapping_spec = models.JSONField(null=True, blank=True)
    batch_label = models.TextField(null=True, blank=True)  # r10 "Batch label (audit trail)"
    write_mode = models.TextField(null=True, blank=True)  # IMPORT_WRITE_MODES — stage 4 only
    #: `{in, duplicates_dropped, skipped, forward, checked, clean, errors,
    #: warnings, loaded, rejected, flagged}`. Denormalised and MUST RECONCILE —
    #: TC-3: in − duplicates_dropped − skipped = forward. The same discipline
    #: `ReadImportBatch.counts` carries, for the same reason: a count that
    #: cannot be checked against the rows is a number nobody can defend.
    counts = models.JSONField(null=True, blank=True)
    status = models.TextField(default="extracted")  # IMPORT_RUN_STATUSES
    run_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="run_by"
    )
    session_ref = models.TextField(null=True, blank=True)  # the receipt's `sess_2b41`
    ip = models.GenericIPAddressField(null=True, blank=True)  # the receipt's `71.42.108.14`
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)  # set at stage 4/5
    #: BR-TEN-057 — the sample-data tag, on the OWNING row, written only by
    #: this module's own sample path (BR-TEN-013). B15 §15 requires it: the
    #: three seeded runs PRM-04 needs must be deletable by BR-TEN-061.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_runs"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "run_no"],
                condition=Q(run_no__isnull=False),
                name="uq_import_runs_no",
            ),
            #: 🔒 TC-21, and the shape is `uq_read_import_batches_idempotency`
            #: verbatim: **scoped to LOADED runs**, because re-uploading the
            #: same file to look at it again is legitimate — r10's own stage 1
            #: invites it — and only a second COMMIT is the double-load this
            #: prevents. A staged run is a rehearsal; a loaded run is a fact.
            models.UniqueConstraint(
                fields=["tenant", "target", "file_hash"],
                condition=Q(status="loaded", file_hash__isnull=False),
                name="uq_import_runs_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_import_runs_status"),
        ]


class ImportRunRow(models.Model):
    """One source row, as extracted and as mapped — B15 §5.

    Generalised from `ReadImportRow`, which defends the same claim and states
    it best: *"every row that enters the file comes out of the report"*,
    accepted / flagged / rejected, each with its reason. A silently dropped row
    is DEF-016's failure mode over one file; over a 431-row migration it is a
    customer asking what happened to property 88214 and nobody being able to
    answer.

    `created_record_id` is the column `ReadImportRow` does not have and rollback
    cannot work without: it is what this row MADE, so a rollback point knows
    what to reverse (B15 §5, §6.1). It is a bare uuid rather than an FK because
    one run row may create a premises OR a unit depending on `run.target`, and
    a column cannot point at two tables.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    run = models.ForeignKey(ImportRun, on_delete=models.PROTECT, db_column="run_id")
    row_no = models.IntegerField()  # 1-based, as the operator counts them
    source_key = models.TextField(null=True, blank=True)  # `P-11902` — what the file called it
    raw = models.JSONField(null=True, blank=True)  # AS EXTRACTED, never coerced
    mapped = models.JSONField(null=True, blank=True)  # after transform
    outcome = models.TextField(default="staged")  # IMPORT_ROW_OUTCOMES
    #: CUSTOMER-FACING ENGLISH, no ids (CR-016's no-internal-references rule
    #: reaches this screen like any other) — *"Address falls outside the
    #: territory boundary"*, *"Parent premise P-11902 was not loaded"*.
    problem = models.TextField(null=True, blank=True)
    fix_hint = models.TextField(null=True, blank=True)  # *"Load the premise first"*
    created_record_id = models.UUIDField(null=True, blank=True)  # what it made, for rollback
    is_sample = models.BooleanField(default=False)  # BR-TEN-057, as the run
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_run_rows"
        constraints = [
            models.UniqueConstraint(fields=["run", "row_no"], name="uq_import_run_rows"),
        ]
        indexes = [
            models.Index(fields=["tenant", "run"], name="ix_import_run_rows_run"),
            models.Index(fields=["tenant", "run", "outcome"], name="ix_import_run_rows_outcome"),
        ]


class ImportRule(models.Model):
    """A tenant's OWN import validation rule, or its override of a platform one
    — BR-MET-090, B15 §4.3A.

    **A RULE IS A DECLARED ROW, NOT AN `if` STATEMENT.** That is the whole
    design brief, and it is what makes the rule set changeable without breaking
    anything already loaded.

    ⚠ **WHY ROWS AND NOT COLUMNS, stated here because the precedent points the
    other way.** `ReadValidationSettings` answers the same question for meter
    reads — *how does this utility want its inbound data checked* — as a WIDE
    ROW OF NAMED COLUMNS (`high_pct 200`, `low_pct 25`, `days_flag_min 25`…).
    That works for reads and cannot work here: reads have a **fixed,
    finance-signed** rule set, so a new rule is a deliberate act with a
    migration behind it; imports have an **open** one, and tier 3 is a utility
    writing a rule we never shipped — *"No premise outside our three ZIP
    codes"*. A column set cannot express a rule nobody has thought of yet.
    Both shapes are correct for their own half, and B15 §4.3A says so.

    **TIER 1 IS NEVER IN THIS TABLE.** Structural rules come from the schema
    and the hard rules — `address_line` NOT NULL, `uq_premises_tenant_premise_no`,
    BR-MET-003 — and switching one off would write a row the database or a hard
    rule refuses. They are declared in `apps/metering/import_rules.py` with a
    fixed severity and no configuration surface at all.

    **A `code` IS NEVER REUSED** (BR-MET-090), because `ImportRuleResult` rows
    from years ago still name it. Retiring a rule sets `active=False`; it never
    frees the code.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # `PRM.ADDRESS_IN_TERRITORY` — stable forever
    target = models.TextField()  # IMPORT_TARGETS — a rule belongs to one target
    tier = models.IntegerField(default=3)  # 2 = override of a platform rule; 3 = the utility's own
    #: Customer-facing English, no ids. Tier-3 sentences are TENANT PROSE and
    #: deliberately not a `message_key`, on the ratified `custom_field.label`
    #: precedent (B2 r17.5 #1, PO 2026-08-10): a tenant-authored sentence has
    #: no key and never can. Platform sentences live in the code catalog.
    sentence = models.TextField(null=True, blank=True)
    severity = models.TextField(null=True, blank=True)  # IMPORT_RULE_SEVERITIES
    action = models.TextField(null=True, blank=True)  # IMPORT_RULE_ACTIONS
    action_value = models.TextField(null=True, blank=True)  # only for `default_to`
    #: WHICH evaluator runs this rule. Platform rules name their own; a tier-3
    #: rule may only use a kind we have an evaluator for, and one that does not
    #: is reported `available: false` with that reason rather than dropped —
    #: BR-MET-091's discipline applied to the tenant's half of the set.
    rule_kind = models.TextField(null=True, blank=True)
    params = models.JSONField(null=True, blank=True)  # e.g. {"field": "owner_manager"}
    active = models.BooleanField(default=True)  # retired, never deleted
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_rules"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_import_rules_tenant_code"),
        ]
        indexes = [
            models.Index(fields=["tenant", "target"], name="ix_import_rules_target"),
        ]


class ImportRuleResult(models.Model):
    """THE RUN'S OWN COPY OF THE RULES, AS THEY WERE — BR-MET-090, B15 §4.3A.

    ⚠ **STORED, NEVER RECOMPUTED, AND THAT IS THE WHOLE POINT OF THE TABLE.**
    Re-deriving a run's results from today's configuration would rewrite
    history: a receipt reading *"2 warnings"* in July would read *"2 errors"* in
    August, with nothing anywhere to show the reader that the run itself never
    changed. This is the same instinct as the locked-at-issue invoice snapshot,
    and it is why `severity`, `action`, `action_value` and `sentence` are COPIED
    onto this row rather than joined from `ImportRule`.

    Two consequences follow and both are rules for the builder: changing a rule
    NEVER re-validates loaded data (it applies to the next run — a utility that
    wants old rows re-checked is asking for a REPORT, a different feature), and
    a retired rule's `code` is never reused because these rows still name it.

    `available=False` is BR-MET-091: a rule the product CANNOT EVALUATE is
    LISTED with its reason, never omitted — because an operator reading three
    rules where four were expected learns nothing, and one reading four with one
    marked unavailable learns exactly what protection they have.
    `PRM.EXPECTED_UNITS_INTEGER` is the live example: nothing in this product
    records how many units a premises is expected to have, so the rule is
    declared, listed, and reported unavailable.

    ⚠ **`available=False` IS NOT THE SAME AS RULED OUT, AND THE EXAMPLE THAT
    USED TO STAND HERE IS NOW THE COUNTER-EXAMPLE (`BR-MET-097`, PO
    2026-08-21).** This paragraph named `PRM.ADDRESS_IN_TERRITORY` — r10's only
    error-severity platform rule — as the case for listing-with-a-reason. The PO
    then ruled that an imported address is accepted as given, because it comes
    out of the utility's own GIS. So that rule is GONE, not greyed: *"we would
    check this and cannot"* invites a utility to ask when it will be switched
    on, and the answer is now never. **A rule we cannot run yet is listed; a
    rule we have decided not to run is removed.**
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    run = models.ForeignKey(ImportRun, on_delete=models.PROTECT, db_column="run_id")
    rule_code = models.TextField()
    tier = models.IntegerField(default=2)
    sentence = models.TextField(null=True, blank=True)  # as it read WHEN THE RUN RAN
    severity = models.TextField(null=True, blank=True)  # as configured WHEN THE RUN RAN
    action = models.TextField(null=True, blank=True)
    action_value = models.TextField(null=True, blank=True)
    hits = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    #: WHY it could not run, in customer-facing English. Never NULL when
    #: `available` is False — an unavailable rule with no reason is exactly the
    #: silence BR-MET-091 exists to prevent.
    unavailable_reason = models.TextField(null=True, blank=True)
    is_sample = models.BooleanField(default=False)  # BR-TEN-057, as the run
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "import_rule_results"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "rule_code"], name="uq_import_rule_results_run_code"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "run"], name="ix_import_rule_results_run"),
        ]


class RollbackPoint(models.Model):
    """`RB-2812 · available for 30 days` — the receipt's sixth field, B15 §5.

    ⚠ **NOTHING WRITES THIS TABLE YET, AND THAT IS DELIBERATE.** A rollback
    point is ISSUED AT COMMIT (stage 4, P5) and used by stage 7's reversal, and
    both wait on rulings this design does not have: the window is printed on
    screen as a promise to the user and **`30 days` is r10 copy, not a signed
    figure** (B15 §8 Q7), and whether a PARTLY-reversed run keeps its point is
    not stated anywhere. The table lands with the schema so a receipt never
    promises a rollback with no row behind it — the `read_batch`/`jobs`
    posture — and the expiry is NULLABLE precisely so no lane can quietly
    default it to thirty days on the way past.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    point_no = models.TextField(null=True, blank=True)  # `RB-2812`
    run = models.ForeignKey(ImportRun, on_delete=models.PROTECT, db_column="run_id")
    #: ⛔ NULLABLE AND UNSET BY ANYTHING — B15 §8 Q7. `available for 30 days` is
    #: printed on r10's receipt and is not a signed rule; a `default=` here
    #: would make it one silently.
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.TextField(default="available")  # available | used | expired
    is_sample = models.BooleanField(default=False)  # BR-TEN-057, as the run
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rollback_points"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "point_no"],
                condition=Q(point_no__isnull=False),
                name="uq_rollback_points_no",
            ),
        ]


class ImportRunProgress(models.Model):
    """WHERE A RUNNING STAGE SAYS HOW FAR IT HAS GOT — CR-026, one row per run.

    r10's stage rail draws *"Validating… 62,000 of 100,000"* and this table is
    what makes that sentence true WHILE the stage is running, rather than after
    it finishes.

    ⚠ **WHY THIS IS NOT A COLUMN ON `import_runs`, WHICH IS WHERE ANYONE WOULD
    LOOK FIRST.** Every stage holds `SELECT … FOR UPDATE` on its own
    `import_runs` row for the whole stage — `DEF-529` put that lock inside the
    stage's transaction, correctly, and the transform/validate/load bodies each
    run to completion inside it (**77.9s / 50.8s / 101.5s measured at 50,000
    rows**). A progress UPDATE aimed at that same row **from any other
    connection waits for the lock**, so a column could only ever report 0% and
    then 100% — precisely the two numbers a poller does not need. A separate
    row is contended by nobody, so it can be written *while* the stage runs.

    ⚠ **AND IT IS WRITTEN ON A SECOND, AUTOCOMMIT CONNECTION** (see
    `apps/metering/import_progress.py`): a write on the stage's own connection
    would join the stage's transaction and become visible only at commit, which
    is the same uselessness by a different route. That module owns the how; this
    table owns the shape.

    **ONE ROW PER RUN, OVERWRITTEN IN PLACE.** This is a live gauge, not a
    history: what the run DID is `import_runs.counts` and the receipt, both of
    which are the audited record (BR-MET-090). Nothing financial and nothing
    audited reads this table — losing every row in it would cost a screen its
    progress bar and nothing else, which is the property that lets the writer
    swallow its own failures rather than fail a stage over a gauge.

    **`state`** is `queued` the moment the endpoint hands the stage to a worker,
    `running` while it walks, then `done` or `failed` with the reason. The RUN's
    own `status` is untouched by a failure: a transform that died leaves the run
    `extracted`, which is exactly what it is, and the operator may retry it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    run = models.ForeignKey(ImportRun, on_delete=models.PROTECT, db_column="run_id")
    stage = models.TextField()  # IMPORT_PROGRESS_STAGES
    done = models.IntegerField(default=0)
    total = models.IntegerField(null=True, blank=True)
    state = models.TextField(default="queued")  # IMPORT_PROGRESS_STATES
    #: Customer-facing English, no ids — *"Checking rule 4 of 11"*. On a failure
    #: it carries the error class and message the job body died with, because a
    #: progress bar that stops with no sentence is the shape DEF-016 warns about.
    message = models.TextField(null=True, blank=True)
    #: The BE-07 job record this stage is running as, so a screen that would
    #: rather poll `/jobs/{id}` (B12 r1 §3) can, without a second lookup.
    job_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_run_progress"
        constraints = [
            #: ONE row per run — the upsert key the writer's `ON CONFLICT`
            #: names. A second row would mean two stages claiming the same run.
            models.UniqueConstraint(fields=["run"], name="uq_import_run_progress_run"),
        ]
        indexes = [
            models.Index(fields=["tenant", "run"], name="ix_import_run_progress_run"),
        ]


# ════════════════════════════════════════════════════════════════════════════
# BR-MET-106 — THE STORED MONTH (CR-030 W3 task 3.8, PO ruling 2026-08-24)
# ════════════════════════════════════════════════════════════════════════════
class MonthlyUsage(models.Model):
    """One account's usage of one service in one calendar month — BR-MET-106.

    PO verbatim, 2026-08-24: *"based on meter reading calculate monthly useage
    and save them and display them"*.

    WHY THIS TABLE IS IN `metering` AND NOT IN `customers`
    -----------------------------------------------------
    The row is grouped BY ACCOUNT, so the obvious home looks like `customers`.
    It is not, for two reasons that are both module law:

      * The figure is Σ over `meter_reads`, which `metering` owns (B2 r16 #4).
        A writer in `customers` would have to query metering's table, and
        BR-CUS-034 says customers keeps no copy of another module's row.
      * Cross-module WRITES are forbidden (CLAUDE.md module map, B2 §2).
        `metering` may not write an `accounts` row and `customers` may not write
        this one. The module that owns the inputs owns the derived row.

    `account_id` is the SAME reviewed cross-module FK `meter_reads.account_id`
    already is (B2 §2 interface set), so this adds no new interface.

    FOUR STRUCTURAL LAWS, EACH ONE SIGNED
    -------------------------------------
    1. **The quantity carries its unit** (CLAUDE.md hard rule 3, restated by
       BR-MET-106): `unit` is NOT NULL. kWh, kgal and therms are never added
       together, and a stored quantity without its unit is unreadable.
    2. **Corrections RESTATE, they never edit** (hard rule 4; BR-MET-106; the
       same supersede shape `meter_reads` uses per B2 r8). A late or superseded
       read writes a NEW row for the month; the only UPDATE this table ever
       accepts sets `superseded_by_id` + `superseded_at` on the row it replaces.
       Uniqueness therefore holds over LINEAGE HEADS only — a full unique would
       forbid the restatement the rule mandates.
    3. **An unread month is ABSENT, never `0`** (BR-MET-106). There is no row
       for a month with no reads, and no writer creates a zero one. Zero usage
       and no read are different claims about a customer.
    4. **Estimates count and are marked** (BR-MET-028 / BR-MET-106).
       `estimated_read_count` is what lets the screen tell a customer that part
       of a 628 kWh month was estimated; it is a COUNT, so `> 0` is the marker
       and the exact split is available without a second query.

    `source_read_ids` is the read-lineage HEADS this figure summed — the
    provenance BR-MET-106 asks the restatement to carry, and half of the
    idempotency key (see `monthly_usage_service.recompute_month`).

    ⚠ NOT PARTITIONED. `meter_reads` is (DB-7/NFR-24), because it grows with
    every register on every read day; this table grows with accounts × services
    × months, which for a <3,000-connection utility (CLAUDE.md) is three orders
    of magnitude smaller. BR-MET-055's hot-window rule is about the READ table
    and is not inherited here — stated so the next lane does not assume it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module metering→customers (B2 §2 reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    service = models.ForeignKey(  # the 10-service platform catalog (r16 #3)
        "tenancy.Service", on_delete=models.PROTECT, db_column="service_id"
    )
    #: The FIRST DAY of the calendar month this figure covers. A date, not a
    #: (year, month) pair, so ordering and range scans are the database's job.
    period_month = models.DateField()
    #: Σ MeterRead.consumption, UNROUNDED, at the reads' own 18,6 precision
    #: (B4.4 — round only at display). This is a QUANTITY, not money: CLAUDE.md
    #: rule 2's 4-dp law governs money columns and does not apply here.
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    unit = models.TextField()  # EXPLICIT, always (hard rule 3) — never inferred
    read_count = models.IntegerField()
    #: BR-MET-028 estimates carry consumption and no `current_value`. They are
    #: INCLUDED in `quantity` and counted here, because a customer looking at a
    #: 628 kWh month is entitled to know part of it was estimated.
    estimated_read_count = models.IntegerField(default=0)
    #: The lineage HEADS summed, as a JSON list of uuid strings. Same Eng
    #: disposition as `meter_reads.trues_up_read_ids`: this repo's sqlite test
    #: DB has no array type.
    source_read_ids = models.JSONField(default=list)
    #: The content fingerprint of the inputs (see the service). Two recomputes
    #: over the same reads produce the same fingerprint and the second writes
    #: nothing — CLAUDE.md rule 6, expressed over content rather than a caller
    #: supplied key, because nobody submits a "monthly usage request".
    source_fingerprint = models.TextField()
    computed_at = models.DateTimeField()  # BR-MET-106: the restatement carries it
    #: Restatement chain — the ONLY UPDATE a committed row ever accepts, exactly
    #: as `meter_reads` (B2 r8). A bare uuid rather than a self-FK for symmetry
    #: with that table and because the head is found by the partial unique below.
    superseded_by_id = models.UUIDField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    supersede_reason = models.TextField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag on the OWNING row. Inherited from the
    #: reads this row summed: a month computed entirely from sample reads is
    #: sample data and BR-TEN-061 deletes it on this predicate.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meter_read_monthly_usage"
        constraints = [
            #: ONE live statement per account per service per month — over
            #: lineage HEADS only, so a restatement is legal and a SECOND
            #: simultaneous head is not (law 2 in the docstring).
            models.UniqueConstraint(
                fields=["tenant", "account", "service", "period_month"],
                condition=Q(superseded_by_id__isnull=True),
                name="uq_monthly_usage_head",
            ),
        ]
        indexes = [
            #: The Usage tab's own query: one account, newest months first.
            models.Index(
                fields=["tenant", "account", "period_month"],
                name="ix_monthly_usage_acct_month",
            ),
        ]


class PremisesSubmeterReconciliation(models.Model):
    """**BR-MET-125 — the master-vs-sub-meters UNACCOUNTED GAP, per premises
    per period, STORED.**

    PO verbatim, 2026-08-26 (CR-038, closing the Blueprint's Open 9 and
    OQ-327): *"Open 9 - (a) store + report — keeps the door open"*. The worked
    figure they were shown: **master 12,400 kWh − Σ subs 11,940 = 460 kWh
    (3.71%) against a 3% tolerance**. Billing common areas FROM this figure is
    deliberately NOT built; the stored number is what keeps that door open for
    a future ruling.

    ⚠ **THIS TABLE STORES A DERIVED FIGURE, AND THAT IS A DELIBERATE
    EXCEPTION.** The standing posture in this module is that a derivable number
    is DERIVED at read time — `BR-MET-011` progress, occupancy, the S26/S27
    counters all refuse to keep a stored counter precisely so no copy can drift
    from the reads. The PO overrode that here, explicitly, by choosing option
    (a) over "report only": the gap must SURVIVE the period so a future common
    -area ruling has a history to price from, and a figure recomputed from
    today's reads would silently restate a closed month when a late read lands.
    So the exception is the ruling, not a shortcut — and the row records
    everything needed to audit itself: both inputs, the tolerance it was judged
    against, which reads it summed, and when it was computed.

    FIVE STRUCTURAL LAWS
    --------------------
    1. **The quantity carries its unit** (CLAUDE.md hard rule 3). `unit` is NOT
       NULL and is the MASTER's own UoM. A sub-meter reading in a different
       unit is never converted (OQ-004) — it is EXCLUDED from the sum and named
       in `unresolved_submeters`, and the row then states `not_evaluated`
       rather than reporting a gap computed from an incomplete sum.
    2. **A gap that cannot be computed honestly is stored as an ABSENCE, never
       as a number.** `status` is `computed` or `not_evaluated`; on the latter
       every quantity column is NULL and `reason` says why. A partial Σ subs
       would manufacture an unaccounted gap out of a missing reading, which is
       the single most damaging thing this table could do.
    3. **Percentages to 6 decimals, displayed 2** (hard rule 2, PO re-sign
       2026-08-22). `gap_pct` and `tolerance_pct` are `DecimalField(18, 6)`.
       No money lives here and none may: this is a QUANTITY reconciliation.
    4. **One live row per (premises, master, register, period).** A premises
       can carry more than one master — an electric master and a water master —
       so the master asset is part of the key, and so is the channel, because a
       gap is per REGISTER (a TOU premises reconciles `total`, not the windows).
    5. **Recomputed, not appended.** Unlike `meter_read_monthly_usage` next
       door this carries no supersede chain: it is not a customer-facing
       statement and no money reads it, so a recompute UPDATES the row in place
       and stamps `computed_at`. If a future ruling ever prices a common area
       from this figure, that ruling makes it a money row and the restatement
       chain arrives with it — stated here so the next lane does not have to
       infer it.

    `master_asset_id` is the same reviewed cross-module FK metering→assets that
    `meter_reads.asset_id` already is (B2 §2 interface set) — no new interface
    edge. `premises_id` and `service_id` are this module's own and tenancy's
    catalog respectively, both already in the set via `service_points`.
    """

    #: `status` vocabulary. Two values, deliberately: a gap either was computed
    #: from a complete Σ or it was not. There is no "partial".
    STATUS_COMPUTED = "computed"
    STATUS_NOT_EVALUATED = "not_evaluated"

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    premises = models.ForeignKey(Premises, on_delete=models.PROTECT, db_column="premises_id")
    master_asset = models.ForeignKey(  # ⚠ cross-module → assets (reviewed set)
        "assets.Asset", on_delete=models.PROTECT, db_column="master_asset_id"
    )
    service = models.ForeignKey(  # the master's own service; NULL = no service point
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    #: The reading MONTH, stamped to the first of the month — the same shape
    #: `meter_read_monthly_usage.period_month` and `read_import_batches`
    #: `period_month` use, so "per period" means one thing across the module.
    period_month = models.DateField()
    channel = models.TextField(default=CHANNEL_TOTAL)  # the register reconciled
    #: BOTH INPUTS ARE STORED, not just the difference — a gap whose inputs are
    #: gone cannot be argued with, and the whole point of (a) is that somebody
    #: later re-opens this number.
    master_consumption = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    submeter_sum = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    gap_quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    gap_pct = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: The tolerance THIS row was judged against, copied at computation time —
    #: BR-MET-020's config is tenant-editable, so a stored verdict that pointed
    #: at the live setting would silently change its own meaning when somebody
    #: edits S64. Law 1 of the validation engine, applied to storage.
    tolerance_pct = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    within_tolerance = models.BooleanField(null=True, blank=True)
    unit = models.TextField()  # EXPLICIT, always (hard rule 3) — the master's UoM
    status = models.TextField(default=STATUS_COMPUTED)
    reason = models.TextField(null=True, blank=True)  # why `not_evaluated`
    submeter_count = models.IntegerField(default=0)  # sub-meters EXPECTED
    submeters_resolved = models.IntegerField(default=0)  # sub-meters that had a read
    #: Sub-meters whose figure could not be taken, each with its own reason
    #: (`no_read`, `unit_mismatch`, `no_consumption`) — the named absence the
    #: report renders instead of a silently-short sum.
    unresolved_submeters = models.JSONField(default=list)
    #: The lineage HEADS this row summed, as a JSON list of uuid strings — the
    #: same Eng disposition `meter_read_monthly_usage.source_read_ids` records
    #: (this repo's sqlite test DB has no array type).
    source_read_ids = models.JSONField(default=list)
    computed_at = models.DateTimeField()
    #: BR-TEN-057 — the sample-data tag on the OWNING row, inherited from the
    #: master read this row reconciled. BR-TEN-061 deletes on this predicate.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "premises_submeter_reconciliations"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "premises", "master_asset", "channel", "period_month"],
                name="uq_premises_submeter_recon",
            ),
        ]
        indexes = [
            #: The report's own query: one premises, newest periods first.
            models.Index(
                fields=["tenant", "premises", "period_month"],
                name="ix_premises_submeter_recon",
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W6 · NEW CONNECT — the six tables are WORK's now (T-43, 2026-10-21)
# ══════════════════════════════════════════════════════════════════════════
# `connections` · `connection_services` · `work_orders` · `work_order_templates`
# · `service_characteristics` · `connection_todos` were declared in
# `apps/metering/connections.py` and registered by an import on this line.
# CR-187-BRC10 T-43 moved the declarations to `apps/work/connection_models.py`
# (Work owns them — `16-work/03-field-map.md` §4) and the registering import to
# `apps/work/models.py`; `metering/0078` released them from this app's migration
# state and `work/0046` took them, neither touching a table. The New Connect
# SERVICES stay in `apps/metering/connections.py`, which is still imported at
# startup through `connection_fees` below.

# ⚠ SAME REASON, ONE MODEL: `interruptions.Interruption` (CR-068 wave B,
# US-CWP-008) lives in its own module and is registered by being imported
# here. Without this line `makemigrations` sees no table and the project
# sits in permanent migration drift with CI proposing to drop it.
from apps.metering import interruptions  # noqa: E402,F401  (registers Interruption)

# ⚠ SAME REASON, ONE MODEL: `connection_fees.ConnectionFeeBill` (`CR-163-BRC10`
# item 2 — a fee added to a build after submission is a NEW bill, and this is
# the note of which build it is for). Registered by being imported here.
from apps.metering import connection_fees  # noqa: E402,F401  (registers ConnectionFeeBill)

# ⚠ SAME REASON, FOUR MODELS: `field_read_models` (`CR-187-BRC10`, the native
# field app's route reading — `field_reads`, `cant_read_reasons`,
# `field_meter_proposals`, `field_route_turn_ins`). Registered by being imported here.
from apps.metering import field_read_models  # noqa: E402,F401  (registers four models)
# MQ-033 (`CR-192-BRC10`) — the utility's own read FORMATS, their versions,
# questions, service defaults and the answers a reading carries. Same reason.
from apps.metering import read_format_models  # noqa: E402,F401  (registers five models)

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot — EP-MET-01/02 W1 schema half + r16 owner map)
# packet: US-MET-016@c81d5a7 (EP-MET-04 supersede/correction story — read_corrections, added 2026-08-15)
# generated: 2026-08-09 by story-coder v1 (W1 SCHEMA lane — models+migrations only) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (IMPORT_TARGETS gains the three assets targets (BR-MET-096 exercised as written)) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (premises.lat/lng NUMERIC(9,6) NULL — §10-D6; migration 0018, 🔒 HUMAN-REVIEW-PENDING; NO second `area` column — the EXISTING BR-MET-071 FK is the map's area vocabulary, the B16 §6 "reconcile, not duplicate" note applied)
# checklist: A✔ B=deferred(table-half only — service/API TCs land with each story lane) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff✔ black✔ py_compile✔ pytest tests/test_w1_models.py✔ · suite 333 baseline green + W1 (2 pre-existing identity-lane failures, not this lane) · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: meter_reads + read import/validation tables deliberately NOT built (W2 reads lane; r16 #4 channel end-state) · units.occupancy/status deliberately absent (BR-MET-036 derived; US-MET-002 §5 display-only) · premises_types hosted here (no owner-map row — Eng disposition, REPORTED) · services_available as JSON list (array-type Eng disposition — REPORTED) · unit_plan_assignments NOT here (rating-owned per r16 #6 — built in apps/rating)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
