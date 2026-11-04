# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001 (EP-TEN-03 §Provisioning) · US-TEN-002 (seeding) · US-TEN-005 /
#           US-TEN-006 (EP-TEN-05 company + regional/fiscal settings; EP-TEN-06
#           services/UoM columns ride the same tables per r6.4) ·
#           US-TEN-010 (EP-TEN-07 lookup table-half) ·
#           US-TEN-012 (EP-TEN-08 number series) · US-SHL-013 (user_preferences,
#           hosted here — platform-shell owns no Django app) · US-SHL-004 (bell
#           storage — Eng disposition, see below)   Screens: S8, S110–S114, S62
#           AMENDED 2026-08-09 (settings rule-page + reference-data gap lane):
#           US-TEN-009 (the S63–S71 rule-page documents + the two hosted
#           reference lists) · US-TEN-005 (logo bytes) · US-MET-011 (S64 field
#           set)   Screens += S64, S66, S69, S70, S71
# Rules:    BR-TEN-010/011 (subdomain law) · BR-TEN-012 (versioned fixture seeding) ·
#           BR-TEN-030 (codes unique per list per tenant, case-insensitive) ·
#           BR-TEN-035 (number-series storage: per-tenant counter, forward-only) ·
#           BR-TEN-036 (vocabularies = seeded lookup tables) · BR-TEN-039 (holiday
#           calendar card) · BR-SHL-024 (user_preferences constraints) · BR-SHL-026
#           (bell = 5-event attention feed) · BR-RAT-024 (10-service catalog) ·
#           BR-TEN-019 (logo bytes + content type) · BR-TEN-031 (hosting ≠ owning
#           for reason_codes/payment_methods) · BR-MET-020 · BR-BIL-021 ·
#           BR-BIL-017 · BR-PAY-017 · BR-PAY-019 (the five rule-page documents)
# Tests:    06-backend/tests/test_w0_models.py (constraint tests on the sqlite test DB;
#           AMENDED 2026-08-11 (tenant custom-fields lane): `custom_field` (B2
#           addendum r17.1, EP-TEN-09) + `tenant_settings.custom_field_version`.
#           Rules += BR-TEN-046 (tenant-defined data, never schema; RLS FORCE) ·
#           BR-TEN-048 (never influences money) · BR-TEN-050 (deactivate only) ·
#           BR-TEN-053 (the registry read + its version segment). The table's
#           four EP-TEN-09 STORIES are deliberately NOT cited: this ships the
#           table, not their test cases — see the CustomField docstring.
#           RLS assertions live in the G5 isolation suite — sqlite cannot exercise RLS)
# Impacts:  BE-01 tenant resolver · BE-06 number-series sink (US-TEN-012 lane) ·
#           BE-07 job store · BE-09 bell sink · every module FK-ing tenants/services
# ───────────────────────────────────────────────────────
"""tenancy models — tables owned per B2 r16 owner map (§6: number_series →
tenancy · services catalog → tenancy platform ref) plus the W0 platform tables
this module HOSTS by Eng disposition 2026-08-09 (recorded in the build report):

- `user_preferences` (platform-shell's only table, US-SHL-013) — shell has no
  Django app; tenancy is the platform module.
- `jobs` (BE-07 store) and `bell_events` (BE-09 sink) — owner-module
  assignment was queued as an Eng disposition (decision log 2026-08-09);
  hosted here for the same reason.
- `holiday_calendars` — B2 r16 #6 PM-proposes rating ownership; the W0
  migrations lane builds it with the Settings reference-data family (S63,
  BR-TEN-039). Flagged in the build report, not silently resolved.

Schema law implemented here (signed): B2 §2 tenancy DDL + addenda r5 #1/#3,
r6.0 (subscription_plans rename), r6.4 (UoM gate columns), r9 #5 (deposit
interest), r12 #15 (checklist_state, ein, lock_closed_periods), r15
(localization settings), r16 (10-service catalog replaces the service_type
enum; newest-wins). Monetary columns are NUMERIC(18,6) (DB-3). All PKs are
uuidv7-style (DB-2, app-side shim per O-1 residue).

RLS: every tenant-scoped table below gets ENABLE+FORCE via migration
0003_rls_w0_policies (SQL in 06-backend/db/rls_tenancy_w0.sql). Platform
tables (subscription_plans, services, tenants itself) are RLS-exempt per B2
§3 — `tenants` is filtered by membership at the app layer.
"""

from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.tenancy import settings_families
from core.crypto import EncryptedTextField  # BR-CUS-092(b) / OQ-016 — tenants.ein
from core.dbfields import CITextField, uuid7_pk


class SubscriptionPlan(models.Model):
    """PLATFORM SKU catalog (B2 `plans`, renamed subscription_plans per r6.0)."""

    id = uuid7_pk()
    code = models.TextField(unique=True)  # 'starter' | 'growth' | 'scale'
    name = models.TextField()
    price_month = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    currency = models.CharField(max_length=3, default="USD")
    min_accounts = models.IntegerField()
    max_accounts = models.IntegerField()  # commercial tier bound, NEVER enforced (B6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscription_plans"


class Service(models.Model):
    """PLATFORM 10-service catalog (r5 #1, BR-RAT-024) — replaces the
    service_type enum's role (r16 #3); seeded in migration 0001."""

    id = uuid7_pk()
    code = models.TextField(unique=True)  # 'electric' … 'battery'
    name = models.TextField()
    default_uom = models.TextField(null=True, blank=True)  # filled by US-TEN-007 lane
    color = models.TextField(null=True, blank=True)  # prototype service colors
    sort = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "services"


class Currency(models.Model):
    """The money a utility keeps its books in — `P0.6`, the lookup that was not
    there.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  WHAT WAS WRONG, MEASURED RATHER THAN ASSERTED                       ║
    ╚══════════════════════════════════════════════════════════════════════╝
    On 2026-09-24 this product held **39 free-text currency columns** —
    `invoices`, `payments`, `journal_entries`, `refunds`, `settlements`,
    `tariff_versions` and thirty-three more — every one a bare `CharField(3)`,
    and **no table anywhere said what a currency is**. The lawful set lived in
    a Python tuple in ONE module (`tenancy.services.SEED_CURRENCIES`), its
    symbols in a second constant in `apps/reports/dashboard_format.py`, and
    nothing linked a single stored value to either.

    ⚠ **THE FINANCE BLUEPRINT RECORDS 27 COLUMNS. THERE ARE 39**, counted from
    `information_schema` on 2026-09-24. The document was written before the
    settlement, counter and correction tables landed. The figure moved; the
    shape of the problem did not.

    **`OQ-031` ALREADY RULED THE SHAPE, SO THIS IS NOT A NEW DECISION**
    (CLOSED → `BR-TEN-036`, PO R6): *enums → lookup tables, seeded defaults,
    tenant-extensible*. Two of those three apply here and the third
    deliberately does not — see below.

    ════════════════════════════════════════════════════════════════════════
    PLATFORM-CURATED, NOT TENANT-EXTENSIBLE, AND THE REASON IS STRUCTURAL
    ════════════════════════════════════════════════════════════════════════
    `account_statuses`, `account_types` and the rest of `BR-TEN-036`'s family
    are tenant-scoped and extensible. **This one cannot be**, and not as a
    policy preference: `tenants.currency` references it, and `tenants` is the
    table every tenant-scoped row hangs off. A tenant-scoped `currencies` would
    have to exist before the tenant that scopes it.

    It is also the right answer on its own terms. ISO 4217 is not a vocabulary
    a utility extends — a made-up code would be accepted by the books, rendered
    as `1,234.56 XYZ` by every screen (`dashboard_format.CURRENCY_SYMBOLS`
    covers the seeded five and invents nothing for anything else), and settled
    by no bank. Adding a currency is a PLATFORM act, and `is_active` is how one
    is withdrawn without deleting a row the books already point at
    (`BR-TEN-036`: *a seeded row is deactivatable, never deletable*).

    ════════════════════════════════════════════════════════════════════════
    WHAT THIS CHANGES TODAY: NOTHING A USER CAN SEE, AND THAT IS DELIBERATE
    ════════════════════════════════════════════════════════════════════════
    The five seeded rows are **exactly** `SEED_CURRENCIES`' five, and
    `SEED_CURRENCIES` is now DERIVED from this table rather than typed beside
    it — so there is one vocabulary where there were two that could disagree.

    ⚠ **`P0.8`'s OUTCOME — *"a tenant cannot type `US$`"* — WAS ALREADY TRUE
    BEFORE THIS TABLE EXISTED**, and saying so is more useful than claiming
    credit for it: `services.provision_tenant` and
    `services.save_regional_settings` have both refused an unknown code for
    weeks. The blueprint's `EXISTS, WEAK` is right about the COLUMN and not
    about the behaviour. What was actually missing is that the refusal was a
    hardcoded tuple inside one module rather than a fact the database holds and
    every module can read — which is what `P0.6` asks for and what this is.

    `minor_units` is carried because rounding is a per-currency fact — JPY has
    none, most have two — and `CLAUDE.md` rule 2 rounds at display. **Nothing
    reads it yet.** It is here because adding a column later to a table the
    books reference is a migration, and because a lane that needs it should
    find it rather than hardcode a 2.
    """

    #: **THE CODE IS THE KEY**, not a surrogate uuid, and that is what makes
    #: this table usable at all: 39 columns already hold a `CHAR(3)` code, and
    #: a uuid key would have required every one of them to be rewritten before
    #: a single one could reference anything.
    code = models.CharField(max_length=3, primary_key=True)
    name = models.TextField()
    #: The symbol a screen shows, transcribed from `Intl.NumberFormat` so the
    #: server's string and the client's string are the same string — which is
    #: `apps/reports/dashboard_format.CURRENCY_SYMBOLS`' own reasoning.
    symbol = models.TextField()
    #: Digits after the point for DISPLAY. Two everywhere this platform sells
    #: today; stored per row because it is a property of the currency and not
    #: of the product.
    minor_units = models.IntegerField(default=2)
    #: `BR-TEN-036` — a seeded row is deactivatable, never deletable. A
    #: currency the books already reference cannot be removed (the foreign keys
    #: refuse it), so withdrawing one is a flag rather than a DELETE.
    is_active = models.BooleanField(default=True)
    sort = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "currencies"
        ordering = ("sort", "code")

    def __str__(self) -> str:  # pragma: no cover — admin/debug convenience
        return self.code


class Tenant(models.Model):
    """PLATFORM root (B2 §tenancy) + the Company-profile columns (US-TEN-005
    field map) + r12 #15 residuals (checklist_state, ein)."""

    id = uuid7_pk()
    name = models.TextField()
    subdomain = models.TextField(unique=True)  # BR-TEN-011; BE-01 resolves on this
    state = models.TextField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")  # BR-TEN-021 forward-only
    tax_region = models.TextField(null=True, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)  # US-TEN-001, set once
    checklist_state = models.JSONField(null=True, blank=True)  # S62 mark-done/dismiss (r12 #15)
    # Company profile (US-TEN-005; all optional until the S62 checklist drives fill-in)
    legal_name = models.TextField(null=True, blank=True)
    dba_name = models.TextField(null=True, blank=True)
    # ⚠ THIS LINE SAID "PII — app-layer encrypted (OQ-016, r12 #15)" ON A PLAIN
    # TextField UNTIL 2026-08-24, AND IT WAS A COMMENT CLAIMING A GUARANTEE THAT
    # DID NOT EXIST (hard-won law 1). Nine plain digits sat here against a CLOSED
    # ruling for the life of the product; `services.py` said so in prose and no
    # test asserted it. BR-CUS-092(b) makes this the SECOND CALLER of the
    # encryptor OQ-016 required — "a helper with one caller is exactly how the
    # first one was skipped" — and the claim is now the field class, not a note.
    # The column type is unchanged (text); only what is written into it changed.
    # Display is UNTOUCHED: BR-TEN-018 still shows the EIN NN-NNNNNNN in full on
    # the S8 company tab, and BR-AUD-006 still masks it into the audit trail.
    # Guarded by tests/test_br_cus_092_ein_encryption.py.
    ein = EncryptedTextField(crypto_context="tenants.ein", null=True, blank=True)
    state_utility_id = models.TextField(null=True, blank=True)
    mailing_address = models.TextField(null=True, blank=True)
    support_phone = models.TextField(null=True, blank=True)
    support_email = CITextField(null=True, blank=True)
    website = models.TextField(null=True, blank=True)
    logo_file_id = models.TextField(null=True, blank=True)  # object-store ref (BR-TEN-019)
    # BR-TEN-019 upload storage. No document-storage kernel exists in core/ (no
    # object store, no signed-URL contract), so the sanitized bytes live on the
    # row and `logo_file_id` carries their content reference `sha256:<hex>`.
    # Swapping to an object store later changes these two columns and nothing
    # else — the reference column is already the one US-TEN-005 §5 named.
    logo_content_type = models.TextField(null=True, blank=True)  # image/svg+xml | image/png
    logo_bytes = models.BinaryField(null=True, blank=True)  # sanitized (apps/tenancy/logo.py)
    brand_primary_hex = models.CharField(max_length=7, null=True, blank=True)
    brand_accent_hex = models.CharField(max_length=7, null=True, blank=True)
    #: `CR-199-BRC10` S5 (PO 2026-10-29, ruling 1A: the logo link is set ONCE
    #: per utility in Settings › Company › Branding). Where the logo in every
    #: customer email's header points. `https://` only — validated in
    #: `services._validate_company_changes`; NULL means the logo links nowhere.
    brand_logo_link_url = models.TextField(null=True, blank=True)
    remit_to_address = models.TextField(null=True, blank=True)
    remit_payable_to = models.TextField(null=True, blank=True)
    service_hours = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenants"


#: CR-060 C7 / task T2 — WHAT KIND OF ORGANISATION THIS TENANT IS.
#:
#: The product serves three (BR-LED-028, PO verbatim 2026-08-12: *"help Utility,
#: Sub metering copany or HOA reconcile both sides as system of record"*) and
#: until 2026-09-01 it could not tell them apart — *"HOA"* existed in the
#: database only as a premises OWNER category, which describes who owns a
#: building and not who is running the software. So every tenant got the
#: utility's screen, and the one figure a sub-metering company exists to watch
#: was computed at a grain that is useless to it.
#:
#: **NO CHECK CONSTRAINT, and the choice follows this table's own precedent**
#: (`accounting_method`, `close_cadence`, `first_day_of_week`, `number_format`
#: — every one a TEXT column validated in the service against a tuple here).
#: A reader falls back rather than erroring on an unknown value
#: (`selectors.organisation_type`), which is CR-060 C8's stated proof.
ORGANISATION_TYPE_UTILITY = "utility"
ORGANISATION_TYPE_SUB_METERING = "sub_metering"
ORGANISATION_TYPE_HOA = "hoa"
ORGANISATION_TYPES = (
    ORGANISATION_TYPE_UTILITY,
    ORGANISATION_TYPE_SUB_METERING,
    ORGANISATION_TYPE_HOA,
)


class TenantSettings(models.Model):
    """1:1 regional/fiscal settings row (US-TEN-006 field map + B2 header
    late-fee settings + r9 #5 + r12 #15 + r15). Nullable until each S8 tab
    save fills its fields — enforcement stories carry the semantics."""

    id = uuid7_pk()
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    country = models.TextField(null=True, blank=True)
    timezone = models.TextField(null=True, blank=True)  # IANA name
    language = models.TextField(null=True, blank=True)  # BCP-47 (r15 default_language)
    first_day_of_week = models.TextField(null=True, blank=True)  # 'sunday' | 'monday'
    number_format = models.TextField(null=True, blank=True)
    date_format = models.TextField(null=True, blank=True)
    time_format = models.TextField(null=True, blank=True)
    fy_start_month = models.IntegerField(null=True, blank=True)
    fy_start_day = models.IntegerField(null=True, blank=True)
    accounting_method = models.TextField(null=True, blank=True)  # 'accrual' | 'cash'
    #: CR-060 C7 · BR-TEN-1050. **SEEDED `utility`, NEVER NULL**, and the
    #: not-null default is the whole of C7's *"every existing tenant gets a
    #: correct default"*: an `AddField` carrying a default backfills every row
    #: that already exists, so no tenant is ever in an unknown state and nobody
    #: has to open a tab to leave one. It follows the precedent ratified by
    #: CR-010 ruling 7 for the eleven regional fields that sat NULL until a
    #: human opened Settings. The three values are `ORGANISATION_TYPES` above.
    organisation_type = models.TextField(default=ORGANISATION_TYPE_UTILITY)
    close_cadence = models.TextField(null=True, blank=True)  # 'monthly' | 'quarterly'
    close_day = models.TextField(null=True, blank=True)
    lock_closed_periods = models.BooleanField(default=False)  # BR-TEN-038 enforcement = ledger
    late_grace_mode = models.TextField(null=True, blank=True)  # 'calendar' | 'business' (B2 hdr)
    late_grace_days = models.IntegerField(null=True, blank=True)
    deposit_interest_rate_annual = models.DecimalField(  # r9 #5 (S66), DB-3
        max_digits=18, decimal_places=6, default=Decimal("0")
    )
    # ── S64/S66/S69/S70/S71 rule-page documents (11b §2.3) ──────────────────
    # One jsonb document per Settings rule page, born holding that family's
    # ratified seeded defaults so the DATABASE — never a code constant — is
    # what an engine reads (BR-MET-020's config-over-constant law). The field
    # law (which parameters exist, their defaults, their bounds, and the rule
    # behind each) lives in apps/tenancy/settings_families.py; three S66
    # parameters deliberately stay in the typed columns above rather than
    # being duplicated here (late_grace_mode/days, deposit_interest_rate_annual).
    read_validation = models.JSONField(  # S64 — BR-MET-020/025/026/027/052
        default=settings_families.default_read_validation, blank=True
    )
    billing_defaults = models.JSONField(  # S66 — BR-BIL-001/021/029, BR-PAY-010
        default=settings_families.default_billing_defaults, blank=True
    )
    budget_billing = models.JSONField(  # S69 — BR-BIL-017
        default=settings_families.default_budget_billing, blank=True
    )
    collections = models.JSONField(  # S70 — BR-PAY-013/016/017/018
        default=settings_families.default_collections, blank=True
    )
    finance_controls = models.JSONField(  # S71 — BR-PAY-019, BR-BIL-013/014/018, BR-REP-022
        default=settings_families.default_finance_controls, blank=True
    )
    #: `S8` → Configure → Reference data → REPORTS (`CR-142-BRC07` `P4.6`).
    #: The PLATFORM EXPORT KERNEL's two tenant-settable facts — how long a
    #: generated file is kept and what a download is unless the clerk asks
    #: otherwise (BR-REP-018 / IS-11). Tenancy's, because the kernel is:
    #: `exports.ARTIFACT_RETENTION_DAYS` is what every list export in this
    #: product is kept for, reports' among them and not only reports'.
    reports = models.JSONField(  # S8 · REPORTS section — BR-REP-018
        default=settings_families.default_reports, blank=True
    )
    #: `S8` → Configure → Reference data → ACCOUNTS → Service requests
    #: (`DEF-CUS-10445`, PO 2026-10-22 *"Default 15 days"*). How many WORKING
    #: days after the request date the acknowledgement aims at when the customer
    #: gave no preferred date, and how far ahead a new request's Connection date
    #: opens. Seeded 15 by the family's own default.
    service_requests = models.JSONField(  # S8 · ACCOUNTS section — BR-CUS-079
        default=settings_families.default_service_requests, blank=True
    )
    #: B2 r17.1 — the custom-field registry's cache-key version segment
    #: (BR-TEN-053), bumped in the SAME TRANSACTION as any `custom_field` write
    #: so a new key supersedes the old one and there is no delete fan-out to get
    #: wrong. ⚠ NOTHING BUMPS IT YET: the definition-write service is US-TEN-015
    #: /US-TEN-017 in this module's own lane, and the invoice stamp reads
    #: Postgres directly rather than the cache. The column lands with the table
    #: because the bump must be in the same transaction as the write, and adding
    #: it after that service exists would make the first version of it wrong.
    custom_field_version = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_settings"


class Subscription(models.Model):
    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, db_column="plan_id")
    status = models.TextField(default="trial")  # value set = O-9 closure (B10)
    trial_ends_at = models.DateTimeField(null=True, blank=True)  # +14d (BR-TEN-014)
    started_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"


# ══════════════════════════════════════════════════════════════════════════
# CR-039 WAVE F — THE COMMERCIAL MODEL, PLATFORM SIDE
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERYTHING IN THIS BLOCK IS WHAT A UTILITY PAYS BYNRY. IT IS A DIFFERENT
# CLASS OF MONEY FROM WHAT A UTILITY'S CUSTOMERS PAY THEM**, and CR-039 task 27
# is that sentence made structural: none of it may appear in Billing, Payments,
# Finance or Reports, and it carries its own numbering. `Subscription` and
# `SubscriptionPlan` above are already on this side of the line; these three
# join them.
#
# **The model, from the PO's own words (2026-08-26):** *"we have 2 or 3 busines
# smodel - 1 we have self serve, 6 months, 9 months, 12 months and custom
# implementation plan, then we have subscrption plan - currently we ahve
# $1000,$5000,$8000 plan and then we have add-on"*. The subscription plans have
# been built and seeded since `0005`; these are the other two thirds, which sat
# unbuilt because three questions in that sentence were open. **All three were
# ruled on 2026-08-27** — see the decision log — and each ruling is quoted at
# the field it decides.


class ImplementationOrder(models.Model):
    """What a utility buys to get set up — CR-039 task 25.

    ⚠ **THE 6/9/12 IS A DURATION, NOT A CONTRACT TERM (PO 2026-08-27,
    verbatim: *"it is duration of implmentation project"*).** Wave F task 24 was
    written as *"Term on the subscription"*, which put the number on
    `subscriptions` and implied a renewal, a commitment discount and an
    end-of-term event. It belongs HERE instead: how long the project takes, not
    how long the customer is tied in. **Nothing about the subscription changed.**

    ⚠ **AND THAT LEAVES A QUESTION THIS MODEL DELIBERATELY DOES NOT ANSWER:**
    if 6/9/12 is not a contract term, **nothing in the product states how long a
    subscription runs for** — the plans are month-to-month by omission. That may
    be exactly right for a self-serve SaaS. It was not ruled, so no column here
    pretends it was.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    #: The platform-side reference a person quotes — `IMPL-26-0001`. Its own
    #: series, on its own side of the boundary (task 27), and NOT one of the
    #: twenty-six tenant series in `core/numbering.py`: a tenant's own
    #: numbering is the tenant's to configure, and this number is Bynry's.
    order_no = models.TextField(null=True, blank=True)

    #: ❄️ **ZERO IS SELF-SERVE, AND IT IS A ROW RATHER THAN AN ABSENCE.**
    #: PO 2026-08-27, verbatim: *"when utility will do cofiguration, data
    #: migrton by themself then it is self serve and we dont have to implment it
    #: - how you want to handle it, youc anhave 0 month implmentaiton"*. The
    #: MODELLING was delegated and the build chose the row, for one reason: a
    #: row and no row are different things to a report. With a zero-month row,
    #: *"how many customers are self-serve?"* is one query and the answer is a
    #: fact; with no row, self-serve is indistinguishable from
    #: implementation-not-yet-scoped, and a sales report cannot tell a customer
    #: who needs nothing from a customer nobody has looked at.
    #:
    #: 0 · 6 · 9 · 12 are the PO's four; `custom` is expressed as any other
    #: positive number rather than as a fifth enum, because *"custom"* is a
    #: length nobody has named yet and a CHECK that refused 8 would refuse a
    #: real engagement.
    duration_months = models.IntegerField(default=0)

    #: Priced per engagement (PO 2026-08-26: *"custom implementation plan"*).
    #: 4 decimals stored, 2 displayed — CLAUDE.md hard rule 2, the same as every
    #: other money column in this product.
    price = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="USD")

    #: **100% upfront, or at most TWO instalments** — typically kickoff and
    #: go-live. Already ruled; milestone-split schedules were dropped, and
    #: kickoff is trial conversion. The CHECK lives in the migration so the
    #: database refuses a three-instalment order rather than trusting a caller.
    instalments = models.IntegerField(default=1)

    status = models.TextField(default="draft")  # draft · agreed · in_progress · delivered
    started_on = models.DateField(null=True, blank=True)
    delivered_on = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "implementation_orders"
        constraints = [
            # Ruled, not invented: 100% upfront, or at most TWO instalments —
            # typically kickoff and go-live. Milestone-split schedules were
            # dropped. In the DATABASE rather than in a serializer because it is
            # a rule about money, and a caller that bypasses the serializer is
            # exactly who it needs to refuse.
            models.CheckConstraint(
                check=Q(instalments__in=(1, 2)),
                name="implementation_orders_instalments_ck",
            ),
            # Zero is meaningful — it is self-serve, the PO's own case — and a
            # negative duration is a data error with no reading.
            models.CheckConstraint(
                check=Q(duration_months__gte=0),
                name="implementation_orders_duration_ck",
            ),
            # CR-039 wave F task 27 (tenancy 0025). UNIQUE ACROSS THE PLATFORM,
            # not per tenant: `transfers.transfer_no` is the TENANT's number and
            # two utilities may both hold a `TRF-26-0001`; this one is Bynry's,
            # there is one Bynry, and two implementation orders may never share
            # a reference. Partial, because NULL was lawful for every row `0021`
            # could have created and several NULLs are not a collision.
            models.UniqueConstraint(
                fields=["order_no"],
                condition=Q(order_no__isnull=False),
                name="uq_implementation_orders_order_no",
            ),
        ]

    @property
    def is_self_serve(self) -> bool:
        """The PO's own word for a zero-month order, answered from the DATA.

        A named property rather than a stored flag: two places that can each say
        whether an order is self-serve is two places that can disagree, and the
        duration already carries the fact.
        """
        return self.duration_months == 0


class PlatformNumberSeries(models.Model):
    """BYNRY'S OWN COUNTER — the high-water mark for `IMPL-26-0001` and its kin.

    ⚠ **IT EXISTS BECAUSE `implementation_orders` GAINED A ROW-LEVEL SECURITY
    POLICY (DEF-TEN-4446, tenancy `0042`), AND THE OLD ALLOCATOR CANNOT SURVIVE
    THAT.** Until 2026-09-07 the next implementation-order number was derived by
    scanning every row of `implementation_orders` across every tenant — which is
    the right answer while the table is readable across tenants and is the wrong
    one the moment it is not. With the policy on, that scan runs inside the
    signing-up tenant's own context and sees only that tenant's rows, which for
    a brand-new tenant is **none**: every signup would propose `IMPL-26-0001`,
    collide with the unique index, retry three times and fail. So the count
    moved off the rows and onto a row of its own.

    ⚠ **THIS TABLE HAS NO `tenant_id`, AND THAT IS THE WHOLE POINT.** It is not
    RLS-exempt by exception, it is platform data by construction: there is one
    Bynry and one series, and no tenant has an opinion about what the next
    number is. B2 §3's "No RLS (platform)" list names it beside `plans` and
    `tenants` for exactly that reason, and the G5 sweep — which asks for a
    policy on every table that HAS a `tenant_id` — never sees it at all.

    ⚠ **AND IT IS NOT `number_series`.** That table is the TENANT's: one row per
    tenant per document type, a format the utility edits on Settings → Numbering,
    and BR-TEN-035's gapless promise for documents a regulator may audit. This
    one is Bynry's sales counter. The two must never be merged, because merging
    them would let a utility rename or reset the reference on its own contract.

    WHAT REPLACED WHAT, AND WHAT IT COST
    ------------------------------------
    `platform_numbering.py` argued against a counter table in 2026-08-27 on two
    grounds, and only one of them still holds:

    * *"it can drift from the rows it counts. Deriving cannot: the answer IS the
      data."* — **TRUE, and now unavoidable.** The unique index on `order_no`
      remains, and the allocator still retries on collision, so a counter that
      drifts LOW is corrected by the next allocation rather than by a person.
    * *"a counter table is one more platform table and one more thing to seed"*
      — the seed is a data migration beside the schema, and it runs BEFORE the
      policy lands so it can still read every row.

    Gaps: there are none. The counter is bumped inside the caller's transaction,
    so a signup that rolls back returns its number. That is stricter than the
    module promises (a sales reference has never claimed to be gapless) and it
    falls out of the design rather than being paid for.
    """

    id = uuid7_pk()

    #: `implementation_order` today, and the only one. A column rather than a
    #: second table per series, so Bynry's next platform number — a quote, a
    #: renewal — is a row and not a migration.
    series = models.TextField()

    #: The CALENDAR year the number belongs to, four digits. It is the year of
    #: the date the CALLER named, never a clock read here: a signup at 23:59 on
    #: 31 December belongs to the year it happened in (BR-TEN-043).
    year = models.IntegerField()

    #: The number the NEXT allocation will take — so a fresh year starts at 1
    #: and `IMPL-26-0001` is the first order of 2026. Stored as "next" rather
    #: than "last issued" so that seeding a new row and reading it are the same
    #: statement, with no empty-series special case to get wrong.
    next_sequence = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_number_series"
        constraints = [
            # One counter per series per year. It is what makes the lazy
            # `ON CONFLICT DO NOTHING` seed in `platform_numbering.py` safe:
            # two signups racing to open a new year produce one row, no
            # exception, and therefore no aborted PostgreSQL transaction
            # (CLAUDE.md hard-won law 14).
            models.UniqueConstraint(
                fields=["series", "year"],
                name="uq_platform_number_series_series_year",
            ),
        ]


class Addon(models.Model):
    """The platform's add-on CATALOGUE — CR-039 task 26.

    ⚠ **SEEDED EMPTY, ON PURPOSE, AND THAT IS THE HONEST STATE.** The PO
    established on 2026-08-26 that add-ons exist — *"and then we have add-on"* —
    and **named none**. Asked to name and price one on 2026-08-27 they gave the
    price and not the name: *"we will add price latet currently you default it
    to $1"*. So the table and the default ship and **no row is planted**:
    inventing a product's name is the same class of error as inventing its
    price, which is what stopped this being built for a fortnight.
    """

    id = uuid7_pk()
    code = models.TextField(unique=True)
    name = models.TextField()

    #: ⚠ **$1.00 IS A PLACEHOLDER THE PO CHOSE, NOT A RATIFIED PRICE.**
    #: PO 2026-08-27, verbatim: *"we will add price latet currently you default
    #: it to $1"*. That closes the objection that blocked this table — *"an
    #: add-on with an invented price is invented money"* — and it closes it the
    #: only way it could be closed: the figure now comes from the PO rather than
    #: from a builder. **But a $1.00 reaching an invoice while looking like a
    #: considered price is worse than no add-on at all**, so `priced` below
    #: exists to say which it is, and the screen marks an unpriced add-on as
    #: awaiting its figure.
    price_month = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("1.0000")
    )
    currency = models.CharField(max_length=3, default="USD")

    #: FALSE until somebody sets a real price. The product can then say *"not
    #: yet priced"* instead of showing a dollar that means nothing — the
    #: honest-absence posture used everywhere else in this product.
    priced = models.BooleanField(default=False)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "addons"


class TenantAddon(models.Model):
    """One add-on a tenant actually has — CR-039 task 26's second half.

    A row of its own rather than a column on `subscriptions`, which is the
    shape the design already pointed at: an add-on can be taken or dropped
    mid-term without rewriting the plan, and an invoice can show what was
    actually bought.

    `price_month` is NULLABLE and null means *whatever the catalogue says
    today*. A tenant that negotiated its own figure carries it; one that did not
    follows the catalogue, and a catalogue price change reaches it. Copying the
    catalogue price onto every row at sign-up would freeze a placeholder $1.00
    onto real customers the moment a real price replaced it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    addon = models.ForeignKey(Addon, on_delete=models.PROTECT, db_column="addon_id")
    price_month = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_addons"


class Uom(models.Model):
    """Tenant UoM vocabulary (US-TEN-002/010 field map; BR-TEN-036 lookup
    shape: code · name · is_system · active) + the CR-004 utility-service scope.

    ── `service` — THE UTILITY-SERVICE SCOPE (CR-004 task A3 / DEF-184) ───────
    PO ruling 2026-08-16, verbatim: *"it's a real field - every entry can be
    scoped to one service or all - I added it in Unit of measure since unit of
    measure is for speific service; so when we select service we have specific
    unit of measure available; currently it is not as per utility service"*.

    **NULL means "All services"**, and NULL is the default — the capability is
    PER-LIST and OPT-IN, and units of measure is the ONLY list switched on.
    Nine lists are CONFIRMED unscoped by the PO (payment methods, reason codes,
    account types, account statuses, premise & unit types, holiday calendar,
    custom fields, occupancy statuses, charge codes) and eight more are unruled
    and therefore unscoped by default — so no other model here gains this
    column. Turning scoping ON for a list later is a one-line registry change;
    turning it OFF after tenants have entered scoped data is a migration, which
    is the asymmetry the PO's sequencing was ruled on.

    **WHY THE FK POINTS AT THE PLATFORM `services` CATALOG AND NOT AT
    `tenant_services`.** The thing a unit belongs to is the SERVICE — kWh is
    electric's unit for every tenant alive — not one tenant's enablement row,
    which comes and goes as staff switch a service off. `services` is
    RLS-EXEMPT platform reference data (B2 §3), so the FK leaks nothing: the
    ROW is still gated by `uoms_tenant_isolation`, and the value it holds is
    catalog vocabulary every tenant already reads. The tenant half of the rule
    is enforced where it belongs, in validation: `UomLookupHandler` refuses a
    service this tenant has not ENABLED (BR-TEN-026), so a water-only co-op
    cannot scope a unit to a service it does not sell.

    `on_delete=PROTECT` because the catalog is closed (BR-TEN-025) and a
    service is never deleted; PROTECT states that rather than trusting it.

    DEF-184 is what this column closes: before it, `uoms` carried
    `code · name · is_system · active` and nothing else, so a WATER service
    could be assigned `therm` on SET-03 and nothing refused it — while
    `SERVICE_DEFAULT_UOMS` had been seeding electric kWh/kW, water kgal/ccf,
    gas therm/ccf since US-TEN-007. The product built the service-aware half of
    its own idea; this is the other half.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    #: CR-004 / DEF-184 — NULL = "All services" (see the class docstring).
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
        related_name="uoms",
    )
    is_system = models.BooleanField(default=False)  # seeded rows (BR-TEN-036)
    active = models.BooleanField(default=True)  # deactivation, not deletion (BR-TEN-034)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "uoms"
        constraints = [
            # BR-TEN-030 / US-TEN-010 TC-4: case-insensitive duplicate rejected.
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_uoms_tenant_code_ci"
            ),
        ]


class ReasonCode(models.Model):
    """S8 Reference-data list `reason_codes` (BR-TEN-036 shape: code · name ·
    is_system · active), HOSTED here by the same Eng disposition that hosts
    user_preferences/jobs/bell_events: BR-TEN-031 names BILLING as the content
    owner, but apps/billing has no tables and is another lane's territory, so
    the card had a declared list, a seeded fixture, and nowhere to put a row.
    Hosting ≠ owning — when the billing lane lands, it registers its handler
    through services.register_lookup_handler and re-homes this table in one
    migration; the card keeps naming billing as its owner throughout.

    ⚠ **`default_gl_account_id` LANDED 2026-08-17 (CR-008 ruling 9).** This
    docstring used to say it was *"deliberately absent … no ledger table
    exists"*, and that stopped being true the day `apps/ledger` seeded twenty-
    four accounts — an absence claim that outlives the absence is hard-won law
    1 in its most dangerous direction (a reader checking whether the column
    exists is sent away).

    The PO asked for adjustment reasons to map to GL accounts and ruled *"make
    it separate"* — its own section on Settings → Accounting → GL mapping — so
    a *billing error* credit and a *goodwill* credit can post to different
    accounts. It is a DEFERRED-FK uuid (B11 F-3), exactly as
    `rating.taxes.liability_gl_account_id` and `rating.charges.gl_account_id`
    are: the row is the LEDGER's, so the ledger validates ownership and
    liveness through `seams.ledger_account_is_live`, and no cross-module FK
    constraint is minted here (B2 §2 — the reviewed interface set is not a
    thing a lane extends on its own)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    #: US-TEN-010 §5 · CR-008 ruling 9. NULL = unmapped, which is a real state:
    #: an adjustment on an unmapped reason posts to the designation the
    #: correction path already resolves, and nothing here changes that today.
    default_gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger
    is_system = models.BooleanField(default=False)  # seeded rows (BR-TEN-036)
    active = models.BooleanField(default=True)  # deactivation, not deletion (BR-TEN-034)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reason_codes"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_reason_codes_tenant_code_ci"
            ),
        ]


# ── CR-004: the six r10 SET-04 reference lists that had no table ────────────
#
# All six are HOSTED here and owned elsewhere, exactly as ReasonCode and
# PaymentMethod are: BR-TEN-031 puts content and validation in the owning
# module, but apps/metering and apps/assets author no lookup CRUD, so each list
# had a design, a vocabulary and nowhere to put a row. Hosting is not owning —
# when the owning lane lands it registers its handler through
# services.register_lookup_handler and re-homes the table in one migration, and
# the card names the true owner throughout.
#
# Every one is the BR-TEN-036 flat shape (code · name · is_system · active) and
# is driven by HostedFlatLookupHandler, so none of them adds a new pattern.
#
# DELIBERATELY ABSENT, and this is the same restraint ReasonCode shows above:
# none of these carries the extra column r10's card text hints at. Meter size
# classes shows "Water 5/8" · base $12.00" — a BASE CHARGE, which is money and
# belongs to a B4-governed screen, not to a settings lookup; a numeric column
# here would be an invented rating input. Certification types shows "3-yr
# validity" and areas shows "3 sub-areas": a validity period and a parent-child
# hierarchy are both real shapes, and neither is specified anywhere yet. The
# vocabulary lands now; the shapes land when they are ruled.


class Area(models.Model):
    """S8 Reference-data list `areas` — districts and routes premises are
    grouped by (r10 SET-04). Content owner is metering (premises).

    ⚠ `parent` IS THE ONE COLUMN THE BLOCK COMMENT ABOVE SAYS MUST NOT EXIST,
    AND THE COMMENT IS NOW OUT OF DATE RATHER THAN WRONG (BR-MET-066b).
    CR-004 shipped this list flat and recorded why: *"a validity period and a
    parent-child hierarchy are both real shapes, and neither is specified
    anywhere yet."* On 2026-08-16 the PO specified it — *"user can define their
    own areas and we wil tag them to premises ; in CR06 you can use area and
    sub area for filtering"* — so the shape stopped being an invention and
    became a requirement. The restraint was right and so is lifting it; both
    are recorded because a later lane will otherwise read the comment above,
    conclude this column was smuggled in, and delete it.

    **A row with no parent IS an area. A row with a parent IS a sub-area.**
    One list, one column, exactly two levels: `services.py` refuses a
    grandparent and refuses a cycle, because r10's card is titled *"Areas &
    sub-areas"* and nothing in the corpus describes a third level. Depth is
    enforced in the service and NOT by a constraint — SQL cannot express
    "a parent must itself have no parent" without a trigger, and a trigger
    would be a second place the rule lives.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    #: BR-MET-066b — NULL = a top-level area; set = a sub-area of that row.
    #: PROTECT, not CASCADE: deleting an area that has sub-areas must refuse
    #: and say so, never silently take three children with it.
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="parent_id",
        related_name="sub_areas",
    )
    is_system = models.BooleanField(default=False)  # seeded rows (BR-TEN-036)
    active = models.BooleanField(default=True)  # deactivation, not deletion (BR-TEN-034)
    #: CR-161-BRC10 W4 — the utility's OWN fields on an area (PO 2026-10-02,
    #: Part 2 row 13: *"Add / edit area · Area page"*). Typed on the Areas card's
    #: add/edit dialog and validated by `custom_fields.validate_custom_data` with
    #: `screen="AREA_FORM"`. Captured and shown only (BR-TEN-048). `tenancy/0057`.
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "areas"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_areas_tenant_code_ci"
            ),
        ]


class MeterSizeClass(models.Model):
    """S8 Reference-data list `service_size_classes` — 5/8"–4" water, 1φ/3φ
    electric, gas classes, carts, and since CR-063 fire lines (r10 SET-04).
    Content owner is metering. The TABLE keeps the old name (DEF-970); the LIST
    was renamed by the PO on 2026-08-27 (BR-TEN-170).

    NO base-charge column: see the block comment above. r10 renders a price on
    this card and a price is B4-governed money.

    ── `service` — THE UTILITY-SERVICE TAG (CR-065, PO ruling 2026-09-02) ─────
    **THIS COLUMN REVERSES A RULING THE PRODUCT OWNER CONFIRMED TWICE, AND THE
    REVERSAL IS THEIRS.** `BR-TEN-078` named this list among the UNSCOPED on the
    PO's own words of 2026-08-16 — *"I have clariffied - already - dont attached
    them to service"* — and it was put to them twice, deliberately, because size
    classes read as the strongest candidate for scoping. On 2026-09-02 they
    ruled the opposite for the same list, with a screenshot of the Fire rate
    schedule pricing *Electric CT-metered*:

        "This is where we are setting rates for fire  you should show only
         capacity for fire . in Setting a capacity needs to tags to utility
         services ."

    The supersession is written into `BR-TEN-078`, `BR-TEN-170` and the decision
    log, dated. **It is ONE LIST WIDE:** every other list `BR-TEN-078` names is
    still unscoped, and `uoms` is no longer the only scoped one — it is the
    first of two.

    **NULL MEANS "NOBODY HAS SAID", AND THAT ROW LISTS ON EVERY SERVICE.** It is
    not "unconfigured" and nothing fills it in behind a tenant's back:
    `BR-TEN-071` forbids deleting a tenant's own row, so a size class a tenant
    added before today keeps its blank tag and keeps working exactly as it did.
    The offer rule is `uoms`' rule, unchanged and stated once in
    `selectors.service_scope_filter`: **scoped to THIS service, plus everything
    scoped to none.**

    **THE FK POINTS AT THE PLATFORM `services` CATALOG, NOT AT
    `tenant_services`** — the same choice, for the same reason, that `Uom.service`
    documents at length: a 2" fire line is fire's size for every tenant alive,
    not one tenant's enablement row. `services` is RLS-exempt platform reference
    data (B2 §3), so the FK leaks nothing; the ROW is still gated by
    `meter_size_classes_tenant_isolation`, and the tenant half of the rule is
    enforced in validation, where `ServiceScopeLookupMixin` refuses a service
    this tenant has not ENABLED (BR-TEN-026).

    ⚠ **THE SEED IS THE ONE PATH THAT TAGS WITHOUT ASKING ABOUT ENABLEMENT**, and
    deliberately: the platform fixture states what a size IS, and a tenant that
    has not switched fire on still receives fire's six rows tagged `fire` —
    they simply never appear on a picker, because no picker asks about a service
    the tenant does not sell.

    ⚠ **`rating.size_class` IS STILL TEXT AND IS NOT AN FK** (`rating/models.py`).
    This column tags the LOOKUP row; it does not make a priced size a foreign
    key, and CR-065 changes nothing about how a schedule stores which size it
    priced.

    **`OQ-1380` IS OPEN: may one size class belong to MORE than one service?** A
    2" pipe is a water size and a fire size. The seeded lists spell the two apart
    (`W-2` *Water 2"*, `FL-2` *Fire line 2"*) so nothing waits on the answer, and
    a tenant needing one size on two services enters it twice or leaves it
    untagged."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    #: CR-065 — NULL = "nobody has said", which lists everywhere (class docstring).
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
        related_name="size_classes",
    )
    #: `DEF-RAT-10220` (PO 2026-10-17) — HOW MUCH ONE OF THIS SIZE IS, in the
    #: unit its service sums in (`service_size_classes.capacity_uom_for_service`
    #: — kW for solar and battery, ton, Mbps…). A QUANTITY, never money, stored
    #: to 4 decimals (the PO's *"stored to 4 decimals"*; money's scale, so
    #: `capacity × rate` adds no rounding step). NULL on every row whose service
    #: does not SUM — a band picks a rate and a counted size is counted — and
    #: NULL means unknown, never zero: the bill refuses on it and names the
    #: asset. Built-in rows carry the ratified ladder's figure here (seeded and
    #: back-filled, `tenancy/0064`), so ONE column answers for every size and a
    #: tenant-added one is read exactly like a built-in one.
    capacity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meter_size_classes"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_meter_size_classes_tenant_code_ci"
            ),
        ]


class OccupancyStatus(models.Model):
    """S8 Reference-data list `occupancy_statuses` — occupied tenant-billed,
    occupied owner-billed, landlord-billed, vacant base-only, vacant no-billing
    (r10 SET-04.occupancy). Content owner is metering (premises/units).

    STRUCTURAL (decision log 2026-08-16): these values are BILLING BEHAVIOUR,
    not description — the difference between billing the tenant, billing the
    owner, billing base only and billing nobody — so a unit that cannot be
    given one has undefined billing behaviour. Always seeded; the sample-data
    toggle cannot suppress it."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "occupancy_statuses"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_occupancy_statuses_tenant_code_ci"
            ),
        ]


class DeviceType(models.Model):
    """S8 Reference-data list `device_types` — backflow preventer, inverter,
    EV charger, battery, endpoint (r10 SET-04, "Device types (BTM)"). Content
    owner is metering/assets.

    STRUCTURAL by consistency with asset_types and meter_types, which are
    structural for the same reason: a device row needs a type to exist."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "device_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_device_types_tenant_code_ci"
            ),
        ]


class PremisesOwnerCategory(models.Model):
    """S8 Reference-data list `owner_categories` — WHAT KIND OF PARTY a premises
    owner is (BR-TEN-150). Content owner is metering (premises owners).

    **The five, and where they come from.** PO ruling 2026-08-27, verbatim —
    *"category is okay, no richer text"* — answering whether an owner is a typed
    party record (owner-occupier · landlord · property manager · HOA · builder,
    with contact details, linked to the customer they already are) or richer
    free text. The five put to them ARE the seeded rows, in that order.

    **STRUCTURAL, and not by analogy.** `premises_owners.category_id` is NOT
    NULL, so a tenant whose S111 toggle suppressed this list could not record an
    owner at all — the exact failure BR-TEN-067 exists to prevent (*"a tenant
    that literally could not create its first record, with eleven empty
    dropdowns and no way to fill them from the UI"*).

    **TENANT-EXTENSIBLE, which is the house pattern rather than a ruling.**
    DB-14 / BR-TEN-036 make every tenant-facing vocabulary seeded-and-extensible
    and nothing was put to the PO about this one — so the build follows the house
    pattern and `OQ-502` asks them to close or confirm it. A tenant that adds
    `executor_of_estate` is doing what every other list here allows.

    ⚠ **PROTECT, and BR-TEN-030's code lock, both matter here.** An owner whose
    category was deleted or recoded is the untyped record the ruling rejected;
    the FK refuses the delete and the lookup service refuses the recode once the
    row is in use.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "premises_owner_categories"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("code"),
                name="uq_premises_owner_categories_tenant_code_ci",
            ),
        ]


class CertificationType(models.Model):
    """S8 Reference-data list `certification_types` — confined space, backflow
    tester and the rest (r10 SET-04). Content owner is metering/assets.

    NO validity-period column: r10's card says "3-yr validity" and a cadence is
    a real shape that nothing has specified. The vocabulary lands now."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certification_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_certification_types_tenant_code_ci"
            ),
        ]


class ImportMapping(models.Model):
    """S8 Reference-data list `import_mappings` — saved ETL column mappings
    reused by every run (r10 SET-04). Content owner is ledger/integrations.

    ⚠ **"SEEDED WITH NOTHING" IS SUPERSEDED FOR THE THREE GENERATED DEFAULTS
    (BR-AST-048, PO 2026-08-22 — CR-028).** The 2026-08-16 decision's reasoning
    stands for TENANT maps (a mapping describes the tenant's own file layout,
    so a fixture cannot carry one) — but each assets import target now ships
    ONE system default (`Meters default` · `Sub-meters default` · `Devices
    default`) GENERATED from the same target contract that generates the
    CR-025 sample CSV, so the known-good sample round-trips with zero mapping
    work and the two can never drift. System rows are copy-on-write: a
    tenant's "Save mapping as template" always writes a NEW row.

    `mapping` closes DEF-512's gap (*"saved ETL column mappings" with no
    column a mapping could live in*): `{SOURCE_HEADER: {"target": column}}`,
    the exact shape `import_runs.mapping_spec["columns"]` stores per run.
    `target` scopes recognition to one runner target; `last_used_at` is the
    BR-AST-048 tie-breaker (most-recently-used wins)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    #: Which runner target this template maps (IMPORT_TARGETS vocabulary).
    #: NULL on legacy rows created before BR-AST-048 — they name no target and
    #: are never auto-recognised.
    target = models.TextField(null=True, blank=True)
    #: `{source header: {"target": real column}}` — the saved map itself.
    mapping = models.JSONField(null=True, blank=True)
    #: BR-AST-048's tie-breaker: set each time a run is started from (or
    #: recognised as) this template.
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_mappings"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_import_mappings_tenant_code_ci"
            ),
        ]


class PaymentMethod(models.Model):
    """S8 Reference-data list `payment_methods` (BR-TEN-036; OQ-031 CLOSED made
    the former `payment_method_t` enum a seeded, tenant-extensible table).
    Content owner per BR-TEN-031 is PAYMENTS; hosted here for the same reason
    as ReasonCode above — see that docstring for the re-homing path.

    Seeds are the W0 fixture's seven (BR-PAY-026 `wire`, BR-TEN-041 upgrade
    `money_order`).

    ⚠ **`clearing_gl_account_id` LANDED 2026-08-17 (CR-008, second-set ruling
    1).** Until then this row was code · name · is_system · active and **no GL
    column at all**, so a utility taking card, cheque, cash and IVR had nowhere
    to say that card lands in a merchant clearing account and cheques in the
    bank. The PO ruled *"Im good with all"* on the three-item list that gap
    headed.

    It is a DEFERRED-FK uuid (B11 F-3), exactly as
    `reason_codes.default_gl_account_id`, `rating.taxes.liability_gl_account_id`
    and `rating.charges.gl_account_id` are: the row is the LEDGER's, so the
    ledger validates ownership and liveness through `seams.ledger_account_is_live`
    (see `GlPointerLookupMixin`), and no cross-module FK constraint is minted
    here (B2 §2 — the reviewed interface set is not a thing a lane extends on
    its own).

    ⚠ **IT IS THE CASH SIDE, AND EVERY OTHER GL COLUMN IN THIS PRODUCT IS THE
    REVENUE SIDE.** `charges.gl_account_id` and `plan_services.gl_account_id`
    say where money a bill EARNS lands; this says where money a customer HANDS
    OVER lands. The name carries the difference on purpose — see migration
    `0015_cr008_payment_method_gl` for why it is not called `gl_account_id`.

    ⚠ **WIRED TO POSTING 2026-08-18 (CR-008 B-10 — this paragraph used to say
    the opposite, and the reversal is the PO's).** OQ-264 closed on 2026-08-17
    (*"10 - A inside CR-008 now"*), and BOTH legs moved in one change, exactly
    as the measured warning that used to stand here required:
    `apps/payments/ledger_seam.post_payment_cleared` debits THIS account when
    it is set (undeposited funds when NULL — unmapped is still today's
    pre-B-10 behaviour), and `apps/payments/reconciliation.reconcile_batch`
    credits at reconciliation exactly what each member receipt DEBITED, read
    from the entries themselves through the ledger's `entry_debit_totals` —
    never from this column at reconcile time, so re-pointing a tender never
    strands money in the old account. A mapping to a dead account refuses the
    payment BY NAME (`ledger_seam.tender_clearing_account_id`). Proof:
    tests/test_cr008_tender_gl_posting.py, receipt to trial balance."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    #: CR-008 second-set ruling 1. NULL = unmapped, which is a real state and
    #: is TODAY'S BEHAVIOUR FOR EVERY TENDER: the receipt leg resolves the
    #: `undeposited_funds` designation regardless. Nothing refuses a NULL here.
    clearing_gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_payment_methods_tenant_code_ci"
            ),
        ]


#: ── BR-TEN-1180 · HOW A SERVICE IS PRICED — THREE VALUES, NOT TWO ──────────
#: PO ruling 2026-09-02, verbatim: *"Shall we consider Metered, % of service and
#: Capacity based"*. It SUPERSEDES `BR-RAT-081`'s two-state declaration (PO
#: 2026-08-20, *"yes we have to say service is meter or unmetered"*), which was
#: right about the question and one value short of the answer.
#:
#: **`DEF-2409` is the proof that two values could not carry it, and sewer is
#: the case that proves it.** Sewer reads no register, so on the boolean it had
#: to be `metered=False` — and the false side of that column MEANS *priced from
#: a COUNT of the unit's assets* (`BR-RAT-090`, option A, closing `OQ-283`). A
#: sewer connection has no assets, so the count is 0. Sewer is in fact a
#: PERCENTAGE of the water usage charge (`BR-RAT-015`), and **neither value of
#: the boolean was true for it**: declaring it unmetered to make the screen
#: honest would have told the engine to price sewer by counting carts.
#:
#: The three, and what each one means to the bill run:
#:   * `metered`  — a register is read; quantity is read × multiplier.
#:   * `share`    — a percentage of another service's money (`BR-RAT-015`).
#:                  No register, no count, no unit of its own.
#:   * `capacity` — priced by a COUNT of capacity units on the unit
#:                  (`BR-RAT-090`): carts, ERUs, panels, Mbps, kW.
#:
#: **`metered` STAYS THE DEFAULT and that is deliberate** — the same safe-default
#: argument `BR-RAT-081` made and hard-won law 3's *"the unsafe option is the one
#: you type"*. It also makes the migration's `metered=True → "metered"` half a
#: no-op in meaning as well as in value.
#:
#: **NO CHECK CONSTRAINT, and the choice follows this table's own precedent** —
#: `organisation_type`, `accounting_method`, `close_cadence`, `first_day_of_week`
#: and `number_format` are every one a TEXT column validated in the service
#: against a tuple declared here. A `CharField(max_length=…)` would be a second,
#: weaker statement of the same rule in a different place, and a truncating one.
BILLING_BASIS_METERED = "metered"
BILLING_BASIS_SHARE = "share"
BILLING_BASIS_CAPACITY = "capacity"
BILLING_BASES = (
    BILLING_BASIS_METERED,
    BILLING_BASIS_SHARE,
    BILLING_BASIS_CAPACITY,
)


class TenantService(models.Model):
    """tenant × service enablement (B2 tenant_services) — service_id FK to the
    10-service catalog per r16 #3 (enum role superseded); soft On/Off with
    history (US-TEN-007) + UoM gate columns (r6.4, US-TEN-008 W1 half).

    ── THE SERVICE GL ATTRIBUTES (BR-BIL-010; PO ruling 2026-08-11, OQ-106) ──
    HUMAN-REVIEW-PENDING for these two columns — they decide which revenue
    bucket a billed line lands in. The PO closed OQ-106 with *"using attributes
    on accounts and Utility services - we can derive how it sum up at
    Ledger"*: a GL designation is an attribute on a ledger account, and a
    utility SERVICE carries attributes too, so service-wise revenue is
    computable without a second mapping table. These are those attributes.

    **WHY HERE AND NOT ON A LEDGER `service_gl_map` TABLE** (B2 r10 #2 names
    such a table, and this is the divergence, stated rather than buried). The
    same ruling that made the ledger the OWNER also made a designation *"a
    field, not a table"* — and the thing a service's revenue account is an
    attribute OF is the tenant's service, which is this row. It is the same
    shape `primary_uom` / `billed_uom` already have: a cross-module FK on
    `tenant_services` pointing at the table that owns the target. A separate
    `service_gl_map` would be a second row per service carrying one uuid, with
    its own RLS policy, its own idempotency story and two places to look for
    one fact. Recorded in 12-governance/02-decision-log.md 2026-08-11 as an
    Eng-Lead disposition under the PO's ruling, and flagged in the human-review
    ledger — the PO ruled the SHAPE ("attributes on ... Utility services"), the
    table choice is Eng-Lead's reading of it.

    **`base_revenue_account` IS OPTIONAL AND THAT IS THE RULE, NOT LAXITY**
    (BR-BIL-010, CONFIRMED). The finance-signed chart splits exactly two
    services — Electric 4100/4105 and Water 4110/4115. Sewer, Trash, Gas and
    Broadband carry ONE account each, so a second REQUIRED field would have
    four services storing a duplicate of the first and a reader unable to tell
    a real split from a filled-in blank. NULL means "no split": a base line
    falls back to `revenue_account`, and `apps/ledger/selectors.py` is the one
    place that fallback is implemented.

    **BOTH COLUMNS ARE A TENANT-OVERRIDABLE DEFAULT** (BR-BIL-067, CONFIRMED —
    PO ruling 2026-08-11 closing OQ-115, verbatim: *"you create an account, but
    allow tenant user to override it"*). The seed points Water revenue at 4110;
    a utility that keeps water revenue in an account of its own numbering
    re-points it through `apps.tenancy.services.update_tenant_service`, and no
    re-seed may take that back. Everything downstream reads THIS row, never
    `chart.SERVICE_REVENUE_ACCOUNTS`, which is what makes the override real
    rather than cosmetic.

    **NEITHER IS NOT NULL**, though BR-BIL-010 calls `revenue_account`
    required. The original reason — two catalog services with no signed account
    — is GONE: the PO created 4160 Storm water and 4170 Thermal/Heat on
    2026-08-11 (OQ-115), so all ten services now map. Nullable stays for two
    reasons that outlive it: a tenant may CLEAR a mapping (an account retired, a
    chart restructured), and since the same ruling a tenant is seeded only the
    revenue accounts of the services it SELLS, so a service row can exist before
    any account does. "Required" is enforced where it can be enforced honestly:
    at issue, where an unmapped line refuses its bill (BR-BIL-010's stamp,
    US-BIL-007 TC-5) rather than posting revenue into a bucket nobody chose.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, db_column="service_id")
    enabled = models.BooleanField(default=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    #: BR-RAT-081 (PO ruling 2026-08-20): *"yes we have to say service is meter
    #: or unmetered."* The bill run reads THIS instead of demanding a meter, and
    #: it is DEF-161's fix — a plan carrying any non-metered service could not be
    #: billed at all, because `resolution.resolve()` refused every service with
    #: no service point.
    #:
    #: **It lives here, on the SERVICE, and not on a plan, an account or a
    #: premise, because it is a property of what the utility SELLS** — the same
    #: argument the GL attributes above make for living on this row.
    #:
    #: **Default True is the safe default and it is deliberate.** Every service
    #: this product has billed to date is metered, so True preserves today's
    #: behaviour exactly for every existing row; a tenant selling Trash sets it
    #: False and opts into the branch. The unsafe option is the one you type
    #: (hard-won law 3).
    #:
    #: ⚠ **`OQ-283` IS CLOSED — CORRECTED 2026-08-21 (DEF-495).** This note said
    #: *"WHERE AN UNMETERED SERVICE'S QUANTITY COMES FROM IS OQ-283, OPEN … and
    #: `resolution.resolve()` refuses by name until that is ruled"*, and both
    #: halves had stopped being true: the PO closed OQ-283 on 2026-08-20 with
    #: **BR-RAT-090, option A** — *"an unmetered service's quantity is a COUNT
    #: OF ITS ASSETS ON THE UNIT"*, observed and never typed — and
    #: `resolution.counted_quantity` implements it (3 carts × `$15.00` =
    #: `$45.00`; remove one and the next bill is `$30.00`).
    #:
    #: ⚠ **THIS COLUMN REPLACED `metered` (a BooleanField) ON 2026-09-02 —
    #: `BR-TEN-1180`, closing `DEF-2409`.** The vocabulary is the three values
    #: above; the reasoning is on `BILLING_BASES`. **The boolean is GONE from the
    #: database**, and `metered` below is a derived property, so every one of the
    #: readers that asked `row.metered` still asks it and still gets the right
    #: answer. What CANNOT survive the cut is a WRITE or a FILTER — those are
    #: exactly the two places the meaning changed, and there were exactly two of
    #: them (`selectors.unmetered_service_codes`, `sample_data.
    #: declare_estate_metering`). A `TypeError` on `create(metered=…)` and a
    #: `FieldError` on `filter(metered=…)` are the cut being loud rather than
    #: quiet, which is what hard-won law 1 asks of a change like this.
    #:
    #: **NO BACK-COMPAT SHIM ON THE API, by PO ruling of 2026-09-02:** *"we are
    #: in beta stage - so no real utility is actually onboarded yet - so there is
    #: no real data yet - hence you can fix it; I will delete the DB and
    #: relaunch"*. The read payload and the write payload both take
    #: `billing_basis` and neither takes `metered`.
    billing_basis = models.TextField(default=BILLING_BASIS_METERED)
    primary_uom = models.ForeignKey(
        Uom,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="primary_uom_id",
        related_name="primary_for_services",
    )
    alt_uom = models.ForeignKey(
        Uom,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="alt_uom_id",
        related_name="alt_for_services",
    )
    billed_uom = models.ForeignKey(  # r6.4 UoM gate (register→billed)
        Uom,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="billed_uom_id",
        related_name="billed_for_services",
    )
    conversion_factor = models.DecimalField(  # r6.4; NUMERIC(18,6)
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    #: ⚠ cross-module FK → ledger (BR-BIL-010; PO 2026-08-11, OQ-106). An
    #: ADDITION to B2 §2's reviewed interface set, registered per r16 #7 "at
    #: DDL time" — this is that time. PROTECT for the same reason every other
    #: chart reference is protected: an account a service points at is in use,
    #: and IS-1 says a referenced account deactivates but never deletes.
    revenue_account = models.ForeignKey(
        "ledger.LedgerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="revenue_account_id",
        related_name="services_billing_usage_here",
    )
    #: OPTIONAL by rule, not by omission — see the class docstring. NULL means
    #: "this service has no usage/base split"; the base line uses
    #: `revenue_account`, and that fallback lives in apps/ledger/selectors.py.
    base_revenue_account = models.ForeignKey(
        "ledger.LedgerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="base_revenue_account_id",
        related_name="services_billing_base_here",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def metered(self) -> bool:
        """`BR-RAT-081`'s question, answered from `BR-TEN-1180`'s column.

        **READ-ONLY, AND DELIBERATELY SO.** `BR-RAT-081` asked *is there a
        register?* and that question is still worth asking — the bill run branches
        on it, `metering.selectors.billing_reads_for_unit` branches on it, and
        thirty-odd call sites across ten backend files read it. All of them keep
        working unchanged, which is the whole reason this property exists rather
        than a mass rename: a rename would have collided with three lanes editing
        `apps/rating` and `apps/billing` the day this landed, for no gain.

        **WHAT IT MUST NOT BECOME IS A WRITE PATH.** `metered = False` was two
        answers wearing one word — *"priced from a count"* and *"a share of
        another service's money"* — and `DEF-2409` is what that cost. Assigning
        through this property would let a caller say "not metered" again without
        saying which of the two it meant, which is precisely the ambiguity the
        column was widened to remove. A caller that WRITES names the basis.
        """
        return self.billing_basis == BILLING_BASIS_METERED

    class Meta:
        db_table = "tenant_services"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "service"], name="uq_tenant_services"),
        ]


class ReferenceSeedRun(models.Model):
    """Per-list idempotency evidence for fixture seeding (US-TEN-002 §5)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    list_code = models.TextField()
    fixture_version = models.TextField()  # e.g. 'V1.0.0.0' (legacy rows: '2026.08')
    seeded_count = models.IntegerField(default=0)
    seeded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reference_seed_runs"
        constraints = [
            # US-TEN-002 TC-3: single seed-run record per list per version.
            models.UniqueConstraint(
                fields=["tenant", "list_code", "fixture_version"], name="uq_seed_runs"
            ),
        ]


class NumberSeries(models.Model):
    """BR-TEN-035 storage (US-TEN-012 §5): one row per series per tenant.
    Allocation is the BE-06 sink's law — SELECT FOR UPDATE inside the issuing
    transaction, forward-only counter; that service lands with US-TEN-012's
    story lane. This table is deliberately dumb: format + next_number, plus the
    two CR-005 columns below.

    ⚠ `restart_period` + `period_counted` ARE ONE FACT IN TWO COLUMNS and must
    be read together. CR-005 (PO 2026-08-16) asks for *"Restart counter each
    year/month — Yes/No per entity"*, and a restart is only decidable against
    the period the counter is CURRENTLY counting in — otherwise the first
    allocation of every January resets, and so does the second. So the policy
    lives in `restart_period` and the position lives in `period_counted`
    (`""` · `"2026"` · `"2026-08"`, from `core.numbering.period_key`), both
    written under the same row lock that hands out the sequence.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    series = models.TextField()  # core.numbering.KNOWN_SERIES keys
    format = models.TextField()  # BR-TEN-035 grammar (validated by core.numbering)
    next_number = models.BigIntegerField(default=1)
    # CR-005: never · yearly · monthly. Default `never` is every row's behaviour
    # before this change, so an existing tenant's numbering does not move
    # because a column arrived.
    restart_period = models.TextField(default="never")
    period_counted = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "number_series"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "series"], name="uq_number_series"),
            # Counters are monotonic from 1 (BR-TEN-035; forward-only edits).
            models.CheckConstraint(
                condition=Q(next_number__gte=1), name="ck_number_series_next_ge_1"
            ),
            # CR-005: the three restart values and nothing else. CHECK-constrained
            # rather than free text for the reason CUSTOM_FIELD_ENTITIES gives
            # below — a typo'd policy would be a rule nothing implements, and
            # here it would silently mean "never" on a series the utility
            # believes restarts every January.
            models.CheckConstraint(
                condition=Q(restart_period__in=["never", "yearly", "monthly"]),
                name="ck_number_series_restart_period",
            ),
        ]


class HolidayCalendar(models.Model):
    """Tenant holiday dates (r5 #3; S63 card, BR-TEN-039; TOU Option B:
    holidays bill off-peak — consumption is rating's story)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    holiday_date = models.DateField()
    label = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "holiday_calendars"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "holiday_date"], name="uq_holidays"),
        ]


class UserPreference(models.Model):
    """US-SHL-013 PROPOSED-SCHEMA, verbatim shape (BR-SHL-024): UI preferences
    only, one row per (tenant, user, key); value size/namespace policed by the
    preference service story. CASCADE on user: prefs leave with the user row
    (BR-SHL-024 'removed when the membership is removed')."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    user = models.ForeignKey(  # ⚠ cross-module → identity (B2 §2 reviewed FK set)
        "identity.User", on_delete=models.CASCADE, db_column="user_id"
    )
    key = models.TextField()  # dotted namespace, ≤128 chars (service-enforced)
    value = models.JSONField()  # ≤32 KB, UI preferences only (service-enforced)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_preferences"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user", "key"], name="uq_user_prefs"),
        ]


#: The EIGHT tables a tenant may extend (B2 r17.2, verbatim and closed).
#: CHECK-constrained rather than free text because the exclusions each have a
#: stated reason in r17.2 and a typo'd entity would create a definition that
#: renders nowhere and stamps onto nothing: `tariffs`/`rate_tiers`/`charges`/
#: `taxes` are the calculation boundary (DB-3/B4), `invoices`/`invoice_lines`/
#: `payments`/`journal_*` are append-only (DB-4 — they receive the r17.3
#: snapshot instead), and `meter_reads` is monthly-partitioned and cold-detached
#: at two years (DB-7).
CUSTOM_FIELD_ENTITIES = (
    "premises",
    "units",
    "service_points",
    "assets",
    "accounts",
    "contacts",
    "addresses",
    "service_agreements",
    # CR-161-BRC10 W5 (PO 2026-10-02, R3: *"Payments IN as capture-at-entry
    # only"*). r17.2 kept `payments` out as append-only; the ruling lets a
    # payment carry answers written at its INSERT and never afterwards —
    # hard rule 4's trigger freezes the column with no allow-list change
    # (`payments/0046`). BR-TEN-048 still holds: never allocation, deposit,
    # refund, dunning or a ledger posting. `tenancy/0056` widens the CHECK.
    "payments",
    # CR-161-BRC10 W4 (PO 2026-10-02, Part 1 rows 2 and 10–13: *"Customer
    # (person / company) · Work orders · Readings · Routes · Areas"*, each
    # *"Not offered"* until now). `tenancy/0057` widens the CHECK and adds
    # `areas.custom_data`; `metering/0067` adds the column to `routes`,
    # `work_orders`, `read_import_rows` and `meter_reads`; `customers` has
    # carried one since r17.2.
    #
    # ⚠ `meter_reads` WAS KEPT OUT BY r17.2 FOR A REASON THAT STILL HOLDS AND
    # IS ANSWERED RATHER THAN WAVED AWAY: the table is partitioned monthly and
    # cold-detached at two years (DB-7). `ADD COLUMN` on the parent reaches
    # every ATTACHED partition; a detached archive partition never receives
    # it, and `selectors.ReadArchiveResultSet._COLUMNS` deliberately does not
    # name the column — so an archived reading shows no answers rather than
    # raising. And Part 2 row 11: *"Never used in the bill calculation"* —
    # G6 / DB-17 stays ABSOLUTE for `apps/rating/`.
    "customers",
    "work_orders",
    "meter_reads",
    "routes",
    "areas",
)

#: B2 r17.1 `data_type`, the six signed values. This lane invents none, and it
#: also does not IMPLEMENT all six on the document path — see
#: `apps/billing/custom_snapshot.py`, which stamps `text`/`select` verbatim and
#: stubs the other four on OQ-125 (how a non-string value renders to its
#: snapshot string under IS-8 is not ruled anywhere).
CUSTOM_FIELD_DATA_TYPES = ("text", "number", "date", "boolean", "select", "multi_select")


class CustomField(models.Model):
    """A tenant-defined field DEFINITION (B2 addendum r17.1, EP-TEN-09).

    Tenant-defined DATA, never schema (BR-TEN-046): creating one writes a row
    here and never runs DDL, and the table is tenant-scoped with RLS FORCE like
    every other tenant table (CLAUDE.md rule 1). The VALUES live in a
    `custom_data jsonb` column on the owning row (r17.2), never in a shared
    value table — a shared table would be written by customers, metering AND
    assets, which is the cross-module write DB-16/§2 forbids, and it would need
    its own audit path where a column on the owning row rides BR-AUD-003's
    whole-row before/after for free.

    WHAT THIS LANE BUILT AND WHAT IT DID NOT
    ----------------------------------------
    Built: the table, its constraints, its RLS policy, and ONE read
    (`selectors.document_safe_custom_fields`) that the invoice stamp calls.
    NOT built, and each belongs to EP-TEN-09 in this module's own lane:
    US-TEN-014 (the S8 card + management view), US-TEN-015 (the Add modal, the
    BR-TEN-051 cap of 10 active per entity per tenant, the BR-TEN-049 key
    immutability), US-TEN-016 (the placement editor and its eligible-slot
    allow-list), US-TEN-017 (deactivate/reactivate and the BR-TEN-053 Redis
    registry cache). **So nothing writes this table today except a test or a
    fixture** — stated here rather than implied, because hard-won law 2 is that
    built is not wired. The reason the TABLE lands ahead of its UI is the one
    the engineering plan gives for the whole slice (B12 r7.2): the invoice
    snapshot is a ONE-WAY DOOR and cannot read a registry that does not exist.

    `is_document_safe` — THE ONE COLUMN NOT IN r17.1, and it is a PO ruling.
    OQ-076 closed on 2026-08-10 with *"Dont put SSN on invoices"*, and the
    MECHANISM was confirmed the same day as INVERTED / fail-closed: *"A custom
    field is NOT snapshotted onto a document unless the tenant explicitly marks
    it document-safe — the unsafe option is the one you have to type (hard-won
    law 3)."* r17.1 predates that confirmation and still describes the rejected
    opt-out `contains_pii` flag, so the column is minted here from the ruling
    rather than from the table. `default=False` IS the ruling: an unmarked
    field never reaches `invoices.custom_snapshot`, which is append-only and
    which BR-TEN-044's day-91 deletion can never reach.

    Deliberately NOT minted here: `default_value` (OQ-075's closure — *"the
    field may carry a DEFAULT VALUE"*). Nothing in R2 reads it: the default is
    what a document renders for a DEACTIVATED field, and rendering is R3
    (US-NOT-016), while US-BIL-028 TC-6 excludes deactivated fields from new
    snapshots. Minting an unread column would be exactly the dead-weight
    hard-won law 2 warns about. The closure's own words — *"BR-ID to be minted
    at propagation"* — put it in EP-TEN-09's propagation pass; recorded in
    12-governance/02-decision-log.md so it is not lost.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    entity = models.TextField()  # one of CUSTOM_FIELD_ENTITIES
    #: `^[a-z][a-z0-9_]{1,39}$`, UNIQUE (tenant, entity, key), and IMMUTABLE
    #: after insert (BR-TEN-049) — a stamped snapshot and a pinned template
    #: both reference the key forever, so a rename silently breaks history.
    #: The regex and the immutability are the WRITE service's to enforce
    #: (US-TEN-015); the uniqueness is below because only the database can
    #: hold it under concurrency.
    key = models.TextField()
    #: Tenant PROSE, deliberately not a `message_key` (B2 r17.5 #1). G14/TD-16
    #: say the server sends keys and never prose; a tenant-authored label has
    #: no key and never can. PO accepted the exception 2026-08-10, scoped to
    #: `label`/`help_text` and to nothing else.
    label = models.TextField()
    help_text = models.TextField(null=True, blank=True)
    data_type = models.TextField()  # one of CUSTOM_FIELD_DATA_TYPES
    options = models.JSONField(null=True, blank=True)  # ≥2, select types only
    is_required = models.BooleanField(default=False)
    #: BR-TEN-050 — deactivate only, no delete path at any layer. Stored values
    #: survive and reappear verbatim on reactivation.
    is_active = models.BooleanField(default=True)
    #: OQ-076 CLOSED / mechanism INVERTED, PO 2026-08-10. Fail-closed: see the
    #: docstring. Nothing stamps a field onto an invoice without this True.
    is_document_safe = models.BooleanField(default=False)
    placement = models.JSONField(default=dict, blank=True)  # {"S51": "input"}
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "custom_field"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "entity", "key"], name="uq_custom_field_key"),
            models.CheckConstraint(
                condition=Q(entity__in=CUSTOM_FIELD_ENTITIES), name="ck_custom_field_entity"
            ),
            models.CheckConstraint(
                condition=Q(data_type__in=CUSTOM_FIELD_DATA_TYPES),
                name="ck_custom_field_data_type",
            ),
        ]
        indexes = [
            # r17.1: the registry read (BR-TEN-053) is the only hot query, so
            # the one index is partial on `is_active`. No GIN index over
            # `custom_data` ships in R2 — filtering and sorting over it are
            # explicitly out (BR-SHL-038) so that no index decision is made
            # before a story needs one.
            models.Index(
                fields=["tenant", "entity"],
                condition=Q(is_active=True),
                name="ix_custom_field_active",
            ),
        ]


def job_progress_default() -> dict:
    """BE-07 record shape: progress starts {done: 0, total: unknown}."""
    return {"done": 0, "total": None}


class Job(models.Model):
    """BE-07 job record (core/jobs.py contract, column-per-key). The store
    that adapts this model to set_job_store() lands with the /jobs/{id}
    endpoint story; the table exists now so 202s never promise a poll URL
    without a row behind it. Status vocabulary = core.jobs (kernel-defined,
    flagged pending an A5 row)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    kind = models.TextField()
    status = models.TextField(default="queued")  # core.jobs.STATUSES
    progress = models.JSONField(default=job_progress_default)
    checkpoint = models.JSONField(null=True, blank=True)  # TD-17 resume marker
    result_link = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    scope_key = models.TextField(null=True, blank=True)  # NFR-16 idempotent fold-in
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        constraints = [
            # NFR-16: one ACTIVE job per (tenant, kind, scope_key) — the DB
            # backs core.jobs.enqueue()'s fold-in against races.
            models.UniqueConstraint(
                fields=["tenant", "kind", "scope_key"],
                condition=Q(status__in=["queued", "running"]) & Q(scope_key__isnull=False),
                name="uq_jobs_active_scope",
            ),
        ]


# ── `BellEvent` / `bell_events` WAS HERE AND IS GONE (DEF-3422, 2026-09-03) ──
#
# It was BE-09's bell storage: a table with an index, a docstring naming
# `core.bell.notify()` as *"the only sanctioned writer"*, and a writer that
# handed every item to a sink NOTHING EVER REGISTERED — so it logged *"bell item
# not persisted (no sink yet)"* and returned None. Nothing read it either, and
# nothing outside its own tests ever called `notify()` at all. Three weeks, three
# missing links, and a docstring claiming a guarantee for every one of them
# (hard-won law 1). `10-scripts/gates/g74_tables_nobody_reads.py` is the check
# that found it by asking the only question that cannot be answered innocently:
# does anything in this product touch this table?
#
# It was REMOVED rather than wired, and the decision is in
# `12-governance/02-decision-log.md` (2026-09-03). The short of it: the bell
# already HAS a store — `outbound_messages` (what the platform undertook to
# send) and `in_app_messages` (what a person received and whether they have
# looked at it) — with tenant scoping, read state, an audience ruled by
# BR-NOT-021, a settings screen, an API and a screen that renders it. A second
# table behind the same bell would be two answers to *"what is in my bell"*, and
# the one that had no writer, no reader and no caller is the one that went.
#
# BR-SHL-026's five events are untouched: they are what the bell SHOWS, not
# where it is kept. Of the five, ONE has a trigger in this product today (the
# billing run, wired by CR-048); the count is on BR-SHL-026's own row in
# 04-docs/05-modules/00-platform-shell/02-business-rules.md.


#: US-TEN-019 §5 / BR-TEN-060 — the outcome vocabulary of one module's sample
#: block. `skipped` ALWAYS carries a machine-readable `reason_code`, which is
#: the whole point: DEF-016 was a skip nobody could see.
SAMPLE_RUN_OUTCOMES = ("seeded", "skipped", "failed")

#: The reason codes a non-`seeded` outcome may carry. `seam_not_wired` is the
#: one every module answers with today (see apps/tenancy/sample_data.py).
SAMPLE_RUN_REASONS = (
    "seam_not_wired",  # the owning module publishes no sample-seeding function
    "catalog_empty",  # BR-TEN-012's vocabulary is missing, so nothing can be built on it
    "exception",  # the module's own seeder raised; the class is in `detail`
)


class SampleDataRun(models.Model):
    """One module's outcome inside one tenant's sample-data run (US-TEN-019 §5).

    THIS TABLE IS THE HONESTY REPORT, and it exists precisely because the
    alternative failed in production. DEF-016: the reference fixture covered
    four lists and `charge_codes` silently skipped because rating's seeding seam
    had never been written; the skip went into a run summary nobody reads, and
    the PO found the empty cards by opening Settings on the live deployment.
    BR-TEN-060 is the prevention — *"an unwired seam is a named line on S62, not
    a skip"* — and a row here per module is what makes the line renderable.

    UNIQUE (tenant, module) is BR-TEN-063's idempotency: a replay updates the
    module's row rather than accumulating a history nobody reads. The RUN is
    per tenant and the ROW is per module because BR-TEN-063 makes each module's
    sample block its OWN transaction — one unwired module must not roll back
    the rest.

    ⚠ WHAT IT RECORDS TODAY, SAID PLAINLY (hard-won law 1: a docstring claiming
    a guarantee is not the guarantee). Every module resolves to
    `skipped/seam_not_wired`, and the sample-data job therefore seeds NOTHING.
    That is not a bug in this table; it is the state of the product, and the
    reason is structural: BR-TEN-057 puts `is_sample` on `premises`, `units`,
    `service_points`, `assets`, `asset_assignments` and `meter_reads` — every
    one of them owned by apps/metering or apps/assets — and BR-TEN-013 forbids
    tenancy writing another module's tables. Until those columns and each
    module's `seed_sample_records` exist, the only honest thing this run can do
    is name every module it could not reach. It does exactly that.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    #: The OWNING module whose sample block this row reports: metering, assets,
    #: customers, rating. Not a screen and not a table — BR-TEN-060 counts by
    #: module because that is the unit a seam is wired at.
    module = models.TextField()
    outcome = models.TextField()  # SAMPLE_RUN_OUTCOMES
    seeded_count = models.IntegerField(default=0)
    #: Required whenever `outcome != 'seeded'` (CheckConstraint below). A skip
    #: with no reason is the DEF-016 shape and the database refuses it.
    reason_code = models.TextField(null=True, blank=True)
    #: Prose for the operator — the S62 line's tail ("rating seeding seam not
    #: wired"). Never a message_key: it names code, not user-facing copy.
    detail = models.TextField(null=True, blank=True)
    #: ⚠ **THE PER-BLOCK BREAKDOWN BEHIND THIS ROW — CR-039 wave B, 2026-08-26.**
    #:
    #: The row above is BR-TEN-060's line and its shape is UNCHANGED: one row
    #: per module, worst-first, because the rule says *"a row per module with a
    #: machine-readable reason_code and a sentence an operator can act on"* and
    #: a lane does not re-shape a signed rule to make a screen easier.
    #:
    #: But a module owns up to THREE blocks (`customers` owns accounts, payment
    #: plans and the parked move-in; `metering` owns premises and reads), and
    #: the merge that makes the module line honest is exactly what destroys the
    #: answer to the Product Owner's question — *"we need to look at what of 1
    #: job fails"*. Four blocks' outcomes were being reconciled away, and the
    #: only trace of WHICH one broke was a sentence.
    #:
    #: So each block records itself here, in `SAMPLE_MODULES` order:
    #:   `{block, label, outcome, count, reason_code, error_code, detail,
    #:     finished_at}`
    #: `block` is the seam function name, which is what identifies a block
    #: uniquely inside a module and is what a per-block RETRY names.
    #:
    #: Empty on a row recorded before this column existed, and on nothing else:
    #: every run and every retry writes it. A screen therefore treats `[]` as
    #: "recorded before block-level reporting — re-run to see it", never as
    #: "no blocks" (the DEF-127 shape: a zero standing in for "I don't know").
    blocks = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sample_data_runs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "module"], name="uq_sample_data_runs"),
            models.CheckConstraint(
                condition=Q(outcome__in=SAMPLE_RUN_OUTCOMES), name="ck_sample_run_outcome"
            ),
            # BR-TEN-060 in the schema: a non-seeded outcome MUST say why.
            models.CheckConstraint(
                condition=Q(outcome="seeded") | Q(reason_code__isnull=False),
                name="ck_sample_run_reason_required",
            ),
        ]


#: The flows that can be parked. ⚠ **SERVICE REQUESTS ARE NOT HERE, AND THAT IS
#: THE POINT.** A service request is a numbered row from the moment it is
#: created, so parking it ANNOTATES that row — `waiting_on`, `park_note`,
#: `remind_on` on `customers.ServiceRequest`, which has worked since CR-031.
#: These five have no row at all until they commit, which is the whole reason
#: this table exists.
WIZARD_PARK_FLOWS = ("move_in", "move_out", "transfer", "disconnect", "new_connect")


class WizardPark(models.Model):
    """A wizard a clerk stopped halfway through, kept so they can come back.

    **BR-SHL-048 (PO 2026-08-26, CR-035), and the rule is one sentence: a
    parked wizard changes NOTHING until it is executed.** The Product Owner's
    words: *"Option A - Unitl move in executed, no records updates."* The
    question they answered was concrete — a clerk starts a move-in for Unit 12,
    500 Main St on 26 August, stops at step 3 waiting on a $150 deposit, parks
    it, and comes back on 2 September. Between those dates **Unit 12 reads
    Vacant**, no account exists, no occupancy begins and no bill changes. This
    row is a saved draft of a FORM and appears in the clerk's own "Waiting on"
    list and nowhere else in the product.

    The requirement under the ruling, in the PO's own words: *"in pratcicail
    life all these request does not close in  day, hence user genrllay park
    them … help them to work on these request as per their pace"*.

    ⚠ **THIS TABLE CARRIES NO FOREIGN KEY TO ANYTHING IT DESCRIBES, AND THAT IS
    THE RULING IN THE SCHEMA — BR-SHL-048 (a).** An FK is a relationship, and
    the ruling says there is none yet. So the unit, account and premises a clerk
    has chosen are stored inside `subject_ref` as COPIED VALUES. Three
    consequences, all of them the point rather than a price:

      1. Deleting a unit can never be blocked by a forgotten draft.
      2. No report, ageing bucket or occupancy query can reach a draft by
         joining to it — a draft is invisible to the rest of the product by
         construction, not by every future author remembering to exclude it.
      3. A draft cannot hold a unit, so **no parked wizard can block anything**.
         That settles the half of BR-SHL-047 left open — it feared a parked
         move-out would keep hold of its unit — and settles it by removing the
         mechanism rather than by adding a rule.

    ⚠ **THE COST THE RULING ACCEPTS, STATED HERE BECAUSE IT IS INVISIBLE
    EVERYWHERE ELSE.** A parked move-out is a closure nobody downstream can
    see, so **that account keeps billing** until the wizard is finished.
    `remind_on` and the age on the "Waiting on" list are the only things
    standing between a parked draft and one that sits forever.

    ⚠ **`values` IS A DRAFT OF A FORM AND NEVER A FINANCIAL RECORD.** Nothing
    here is money that has happened — CLAUDE.md rule 4's immutability governs
    issued invoices, payments and journal lines, and a half-typed form is none
    of those. It follows that a draft may be edited and discarded freely, and
    that **everything in it is re-validated at execution, never trusted from
    the park** (BR-SHL-048 (b)): what was true on 26 August — the unit vacant,
    the plan version, the deposit rule — may not be true on 2 September.

    ⚠ **IT CAN HOLD PII BEFORE ANY CUSTOMER EXISTS.** A parked move-in carries
    the incoming occupant's name, email and phone while there is no account and
    no customer row to attach them to. It is tenant-scoped under RLS FORCE like
    every other table here, and a draft is deletable — which is what makes an
    erasure request answerable at all.

    **Hosted by tenancy, owned by nobody else — the `user_preferences` /
    `bell_events` posture** (this module's own lifecycle note: *"hosting ≠
    owning"*). Platform-shell has no Django app, and these drafts belong to five
    flows across TWO modules (customers and metering), so parking them in either
    one would put half of them in a module that does not own them. Nothing here
    is a customers table or a metering table; it is the shell's scratch pad.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    #: Which wizard. Checked against WIZARD_PARK_FLOWS in the schema, so a typo
    #: cannot create a sixth flow nothing can resume.
    flow = models.TextField()
    #: What the clerk sees in their list — "Unit 12, 500 Main St". Denormalised
    #: ON PURPOSE: there is no FK to re-read it through (see the class note), and
    #: a label that goes stale is honest about WHAT WAS PARKED, which is what a
    #: clerk is looking for. The wizard re-reads the real record on resume.
    subject_label = models.TextField(blank=True, default="")
    #: The ids the clerk chose, COPIED not referenced — {"unit_id": "...",
    #: "account_id": "..."}. Resume looks them up; nothing joins to them.
    subject_ref = models.JSONField(default=dict, blank=True)
    #: 1-based, and it is an INDEX not a decoration — BR-SHL-046: one declared
    #: step list drives the wizard's bar, the list's STEP column and where a
    #: resume lands. A skipped step is still one of the six.
    step = models.PositiveSmallIntegerField(default=1)
    #: What was typed. A draft of a form; see the class note.
    values = models.JSONField(default=dict, blank=True)
    #: ⚠ **FREE TEXT, DELIBERATELY, AND MATCHING `ServiceRequest.waiting_on`.**
    #: The nine reasons (waiting on the customer · documents · a deposit · a
    #: payment · inspection · a permit · materials · site access · a third
    #: party) are what the SCREEN OFFERS; the column stores what was chosen.
    #: Closing the vocabulary here would give one "Waiting on" list two
    #: incompatible contracts for one column, and service requests — the one
    #: flow where parking already works — got there first.
    #: ⚠ **EMPTY MEANS *A DRAFT*, NOT *A PARK WITH NO REASON* (`CR-122-BRC06`,
    #: PO 2026-09-19).** B19 §12.2's two controls are unchanged and still two:
    #: `Park` records WHAT IS AWAITED and fills this; `Save & exit` records
    #: nothing but the typing and leaves this empty. Until this ruling a row
    #: with no reason was refused outright, because `Save & exit` wrote no row
    #: at all — and that is the defect the ruling closed: a clerk who keyed five
    #: steps and a deposit lost every one of them. **A reader telling the two
    #: apart reads THIS COLUMN**, which is why the draft did not get a flag of
    #: its own: two columns that must agree are two columns free to disagree.
    waiting_on = models.TextField(blank=True, default="")
    #: `CR-122-BRC06` — **the reference a clerk quotes while the job is still in
    #: their hands**: `MVI-{YY}-{0000}` from the `move_in` series for a move-in
    #: draft, `MVO-{YY}-{0000}` from the `move_out` series for a move-out,
    #: allocated the moment the wizard writes the row.
    #:
    #: ⚠ **IT IS THE SAME NUMBER THE FINISHED `move_records` ROW CARRIES.**
    #: `services.move_in` and `services.move_out` adopt it rather than
    #: allocating a second one, so the number a clerk wrote on a sticky note
    #: while they waited for a deposit is the number the completed move is
    #: filed under. Two numbers for one job is how
    #: `move_reads._requests_by_account_no` came to match on an account
    #: number, and that docstring already records what it cost.
    #:
    #: ⚠ **THE MOVE-OUT HALF ARRIVED 2026-09-20 AND THIS NOTE SAID `move_in`
    #: ONLY UNTIL THEN** (PO ruling of that date, option A, item 9;
    #: `OQ-CUS-12489` closed, `DEF-CUS-5922` closed). Until it did,
    #: `/moves/{ref}` — which matches on this column — could not address a
    #: parked move-out at all, because NULL matches no reference.
    #: `wizard_parks.DRAFT_REFERENCE_SERIES` is the list, and its docstring
    #: carries why the remaining three flows still take no number.
    #:
    #: ⚠ **NULL IS A REAL ANSWER AND IS NOT AN ERROR.** A tenant with no series
    #: row for that flow gets a draft with no reference rather than no draft
    #: — `moves._allocate_move_no` takes the same posture for the same reason
    #: (*"the move is the regulated act; its reference is not"*), and the three
    #: remaining flows allocate nothing here at all.
    reference = models.TextField(null=True, blank=True)
    park_note = models.TextField(null=True, blank=True)
    remind_on = models.DateField(null=True, blank=True)
    parked_at = models.DateTimeField(auto_now_add=True)
    parked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="parked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wizard_parks"
        constraints = [
            models.CheckConstraint(
                condition=Q(flow__in=WIZARD_PARK_FLOWS), name="ck_wizard_parks_flow"
            ),
            #: A step is an index into a declared list; zero indexes nothing.
            models.CheckConstraint(condition=Q(step__gte=1), name="ck_wizard_parks_step"),
            #: ⚠ **`ck_wizard_parks_waiting_on` WAS DROPPED, NOT WEAKENED BY
            #: ACCIDENT (`CR-122-BRC06`, migration `tenancy/0046`).** It
            #: refused an empty reason because `Save & exit` wrote no row at
            #: all; the PO ruled on 2026-09-19 that it must write one, so an
            #: empty reason is now the DRAFT state and the check would refuse
            #: every draft. The column's own docstring carries the distinction.
            #: One number to a human is one number to the index: per tenant,
            #: case-insensitive, and only where a reference exists.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("reference"),
                name="uq_wizard_parks_tenant_reference_ci",
                condition=Q(reference__isnull=False),
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03 lead story of the W0 migrations lane; AMENDMENT co-packet US-TEN-009@178c282 — EP-TEN-07 scope addendum); AMENDMENT co-packet US-TEN-019@c3b7d18 — `SampleDataRun`, the per-module honesty ledger BR-TEN-060 is rendered from
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations lane) · AMENDED 2026-08-09 by story-coder (settings rule-page + reference-data + logo gap lane) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (ImportMapping gains target/mapping/last_used_at (BR-AST-048; closes DEF-512's missing column — migration 0017, HUMAN-REVIEW-PENDING))
# checklist: A✔ B=deferred(table-half only — service/API TCs land with each story lane) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff✔ black✔ py_compile✔ pytest tests/test_w0_models.py✔ · suite 180/180✔ (147 baseline + 33 W0) · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · run_gates 11-PASS/0-FAIL/1-SKIP✔ · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: hosting dispositions flagged (user_preferences/jobs/bell_events hosted by tenancy — shell has no app; holiday_calendars here vs r16 #6 rating-owner proposal) · sessions/auth_tokens/security_policies (identity) deliberately NOT built — outside the W0 migrations scope list, reported · [gap lane 2026-08-09] reason_codes + payment_methods are now HOSTED here (BR-TEN-031 names billing/payments as content owners; neither app has tables and both are another lane's territory — hosting ≠ owning, re-homing path in each model docstring) · the S64 document lives on tenant_settings, not the metering-owned `read_validation_settings` table B2 r16 #6 PM-proposes — REPORTED · reason_codes carries no default_gl_account_id (US-TEN-010 §5) because no ledger_accounts table exists to FK
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
