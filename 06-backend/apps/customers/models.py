# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (EP-CUS-01 Accounts list — `accounts` + the BR-CUS-055
#           status lookup it renders) · US-CUS-003 (EP-CUS-02 New Account
#           wizard — the account/contact/address/service-agreement row set its
#           §5 field map targets)   Screens: S17 · S18 · S8 (Reference data)
# Rules:    BR-CUS-012 (account attribute set — type/sub-type/deposit/tax-
#           exempt/autopay/credit tier) · BR-CUS-016 (stored status comes from
#           the account-status LOOKUP; aging is derived, never stored) ·
#           BR-CUS-017 (one account ↔ one unit; at most ONE active account per
#           unit — see the boundary note below) · BR-CUS-055 (the five seeded,
#           tenant-extensible statuses + their behaviour classes, OQ-058(b) /
#           OQ-064 CLOSED) · BR-CUS-045 (contact PII columns) · BR-CUS-064
#           (accounts.preferred_language) · BR-TEN-036 (former enums become
#           seeded, tenant-extensible lookup tables) · BR-TEN-030/034 (code
#           immutable once used; used rows are not deletable)
#           AMENDED 2026-08-11 (tenant custom-fields lane): r17.2
#           `custom_data` on accounts · contacts · addresses ·
#           service_agreements (BR-TEN-046; never a money input,
#           BR-TEN-048/DB-17). The now-false 'NOT built' claim this file
#           carried in two places is corrected below.
#           AMENDED 2026-08-11 (US-CUS-019 account-import lane): the r9 #1
#           customer entity (`customers` + `customer_accounts`, BR-CUS-054)
#           and the two US-CUS-019 §5 staging tables
#           (`account_import_batches` + `account_import_rows`, carrying the
#           🔒 DB-12 file+tags idempotency pair).
# Tests:    06-backend/tests/test_w2_models.py (constraint + money-precision
#           halves on the migrated sqlite test DB) ·
#           06-backend/tests/test_us_cus_schema_and_seed.py (seam + live-RLS
#           halves; the RLS assertions run in the G5 isolation suite)
# Impacts:  apps/customers/lookups.py (the two S8 cards) · apps/customers/
#           services.py (the tenancy reference-seeding seam) · apps/tenancy
#           LOOKUP_LISTS `account_statuses` + `account_types` · rating's
#           DEFERRED account_type_id/account_subtype_id columns (B11 F-3) ·
#           every later customers lane (account CRUD, move-in/out, import)
# ───────────────────────────────────────────────────────
"""customers models — the B2 §2 `Module: customers` DDL, redlined by r16.

Schema law implemented here (signed, never invented):
- **B2 §2 customers** — `accounts` · `contacts` · `addresses` ·
  `service_agreements`, column-for-column, including the cross-module FK set
  §2 marks with ⚠ and reviews (`accounts.unit_id` → metering `units`,
  `service_agreements.service_point_id` → metering `service_points`).
- **B2 post-design confirmations (finance, 2026-08-07)** — `accounts.
  tax_exempt` / `.tax_exempt_ref` / `.tax_exempt_expires` (account-level
  exemption, B4.2).
- **r5 #12 / #19** — `account_types` (PLATFORM, no tenant_id) +
  `account_subtypes` (tenant-defined, RLS) and the two columns they hang on
  `accounts`.
- **r5 #20 (BR-TEN-036) + r9 #7 (BR-CUS-055)** — the account-status ENUM
  becomes the seeded, tenant-extensible `account_statuses` LOOKUP carrying a
  `behavior_class`. The swap is per-module at build waves; customers builds in
  W2, so it happens here and B2 §2's `status account_status` enum column never
  materializes.
- **r9 #5** `accounts.deposit_received_on` · **r9 #6** `accounts.credit_tier`
  as a COMPUTED cache (BR-CUS-058) · **r12 #8** `accounts.bad_address` ·
  **r12 #12** `accounts.nsf_count` · **r15 #2** `accounts.preferred_language`
  (BR-CUS-064).
- **r16 #3** — `service_agreements.tariff_id` is SUPERSEDED (by the
  BR-CUS-029 plan-assignment record), so the column is NOT built. See the
  deliberate-omissions list below.

Money is NUMERIC(18,6) + CHAR(3) currency, never float and never cents
(CLAUDE.md rule 2 / DB-3). PKs are uuidv7-style (DB-2, O-1 residue → app-side
shim). RLS: every TENANT table below gets ENABLE + FORCE via migration
0002_rls_w2_policies (B2 §3 template verbatim); `account_types` is the one
table here with NO tenant_id and therefore no policy — r5 closes with
"platform tables (services, account_types, B10 set) excluded per B2 §3".

────────────────────────────────────────────────────────────────────────────
BR-CUS-017's enforcement — REPORTED here, RULED on 2026-08-10 (OQ-092 CLOSED)
────────────────────────────────────────────────────────────────────────────
UPDATE (customers slice 2): the boundary below was reported by this file and
the PO closed it the same day — OQ-092, option (a): **service-layer
enforcement only**, "the check runs inside the create/update transaction with
row locking so two concurrent requests cannot both win, and a test proves the
race is closed. No denormalised column is added — it could drift from the
status FK and would be a second source of truth for the same fact."

So the absence of the index below is now the RULING, not an open gap: it stays
absent permanently, pinned by
`test_us_cus_001_tc5__one_active_account_per_unit_has_no_database_half`, and
the rule is enforced in apps/customers/services.py (`lock_unit_scope` +
`_refuse_if_unit_occupied`, proved in tests/test_us_cus_003_account_race.py).
The original report is kept verbatim below because it is why the ruling reads
the way it does.


BR-CUS-017 ("at most ONE active account per unit") is CONFIRMED as a RULE.
Its *enforcement* is recorded as PROPOSED-SCHEMA: a partial unique index on
`accounts(tenant_id, unit_id) WHERE status = 'active'`. That proposal assumes
`status` is the B2 §2 ENUM column. r5 #20 / BR-CUS-055 replace it with a
tenant-extensible LOOKUP, and a PostgreSQL partial-index predicate cannot
read `account_statuses.behavior_class` through the FK — the predicate may
only name this table's own columns. So the proposed index is not
constructible as written, and NO substitute is invented here: adding a
denormalized status code column, or keying the predicate on `closed_at`,
would each be a different rule than the one the PO signed.

Consequence, stated plainly: the one-active-account-per-unit law has NO
database half in this slice. It is enforceable in the customers SERVICE the
day account writes land (the same slice that owns BR-CUS-020's vacant-unit
picker), and the choice between "service-only" and "a new signed column that
makes the index constructible" is a PO/Eng-Lead call, not this lane's.
REPORTED in the lane report and in the human-review ledger row for migration
0001.  ← ANSWERED: service-only, per the OQ-092 closure recorded above.

────────────────────────────────────────────────────────────────────────────
DELIBERATELY NOT BUILT in this slice (each named, none silently dropped)
────────────────────────────────────────────────────────────────────────────
- `service_agreements.tariff_id` — SUPERSEDED by r16 #3 in favour of the
  BR-CUS-029 plan-assignment record. That record (`account_plan_assignments`,
  r12 #14) has no DDL in B2 or any addendum; authoring one would be inventing
  schema, so neither the superseded column nor its replacement ships here.
- ~~r9 #1 `customers` + `customer_accounts`~~ — **BUILT 2026-08-11**
  (migration 0005, the US-CUS-019 account-import lane). This entry used to
  group them with the tables that have "no column list in B2"; r9 #1 DOES give
  one — *"`customers` (kind person|company, display_name, external_ref UNIQUE
  per tenant) + `customer_accounts` N:M link"* — and the claim was false the
  day someone read that line. Corrected rather than left standing (hard-won
  law 1).
- ~~r9 #4 the three import-staging tables~~ — **TWO OF THREE BUILT 2026-08-11**
  (`account_import_batches` + `account_import_rows`, from US-CUS-019 §5's own
  column list). `account_import_value_maps` is NOT built: it belongs to
  US-CUS-020, which this lane did not build, and a table with no writer is a
  promise.
- r9 #2 `account_opening_buckets` · r9 #6 `credit_tier_rules` · r5 #5
  `account_capacities` — still PROPOSED-SCHEMA with no column list in B2
  ("Exact DDL of all addenda = Eng-Lead 🔒 at migration authoring"). The
  opening-bucket columns of the US-CUS-019 template are PARSED and staged, and
  writing them is US-CUS-021's story, not this one's.
- The story-§5 PROPOSED-SCHEMA columns on `accounts` (budget_billing,
  statement_language, deposit_election, deposit_waive_reason_id,
  deposit_interest_accrued, portal_enabled, autopay_method_id)
  — every one of them hangs off a story whose `status:` is still `draft`. They
  are additive columns on a table that ships empty, so they cost nothing to add
  later and would cost a review now.
  ⚠ **THIS LIST NAMED `paperless`, `sms_reminders` AND `template_override_id`
  UNTIL 2026-08-31 AND ALL THREE ARE NOW BUILT** (migration 0034, CR-052 tasks
  12 and 14). They came out of the "cost a review now" bucket because a
  CONFIRMED rule was waiting on each: BR-BIL-036 makes print the floor with
  email and SMS *elected on top* and the election could not be read, and
  BR-BIL-025 resolves the bill template *account override → category default →
  fallback* with no column for the first leg. Corrected rather than left
  standing — hard-won law 1.
  ⚠ **AND IT NAMED `close_reason` UNTIL 2026-09-20, WHEN IT LEFT THE BUCKET FOR
  THE SAME REASON THOSE THREE DID** (migration 0058, PO ruling of that date,
  option A). The rule waiting on it was not merely confirmed, it was drawn and
  ignored: the move-out wizard has named five reasons on screen and stored none
  since the day it shipped, which the blueprint's own dashed panel on p110
  calls *"worse than not asking"*. See `CLOSE_REASONS` below for the
  vocabulary and `Account.close_reason` for why NULL stays NULL on every
  account already closed.
- ~~r17.2 `custom_data jsonb`~~ — **BUILT 2026-08-11** (migration 0004). This
  entry used to read "NOT built — r17 forbids DDL while OQ-075/076/077 are
  OPEN". All three closed on 2026-08-10 (OQ-075 warn-don't-block + a default
  value · OQ-076 *"Dont put SSN on invoices"*, mechanism confirmed INVERTED /
  fail-closed · OQ-077 the MT publish gate → BR-SHL-043), so r17.6's DDL block
  lifted and the claim above became false while nothing in this file changed.
  Corrected rather than left standing: hard-won law 1 — a comment claiming a
  guarantee is not the guarantee, and it works in this direction too.
- `contacts` re-homing onto the customer entity (r9 #1, "Eng-Lead
  disposition") — `contacts.account_id` stays exactly as B2 §2 declares it.
  STILL TRUE after the customer entity landed: moving a live PII table's
  parent is not a side effect of an import story.
"""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.crypto import EncryptedTextField
from core.dbfields import CITextField, uuid7_pk
from core.money_fields import money_field


class AccountType(models.Model):
    """TENANT-OWNED consumer category — **seeded with seven, extensible without
    limit** — plus one LEGACY code no new record may pick.

    ⚠ **THE PO RULING OF 2026-09-17 SUPERSEDES `BR-CUS-094`'s PLATFORM POSTURE,
    IN THEIR OWN WORDS: *"utility can get their own account types"*.** Until that
    day this table was a PLATFORM table — no `tenant_id`, no RLS policy, a
    GLOBAL `UniqueConstraint(Lower("code"))`, and `customers/lookups.py`
    refusing create/update/set_active/delete by name. The question put to the PO
    was a straight either/or (*do utilities get their own account types, or do
    the seven stay the signed vocabulary and the screen simply stops pretending
    they're editable?*) and they chose the first. **So the seven stop being the
    vocabulary and become the SEED**, and this table joins the two lookup tables
    either side of it: `account_statuses` and `account_subtypes` were already
    seeded, tenant-extensible and RLS-scoped, and `account_types` was the single
    exception. It is the house pattern now — `BR-TEN-030` (a code is frozen once
    used), `BR-TEN-034` (a used row is not deletable; a deactivated row stops
    being pickable), `BR-TEN-036` (a seeded row is deactivatable, never
    deletable).

    ⚠ **WHAT THAT COSTS, SAID PLAINLY RATHER THAN LEFT TO BE FOUND:** two
    tenants may now use ONE code for DIFFERENT meanings. `rating` stores the
    code as TEXT in charge narrowing and in the plan/tax targeting JSON lists,
    and those columns keep working because every read of them happens inside one
    tenant's context — but a code is no longer a platform-wide fact and no
    module may treat it as one. **Every hardcoded consumer is now a real bug**
    where before it was a defensible reading of a platform vocabulary.

    ⚠ **`SEVEN_CATEGORIES` KEEPS ITS NAME AND STOPS BEING THE VOCABULARY.** It
    is the SEED — what a brand-new tenant's list holds on day one — and reading
    it as the set of lawful values is what `service_request_api` did until
    `DEF-CUS-5647`, which silently dropped every row a tenant added. The name is
    deliberately NOT changed: `apps/rating/seams.py` and four test files cite it,
    a sibling lane is de-hardcoding those consumers in the same window, and
    renaming a constant under a running lane is a collision (CLAUDE.md law 11).
    **Read the tenant's rows; fall back to this tuple only for a tenant that has
    none** — `metering._resolve_unit_type` is the shape, and a DEACTIVATED row is
    deliberately not resurrected by the fallback (`BR-TEN-034`).

    ⚠ **`government` IS NOT ONE OF THE SEVEN, AND IT IS NOT RE-LABELLED.**
    `BR-CUS-094` was explicit that this is the part it could not settle for us:
    *"Municipal and Institutional are both plausible readings of it — a city
    water department and a state university are different things and the stored
    value cannot tell them apart. So no row is re-labelled by guess."* It is
    marked `legacy=True`, which **stops it being selectable on new records and
    changes nothing else** — still a valid FK, still filterable, still priceable,
    every existing account keeps it and bills exactly as it did yesterday.
    Re-pointing is a human act per record.

    `is_system` follows the BR-TEN-036 shape: a seeded row is deactivatable,
    never deletable. `legacy` is a THIRD axis and not a synonym for either:
    `active=False` retires a code from every surface; `legacy=True` keeps it
    working everywhere it already works and only closes the picker.

    `sort_order` answers the one question the ruling opens and nothing else
    settles: **where does a row a tenant ADDS go in a picker the PO drew?** The
    seeded seven carry `BR-CUS-094`'s ruled order as 10..70, `government` sits at
    900 behind them, and a tenant-added row is appended at `max + 10` — so the
    drawn screen keeps the order it was drawn in and a new row lands after it,
    in the order the tenant created them. The S8 reference-data CARD still sorts
    by `code` like every other card (IS-2); this column is the PICKER's order.
    """

    #: `BR-CUS-094`'s seven, in the ruling's own order. ⚠ **THIS IS THE SEED,
    #: NOT THE VOCABULARY — PO ruling 2026-09-17.** See the class docstring.
    SEVEN_CATEGORIES: tuple[tuple[str, str], ...] = (
        ("residential", "Residential"),
        ("commercial", "Commercial"),
        ("industrial", "Industrial"),
        ("agricultural", "Agricultural"),
        ("institutional", "Institutional"),
        ("municipal", "Municipal"),
        ("builder_developer", "Builder or developer"),
    )
    #: The codes `BR-CUS-094` marks legacy. A legacy code is UNSELECTABLE on new
    #: records and lawful everywhere else.
    LEGACY_CODES: tuple[str, ...] = ("government",)

    #: The gap the seeded rows are spaced by, and where a tenant-added row lands
    #: (`max + SORT_ORDER_STEP`). Legacy rows start at LEGACY_SORT_ORDER so they
    #: sit behind everything a tenant can pick.
    SORT_ORDER_STEP: int = 10
    LEGACY_SORT_ORDER: int = 900

    id = uuid7_pk()
    #: PO ruling 2026-09-17. NOT NULL, exactly like `account_statuses` and
    #: `account_subtypes`: there is no such thing as a platform row any more, so
    #: a row with no tenant would be a row no policy can reach.
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # seeded from SEVEN_CATEGORIES/LEGACY_CODES, or the tenant's own
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    #: BR-CUS-094 — unselectable on new records, valid everywhere else.
    legacy = models.BooleanField(default=False)
    #: PICKER order (see the class docstring). The card sorts by `code`.
    sort_order = models.IntegerField(default=LEGACY_SORT_ORDER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_types"
        constraints = [
            # TENANT table since the PO ruling of 2026-09-17: the code is unique
            # WITHIN one utility and two utilities may lawfully use the same one
            # for different things. The global constraint this replaces
            # (`uq_account_types_code_ci`) is dropped by customers.0054.
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_account_types_tenant_code_ci"
            ),
        ]


class AccountSubtype(models.Model):
    """TENANT-DEFINED sub-category (r5 #12 [D5]: "account_subtypes
    (tenant-defined, RLS)") — since CR-010 a TWO-LEVEL tree under the
    platform `account_types` (BR-CUS-067).

    The paragraph that stood here until 2026-08-18 said the table ships with
    NO seed and no parent-type FK, because r5 #12 was one line and inventing
    the link would have answered an unasked question. The question was ASKED
    and ANSWERED on 2026-08-17 (CR-010, decision log "Part-10 confirmations",
    PO verbatim *"add them"*): the sub-type tree ships exactly as drawn —
    Residential (Single-family · Multi-family · Senior/Low-income), Commercial
    (Small · Large · Institutional & non-profit · Healthcare), Industrial
    (Light · Heavy), Municipal/Government (Municipal buildings · Schools ·
    Parks & facilities). So `account_type` is the parent FK (migration 0011),
    the 12 rows seed per tenant through `seed_reference_list`
    (SEED_ACCOUNT_SUBTYPES), and the S8 card renders type → sub-type.

    `account_type` is NULLABLE deliberately: rows created before 2026-08-18
    (the table has been writable since W2) carry no parent and nothing signed
    invents one for them; the LOOKUP HANDLER requires a parent on every new
    or edited row, so the tree is two-level from here on. `accounts.
    account_subtype_id` references this table; rating's `account_subtype_id`
    column is still DEFERRED (B11 F-3)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: CR-010 (PO 2026-08-17): the parent type. ⚠ **SINCE THE PO RULING OF
    #: 2026-09-17 THIS IS A TENANT-ROW → TENANT-ROW FK** — `account_types` is no
    #: longer a platform table, so parent and child now belong to the SAME
    #: utility and `customers.0054` repointed every existing row at its own
    #: tenant's clone. PROTECT: deleting a type that has sub-types under it must
    #: refuse.
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_type_id",
        related_name="subtypes",
    )
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_subtypes"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_account_subtypes_tenant_code_ci"
            ),
        ]


class AccountStatus(models.Model):
    """The account-status Reference-data list (r5 #20 enum→lookup + r9 #7).

    BR-CUS-055 (CONFIRMED — PO OQ-058 option b; class seed OQ-064 CLOSED)
    names the seed and its behaviour classes:

        Pending activation   → non_billable
        Active               → billable
        Marked disconnect    → billable          (consuming until cut)
        Vacation hold/Suspended → billable_base_only
        Closed               → terminal

    Tenant-extensible (US-CUS-020 TC-3 adds "Legal hold"), which is exactly
    why this is a table and not an enum. Every status carries a behaviour
    class so billing keys off the CLASS, never the tenant's label — the same
    shape assets uses for its lifecycle stages (BR-AST-031).

    The older readings — B2 §2's `account_status` ENUM, A5 §Account (which A5
    itself marks UNKNOWN) and the S8 prototype card — all PREDATE the ruling
    and do not reopen it."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    # non_billable | billable | billable_base_only | terminal (BR-CUS-055)
    behavior_class = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_statuses"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_account_statuses_tenant_code_ci"
            ),
        ]


#: CR-038 W9 task 4 — the vocabulary of `Account.final_read_state`: how the
#: move-out settlement's final read was obtained. B18 §5.6.2 draws exactly
#: these three on the FINAL READ cell (`taken` · `due` · `estimated` — the
#: third amber, and the one that had no store until this column). Derived at
#: close by `services._final_read_state`, rendered by `move_reads`.
FINAL_READ_STATES: tuple[str, ...] = ("taken", "due", "estimated")

#: **THE MOVE-OUT REASON — WHY THIS TENANCY ENDED** (PO ruling 2026-09-20,
#: option A, decision log *"TEN MOVE-OUT RULINGS IN ONE SITTING"* item 3).
#: The vocabulary of `Account.close_reason`, and it is the FIVE THE BLUEPRINT
#: DRAWS, in the order it draws them — the same five the move-out wizard has
#: been naming on screen and throwing away since it was built.
#:
#: ⚠ **A FIXED LIST AND NOT A TENANT LOOKUP, AND THE RULING LEFT THAT OPEN ON
#: PURPOSE** — *"whether the reason list is the five drawn or tenant-editable"*
#: is named in the decision entry's own "what none of these ten decides".
#: Three reasons for the fixed five, recorded here so the next lane does not
#: re-derive them:
#:   · **The ruling exists to make closures COUNTABLE.** `OQ-830` states the
#:     reporting gap in as many words — *"a fixed list can be COUNTED … and a
#:     free sentence can only be read one at a time"*. A per-tenant list is
#:     countable within one utility and not across the product, which is half
#:     the thing asked for.
#:   · **`CUT_REASONS` (`disconnects.py`) IS THE ESTABLISHED SHAPE** for
#:     exactly this question one table over — five fixed codes, TEXT, a CHECK
#:     — and OQ-830 itself describes the cut reasons as *"the five cut reasons
#:     they already pick one of"*. A second, differently-shaped answer to the
#:     same question on the same screen family is how one product grows two
#:     vocabularies.
#:   · **A tenant-editable list is a Settings screen, a lookup table, a seed
#:     and a migration** — more than the ruling asked for, and it would decide
#:     `OQ-830` (OPEN, about the CLOSE-OUT reason's values) by building its
#:     answer first.
#: **Widening to tenant-extensible stays cheap and is `OQ-CUS-12512`**: these
#: are codes, never display strings, so a lookup table can adopt them as seeded
#: rows without moving a stored value.
#:
#: ⚠ **CODES, NEVER THE WORDS ON SCREEN.** What a clerk reads is an i18n key
#: per code (B14 rule 35 — each catalogue is written in its own language), so
#: renaming a label never rewrites a stored row and never breaks a count.
CLOSE_REASON_LEASE_ENDED = "lease_ended"
CLOSE_REASON_OWNER_SOLD = "owner_sold"
CLOSE_REASON_DOWNGRADE_OR_HARDSHIP = "downgrade_or_hardship"
CLOSE_REASON_DECEASED = "deceased"
CLOSE_REASON_OTHER = "other"
CLOSE_REASONS: tuple[str, ...] = (
    CLOSE_REASON_LEASE_ENDED,
    CLOSE_REASON_OWNER_SOLD,
    CLOSE_REASON_DOWNGRADE_OR_HARDSHIP,
    CLOSE_REASON_DECEASED,
    CLOSE_REASON_OTHER,
)


#: CR-171-BRC10 `P1.01` — `accounts.bills_go_to`'s vocabulary (image 40).
BILLS_GO_TO: tuple[str, ...] = ("account_holder", "contact_person")
#: CR-171-BRC10 `P1.01` — *Contact by* (images 33, 38, 40): the four ways this
#: product reaches a person. One list for `contacts.contact_by` and
#: `account_co_owners.contact_by`; `letter` because a person may have no phone
#: and no email at all.
CONTACT_BY: tuple[str, ...] = ("email", "text", "phone", "letter")


class Account(models.Model):
    """The billing account (B2 §2 `accounts`).

    `balance` is a CACHE — the ledger stays the source of truth (B2's own
    column comment); nothing in this slice writes it. `credit_tier` is a
    COMPUTED cache too (r9 #6 / BR-CUS-058: 12-month window, tenant-
    configurable rule params in the not-yet-built `credit_tier_rules`), never
    an input field.

    `account_type` is NOT NULL: r5 #19 reads "accounts += account_type_id,
    account_subtype_id NULL", and by B2's own DDL convention the trailing NULL
    marks the sub-type column only; BR-CUS-012 lists the type in the confirmed
    attribute set. The platform rows exist from migration 0003 onward, so the
    constraint can never be unsatisfiable. READING REPORTED — one migration
    relaxes it if the PO reads r5 #19 the other way."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ **NULLABLE SINCE 2026-09-01 (`CR-056` W1 task 5, migration 0036) — AN
    #: ACCOUNT NEED NOT NAME A UNIT ANY MORE.** `BR-CUS-1010`: a Master Account
    #: is the OWNER'S ACCOUNT AT AN ADDRESS, so it names `premises_id` below and
    #: names no unit at all; a common area is something it is CHARGED FOR
    #: (through `service_agreements`, exactly as before) rather than the thing it
    #: hangs off. **A `regular` account still MUST name a unit** — enforced by
    #: `ck_accounts_regular_has_unit` below as well as by the door, because that
    #: is the direction where a missing unit means a bill with nothing to price.
    #:
    #: ⚠ **EVERY ROW WRITTEN BEFORE THAT MIGRATION STILL HAS ITS UNIT AND KEEPS
    #: IT.** The 0036 backfill fills `premises_id` in and moves no `unit_id`, so
    #: every Master Account created before 2026-09-01 bills exactly what it
    #: billed before it (`CR-056` task 6): `1408 Elm Street` is `$41.20` +
    #: `$28.40` = `$69.60` on both shapes.
    unit = models.ForeignKey(  # ⚠ cross-module customers→metering (B2 §2 reviewed set)
        "metering.Unit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="unit_id",
    )
    #: ── `CR-056` W1 · `BR-CUS-1010` — THE ADDRESS THIS ACCOUNT HANGS OFF.
    #:
    #: **A PLAIN UUID, NOT A ForeignKey, AND THAT IS THIS REPOSITORY'S ESTABLISHED
    #: SHAPE FOR A LINK THAT IS NOT IN THE REVIEWED SET.** B2 §2's cross-module FK
    #: set is REVIEWED and `accounts.unit_id` is in it; `accounts.premises_id` is
    #: not, and minting a second one is a schema review rather than a side effect
    #: of a wave. The two precedents are `template_override_id` on this same model
    #: (*"a plain UUID, NOT a ForeignKey, AND THAT IS THE ESTABLISHED SHAPE"*) and
    #: `ServiceRequest.resolved_premises_id` (*"plain UUIDs, NOT ForeignKeys"*),
    #: and `discount_grants.invoice_id` before both.
    #:
    #: NULL is a real answer and is every account the product had before
    #: 2026-09-01 that the 0036 backfill could not resolve — an account whose unit
    #: the metering seam cannot answer for. It is never a fabricated value.
    premises_id = models.UUIDField(null=True, blank=True)  # BR-CUS-1010 (deferred FK → metering)
    account_no = models.TextField()  # 'A-10432'; allocated from the tenancy series (BR-TEN-035)
    status = models.ForeignKey(  # r5 #20 swap: the lookup replaces B2 §2's enum column
        AccountStatus, on_delete=models.PROTECT, db_column="status_id"
    )
    account_type = models.ForeignKey(  # r5 #19 → the TENANT's own catalogue
        # ⚠ PLATFORM until the PO ruling of 2026-09-17 ("utility can get their
        # own account types"). The row this points at now belongs to this
        # account's own tenant and to no other — `customers.0054` fanned the
        # eight rows out per tenant and repointed every account at its own.
        AccountType,
        on_delete=models.PROTECT,
        db_column="account_type_id",
    )
    account_subtype = models.ForeignKey(  # r5 #19 — NULL per the addendum
        AccountSubtype,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_subtype_id",
    )
    #: BR-CUS-068 (PO ruling 2026-08-22, closing OQ-314's second half — PO
    #: verbatim: "build it and also tell me how you will strore it can it go
    #: into account table as master accounts"): a MASTER ACCOUNT is an ordinary
    #: accounts row with `kind='master'`, payer = the premises' owner/manager,
    #: attached to the premises' common-area units — no new table.
    #:
    #: A COLUMN, not a fifth `account_types` row, deliberately: that catalog is
    #: the SIGNED four-code consumer-category vocabulary (B2 r5 #12 [D5];
    #: migration 0003 names B2 as the tiebreaker), and a master account still
    #: HAS a consumer category — the shared hallway of a residential building
    #: is residential. Orthogonal facts, orthogonal columns.
    #:
    #: Values: `regular` | `master`. `kind` is a REFUSED input on every other
    #: account path (services.REFUSED_FIELDS) — the only door to `master` is
    #: services.create_master_account (POST /accounts/master). One master row
    #: covers SEVERAL common-area units by anchoring `unit_id` on the first and
    #: holding `service_agreements` over every covered unit's service points —
    #: the same linkage every account already uses (BR-MET-101's worked case:
    #: 1408 Elm, $41.20 + $28.40 = $69.60 on one owner bill).
    kind = models.TextField(default="regular")  # regular | master (BR-CUS-068)
    #: ⊕ **`CR-164-BRC10` wave 4 — A BILLING-ONLY OWNER'S ACCOUNT** (PO ruling
    #: 2026-10-03, verbatim: *"C By owner type: an owner who lives there holds
    #: it; a landlord or builder doesn't"*). A single-family New Connection
    #: (Then *"B"*, then *"i dont know yet"* — the owner-occupier half is `OQ-CUS-12785`, OPEN.)
    #: whose owner does NOT live there opens a `regular` account that names the
    #: premises and NO unit, so it pays the build's charges and occupies
    #: nothing: occupancy, Move-in's guard and every bill-run scope key off
    #: `unit_id`, and a NULL unit is not a unit (`BR-CUS-1012`). The flag is
    #: what lets `ck_accounts_regular_has_unit` stay strict for every other
    #: regular account, and `ck_accounts_billing_only_has_no_unit` makes it
    #: unable to occupy. Written only by `create_build_owner_account`.
    billing_only = models.BooleanField(default=False)
    balance = models.DecimalField(max_digits=18, decimal_places=6, default=0)  # cached; DB-3
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), never a float partner
    deposit_on_file = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    deposit_received_on = models.DateField(null=True, blank=True)  # r9 #5 / BR-CUS-050
    #: **WHAT THIS ACCOUNT WAS ASSESSED — the other side of `Still to collect`.**
    #: `customers 0059`, `BR-CUS-1050` as amended 2026-09-20, `DEF-CUS-5909`.
    #:
    #: ⚠ **`deposit_on_file` IS WHAT ARRIVED; THIS IS WHAT WAS ASKED FOR.** The
    #: move record's `Still to collect` is **assessed minus taken** — blueprint
    #: p075 draws `Amount $150.00`, `Amount taken $150.00`, `Still to collect
    #: $0.00` — and until this column existed the page had only ONE of the two
    #: sides, so it reached for `plan_deposit_rules` instead. That is a
    #: REFERENCE figure the product reports and never enforces (`BR-CUS-1050`:
    #: *"the server RESOLVES the plan's standard and reports it beside what was
    #: typed rather than overriding it"*), so the shortfall came out **$95.00**
    #: where the review screen computes **$125.00** — right arithmetic over the
    #: wrong pair.
    #:
    #: ⚠ **NULL AND `0` ARE DIFFERENT, AS EVERYWHERE ELSE IN THIS MODULE.** NULL
    #: means *no deposit is owed on this account*; `0` would mean *one was
    #: assessed at nothing*. Written ONLY on the `required` decision:
    #:   * `not_required` — nothing was ever assessed, so NULL;
    #:   * `waived` — one WAS assessed and somebody with authority decided not
    #:     to collect it (`BR-CUS-1050`), so **nothing is still to collect** and
    #:     a figure here would make the record demand money the utility chose to
    #:     forgive. The amount waived is kept in the four `deposit_waived_*`
    #:     columns below — see there for why the audit row was not enough.
    #:
    #: Four decimals, per CLAUDE.md hard rule 2 as re-signed 2026-08-22 — what a
    #: NEW money column declares. `deposit_on_file` beside it stays `18,6`: the
    #: rule governs what is written, and an existing container is lawful.
    deposit_assessed = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    #: **A WAIVED DEPOSIT, KEPT ON THE ACCOUNT — `customers 0066`, `DEF-CUS-6370`.**
    #:
    #: ⚠ **THE NOTE ABOVE USED TO SAY THE WAIVE "RIDES THE COMMIT'S ANSWER AND
    #: THE AUDIT ROW", AND THAT STOPPED BEING ENOUGH ON 2026-09-23.** `OQ-1340`
    #: was closed that day with *"when audit log is delete - it is deleted thats
    #: okay"*: `audit_log` has ONE retention rule and no row is exempt. So a
    #: year on, a supervisor's **$150.00** waive and a plan that asked nothing
    #: read identically on the account — `deposit_on_file` 0, `deposit_assessed`
    #: NULL — and the only record that a person forgave money is gone. A waive is
    #: a money decision with a person behind it (`BR-CUS-1050`), so the account
    #: keeps who, when, how much and why, for the life of the account.
    #:
    #: ⚠ **ALL FOUR ARE NULL TOGETHER OR SET TOGETHER, AND ONLY `deposit.take()`
    #: WRITES THEM**, inside the creating transaction (S18 / S19). No payload
    #: vocabulary names them, so no other door can set them.
    #: NULL means *no deposit was waived on this account*, never *waived $0*.
    #:
    #: `_amount` is the PLAN's figure for the category at the moment of the
    #: waive (`BR-RAT-020/023`), four decimals per hard rule 2. The currency is
    #: the account's own `currency` — `BR-TEN-042` locks it, so a second column
    #: would be a second place for the same fact.
    deposit_waived_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    deposit_waived_at = models.DateTimeField(null=True, blank=True)
    #: A PERSON, and one `deposit.WAIVE_ROLES` admits — a Billing Clerk or a
    #: System Admin since 2026-09-24 (`BR-CUS-1050`, `OQ-CUS-12623`). The same
    #: customers→identity FK `service_request_fees.waived_by` already carries
    #: for the application fee's waive (B2 §2's reviewed interface set).
    deposit_waived_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="deposit_waived_by",
    )
    #: Required when waiving — one short sentence, as typed (`deposit.clean`).
    deposit_waive_reason = models.TextField(null=True, blank=True)
    #: **THE SIZE THE CLERK PICKED BECAUSE NO METER WAS FITTED — `customers
    #: 0078`, `DEF-CUS-9521`.** PO 2026-10-04, verbatim: *"(c) Let the clerk
    #: pick the size on the Deposit step."* A plan whose deposit is priced by
    #: meter size asks the size of the connection; a vacant unit with no meter
    #: has none, so the clerk picks one (Rosa: 2" → **$600.00**). Kept here,
    #: not only in `audit_log` (pruned with no row exempt, `OQ-1340`), because
    #: the FIRST BILL reads it back (`rating.seams.account_deposit_size_class`)
    #: and must ask what the counter took. A size `service_size_classes.code`;
    #: NULL means *no size was picked* — a meter size was recorded, or the
    #: deposit is not priced by size. All three set together, and only
    #: `deposit.take()` writes them. A recorded meter size always wins.
    deposit_size_class = models.CharField(max_length=40, null=True, blank=True)
    deposit_size_picked_at = models.DateTimeField(null=True, blank=True)
    deposit_size_picked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="deposit_size_picked_by",
    )
    credit_tier = models.TextField(null=True, blank=True)  # COMPUTED cache (r9 #6, BR-CUS-058)
    autopay = models.BooleanField(default=False)  # CAPTURE-ONLY in v1 (BR-CUS-059)
    tax_exempt = models.BooleanField(default=False)  # finance 2026-08-07, B4.2
    tax_exempt_ref = models.TextField(null=True, blank=True)
    tax_exempt_expires = models.DateField(null=True, blank=True)
    # ══════════════════════════════════════════════════════════════════════
    # CR-122-BRC06 · A DISCOUNT CLAIM — B18 §5.3.4, PO ruling 2026-09-19
    # ══════════════════════════════════════════════════════════════════════
    #: ⚠ **A CLAIM IS NOT A GRANT, AND NOTHING READS THIS AS ONE.** `Discount
    #: Version.eligibility_rule` is ADVISORY — its own docstring says no code
    #: evaluates it and names automatic evaluation as `EP-RAT-12`'s remainder —
    #: and `proof_before_first_reduction` defaults to true, so an unverified
    #: enrolment reduces nothing. Enrolment stays a staff act through
    #: `discount_services.enrol_account`. What these two columns record is that
    #: the customer SAID SO at move-in, so somebody can follow it up; no
    #: discount, enrolment or reduction is created by writing them.
    #:
    #: ⚠ **AND IT NEVER GATES SERVICE.** B18 §5.3.4 is explicit — *"never blocks
    #: service — only the discount"* — so no validator, guard or refusal reads
    #: these. A move-in with a claim and a move-in without one take exactly the
    #: same path.
    #:
    #: They MIRROR `service_requests.eligibility_claimed` / `eligibility_note`
    #: deliberately, name for name: a claim made on an application and the same
    #: claim made at the counter are one fact, and two shapes for it would be
    #: two things to join later.
    eligibility_claimed = models.BooleanField(default=False)
    eligibility_note = models.TextField(null=True, blank=True)
    bad_address = models.BooleanField(default=False)  # r12 #8 / BR-PAY-018
    nsf_count = models.IntegerField(default=0)  # r12 #12 / BR-PAY-013
    #: r12 #12's SECOND half — *"`accounts.nsf_count` + cash-only/no-autopay
    #: privilege flag [BR-PAY-013]"*. Only the first half was ever built, which
    #: is DEF-070: BR-PAY-013 is CONFIRMED and says that at the tenant's N
    #: (default 2, `nsf_privilege_n`) the account goes cash-only and off
    #: autopay, and there was no column for it to go to, so the second bounce
    #: did nothing at all.
    #:
    #: ONE boolean, not two, because the signed line names ONE flag. Column
    #: NAME under the standing *"Exact DDL = Eng-Lead 🔒"* delegation.
    #:
    #: ⚠ NOTHING AUTO-CLEARS IT (J12 step 6): *"the cash-only flag REMAINS — no
    #: rule auto-clears it; lifting it is an explicit staff config action,
    #: audited"*. So no path in this module unsets it as a side effect, and the
    #: WHEN of the trip lives in `audit_log` (hard rule 7) rather than in a
    #: second column — J12 step 6 asks the trail to reconstruct the trip and any
    #: lift, which is what the trail is for.
    #:
    #: It is a PRIVILEGE, not an enrolment: `autopay` above stays exactly as the
    #: customer elected it. Flipping that column would destroy the election and
    #: leave nothing to restore when the flag is lifted; the flag is what the
    #: autopay path reads (`apps.payments.autopay.is_enrolled`).
    cash_only_no_autopay = models.BooleanField(default=False)  # r12 #12 / BR-PAY-013
    preferred_language = models.TextField(null=True, blank=True)  # r15 #2 / BR-CUS-064
    #: ── THE DELIVERY ELECTION — BR-BIL-036's "elected on top" (CR-052 task 14)
    #: PRINT IS THE FLOOR AND THESE TWO CANNOT LOWER IT. BR-BIL-036 (CONFIRMED,
    #: PO 2026-08-10 closing OQ-091): *"every bill is rendered, its document is
    #: STORED, and the print batch goes to the vendor; email/SMS notification of
    #: the billed amount rides alongside"*. So a `paperless` account still gets
    #: its print row — the floor is applied inside `apps/notifications` where no
    #: writer can forget it (`CHANNEL_FLOOR_BY_SOURCE`) — and these columns only
    #: ever ADD a channel.
    #:
    #: ⚠ **THEY ARE NOT NULLABLE, AND THE FAIL-CLOSED DIRECTION IS THE REASON**
    #: (hard-won law 3). `False` is a real, correct answer for every account in
    #: the product today: nobody has been asked, so nobody has elected, and a
    #: bill that queues print alone is exactly what BR-BIL-036 requires. A
    #: NULLable column would make the election unreadable on every existing row
    #: and `delivery_seam.elected_channels` would go on reporting
    #: `delivery_election_unreadable` for ever — the read would exist and answer
    #: nothing, which is hard-won law 2 wearing a migration. The UNSAFE value —
    #: emailing somebody who never asked — is the one an operator must type.
    #:
    #: These were PROPOSED-SCHEMA on `US-CUS-003 §5` and are `[D-8]` in B2's
    #: field-map anchoring list ("customer paperless-delivery preference"). They
    #: are CAPTURED per BR-CUS-028 and now also READ, by
    #: `selectors.delivery_channel_election_for_account`.
    paperless = models.BooleanField(default=False)  # BR-CUS-028 / BR-BIL-036
    sms_reminders = models.BooleanField(default=False)  # BR-CUS-028 / BR-BIL-036
    #: ── BR-BIL-025's ACCOUNT OVERRIDE — B2 field-map anchor `[BR-BIL-025/D-4]`
    #: *"the template resolves per ACCOUNT: account override → category default
    #: → tenant fallback"*. `billing.templates_service.resolve_for` has
    #: implemented all three legs since 2026-08-15 and its own docstring says
    #: the override *"is an ARGUMENT, not a lookup … so the caller supplies it
    #: and the ORDER is implemented here — which is the half that would
    #: otherwise be re-guessed at every call site ONCE THE COLUMN LANDS"*. This
    #: is that column, and `apps/billing/issue.py` is the caller (CR-052 task 12).
    #:
    #: ⚠ **A PLAIN UUID, NOT A ForeignKey, AND THAT IS THE ESTABLISHED SHAPE.**
    #: `bill_templates` is BILLING's table and B2 §2's reviewed cross-module FK
    #: set is `invoices.account_id` in the other direction; minting a second one
    #: is a schema review, not a side effect of a wave. `discount_grants
    #: .invoice_id` is the precedent — *"a plain uuid (deferred FK → billing,
    #: B11 F-3)"*. NULL is the ordinary answer and means *no override*, which is
    #: every account in the product.
    template_override_id = models.UUIDField(null=True, blank=True)  # BR-BIL-025 [D-4]
    opened_at = models.DateField(null=True, blank=True)  # move-in
    closed_at = models.DateField(null=True, blank=True)  # move-out
    #: **CR-038 W9 task 4 — HOW THE SETTLEMENT'S FINAL READ WAS OBTAINED.**
    #: One of FINAL_READ_STATES (`taken` / `due` / `estimated`), derived ONCE
    #: at move-out commit from the metering read seam and stored beside
    #: `closed_at` — the fact B18 §5.6.2's amber `estimated` cell is a claim
    #: about, which until this column had no store (TC-MVO-7 asserted exactly
    #: that; `move_reads.ESTIMATED_STATE_HAS_NO_SETTLEMENT_FLAG` was the
    #: stated absence it retires). NULL = the close predates this column, or
    #: the seam could not answer at close time, or the unit held no meters —
    #: three honest absences, never a fourth value invented to cover them.
    #: There is no `move_out_settlement` TABLE (the settlement is a pure
    #: derivation, its own docstring: *"Nothing in here is stored"*), so the
    #: flag lives on the ONE row a move-out has — this account row — written
    #: only by `services.move_out` in the same transaction as the close.
    #: HUMAN-REVIEW-PENDING — migration 0026 (🔒 migration ordering); the G7
    #: ledger row is OWED via the W9 lane report (12-governance/ is not this
    #: worktree's to edit).
    final_read_state = models.TextField(null=True, blank=True)
    #: **WHY THIS TENANCY ENDED** — one of `CLOSE_REASONS` (PO ruling
    #: 2026-09-20, option A). US-CUS-005 §5 mapped this column and B2 carried
    #: it as PROPOSED-SCHEMA from 2026-08-08 until today; the blueprint's own
    #: dashed panel on p110 is why it stopped being proposed: *"Five options
    #: are named on screen and none of them is stored. There is no column for
    #: it, so the wizard asks and forgets - which is worse than not asking."*
    #:
    #: ⚠ **NULL IS A REAL ANSWER AND MEANS *NOBODY WAS ASKED*, NEVER *no
    #: reason*.** Every account closed before this column existed carries NULL
    #: and MUST keep it: hard rule 4 makes a closed account's history a record,
    #: and a migration that invented a reason for one would be falsifying it
    #: (the PO ruling names this explicitly — *"no migration may write one"*).
    #: A report counting closures therefore counts `NULL` as its own bucket,
    #: *not asked*, and never folds it into `other`.
    #:
    #: ⚠ **WRITTEN ONLY BY `services.move_out`, IN THE CLOSE'S OWN
    #: TRANSACTION**, exactly as `final_read_state` beside it is — so a
    #: refused reading or a refused status rolls the reason back with the
    #: close, and a reason can never sit on an account that did not close.
    #: `close_out.py`'s cut-customer close-out does NOT write it: that act asks
    #: its own free-text reason on the CASE and `OQ-830` owns its vocabulary.
    #:
    #: ⚠ **NOT EDITABLE AFTER THE CLOSE, and that is not this column's rule to
    #: make** — `REFUSED_FIELDS` already refuses `close_reason` on every other
    #: door, so the only way in is the move-out. Whether a mistyped reason may
    #: be corrected is `OQ-CUS-12513` and is OPEN; nothing here implies it can.
    #:
    #: 🔒 HUMAN-REVIEW-PENDING — migration `customers/0058` (migration ordering
    #: is a sensitive path); the G7 ledger row is
    #: `12-governance/09-human-review-ledger.md`.
    close_reason = models.TextField(null=True, blank=True)
    #: r17.2 — tenant-defined VALUES for the definitions in `custom_field`
    #: (tenancy). A column on the OWNING row, never a shared value table: a
    #: shared table would be written by customers, metering and assets alike
    #: (a cross-module write, forbidden by DB-16/§2), and it would need its own
    #: audit path where this rides BR-AUD-003's whole-row before/after for free.
    #: DB-17: nothing in a money path may read it except
    #: `apps/billing/custom_snapshot.py` — G6 enforces that, not review.
    custom_data = models.JSONField(default=dict, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    #: ⛔ **CR-046 C4/C5 · `BR-CUS-172` — THE UTILITY'S OWN ACCOUNT REFERENCE,
    #: AND IT IS NEW HERE EVEN THOUGH THE IMPORT HAS OFFERED THE COLUMN FOR
    #: MONTHS (`DEF-1660`).**
    #:
    #: CR-046 C4 says to read `BR-CUS-054` first because *"accounts already have
    #: the `external_ref` column this change is adding to the others"*. **They
    #: did not.** `BR-CUS-054`'s `external_ref` is on **`customers`** — the
    #: PERSON — and this is the **ACCOUNT**. One landlord with fourteen units is
    #: one customer row and fourteen account rows, so their old system's
    #: *account* number cannot live on the customer: fourteen values, one
    #: column, thirteen of them lost.
    #:
    #: The accounts import template has offered an `External reference` column
    #: since CR-030 W1 and `_account_payload_from` dropped it on the floor —
    #: mapped, shown as `Matched` at stage 2, written nowhere. That is DEF-1660,
    #: and this column is where the value now lands.
    #:
    #: ⚠ **IT IS NOT `customer_ref`.** That column is the CUSTOMER's legacy id
    #: and reaches `customers.external_ref` through `link_customer`; both are
    #: offered, because a utility migrating its books holds both facts and a
    #: column that holds either means neither (BR-AST-049's own wording).
    external_ref = models.TextField(null=True, blank=True)  # the LEGACY account id
    # ══════════════════════════════════════════════════════════════════════
    # CR-171-BRC10 `P1.01` · WHERE A COMPANY'S BILLS GO (image 40, 🔒 0080)
    # ══════════════════════════════════════════════════════════════════════
    #: *"PO or reference on bills"* — printed on every bill of THIS account.
    #: ⚠ **NAMED `po_number` ON PURPOSE:** the commercial bill template has
    #: carried a `po_number` token since A19 rule 4 (*"PO number, tax ID … only
    #: exist on the commercial bill"*, `notifications.catalogs`) with no column
    #: behind it; this is that column, in that spelling, so printing it is a
    #: billing READ and not a new rule (CR-171 `P1.11`). On the ACCOUNT, not the
    #: customer, because one company's fourteen accounts quote fourteen POs.
    po_number = models.TextField(null=True, blank=True)
    #: *Bills go to* — `account_holder` | `contact_person` (image 40's tick
    #: *"Same as the contact person"*; image 46 reads *"The contact person"*).
    #: NULL = not stated, which bills to the account holder exactly as every
    #: account before this column did. CHECK-constrained; a third addressee is
    #: not drawn and is not invented here.
    bills_go_to = models.TextField(null=True, blank=True)
    #: *Autopay from* (image 41, v20 ruling: *"Autopay On adds Autopay from"*) —
    #: WHICH saved card or bank mandate pays this account. CR-171 §6 names it:
    #: *"the Autopay source points at a `StoredPaymentInstrument`"*. That table
    #: hangs off the CUSTOMER (a landlord saves one card for four accounts), so
    #: the per-account choice lives here — the election `payments.instruments.
    #: autopay_stance` says no screen has offered yet (`CWP-040`).
    #: ⚠ **A UUID, NOT A FOREIGN KEY:** `stored_payment_instruments` is
    #: PAYMENTS' table, which already points INTO customers; a key back would be
    #: a second cross-module edge outside B2 §2's reviewed set. Validated by the
    #: writer (`P1.15`). NULL = none chosen; `autopay` above stays the on/off.
    autopay_instrument_id = models.UUIDField(null=True, blank=True)  # DEFERRED → payments
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"
        constraints = [
            # CR-171 `P1.01` — the two addressees image 40 draws.
            models.CheckConstraint(
                condition=Q(bills_go_to__isnull=True) | Q(bills_go_to__in=BILLS_GO_TO),
                name="ck_accounts_bills_go_to",
            ),
            # B2 §4 ux_accounts_no — account # unique WITHIN a tenant.
            models.UniqueConstraint(fields=["tenant", "account_no"], name="ux_accounts_no"),
            # ── CR-046 C5 · BR-CUS-172 — UNIQUE PER TENANT, CASE-INSENSITIVELY,
            # PARTIAL: `customers.external_ref`'s own posture (BR-CUS-054),
            # followed verbatim on the row one table along.
            #
            # **The worked figure.** A utility migrates 1,213 accounts. Under
            # the 2026-08-27 ruling `account_no` is blank on every row, so we
            # issue `AC-2026-00001 … AC-2026-01213` and post $184,320.55 of
            # opening AR (GT-16). They then correct twelve deposit dates and
            # re-run the SAME file. Without a unique legacy key every row reads
            # as new: 1,213 SECOND accounts — and BR-CUS-017 (one live account
            # per unit) rejects all 1,213 at the seat, so the operator meets
            # 1,213 refusals on a file the product told them to correct. With
            # it: 1,213 matches, 12 updates, and NOT ONE new journal entry
            # (hard rule 4 — the opening batch is posted once and corrected by
            # new rows, never by a re-import).
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_accounts_tenant_external_ref_ci",
            ),
            # BR-CUS-017's one-active-account-per-unit index is NOT here.
            # See the module docstring: its predicate cannot be written once
            # `status` is a lookup FK, and no substitute is invented.
            #
            # ── `CR-056` W1 · THE TWO CHECKS THAT REPLACE THE `NOT NULL`
            # `unit_id` LOST. Both are writable predicates over columns that are
            # never lookups, which is exactly why they CAN exist where
            # BR-CUS-017's could not.
            #
            # 1 · AN ACCOUNT HANGS OFF SOMETHING. A row with neither a unit nor a
            #     premises is an account at no address, which nothing in this
            #     product can bill, show, or find an owner for. Every existing row
            #     satisfies it before the migration runs (they all have a unit).
            models.CheckConstraint(
                condition=Q(unit__isnull=False) | Q(premises_id__isnull=False),
                name="ck_accounts_anchored",
            ),
            # 2 · A `regular` ACCOUNT STILL NAMES A UNIT (`BR-CUS-1012`). The
            #     nullability exists for `BR-CUS-1010`'s owner account and for
            #     nothing else; letting an occupying account lose its unit would
            #     make `covered_unit_ids` answer `[]` and produce a bill with
            #     nothing to price, silently.
            #     ⊕ `CR-164-BRC10` wave 4 — except a BILLING-ONLY owner's
            #     account, which is unit-less on purpose: it pays a build's
            #     charges and must never read as the home's occupant.
            models.CheckConstraint(
                condition=~Q(kind="regular") | Q(unit__isnull=False) | Q(billing_only=True),
                name="ck_accounts_regular_has_unit",
            ),
            # 3 · ⊕ `CR-164-BRC10` wave 4 — a billing-only account names NO
            #     unit, so it can never occupy one, whatever its status.
            models.CheckConstraint(
                condition=Q(billing_only=False) | Q(unit__isnull=True),
                name="ck_accounts_billing_only_has_no_unit",
            ),
            # ── THE MOVE-OUT REASON IS ONE OF FIVE, OR IT IS ABSENT (PO ruling
            # 2026-09-20 item 3). `DisconnectCase.cut_reason`'s constraint,
            # verbatim in shape, because it answers the same question about the
            # same kind of act one table over.
            #
            # ⚠ **NULL IS PERMITTED BY THE FIRST CLAUSE AND THAT IS LOAD-BEARING,
            # NOT LENIENCY.** Every account closed before today holds NULL and
            # hard rule 4 forbids writing one in; a constraint demanding a value
            # would make those rows unsatisfiable and the migration
            # unappliable — which is how a check ends up quietly dropped.
            models.CheckConstraint(
                condition=Q(close_reason__isnull=True) | Q(close_reason__in=CLOSE_REASONS),
                name="ck_accounts_close_reason",
            ),
        ]
        indexes = [
            # B2 §4 ix_ar_outstanding — Outstandings high→low (partial).
            models.Index(
                fields=["tenant", "-balance"],
                condition=Q(balance__gt=0),
                name="ix_ar_outstanding",
            ),
            models.Index(fields=["tenant", "unit"], name="ix_accounts_tenant_unit"),
            # `CR-056` W1 — the address-shaped read that replaces the unit-shaped
            # one: "which account is the owner's at this premises" (BR-CUS-1011's
            # guard, `accounts_for_bill_run`'s master leg, PRM-02's owner card).
            models.Index(fields=["tenant", "premises_id"], name="ix_accounts_tenant_premises"),
            # ── `BR-CUS-1046` (PO 2026-09-10) — THE ORDER THE LIST OPENS ON ──
            # *"The new newly created entries should always show on the top."*
            # `S17` and every screen that lists accounts now orders
            # `-created_at, -id` by default, so this is the ONE read every clerk
            # makes on every visit. Without the index PostgreSQL sorts the whole
            # tenant to hand back fifty rows, which is the `NFR-3` breach moved
            # from Python into the database rather than removed.
            #
            # ⚠ **THE DESCENDING SPELLING AND THE `id` TAIL ARE BOTH
            # LOAD-BEARING.** The index has to match the ORDER BY term for term
            # or the planner sorts anyway: `-id` is in the query because
            # `created_at` is `auto_now_add` and an import writes many rows
            # inside one clock tick, so the tiebreak is not optional and an
            # index without it would cover only the first column of the sort.
            #
            # ⚠ **NO `condition=` HERE, ON PURPOSE (`NFR-5`).** A partial index
            # is a cap wearing a performance costume: it would make the default
            # list fast for the rows it covers and quietly slow for the rest,
            # and the rows it left out would be the oldest ones — exactly what
            # a utility migrating its books has most of.
            models.Index(
                fields=["tenant", "-created_at", "-id"], name="ix_accounts_tenant_recent"
            ),
        ]


class Contact(models.Model):
    """Account contact (B2 §2 `contacts`). Every column here is PII per
    BR-CUS-045; `gov_id_last4` stores the last four only, tokenized per the
    OQ-016 closure, and `email` is citext (DB-15).

    `account_id` is B2 §2 verbatim. r9 #1 flags re-homing contacts onto the
    BR-CUS-054 customer entity as an Eng-Lead disposition — that entity is not
    built in this slice, so nothing is pre-empted here."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_column="account_id")
    full_name = models.TextField()  # PII
    email = CITextField(null=True, blank=True)  # PII (DB-15 citext)
    phone = models.TextField(null=True, blank=True)  # PII
    dob = models.DateField(null=True, blank=True)  # PII
    gov_id_last4 = models.TextField(null=True, blank=True)  # PII — last 4, tokenized
    is_primary = models.BooleanField(default=True)
    #: CR-171-BRC10 `P1.01` (🔒 `customers/0080`), asked for by lane MVI-IDN
    #: (CR-171 §9.IDN): a company's CONTACT PERSON has a *Job title* (image 40)
    #: and every contact a *Contact by* (images 33, 40). The contact person is
    #: this row (CR-171 E59), so the two facts live here; `contact_by` is
    #: CHECK-constrained to `CONTACT_BY`. Nullable, nothing back-filled.
    job_title = models.TextField(null=True, blank=True)
    contact_by = models.TextField(null=True, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Account
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "contacts"
        constraints = [
            models.CheckConstraint(
                condition=Q(contact_by__isnull=True) | Q(contact_by__in=CONTACT_BY),
                name="ck_contacts_contact_by",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_contacts_tenant_account"),
        ]


class Address(models.Model):
    """Account address (B2 §2 `addresses`). `kind` stays the plain value B2
    declares (mailing|service) — r5 #20's enum→lookup direction names payment
    methods, account statuses and the meter/asset catalogs, not this column,
    so no lookup table is invented for it."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_column="account_id")
    kind = models.TextField(default="mailing")  # mailing | service (B2 §2)
    line1 = models.TextField()  # PII
    #: ⚠ ADDED 2026-09-01 (DEF-2847, migration 0039). Two of the print
    #: manifest's nine address fields had no column ANYWHERE in this product, so
    #: `BR-NOT-029`'s hand-over file emitted `address_line_2` and `country`
    #: empty on every row while every layer above the table — the selector, the
    #: billing seam, the manifest writer — was already written to carry them.
    #:
    #: NULLABLE AND NEVER BACKFILLED, for two separate reasons the migration
    #: states in full: line 2 may not be carved out of line 1 (`BR-NOT-029`
    #: clause (a) — *"splitting an address is guessing"*), and country may not be
    #: taken from `TenantSettings.country`, which is the UTILITY's regional
    #: setting and not a statement about where a customer lives. NULL here means
    #: *nobody has told us*, which is true.
    #:
    #: Neither is in `selectors.REQUIRED_ADDRESS_PARTS` (clause (b) names city,
    #: state and postal code), so neither holds a bill out of the print file.
    line2 = models.TextField(null=True, blank=True)  # PII
    city = models.TextField(null=True, blank=True)
    state = models.TextField(null=True, blank=True)
    postal_code = models.TextField(null=True, blank=True)
    country = models.TextField(null=True, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Account
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "addresses"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_addresses_tenant_account"),
        ]


class Customer(models.Model):
    """The FIRST-CLASS customer entity (BR-CUS-054 — PO OQ-057 option b).

    B2 r9 #1 gives the column list and this table is it, verbatim:
    *"`customers` (kind person|company, display_name, external_ref UNIQUE per
    tenant) + `customer_accounts` N:M link [BR-CUS-054]"*.

    Until 2026-08-11 this table was in `models.py`'s deliberately-not-built
    list, and `services.link_customer` was a `NotImplementedError("BR-CUS-054")`
    stub. Both said the same true thing — there was no column list in B2 §2 and
    inventing one would have been inventing schema. r9 #1 is that column list;
    the entity is built now because US-CUS-019's template has a `customer_ref`
    column and "one customer, many accounts" is the whole point of the landlord
    case (US-CUS-019 TC-2: one ref on three rows → ONE customer row).

    `external_ref` is the LEGACY system's identifier, unique per tenant — it is
    what makes a re-import LINK to the customer it made last time instead of
    duplicating them (BR-CUS-054: "a ref matching an EXISTING tenant customer
    links instead of duplicating"). Case-insensitive, like every other code in
    this module, because `CUST-118` and `cust-118` are one customer in every
    legacy export anyone will hand us.

    NOT BUILT here, and named rather than passed over: `contacts` do NOT
    re-home onto this row. r9 #1 flags that as an "Eng-Lead disposition" and
    B2 §2 declares `contacts.account_id`; moving a live PII table's parent is
    not a side effect of an import story."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: CR-030 W0 — OUR number for this customer, allocated from the `customer`
    #: series (the catalogue's twenty-fourth, default `C-{00000}`).
    #:
    #: ⚠ THIS IS NOT `external_ref` AND DOES NOT REPLACE IT. `external_ref`
    #: below is the LEGACY system's id and is what makes a re-import link
    #: instead of duplicating (BR-CUS-054). A utility needs both: theirs to
    #: reconcile against the system we migrated from, ours to quote down a
    #: phone. A customer created by the S18 wizard has no `external_ref` at
    #: all and still needs a number.
    #:
    #: WHY IT EXISTS: accounts, premises, units, bills, payments, assets and
    #: work orders all carry a number and `customers` did not, so every deposit
    #: carry-forward and every "they owe money on another account" check rested
    #: on a clerk matching a NAME. The worked case put to the PO (B18 §2.5): a
    #: returning customer holding $153.50 on a CLOSED account gets it carried
    #: across, or does not, because nobody found them.
    #:
    #: NULLABLE, and deliberately: this column lands on a table that already has
    #: rows, and a NOT NULL added in the same migration as its backfill is a
    #: migration that cannot be replayed against a large tenant without a lock
    #: nobody asked for. The allocator fills it on every create from here on and
    #: migration 0014 backfills what existed; tightening it is its own change
    #: once no NULL remains.
    customer_no = models.TextField(null=True, blank=True)
    kind = models.TextField(default="person")  # person | company (B2 r9 #1)
    display_name = models.TextField()
    external_ref = models.TextField(null=True, blank=True)  # the LEGACY id
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Account
    #: ══════════════════════════════════════════════════════════════════
    #: IDENTITY — CR-056 W2 task 11 (🔒 sensitive path, BR-CUS-092 / BR-CUS-089)
    #: ══════════════════════════════════════════════════════════════════
    #: **WHAT MADE AN OWNER ONE PERSON UNTIL 2026-08-31 WAS HIS NAME**, unique
    #: per utility, case-insensitively (`uq_customers_tenant_name_ci` does not
    #: even exist — only `display_name` was indexed). CR-056 §4 states the cost
    #: in one line: *"A. Kulkarni and Ajinkya Kulkarni are two landlords and
    #: nothing objects."* Under CR-056 every address gets its owner an account,
    #: so the same landlord now arrives through twelve doors instead of one,
    #: and a name is not enough to tell two of them apart.
    #:
    #: ⚠ **THIS IS A MONEY PATH, NOT A CONVENIENCE.** `BR-CUS-089` lets a
    #: `strong` identity match CARRY A DEPOSIT (WE-7/GT-23: **$150.00**
    #: principal + **$3.50** interest = **$153.50**). Recognition was
    #: deliberately absent until now — `service_request_service.
    #: suggest_customer_matches` refuses BY NAME with *"a matcher built now
    #: would be matching on fields that do not exist"* — and these columns are
    #: what make the PO's own criteria assessable rather than inert.
    #: ⚠ **THAT QUOTED REASON EXPIRED ON 2026-09-15** and the stub now names
    #: `BR-CUS-089` instead: the SERVICE REQUEST carries a date of birth and a
    #: driving licence too, so the fields exist on both surfaces and what is
    #: still missing is a matcher aimed at a request.
    #:
    #: **THE SIGNED CRITERIA (BR-CUS-089, PO 2026-08-25 closing `OQ-364`,
    #: verbatim): NAME + DATE OF BIRTH + ONE GOVERNMENT ID.** Three of these
    #: four columns are that rule's evidence; `phone` is not part of it and
    #: cannot make a match strong on its own (see `identity_match.py`).
    #:
    #: **WHY ENCRYPTED, AND IT IS SIGNED LAW RATHER THAN THIS LANE'S TASTE.**
    #: `OQ-016` is CLOSED — *"app-layer encryption for high-sensitivity
    #: columns, disk for rest (PO R6)"*, B2 §6 — and `BR-CUS-092` (PO
    #: 2026-08-24, settling DEF-632) says the Social Security number and the
    #: driving licence are *"captured, encrypted at the application layer, and
    #: shown as the last four digits only"*. `core.crypto` implements it:
    #: AES-256-GCM, a fresh 96-bit nonce per write, AAD binding a ciphertext to
    #: the column it was written for — so a value lifted out of `customers.ssn`
    #: and dropped into `service_requests.ssn` RAISES instead of decrypting.
    #:
    #: ⚠ **THE SCHEME IS RANDOMISED, SO THESE COLUMNS CANNOT BE SEARCHED** —
    #: `EncryptedTextField.get_lookup` refuses every lookup but `__isnull`,
    #: loudly, because a silently-empty queryset on an identity match is the
    #: failure BR-CUS-089 can least afford. Matching therefore runs on the
    #: `*_bidx` BLIND INDEX beside each one (`bix1:<kid>:<HMAC>`), which is
    #: deterministic and equality-searchable and leaks equality and nothing
    #: else. `BR-CUS-092`'s own row records *"NO BLIND INDEX, so BR-CUS-089's
    #: matcher is still unbuilt and the column cannot be searched"* — this is
    #: the lane that builds the matcher, which is the only lane that can prove
    #: the index works (`service_requests.ssn`'s docstring says so in as many
    #: words).
    #:
    #: ⚠ **THERE IS NO `ssn_last4` COLUMN AND THERE MUST NOT BE.** The last
    #: four is a READ projection (`crypto.last_four`); storing it would put four
    #: of the nine digits back in the clear and make BR-CUS-092(c)'s promise
    #: false while every test still passed.
    date_of_birth = models.DateField(null=True, blank=True)  # PII
    ssn = EncryptedTextField(null=True, blank=True, crypto_context="customers.ssn")
    ssn_bidx = models.TextField(null=True, blank=True)
    driving_licence = EncryptedTextField(
        null=True, blank=True, crypto_context="customers.driving_licence"
    )
    driving_licence_bidx = models.TextField(null=True, blank=True)
    phone = EncryptedTextField(null=True, blank=True, crypto_context="customers.phone")
    phone_bidx = models.TextField(null=True, blank=True)
    #: ══════════════════════════════════════════════════════════════════
    #: A COMPANY'S IDENTITY — CR-056 W2b (🔒 sensitive path, BR-CUS-1022)
    #: ══════════════════════════════════════════════════════════════════
    #: **THE FOUR COLUMNS ABOVE ARE A PERSON'S AND A COMPANY HAS NONE OF
    #: THEM.** PO ruling 2026-09-01, verbatim: *"Customer can be person or
    #: company - in case of person , if we have SSN, or DL or Phone number, we
    #: create the Customer ID and attached these to custoemr ID ; if it is
    #: Company then we ask for Tax ID"*. `BR-CUS-089`'s signed three-part test
    #: needs a DATE OF BIRTH, and a company has none — read literally it made
    #: every company permanently unmatchable, which nobody intended. The
    #: decision log of 2026-09-01 narrows that rule onto PERSONS and gives a
    #: company its own identifier, which is this column.
    #:
    #: ⚠ **`tenancy.ein` IS NOT THIS AND MUST NOT BE READ AS IT.** That column
    #: is the UTILITY's own tax number, on another module's table; this is a
    #: fact about a CUSTOMER. Reaching for the tenant's would be a cross-module
    #: read of the wrong party's row.
    #:
    #: **ENCRYPTED FOR THE SAME SIGNED REASON THE SSN IS** — `OQ-016` is CLOSED
    #: (*"app-layer encryption for high-sensitivity columns, disk for rest"*,
    #: PO R6, B2 §6) and a company's tax identifier is the same shape and the
    #: same sensitivity as the personal one `BR-CUS-092` legislates. ⚠ And
    #: `tenancy.ein` is the counter-example rather than the precedent: it holds
    #: nine plaintext digits against that closed ruling and says so in its own
    #: docstring. This column does not repeat it.
    #:
    #: ⚠ **NO UNIQUE CONSTRAINT, AND IT IS A PO RULING RATHER THAN AN
    #: OVERSIGHT** (2026-09-01): *a duplicate identifier refuses to LINK and
    #: never refuses to SAVE.* A clerk who mistypes one digit of a real Tax ID
    #: must still be able to open the account.
    tax_id = EncryptedTextField(null=True, blank=True, crypto_context="customers.tax_id")
    tax_id_bidx = models.TextField(null=True, blank=True)
    #: ══════════════════════════════════════════════════════════════════
    #: A COMPANY'S OTHER NAMES — CR-171-BRC10 `P1.01` (image 40, 🔒 0080)
    #: ══════════════════════════════════════════════════════════════════
    #: `display_name` is the LEGAL name (*"Legal name \*"*); these three are
    #: the facts image 40 draws beside it that no column held. Company facts,
    #: so they live with `tax_id` on the CUSTOMER, not on each account. All
    #: nullable and free text: the *Business type* and *Registered in*
    #: dropdowns' vocabularies are the screen's (`P1.11`/`P2.27`), and a CHECK
    #: here would be a list nobody signed. `registered_in` holds the state's
    #: two-letter code (*IA*), shown as its name.
    trading_as = models.TextField(null=True, blank=True)
    business_type = models.TextField(null=True, blank=True)
    registered_in = models.TextField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"
        constraints = [
            # r9 #1 "external_ref UNIQUE per tenant". Partial: a customer
            # created by the S18 wizard has no legacy ref, and N of those must
            # be allowed to coexist.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_customers_tenant_external_ref_ci",
            ),
            # CR-030 W0. Unique WITHIN a tenant, case-insensitively — `C-00417`
            # and `c-00417` are one customer in any legacy export, the same
            # posture `external_ref` above already takes. PARTIAL, because the
            # column is nullable while the backfill runs and N NULLs must be
            # allowed to coexist (a plain UNIQUE would permit that anyway in
            # Postgres, but stating the predicate makes the intent readable
            # rather than incidental).
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("customer_no"),
                condition=Q(customer_no__isnull=False),
                name="uq_customers_tenant_customer_no_ci",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "display_name"], name="ix_customers_tenant_name"),
            # CR-056 W2 task 13 — the three lookups the matcher makes, and it
            # makes NO others. Each is an equality probe against a blind-index
            # token (`bix1:<kid>:<HMAC>`), so a plain btree is the right shape;
            # there is no range, no prefix and no ordering on these columns and
            # there must not be, because a prefix search over an HMAC would be
            # a search over nothing.
            models.Index(fields=["tenant", "ssn_bidx"], name="ix_customers_ssn_bidx"),
            models.Index(fields=["tenant", "driving_licence_bidx"], name="ix_customers_dl_bidx"),
            models.Index(fields=["tenant", "phone_bidx"], name="ix_customers_phone_bidx"),
            # CR-056 W2b — the ONE lookup a company match makes. Same shape and
            # same reasoning as the three above: an equality probe against a
            # blind-index token, so a plain btree is right and a prefix search
            # would be a search over an HMAC.
            models.Index(fields=["tenant", "tax_id_bidx"], name="ix_customers_tax_id_bidx"),
        ]


class CustomerAccount(models.Model):
    """The BR-CUS-054 link — `customer_accounts`, B2 r9 #1's "N:M link".

    N:M is B2's word and it is honoured: the uniqueness is on the PAIR, not on
    the account, so nothing here forbids a jointly-held account. What the
    import writes is one link per created account (US-CUS-019 TC-2: three
    accounts, three links, one customer)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, db_column="customer_id")
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: ══════════════════════════════════════════════════════════════════
    #: HOW THIS LINK CAME TO BE MADE — CR-056 W3 (BR-CUS-089, BR-CUS-471)
    #: ══════════════════════════════════════════════════════════════════
    #: **`BR-CUS-089` REQUIRES THE TIER AND ITS CONFIRMER TO BE STORED, AND
    #: UNTIL 2026-08-31 THE ONLY PLACE THEY COULD BE STORED WAS A SERVICE
    #: REQUEST.** `discounts._stored_match` says so in its own words — it reads
    #: `service_requests.match_tier` and nothing else — so *"a move-in that did
    #: not come from a service request has no stored tier at all"*. An account
    #: opened at the counter could therefore never carry a returning customer's
    #: deposit, however well the clerk had identified them.
    #:
    #: These four columns are the same four `service_requests` carries, on the
    #: row that records the link itself, so **every door that links a customer
    #: records HOW** and `_stored_match` has a second store to read.
    #:
    #: ⚠ **`match_tier` IS NULL ON EVERY LINK MADE BEFORE THIS COLUMN AND ON
    #: EVERY IMPORT LINK, AND THAT IS A REAL STATE.** The bulk import matches on
    #: `external_ref` — the LEGACY system's id (BR-CUS-054) — which is a
    #: reconciliation key and not identity evidence. Writing `strong` there
    #: would let a spreadsheet column move a deposit. A NULL tier refuses the
    #: carry-forward, which is the safe direction and the one `_stored_match`
    #: already takes for an absent tier.
    #:
    #: ⚠ **`match_confirmed_by` IS A PERSON AND MUST STAY ONE.** BR-CUS-089's
    #: confirmer half assumes a human looked; the matcher proposes a tier and a
    #: human at a door commits it. There is no system actor here and adding one
    #: would make the column say a machine confirmed an identity.
    match_tier = models.TextField(null=True, blank=True)  # strong | probable | weak
    #: The facts that agreed, in words — the same posture `service_requests.
    #: match_basis` takes. TEXT and not a field list, because what a clerk
    #: matched on is sometimes a passport on the counter that no column holds.
    match_basis = models.TextField(null=True, blank=True)
    match_confirmed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="match_confirmed_by",
    )
    match_confirmed_at = models.DateTimeField(null=True, blank=True)
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    #: ══════════════════════════════════════════════════════════════════
    #: WHEN THIS PERSON STOPPED HOLDING THIS ACCOUNT — migration 0060
    #: ══════════════════════════════════════════════════════════════════
    #: **`BR-CUS-1030` · PO ruling 2026-09-20, verbatim: *"we cannot override
    #: customer id - seller and buyer cstmer id are unique those does not
    #: change"*.** A property sale used to DELETE the seller's row here, so
    #: after a sale nothing in the database answered *who sold this property*
    #: — only `audit_log`, which is pruned on a retention schedule.
    #:
    #: **NULL means THIS PERSON HOLDS THIS ACCOUNT NOW.** A timestamp means
    #: they held it until then. Every row written before 0060 reads NULL and
    #: that is correct rather than a missing back-fill: the old code deleted a
    #: link the moment it stopped being live, so every surviving row IS one.
    ended_at = models.DateTimeField(null=True, blank=True)
    #: WHICH sale ended it. An account sold twice has two ended rows, and the
    #: timestamps alone cannot say which sale ended which once a sale is
    #: back-dated — which `BR-CUS-1030` permits. No FK, deliberately: the same
    #: call 0048 made for `transfers.request_id`, because `transfers` is
    #: unmanaged and this link is EVIDENCE rather than integrity.
    ended_by_transfer_id = models.UUIDField(null=True, blank=True)
    #: ══════════════════════════════════════════════════════════════════
    #: WHICH OF TWO JOINT HOLDERS IS BILLED — `P0.2` (customers/0070)
    #: ══════════════════════════════════════════════════════════════════
    #: **THIS TABLE IS N:M BY DESIGN AND NOTHING IN IT SAID WHICH ONE.** B2
    #: r9 #1 puts the uniqueness on the PAIR, deliberately, so a jointly-held
    #: account is lawful — two people, two live rows, neither marked.
    #: Everything that then has to name ONE customer picks whichever row the
    #: database happens to hand back first: the statement header, a notice's
    #: addressee, and — since `P0.1` — **the customer stamped on a journal
    #: line, which is immutable the moment it posts.** The blueprint's words:
    #: *"nothing today says which of two joint holders is billed"*, and
    #: *"`P0.2` is a prerequisite for stamping a customer on a journal line"*.
    #:
    #: **ONE PRIMARY PER ACCOUNT AT A TIME, ENFORCED IN THE DATABASE**
    #: (`uq_customer_accounts_primary_live` below, partial on
    #: `is_primary AND ended_at IS NULL`). A service-layer check loses the
    #: race between two clerks, and the prize for losing it is a bill with
    #: two addressees.
    #:
    #: ⚠ **`False` IS A REAL ANSWER, NOT AN ABSENCE.** It means *this person
    #: holds the account and is not the one billed*; it does NOT mean
    #: *unknown*. An account whose live links are ALL false is a state the
    #: backfill deliberately leaves behind — joint holders with nobody
    #: nominated (see `customers/0070`) — and a caller needing the billed
    #: party must handle it rather than fall back to the first row, which is
    #: the bug this column exists to remove.
    #:
    #: The default is `False`, so arriving at this column can never silently
    #: nominate anybody.
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "customer_accounts"
        constraints = [
            #: ⚠ **PARTIAL, AND THE `condition` IS THE WHOLE POINT (0060).**
            #: This was unique on the bare pair until 2026-09-20. Ending a
            #: link rather than deleting it means a seller who later BUYS THE
            #: PROPERTY BACK needs a second row for the same pair — and under
            #: the old whole-pair rule that sale died on a uniqueness error
            #: naming neither person. One LIVE link per person per account;
            #: any number of ended ones. What the original constraint existed
            #: to refuse — the same person linked twice, LIVE, to one account
            #: — is still refused.
            #:
            #: ⚠ **AND THIS IS WHY IT COULD NOT BE DONE IN PYTHON.** Filtering
            #: ended rows out in the service layer leaves the uniqueness on
            #: the whole pair, so the buy-back still cannot be written. The
            #: guarantee has to move in the database or it has not moved.
            models.UniqueConstraint(
                fields=["customer", "account"],
                condition=Q(ended_at__isnull=True),
                name="uq_customer_accounts_pair_live",
            ),
            #: ⚠ **`P0.2` — ONE PRIMARY HOLDER PER ACCOUNT, AT A TIME.**
            #: PARTIAL on both clauses and both are load-bearing. `is_primary`
            #: because a plain UNIQUE on `(tenant, account)` would allow
            #: exactly ONE LINK per account in total — the N:M this table
            #: exists to permit, forbidden by a typo. `ended_at IS NULL`
            #: because a seller who was primary and later buys the property
            #: back needs a second primary row for the same account, and under
            #: the whole-table rule that repurchase would die on a uniqueness
            #: error naming neither person — the identical trap
            #: `uq_customer_accounts_pair_live` above sidesteps, for the
            #: identical reason.
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(is_primary=True, ended_at__isnull=True),
                name="uq_customer_accounts_primary_live",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_customer_accounts_account"),
        ]

    #: ⚠ **`objects` IS DELIBERATELY NOT FILTERED, AND THAT WAS A DECISION
    #: RATHER THAN AN OMISSION.** A default manager hiding ended rows would
    #: have left every one of this table's ~40 readers correct with no edit —
    #: which is exactly why it was the tempting answer. It was REJECTED
    #: because the property-sale suite asks *"is the seller still linked to
    #: this account?"* by reading `CustomerAccount.objects`, so a filtered
    #: manager would have made the ended row invisible to the one check this
    #: column exists to satisfy. The fix would have shipped, the test would
    #: have stayed red, and the obvious next move would have been to weaken
    #: the test. That is hard-won law 7's second habit run backwards: ask what
    #: would make this check FAIL wrongly.
    #:
    #: **So every caller asking "who holds this account NOW" must say so**, and
    #: `live()` is that sentence. ⚠ **IT IS NOT OPTIONAL POLISH:** leaving one
    #: reader unfiltered took the property-sale suite from 23 of 25 rows with
    #: nothing red to 5 of 25 — see `selectors.customer_for_account`.

    @classmethod
    def live(cls, **kwargs):
        """The links that are CURRENT — `ended_at IS NULL`.

        Use this wherever the question is *who holds this account now*: portal
        sign-in, the account's customer, discounts, settlement, deposits. Use
        the bare manager only where the question is genuinely *who has EVER
        held it* — the transfer record and the ownership history.
        """
        return cls.objects.filter(ended_at__isnull=True, **kwargs)


class AccountOpeningBucket(models.Model):
    """The migrated receivable, AGED — `account_opening_buckets` (B2 r9 #2).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — money columns under CLAUDE.md rule 2.
    Row in `12-governance/09-human-review-ledger.md`.

    **BR-CUS-048 (CONFIRMED, PO AC-3 option B): opening balances are FOUR AGED
    BUCKETS, not a lump sum — and lump-sum and invoice-level were EXPLICITLY
    REJECTED.** One figure has no age, so a lump sum lands every migrated
    account at `Current` on day one: collections cannot act, and late fees are
    wrong until the first real invoice ages. The PO asked for this on
    2026-08-24 (*"you will need trial balance field - opening balance for that
    account"*) and it turned out to be signed law from 2026-08-08.

    **The ❄️ FROZEN worked case (GT-16, finance-signed):** `A-12103` at cutover
    2026-08-31 — `84.20 / 62.10 / 0.00 / 121.00` = **267.30**, overdue-day-one
    `62.10 + 0.00 + 121.00` = **183.10**, and one journal entry
    **DR AR 267.30 / CR opening-clearing 267.30**. Batch tie-out: 1,213 accounts
    → **$184,320.55**, which is the `OUTSTANDING` figure on the PO's own
    Accounts screenshot.

    **APPEND-ONLY.** Rows are never edited — a wrong opening balance is
    corrected by a J6 adjustment, because the moment US-CUS-022 posts, an
    immutable journal entry exists against these numbers (hard rule 4).

    ⚠ **TWO JUDGMENTS THIS LANE HAD TO MAKE. Both are recorded in
    `12-governance/02-decision-log.md` rather than left to be discovered.**

    **(1) `amount` is `NUMERIC(18,4)`, not the `(18,6)` US-CUS-021 wrote.** That
    story is dated 2026-08-08; the PO re-signed the money rule on 2026-08-22 —
    *"MOney 4 decimal, percentage 6 decimal , display both 2 decimal"* — and
    CLAUDE.md rule 2 says the rule *"governs what is WRITTEN and what NEW
    COLUMNS DECLARE"*, with existing 18,6 columns staying lawful containers. A
    new column declared today therefore declares 4. GT-16's figures are 2 dp, so
    no frozen number changes; `accounts.balance` stays 18,6 and the sum is exact
    either way.

    **(2) `import_run_id` is a plain UUID, NOT a ForeignKey.** The batch is now
    metering's `ImportRun` (CR-030 W1 puts accounts on the ONE ETL runner,
    BR-MET-096) rather than the `account_import_batches` row US-CUS-021 assumed
    in 2026-08-08. A customers→metering FK is a CROSS-MODULE FK, and B2 §2 makes
    those *the reviewed interface set* — `accounts.unit_id` is in it, this is
    not, and adding one is not a lane's call. A UUID carries the same identity
    for the idempotency key (`opening_balance|<account>|cutover:<batch>`) and
    invents no interface. **Flagged for the Eng-Lead: promote it to a reviewed FK
    or leave it deliberately loose.**"""

    #: The four bands, in ageing order. `current` is not overdue; the other
    #: three are, which is what `overdue_amount` sums for the late-fee base.
    BUCKET_CURRENT = "current"
    BUCKET_31_60 = "d31_60"
    BUCKET_61_90 = "d61_90"
    BUCKET_90_PLUS = "d90_plus"
    BUCKETS = (BUCKET_CURRENT, BUCKET_31_60, BUCKET_61_90, BUCKET_90_PLUS)
    #: The three that are already overdue at cutover (BR-CUS-048, GT-16's
    #: 183.10). Derived from BUCKETS so the two can never disagree.
    OVERDUE_BUCKETS = BUCKETS[1:]

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_column="account_id")
    #: See judgment (2) above — deliberately not an FK.
    import_run_id = models.UUIDField(null=True, blank=True)
    #: BR-CUS-049 "dated at cutover" — ONE date per batch, and it is the JE's
    #: entry date. Stored per row so a bucket can always answer *"aged as of
    #: when?"* without a join to a run that may be years old.
    as_of = models.DateField()
    bucket = models.TextField()  # one of BUCKETS
    amount = models.DecimalField(max_digits=18, decimal_places=4)  # judgment (1)
    currency = models.CharField(max_length=3)
    is_sample = models.BooleanField(default=False)  # BR-TEN-057
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_opening_buckets"
        constraints = [
            # US-CUS-021 §5: UNIQUE (account, bucket). An account has ONE
            # opening position, so a second `d90_plus` row is a double-count of
            # real money, not a second fact.
            models.UniqueConstraint(
                fields=["account", "bucket"], name="uq_account_opening_buckets_account_bucket"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_aob_tenant_account"),
        ]


class AccountImportBatch(models.Model):
    """S68 staged account batch (US-CUS-019 §5 PROPOSED-SCHEMA verbatim —
    "tenant, filename, uploaded_by, row/valid counts, committed_at" — plus the
    🔒 DB-12 file+tags idempotency pair, which §5 does not list and CLAUDE.md
    rule 6 requires).

    HUMAN-OWNED (idempotency keys 🔒). BR-CUS-051: staging writes NOTHING to
    `accounts`/`customers`; a batch that is never committed is retained as
    audit evidence of what someone tried to load.

    **The unique below is the whole of hard rule 6 for this story.** Scoped to
    COMMITTED batches deliberately, exactly as `ReadImportBatch` scopes its own
    to POSTED ones: re-STAGING a file is a legitimate thing to do (an operator
    re-opens the wizard, or fixes the value map and looks again), and it is the
    second COMMIT that would double 1,240 accounts. A full unique would forbid
    the harmless act and the harmful one alike.
    """

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
    #: US-CUS-021 §5 "one date per batch" — the as-of date the opening buckets
    #: age forward from, and the TAG half of the idempotency key.
    cutover_date = models.DateField(null=True, blank=True)
    file_hash = models.TextField(null=True, blank=True)  # 🔒 SHA-256, server-side
    tag_fingerprint = models.TextField(null=True, blank=True)  # 🔒 batch tags
    row_count = models.IntegerField(default=0)
    valid_count = models.IntegerField(default=0)
    skip_errors = models.BooleanField(default=True)  # BR-CUS-051: default ON
    committed_at = models.DateTimeField(null=True, blank=True)  # NULL until commit
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_import_batches"
        constraints = [
            # 🔒 CLAUDE.md rule 6 / B2 DB-12 "file+tags imports".
            models.UniqueConstraint(
                fields=["tenant", "file_hash", "tag_fingerprint"],
                condition=Q(committed_at__isnull=False, file_hash__isnull=False),
                name="uq_account_import_batches_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="ix_account_imports_recent"),
        ]


class AccountImportRow(models.Model):
    """Per-row staging record (US-CUS-019 §5: "batch, row_no, raw jsonb, errors
    jsonb, account_id NULL until commit"). `tenant_id` is carried per DB-1 —
    every tenant-scoped table is RLS-scoped, staging tables included, because
    a staged row holds the customer's name, email and phone before any account
    exists to hang them on."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(AccountImportBatch, on_delete=models.PROTECT, db_column="batch_id")
    row_no = models.IntegerField()
    raw = models.JSONField()  # {"source": <the file's own cells>, "resolved": …}
    errors = models.JSONField(null=True, blank=True)  # list of {column, code, …}
    account = models.ForeignKey(  # set at commit for created rows
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_import_rows"
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_no"], name="uq_account_import_rows"),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="ix_account_import_rows_batch"),
        ]


class ServiceAgreement(models.Model):
    """account ↔ service_point over time (B2 §2 `service_agreements`).

    B2 §2's `tariff_id NOT NULL REFERENCES tariffs(id)` is DELIBERATELY ABSENT:
    r16 #3 supersedes it ("service_agreements.tariff_id → superseded by
    account_plan_assignments, BR-CUS-029"), and r16 is newest-wins over §2.
    Building the superseded column would ship known-dead schema; building its
    replacement would mean authoring DDL no signed document states. Both are
    refused and REPORTED — the plan-assignment record is the next slice."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_column="account_id")
    service_point = models.ForeignKey(  # ⚠ cross-module customers→metering (reviewed set)
        "metering.ServicePoint", on_delete=models.PROTECT, db_column="service_point_id"
    )
    started_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True)  # NULL = still in force
    custom_data = models.JSONField(default=dict, blank=True)  # r17.2 — see Account
    #: BR-TEN-057 — the sample-data tag, on the OWNING row rather than in a
    #: central registry, so it is written only by this module's own service
    #: function on the sample path (BR-TEN-013: tenancy may not write it).
    #: BR-TEN-061 deletes on this predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_agreements"
        indexes = [
            models.Index(
                fields=["tenant", "account", "started_on"], name="ix_sa_tenant_account_started"
            ),
            models.Index(fields=["tenant", "service_point"], name="ix_sa_tenant_service_point"),
        ]


class AccountNote(models.Model):
    """A staff annotation on an account (BR-CUS-035 — CONFIRMED, PO closure
    batch 2026-08-08; US-CUS-011 §5's column list verbatim).

    Customers OWNS this table outright — it is one of exactly two things on S21
    that is not another module's read-model (BR-CUS-034), and the S22 Add-note
    modal (US-CUS-015) is its second door.

    `customer_visible` is CAPTURED AND INERT in v1, and that is the rule, not a
    shortcut: the customer portal is out of v1 scope (roadmap), so nothing reads
    this flag. It is stored anyway because the note that a clerk marked
    customer-visible in August is a fact about what they intended, and a column
    added later cannot recover it. Nothing in this repo may treat it as a
    permission — there is no portal to permit.

    `author` is the identity user, nullable for the same reason every other
    actor column in this repo is: a note written by a background process (the
    prototype's "Autopay enrollment confirmed · System") has no human behind it,
    and a NOT NULL column would force one to be invented.

    NO `deleted_at`. IS-1's 🔒 pattern is deactivate-or-supersede, and a note is
    already append-mostly; what US-CUS-011 asks for is an audited EDIT, which is
    `note.updated` with the whole-row before/after (BR-AUD-003). If a delete is
    ever ruled, it arrives as a rule and a column together.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_column="account_id")
    title = models.TextField(null=True, blank=True)  # title OR body required — service-enforced
    body = models.TextField(null=True, blank=True)
    author = models.ForeignKey(  # ⚠ cross-module customers→identity (B2 §2 reviewed set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="author_id",
    )
    pinned = models.BooleanField(default=False)  # prototype Notes tab: pinned first
    customer_visible = models.BooleanField(default=False)  # captured, inert in v1
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_notes"
        indexes = [
            # The Notes tab's own order: pinned first, then newest (capability
            # matrix row, EP-CUS-03). Indexed as the query runs so a landlord
            # with four hundred notes does not sort them in Python.
            models.Index(
                fields=["tenant", "account", "-pinned", "-created_at"],
                name="ix_account_notes_pinned",
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-031 · THE SERVICE REQUEST — the front door (B19, W4 backend lane)
# ═══════════════════════════════════════════════════════════════════════════
# Story:   CR-031 (PO 2026-08-24, verbatim in 12-governance/11-change-requests.md)
#          Screens: REQ-01 list · REQ-02 detail · REQ-03.1..6 capture · REQ-03.sent
# Rules:   BR-CUS-079 (CONFIRMED — submitting sends the applicant an
#          acknowledgement by email or SMS; it is a NOTIFICATION, so it renders
#          its own absence rather than fabricating a `sent` state) ·
#          BR-CUS-080 (CONFIRMED — `origin_service_request_id` on the CHILD, the
#          SR keeps `outcome` + `outcome_ref`, documents move BY REFERENCE) ·
#          BR-CUS-070 (`address_as_given` is kept verbatim and never overwritten
#          by the resolved record — B19 §12.3 draws the footnote) ·
#          B18 §4.6 (fees are a QUOTE — the request NEVER posts to the ledger) ·
#          CLAUDE.md rules 1 (RLS FORCE), 2 (money 4dp / CHAR(3)), 4
#          (immutability — `service_request_events` is append-only), 6
#          (idempotent number allocation), 7 (every money action audits).
# Design:  04-docs/02-decisions/19-cr031-service-request-capture.md (B19) —
#          the PO's own screenshots, read screen by screen. Where B19 and
#          B18 §5.3 disagree, B19 is the later evidence and says so itself.
#
# ⚠ FOUR COLUMNS THE SCREENS DRAW AND THIS SCHEMA DELIBERATELY DOES NOT CARRY.
#   Each is left OUT rather than guessed, and each names the row that will bring
#   it back (CLAUDE.md prime directive · hard-won law 1). **This list was FIVE
#   until 2026-08-24: the document checklist came off it when BR-CUS-095 closed
#   OQ-351, and it is now a table (`ServiceRequestDocumentRequirement`).**
#
#   1. **The applicant's government identifier — BR-CUS-092 IS RULED AND THE
#      COLUMN IS STILL NOT HERE, WHICH IS A DIFFERENT STATEMENT FROM THE ONE
#      THAT STOOD HERE YESTERDAY.** REQ-03.1 makes `Social Security Number`
#      REQUIRED and promises the customer *"Stored encrypted and shown to staff
#      as the last four digits only."* The PO ruled on 2026-08-24 — *"we have to
#      take SSn and Driver lience and follow PII rules"* — and BR-CUS-092 spells
#      out what that costs: **(b)** both identifiers are written through the
#      app-layer encryptor OQ-016 has required since PO R6, **which must be
#      BUILT**, and `tenancy.ein` migrates onto it as the second caller;
#      **(c)** every read path renders last four only; **(d)** *"the screen may
#      only claim 'stored encrypted' once (b) is live — until then the claim
#      comes OFF the screen"*.
#      **There is still no encryption helper anywhere in `06-backend/`.** A
#      column added before one exists would put *"stored encrypted"* in front of
#      a customer over plaintext — the exact thing clause (d) forbids — and a
#      last-four column is a partial disclosure of the same identifier, so it
#      would make the promise no truer. The encryptor is a `core/` file and
#      `tenancy.ein` is another module's table; **neither is this lane's to
#      write**, and that is reported rather than worked around.
#      `service_request_service.capture_applicant_identifier` refuses by name
#      and now cites BR-CUS-092(b) instead of an unruled question.
#      ⚠ **STALE SINCE 2026-09-15: that function no longer exists.** The
#      encryptor was built 2026-08-27, the SSN landed with it, and the date of
#      birth and the driving licence landed on the PO's ruling of 2026-09-15 —
#      so the stub whose whole job was to state the absence was deleted rather
#      than left refusing a field that works. The paragraph is kept as the
#      record of what was true when it was written. The detail
#      screen also calls the same field `ID`, not `Social Security Number`
#      (DEF-638 12.c), so its NAME is unruled as well as its storage.
#   2. **`date_of_birth` — DEF-638 12.b.** The detail shows `Date of birth →
#      Mar 1988` and matches the customer ON it (*"Matched on: ID number and
#      date of birth"*), and the six-step capture form never asks for it.
#   3. **`acting_for` — DEF-638 12.b.** Same shape: the detail renders
#      `Acting for → Self`; nothing collects it.
#   4. **A business identity field — B19 §8.7.** `Applying as → A business` is
#      drawn and a business has no SSN. What the identifier becomes for a
#      company is *"not recorded and must not be guessed"*.
#
# ✅ AND THE COLUMN THAT USED TO BE FILLED BY NOTHING IS NOW FILLED AT CREATION:
#   `request_no`. **BR-CUS-093 (PO 2026-08-24) closed DEF-634 on the first of
#   its three readings — *"At creation — every draft is numbered"*.** So
#   `create_request` allocates, `allocate_number` stays idempotent, and `submit`
#   allocates nothing at all: a repeated submit is a state transition on a row
#   that already has its identity, which is CLAUDE.md rule 6 getting SIMPLER
#   rather than harder (consequence (e)). Abandoned drafts burn their numbers
#   and **gaps are normal** (consequence (a)) — nothing renumbers, backfills or
#   reuses, and no report may present a gap as a missing record.


class ServiceRequest(models.Model):
    """One numbered application, whatever channel it arrived by (`service_requests`).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — RLS policy (migration 0018) and the
    idempotent number allocation are CLAUDE.md 🔒 paths. Row in
    `12-governance/09-human-review-ledger.md`.

    **This is the object the product does not have** (B18 §5.3). It is the front
    door for every job, not only onboarding: the list's `TYPE` column draws five
    outcomes and the decision panel offers the same five (B19 §12.4 — *"FIVE
    outcomes, not three"*, drawn twice).

    **THE SYSTEM SUGGESTS, THE CLERK DECIDES.** `resolution_kind` and
    `lookup_found` are EVIDENCE the address resolver produced; `outcome` is a
    judgment a named human committed. B19 §12.3: *"Nothing is preselected.
    Approving creates real service and real charges, so the decision is made
    deliberately."* Nothing in this module writes `outcome` from evidence.

    **`address_as_given` is never overwritten** (BR-CUS-070, drawn as a footnote
    on the Location tab): *"The address as the applicant gave it is kept verbatim
    and never overwritten by the resolved record."* The resolved ids sit BESIDE
    it in their own columns and the service refuses an edit to it after
    submission.

    **`waiting_on` is ORTHOGONAL to `state`**, and that is what the list proves:
    `SR-26-0046` is `Submitted` waiting on a *scheduled date* while `SR-26-0042`
    is `Under review` waiting on *payment*. Park sets these four columns and
    moves no state — *"Everything entered stays."*

    ⚠ **`resolved_premises_id` / `resolved_unit_id` are plain UUIDs, NOT
    ForeignKeys**, exactly as `AccountOpeningBucket.import_run_id` is and for the
    same reason: a customers→metering FK is a CROSS-MODULE FK and B2 §2 makes
    those *the reviewed interface set*. `accounts.unit_id` is in that set; this
    is not, and adding one is not a lane's call. **Flagged for the Eng-Lead:**
    promote to a reviewed FK or leave deliberately loose.
    """

    # ── the ELEVEN states ────────────────────────────────────────────────────
    # B18 §5.3.3 draws TEN and B19 adds the eleventh by drawing a control that
    # none of the ten can express: `Manual close` badged `Rarely needed` —
    # *"A request closes on its own when the job it created finishes. Close it
    # by hand only when the job will never run…"*. Recording that as
    # `completed` (*"Service is live"*) would state something false about a job
    # that never ran, so it gets its own terminal state. **Lane judgment, named
    # here rather than left to be discovered** — B19 settles that the control
    # exists and not what state it lands in.
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    MORE_INFO = "more_info"
    APPROVED = "approved"
    IN_FULFILMENT = "in_fulfilment"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"  # the manual close — see above
    STATES = (
        DRAFT,
        SUBMITTED,
        UNDER_REVIEW,
        MORE_INFO,
        APPROVED,
        IN_FULFILMENT,
        ON_HOLD,
        COMPLETED,
        REFUSED,
        WITHDRAWN,
        CLOSED,
    )
    #: The four the list's `Closed` segment groups. Nothing moves out of them
    #: except `reopen`, which B18 §5.3.3 allows from `refused` and `withdrawn`
    #: **with a reason** and from nowhere else.
    TERMINAL_STATES = (COMPLETED, REFUSED, WITHDRAWN, CLOSED)

    #: `Applying as` — REQ-03.1's segmented control, two values.
    APPLICANT_PERSON = "person"
    APPLICANT_BUSINESS = "business"
    APPLICANT_KINDS = (APPLICANT_PERSON, APPLICANT_BUSINESS)

    #: REQ-03.3's six property radios, with the descriptions the review echoes.
    #: ⚠ The description is STORED VOCABULARY, not decoration: B19 §11.1 notes
    #: the review renders `What that means → "The applicant owns and lives in
    #: it"` beside the label, so the pair travels together.
    PROPERTY_TYPES = (
        "standalone_owner_occupied",
        "rental_tenant_applying",
        "rental_landlord_applying",
        "multi_unit_building",
        "under_construction",
        "vacant_land",
    )

    #: What the address resolver FOUND. Evidence, never a decision.
    RESOLUTION_UNRESOLVED = "unresolved"  # nobody has run the resolver yet
    RESOLUTION_NO_PREMISE = "no_premise"  # `Resolved to → No premise record`
    RESOLUTION_SERVED_VACANT = "served_vacant"  # `Served, and the unit is vacant`
    RESOLUTION_SERVED_OCCUPIED = "served_occupied"  # a live account holds it
    #: ⊕ **A FIFTH, 2026-09-15 (CR-094 capture lane E) — *"The address is on
    #: record; no unit was named."*** The PO ruled that day that step 3 SEARCHES
    #: this register (*"if we have unit or street address then we should take it
    #: from premises/Unit - it means its a search"*), and a clerk may pick a
    #: building and name no unit inside it. `BR-CUS-1010` makes that ordinary
    #: rather than an edge case: the owner's account is at an ADDRESS and names
    #: no unit at all.
    #:
    #: ⚠ **NEITHER OF THE TWO VALUES THAT ALMOST FIT WOULD HAVE BEEN TRUE, AND
    #: EACH IS WRONG IN A WAY THAT SHOWS.** `no_premise` says there is no record
    #: — it raises `no_premise_flag` and opens the add-a-premises path over a
    #: property that exists. `unresolved` says *nobody has looked yet*, so
    #: `evidence_for` answers with an empty `Evidence` and `premise_exists`
    #: comes back false — which is the term `_verdict_for` reads to decide that
    #: a NEW CONNECTION is not possible here. The resolver would have argued for
    #: a new connection at an address the clerk had just found in the register.
    #:
    #: The column is a `TextField` with no database constraint, so this widening
    #: moves no migration. Its sentence is a catalogue key like the other four.
    RESOLUTION_PREMISE_NO_UNIT = "premise_no_unit"
    RESOLUTIONS = (
        RESOLUTION_UNRESOLVED,
        RESOLUTION_NO_PREMISE,
        RESOLUTION_PREMISE_NO_UNIT,
        RESOLUTION_SERVED_VACANT,
        RESOLUTION_SERVED_OCCUPIED,
    )

    #: The FIVE outcomes the decision panel offers, plus the two commits that
    #: are not job types (B19 §12.3/§12.4).
    #:
    #: ✅ **`disconnect` COMMITS — BR-CUS-091 (PO 2026-08-24, *"Yes customer can
    #: request it"*), closing DEF-638 12.a.** Two artefacts disagreed and the
    #: ruling says which was right: the list's `SR-26-0048 · DISCONNECT · Ridge
    #: Coffee Co.` is CORRECT, and REQ-02's decision-panel reason (*"only ever
    #: started by collections, never from a customer request"*) is WITHDRAWN and
    #: the control enabled.
    #:
    #: ⚠ **WHAT THE WITHDRAWN REASON GOT RIGHT SURVIVES, AND IT IS THE PART THAT
    #: MATTERS HERE:** a disconnect and a move-out are DIFFERENT OUTCOMES. A
    #: move-out CLOSES the account and settles the deposit (BR-CUS-030); a
    #: disconnect leaves it OPEN AND ACCRUING (BR-MET-105's base charge keeps
    #: running). Nothing in this module may quietly convert one into the other —
    #: the clerk picks and the row records which was picked.
    OUTCOME_NEW_CONNECTION = "new_connection"
    OUTCOME_MOVE_IN = "move_in"
    OUTCOME_MOVE_OUT = "move_out"
    OUTCOME_TRANSFER = "transfer"
    OUTCOME_DISCONNECT = "disconnect"
    JOB_OUTCOMES = (
        OUTCOME_NEW_CONNECTION,
        OUTCOME_MOVE_IN,
        OUTCOME_MOVE_OUT,
        OUTCOME_TRANSFER,
        OUTCOME_DISCONNECT,
    )
    OUTCOME_REFUSED = "refused"
    OUTCOME_CLOSED = "closed"
    OUTCOMES = JOB_OUTCOMES + (OUTCOME_REFUSED, OUTCOME_CLOSED)

    #: `When is it being paid?` — REQ-03.5's two branches, and BOTH are now
    #: actionable. BR-CUS-093 settled when the request exists (at creation, so
    #: `Collect later`'s fee invoice has a parent from the first keystroke —
    #: consequence (f)) and BR-CUS-090 settled how much is handed over
    #: (whatever the counter took, against the quote).
    FEE_TIMING_COLLECT_NOW = "collect_now"
    FEE_TIMING_COLLECT_LATER = "collect_later"
    FEE_TIMINGS = (FEE_TIMING_COLLECT_NOW, FEE_TIMING_COLLECT_LATER)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: `SR-26-0056`, from the `service_request` series (BR-TEN-035;
    #: `core.numbering.SERIES_CATALOG` seeds `SR-{YY}-{0000}` into every
    #: tenant).
    #:
    #: ⚠ **BR-CUS-093 (CONFIRMED, PO 2026-08-24, closing DEF-634): ALLOCATED AT
    #: CREATION.** The PO was shown three readings and chose *"At creation —
    #: every draft is numbered"*, and the reason they gave IS the requirement:
    #: a clerk quotes `SR-26-0048` down the phone while the form is still
    #: half-filled. `create_request` allocates inside its own transaction, so
    #: every row this product writes from 2026-08-24 carries a number.
    #:
    #: **STILL NULLABLE, and the reason is rows, not rules.** Drafts created
    #: before this ruling landed carry NULL and nothing back-fills them —
    #: consequence (a), *"gaps are normal and must not be treated as loss"*,
    #: applies to a missing number for the same reason it applies to a missing
    #: row: renumbering afterwards would move an identifier somebody has
    #: already written down. The partial unique below is what lets several such
    #: rows coexist without being duplicates of each other.
    request_no = models.TextField(null=True, blank=True)
    state = models.TextField(default=DRAFT)

    #: B18 §2.1 *"six channels, one record"*; REQ-03's banner dropdown shows
    #: `Customer portal` and `Physical form`, and the detail header reads
    #: *"Received Aug 08 by walk-in"*. Free text against a service-side
    #: vocabulary rather than a lookup table: the six are a design statement in
    #: a DRAFT document, not a signed reference list, and BR-TEN-036 would make
    #: a lookup tenant-extensible — which nothing has ruled.
    #:
    #: ⚠ **BR-CUS-091 MAKES ONE DISTINCTION LOAD-BEARING (PO 2026-08-24,
    #: *"Yes customer can request it"*).** A request may now ORIGINATE FROM
    #: STAFF — collections raising a disconnect — rather than from an
    #: applicant, and the rule names the consequence in as many words:
    #: *"`channel` must distinguish them and the applicant-identity fields are
    #: not required on a staff-raised disconnect."* So the vocabulary is still
    #: open, and ONE value in it is a rule: `staff_collections`.
    channel = models.TextField(null=True, blank=True)

    #: The channels that mean *staff raised this, there is no applicant*.
    CHANNEL_STAFF_COLLECTIONS = "staff_collections"
    STAFF_RAISED_CHANNELS = (CHANNEL_STAFF_COLLECTIONS,)

    applicant_kind = models.TextField(default=APPLICANT_PERSON)  # person | business
    #: ⚠ **NULLABLE SINCE BR-CUS-091**, and only for a staff-raised request. An
    #: applicant-raised request still refuses to be created without a name
    #: (`service_request_service._clean_capture`) — the column widened, the
    #: rule did not.
    applicant_name = models.TextField(null=True, blank=True)
    applicant_email = models.TextField(null=True, blank=True)
    applicant_phone = models.TextField(null=True, blank=True)
    preferred_language = models.TextField(null=True, blank=True)  # detail `Language`

    #: ── the applicant's Social Security number ───────────────────────────────
    #: 🔒 SENSITIVE PATH · HUMAN-REVIEW-PENDING — row in
    #: `12-governance/09-human-review-ledger.md`.
    #:
    #: ✅ **CAPTURED AND ENCRYPTED AT REST — BR-CUS-092(a)/(b), and the PO
    #: ruling of 2026-08-27 closing DEF-632.** PO verbatim: *"We need to capture
    #: SSN and encript it; we have to ensure it is working"*.
    #:
    #: **Neither half was invented here.** The screen already drew the field
    #: (B19 §2 `Social Security Number *`) and `core.crypto` already implemented
    #: AES-256-GCM with a 96-bit nonce per encryption and AAD binding a
    #: ciphertext to its column (signed law from OQ-016, CLOSED at PO R6). This
    #: column connects them; `crypto_context` is the AAD, so a value lifted out
    #: of here and dropped into `tenants.ein` raises rather than decrypting.
    #:
    #: ⚠ **THERE IS NO `ssn_last4` COLUMN AND THAT IS DELIBERATE.** BR-CUS-092(c)
    #: requires last-four rendering, which is a READ projection —
    #: `service_request_reads` computes it with `crypto.last_four()` at the
    #: moment it serves. Storing four of the nine digits beside the ciphertext
    #: would put part of the identifier back in the clear for no gain: the
    #: promise this ruling asks us to keep is that **the database row contains
    #: no part of the number**, and a derived column would make that sentence
    #: false while every test still passed.
    #:
    #: ⚠ **AND NO BLIND INDEX.** `crypto.blind_index()` exists and BR-CUS-089's
    #: match tiers will want it, but no matcher is built (`suggest_matches`
    #: refuses by name) and an equality-searchable token nothing queries is
    #: surface without a caller. It is added by the lane that builds the matcher,
    #: which is the only lane that can prove it works.
    #:
    #: ✅ **THE DRIVING LICENCE IS CAPTURED TOO SINCE 2026-09-15** — see
    #: `drivers_licence` below. BR-CUS-092(a) names both identifiers and this is
    #: the second half of it landing; nothing about THIS column changed.
    #:
    #: ⚠ **B19 §14.1 STILL DRAWS ONE TYPED COLUMN** (`ID type` + `ID number`,
    #: `DL ••••4417`) where we now hold two, which is `OQ-780` — open,
    #: non-blocking, and narrowed rather than answered by the ruling of
    #: 2026-09-15: the PO named the two columns, so an applicant may hold BOTH
    #: identifiers, and what is left open is whether the DETAIL screen ever
    #: collapses them into one typed row.
    ssn = EncryptedTextField(
        null=True,
        blank=True,
        crypto_context="service_requests.ssn",
    )

    #: ── the applicant's date of birth ────────────────────────────────────────
    #: ✅ **CAPTURED SINCE 2026-09-15 — PO ruling of that date, finishing
    #: `BR-CUS-092`(a) and making `BR-CUS-089` assessable for the first time.**
    #: PO verbatim: *"ensure user is able to inputs both these on step 1 - Date
    #: of birth and driver's licence on step 1"*.
    #:
    #: **A PLAIN `date`, AND `BR-CUS-1020` ALREADY SETTLED WHY:** *"it must be
    #: COMPARABLE, `contacts.dob` is a plain date too, and `BR-CUS-092` names two
    #: identifiers of which it is not one."* It is the MIDDLE CLAUSE of
    #: `BR-CUS-089`'s *name + date of birth + one government ID*, not an
    #: identifier — encrypting it would mean the reconciliation against
    #: `contacts.dob` and `customers.date_of_birth` could not compare them at
    #: all, and widening a signed encryption rule to a column it does not name
    #: would be inventing law.
    #:
    #: ⚠ **A COMPANY HAS NONE** (`BR-CUS-1022`), so `_clean_capture` refuses it
    #: BY NAME on a request whose `applicant_kind` is `business` rather than
    #: storing a date a business has not got.
    date_of_birth = models.DateField(null=True, blank=True)

    #: ── the applicant's driving licence ──────────────────────────────────────
    #: 🔒 SENSITIVE PATH · HUMAN-REVIEW-PENDING — row in
    #: `12-governance/09-human-review-ledger.md`.
    #:
    #: ✅ **THE SECOND HALF OF `BR-CUS-092`(a), LANDING 2026-09-15.** That clause
    #: has read *"both identifiers are captured on the service request"* since
    #: 2026-08-24; the amendment of 2026-08-31 said in capitals that this half
    #: was outstanding. **No signed statement is superseded by this column.**
    #:
    #: **THE THIRD CALLER OF `core.crypto`, NOT A NEW CAPABILITY** — after
    #: `tenants.ein` and `service_requests.ssn`. AES-256-GCM, a fresh 96-bit
    #: nonce per write, and `crypto_context` as the AAD, so a value lifted out of
    #: `customers.driving_licence` and dropped in here RAISES rather than
    #: decrypting.
    #:
    #: ⚠ **THE COLUMN IS `drivers_licence` AND THE CUSTOMER'S IS
    #: `driving_licence`.** Two spellings of one fact is a hazard, and it is
    #: recorded rather than tidied: the ruling of 2026-09-15 and `BR-CUS-092`'s
    #: amendment both name `service_requests.drivers_licence` in as many words,
    #: `customers 0036` shipped `customers.driving_licence` three weeks ago, and
    #: renaming either moves every citation at once. The seam already copes —
    #: `identity_match.from_payload` reads both spellings — and
    #: `_clean_capture` refuses the other spelling BY NAME rather than dropping
    #: it, so a caller that guesses wrong is told which name to use.
    #:
    #: ⚠ **THERE IS NO `drivers_licence_last4` COLUMN AND THERE MUST NOT BE.**
    #: The last four is a READ projection (`crypto.last_four`), computed by
    #: `service_request_reads` at the moment it serves. A stored one puts four
    #: characters of the identifier back in the clear while every test still
    #: passes — `BR-CUS-092` says so three times and this is the fourth.
    drivers_licence = EncryptedTextField(
        null=True,
        blank=True,
        crypto_context="service_requests.drivers_licence",
    )

    #: The keyed blind index beside it — `bix1:<kid>:<HMAC-SHA256>`, the same
    #: shape `customers.driving_licence_bidx` carries (`customers 0036`).
    #:
    #: **IT IS WHY THE COLUMN IS WORTH CAPTURING.** The encryption scheme is
    #: RANDOMISED, so `drivers_licence` cannot be searched, joined or uniquely
    #: indexed — `EncryptedTextField.get_lookup` refuses every lookup but
    #: `__isnull`, loudly. `BR-CUS-089`'s matcher needs equality and nothing
    #: else, and this token gives it equality and leaks nothing else. It is
    #: KEYED, not hashed: a bare digest of a licence number falls to a dictionary
    #: attack on a database dump, and the HMAC key is not in the database.
    #:
    #: ⚠ **NO UNIQUE CONSTRAINT**, for `customers 0036`'s reason: a unique index
    #: is a one-way door that refuses a write at the counter on evidence a clerk
    #: may have mistyped, and `BR-CUS-1022` rules that *a duplicate identifier
    #: refuses to LINK and never refuses to SAVE*.
    #:
    #: ⚠ **NEVER SET DIRECTLY.** It is derived from the identifier and written
    #: with it, in one act — `identity_match.request_blind_index`.
    drivers_licence_bidx = models.TextField(null=True, blank=True)

    #: `Co-applicant`, badged `Optional · contact only` — REQ-03.1, verbatim:
    #: *"They carry no liability for the bill, so we do not need their SSN or
    #: their documents."* Three contact columns and nothing else, which is
    #: exactly what that sentence licenses.
    co_applicant_name = models.TextField(null=True, blank=True)
    co_applicant_email = models.TextField(null=True, blank=True)
    co_applicant_phone = models.TextField(null=True, blank=True)
    #: ⚠ **THE PORTAL'S CO-APPLICANT CARD, *CONTACT BY* AND PREFERENCES LAND
    #: ON CF-1'S COLUMNS BELOW** (`co_applicants`, `contact_by`, `paperless`,
    #: `sms_reminders`, `mailing_*` — `customers/0087`), never on a second set:
    #: lane CF-2 first added its own five and dropped them for CF-1's, so the
    #: move-in reads ONE place whichever screen captured the request.

    #: 🔒 ⊕ **DEF-CUS-10250 — THE LAST FOUR OF THE SSN, AS AN APPLICANT TYPED IT
    #: ONLINE, ENCRYPTED.** PO 2026-10-18, *"okay"* to *"last 4 of SSN only"* on
    #: the portal: the applicant gives four digits and no more, so there is no
    #: full number for `ssn` to hold and `crypto.last_four(ssn)` has nothing to
    #: project. These four digits are stored ONCE, here, through `core.crypto`
    #: (its own AAD) — never in the clear, so `BR-CUS-092`(c)'s promise about the
    #: row is kept — and served exactly as the clerk's own SSN is, last four
    #: only (`service_request_reads`). Written ONLY by `create_from_portal`; the
    #: staff capture still refuses `ssn_last4` BY NAME (`IDENTIFIER_FIELDS`),
    #: because a clerk holds the whole number and types it into `ssn`.
    #: (`customers/0088`, after CF-1's `0087`.)
    applicant_ssn_last4 = EncryptedTextField(
        null=True, blank=True, crypto_context="service_requests.applicant_ssn_last4"
    )

    #: `Customer category` / `Sub-category` — REQ-03.2.
    #: ✅ **ALL SEVEN CHIPS ARE REAL CATEGORIES — BR-CUS-094 (PO 2026-08-24,
    #: *"Expand the signed list to seven"*), closing DEF-635.** The seven the
    #: screen draws are seeded (migration 0019 adds the four that were missing)
    #: and `government` is marked LEGACY: unselectable here, valid everywhere
    #: else. `set_customer_category` refuses a legacy code BY NAME and accepts
    #: any ACTIVE, non-legacy row of **THIS TENANT's own list** — the seven are
    #: the SEED since the PO ruling of 2026-09-17 (*"utility can get their own
    #: account types"*) and a utility may add as many more as it likes. See
    #: `AccountType`.
    #: NULLABLE because the capture form may be saved as a draft before step 2.
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_type_id",
    )
    #: BR-CUS-067's two-level tenant tree. ⚠ The screen's help says *"5 options
    #: for residential"* and the ratified tree has THREE. BR-CUS-094 settled the
    #: PARENT vocabulary (seven categories) and said nothing about the sub-type
    #: counts, so that half of DEF-635 is UNCLOSED and is reported, not filled.
    account_subtype = models.ForeignKey(
        AccountSubtype,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_subtype_id",
    )
    requested_start = models.DateField(null=True, blank=True)  # `Connection date`

    #: BR-CUS-070 — **kept verbatim, never overwritten by the resolved record.**
    address_as_given = models.TextField()
    address_unit_as_given = models.TextField(null=True, blank=True)
    # ══════════════════════════════════════════════════════════════════════
    # **THE ADDRESS PARTS AN APPLICANT GAVE — PO ruling 2026-09-22.**
    #
    # Verbatim: *"correct address will be on presmies but first time you will
    # ahve to take the details to match it"*.
    #
    # ⚠ **THIS IS NOT A FOURTH HOME FOR AN ADDRESS AND `BR-MET-1161` IS NOT
    # NARROWED.** The rule governs where an address is STORED AS THE TRUTH;
    # these are a record of WHAT A MEMBER OF THE PUBLIC SAID, which is why
    # every one of them carries `_as_given` in its name — the same posture
    # `address_as_given` has had since it was written, and the same posture
    # `interruptions.location_text` has (*"what a stranger typed — a report,
    # not a record"*). The decision log of 2026-09-22 states it: *"a request is
    # not a home for an address: it is a record of a statement made by a member
    # of the public."*
    #
    # ⚠ **WHAT THEY ARE FOR: MATCHING.** A request that cannot take a city and
    # a ZIP cannot find the premises it is about, which is the one thing step 3
    # exists to do. Once `premises_id` is set, **the premises is what every
    # screen shows** — that clause is part of the ruling, not a nicety.
    #
    # ⛔ **THREE IDENTICAL COLUMNS WERE ADDED ON 2026-09-15 AND TAKEN OUT THE
    # SAME HOUR, AND THE DIFFERENCE IS THE NAME AND THE RULING.** Those were
    # `address_city_as_given` / `address_state_as_given` /
    # `address_postal_code_as_given`, added while the PO's ruling of that day
    # said capture is a SEARCH and the locality is walked to. `BR-CUS-1055`
    # records the near-miss. The PO has now ruled the other way, with the
    # storage rule explicitly untouched, and these are named
    # `..._as_given` so `G85` can go on refusing a real fourth home while
    # letting a STATEMENT through.
    #
    # ⚠ **NOTHING DOWNSTREAM MAY READ THESE AS THE SERVICE ADDRESS.** They are
    # not indexed, not walked to, and no screen presents them as the property's
    # address once a premises is matched.
    # ══════════════════════════════════════════════════════════════════════
    address_city_as_given = models.TextField(null=True, blank=True)
    address_state_as_given = models.TextField(null=True, blank=True)
    address_postal_code_as_given = models.TextField(null=True, blank=True)  # `Unit, flat or suite`
    #: ⛔ **THERE IS NO `city`, `state` OR `postal_code` ON THIS ROW, AND THERE
    #: MUST NOT BE — PO ruling 2026-09-15, verbatim: *"if we have unit or street
    #: address then we should take it from premises/Unit - it means its a search
    #: and if not foudn them alow user to add them"*.**
    #:
    #: The Accounts blueprint draws five address boxes on capture step 3 (p077)
    #: and prints the whole of it back as one line on the request's own screen
    #: (p083) — `As given → 212 Balcones Drive, Unit 3, Austin TX 78704` — and
    #: the town, the state and the postcode in that line are **the matched
    #: PREMISES' facts, read by walking to it**, not three more columns here.
    #: Capture is a SEARCH of the premises register; where the search finds
    #: nothing, a premises is added and the facts are its.
    #:
    #: That is `CLAUDE.md` hard rule 8 / `BR-MET-1161` applied to this screen
    #: rather than a new rule, and three such columns would have been exactly
    #: the fourth address home `G85` exists to refuse. **This comment exists
    #: because they were written and taken out again on 2026-09-15** — the next
    #: lane reading the drawing will want to add them, and the answer is in the
    #: read model: `service_request_reads.resolved_place` serves
    #: `premise_locality` by walking, exactly as `DEF-CUS-3653` fixed the
    #: account header.
    #:
    #: `address_as_given` and `address_unit_as_given` above STAY. They are what
    #: the applicant said — evidence, never overwritten by the resolver
    #: (`BR-CUS-070`, and p077 draws the same rule as a footnote).
    #:
    #: `How many units are on this property? *` — drawn on capture step 3 helped
    #: by *"What the applicant says is there"* (p077) and printed on the
    #: request's own screen as `Units on the property · 6` (p082). **PO ruling
    #: 2026-09-15, verbatim: *"we need to build this"*.**
    #:
    #: ⚠ **IT IS A CLAIM, NOT A COUNT, AND THE DIFFERENCE IS DRAWN.** The
    #: blueprint's match table puts them side by side — `Units on the property ·
    #: 6` against `6 units on PR-0731`, confidence `Agrees` — so what the
    #: applicant SAYS and what the register HOLDS are two facts that may
    #: disagree. Nothing here reads `units` and nothing here writes it; a
    #: premises' real unit count is metering's and is reached by walking.
    #:
    #: ⚠ **NO CAP (`NFR-5`).** No maximum is declared and none may be added.
    #:
    #: Before this column the number survived only in whatever a clerk typed
    #: into free-text notes, *"which no screen and no rule can read"* — the
    #: drawing's own annotation, and `DEF-CUS-5385`'s finding.
    units_on_property = models.IntegerField(null=True, blank=True)
    billing_address_same = models.BooleanField(default=True)
    #: ⚠ **THE ONE-BOX BILLING ADDRESS, KEPT AND NO LONGER WRITTEN BY THE
    #: CAPTURE WIZARD — `DEF-CUS-6408`, PO report 2026-09-23.** Every request
    #: captured before that day holds whatever the clerk typed here as ONE
    #: string, and it stays exactly as typed (`BR-CUS-070`): nothing parses it,
    #: because splitting a free-text address into parts is the guess
    #: `BR-NOT-029` clause (a) forbids and `DEF-2703` warned against. Screens
    #: show it where the parts below are empty.
    billing_address_as_given = models.TextField(null=True, blank=True)
    #: ✅ **WHERE THE BILL GOES, IN PARTS, AS THE APPLICANT GAVE IT — PO report
    #: 2026-09-23, verbatim: *"if customer want put billing address then it
    #: should full address line, unit, city, zip it shoould be match how address
    #: taken in USA ;do'nt make it mandatory"*.** `DEF-2703`'s own
    #: recommendation: *"discrete columns going forward, the blob kept verbatim
    #: beside them"*. `DEF-CUS-6408`.
    #:
    #: ⚠ **NOT A FOURTH HOME FOR AN ADDRESS.** This is `CLAUDE.md` hard rule 8's
    #: FIRST named exception — *where the BILL goes* — held on the request
    #: because a request is not an account yet. When an account is opened from
    #: the request the parts become that account's `customers.addresses`
    #: `kind='mailing'` row (the move-in wizard prefills its mailing block from
    #: them). Each carries `_as_given` for the same reason `address_as_given`
    #: does, and `G85`'s declared blind spot moves from 6 columns to 11 in the
    #: same commit.
    #:
    #: **All optional, including once the box is unticked.** `state` is the
    #: two-letter code the capture wizard's picker offers; the ZIP's FORMAT is
    #: checked on the screen (5 digits or ZIP+4) and nothing here refuses a
    #: value, because what the applicant said is kept as said.
    billing_line1_as_given = models.TextField(null=True, blank=True)
    billing_line2_as_given = models.TextField(null=True, blank=True)
    billing_city_as_given = models.TextField(null=True, blank=True)
    billing_state_as_given = models.TextField(null=True, blank=True)
    billing_postal_code_as_given = models.TextField(null=True, blank=True)
    # ── Lane CF-1 (2026-10-18) — ONE CUSTOMER-DATA SHAPE ACROSS THE CREATE
    # SCREENS (decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT
    # ACROSS THE CREATE SCREENS"*; PO: *"ALSO DATA COLECTED IS NOT LOST"*). The
    # staff request now asks the shared customer form, and every value it asks
    # is kept here until the move-in or new connect it leads to carries it on
    # (`services._carry_request_decisions`).
    #
    # **WHERE THE BILL GOES is the MAILING address, as on every other screen**
    # (`customers.addresses` `kind='mailing'`, hard rule 8's first named
    # exception). `customers/0087` copied every `billing_*_as_given` value into
    # these columns and deleted nothing: the old columns stay as written, and a
    # reader with no mailing value falls back to them (`_mailing_parts`).
    mailing_same = models.BooleanField(default=True)
    mailing_line1 = models.TextField(null=True, blank=True)
    mailing_line2 = models.TextField(null=True, blank=True)
    mailing_city = models.TextField(null=True, blank=True)
    mailing_state = models.TextField(null=True, blank=True)
    mailing_postal_code = models.TextField(null=True, blank=True)
    #: `DEF-CUS-10223` — a BUSINESS applicant's Tax ID / EIN, which the staff
    #: request drew and never sent. Encrypted like every identifier
    #: (BR-CUS-092(b)); every read serves its last four only.
    tax_id = EncryptedTextField(null=True, blank=True, crypto_context="service_requests.tax_id")
    #: Move-in's *Government ID* — the LAST FOUR only (BR-CUS-045), as
    #: `contacts.gov_id_last4` holds it.
    gov_id_last4 = models.TextField(null=True, blank=True)
    #: Move-in's *Contact by* — `CONTACT_BY`.
    contact_by = models.TextField(null=True, blank=True)
    #: The full co-applicant cards (Move-in's co-owner card: name,
    #: relationship, responsible for bills, phone, email, date of birth, SSN,
    #: licence, contact by). ⚠ The SSN and the licence are stored as
    #: `core.crypto` CIPHERTEXT inside each row (contexts
    #: `service_requests.co_applicants.ssn` / `.driving_licence`) — never in
    #: the clear — and every read serves their last four only. The three
    #: `co_applicant_*` columns above stay, mirrored from the FIRST card.
    co_applicants = models.JSONField(default=list, blank=True)
    #: The shared *Preferences* panel on a request (no Autopay — PO
    #: 2026-10-18: autopay needs a saved payment method). Carried into the
    #: move-in or new connect it leads to.
    paperless = models.BooleanField(default=False)
    sms_reminders = models.BooleanField(default=False)
    #: The unresolved-address branch (REQ-03.3): `Plot or parcel number` and
    #: `What is being built`. Blanks are RENDERED as blanks, never omitted
    #: (B19 §7: `Plot or parcel → Not supplied`).
    plot_or_parcel = models.TextField(null=True, blank=True)
    what_is_being_built = models.TextField(null=True, blank=True)
    property_type = models.TextField(null=True, blank=True)

    #: ── the resolver's EVIDENCE (never a decision) ───────────────────────────
    resolution_kind = models.TextField(default=RESOLUTION_UNRESOLVED)
    #: `What the lookup found` is **STORED ON THE REQUEST**, not merely rendered
    #: (B19 §7). The sentence a clerk read when they decided has to survive the
    #: premises being created the next day, or the audit of the decision is a
    #: reconstruction.
    lookup_found = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_premises_id = models.UUIDField(null=True, blank=True)  # see class docstring
    resolved_unit_id = models.UUIDField(null=True, blank=True)
    no_premise_flag = models.BooleanField(default=False)
    #: `What they said` → *"I'm moving into somewhere"* — the applicant's own
    #: words, beside `What the address lookup found`. B19 §12.3 right-labels the
    #: pair *"The application never asked what kind of job this is — that is
    #: decided here"*.
    what_they_said = models.TextField(null=True, blank=True)

    #: ── CR-072: THE REPORT IS THE REQUEST ────────────────────────────────────
    #: *What sort of problem* — `leak_or_burst`, `no_water`, `low_pressure`,
    #: `missed_collection`, `damaged_meter`. NULL on every request that is not a
    #: report, which is most of them.
    #:
    #: ⚠ **THIS COLUMN IS THE WIDENING THE PRODUCT OWNER PRE-AUTHORISED**
    #: (`CR-072`, 2026-09-04, verbatim: *"all the request coming from portal
    #: should go in Service request. if we have to icnrease the defination of
    #: Service request we should do it"*). Before it, a passer-by's report had
    #: nowhere on this row to say WHAT was wrong, which is why the act wrote a
    #: second record and handed the stranger that one's reference.
    #:
    #: ⚠ **IT IS `problem_kind` AND NOT `kind`, AND THE NAME IS LOAD-BEARING.**
    #: This table already carries `applicant_kind` (person or business) and
    #: `outcome_kind` (what sort of child the decision opened). A third bare
    #: `kind` on the same row would be read wrong by the next person who greps
    #: for it — and a mis-read column on the row a clerk works from is exactly
    #: the class of fault `DEF-2804` records one register over.
    #:
    #: **The VOCABULARY still lives in `metering`** (`interruptions.
    #: STORABLE_KINDS`) and is imported, not copied. The operational record is
    #: metering's (B2 §2) and two spellings of one list is how they drift.
    problem_kind = models.TextField(null=True, blank=True)

    #: The CONFIRMED interruption this report is about, once a clerk has judged
    #: the reports real — or NULL, which is the normal state of a report nobody
    #: has looked at yet.
    #:
    #: ⚠ **MANY REPORTS POINT AT ONE INTERRUPTION, AND THE FK USED TO RUN THE
    #: OTHER WAY.** `interruptions.service_request_id` was one-to-one, which is
    #: what forced a second interruption row per report — twelve people ringing
    #: about one burst main made twelve "interruptions". `CR-072` §4 reverses
    #: it: the report is the request, the interruption is the utility's own
    #: operational record, and it may GATHER many requests.
    #:
    #: ⚠ **A PLAIN UUID AND NOT A ForeignKey**, exactly as `resolved_premises_id`
    #: and `resolved_unit_id` are three fields up, and for the same reason: a
    #: customers→metering FK is a CROSS-MODULE FK and B2 §2 makes those *the
    #: reviewed interface set*. **Flagged for the Eng-Lead** alongside the two
    #: that are already flagged — promote all three, or leave all three
    #: deliberately loose.
    interruption_id = models.UUIDField(null=True, blank=True)

    #: ── the customer match (BR-CUS-089's tier vocabulary, drawn `Strong`) ────
    #: ⚠ There is NO automatic matcher here. The detail says *"Matched on: ID
    #: number and date of birth"* and this schema carries NEITHER (DEF-632,
    #: DEF-638 12.b), so a matcher would be matching on fields that do not
    #: exist. A clerk LINKS a customer explicitly — the Decision tab draws that
    #: search and its `Linked ✓` — and `service_request_service.suggest_matches`
    #: refuses by name.
    matched_customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="matched_customer_id",
    )
    match_tier = models.TextField(null=True, blank=True)  # strong | probable | weak
    match_confirmed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="match_confirmed_by",
    )
    match_confirmed_at = models.DateTimeField(null=True, blank=True)
    #: `Matched on` → the fields the clerk says they matched on, in their words.
    #: TEXT and not a field list, because the two the screen names are the two
    #: this schema does not carry.
    match_basis = models.TextField(null=True, blank=True)

    #: ── eligibility (B18 §5.3.4: *"Never blocks service — only the discount"*,
    #: and B19 §12.3 draws the condition as `Eligibility evidence — None claimed
    #: — does not block`). A claim is recorded; it never gates approval.
    eligibility_claimed = models.BooleanField(default=False)
    eligibility_note = models.TextField(null=True, blank=True)

    #: ── intake provenance ────────────────────────────────────────────────────
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="received_by",
    )
    assigned_to = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="assigned_to",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    #: ── PARK — the PO's save-and-exit requirement, and it is TWO controls ────
    #: B19 §12.2: `Save & exit` leaves quietly and writes nothing here; `Park`
    #: records WHAT is awaited, a note and a reminder date, and surfaces on the
    #: list's `WAITING ON` column. **It moves no state** — the list shows
    #: `Submitted`/`Under review` rows carrying a `WAITING ON` value.
    waiting_on = models.TextField(null=True, blank=True)
    park_note = models.TextField(null=True, blank=True)
    remind_on = models.DateField(null=True, blank=True)
    parked_at = models.DateTimeField(null=True, blank=True)
    parked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="parked_by",
    )

    #: ── THE FEE, AS THE COUNTER RECORDED IT — BR-CUS-090 ─────────────────────
    #: **CONFIRMED, PO 2026-08-24, closing DEF-637.** Verbatim: *"we acept it
    #: and in finance we will reconcile ; here segregation of responsibilitys,
    #: accept it and mark it as cash"*. The two screens that disagreed were both
    #: right about their own half — the capture QUOTES $130.00, the receipt
    #: records the $25.00 that was actually handed over — and the resolution is
    #: to store BOTH rather than pick one.
    #:
    #: **`fee_collected < fee_quoted` IS A LAWFUL, STORABLE STATE.** The
    #: difference is an open fee balance; it is never a refusal at the desk and
    #: never a silent waiver (a waiver is BR-CUS-073's explicit act with a
    #: reason — `waive_fee_line`). Worked, on the screen that raised the defect:
    #: quoted **$130.00**, taken **$25.00** cash, receipt `RCP-26-4471` →
    #: **$25.00 collected of $130.00 quoted · $105.00 outstanding**, and the
    #: review step reads that outstanding figure.
    #:
    #: **The two roles stay separate, which is the reason the PO gave.** The
    #: person who takes the money records it here; finance agrees it against the
    #: cash count. So the request never adjusts its own quote to match the cash.
    #:
    #: ⚠ **`fee_receipt_no` IS RECORDED, NOT ALLOCATED.** The screen's
    #: `RCP-26-4471` is not payments' `RCT-` series, and this module may not
    #: write payments' tables (hard rule 5, cross-module writes forbidden). It
    #: stores the number the counter wrote on the slip. ONE of them, per
    #: BR-CUS-090's own wording.
    #:
    #: **Still no ledger posting** (B18 §4.6). Money at 4 dp, `CHAR(3)`
    #: currency, display 2 (CLAUDE.md rule 2); every write audits (rule 7).
    fee_timing = models.TextField(null=True, blank=True)  # collect_now | collect_later
    fee_due_by = models.DateField(null=True, blank=True)  # `Due by` on Collect later
    fee_method = models.TextField(null=True, blank=True)  # cash | card | check

    #: How the collection was taken. `waive` is NOT here — waiving is a LINE
    #: act with a reason (BR-CUS-073 / `waive_fee_line`), not a way of paying.
    #:
    #: ⚠ **AMERICAN ENGLISH — `check`, NEVER `cheque`.** PO ruling 2026-09-29,
    #: verbatim: *"use american english check = not cheque"*. This was
    #: `cheque`, and it was the ONE place in this product that stored the
    #: British spelling of a tender: `payments` has spelled it `check` since
    #: `BR-PAY-026`, `payments.counter_receipts.FEE_METHOD_TO_TENDER` existed
    #: only to translate between the two, and `tenancy.PaymentMethod` seeds
    #: `check`. A stored value is not a label, so this moved with a data
    #: migration (`customers/0069`) rather than with a rename.
    #:
    #: ⚠ **`cheque` IS STILL ACCEPTED ON THE WIRE AND NEVER WRITTEN AGAIN.**
    #: `collect_fee` normalises it before anything is stored, so a caller that
    #: has not been redeployed keeps working and the column holds one spelling.
    #: Retiring the input would break a live screen for a word (`DEF-CUS-3653`
    #: is what retiring a value without grepping its consumers costs).
    FEE_METHOD_CASH = "cash"
    FEE_METHOD_CARD = "card"
    FEE_METHOD_CHECK = "check"
    #: ⛔ LEGACY INPUT ONLY. Never stored, never served, never offered.
    FEE_METHOD_CHEQUE_LEGACY = "cheque"
    FEE_METHODS = (FEE_METHOD_CASH, FEE_METHOD_CARD, FEE_METHOD_CHECK)
    #: What an older caller may still send, and what it becomes.
    FEE_METHOD_ALIASES = {FEE_METHOD_CHEQUE_LEGACY: FEE_METHOD_CHECK}

    #: The quote AS IT STOOD when the money was taken — a snapshot, not a live
    #: sum. Adding a line afterwards must not retro-change what the clerk was
    #: holding a receipt for.
    fee_quoted = money_field(null=True, blank=True)
    fee_collected = money_field(null=True, blank=True)
    fee_currency = models.CharField(max_length=3, null=True, blank=True)
    fee_receipt_no = models.TextField(null=True, blank=True)
    fee_collected_at = models.DateTimeField(null=True, blank=True)
    fee_collected_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="fee_collected_by",
    )

    #: ── BR-CUS-080: the SR alone answers *"what happened to this application"* ─
    outcome = models.TextField(null=True, blank=True)  # one of OUTCOMES
    #: What KIND of child the outcome opened, and its reference. The child's own
    #: `origin_service_request_id` is the other half of the link and lands with
    #: the child table (W5 move-in / W6 new connect) — it does not exist yet, so
    #: this side is written and the pair is completed there.
    outcome_kind = models.TextField(null=True, blank=True)
    outcome_ref = models.TextField(null=True, blank=True)
    outcome_linked_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="decided_by",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    #: One of `service_request.REFUSAL_REASONS` — the five the blueprint draws
    #: in the Refuse dialog's `Reason *` select. ⚠ **IT HAS BEEN ACCEPTED SINCE
    #: CR-031 AND NO SCREEN EVER SET IT, AND IT WAS FREE TEXT** (`DEF-CUS-5389`,
    #: 2026-09-15): a register of refusals with typed sentences in this column
    #: answers no question about why this utility turns people down. It is
    #: validated against the vocabulary now.
    reason_code = models.TextField(null=True, blank=True)
    #: Why, for US. Internal — it is what the clerk tells the register, and it
    #: has always been the only thing a refusal stored.
    decision_reason = models.TextField(null=True, blank=True)
    #: ── CR-094-BRC01 · DEF-CUS-5389 — what the APPLICANT is told ────────────
    #: ⚠ **THESE THREE ARE THE FIRST COLUMNS ON THIS TABLE WHOSE CONTENTS LEAVE
    #: THE BUILDING.** Everything above is what the utility records; these are
    #: what a person outside it reads.
    #:
    #: `refusal_message` is the drawing's `What to tell them`, whose helper line
    #: is *"Goes into the refusal letter."* — so it is the body of the letter and
    #: not a note. `decision_reason` directly above is its opposite number and
    #: stays internal; keeping them apart is the whole point, because one
    #: column serving both would put a clerk's shorthand in front of an
    #: applicant.
    refusal_message = models.TextField(null=True, blank=True)
    #: The Ask-for-more dialog's `WHAT IS NEEDED` tick list, as a list of codes
    #: from `service_request.INFO_NEEDED_KINDS`. A LIST rather than four
    #: booleans because the drawing ticks two of four in one act and the set is
    #: what the clerk chose, and because a fifth thing to wait for is then a
    #: vocabulary edit rather than a migration.
    #: ⚠ It is NOT sent: the drawing attaches *Sent to them* to the message box
    #: alone. This is the clerk's checklist, kept on the request and on its
    #: history.
    info_needed = models.JSONField(default=list, blank=True)
    #: The drawing's `Message to the applicant`, *"Sent to them and kept on the
    #: request's history."* It replaces one fixed sentence — *"More information
    #: is needed before this can be reviewed."* — that every request in the
    #: product sent alike and that no applicant ever received.
    info_message = models.TextField(null=True, blank=True)
    #: TRUE when the clerk committed an outcome the evidence marked
    #: `not_possible`. **The choice is NOT refused** — CR-031 ruled the clerk
    #: decides and B19 §12.4 restates it — so the disagreement is RECORDED,
    #: with the verdict and the reason that was on screen, rather than blocked.
    decided_against_evidence = models.BooleanField(default=False)
    #: The verdict table exactly as it was rendered at the moment of the
    #: decision. A judgment is only auditable against the evidence it was made
    #: on, and the evidence moves (a premises gets created, an account closes).
    evidence_snapshot = models.JSONField(default=dict, blank=True)

    #: ── BR-CUS-079's acknowledgement, and its ABSENCE ────────────────────────
    #: CONFIRMED: *"when you take and submit SR - we have to send email or text
    #: messge to customer"*. The rule itself says the acknowledgement is a
    #: NOTIFICATION and therefore subject to the same absence rule as every
    #: other — **no delivery adapter exists in this product**, so this records
    #: what was QUEUED and, when nothing could be, WHY. Never a `sent` state
    #: (hard-won law 1; the same posture as W7 task 7.10's `LAST NOTICE`).
    acknowledgement_state = models.TextField(null=True, blank=True)
    acknowledgement_ref = models.TextField(null=True, blank=True)
    acknowledgement_absence_reason = models.TextField(null=True, blank=True)
    acknowledgement_at = models.DateTimeField(null=True, blank=True)

    closed_at = models.DateTimeField(null=True, blank=True)
    #: `CR-161-BRC10` W6 — the REQUEST'S OWN COPY of the utility's fields typed
    #: on Staff New Request, one blob per record type it will feed:
    #: ``{"customers": {…}, "accounts": {…}, "premises": {…}}``. Kept whatever
    #: approval does; copied onto the real records by
    #: `request_custom_fields.apply_on_approval` (`customers/0076`).
    custom_data = models.JSONField(default=dict, blank=True)
    is_sample = models.BooleanField(default=False)  # BR-TEN-057
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_requests"
        constraints = [
            # One request number per tenant. STILL PARTIAL after BR-CUS-093:
            # every row created from 2026-08-24 is numbered at creation, and
            # rows that predate the ruling sit at NULL forever (nothing
            # back-fills — consequence (a)). Several NULLs are not duplicates
            # of each other.
            models.UniqueConstraint(
                fields=["tenant", "request_no"],
                condition=Q(request_no__isnull=False),
                name="ux_service_requests_no",
            ),
            # BR-CUS-080, the half this table can enforce: **one SR produces one
            # live child per decision.** The child cannot be pointed at twice
            # because the pair is unique within the tenant.
            models.UniqueConstraint(
                fields=["tenant", "outcome_kind", "outcome_ref"],
                condition=Q(outcome_ref__isnull=False),
                name="ux_service_requests_outcome_ref",
            ),
        ]
        indexes = [
            # The list's own order — *"Sorted by age, oldest first"* — and its
            # segment filter, in one index.
            models.Index(fields=["tenant", "state", "received_at"], name="ix_sr_state_received"),
            models.Index(fields=["tenant", "waiting_on"], name="ix_sr_waiting_on"),
            # CR-072 — *"which reports is this burst main gathering?"*, which is
            # the read the clerk's interruption section makes on every open.
            models.Index(fields=["tenant", "interruption_id"], name="ix_sr_interruption"),
            # BR-CUS-089's matcher asks one question of this column — *"does any
            # request carry this licence?"* — and asks it with an `__in` over
            # one token per configured key, so an ordinary btree is exactly the
            # right index and a unique one is deliberately not (see the column).
            models.Index(
                fields=["tenant", "drivers_licence_bidx"], name="ix_sr_drivers_licence_bidx"
            ),
        ]


class ServiceRequestService(models.Model):
    """One requested utility service on a request (`service_request_services`).

    REQ-03.2's ten cards, right-labelled *"Everything we supply is listed. Step
    3 confirms what is actually available at the address given."* — which is why
    `available` is NULLABLE and starts NULL: at capture the answer is not known,
    and the CHECK callout says so in as many words (*"we cannot confirm which of
    the requested services are available. That is settled at review."*). NULL is
    *not yet asked*; it is never spelled the same way as *no*.

    ⚠ **This is NOT B18 §5.3.7's `service_request_items`.** That table is one
    row per UNIT on a bulk request (25 units at 500 Main St) and REQ-03 never
    draws it — the capture form asks for services at ONE address. The bulk unit
    schedule belongs to the new-connect wave (W6) that consumes it, and a table
    with no writer is a promise (the `account_import_value_maps` lesson, this
    module's own docstring).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="services",
    )
    #: The PLATFORM ten-service catalogue (r5 #1 / BR-RAT-024) — no tenant_id,
    #: so this is not a cross-tenant reach. B19 §3 confirms the ten cards match
    #: CLAUDE.md's ten exactly; **the BADGE LETTERS do not** (DEF-636 — the
    #: prototype draws `D`/`O`/`H`/`Y`, the product ships `St`/`So`/`Th`/`Ba`),
    #: and badges are a frontend fact, so nothing here stores one.
    service = models.ForeignKey("tenancy.Service", on_delete=models.PROTECT, db_column="service_id")
    requested_start = models.DateField(null=True, blank=True)
    available = models.BooleanField(null=True, blank=True)  # NULL = not yet asked
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "service_request_services"
        constraints = [
            models.UniqueConstraint(
                fields=["request", "service"], name="ux_sr_services_request_service"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "request"], name="ix_sr_services_request")]


class ServiceRequestDocument(models.Model):
    """A file attached to a request (`service_request_documents`).

    **TWO GATES, NOT ONE — B19 §12.4, and it is the finding of that batch.**
    REQ-03.4's `NOT BLOCKING` callout: *"A missing document does not stop the
    request being created. It is verified at review, and the request shows as
    waiting on documents until then."* The detail's `BLOCKING` callout:
    *"Approval is blocked until somebody checks each one — **attaching a file is
    not the same as verifying it**."* So attaching never blocks CREATION and
    verifying blocks APPROVAL, and the two live in different columns.

    **DOCUMENTS MOVE BY REFERENCE, NEVER BY COPY (BR-CUS-080, CONFIRMED).** The
    child job reads this table through the parent's id; nothing copies a row.
    One uploaded file stays ONE row, so `uploaded_by` — the audit of who
    supplied it — survives the hand-off, where a copy would fork it.

    ✅ **OQ-351 IS CLOSED — BR-CUS-095 (PO 2026-08-24).** *"who decides which of
    those eight are compulsory? If the answer is each utility decides for
    itself, then Settings grows a checklist — for each request type, tick which
    documents are required. We ship with nothing ticked, and a utility that
    configures nothing blocks nothing."* The checklist lives in
    `ServiceRequestDocumentRequirement` below, `(request_type × document_type) →
    required`, tenant-scoped and **shipping entirely unticked**.

    `required_flag` on THIS row survives that ruling and means something
    narrower and still useful: *a clerk marked this particular attachment
    required on this particular request*. The tenant checklist is the general
    rule; this column is the case-by-case one. Both feed the same approval gate.
    """

    NOT_CHECKED = "not_checked"
    VERIFIED = "verified"
    REJECTED = "rejected"
    VERIFICATION_STATES = (NOT_CHECKED, VERIFIED, REJECTED)

    #: **THE EIGHT DESIGNED TYPES, quoted from BR-CUS-095 verbatim** — *"proof
    #: of identity, proof of address or occupancy, tenancy agreement or deed,
    #: authority to act, site plan or unit schedule, assistance evidence, signed
    #: service agreement, completion paperwork"* (B18 §5.3.6). These, and only
    #: these, are what a tenant may TICK on the checklist: a rule that could be
    #: written against a free-text label would be a rule nobody could satisfy.
    DOC_PROOF_OF_IDENTITY = "proof_of_identity"
    DOC_PROOF_OF_ADDRESS = "proof_of_address_or_occupancy"
    DOC_TENANCY_OR_DEED = "tenancy_agreement_or_deed"
    DOC_AUTHORITY_TO_ACT = "authority_to_act"
    DOC_SITE_PLAN = "site_plan_or_unit_schedule"
    DOC_ASSISTANCE_EVIDENCE = "assistance_evidence"
    DOC_SIGNED_AGREEMENT = "signed_service_agreement"
    DOC_COMPLETION_PAPERWORK = "completion_paperwork"
    DESIGNED_DOC_TYPES = (
        DOC_PROOF_OF_IDENTITY,
        DOC_PROOF_OF_ADDRESS,
        DOC_TENANCY_OR_DEED,
        DOC_AUTHORITY_TO_ACT,
        DOC_SITE_PLAN,
        DOC_ASSISTANCE_EVIDENCE,
        DOC_SIGNED_AGREEMENT,
        DOC_COMPLETION_PAPERWORK,
    )
    #: ⚠ **A NINTH VALUE IS ATTACHABLE AND MAY NEVER BE TICKED.** B19 §5 draws
    #: three inputs on REQ-03.4 and the third is `Anything else`, badged
    #: **Optional** — *"Whatever the applicant brought that helps"*. It is drawn,
    #: so it is storable; it is not one of the eight, so it cannot be made
    #: compulsory. Keeping the two vocabularies separate is what stops a tenant
    #: ticking a box that no attachment can ever satisfy.
    DOC_OTHER = "other"
    ATTACHABLE_DOC_TYPES = DESIGNED_DOC_TYPES + (DOC_OTHER,)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="documents",
    )
    doc_type = models.TextField()
    #: `WHAT IT PROVES` — the detail's own column. Stored beside the type
    #: because the contextual list carries its own explanation (*"Deed or site
    #: plan — Shows they may build on the plot"*).
    what_it_proves = models.TextField(null=True, blank=True)
    #: **`DOCUMENT NUMBER` — the number ON the document, PO ruling 2026-09-22.**
    #:
    #: ⚠ **IT EXISTS BECAUSE ITS ABSENCE PUT A LICENCE NUMBER ON A LIST SCREEN.**
    #: The capture form's only free-text box asked *what does this document
    #: prove*, and the column heading beside it read the same three words, so a
    #: clerk with a driving licence in their hand had nowhere to put `865554556`
    #: and typed it there. The PO ruled *"Yes, last four only"* on how it is
    #: SHOWN, and option (a) — a field of its own — is the lane judgment
    #: recorded in the decision log of the same day.
    #:
    #: ⚠ **PLAIN TEXT, AND THAT IS A NARROW CLAIM.** `BR-CUS-092` names the SSN
    #: and the driving licence as the two identifiers this product encrypts, and
    #: both have their own encrypted columns on `service_requests`. This is the
    #: reference number of whatever paper was handed over — a tenancy agreement,
    #: a utility bill, a passport — and it is masked on every read path
    #: (`BR-CUS-092(c)`'s posture) rather than encrypted at rest. **No screen
    #: may print it in full**, which is what `maskLastFour` is for.
    document_number = models.TextField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    #: The bytes that are ON DISK. ⚠ **NOT NECESSARILY THE BYTES THE CLERK
    #: CHOSE** — see `original_size` directly below.
    size = models.BigIntegerField(null=True, blank=True)
    #: What the clerk uploaded, when that differs from what was stored.
    #:
    #: ⚠ **NULL MEANS "NOTHING WAS DONE TO THIS FILE", NOT "WE DID NOT LOOK".**
    #: A PDF is stored byte for byte and carries NULL here; an oversized PNG is
    #: losslessly re-deflated on the way in and carries the size it arrived at.
    #: The two must be tellable apart, which is the whole reason this is a
    #: nullable column rather than a copy of `size`: a clerk told a file is
    #: 3.1 MB who then finds 400 KB on disk needs the record to say why, and a
    #: column that always equalled `size` would answer that question wrongly
    #: and confidently.
    #:
    #: **`core.document_shrink` does the reduction and NOTHING IT DOES IS
    #: LOSSY** — the image a reader decodes is bit-identical to the one that
    #: was uploaded. That module's docstring argues why at length; the short
    #: version is that a site plan a clerk reads a boundary off is not a
    #: holiday photograph, and the Accounts blueprint's own worked example has
    #: one marked `Rejected · unreadable`.
    original_size = models.BigIntegerField(null=True, blank=True)
    #: The `tenancy.StoredDocument` id, as text. ⚠ **A REFERENCE, NEVER A
    #: STORAGE KEY** — `document_store` refuses to hand a key out at all, and
    #: `download_url()` re-resolves this id under the caller's own tenant
    #: context before it mints anything.
    storage_ref = models.TextField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="uploaded_by",
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    #: A clerk marked THIS attachment required on THIS request. The tenant-wide
    #: rule is `ServiceRequestDocumentRequirement` (BR-CUS-095); both feed the
    #: same approval gate and neither seeds the other.
    required_flag = models.BooleanField(default=False)
    verification_state = models.TextField(default=NOT_CHECKED)
    verified_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="verified_by",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "service_request_documents"
        indexes = [
            models.Index(fields=["tenant", "request"], name="ix_sr_documents_request"),
        ]


class ServiceRequestDocumentRequirement(models.Model):
    """**BR-CUS-095's checklist — `(request_type × document_type) → required`,
    tenant-scoped, and it SHIPS ENTIRELY UNTICKED**
    (`service_request_document_requirements`).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — RLS policy (migration 0019) is a
    CLAUDE.md rule-1 🔒 path. Row in `12-governance/09-human-review-ledger.md`.

    **PO ruling 2026-08-24, verbatim, closing OQ-351:** *"who decides which of
    those eight are compulsory? If the answer is each utility decides for
    itself, then Settings grows a checklist — for each request type, tick which
    documents are required. We ship with nothing ticked, and a utility that
    configures nothing blocks nothing."*

    ⚠ **THE DEFAULT IS THE SHARPEST CLAUSE AND IS NOT SOFTENED ANYWHERE.** There
    is NO seed, NO data migration and NO fixture behind this table — not even a
    helpful pre-tick of *proof of identity*, however reasonable that looks. The
    reason the ruling gives is a product constraint, not a preference: **the
    product ships with no opinion about any jurisdiction's law**, and a product
    that blocks approvals out of the box for a rule its customer never chose is
    worse than one that blocks none. A row here exists only because a human
    ticked a box. **If you are about to add a seed to this table, you are about
    to break the ruling.**

    **TWO GATES, unchanged and joined rather than replaced** (B19 §5):
    attaching never blocks CREATION; an unverified required document blocks
    APPROVAL. This table decides only WHICH documents are required for which
    kind of job — it has no say in whether a request may be raised.

    **Worked, end to end (the ruling's own case):** a utility ticks
    `proof_of_identity` and `signed_service_agreement` for `move_in` ONLY → a
    move-in request submits and sits happily in `Under review` with neither
    attached, and `approve` refuses by name until both are attached **and
    verified**; the same tenant's `transfer` requests tick nothing and approve
    with no documents at all.

    `request_type` is one of `ServiceRequest.JOB_OUTCOMES` — the kind of job the
    request becomes, which is the clerk's decision and is what `approve` already
    requires before it will look at any condition. `doc_type` is one of the
    EIGHT (`ServiceRequestDocument.DESIGNED_DOC_TYPES`); the drawn `other` is
    excluded on purpose (see that class).

    A row with `required=False` is a tick that was TAKEN BACK, and it is stored
    rather than deleted so the settings screen can show a deliberate "no"
    differently from "never opened" and so `updated_by` survives.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request_type = models.TextField()  # one of ServiceRequest.JOB_OUTCOMES
    doc_type = models.TextField()  # one of ServiceRequestDocument.DESIGNED_DOC_TYPES
    required = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="updated_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_request_document_requirements"
        constraints = [
            # One answer per (tenant, request type, document type). Two rows for
            # the same pair would be two answers to one question, and the
            # approval gate would have to pick.
            models.UniqueConstraint(
                fields=["tenant", "request_type", "doc_type"],
                name="ux_sr_doc_requirements",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "request_type"], name="ix_sr_doc_req_type"),
        ]


class ServiceRequestFee(models.Model):
    """A QUOTED application-fee line (`service_request_fees`).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — money columns (CLAUDE.md rule 2).

    **THIS TABLE NEVER POSTS TO THE LEDGER.** B18 §4.6, and the detail's own
    `SEPARATE` callout says the same thing to the clerk: *"The quote prices the
    work itself and is raised after review. It is not the application fee, and
    settling one does not settle the other."* These rows are a quote; billing
    owns invoices and the ledger posting service owns journal lines (hard rules
    4 and 5). Adding or waiving a line is still a MONEY ACTION and writes
    `audit_log` (hard rule 7).

    `amount` is `NUMERIC(18,4)` and `currency` is `CHAR(3)` — the PO re-sign of
    2026-08-22 (*"MOney 4 decimal, percentage 6 decimal , display both 2
    decimal"*) governs what a NEW column declares. Rounding to two happens at
    display, never here.

    ✅ **WHAT A LINE MEANS IS SETTLED — BR-CUS-090 (PO 2026-08-24), closing
    DEF-637.** The contradiction was real: REQ-03.5 totals three lines to
    **$130.00** (`CC-REQFEE` $25.00 + `CC-EXPED` $60.00 + `CC-METERT` $45.00)
    while the confirmation's `Form fee` panel reads **$25.00, Collected**,
    receipt `RCP-26-4471`. **Both screens were right about their own half.** The
    lines here are the QUOTE; what the counter took is `ServiceRequest.
    fee_collected`; the difference is an open fee balance, not a discrepancy to
    resolve and not a waiver. PO verbatim: *"we acept it and in finance we will
    reconcile ; here segregation of responsibilitys, accept it and mark it as
    cash"*. So `service_request_service.fee_total_to_collect` now TOTALS these
    lines, and `collect_fee` records what was handed over against that total.

    ✅ **OQ-357 CLOSED 2026-09-23 AS "BOTH"** — a DRAFT's line is removed
    (`remove_fee_line`, which deletes the row and leaves `audit_log`), a
    submitted request's is waived. The paragraph below is how it stood before.

    ⚠ **AND A LINE STILL CANNOT BE REMOVED — OQ-357, WHICH BR-CUS-090 DID NOT
    TOUCH.** That ruling settled how much was COLLECTED against the quote; it
    says nothing about what the `⊘` on a quote row does. Each row carries a `⊘` glyph on
    screen and B19 §8.8 records that *"remove, or waive-with-reason"* is **not
    determinable from a picture**. Waiving IS drawn (*"A reason is required and
    recorded against your name"*) and is built; removal is not built and is not
    guessed.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="fees",
    )
    line_no = models.IntegerField()
    #: rating's `charges` row, as a plain UUID for the AccountOpeningBucket
    #: reason: a customers→rating FK is not in B2 §2's reviewed interface set.
    #: The CODE is snapshotted beside it so a retired charge code still prints.
    charge_code_id = models.UUIDField(null=True, blank=True)
    charge_code = models.TextField()  # `CC-REQFEE`
    description = models.TextField(null=True, blank=True)
    basis = models.TextField(null=True, blank=True)  # `per request` · `per meter`
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    unit_amount = money_field()
    amount = money_field()
    currency = models.CharField(max_length=3)
    waived = models.BooleanField(default=False)
    waive_reason = models.TextField(null=True, blank=True)
    waived_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="waived_by",
    )
    waived_at = models.DateTimeField(null=True, blank=True)
    #: Set by whatever raises the invoice — NOT by this module. Present so the
    #: approval condition can read *is this line settled* without inventing a
    #: second source for the answer.
    invoice_ref = models.TextField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    settlement_ref = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "service_request_fees"
        constraints = [
            models.UniqueConstraint(fields=["request", "line_no"], name="ux_sr_fees_request_line"),
        ]
        indexes = [models.Index(fields=["tenant", "request"], name="ix_sr_fees_request")]


class ServiceRequestEvent(models.Model):
    """The History tab — one append-only row per thing that happened
    (`service_request_events`).

    **APPEND-ONLY.** Nothing in this module updates or deletes a row here; a
    correction is a new row. That is not decoration on a timeline: B18 §5.3.3
    keeps a REFUSED request rather than deleting it *"because someone turned
    down for arrears at a previous address simply reapplies"*, and TC-REQ-10
    requires the refusal to still be readable after a reopen.

    The History tab mixes `Note` and `System` rows, newest first, each stamped
    date · time · actor, and `Add a note` is badged **`Internal · never shown to
    the customer`** — so `internal` defaults True and there is no path in this
    module that sets it False. A customer-visible note would need a portal to
    show it in, and there is none (the `AccountNote.customer_visible` lesson,
    same file).
    """

    KIND_STATE = "state"
    KIND_NOTE = "note"
    KIND_SYSTEM = "system"
    KINDS = (KIND_STATE, KIND_NOTE, KIND_SYSTEM)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="events",
    )
    at = models.DateTimeField()
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="actor_user_id",
    )
    kind = models.TextField(default=KIND_SYSTEM)
    from_state = models.TextField(null=True, blank=True)
    to_state = models.TextField(null=True, blank=True)
    note_type = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "service_request_events"
        indexes = [
            # The tab's own order: *"This request only · newest first"*.
            models.Index(fields=["tenant", "request", "-at"], name="ix_sr_events_newest"),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-030 W7 · DISCONNECTS — three models that live in `disconnects.py`
# ══════════════════════════════════════════════════════════════════════════
# `disconnect_cases` · `disconnect_notices` · `account_protections` are declared
# in `apps/customers/disconnects.py`, beside the ladder and the protection
# lifetimes that give them meaning — `apps/rating/models.py`'s precedent for
# `apps.rating.discounts`, and the same route `apps/metering/models.py` takes
# for the W6 connection models.
#
# ⚠ WITHOUT THIS LINE DJANGO PROPOSES TO DROP THE THREE TABLES. A model must be
# REGISTERED at startup for the autodetector to see it; migration state would
# hold three models the app registry lacks, and `makemigrations --check` answers
# that with `Delete model AccountProtection / DisconnectCase / DisconnectNotice`
# — measured on this tree before the line landed.
#
# ⚠ AND THE ALTERNATIVE WAS REJECTED FOR A REASON WORTH KEEPING. `managed=False`
# plus hand-written per-vendor DDL would move six load-bearing constraints — the
# three protection lifetimes, `ck_collections_sequence_never_cuts`, the two
# vocabularies and the one-open-case partial unique — into two SQL dialects
# nothing compares. Worse, `managed=False` makes the `CheckConstraint`
# declarations DECORATIVE, so the red proof that a payment-plan protection
# cannot carry an expiry would be asserting hand-written SQL rather than the
# declaration beside it. That is hard-won law 5 over a constraint deciding
# whether somebody's power stays on.
from apps.customers import disconnects  # noqa: E402,F401  (registers three models)

# ⚠ AND THE SAME LINE FOR `transfers`, FOR THE REASON ITS OWN MIGRATION ASKED
# FOR IT (DEF-801). `apps/customers/migrations/0021_cr030_w7_transfers.py`
# carries the DDL for `transfers` and NO model state, on the reading that
# Django never imports `transfers.py` at startup — so a `CreateModel` there
# would have left state holding a model the registry lacks. That reading
# stopped being true the moment an imported module imported it: today
# `config/urls.py` -> `apps/customers/api.py` -> `move_reads.py` does exactly
# that, so `makemigrations --check` saw a REGISTERED model with no state and
# answered `+ Create model Transfer` — red, on a check every lane report
# claims green. An accidental import is not a decision, so this line makes the
# registration DELIBERATE and `0027_transfer` gives it the state half.
# `managed = False` is unchanged, so that migration creates no table: the DDL
# is still 0021's and the introspection test still holds the two together.
from apps.customers import transfers  # noqa: E402,F401  (registers Transfer)

# CR-039 wave D task 18 — `MoveRecord` lives in `apps/customers/moves.py` for
# the reason `disconnects.py` gives for `DisconnectCase`: one flow, one module,
# with its rules in the docstring beside the columns they govern. Unlike
# `Transfer` above it is MANAGED, so this import is what registers it and
# `0030_cr039_wd_move_records` is an ordinary `CreateModel` — no raw DDL, no
# state-only migration, no introspection test to keep in step.
from apps.customers import moves  # noqa: E402,F401  (registers MoveRecord)

# CR-094-BRC01 wave I — `AccountDocument` lives in
# `apps/customers/account_document_models.py` for the reason `moves.py` gives
# for `MoveRecord`: one capability, one module, with its rules in the docstring
# beside the columns they govern. It is MANAGED, so this import is what
# registers it and `0042_cr094_i_account_documents` is an ordinary `CreateModel`.
from apps.customers import account_document_models  # noqa: E402,F401  (registers AccountDocument)

# CR-142-BRC07 `P0.18` (the Reports Build Brief §7.2.4, RULED option (b)) —
# `AccountAttributeHistory` lives in `apps/customers/attribute_history_models.py`
# for the same reason as the three above: one capability, one module, with its
# rules in the docstring beside the columns they govern. It is MANAGED, so this
# import is what registers it and `0072_cr142_p0_18_attribute_history` is an
# ordinary `CreateModel`; `0073` carries the B2 §3 RLS policy.
from apps.customers import attribute_history_models  # noqa: E402,F401  (registers AccountAttributeHistory)

# `BR-CUS-1047` (PO ruling 2026-09-12) — `AccountUnitCorrection` lives in
# `apps/customers/unit_correction_models.py` for the same reason as the three
# above: one capability, one module, with its rules in the docstring beside the
# columns they govern. MANAGED, so this import registers it and
# `0045_br_cus_1047_unit_correction` is an ordinary `CreateModel`.
from apps.customers import unit_correction_models  # noqa: E402,F401  (AccountUnitCorrection)

# `BR-CUS-1076` (`CR-094-BRC01` lane J) — `ServiceRequestMessage` lives in
# `apps/customers/applicant_message_models.py` for the same reason as the three
# above: one capability, one module, with its rules in the docstring beside the
# columns they govern. MANAGED, so this import registers it and
# `0051_br_cus_1076_service_request_messages` is an ordinary `CreateModel`.
from apps.customers import applicant_message_models  # noqa: E402,F401  (ServiceRequestMessage)

# `BR-CUS-1077` (PO ruling 2026-09-16, *"it should do B"*) — `MoveInJob` lives
# in `apps/customers/move_in_jobs.py` for the same reason as the four above: one
# capability, one module, with its rules in the docstring beside the columns
# they govern. MANAGED, so this import is what registers it and
# `0053_br_cus_1077_move_in_jobs` is an ordinary `CreateModel`.
from apps.customers import move_in_jobs  # noqa: E402,F401  (registers MoveInJob)

# `BR-CUS-1083` (PO ruling 2026-09-20, the four crew outcomes verbatim) —
# `DisconnectVisit` lives in `apps/customers/disconnect_visits.py` for the same
# reason as the five above: one capability, one module, with its rules in the
# docstring beside the columns they govern. MANAGED, so this import is what
# registers it and `0062_br_cus_1083_disconnect_visits` is an ordinary
# `CreateModel` plus its RLS policy.
from apps.customers import disconnect_visits  # noqa: E402,F401  (registers DisconnectVisit)

# CR-171-BRC10 `P1.01` (lane MVI-SCHEMA) — the move-in redesign's three new
# tables, each in its own module for the same reason as the six above.
# MANAGED, so these imports register them and `0080_cr171_p1_01_move_in_redesign`
# is ordinary `CreateModel`s plus their RLS policies.
from apps.customers import co_owner_models  # noqa: E402,F401  (registers AccountCoOwner)
from apps.customers import move_in_extras  # noqa: E402,F401  (MoveFeeLine, MoveExtraMessage)

# CR-181-BRC10 B2/B3 (lane REOPEN, 2026-10-13) — a move-in that reopened the
# returning customer's own account on this unit, and the balance choice.
# MANAGED; `0083_cr181_move_in_reopenings` creates it with its RLS policy.
from apps.customers import move_in_reopen_models  # noqa: E402,F401  (MoveInReopening)

# CR-183-BRC10 (lane TSTOP, 2026-10-14) — a temporary stop on an account: the
# portal ask's structured facts, the schedule, and the field visit tick.
# MANAGED; `0084_cr183_temporary_stops` creates it with its RLS policy.
from apps.customers import temporary_stop_models  # noqa: E402,F401  (TemporaryStop)

# CR-185-BRC10 (lane OWNER-D4D5, 2026-10-14) — a residue tied back to the owner,
# pending until the final bill that puts it in the books is issued. MANAGED;
# `0085_cr185_balance_tie_backs` creates it with its RLS policy.
from apps.customers import tie_back_models  # noqa: E402,F401  (BalanceTieBack)
from apps.customers import agreement_models  # noqa: E402,F401  (AgreementRequest, CR-190-BRC10)

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets EP-CUS-02@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice — tables, RLS policies, reference-data seeding seam only) · AMENDED 2026-08-11 by story-coder (US-CUS-019 account-import lane — customers · customer_accounts · account_import_batches · account_import_rows)
# checklist: A✔ B=deferred(table-half only — the service/API TCs land with the account-CRUD slice) C✔ D=deferred(no-API-half in this slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations + RLS are 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: see the lane report — ruff✔ black✔ migrate-from-empty✔ makemigrations --check✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: BR-CUS-017's PROPOSED-SCHEMA partial unique index is NOT built — its `WHERE status='active'` predicate is unwritable once r5 #20 makes status a lookup FK, and no substitute is invented (REPORTED, ledger row; RULED 2026-08-10 — OQ-092 closed option (a), service-layer enforcement only, so the absence is now permanent and pinned by test_us_cus_001_tc5__one_active_account_per_unit_has_no_database_half) · `service_agreements.tariff_id` NOT built (r16 #3 supersedes it) and `account_plan_assignments` NOT built (no DDL in any signed document) · `account_subtypes` ships with no parent-type FK — nothing states whether a sub-type belongs to a type (REPORTED) — RESOLVED 2026-08-18 (CR-010 lane): the PO answered the reported question on 2026-08-17 (*"add them"*, decision log "Part-10 confirmations"), so migration 0011 adds the nullable `account_type_id` parent FK, BR-CUS-067 records the ratified 12-row tree, and the handler requires a parent on new rows · `accounts.account_type_id` read as NOT NULL from B2's DDL convention in r5 #19 (READING REPORTED) · r9 #1/#2/#4/#6 and r5 #5 tables NOT built (PROPOSED-SCHEMA, no column list) · CORRECTED 2026-08-11 (custom-fields lane): this line said "r17.2 `custom_data` NOT built (r17 forbids DDL while OQ-075/076/077 are OPEN)" — all three OQs closed on 2026-08-10, the block lifted, and the four columns are BUILT in migration 0004; the stale claim was the one a reader would have trusted without checking · story-§5 PROPOSED-SCHEMA account columns NOT built (every owning story is `status: draft`) · [US-CUS-019 lane 2026-08-11] `customers` + `customer_accounts` BUILT from B2 r9 #1's own column list (kind, display_name, external_ref UNIQUE per tenant, N:M link) — the earlier "no column list in B2" claim was FALSE and is corrected in the docstring · `account_import_batches` + `account_import_rows` BUILT from US-CUS-019 §5 verbatim, PLUS the 🔒 DB-12 file+tags idempotency pair (`file_hash` + `tag_fingerprint`) which §5 does not list and CLAUDE.md rule 6 requires; the unique is scoped to COMMITTED batches for the same reason metering scopes its own to POSTED ones · `account_import_value_maps` (r9 #4's third table) NOT built — it belongs to US-CUS-020 · `account_opening_buckets` (r9 #2) NOT built — US-CUS-021 owns it; this lane PARSES and STAGES the four bucket columns and writes none of them · `contacts` still hang off `accounts`, not off the new customer row (r9 #1 flags the re-home as an Eng-Lead disposition)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
