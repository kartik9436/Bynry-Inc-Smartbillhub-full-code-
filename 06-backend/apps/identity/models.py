# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-004 (EP-IDN-02 §user list — table halves of the list columns) ·
#           US-IDN-005 (add-a-user: per-tenant users + temp-password columns) ·
#           US-IDN-001 (lockout counter columns — §5 PROPOSED-SCHEMA) ·
#           US-IDN-003 (sessions table — §5 PROPOSED-SCHEMA platform shape) ·
#           US-IDN-010 (security_policies — §5 PROPOSED-SCHEMA, one row/tenant)
#           Screens: S2/S3 (sign-in) · S8 (Users & roles, Security) · S48 (user menu)
# Rules:    BR-IDN-029 / BR-IDN-010 (PER-TENANT users, UNIQUE(tenant_id, email) —
#           B2 r11, r16 #2) · BR-IDN-008 (exactly 3 predefined platform roles) ·
#           BR-IDN-011 (invited = temp password not yet changed) · BR-IDN-022/025
#           (temp password shown once, 7-day validity; lockout 5-fail/15-min columns) ·
#           BR-IDN-006/026 (server-side sessions bound to one (user, tenant)) ·
#           BR-IDN-019/020 (security policy record + IP allowlist storage) ·
#           BR-IDN-014 (read-only permission catalog)
# Tests:    06-backend/tests/test_w0_models.py (UNIQUE(tenant_id,email) etc. on the
#           sqlite test DB; RLS assertions = G5 isolation suite, sqlite cannot RLS) ·
#           06-backend/tests/test_us_idn_00*.py (service/API lanes)
# Impacts:  BE-01 membership resolution · BE-04 RBAC checks · US-SHL-013
#           user_preferences FK · every `*_by` actor column across the corpus
# ───────────────────────────────────────────────────────
"""identity models — tables owned per B2 §identity as REWRITTEN by Addendum
r11 / r16 #2 (per-tenant identity): `users` is TENANT-SCOPED with
UNIQUE(tenant_id, email) — the same email in another tenant is a DIFFERENT
user; the §3 no-RLS listing for users is void (r16 #2), so users carries the
standard RLS block (migration 0002_rls_w0_policies, SQL in
06-backend/db/rls_identity_w0.sql).

Eng-Lead disposition (r11 left it open 🔒, recorded in the build report):
`tenant_memberships` STAYS as a thin 1:1 table carrying role + lifecycle
(status/invited/last_active) rather than folding onto users — every W0 story
text (US-IDN-004..007 §5) anchors to `tenant_memberships.*` columns, so the
thin table keeps code and signed story text aligned (LAW 0: boring, literal).

`roles` / `permissions` / `role_permissions` remain PLATFORM catalog tables
(no tenant_id, RLS-exempt per B2 §3; BR-IDN-008: no tenant role CRUD). The 3
predefined roles are seeded in migration 0001. The A4 matrix CELL values
(Full/View/Run/…) have no B2 column — that gap is reported, not invented.

EP-IDN-01/-04 service lanes (2026-08-09, this file as amended): the story-
anchored PROPOSED-SCHEMA shapes now land — `users.failed_attempts` +
`users.locked_until` (US-IDN-001 §5 lockout counter), `sessions` (US-IDN-003
§5: platform table, RLS-exempt — the session must be readable to ESTABLISH
tenant context; bound to one (user, tenant) and validated against the
path-resolved tenant on every request — PO ruling 2026-08-10), and `security_policies`
(US-IDN-010 §5: tenant-scoped, one row per tenant, RLS in migration 0004).
Eng dispositions recorded here, not invented law:
- The session id (uuid7) IS the opaque httpOnly cookie token — US-IDN-003 §4
  anchors "session ids UUID v7; tokens opaque, httpOnly" and no separate
  token column, so none is minted.
- `security_policies.ip_allowlist` is anchored `cidr[]` (Postgres-only type);
  stored as a JSON list of CIDR strings so the two-vendor W0 test lane runs —
  DB-type tightening to cidr[] is a deploy-time follow-up, flagged.
Still out of scope (reported, not built): `auth_tokens` (v2 email-verify
seam) and `sso_links` (v2 — no SSO in v1, BR-IDN-021/OQ-013). BR-IDN-025's
last-5 password-history block has NO anchored storage anywhere (no B2 table,
no §5 column) — reported to the PO batch, not invented; the check is absent.
"""

from typing import Any

from django.db import models
from django.db.models.functions import Lower

from core.dbfields import CITextField, uuid7_pk


#: The platform role catalogue's codes, in the order they were seeded.
#:
#: ⚠ **THREE BECAME FOUR ON 2026-09-05, AND `BR-IDN-008` IS SUPERSEDED FOR THE
#: FOURTH ONE ONLY.** `OQ-WRK-1494` was ruled on 2026-09-04, PO verbatim:
#: *"Field technicians will not logn to web app; they will login to mobile app
#: only; will you keep them in user table?"* — so a field technician is a
#: member of staff with a login like everybody else, and the surface that login
#: may use is a property OF the login. That needs a role to hang the decision
#: on. It is still a PREDEFINED platform role: a tenant cannot create, rename or
#: delete one (`BR-IDN-008`'s actual protection), and this is the only addition
#: any ruling has made.
SYSTEM_ADMIN = "system_admin"
BILLING_CLERK = "billing_clerk"
EXECUTIVE = "executive"
#: `WM-31`, r10's own Users screen: *D. Ortiz · FIELD TECHNICIAN · Work (mobile
#: only)*. It holds NO staff permission — see `A4_MATRIX` below, where every one
#: of the nine rows renders "—" for it because no cell names it.
FIELD_TECHNICIAN = "field_technician"

#: ⚠ **THE TENTH PERMISSION, AND IT IS DELIBERATELY NOT AN A4 ROW.**
#: `OQ-WRK-1492`, ruled 2026-09-04: *"clark can do it sicne it s a day to day
#: work"* — a billing clerk may accept a finished job, because accepting is
#: ordinary daily work and a two-person utility has no supervisor sitting by
#: the screen. So `work_accept` is declared here, seeded into `permissions`, and
#: granted to the three OFFICE roles.
#:
#: It is kept OUT of `A4_MATRIX` because that constant transcribes a SIGNED
#: grid verbatim (`BR-IDN-014`) and a tenth row would make the transcription
#: untrue. The consequence is honest and is written down rather than hidden:
#: Settings › Users & roles renders the nine signed rows and does not yet show
#: this one. Putting it on that screen is a change to a signed artefact and
#: belongs to identity's own story, not to a Work wave.
WORK_ACCEPT = "work_accept"


class Role(models.Model):
    """PLATFORM role catalog — four predefined (A4 addendum's three, settling
    O-5, plus `field_technician` under the 2026-09-04 ruling above)."""

    id = uuid7_pk()
    code = models.TextField(unique=True)  # system_admin | billing_clerk | executive
    name = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "roles"


class Permission(models.Model):
    """PLATFORM permission catalog (B2 §identity) — the 9 A4 matrix rows land
    with US-IDN-007's story lane; the table is its storage."""

    id = uuid7_pk()
    code = models.TextField(unique=True)  # e.g. 'invoice.void'
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "permissions"


class RolePermission(models.Model):
    id = uuid7_pk()
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="role_id")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, db_column="permission_id")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permissions"),
        ]


# ── A4 addendum grid (BR-IDN-014: the matrix must match A4 VERBATIM) ────────
# The 9 permission rows are seeded into `permissions` (migration 0003) and the
# non-"—" cells into `role_permissions`; the CELL VALUES (Full/View/Run/
# Approve/Request/—) have NO B2 column (gap already reported by the W0
# migrations lane, not invented here) — they are rendered from this constant,
# which transcribes the signed A4 addendum grid. Codes are Eng naming, flagged.
# Shape: (permission_code, A4 row label, {role_code: cell}) — "—" cells omitted.
A4_MATRIX: tuple[tuple[str, str, dict[str, str]], ...] = (
    (
        "settings_lookups",
        "Settings & lookup tables",
        {"system_admin": "Full", "executive": "View"},
    ),
    ("user_management", "User management", {"system_admin": "Full"}),
    (
        "plans_rates",
        "Plans & Rates",
        {"system_admin": "Full", "billing_clerk": "View", "executive": "View"},
    ),
    (
        "premises_accounts",
        "Premises / Accounts",
        {"system_admin": "Full", "billing_clerk": "Full", "executive": "View"},
    ),
    (
        "reads_billing_runs",
        "Reads & Billing runs",
        {"system_admin": "Full", "billing_clerk": "Full", "executive": "View"},
    ),
    (
        "payments_record",
        "Payments (record)",
        {"system_admin": "Full", "billing_clerk": "Full", "executive": "View"},
    ),
    (
        "adjustment_approval",
        "Adjustment / write-off approval",
        {"system_admin": "Approve", "billing_clerk": "Request", "executive": "Approve"},
    ),
    (
        "finance_reconcile_export",
        "Finance / reconcile / export",
        {"system_admin": "Full", "executive": "Full"},
    ),
    (
        "reports",
        "Reports",
        {"system_admin": "Full", "billing_clerk": "Run", "executive": "Full"},
    ),
)

# ── A4 AMENDED, 2026-10-02: ONE NARROW READ, AND THE GRID ABOVE DOES NOT MOVE ──
# PO verbatim: *"5. Should a billing clerk see the size lists New Connection
# needs? A · Let the billing clerk read the size and equipment lists (read
# only)."* (`DEF-CUS-9048`; decision log 2026-10-02, top row.) The nine rows
# above stay nine (BR-IDN-014): the clerk still has NO `settings_lookups` cell,
# so every other Settings list and tab stays shut to them. What the ruling adds
# is a READ of exactly the three lists New Connect step 3 reads — and no write.
# Shape: (role_code, permission_row, the lists, the cell). Enforced by
# `core.permissions.NewConnectionLookupRead` / `WorkTemplateListRead`;
# `tests/test_def_cus_9048_clerk_reads_new_connect_lists.py` holds the two equal.
A4_CLERK_READ_GRANTS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "billing_clerk",
        "settings_lookups",
        ("lookups/asset_types", "lookups/service_size_classes", "work/templates"),
        "View",
    ),
)


class User(models.Model):
    """PER-TENANT user (BR-IDN-029, B2 r11): tenant_id NOT NULL + RLS; email
    unique within the tenant only, case-insensitively (citext on Postgres,
    Lower() constraint everywhere — the constraint is the law's teeth)."""

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    email = CITextField()  # PII; sign-in identifier within this tenant (BR-IDN-001)
    full_name = models.TextField(default="")  # renders "—" while invited (US-IDN-004)
    phone = models.TextField(null=True, blank=True)  # PII — as typed, for display
    #: `CR-187-BRC10` (`identity/0013`) — the SAME number in E.164 (`+15125550104`),
    #: the only form a phone sign-in compares (`apps/identity/phones.py`). PO
    #: 2026-10-21: a technician signs in with work email OR phone number. Unique
    #: inside ONE utility (`uq_users_tenant_phone_e164`), never across — sign-in
    #: fixes the utility first (BR-IDN-001). Filled from `phone` on create and on
    #: any save that names `phone`; NULL when there is no phone, it is not a
    #: number, or (from the backfill only) two people at one utility already
    #: shared it — such a number signs in nobody, and those people use email.
    #: `manage.py phone_sign_in_duplicates` lists them for the office.
    phone_e164 = models.TextField(null=True, blank=True)  # PII
    password_hash = models.TextField(null=True, blank=True)  # never raw (BR-IDN-002)
    must_change_password = models.BooleanField(default=False)  # BR-IDN-022 forced change
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)  # +7d (BR-IDN-025)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)  # BR-IDN-025 lockout counter (US-IDN-001 §5)
    locked_until = models.DateTimeField(null=True, blank=True)  # 5 fails → +15 min (BR-IDN-025)
    pending_email = CITextField(null=True, blank=True)  # BR-IDN-017 (v1 admin-only change)
    ui_language = models.TextField(null=True, blank=True)  # per-user override (r15 #4)
    #: ⚠ **WHICH APP THIS LOGIN MAY OPEN — `OQ-WRK-1494`, ruled 2026-09-04,
    #: option (a): a surface scope on the user.** PO verbatim: *"Field
    #: technicians will not logn to web app; they will login to mobile app
    #: only"*. `both` is the default and is what every existing login gets, so
    #: the column changes nothing for anyone until a field technician is
    #: invited. The refusal is served by `services.sign_in`, which is the only
    #: place a surface is known.
    #:
    #: **It is a column and not a second users table**, and that is the other
    #: half of the same ruling — the PO asked *"will you keep them in user
    #: table?"* and the answer recorded in the register is yes: a technician is
    #: invited, deactivated, password-reset and audited exactly like a clerk,
    #: and a second table would fork all four of those flows for one role.
    surface_scope = models.TextField(default="both")  # 'web' | 'mobile' | 'both'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "users"
        constraints = [
            # BR-IDN-029 / DB-13: UNIQUE (tenant_id, email), case-insensitive —
            # US-IDN-005 TC-3 (dup in-tenant rejected) / US-IDN-004 TC-6
            # (same email in two tenants = two users).
            models.UniqueConstraint(
                models.F("tenant"), Lower("email"), name="uq_users_tenant_email_ci"
            ),
            # `identity/0013` — one phone sign-in name per person inside a
            # utility; no phone (NULL) is never a duplicate.
            models.UniqueConstraint(
                fields=["tenant", "phone_e164"],
                condition=models.Q(phone_e164__isnull=False),
                name="uq_users_tenant_phone_e164",
            ),
        ]

    @classmethod
    def from_db(cls, db: Any, field_names: Any, values: Any) -> "User":
        instance = super().from_db(db, field_names, values)
        instance._loaded_phone = getattr(instance, "phone", None)
        return instance

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Derive `phone_e164` from `phone` — on create, and on any save that
        CHANGES `phone` (named in `update_fields`, or a full save after the
        value moved). A save that does not touch `phone` leaves `phone_e164`
        alone, so a backfill-NULLed duplicate is never silently filled by a
        name change. Services check the utility for another holder FIRST
        (`errors.identity.phone_in_use`): an IntegrityError would poison a
        PostgreSQL transaction (hard-won law 14), so the constraint is the
        guarantee and the check is the sentence."""
        from apps.identity.phones import normalise_phone

        update_fields = kwargs.get("update_fields")
        if self._state.adding:
            self.phone_e164 = normalise_phone(self.phone)
        elif update_fields is not None:
            if "phone" in update_fields:
                self.phone_e164 = normalise_phone(self.phone)
                if "phone_e164" not in update_fields:
                    kwargs["update_fields"] = [*update_fields, "phone_e164"]
        elif self.phone != getattr(self, "_loaded_phone", self.phone):
            self.phone_e164 = normalise_phone(self.phone)
        super().save(*args, **kwargs)
        self._loaded_phone = self.phone

    # The auth layer (apps.identity.auth) attaches instances of THIS model as
    # request.user; DRF and core.permissions probe the Django user contract.
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


class Session(models.Model):
    """Server-side session, exactly the US-IDN-003 §5 anchored shape — a
    PLATFORM table (RLS-exempt per that mapping: the row must be readable to
    ESTABLISH tenant context; tenant binding is validated in the auth layer
    against the PATH-resolved tenant (PO ruling 2026-08-10), BR-IDN-006
    one-tenant-per-session — under one origin that check is the ONLY thing
    keeping a tenant-A cookie out of tenant B, so it answers 404, not 403).
    The uuid7 `id` is the opaque httpOnly cookie token (US-IDN-003 §4 —
    Eng disposition: no separate token column is anchored, none minted)."""

    id = uuid7_pk()
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="user_id", related_name="sessions"
    )
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    persistent = models.BooleanField(default=False)  # "Keep me signed in", off by default
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()  # slides on activity (US-IDN-003 TC-4)
    expires_at = models.DateTimeField()  # absolute lifetime cap, 12 h (BR-IDN-026)
    revoked_at = models.DateTimeField(null=True, blank=True)  # server-side, immediate
    ip = models.GenericIPAddressField(null=True, blank=True)  # anchored `inet`
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "sessions"


class PasswordHistory(models.Model):
    """One PREVIOUS password of one user, as a Django password hash — never
    the password itself (BR-IDN-025's last-5 block, `DEF-IDN-10023`, PO ruling
    2026-10-08: *"go - build the last 5 passwords check"*).

    HUMAN-REVIEW-PENDING — 🔒 identity/credentials, AI-authored 2026-10-08;
    row in `12-governance/09-human-review-ledger.md`.

    ⚠ **A TABLE AND NOT A COLUMN ON `users`, AND THAT IS THE LAWFUL SHAPE
    RATHER THAN THE TIDY ONE.** A JSON list of hashes on the user row would
    be one more thing every `users` write re-serialises, and would need its
    own pruning arithmetic inside a JSON value. A row per previous password
    is append-and-prune, carries its own `created_at`, and takes the B2 §3
    RLS block exactly as every other tenant table does (`identity/0010`,
    ENABLE + FORCE, the `NULLIF` form) — hard rule 1.

    **What goes in:** the hash a user is LEAVING, when it was one they chose.
    A system-generated temporary password is never recorded — it is random,
    nobody will choose it again, and recording it would spend one of the five
    slots on a password the person never picked.
    **How many stay:** `services.PASSWORD_HISTORY_BLOCK` (5), pruned on every
    write; the CURRENT password lives on `users.password_hash` and is checked
    beside these, so a change refuses the current one and the five before it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", related_name="password_history"
    )
    password_hash = models.TextField()  # Django hasher output — never raw (BR-IDN-002)
    created_at = models.DateTimeField()  # when this password STOPPED being current

    class Meta:
        db_table = "password_history"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="ix_password_history_user"),
        ]


class SecurityPolicy(models.Model):
    """Tenant security policy — US-IDN-010 §5 anchored shape: one row per
    tenant (UNIQUE(tenant_id) via OneToOne), RLS + FORCE in migration 0004.
    Column defaults ARE the BR-IDN-025/026 seed defaults; a tenant without a
    row is served exactly these values (read side never writes).
    `ip_allowlist`: anchored `cidr[]` is a Postgres-only type — stored as a
    JSON list of IPv4 CIDR strings (Eng disposition, see module docstring)."""

    id = uuid7_pk()
    tenant = models.OneToOneField(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant",
        on_delete=models.PROTECT,
        db_column="tenant_id",
        related_name="security_policy",
    )
    pw_min_length = models.IntegerField(default=8)  # ∈ {8,10,12} (BR-IDN-025)
    pw_require_mixed = models.BooleanField(default=True)  # upper+lower+number (BR-IDN-025)
    pw_require_symbol = models.BooleanField(default=False)  # optional (BR-IDN-025)
    pw_expiry_days = models.IntegerField(null=True, blank=True)  # ∈ {null,90,180}; null=Never
    session_timeout_minutes = models.IntegerField(default=60)  # ∈ {15,30,45,60} (BR-IDN-026)
    # ── CR-145-BRC08 · the five that turned from platform constants into the
    # utility's own choice (PO ruling 2026-09-28, *"Im okay with these limit"*;
    # BR-IDN-025 lockout half, BR-IDN-026 session half).
    #
    # ⚠ **EVERY DEFAULT HERE IS TODAY'S FIXED VALUE, AND THAT IS THE POINT.**
    # `services.py` carried each of these as a named constant, so a utility
    # that never opens the Security tab must behave on the day this ships
    # exactly as it did the day before. The only value that moves is
    # `session_timeout_minutes`, and it moves by DATA MIGRATION rather than by
    # a default: 240 and 480 are withdrawn from the choices, and `identity/
    # 0007` moves the utilities sitting on them to 60 with an audit row each.
    #
    # ⚠ **THE LIMITS ARE NOT HERE.** A column default is what a NEW row gets;
    # what an admin may CHOOSE is `services.SETTING_LIMITS`, in one place, read
    # by the validator and served to the front end by `security_policy_values`
    # so no screen keeps its own copy.
    absolute_session_hours = models.IntegerField(default=12)  # 4..12 (BR-IDN-026)
    keep_signed_in_offered = models.BooleanField(default=True)  # on/off (BR-IDN-026)
    keep_signed_in_days = models.IntegerField(default=30)  # 1..30 (BR-IDN-026)
    lockout_max_failed = models.IntegerField(default=5)  # 3..10 (BR-IDN-025)
    lockout_minutes = models.IntegerField(default=15)  # 5..60 (BR-IDN-025)
    ip_allowlist = models.JSONField(default=list, blank=True)  # [] = unrestricted (BR-IDN-020)
    # ── The field app's capture life (PO 2026-10-21, *"this should come from
    # settings"*; decision log *"Field app: the PO corrects four of the ten
    # answers"* item 2). How long a phone keeps capturing — and renewing its
    # bearer sign-in — without a password. HOURS, default 168 = the 7 days
    # `BR-WRK-060` signed, so nothing moves the day it ships (`identity/0012`).
    # Read by `apps/work/mobile.capture_token_max_age_s` and
    # `apps/identity/native.refresh_token_max_age_s`; the choices are
    # `services.SETTING_LIMITS["field_capture_hours"]`.
    field_capture_hours = models.IntegerField(default=168)
    # ── How long an emailed one-time sign-in link stays valid, in DAYS
    # (`CR-188-BRC10`, PO 2026-10-22: *"don't do any hardcoding"* — *"How long a
    # link stays valid is a setting, with today's value (7 days, BR-IDN-025) as
    # its seeded default"*). Read by `password_links.link_valid_days`; the
    # choices are `services.SETTING_LIMITS["password_link_valid_days"]`.
    password_link_valid_days = models.IntegerField(default=7)
    # ── The field app's certificate pins (`OQ-FLD-12797`, PO 2026-10-24:
    # *"plese dont hardcode it use settings - security values set in staff
    # portal"*). A JSON list of `{spki_sha256, label, not_after, active}`.
    # **NULL means "this utility has never edited the list"** and is served the
    # platform's default set (`settings.FIELD_APP_DEFAULT_PINS`) — so a utility
    # that never opens the card behaves exactly as the build it ships with, and
    # the platform can rotate the default for every utility that has not taken
    # the list over. Validated and written only by `field_pins.save_pins`.
    field_app_pins = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "security_policies"


class TenantMembership(models.Model):
    """Thin 1:1 membership row (Eng disposition on r11): role + lifecycle for
    exactly one (tenant, user). Status flow invited→active→deactivated is the
    US-IDN-005/006 service lanes' law; these are their columns."""

    STATUS_INVITED = "invited"
    STATUS_ACTIVE = "active"
    STATUS_DEACTIVATED = "deactivated"

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    user = models.ForeignKey(User, on_delete=models.PROTECT, db_column="user_id")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="role_id")
    status = models.TextField(default=STATUS_INVITED)  # BR-IDN-011
    invited_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(  # PROTECT: referenced users are audit-locked (IS-1)
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="invited_by",
        related_name="memberships_invited",
    )
    last_active_at = models.DateTimeField(null=True, blank=True)  # null renders "Never"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_memberships"
        constraints = [
            # r11: memberships are 1:1 per (tenant, user).
            models.UniqueConstraint(fields=["tenant", "user"], name="uq_tenant_memberships"),
        ]



# ══════════════════════════════════════════════════════════════════════════
# CR-187-BRC10 · THE NATIVE FIELD APP'S SIGN-IN (Security §1, AD-21, N24)
#
# HUMAN-REVIEW-PENDING — 🔒 identity/credentials + RLS (hard rule 1), AI-authored
# 2026-10-21 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
# it later as human"*). The review-ledger row is owed by the coordinator (this
# lane may not edit shared registers); not RATIFIED without a sign-off.
# ══════════════════════════════════════════════════════════════════════════
class NativeToken(models.Model):
    """One bearer credential of the native field app — an ACCESS token (one
    hour) or a REFRESH token — stored as a SHA-256 digest, never in the clear.

    ⚠ **ADDITIVE: THE WEB'S COOKIE SESSION IS UNTOUCHED.** A browser still signs
    in at `POST auth/session` and lives in `sessions`. This table exists because
    a native app cannot hold an httpOnly cookie and the design splits the job in
    two (Security §1): the access token authorises TALKING TO THE SERVER and
    nothing else, so its expiry is normal and uneventful.

    ⚠ **UNLIKE `sessions`, THIS TABLE CARRIES RLS + FORCE (`identity/0011`).**
    `sessions` is RLS-exempt because it is read before a tenant is known. A
    native token never is: it is presented only on `/api/{tenant}/…` paths, and
    the plaintext names its tenant (`native.TOKEN_FORMAT`), so the auth class
    compares that tenant with the path's BEFORE it reads a row — a mismatch is
    the 404 `BR-IDN-006` demands — and then reads under the path tenant's own
    context. No new exemption was needed, and none was taken.

    **A FAMILY is one sign-in.** Every refresh marks the refresh token it spent
    (`used_at`) and mints a new access + refresh pair in the same family. A
    spent refresh token presented AGAIN is the signature of a stolen copy, so
    the whole family is revoked (`revoked_reason = refresh_reuse`).

    **`device_uid` is the handset's own id** (the app's `deviceId`), not a key
    to work's `technician_devices` — identity must not import work. The office's
    remote sign-out (work) revokes by `(tenant, device_uid)` through
    `native.revoke_device`, and that reason is what the phone is told
    (`params.reason = device_signed_out`, `native_auth.py`).
    """

    KIND_ACCESS = "access"
    KIND_REFRESH = "refresh"
    KINDS = (KIND_ACCESS, KIND_REFRESH)

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", related_name="native_tokens"
    )
    family_id = models.UUIDField()
    kind = models.TextField()  # access | refresh
    #: SHA-256 hex of the plaintext. 256 random bits, so a plain digest is the
    #: right hash and a slow KDF would buy nothing (reports' service-account
    #: tokens make the same choice and say why).
    token_hash = models.CharField(max_length=64, unique=True)
    device_uid = models.TextField()
    #: What the technician called this handset at activation (*Van 14 tablet*).
    device_name = models.TextField(default="")
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    #: A REFRESH token is single-use: set when it is spent.
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    #: signed_out | device_signed_out | refresh_reuse | password_changed | ""
    revoked_reason = models.TextField(default="")
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "native_tokens"
        indexes = [
            models.Index(fields=["tenant", "device_uid"], name="ix_native_tokens_device"),
            models.Index(fields=["family_id"], name="ix_native_tokens_family"),
            models.Index(fields=["user", "revoked_at"], name="ix_native_tokens_user_live"),
        ]


class ActivationCode(models.Model):
    """FF-56 *First time here* — the six-character code the office hands a
    technician so the app can CLAIM an account that already exists (`R105`:
    *"the office creates the account; the app only claims one that exists, with
    a code that expires"*). Technicians never self-register.

    Good for seven days (FF-56, *"It lasts seven days"* — the same 7 as
    `TEMP_PASSWORD_VALID_DAYS`, which is the signed figure for an office-issued
    first credential), single use (`used_at`), and burnt after
    `native.ACTIVATION_MAX_FAILED` wrong emails against it. Issuing a new one
    voids every earlier unused code of the same user.

    ⚠ **THE CODE IS STORED AS AN HMAC, NEVER IN THE CLEAR.** A six-character
    code from a 31-letter alphabet is ~887 million values — enough to be
    unguessable through a rate-limited door, too few to survive a stolen table
    if stored plainly or as a bare digest. The HMAC is keyed with the server's
    `SECRET_KEY` and the tenant, so a dump of this table without the key gives
    nothing to brute-force offline.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", related_name="activation_codes"
    )
    code_hmac = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    issued_by = models.UUIDField(null=True, blank=True)  # the office user; no FK, audit names them
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)

    class Meta:
        db_table = "activation_codes"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code_hmac"], name="uq_activation_codes_tenant_code"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "used_at"], name="ix_activation_codes_user"),
        ]


class ActivationCodeRegister(models.Model):
    """EVERY ACTIVATION CODE EVER ISSUED, ON EVERY UTILITY — `DEF-FLD-10580`
    (beta report MQ-006), PO 2026-10-24: *"A. The code from the office sets the
    utility … but how will you ensure the code is always unique?"*

    The field app is ONE build for every utility. A technician types the code
    the office gave them and the code alone says which utility they work for
    (`POST /api/auth/activation/lookup`). That only works if no two utilities
    ever hold the same code, so this table carries a DATABASE UNIQUE
    constraint on the code's digest: when Brookfield's random draw lands on a
    code Houston already holds, the INSERT is refused and a new code is drawn
    (`native.issue_activation_code`, inside a savepoint — hard-won law 14).

    ⚠ **IT IS NOT A TENANT TABLE AND CARRIES NO RLS POLICY, ON PURPOSE** — the
    lookup happens before any utility is open, so a tenant policy would make
    every valid code read as unknown (law 7, *incapable of passing*). It is
    `integration_key_directory`'s class: declared in `core.rls_guard.
    TENANT_TABLE_EXEMPTIONS`, `tests/isolation_helpers.RLS_EXEMPT_TABLES` and
    B2 §3. **What it holds is why it may be exempt**: a keyed one-way digest
    (HMAC under the server secret, NOT per tenant — a per-tenant key would make
    the same code two different digests and the constraint could not see the
    clash), the utility's id and a timestamp. No code, no user, no name, no
    email. And it AUTHORISES nothing: the lookup then reads the tenant's own
    `ActivationCode` row under that tenant's RLS context, and only a live row
    answers.

    ⚠ **ROWS ARE NEVER DELETED.** A code is never reused, even after it
    expires, is used or is voided — a code a technician wrote down last month
    must never start naming somebody else's utility.
    """

    id = uuid7_pk()
    #: HMAC-SHA256 under the server secret of the normalised code — unique.
    code_digest = models.CharField(max_length=64)
    #: The utility that holds the code. Deliberately no FK: the row must be
    #: readable before any utility is open, and it names nothing else.
    tenant_id = models.UUIDField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = "activation_code_register"
        constraints = [
            models.UniqueConstraint(
                fields=["code_digest"], name="uq_activation_code_register_digest"
            ),
        ]



class PasswordLink(models.Model):
    """A ONE-TIME SIGN-IN LINK emailed to a member of staff — `CR-188-BRC10`.

    PO 2026-10-22, answer 1: *"email a one-time sign-in link instead, no
    password."* A System Admin's *Create user*, *Reset temp password* and
    *Resend invitation* each issue one; the person opens it and sets their OWN
    password on `/{tenant}/set-password`. The on-screen temporary password is
    issued beside it exactly as before (BR-IDN-022/023) — the two coexist.

    ⚠ **ONLY A SHA-256 DIGEST IS STORED.** The plaintext is 256 random bits, so
    a plain digest is the right hash (`NativeToken`'s reasoning) and a dump of
    this table opens nothing.

    **Seven days** — `TEMP_PASSWORD_VALID_DAYS`, the signed life of an
    office-issued first credential (BR-IDN-025). **Single use** (`used_at`).
    **Void** (`revoked_at` + `revoked_reason`) when a newer link is issued, when
    the temporary password is reset, or when the password is changed by any
    other route — a link left live after the person has already chosen a
    password would let whoever reads the mailbox later choose another.

    RLS + FORCE (`identity/0014`); read on the public door UNDER the path
    tenant's own context, like `activation_codes`.
    """

    PURPOSE_INVITE = "invite"
    PURPOSE_RESET = "reset"
    PURPOSES = (PURPOSE_INVITE, PURPOSE_RESET)

    REVOKED_SUPERSEDED = "superseded"
    REVOKED_PASSWORD_CHANGED = "password_changed"

    id = uuid7_pk()
    tenant = models.ForeignKey(  # ⚠ cross-module → tenancy (B2 §2 reviewed FK set)
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", related_name="password_links"
    )
    purpose = models.TextField()  # invite | reset
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    issued_by = models.UUIDField(null=True, blank=True)  # the System Admin; audit names them
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.TextField(default="")

    class Meta:
        db_table = "password_links"
        indexes = [
            models.Index(fields=["user", "used_at"], name="ix_password_links_user"),
        ]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-004@9d61512 (story+rules snapshot hash — EP-IDN-02 lead story of the W0 migrations lane)
# packet: US-IDN-001@402b6db + US-IDN-003@402b6db (EP-IDN-01) · US-IDN-010@493ea2f (EP-IDN-04) — amended 2026-08-09 by the EP-IDN service lanes (lockout columns · sessions · security_policies)
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations lane; amended same day by the identity W0 feature-story lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B=deferred(auth/list/service TCs live in tests/test_us_idn_*.py with the service lanes) C✔ D=deferred(API half in api.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: ruff NOT run (not in verify list) · py_compile✔ · pytest tests -m "not golden and not isolation" 323-green-0-fail at handoff (180-test baseline + 69 active identity-lane tests + concurrent tenancy lane in the shared tree) · run_gates 11-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: memberships-vs-fold-onto-users = Eng disposition recorded (thin table kept) · A4 matrix cell values have no B2 column — rendered from the signed A4 grid constant, gap reported not invented · session id = cookie token (no token column anchored) · ip_allowlist JSON-list vs anchored cidr[] (two-vendor lane) · last-5 password-history block has NO anchored storage — reported, check absent · auth_tokens/sso_links = v2 seams, not built · [path-tenancy lane 2026-08-10] docstrings only — the Session/`sessions` tenant binding is unchanged SCHEMA and newly LOAD-BEARING: under one origin it is the sole thing keeping a tenant-A cookie out of tenant B, and the auth layer now answers that mismatch 404 rather than 401
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
