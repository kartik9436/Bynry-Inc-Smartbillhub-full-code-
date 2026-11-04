# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (registry tabs — types/stages/status semantics) ·
#           US-AST-002 (add single — 3-identifier model) · US-AST-003 (edit +
#           delete gate) · US-AST-004 (extended spec fields) · US-AST-006
#           (assignment history + maintenance log shapes) · US-AST-007 (repair
#           log) · US-AST-008 (retire columns) · US-AST-009 (reassign +
#           final-read column) · US-AST-010 (bulk-import staging)
#           Screens: S49–S55, S16 (unit-wizard meter grid)
# Rules:    BR-AST-001/004/009 (scope + type set) · BR-AST-026/033 (3-identifier
#           model: hidden uuid + serial + user asset_no) · BR-AST-031 (lifecycle
#           stages = Reference data w/ behavior classes — never a hardcoded
#           enum) · BR-AST-020/030 (transition law — service-enforced) ·
#           BR-AST-003/010 (sub-meter parent, net metering) · BR-AST-014/015
#           (extended specs; register_digits default 9) · BR-AST-017 (assignment
#           history append-only, one current row) · BR-AST-018 (maintenance
#           append-only) · BR-AST-021 (retire columns) · BR-AST-022 (final-read
#           on move) · BR-AST-034 (import contract) · BR-MET-006 (allocation
#           rule / loss tolerance on masters) · BR-TEN-036 (lookup shape) ·
#           BR-AST-043 (PO 2026-08-09: meter_types and read_methods are TWO
#           separate reference lists; assets.read_method REFERENCES the
#           read_methods catalog, superseding B2 r4's plain value) ·
#           BR-AST-044 (PO 2026-08-09: an asset carries BOTH classifications —
#           asset_type AND meter_type — alongside read_method; all three are
#           catalog FKs with PROTECT, meter_type nullable for non-measuring)
#           AMENDED 2026-08-11 (tenant custom-fields lane): r17.2
#           `custom_data` on assets (BR-TEN-046; never a money input,
#           BR-TEN-048/DB-17). NOT reached by the R2 invoice stamp — OQ-118.
# Tests:    06-backend/tests/test_w1_models.py (constraint halves on the migrated
#           sqlite test DB; RLS assertions live in the G5 isolation suite) ·
#           test_us_ast_001_003_registry.py (meter_types/read_methods catalogs)
# Impacts:  W2 reads lane (meter_reads.asset_id + channel model, B2 r8) · S49–S55
#           frontend surface · metering unit wizard (asset create/link seam)
# ───────────────────────────────────────────────────────
"""assets models — the B2 r4 assets set, built to the CHANNEL-model end-state.

OWNERSHIP NOTE (flagged, not resolved): CLAUDE.md + B2 r16 #6 put the assets
tables under METERING's ownership ("assets set → metering; 05-assets is a DOC
module of metering's tables"). The W1 SCHEMA lane instruction hosts them in a
dedicated `apps.assets` Django app so the doc-module boundary stays visible —
an Eng hosting disposition exactly like tenancy hosting user_preferences/jobs
in W0. Table names and FKs are unchanged by the hosting choice; writes remain
metering-service-mediated per the epics ("writes via metering service
functions, B1"). REPORTED in the lane build report for the daily PO batch.

Schema law implemented here (signed): B2 r4 (assets generalize meters: type,
read_method, manufacturer, model, retire_date, status, parent_asset_id,
net_metering + asset_assignments + asset_maintenance) as REDLINED by r16 #3/#4
(build assets, never the superseded `meters` body; reads are W2), A5 v4
lifecycle via the BR-AST-031 Reference-data stage list with behavior classes,
and the story-§5 PROPOSED-SCHEMA columns carried verbatim (US-AST-004/008/009
extended specs, retire fields, final-read column; US-AST-010 import staging).
`asset_assignments.final_read_id` was declared a DEFERRED FK (B11 F-3);
MEASURED 2026-08-22 (CR-028 debt sweep D6): the constraint is UNADDABLE —
`meter_reads` is partitioned with composite PK (tenant_id, read_at, id), so
no unique(id) exists to reference (the `superseded_by_id` fact). See the
AssetAssignment docstring; integrity is the D5-wired capture service's law.

Deliberately absent: hardcoded type/status enums (BR-AST-004/031 — lookup
tables below); `deleted_at` (r4: retire, don't delete — hard delete exists
only for never-referenced inventory, a real row delete per BR-AST-013);
interval non-overlap DDL on assignments (BR-AST-017 — service-enforced; only
the one-current-row law is structural). PKs uuidv7-style (DB-2); multiplier/
tolerance NUMERIC(18,6) (DB-3); UoM always explicit, never assumed (rule 3).
RLS: every table below gets ENABLE+FORCE via migration 0002_rls_w1_policies
for the seven W1 tables and 0003_meter_types_and_read_methods for the two
BR-AST-043 catalogs (SQL in 06-backend/db/rls_assets_w1.sql, one file).

BR-AST-043 (PO 2026-08-09, CONFIRMED) adds the two reference lists the S8
Reference-data card grid has always ratified but no table ever backed:
`meter_types` (what the meter IS — AMI · AMR · walk-by · sub-meter · master;
US-TEN-009 TC-1 "Meter types 5") and `read_methods` (how the read is
COLLECTED — AMI · AMR · walk-by · Manual · Mobile, and since BR-MET-142
(2026-08-27) also Drive-by · Self-read · Field visit). The same rule REPLACES
B2 r4's plain-value `assets.read_method` with a PROTECTed FK into
`read_methods`. Neither list is B2's `meter_source` enum ('ami','manual',
'import'), which stays the read-source marker on `meter_reads` (W2).

BR-AST-044 (PO 2026-08-09, CONFIRMED) then adds the column BR-AST-043 declined
to invent: `assets.meter_type_id`, a PROTECTed FK into `meter_types`. An asset
now carries THREE catalog classifications, each answering a different question
— `type` (what kind of DEVICE it is, asset_types, required), `meter_type`
(what class of METER it is, meter_types, nullable) and `read_method` (how its
read is COLLECTED, read_methods, nullable). They are independent: an
asset_type=meter can be meter_type=ami, amr, walk_by, sub_meter or master, and
a non-measuring asset (PV, battery, cart) simply leaves meter_type null.
Migration 0004 adds the column with NO backfill — existing rows keep null,
because no signed rule maps an asset_type onto a meter type.
"""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.dbfields import uuid7_pk


class AssetType(models.Model):
    """Asset-types Reference-data list (BR-AST-004/009: meter, net_meter,
    sub_meter, backflow, comms, pv, battery, ev_charger, transformer,
    generator + seeded container_cart / modem_cpe per BR-AST-042; tenant-
    extensible per BR-TEN-036). `category` keys the S49 tab partition so
    tenant-added types keep 'every asset on exactly one tab' sound —
    the BR-AST-031 behavior-class pattern applied to types."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    category = models.TextField()  # meters | sub_meters | behind_the_meter (BR-AST-004 tabs)
    #: ⚠ **WHOSE THE KIT IS — `utility` · `customer`** (`CR-085` `CPB-10`,
    #: assets `0012`). A CODE the catalogue turns into *Ours* / *Yours* on the
    #: customer's Equipment screen (B14 rule 35), never English from a server.
    #: On the TYPE rather than on each asset for the reason `BR-AST-031` puts a
    #: behaviour class on a lifecycle stage: it is a property of the KIND of
    #: thing, answered once on Settings, and asking a clerk 40,000 times is how
    #: it gets answered wrong once. Seeded from `category` in `0012` and NEVER
    #: read off it live — `behind_the_meter` is the ordinary customer-owned
    #: case, and a utility that owns the battery it installed must be able to
    #: say so (`DEF-CWP-3765`: read the column, not the shape).
    maintained_by = models.TextField(default="utility")
    is_system = models.BooleanField(default=False)  # seeded rows deactivatable, never deletable
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_asset_types_tenant_code_ci"
            ),
        ]


class AssetLifecycleStage(models.Model):
    """Lifecycle stages as Reference data (BR-AST-031 CONFIRMED — seeded
    Inventory/Spare · Installed/Active · Needs repair · In repair · Retired;
    tenant-renamable/extensible; every stage maps to a system behavior class
    so transitions/filters key off the class, never the label)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    behavior_class = models.TextField()  # available | in_service | out_of_service | terminal
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_lifecycle_stages"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_asset_stages_tenant_code_ci"
            ),
        ]


class MeterType(models.Model):
    """Meter-types Reference-data list (BR-AST-043 CONFIRMED — what the meter
    IS: seeded AMI · AMR · walk-by · sub-meter · master, the five the S8 card
    grid ratifies at US-TEN-009 TC-1; tenant-extensible per BR-TEN-036).

    Deliberately shaped exactly like AssetType MINUS the tab key: BR-AST-043
    gives this list no behavior class and no partition — it is a flat named
    set.

    BR-AST-044 (PO 2026-08-09) ANSWERS the question BR-AST-043 left reported:
    an asset carries BOTH classifications, so `assets.meter_type_id` is a
    PROTECTed FK into this table (nullable — non-measuring assets leave it
    null). A meter type in use can therefore never be deleted, and its code is
    immutable once used (BR-TEN-030/034, live through the lookup handler)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)  # seeded rows deactivatable, never deletable
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meter_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_meter_types_tenant_code_ci"
            ),
        ]


class ReadMethod(models.Model):
    """Read-methods Reference-data list (BR-AST-043 CONFIRMED — how the read is
    COLLECTED: seeded AMI · AMR · walk-by · Manual · Mobile, PO-enumerated
    2026-08-09, plus Drive-by · Self-read · Field visit, added 2026-08-27 by
    BR-MET-142 on the PO's delegated ruling closing OQ-392; tenant-extensible
    per BR-TEN-036).

    ⚠ **THE THREE ADDITIONS ARE CATEGORIES, NOT ALIASES.** They were the legacy
    `read_batches.source_detail` words that mapped to no method at all, and each
    states a fact the other five cannot: `self_read` WHO read the meter,
    `field_visit` WHY somebody went, `mobile` WHAT DEVICE was used. Folding them
    onto neighbours would have re-labelled readings nobody verified — several of
    which are billed and which hard rule 4 forbids rewriting anyway.

    `assets.read_method` is a PROTECTed FK into this table (BR-AST-043
    supersedes the B2 r4 plain value), so a method in use cannot be deleted —
    the BR-TEN-034 audit-lock made structural."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "read_methods"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_read_methods_tenant_code_ci"
            ),
        ]


class Asset(models.Model):
    """The one asset registry (B2 r4, supersedes `meters` — r16 #3). Three
    identifiers per BR-AST-026: hidden uuid PK (never displayed) + serial_no
    (physical) + asset_no (user number from the tenant series, per-type
    prefix, override allowed; duplicate asset_no hard-blocked, duplicate
    serial warn-but-allow — BR-AST-033)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    asset_no = models.TextField()  # user-facing number (BR-AST-008: UNIQUE per tenant)
    serial_no = models.TextField(null=True, blank=True)  # duplicate = warn-but-allow
    #: ── BR-AST-049 (PO ruling 2026-08-27, decision log "A METER NUMBER IS
    #: ALLOCATED FROM THE TENANT'S SERIES, NEVER TAKEN FROM AN UPLOADED FILE")
    #: — THE UTILITY'S **OWN** LEGACY METER REFERENCE.
    #:
    #: ⚠ **THIS IS NEITHER `asset_no` NOR `serial_no`, AND CONFLATING IT WITH
    #: EITHER IS THE DEFECT THIS COLUMN EXISTS TO PREVENT.** `asset_no` is OUR
    #: number, and since the ruling it is issued by the tenant's `asset` series
    #: and NEVER taken off a file. `serial_no` is the MANUFACTURER'S serial —
    #: the number stamped on the device on the wall, and a duplicate of it is
    #: warn-but-allow (BR-AST-033), so it can never identify a row. This is the
    #: third fact: the id the utility's PREVIOUS software used. Overloading it
    #: onto `serial_no` would make a column that holds either and therefore
    #: means neither.
    #:
    #: The precedent is `customers.external_ref` (B2 r9 #1, BR-CUS-054) —
    #: same problem, same name, same partial CI unique, deliberately.
    external_ref = models.TextField(null=True, blank=True)  # the LEGACY id
    type = models.ForeignKey(AssetType, on_delete=models.PROTECT, db_column="type_id")
    status = models.ForeignKey(  # lifecycle stage (BR-AST-031); transitions per BR-AST-020
        AssetLifecycleStage, on_delete=models.PROTECT, db_column="status_id"
    )
    service_point = models.ForeignKey(  # ⚠ cross-module → metering (reviewed set); NULL for
        "metering.ServicePoint",  # non-measuring BTM types (BR-AST-009 — service law)
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_point_id",
    )
    parent_asset = models.ForeignKey(  # sub-meter self-reference (BR-AST-003)
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="parent_asset_id",
        related_name="sub_assets",
    )
    meter_type = models.ForeignKey(  # BR-AST-044: the meter's OWN class (AMI ·
        MeterType,  # AMR · walk-by · sub-meter · master), independent of `type`
        on_delete=models.PROTECT,  # PROTECT — a referenced type is never deletable
        null=True,  # non-measuring assets (PV, battery, cart…) leave it null
        blank=True,
        db_column="meter_type_id",
        related_name="assets",
    )
    read_method = models.ForeignKey(  # BR-AST-043: catalog FK, not a plain value
        ReadMethod,  # PROTECT — a referenced method can never be deleted
        on_delete=models.PROTECT,
        null=True,  # non-measuring BTM assets collect no read at all
        blank=True,
        db_column="read_method_id",
        related_name="assets",
    )
    #: ── BR-AST-500 (DEF-514 · DEF-1811) — THE CONNECTION'S SIZE CLASS.
    #:
    #: `service_size_classes.code` as TEXT, NULL when nobody has recorded one.
    #: This is the fact R3 of the R1–R7 resolution chain narrows the base
    #: charge on (BR-RAT-108, PO verbatim: *"based on Asset and Account type
    #: you will have select 1 base charge"*) and the fact DEF-433's per-size
    #: tier ladder is keyed by. Until this column existed the product **stored
    #: a connection size on no table at all** — not here, not on
    #: `metering.ServicePoint`, not on `metering.Unit` (DEF-255 checked
    #: `information_schema` for `%size_class%` and found nothing) — so
    #: `assets_on_unit` published none, `route_meter_picker.size_class` drew a
    #: permanently empty column, `gather._connection_size_for` had nothing to
    #: pass and the shadow adapter could not be run on a single real account of
    #: any tenant (`attempted 0 · blocked {connection_size_unresolved: 1}`).
    #:
    #: ⚠ **TEXT AND NOT AN FK, AND THAT IS `RateSizeRow`'s OWN REASONING
    #: REACHED ONE TABLE ACROSS.** `rating.ChargeCodeAmount.size_class` and
    #: `rating.RateTier.size_class` are both TEXT for a stated reason: *"a size
    #: Settings RETIRES must not vanish from a schedule that already priced
    #: it"*. The same holds for a meter that is already installed — a utility
    #: deactivating `W-4` on S8 must not thereby erase what is bolted to the
    #: wall on Quarry Hill Road. A cross-module FK is also a REVIEWED interface
    #: (B2 §2) and this row does not need one.
    #:
    #: ⚠ **NOT VALIDATED AGAINST THE LIVE LIST, FOR THE SAME REASON RATING
    #: DOES NOT VALIDATE ITS COPY** (`services._size_rows`: *"`size_class` IS
    #: NOT CHECKED AGAINST `service_size_classes`, DELIBERATELY"*). An
    #: existence check would refuse exactly the retired-size case above. The
    #: picker offers the live list; the column keeps what was recorded.
    #:
    #: ⚠ **AND THE LIST IS NOT SERVICE-SCOPED (BR-TEN-078)** — the row names
    #: its service in its own display name (`Water 5/8"`, `Electric 1φ 100A`),
    #: so `W-58` on an electric meter is expressible and is a data error, never
    #: a schema one. Refusing it here would refuse a tenant's own added row too.
    size_class = models.TextField(null=True, blank=True)
    multiplier = models.DecimalField(max_digits=18, decimal_places=6, default=1)  # > 0, explicit
    unit = models.TextField(null=True, blank=True)  # explicit UoM (rule 3); required for
    #   measuring types — enforced by the asset service, NULL only for non-measuring BTM
    net_metering = models.BooleanField(default=False)  # BR-AST-010; feeds W2 export channel
    manufacturer = models.TextField(null=True, blank=True)
    model = models.TextField(null=True, blank=True)
    install_date = models.DateField(null=True, blank=True)  # required when assigning
    # Extended capture-only specs (BR-AST-014 — display/validation only, no EAM depth)
    form_class = models.TextField(null=True, blank=True)  # '2S'
    register_digits = models.SmallIntegerField(default=9)  # BR-AST-015: read bound; DEFAULT 9
    firmware_version = models.TextField(null=True, blank=True)
    seal_no = models.TextField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)  # single date, no claims depth
    last_test_date = models.DateField(null=True, blank=True)  # updated by kind=test entries
    test_interval_months = models.SmallIntegerField(null=True, blank=True)  # seeds per
    #   BR-AST-027 (backflow 12 / meter 96) ride the reference-data seeding lane
    location_note = models.TextField(null=True, blank=True)  # ≤280 (service law)
    # ── CR-028 valuation & certification (BR-AST-047, PO 2026-08-22) ─────────
    # Everything here lives ON THE DEVICE RECORD and is OPTIONAL: "We capture
    # deprecision methid as optional, even meter cost are optional, you will
    # also need life to be calculated" — and NONE of it reaches finance
    # (no journal line, no GL account; a future linkage is a new CR).
    supplier = models.TextField(null=True, blank=True)  # D5: free text, no list yet
    purchase_cost = models.DecimalField(  # money: STORED 4dp, displayed 2 (rule 2, D10)
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    purchase_date = models.DateField(null=True, blank=True)
    depreciation_method = models.TextField(null=True, blank=True)  # optional; display
    #   assumes straight-line when unset — never a stored default pretending a choice
    expected_life_years = models.SmallIntegerField(null=True, blank=True)  # life must
    #   be CALCULABLE (age · past-life · replacement forecast) — BR-AST-047
    certification_due = models.DateField(null=True, blank=True)  # explicit (import
    #   CERT_DUE); when unset the display derives last_test_date + interval
    export_capacity_kw = models.DecimalField(  # BTM inverters only — a capacity, not money
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    # ── CR-028 AST-W3 (B16 §4.7b — the sub-meters import's ALLOC_PCT) ────────
    #: The sub-meter's allocation SHARE of its master, as a percentage
    #: (hard rule 2: percentages stored to 6 decimals). NULL means "metered,
    #: not allocated" (B16 §4.7b verbatim) — the sub bills its own register and
    #: no share applies. A percentage, never money; nothing prices off it yet.
    allocation_share_pct = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    # Master-meter reconciliation config (US-MET-003 §5 — lives on the master asset)
    allocation_rule = models.TextField(null=True, blank=True)  # rubs | sqft | equal | absorb
    loss_tolerance_pct = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    # Retirement (B2 r4 retire_date + US-AST-008 §5 PROPOSED-SCHEMA reason/replacement)
    retire_date = models.DateField(null=True, blank=True)  # ≥ install_date (service law)
    retire_reason = models.TextField(null=True, blank=True)  # end_of_life | failed |
    #   replaced | removed (required at retire — service law)
    replaced_by_asset = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="replaced_by_asset_id",
        related_name="replaces_assets",
    )
    # D4 (BR-AST-047): retire COMPUTES book value and RECORDS the operator's
    # chosen treatment — it posts nothing. The recorded pair is the future
    # journal's source if finance linkage ever comes (kept by PO instruction).
    book_value_amount = models.DecimalField(  # $164.00 − $19.83 = $144.17 shape; 4dp stored
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    book_value_treatment = models.TextField(null=True, blank=True)  # write_off |
    #   warranty_claim | hold — required at retire only when a book value exists
    #: r17.2 — tenant-defined VALUES for the `custom_field` definitions tenancy
    #: owns (`feeder_number`, `pole_tag` are this epic's own examples). A column
    #: on the OWNING row, never a shared value table: that table would be
    #: written by customers, metering AND assets, which DB-16/§2 forbids as a
    #: cross-module write. DB-17: no money path may read it except
    #: `apps/billing/custom_snapshot.py`, and G6 enforces that rather than
    #: review. Assets are NOT reached by the R2 invoice stamp — an account can
    #: have many meters and the snapshot's key space is flat `<entity>.<key>`
    #: with no ruled disambiguation (OQ-118).
    custom_data = models.JSONField(default=dict, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets"
        constraints = [
            # BR-AST-008/033: duplicate asset # = hard block, per tenant.
            models.UniqueConstraint(fields=["tenant", "asset_no"], name="uq_assets_tenant_no"),
            # ── BR-AST-049 — UNIQUE PER TENANT, CASE-INSENSITIVELY, PARTIAL.
            #
            # **DECIDED, not inherited** (decision log 2026-08-27, "WHAT THE
            # RULING LEFT TO US"): the whole point of a legacy reference is
            # that it identifies ONE row in the system we migrated from, so a
            # second row claiming it is a data error we can see, and the only
            # moment we can see it is the load. Worked: a utility loading
            # 1,847 meters with `external_ref` NOT unique, re-running the same
            # corrected file, gets 1,847 SECOND assets numbered M-01848 …
            # M-03694 and no way to tell the two sets apart. Unique refuses
            # the second load by name, one row at a time.
            #
            # CASE-INSENSITIVE for `customers.external_ref`'s stated reason:
            # `MTR-118` and `mtr-118` are one device in every legacy export.
            # PARTIAL because an asset created by the AST-05 wizard has no
            # legacy reference at all and N of those must coexist.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_assets_tenant_external_ref_ci",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "service_point"], name="ix_assets_tenant_sp"),
        ]


class AssetAssignment(models.Model):
    """Asset ↔ unit history (B2 r4; BR-AST-017: append-only, non-overlapping,
    exactly one current row when assigned — the one-current law is structural
    below; interval non-overlap is the reassign service's transaction law).

    final_read_id — MEASURED 2026-08-22 (CR-028 debt sweep, D6): the "DEFERRED
    FK → meter_reads (B11 F-3, constraint with the reads migration)" this
    docstring promised since W1 CANNOT BE ADDED. `meter_reads` is partitioned
    monthly on `read_at` with composite PK (tenant_id, read_at, id) — Postgres
    requires an FK into a partitioned table to reference a unique constraint
    INCLUDING the partition key, and no unique index on `id` alone can exist.
    This is the SAME schema fact that makes `meter_reads.superseded_by_id` a
    bare uuid rather than the self-FK B2 r8 writes. Closing it needs a B2
    addendum (e.g. a `final_read_at` column beside the id and a composite FK)
    — a schema-law change, not this lane's call. Until then the integrity is
    SERVICE law, now real: the only writer of this column is the D5-wired
    capture path (`metering.capture_final_read` → the fresh committed read's
    id, one transaction with the move), tested end to end in
    tests/test_cr028_final_read_capture.py. Hard-won law 1: this paragraph
    replaces a promise with the measurement that disproved it."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, db_column="asset_id")
    unit = models.ForeignKey(  # ⚠ cross-module → metering units (reviewed set)
        "metering.Unit", on_delete=models.PROTECT, db_column="unit_id"
    )
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)  # NULL = current
    actor_user = models.ForeignKey(  # "System" when NULL (US-AST-006 §5)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="actor_user_id",
    )
    final_read_id = models.UUIDField(null=True, blank=True)  # bare uuid — see class docstring (D6)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # closure sets to_date/final_read only

    class Meta:
        db_table = "asset_assignments"
        indexes = [
            models.Index(fields=["tenant", "asset"], name="ix_asset_assignments_asset"),
        ]
        constraints = [
            # BR-AST-017: at most one current assignment row per asset.
            models.UniqueConstraint(
                fields=["asset"],
                condition=Q(to_date__isnull=True),
                name="uq_asset_assignments_current",
            ),
        ]


class AssetMaintenance(models.Model):
    """Append-only maintenance log (B2 r4 `asset_maintenance`; BR-AST-018:
    kind repair|inspection|test; a test entry updates assets.last_test_date;
    entries are never edited or deleted — corrections are new entries)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, db_column="asset_id")
    kind = models.TextField()  # repair | inspection | test
    date = models.DateField()
    detail = models.TextField()
    tech_user = models.ForeignKey(  # US-AST-006/007 §5 PROPOSED-SCHEMA
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="tech_user_id",
    )
    resulting_status = models.ForeignKey(  # legal per BR-AST-020 (service law); NULL = no change
        AssetLifecycleStage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="resulting_status_id",
        related_name="maintenance_results",
    )
    closed_at = models.DateTimeField(null=True, blank=True)  # US-AST-006 §5 PROPOSED-SCHEMA
    cost = models.DecimalField(  # CR-028 D3: CAPTURED and totalled, never posted —
        max_digits=18, decimal_places=4, null=True, blank=True
    )  # the r10 "posts to O&M 5300" sentence is OMITTED by PO ruling
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_maintenance"
        indexes = [
            models.Index(fields=["tenant", "asset"], name="ix_asset_maintenance_asset"),
        ]


class AssetImportBatch(models.Model):
    """S52 bulk-import staging batch (US-AST-010 §5 PROPOSED-SCHEMA verbatim,
    mirroring the S28 read-import pattern; contract per BR-AST-023/034 —
    staged, ≤10,000 rows, result summary always shown)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    filename = models.TextField()
    uploaded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="uploaded_by",
    )
    row_count = models.IntegerField(default=0)
    valid_count = models.IntegerField(default=0)
    skip_errors = models.BooleanField(default=True)  # commit strategy (default on — PO R4-A5)
    committed_at = models.DateTimeField(null=True, blank=True)  # NULL until explicit commit
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_import_batches"


class AssetImportRow(models.Model):
    """Per-row staging record (US-AST-010 §5: batch_id, row_no, raw jsonb,
    errors jsonb, asset_id NULL until commit). tenant_id carried per DB-1 —
    every tenant-scoped table is RLS-scoped."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(AssetImportBatch, on_delete=models.PROTECT, db_column="batch_id")
    row_no = models.IntegerField()
    raw = models.JSONField()
    errors = models.JSONField(null=True, blank=True)
    asset = models.ForeignKey(  # set at commit for created/updated rows
        Asset, on_delete=models.PROTECT, null=True, blank=True, db_column="asset_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_import_rows"
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_no"], name="uq_asset_import_rows"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@9d8d058 (story+rules snapshot — EP-AST-01..04 W1 schema half + B2 r4/r16)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-043 reference-data gap lane — meter_types + read_methods) · AMENDED 2026-08-09 by story-coder (BR-AST-044 both-classifications lane) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (allocation_share_pct NUMERIC(18,6) — B16 §4.7b's ALLOC_PCT (migration 0008, HUMAN-REVIEW-PENDING))
# checklist: A✔ B=deferred(table-half only — service/API TCs land with each story lane) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ migrate-from-empty✔ makemigrations --check✔ · suite `pytest tests -m "not golden and not isolation"` 587 passed / 8 skipped (580 baseline green + the 7 new BR-AST-043 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (13 baseline + 1 new) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0003 data path exercised on a scratch file-backed sqlite DB seeded at 0002 (ami→AMI, 'AMR'→amr case-insensitively, 'na'→NULL+logged, NULL→NULL; reverse restores the codes and drops both tables) · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [BR-AST-044 lane 2026-08-09] ruff✔(E4/E7/E9/F) black✔ migrate✔ makemigrations --check✔ (hand-written 0004 matches the model state) · suite `pytest tests -m "not golden and not isolation"` 593 passed / 8 skipped (587 baseline green + 6 new BR-AST-044 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (unchanged) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy STILL NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: hosting disposition — metering owns the assets set (r16 #6/CLAUDE.md) but tables are HOSTED in apps.assets per the W1 lane instruction (REPORTED, PO batch) · asset_assignments.final_read_id = deferred FK (meter_reads W2; B11 F-3) · asset_types.category = Eng-proposed tab key (BR-AST-004 soundness, BR-AST-031 pattern — REPORTED) · interval non-overlap on assignments left to the reassign service (only one-current-row structural) · type/stage seeds ride the tenant fixture-seeding lane, not migrations · BR-AST-043 gap lane 2026-08-09: `meter_types` + `read_methods` added (migration 0003, RLS in the marked section of db/rls_assets_w1.sql) and `assets.read_method` rewired from a plain value to a PROTECTed FK — B2 r4's fourth plain value 'na' has no counterpart in the PO's ratified five and is no longer accepted (REPORTED) · NO column references `meter_types` yet: whether an asset should carry a meter_type_id is REPORTED, not decided here · one incidental black reflow of the pre-existing loss_tolerance_pct declaration (line-length 100, no semantic change) · BR-AST-044 lane 2026-08-09: `assets.meter_type_id` added (migration 0004, additive column only — NO backfill, existing rows keep NULL because no signed rule maps an asset_type onto a meter type; the registry's `f.meter_type=none` filter is how a tenant finds what still needs classifying). The "should an asset carry a meter_type_id?" question models.py reported at BR-AST-043 is now ANSWERED by the PO, not by this lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
