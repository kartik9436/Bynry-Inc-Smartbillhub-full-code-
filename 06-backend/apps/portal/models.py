# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — the switch and the five · US-CWP-070 —
#           the portal-only branding fields. Screens: CWP-069 · CWP-070 · CWP-001
#           ⊕ 2026-09-04, CR-068 wave C: US-CWP-013 (the draft that survives a
#           closed tab) · US-CWP-014 (the recorded paperless consent) ·
#           US-CWP-015 (the quick-service cards). Screens: CWP-047 · CWP-009 ·
#           CWP-010
# Rules:    CR-068 R8 (per-tenant switches — all on for a new tenant except
#           self-read) · CLAUDE.md hard-won law 3 (defaults fail closed —
#           `is_live` is false until a person turns it on) · BR-CWP-043's
#           shape → PR-43 (branding is READ from the tenant record and stored
#           nowhere twice: this table has no logo, no name and no colour
#           column) · B14 rule 32 (the strapline is one sentence)
# Tests:    06-backend/tests/test_us_cwp_013_about_you.py ·
#           06-backend/tests/test_us_cwp_014_check_and_send.py ·
#           06-backend/tests/test_us_cwp_014_pg.py (the future-date constraint,
#           PostgreSQL only — law 14) ·
#           06-backend/tests/test_us_cwp_069_settings.py (TC-2 no second
#           address column · TC-3 the defaults) ·
#           06-backend/tests/test_us_cwp_070_branding.py (TC-2 no logo column)
# Impacts:  migrations/0001_initial.py · migrations/0002_rls_portal_settings.py ·
#           migrations/0003_consent_draft_quick_service.py ·
#           migrations/0004_rls_consent_and_draft.py
# ───────────────────────────────────────────────────────
"""portal models — one table in wave A, `portal_settings`, one row per tenant.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
* **The portal address.** It is `tenants.subdomain` — the slug the utility
  chose at sign-up, already the first segment of every request — and this
  table does not copy it (`US-CWP-069` TC-2 asserts no second column). The
  column is still called `subdomain` and now holds a PATH segment; reading
  the column name and inferring the URL shape is the reasoning that wrote all
  seventy-five blueprint routes as subdomains (`03-field-map.md` §1).
* **The logo, the trading name and the two brand colours.** They live on the
  tenant record and are edited on Company → Profile. Repeating them here would
  give a utility two versions of its own logo (`US-CWP-070` TC-2).
* **Enrolment counts.** They are derived over tables later waves create.

`front_page_service_ids` is a JSON list of the platform `services.id` values
the utility ticked, not a PostgreSQL `uuid[]`: the default test suite runs on
SQLite (CLAUDE.md law 14) and `ArrayField` has no SQLite form, while the
validation that matters — a subset of the tenant's OWN enabled services — is
the service's, not the column's. `03-field-map.md` §1 is stamped with this.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.crypto import EncryptedTextField
from core.dbfields import uuid7_pk

#: The five switches, in the order CWP-069 draws them (CR-068 R8).
SWITCH_FIELDS: tuple[str, ...] = (
    "quick_pay_enabled",
    "self_read_enabled",
    "plans_enabled",
    "requests_enabled",
    "outage_reporting_enabled",
)

#: What a tenant with NO row reads as. R8 verbatim: *"All on for a new tenant
#: except self-read"*; law 3 puts the portal itself OFF until a person turns it
#: on. A selector answers these when the row does not exist yet, so a fresh
#: tenant is never written to by a read.
DEFAULTS: dict[str, object] = {
    "is_live": False,
    "quick_pay_enabled": True,
    "self_read_enabled": False,
    "plans_enabled": True,
    "requests_enabled": True,
    "outage_reporting_enabled": True,
    "strapline": None,
    "front_page_service_ids": [],
    "office_hours_text": None,
    "emergency_phone": None,
    "quick_service_categories": [],
    "request_errands": [],
    # CR-190-BRC10 — the agreement link's life, days (the column's own default).
    "agreement_link_valid_days": 7,
    # DEF-BIL-10531 — the bill email's PDF link's life, days (the column's default).
    "bill_link_valid_days": 30,
}

#: The four portal-only branding fields CWP-070 edits (blueprint B2).
#: ⊕ 2026-09-04 — `quick_service_categories` joins the set, so the ONE door
#: a System Admin already saves portal-only content through saves it too
#: rather than gaining a second one (US-CWP-015; see QUICK_SERVICE_FIELDS).
BRANDING_FIELDS: tuple[str, ...] = (
    "strapline",
    "front_page_service_ids",
    "office_hours_text",
    "emergency_phone",
    "quick_service_categories",
    #: ⊕ CR-068 · US-CWP-060, 2026-09-04 — `CWP-046`'s six errand cards, saved
    #: through the SAME door for the reason the line above gives: one list of
    #: portal-only content, one set of rules. See REQUEST_ERRAND_FIELDS below.
    "request_errands",
)

#: ⊕ CR-068 wave C · US-CWP-015 — THE SIX QUICK-SERVICE CARDS, AS THE
#: UTILITY'S OWN LIST AND NOT A HARDCODED ONE.
#:
#: ⚠ **THE STORY SAYS THESE CATEGORIES ARE *"already tenant-configurable"*
#: AND THEY ARE NOT — THERE IS NO SUCH TABLE.** `ServiceRequest` carries no
#: `category` column at all (`apps/customers/models.py` — `account_type`,
#: `outcome` and `channel`, and nothing else that could hold one), and no
#: tenancy lookup list holds request kinds. The plan's §0 rule applies: the
#: code wins and the task says so (`DEF-CWP-3701`).
#:
#: So the vocabulary is the PORTAL's, it lives on the utility's own settings
#: row beside `front_page_service_ids` — the same shape, for the same reason —
#: and every card a visitor is offered is read from it. A tenant that renames
#: a card sees the new label (US-CWP-015 TC-7); a card only Oak Ridge
#: configured is not offered on Pine Hill (TC-6). Each entry is
#: `{"code", "label", "hint", "needs_bill_number"}`.
#:
#: ⚠ **STATED ABSENCE: THE BACK-OFFICE CONTROL THAT EDITS THIS IS NOT BUILT.**
#: The list is seeded per tenant and served; `CWP-069` gains the editor with
#: `US-CWP-071`'s wave. A tenant can change it today only through the
#: settings save, and that is written down rather than implied
#: (`12-governance/02-decision-log.md` 2026-09-04).
QUICK_SERVICE_FIELDS: tuple[str, ...] = ("code", "label", "hint", "needs_bill_number")

#: ⊕ CR-068 · US-CWP-060, 2026-09-04 — `CWP-046`'s SIX ERRAND CARDS, AS THE
#: UTILITY'S OWN LIST.
#:
#: ⚠ **THIS IS A SECOND VOCABULARY ON THIS ROW AND NOT THE FIRST ONE REUSED,
#: WHICH IS A JUDGMENT AND IS WRITTEN DOWN AS ONE.** `quick_service_categories`
#: is `CWP-010`'s list — what a STRANGER WITH NO ACCOUNT asks for (a re-read, a
#: copy of a bill, low pressure). These six are what a SIGNED-IN CUSTOMER wants
#: done to an account they already hold: move out, move home, add a service,
#: stop for a while, report a problem, something else. Serving one list on both
#: screens would offer *"copy of a bill"* where `US-CWP-060` asks for *"move
#: out"*, so they are two columns rather than one column read twice.
#:
#: ⚠ **NOTHING HERE IS A `service_requests` COLUMN, FOR THE REASON
#: `DEF-CWP-3701` ALREADY RECORDED:** that table has no `category` at all, so
#: the chosen card's own label travels into `what_they_said`, exactly as a quick
#: ask does. `outcome` stays the CLERK's — a customer's words never decide a job
#: outcome (`BR-CWP-075`, and the model's own *"Nothing in this module writes
#: `outcome` from evidence"*).
#:
#: Each entry is `{"code", "label", "hint", "screen"}`. **`screen` is the
#: `CWP-###` the card leads to, or `None`** — and the null is load-bearing
#: rather than tidy: a utility can name an errand this product draws no screen
#: for, and the card then renders HELD with its reason instead of linking to
#: nowhere (hard-won law 2, `BR-CWP-056`).
REQUEST_ERRAND_FIELDS: tuple[str, ...] = ("code", "label", "hint", "screen")


#: B14 rule 32 made a number: the sentence under the utility's name.
STRAPLINE_MAX_CHARS = 140


#: `CR-190-BRC10` — the agreement link's life: seeded value and the range a
#: utility may choose (one day to ninety; a link older than a quarter is a link
#: nobody remembers being sent).
AGREEMENT_LINK_DAYS_SEEDED = 7
AGREEMENT_LINK_DAYS_MIN = 1
AGREEMENT_LINK_DAYS_MAX = 90

#: `DEF-BIL-10531` — the bill email's PDF link's life: seeded 30 (decision log
#: 2026-10-22, our judgment; the PO named no number), the same 1–90 range.
BILL_LINK_DAYS_SEEDED = 30
BILL_LINK_DAYS_MIN = 1
BILL_LINK_DAYS_MAX = 90


class PortalSettings(models.Model):
    """`portal_settings` — CP-30, one row per tenant, keyed on the tenant."""

    tenant = models.OneToOneField(
        "tenancy.Tenant",  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        on_delete=models.PROTECT,
        db_column="tenant_id",
        primary_key=True,
        related_name="portal_settings",
    )
    is_live = models.BooleanField(default=False)  # law 3: off until switched on
    quick_pay_enabled = models.BooleanField(default=True)
    self_read_enabled = models.BooleanField(default=False)  # R8: the one that is off
    plans_enabled = models.BooleanField(default=True)
    requests_enabled = models.BooleanField(default=True)
    outage_reporting_enabled = models.BooleanField(default=True)
    strapline = models.TextField(null=True, blank=True)
    front_page_service_ids = models.JSONField(default=list, blank=True)
    office_hours_text = models.TextField(null=True, blank=True)
    emergency_phone = models.TextField(null=True, blank=True)
    #: US-CWP-015 — see QUICK_SERVICE_FIELDS above for why this is a column
    #: here and not a lookup table somewhere else.
    quick_service_categories = models.JSONField(default=list, blank=True)
    #: US-CWP-060 — see REQUEST_ERRAND_FIELDS above for why this is a second
    #: column and not the list above read twice.
    request_errands = models.JSONField(default=list, blank=True)
    #: `CR-190-BRC10` (PO 2026-10-22, answer 1: *"7 Days"*) — how long an
    #: emailed agreement link stays valid, in DAYS. A utility SETTING seeded at
    #: 7, never a constant (*"don't do any hardcoding"*); edited on Settings →
    #: Customer portal; bounds `AGREEMENT_LINK_DAYS_MIN/MAX`.
    agreement_link_valid_days = models.IntegerField(default=AGREEMENT_LINK_DAYS_SEEDED)
    #: `DEF-BIL-10531` — how long the bill email's direct PDF link stays valid,
    #: in DAYS. A setting seeded at 30, beside the agreement link's; bounds
    #: `BILL_LINK_DAYS_MIN/MAX`.
    bill_link_valid_days = models.IntegerField(default=BILL_LINK_DAYS_SEEDED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_settings"


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — the journey that begins before identity exists
# ═══════════════════════════════════════════════════════════════════════════


class PortalApplicationDraft(models.Model):
    """`portal_application_drafts` — the applicant's unsent form, saved from the
    first keystroke and carrying NO reference.

    ⚠ **WHY THIS IS NOT A `service_requests` ROW IN THE `draft` STATE, WHICH IS
    WHAT `03-field-map.md` AND `US-CWP-013` §5 BOTH SAY IT IS.** Two CONFIRMED
    rules collide, and the code settles it:

      * `US-CWP-013` §2 — *"A draft holds **no allocated number** until
        submit"* (blueprint `P33`), and TC-1 asserts *"No reference has been
        issued"*.
      * `BR-CUS-093` (PO ruling 2026-08-24, verbatim: *"At creation — every
        draft is numbered"*) — `service_request_service.create_request`
        allocates `SR-26-nnnn` **inside its own transaction**, so a service
        request in the `draft` state cannot exist without a number.

    A portal draft written as a service request would therefore be numbered on
    the applicant's FIRST KEYSTROKE, and every abandoned half-typed form would
    arrive on the clerk's worklist carrying a reference the applicant was never
    shown. The plan already resolved it — wave C task C2 says the request is
    created *at submit* — and this table is that resolution. `03-field-map.md`
    §1 and `US-CWP-013` §5 are stamped with it (`DEF-CWP-3700`).

    **THE TOKEN IS THE CAPABILITY.** There is no session here and there is
    nobody to authenticate: the draft link the applicant keeps IS how they get
    back to their own typing. It is 128 bits from the browser's own CSPRNG, it
    is scoped to the tenant like every other row (RLS `FORCE`, migration 0004),
    and a draft started on `/pine-hill` is not found under `/oak-ridge`
    (US-CWP-013 TC-6) because the tenant predicate is the database's, not the
    view's.

    ⚠ **WHAT IS DELIBERATELY CLEARED AT SUBMIT.** `date_of_birth` and `tax_id`
    are collected for ONE purpose — recognising somebody who has held an account
    here before, which `BR-CWP-031` permits for an application and forbids for
    enrolment — and `apps.customers.service_request_service._clean_capture`
    REFUSES both by name, deliberately (`DEF-632`'s shape: an identifier that is
    silently dropped is worse than one that is refused). So the verdict is
    recorded on the request in words, the identifier is not copied anywhere, and
    the draft's own copy is blanked the moment it has been used. A business
    applicant's tax ID STAYS here — `OQ-CWP-1560` CLOSED (b) 2026-09-04, stored
    once — and is read from here by `customers.portal_seam.application_tax_id`
    (`DEF-CWP-9045`; this line read *"OPEN"* until 2026-10-02).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    #: The URL capability. Unique per tenant; never shown as a reference.
    token = models.TextField()

    # ── step 1 · the address (from CWP-008) ────────────────────────────────
    address_as_given = models.TextField(null=True, blank=True)
    address_unit_as_given = models.TextField(null=True, blank=True)
    #: ⊕ `DEF-CWP-9817` (portal/0015) — the TOWN and the ZIP as the applicant
    #: typed them on step 1, which the blueprint (p31) draws beside the street.
    #: They exist to FIND the premises (`BR-CUS-1091`, PO 2026-09-22: *"correct
    #: address will be on presmies but first time you will ahve to take the
    #: details to match it"*) and are handed to the request's own `_as_given`
    #: columns at Send. A record of what a stranger said — never the address
    #: (hard rule 8): once a premises is matched, the premises is what shows.
    #: No state: the blueprint asks none (the utility's own state is assumed).
    address_city_as_given = models.TextField(null=True, blank=True)
    address_postal_code_as_given = models.TextField(null=True, blank=True)
    #: Evidence, never a decision — the premises the public lookup matched, so
    #: the review step can quote the services without re-running the search.
    #: A plain uuid, not an FK: metering owns the row and B2 §2's reviewed FK
    #: set is not a thing a lane extends on its own (the same posture as
    #: `service_requests.resolved_premises_id`).
    matched_premises_id = models.UUIDField(null=True, blank=True)
    service_codes = models.JSONField(default=list, blank=True)

    # ── step 2 · about you (CWP-047) ───────────────────────────────────────
    applicant_kind = models.TextField(null=True, blank=True)  # person | business
    first_name = models.TextField(null=True, blank=True)
    last_name = models.TextField(null=True, blank=True)
    company_name = models.TextField(null=True, blank=True)  # business only
    email = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    #: ⚠ RECOGNITION ONLY (BR-CWP-031), cleared at submit — see the docstring.
    date_of_birth = models.DateField(null=True, blank=True)
    tax_id = models.TextField(null=True, blank=True)  # business; cleared at submit
    requested_start = models.DateField(null=True, blank=True)
    #: ⊕ `DEF-CWP-9818` (portal/0015) — the applicant's own pick of customer
    #: CATEGORY and SUB-CATEGORY on step 3 (PO ruling 2026-10-06, option b:
    #: *"Show the full Category and Sub-category dropdowns from Settings on
    #: step 3 … The clerk can still change it."*). CODES, never ids — no id of
    #: any kind travels on the guest surface (`availability.py`), and both codes
    #: are unique per tenant. Resolved to rows by the customers module at Send.
    account_type_code = models.TextField(null=True, blank=True)
    account_subtype_code = models.TextField(null=True, blank=True)

    # ── step 3 · the mailing address, if different (DEF-CWP-9163) ──────────
    #: ⚠ **WHERE THE BILL GOES, NOT WHERE THE SERVICE IS — hard rule 8's first
    #: named exception.** Wireframe s17 draws *"Mailing address, if different"*
    #: with *"Same as the service address"* ticked; `CR-085` lane-3 finding 17.3
    #: recorded it absent and nobody filed it. PO 2026-10-02: *"Mailing Address
    #: is not captured as part of the applicant/customer information."*
    #: `True` (the default) means the bill goes to the service address and the
    #: five boxes below stay empty. When the applicant unticks it, the five are
    #: the applicant's own words; on the account they become ONE
    #: `customers.addresses` `kind='mailing'` row, written by the CUSTOMERS
    #: module's own account-opening door (`services._carry_request_decisions`)
    #: — never a premises address, and never a portal write to an account
    #: (`BR-CWP-026`).
    mailing_same_as_service = models.BooleanField(default=True)
    mailing_line1 = models.TextField(null=True, blank=True)
    mailing_line2 = models.TextField(null=True, blank=True)
    mailing_city = models.TextField(null=True, blank=True)
    mailing_state = models.TextField(null=True, blank=True)
    mailing_postal_code = models.TextField(null=True, blank=True)

    # ── the utility's own questions (`CR-161-BRC10` W7, portal/0014) ────────
    #: The answers to the fields a utility switched to *Ask the customer*,
    #: keyed by record type as the request's copy is: ``{"customers": {…},
    #: "accounts": {…}, "premises": {…}}``. Validated on every save against
    #: ONLY the asked fields (`seams.tenancy_seam.clean_application_custom_
    #: answers`); handed to the customers module at Send.
    custom_data = models.JSONField(default=dict, blank=True)

    # ── DEF-CUS-10225 (portal/0016) — Move-in's fields on the portal form ──
    #: PO 2026-10-18, *"CUSTOMER DATA AND UI CONSISTENT ACROSS THE CREATE
    #: SCREENS"*: the portal asks Move-in's fields in Move-in's order, in the
    #: portal look (image `04-portal.png`). How the applicant wants to be
    #: reached — one of `customers.models.CONTACT_BY` (email/text/phone/letter).
    contact_by = models.TextField(null=True, blank=True)
    #: 🔒 THE LAST FOUR OF THE SSN, AND NOTHING MORE — PO 2026-10-18, verbatim
    #: *"okay"* to *"last 4 of SSN only"*: no full SSN and no licence online.
    #: Encrypted like every other identifier (`core.crypto`, its own AAD), and
    #: blanked here at Send, when it moves to `service_requests.ssn_last4`.
    ssn_last4 = EncryptedTextField(
        null=True, blank=True, crypto_context="portal_application_drafts.ssn_last4"
    )
    #: *Add a co-applicant* — the tick, then the folding card's five fields.
    co_applicant = models.BooleanField(default=False)
    co_applicant_name = models.TextField(null=True, blank=True)
    co_applicant_relationship = models.TextField(null=True, blank=True)
    co_applicant_phone = models.TextField(null=True, blank=True)
    co_applicant_email = models.TextField(null=True, blank=True)
    co_applicant_date_of_birth = models.DateField(null=True, blank=True)
    #: *Set preferences* — paperless, text reminders, language. NO autopay: a
    #: payment method cannot be saved on the portal form (decision log, same
    #: day: *"Autopay only where a payment method can be saved"*). NULL = the
    #: applicant did not set it.
    paperless = models.BooleanField(null=True, blank=True)
    text_reminders = models.BooleanField(null=True, blank=True)
    preferred_language = models.TextField(null=True, blank=True)

    # ── 🔒 DEF-PAY-10554 (portal/0019) — ONE CARD CHARGE PER APPLICATION ─────
    #: The application fee's idempotency key, made by the SERVER and kept here
    #: before the card is charged, so a reload presents the same key (decision
    #: log 2026-10-23, *"one charge per application, even across a reload"*).
    #: `appfee:<tenant id>:<draft id>:<fee 4dp>:<declines>`.
    fee_idempotency_key = models.TextField(null=True, blank=True)
    #: Definite declines so far; the next key ends in this number, because a
    #: provider answers a reused key with its first answer. A timeout does NOT
    #: count — the money may have moved and the same key must go again.
    fee_declines = models.IntegerField(default=0)
    #: ⚠ WHAT THE PROVIDER APPROVED, written in its own savepoint the moment it
    #: approves and BEFORE the request is written. A later attempt that finds it
    #: records it and charges nothing. Kept after submit; NULL = no approval.
    fee_charge_approved = models.JSONField(null=True, blank=True)

    # ── step 4 · what came of it ───────────────────────────────────────────
    #: The request this draft became, once it was sent. NULL until then, which
    #: is the whole of *"no reference until submit"* expressed as a column.
    service_request_id = models.UUIDField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #: ⚠ **THE APPLICANT'S LAST VISIT — WHAT THE 30 DAYS ARE COUNTED FROM**
    #: (PO ruling 2026-10-02, verbatim: *"Delete it 30 days after her last
    #: visit … If she returns on 20 October, the 30 days start again."*).
    #: Stamped by `applications.py` when the draft link is OPENED, when it is
    #: SAVED, and when a file is added or removed — every act that is the
    #: applicant coming back. Read by `draft_cleanup.py`, the nightly job that
    #: deletes an unsent draft 30 days after it.
    #:
    #: ⚠ **NOT `updated_at`, AND THAT IS THE POINT OF A SEPARATE COLUMN.**
    #: `updated_at` moves when the form CHANGES; opening the link and reading
    #: it changes nothing, and the ruling counts that as a return. NULL on a
    #: draft last touched before this column existed (`portal/0012`); the job
    #: then reads `updated_at`, which is the last visit we can prove.
    last_visited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "portal_application_drafts"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "token"], name="uq_portal_application_drafts_token"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "token"], name="ix_portal_app_drafts_token"),
        ]


class PortalApplicationDocument(models.Model):
    """`portal_application_documents` — a file the applicant attached to their
    UNSENT new-service application (`CR-158-BRC10`, PO 2026-10-01: *"you need to
    allow customer to upload documents and save those document to server for
    that Utility"*; `DF-4` superseded for this request only).

    ⚠ **WHY THE BYTES ARE HELD HERE AND NOT IN THE DOCUMENT STORE — A JUDGMENT,
    RECORDED IN THE DECISION LOG OF 2026-10-01.** `apps.tenancy.document_store`
    is the product's one store and it is the right home for a document the
    UTILITY holds — so a file goes there, unchanged, the moment the application
    is SENT (`service_request_documents.attach_from_portal`). It is the wrong
    home for a file on a draft, for two reasons the store's own design makes
    unavoidable:

      * **it is write-once** (`NFR-35`; the database row can never be deleted —
        its seven-year OBJECT lock is suspended from 2026-10-02 by
        `CR-160-BRC10`, which changes nothing here). A
        stranger who picks the wrong scan and removes it, or who never sends the
        form at all, would leave a file the utility can never delete — seven
        years of somebody's driving licence that nobody asked for;
      * **staff can list it.** The notifications register reads
        `document_store.manifest()` — every stored document of the tenant — so a
        file on an abandoned draft would appear on a clerk's screen. The ruling
        is that it never does.

    So a draft's file lives on this row, behind RLS `FORCE` (migration
    `portal/0011`), readable by nothing but the applicant's own token, and is
    DELETED from here once it has been handed to the store at submit. The bytes
    in PostgreSQL are bounded by the limits below: five files of at most 10 MB
    on one draft.

    ⚠ **AND ON A DRAFT NEVER SENT, 30 DAYS AFTER THE APPLICANT'S LAST VISIT**
    (PO ruling 2026-10-02): `draft_cleanup.py` deletes the draft and every row
    here on it, nightly, and logs it. Until that ruling an abandoned draft's
    file was kept for ever.

    **NO DATABASE ID REACHES A SCREEN AS A VALUE** (B14 rule 31): `id` is the
    React key and the address of the remove control, never a cell.
    """

    #: PDF, JPG and PNG — and only those three. The staff door also takes CSV
    #: (`BR-SHL-031`); a customer has no reason to send a spreadsheet, and a
    #: CSV has no byte signature to check, which is the one guard this door
    #: insists on. Values are the media types the BYTES were found to be.
    CONTENT_TYPES = ("application/pdf", "image/jpeg", "image/png")
    #: `BR-SHL-031`'s 10 MB — the same figure every upload door in this product
    #: uses, so a customer and a clerk are never told different limits.
    MAX_BYTES = 10 * 1024 * 1024
    #: Five on one application. Two documents are asked for (`US-CWP-014` §4),
    #: and five covers a second page of each and one more.
    MAX_PER_DRAFT = 5

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    draft = models.ForeignKey(
        PortalApplicationDraft,
        on_delete=models.CASCADE,
        db_column="draft_id",
        related_name="documents",
    )
    #: ⚠ **WHICH REQUIRED DOCUMENT THIS FILE IS — `DEF-CWP-9167`, PO ruling
    #: 2026-10-02 (option A): *"a separate attach row for each requirement
    #: (Photo ID, Proof of address), so it's always clear what each file is
    #: for"*.** One of `applications.DOCUMENT_REQUIREMENTS`, or NULL for a file
    #: attached before this column existed (shown as *Other documents*). At
    #: submit it becomes the service-request document's `doc_type`, so the
    #: clerk sees which file is the ID.
    requirement = models.TextField(null=True, blank=True)
    #: The file's own name as the applicant's computer had it, trimmed.
    name = models.TextField()
    #: What the BYTES are — sniffed on arrival, never the browser's claim.
    content_type = models.TextField()
    size_bytes = models.IntegerField()
    payload = models.BinaryField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_application_documents"
        constraints = [
            models.CheckConstraint(
                condition=Q(content_type__in=("application/pdf", "image/jpeg", "image/png")),
                name="ck_portal_app_docs_content_type",
            ),
            models.CheckConstraint(
                condition=Q(size_bytes__gt=0) & Q(size_bytes__lte=10 * 1024 * 1024),
                name="ck_portal_app_docs_size",
            ),
            # DEF-CWP-9167 — the two documents `US-CWP-014` §4 asks for, or
            # none (a file attached before the column existed).
            models.CheckConstraint(
                condition=Q(requirement__isnull=True)
                | Q(requirement__in=("photo_id", "proof_of_address")),
                name="ck_portal_app_docs_requirement",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "draft"], name="ix_portal_app_docs_draft"),
        ]


class PortalConsent(models.Model):
    """`portal_consent` — `CP-30`, `CR-068` `R5`: paperless is a RECORDED
    CONSENT, not a toggle.

    `BR-CWP-087`, verbatim: *"Paperless is a **recorded consent** — a timestamp,
    the wording version, and a way to withdraw — not a toggle."* The field map
    puts the point sharper still: **a consent without the version of the words
    they saw is not a consent.**

    ⚠ **`account_id` IS NULLABLE, AND THAT IS THE WHOLE POINT OF THIS WAVE.**
    `03-field-map.md` types it `uuid` FK against a screen taken by somebody who
    already has an account. The one place release 1 takes this consent is
    `CWP-009` — the connection form — where **the applicant has no account and
    may never have one**. So the row hangs off the SERVICE REQUEST at that
    moment, and an account is stamped on later if one is opened. A NOT NULL here
    would have made the only consent the product takes impossible to write.

    ⚠ **`agreed_on` CAN NEVER BE IN THE FUTURE, AND THE DATABASE IS WHAT
    REFUSES IT** (`US-CWP-014` TC-4, `03-field-map.md`). The blueprint shipped a
    consent dated nineteen days after its own *today*; a check in Python would
    be a check one importer forgets. **SQLite has no `now()` a CHECK may call,
    so this constraint exists on PostgreSQL and the test that proves it is
    PostgreSQL-only** — CLAUDE.md law 14: a green SQLite run proves nothing
    about it. See `migrations/0003` and `tests/test_us_cwp_014_pg.py`.

    **NEVER DELETED.** Withdrawal writes `withdrawn_on`; the row stays, because
    the record of a consent that was given and then withdrawn is not the same
    fact as no consent at all (`US-CWP-014` TC-2: *an absent consent is not a
    withdrawn one*).
    """

    KIND_PAPERLESS = "paperless"
    KINDS = (KIND_PAPERLESS,)

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    #: Stamped when — and only when — an account is opened for this applicant.
    #: A plain uuid for the same reason `matched_premises_id` is one.
    account_id = models.UUIDField(null=True, blank=True)
    #: What the consent was given ON. Release 1 has exactly one shape: the
    #: application at `CWP-009`.
    service_request_id = models.UUIDField(null=True, blank=True)
    kind = models.TextField(default=KIND_PAPERLESS)
    #: ⚠ THE VERSION OF THE WORDS THEY ACTUALLY SAW (`apps/portal/wording.py`).
    wording_version = models.TextField()
    agreed_on = models.DateTimeField(default=timezone.now)
    withdrawn_on = models.DateTimeField(null=True, blank=True)
    #: `CWP-009` for a new connection, `CWP-025` for a withdrawal.
    taken_on_screen = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_consent"
        constraints = [
            #: The half a CHECK can hold on any engine: a consent must name the
            #: version of the words. An empty string is not a version.
            models.CheckConstraint(
                condition=~Q(wording_version=""),
                name="ck_portal_consent_wording_version_present",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "service_request_id"], name="ix_portal_consent_request"
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave E — getting in: the customer's own credential, their session,
# and the one-time code that stands between the two.
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔒 SENSITIVE PATH (CLAUDE.md "Sensitive paths"): credentials and sessions.
# HUMAN-REVIEW-PENDING — row in 12-governance/09-human-review-ledger.md.
#
# ⚠ **NOT ONE OF THESE THREE MODELS MAY EVER REACH `identity.User`.**
# `BR-CWP-004`: *"A portal credential must never resolve into a staff role.
# Separate table, separate session, separate permission catalogue — not one
# table with a flag on it."* There is no `user` column below and there is no
# import of `apps.identity` in this module; `seams/identity_seam.py` reads the
# tenant's password POLICY and nothing else, and G91 fails the build if a
# credential or session file reaches past it.


#: `BR-CWP-036` and the field map's own numbers, as constants a test can quote.
#: Three different limits guard three different doors and they are NOT the same
#: number: the enrolment FORM is a public guessing surface (three tries), the
#: sign-in form is the staff policy applied to a customer (five), and the code
#: itself is six digits a real person mistypes (six).
ENROLMENT_MAX_TRIES = 3  # BR-CWP-036 — "fifteen minutes after three wrong tries"
SIGN_IN_MAX_TRIES = 5  # field map §1 `failed_attempts` — "lock at 5 for 15 minutes"
CODE_MAX_TRIES = 6  # 10-execution-plan.md E1 — "six wrong locks"
LOCK_MINUTES = 15  # every one of the three

#: `BR-CWP-035` — *"A one-time code lasts ten minutes."*
CODE_TTL_MINUTES = 10
#: `07-endpoints.md` §2 / E2 — the reset link is a seven-day, single-use link.
RESET_TTL_DAYS = 7

CREDENTIAL_ACTIVE = "active"
CREDENTIAL_LOCKED = "locked"
CREDENTIAL_DISABLED = "disabled"
CREDENTIAL_STATUSES = (CREDENTIAL_ACTIVE, CREDENTIAL_LOCKED, CREDENTIAL_DISABLED)

CHANNEL_SMS = "sms"
CHANNEL_EMAIL = "email"
OTP_CHANNELS = (CHANNEL_SMS, CHANNEL_EMAIL)

#: What a one-time code is FOR. **Four doors, one store** — it said three until
#: 2026-09-05: an enrolment code proves the person holding a paper bill also
#: holds the contact already on file, a reset token proves the person asking for
#: a new password holds the mailbox, an add-account code (2026-09-04, wave G,
#: `US-CWP-027`) proves the person adding a SECOND account holds the contact on
#: THAT account, and a step-up code (2026-09-05, phase 5, `US-CWP-022`) proves
#: the person REDIRECTING WHERE MONEY GOES is still the person who signed in.
#: They differ in lifetime and in shape, not in kind, and one table means one
#: place where "consumed" and "superseded" are decided.
#:
#: ⚠ **`PURPOSE_ADD_ACCOUNT` IS THE ONE WHOSE DESTINATION IS NOT THE ASKER'S**
#: (`BR-CWP-033`, `US-CWP-027` TC-3). Enrolment and reset both send to a contact
#: the asker is claiming to be; this one deliberately sends somewhere the asker
#: may not be able to read, because that is the entire guard — a person holding
#: one account and a stolen bill number must not collect a second.
#:
#: ⚠ **`PURPOSE_STEP_UP` IS A SEPARATE VALUE FOR ONE REASON AND IT IS THE WHOLE
#: OF `US-CWP-022`** (`BR-CWP-040`, TC-3): **a code that got somebody IN must not
#: also let them change where their money goes.** `verify_code` filters on this
#: column, so an enrolment code presented at the payment-methods door does not
#: match a row and is refused — without any check having to remember to look.
#: Sharing one purpose across both doors would make a hijacked session's
#: sign-in code a payment-method code, minutes later.
#:
#: ⚠ **NO MIGRATION IS NEEDED AND THAT IS CHECKED, NOT ASSUMED:** `purpose` is a
#: plain `TextField` with no check constraint and no choices (migration
#: `portal/0007` line 114), so a third — or fourth — value is a code change only.
PURPOSE_ENROL = "enrol"
PURPOSE_RESET = "reset"
PURPOSE_ADD_ACCOUNT = "add_account"
PURPOSE_STEP_UP = "step_up"
CODE_PURPOSES = (PURPOSE_ENROL, PURPOSE_RESET, PURPOSE_ADD_ACCOUNT, PURPOSE_STEP_UP)


class PortalCredential(models.Model):
    """`portal_credential` — `CP-01`. What a CUSTOMER signs in with.

    ⚠ **THE TABLE THAT MUST NEVER JOIN TO `identity.user`** (`BR-CWP-004`,
    field map §1 in capitals). A staff account and a customer login are two
    populations with two permission catalogues; one table with a flag on it is
    how a customer becomes a System Admin by a single wrong boolean.

    ⚠ **`customer_id` MUST ALREADY EXIST** (`BR-CWP-029`): enrolment attaches a
    password to a person on file and never creates one. That is why there is no
    `email` uniqueness across the product and no self-registration door — the
    only way a row here comes into being is `enrol/set-password`, and that
    endpoint cannot be reached without a matched account and a proven code.

    `email` is the sign-in identifier and is unique **per tenant**, never
    globally: the same person may hold service from two utilities on this
    platform and each is a separate relationship with a separate password.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    customer = models.ForeignKey(  # ⚠ cross-module → customers (B2 §2 reviewed set)
        "customers.Customer", on_delete=models.PROTECT, db_column="customer_id"
    )
    #: ⚠ **CASE-INSENSITIVE BY NORMALISATION, NOT BY `citext`.** The field map
    #: types this `citext`, which is a PostgreSQL extension SQLite cannot hold
    #: (law 14 — the default suite runs on SQLite and would prove nothing).
    #: `credentials.normalise_email` lower-cases and strips on the way IN, so
    #: the uniqueness below is real on both engines and a mixed-case sign-in
    #: finds the row. The divergence is stamped in `03-field-map.md` §1.
    email = models.TextField()
    #: The product's CONFIGURED hasher, whatever `PASSWORD_HASHERS` names on
    #: this deployment — never a second hashing policy invented here. See
    #: `credentials.py` for why that supersedes the field map's `Argon2id`.
    password_hash = models.TextField()
    password_changed_on = models.DateTimeField(null=True, blank=True)
    otp_channel = models.TextField(default=CHANNEL_SMS)  # OTP_CHANNELS
    failed_attempts = models.SmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    status = models.TextField(default=CREDENTIAL_ACTIVE)  # CREDENTIAL_STATUSES
    enrolled_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_credential"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"], name="ux_portal_credential_tenant_email"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="ix_portal_cred_customer"),
        ]


class PortalSession(models.Model):
    """`portal_session` — `CP-01`. One signed-in customer, on one device.

    ⚠ **`account_set` IS A RECORD OF WHAT WAS TRUE AT ISSUE AND IS NEVER THE
    AUTHORISATION.** The field map says the set is *"built from exactly two
    sources and re-derived on read"* (`BR-CWP-009`), and `session.py` does
    exactly that on every single request. This column is kept because the
    record of what a session was granted is worth having when a dispute is
    about who could see what — but a stale copy that authorised a read would be
    a landlord keeping a tenant's bills after the tenancy ended.

    ⚠ **AND IT IS FLAT** (`BR-CWP-013`): a master account over common areas is
    one more entry, not a parent. There is no tree in this column and a lane
    that adds one has given a landlord their tenants' accounts.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    portal_credential = models.ForeignKey(
        PortalCredential, on_delete=models.PROTECT, db_column="portal_credential_id"
    )
    #: `[{"account_id": "...", "permissions": [...]}, ...]` — see the docstring.
    account_set = models.JSONField(default=list, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    device_fingerprint = models.TextField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "portal_session"
        indexes = [
            models.Index(fields=["tenant", "portal_credential"], name="ix_portal_sess_cred"),
        ]


class PortalOneTimeCode(models.Model):
    """`portal_one_time_code` — ⊕ **ADDED BY THE BUILD, 2026-09-04** (wave E).

    ⚠ **THIS TABLE IS NOT IN THE FIELD MAP'S FIVE AND IT HAD TO BE**
    (`DEF-CWP-3741`). `BR-CWP-033` puts a one-time code between *matched* and
    *proven*, and at that moment **no credential exists yet** — the credential
    is what `enrol/set-password` creates two screens later. So the code cannot
    hang off `portal_credential`, and `BR-CWP-038`'s reset link has the same
    shape one door along. The field map named `otp_channel` and stopped.

    ⚠ **THE CODE ITSELF IS NEVER STORED.** Only its hash is here; the code a
    person types is in the queued outbound message, which is the only place it
    was ever meant to exist. A support screen that could read back a live code
    would be a second way in.

    **`superseded_at` is what makes *resend invalidates* true**: issuing a new
    code marks every live one for the same purpose and account superseded in
    the same transaction, so the first SMS cannot still work after the second
    arrives. `attempts` is the six wrong tries; `consumed_at` is single use.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    purpose = models.TextField()  # CODE_PURPOSES
    #: The account being enrolled on. NULL for a reset, which is asked for by
    #: email address and reaches a credential rather than an account.
    account = models.ForeignKey(  # ⚠ cross-module → customers (B2 §2 reviewed set)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
    )
    portal_credential = models.ForeignKey(
        PortalCredential,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="portal_credential_id",
    )
    code_hash = models.TextField()
    channel = models.TextField()  # OTP_CHANNELS
    #: What the SCREEN shows — `••• ••• 4218`. Masked here as well as on the
    #: way out, so nothing downstream has to remember to mask it (`BR-CWP-033`).
    destination_masked = models.TextField()
    #: The outbound queue row this code was handed to. The demo reads the code
    #: from that row's render context while W6 is not activated.
    outbound_message_id = models.UUIDField(null=True, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    attempts = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_one_time_code"
        indexes = [
            models.Index(fields=["tenant", "purpose", "account"], name="ix_portal_otp_account"),
            models.Index(fields=["tenant", "purpose", "portal_credential"], name="ix_portal_otp_cred"),
        ]


#: Every tenant-scoped table this module owns today. The RLS migration and the
#: PostgreSQL isolation test both read this tuple, so a sixth table cannot land
#: without a policy (US-CWP-001 TC-5 on PostgreSQL).
TENANT_TABLES: tuple[str, ...] = (
    "portal_settings",
    "portal_application_drafts",  # CR-068 wave C
    "portal_consent",  # CR-068 wave C
    "portal_credential",  # CR-068 wave E 🔒
    "portal_session",  # CR-068 wave E 🔒
    "portal_one_time_code",  # CR-068 wave E 🔒
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-069@87b94265 · US-CWP-070@87b94265 (EP-CWP-12 stories + BR-CWP-001..096 snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D✔(backoffice_api.py · guest_api.py) E✔(SettingsCustomerPortalTab.tsx · portal/guest/StartService.tsx · CheckAndSend.tsx) F✔ G✔ H=n/a(the 🔒 half is migrations/0002 and 0004, both *rls*)
# gates: pytest tests/test_us_cwp_069_settings.py tests/test_us_cwp_070_branding.py tests/test_us_cwp_012_availability.py tests/test_us_cwp_013_about_you.py tests/test_us_cwp_014_check_and_send.py tests/test_us_cwp_015_quick_service.py · tests/test_us_cwp_001_pg.py and tests/test_us_cwp_014_pg.py on PostgreSQL · G81 (write points) · G84 (a module writes only the models it declares) · G74 (every table has readers: selectors.py, availability.py)
# exceptions: `front_page_service_ids` is JSON, not uuid[] — SQLite has no array column and the subset rule lives in the service; field map stamped · `portal_consent.account_id` is NULLABLE against a field map that types it NOT NULL, because the one screen that takes this consent belongs to somebody with no account (DEF-CWP-3702) · the future-date CHECK on `agreed_on` is PostgreSQL-only (law 14) · `portal_application_drafts` is a SIXTH portal table the field map does not list, because BR-CUS-093 numbers every service-request draft at creation (DEF-CWP-3700)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
