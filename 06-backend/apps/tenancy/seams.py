# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001 (owner user via identity — EP-TEN-03 §Provisioning) ·
#           US-TEN-002 (cross-module reference seeding) · US-TEN-003 (checklist
#           live counts) · US-TEN-006 (currency-lock probe) · US-TEN-007/008
#           (disable-guard / used-by counts) · US-TEN-010/011 (owning-module
#           lookup content)   Screens: S114, S62, S8
# Rules:    BR-TEN-013 (writes via owning-module service functions only) ·
#           BR-TEN-031 (framework vs content ownership) · BR-TEN-029 (used-by
#           live via owning-module fns) · BR-TEN-026 (disable guard counts) ·
#           BR-TEN-042 (currency locked once a financial record exists)
# Tests:    06-backend/tests/test_us_ten_001_004_provisioning.py (stubbed seams +
#           skip-until-wired integration TCs) · each story test file re-stubs
# Impacts:  apps.identity (provision_owner et al — authored by the identity lane) ·
#           apps.rating / apps.billing / apps.payments / apps.metering /
#           apps.customers (seed + count functions, authored by their lanes)
# ───────────────────────────────────────────────────────
"""tenancy → other-module SEAMS: every cross-module call this module makes.

B1/BR-TEN-013: tenancy NEVER touches another module's ORM. Everything tenancy
needs from a neighbor is one of the documented callables below, resolved AT
CALL TIME from `apps.<module>.services`. While a neighbor's function is not
yet authored (concurrent lanes), the seam reports "not wired" and the caller
takes the documented fallback; integration tests against the real functions
are marked skip-until-wired.

Documented contracts (the owning lanes implement these signatures):

  apps.identity.services.provision_owner(
      *, tenant_id, email, full_name, password, phone) -> owner_user_id
    Creates the per-tenant owner user + System Admin membership INSIDE the
    caller's open provisioning transaction (BR-IDN-029: same email elsewhere
    is a different user; role per A4). REQUIRED — an owner-less tenant would
    be half-seeded (BR-TEN-001), so provisioning refuses without it.

  apps.identity.services.start_owner_session(
      *, tenant_id, user_id, ip=None, user_agent=None) -> session_id: str
    Opens the owner's first session, INSIDE the same provisioning transaction,
    and returns its id — the httpOnly cookie value POST /api/tenants sends
    back (PO ruling 2026-08-10: path tenancy supersedes BR-TEN-045's
    success-screen handoff, so the owner is signed in at commit). OPTIONAL:
    while unwired, provisioning still succeeds and simply hands back no
    session — the tenant is live and the owner signs in at
    /{subdomain}/signin, which is exactly the superseded flow.

  apps.identity.services.owner_email_for(tenant_id) -> str | None
    The provisioning owner's email, for the BR-TEN-010 replay check (same
    subdomain + same owner email = idempotent replay). Called under the
    existing tenant's context. REQUIRED on the replay path.

  apps.identity.services.owner_user_id_for(tenant_id) -> uuid | None
    The provisioning owner's USER ID — the same row `owner_email_for` names.
    Added 2026-08-16 for the sample-data repair path (DEF-153): a command-line
    load has no session, and every service it drives writes an `audit_log` row
    that must say who asked (CLAUDE.md rule 7). None while unwired, and the
    load still runs with an unattributed trail rather than an invented user.

  apps.identity.services.member_count() -> int
    Members of the current-context tenant (S62 "Invite your team" item).

  apps.identity.services.seed_security_policy(actor) -> dict | None
    **CR-011 item 8, which the PO delegated outright** (*"you decide"*, PO
    2026-08-18). The tenant's `security_policies` row, written at provisioning
    at the ratified BR-IDN-025/026 defaults — minimum length 8, upper+lower+
    number required, symbol optional, expiry never, idle timeout 60 minutes, no
    IP restriction. OPTIONAL and idempotent (get_or_create), inside the open
    transaction, exactly like `seed_notification_settings`.

    **Nobody's policy changes**: `identity.selectors.security_policy_values`
    already served those figures from an UNSAVED model instance when no row
    existed, and it still does, which is what makes this safe and what makes it
    the repair path for every tenant provisioned before today. What changes is
    that the figures become DATA. An unwritten row means a tenant's password
    rule is a Python constant, so moving BR-IDN-025's ratified minimum would
    change the effective policy of every tenant that never opened the Security
    tab — with no author, no before/after and no `audit_log` row, because
    nothing was ever saved. It also made *"which tenants have configured
    security?"* unanswerable: 0 rows meant "never looked", indistinguishable
    from nothing.

  apps.<owner>.services.seed_reference_list(list_code, entries, fixture_version) -> int
    Owner modules: rating (charge_codes, tax_jurisdictions) · billing
    (reason_codes) · payments (payment_methods) · metering (meter_types,
    read_methods, asset_types, asset_statuses — routed on to apps.assets) ·
    customers (account_statuses, account_types — NOT AUTHORED, see below).
    Upsert-by-code into the OWNER's tenant-scoped lookup tables;
    tenant-touched rows never overwritten (BR-TEN-012); returns rows created.

    An unwired owner still SKIPS its list (BR-TEN-013) — but since DEF-016 the
    skip is no longer swallowed: `apps.tenancy.services.
    UNSEEDABLE_REFERENCE_LISTS` must carry the reason, and
    `reference_data_report()` marks an unregistered empty list UNEXPLAINED,
    which makes `seed_demo` exit non-zero. Wiring a seam is how you REMOVE an
    entry from that register; writing the reason down is how you keep one.

  apps.<owner>.services.reference_seed_omissions(list_code, entries)
      -> list[{"entry": str, "reason": str}]
    OPTIONAL, read-only, no writes. The fixture entries the owner will NOT
    create, and why — e.g. rating refuses a charge code the fixture carries
    with no amount and no percent, because `create_charge` requires an
    amount_rule and one cannot be chosen without a figure. Unwired ⇒ [] and the
    caller simply reports nothing extra. This is the per-ENTRY half of DEF-016's
    "say what did not land"; `seed_reference_list`'s int is the per-LIST half.

  apps.rating.services.seed_sample_records() -> int
  apps.metering.services.seed_sample_records() -> int
  apps.assets.services.seed_sample_records() -> int
  apps.customers.services.seed_sample_records() -> int
  apps.metering.services.seed_sample_reads() -> int
    US-TEN-019 / BR-TEN-056: the SAMPLE-DATA blocks. Named one module at a time
    rather than as `apps.<owner>.…` on purpose — G20 harvests these lines, and a
    placeholder would leave four of the five contracts invisible to the gate
    that exists to notice an undelivered seam (DEF-075). Rating seeds plans +
    rate schedules (tagged and PROMOTED per BR-TEN-068) · metering the premises,
    units and service points — and, separately, the meter reads · assets the
    meters and their assignments · customers the accounts, customers, contacts,
    addresses and service agreements, seeded NON-BILLABLE per BR-TEN-065.
    Each creates its own rows under the caller's tenant context, **every one
    tagged `is_sample = true`**, and returns how many it wrote.

    NOT ONE OF THESE IS AUTHORED, and the reason is not "the lane has not got
    to it" — it is that the tag has no home yet. BR-TEN-057 puts
    `is_sample boolean NOT NULL DEFAULT false` on the OWNING row, and the rows
    it names (`premises`, `units`, `service_points`, `assets`,
    `asset_assignments`, `meter_reads`) are metering's and assets'. Tenancy may
    not add a column to another module's table (B1 boundary rule, BR-TEN-013),
    and BR-TEN-057 says the same thing from the other side: the tag is written
    *"only by that module's own service function on the sample path, never by
    tenancy directly"*.

    Unwired ⇒ `apps/tenancy/sample_data.py` records
    `sample_data_runs(module, outcome='skipped', reason_code='seam_not_wired')`
    and S62 renders that module BY NAME (BR-TEN-060). It NEVER substitutes a
    count and the run NEVER reports success — DEF-016 was a skip that went into
    a summary nobody read, and this is the shape that ends it. Parked in
    10-scripts/gates/seam_known_gaps.txt with `absent=` guards on the very
    columns BR-TEN-057 names, so the park EXPIRES the minute one arrives.

  apps.metering.services.seed_sample_records_note() -> str | None
    **THE NOTE A BLOCK THAT SUCCEEDED STILL OWES A PERSON — DEF-3224.**
    OPTIONAL, read-only, no writes, and named `<seam>_note` so
    `apps/tenancy/sample_data.py` can resolve one for ANY block without a
    dispatch table: `seams.resolve(module, f"{seam}_note")`.

    The gap it closes is not a failure — it is a SUCCESS that hid a whole
    service. A block that FAILS has carried a sentence to the Sample data panel
    since CR-039 wave B. A block that SUCCEEDS could not: `sample_data.py`
    recorded `detail=None` on every seeded block. So when a utility ticked
    Electric, Water and Sewer, the estate correctly took ONE metered backbone,
    water won it, and **electric got no service point, no meter, no read and no
    line on any of the 95 issued bills — not even its `$12.00` monthly base,
    `$576.00` a month across 48 units** — while 0 of 17 blocks failed and every
    surface was green. The seeder composed a correct sentence naming electric
    and why, and sent it to `logger.info`.

    Metering implements it today; every other module may and none must. Unwired
    ⇒ no note, which is byte-for-byte what every block did before this existed.
    The caller treats a raise as "no note" and logs it: narration must never
    fail a seeding run. The returned sentence is rendered to a utility user, so
    it goes through `apps.tenancy.sample_notes.for_screen` first — B14 rule 31
    keeps rule ids, module paths and file names off a screen.

  apps.<owner>.services.remove_sample_records() -> dict
    The other half (BR-TEN-061/066): a HARD delete of that module's
    `is_sample = true` rows in the fixed reverse-dependency order, returning the
    rows it RETAINED and why — BR-TEN-066 (PO 2026-08-10) is partial-and-named,
    *"remove what is free, report the rest BY NAME"*. Unwired for the same
    reason as its twin, and `sample_data.removal_plan()` answers "nothing, and
    here is why" rather than an empty success.

  apps.rating.services.rate_schedule_count(service_code=None, uom_code=None) -> int
    Live count of rate schedules referencing a service and/or priced in a UoM
    (BR-TEN-026 disable guard · BR-TEN-027 change warning · BR-TEN-029).

  apps.customers.services.active_account_count(service_code) -> int
    Live count of active service agreements per service (BR-TEN-026).
  apps.customers.services.active_account_counts() -> dict[str, int]
    The same live count for EVERY service in one pass, keyed by code — what the
    S8 table reads (`DEF-TEN-8731`: once per service was 11 passes over the
    estate, killed at 60 s at 40,000 accounts).

  apps.billing.services.financial_records_exist() -> bool
  apps.payments.services.financial_records_exist() -> bool
    BR-TEN-042 currency-lock probe. **BOTH ARE LIVE since 2026-08-11** — payments
    since W4, billing since DEF-075.

    The paragraph that stood here said an unwired module *"stores nothing yet, so
    it can hold no financial record — unwired == False BY CONSTRUCTION"*. That
    reasoning was sound the day it was written and became FALSE the day billing
    got `invoices`: the module then held financial records and still published no
    probe, so the fallback that was "honest by construction" started reporting
    False over issued bills. A tenant with a year of bills and no payments could
    re-denominate its books, measured live at 200 OK.

    The correct reading of a None here is therefore *"this module cannot answer"*,
    never *"this module has nothing"* — and the two stop being the same sentence
    the moment a module grows tables. A seam whose safety depends on a neighbour
    never being built needs a check that notices when it is (DEF-075's prevention
    column).

  apps.ledger.services.seed_chart_of_accounts(actor) -> dict | None
    The chart of accounts (B5 line 74, ❄️ finance-signed, plus 4160/4170 which
    are NOT — OQ-115) + the eleven GL designations (PO ruling 2026-08-11,
    OQ-110), seeded into the ledger's own tables at provisioning —
    US-LED-005 TC-1. OPTIONAL and idempotent: insert-missing only, never
    overwriting a tenant's later edit. Called from provisioning INSIDE the open
    transaction. **It seeds the SHARED accounts** — cash, AR, the liabilities,
    opening clearing, the minimum-bill adjustment, fee revenue and the expense
    rows — and the per-service revenue accounts of whatever services the tenant
    already sells, which at provisioning is none (PO ruling 2026-08-11: *"every
    Utility may not have all the services"*). The per-service accounts arrive
    through the next seam, as each service is switched on. **The old ordering
    constraint is therefore GONE**: this call no longer has to precede
    `_enable_signup_services` for a service to get its account. An unwired
    ledger leaves the chart empty and every service's `revenue_account` NULL —
    provisioning still commits, and the gap surfaces at issue where BR-BIL-010
    refuses an unmapped line rather than guessing an account.

  apps.ledger.services.ensure_service_revenue_accounts(service_code, actor)
      -> (revenue_account_id | None, base_revenue_account_id | None)
    MINTS this service's revenue accounts if the tenant does not have them, then
    answers their ids (BR-BIL-010: revenue required, base OPTIONAL — the chart
    splits Electric 4100/4105 and Water 4110/4115 only). Called by BOTH paths
    that switch a service on, signup and the S8 toggle, so a water-only utility
    that enables Gas gets 4140 minted at that moment (PO ruling 2026-08-11,
    OQ-115). Resolved by the LEDGER because the accounts are the ledger's;
    tenancy stores the two uuids on its own row, and they are a DEFAULT the
    tenant may re-point afterwards. `(None, None)` while the ledger is unwired,
    for a service no chart line names, and for an account the tenant has
    deactivated — nothing resurrects a row a tenant retired.

  apps.billing.services.seed_bill_templates(actor, on_date) -> dict | None
    **DEF-123 — the row without which NO TENANT CAN ISSUE A BILL.** Billing's
    fallback bill template (BR-BIL-025) and its published version (BR-BIL-026),
    seeded into billing's own tables at provisioning, inside the open
    transaction. OPTIONAL and idempotent, insert-missing, exactly like
    `seed_chart_of_accounts` — a re-run is a repair run and never overwrites a
    tenant's own edit.

    Until 2026-08-16 this seam did not exist and nothing else created the row.
    `bill_templates` / `bill_template_versions` landed on 2026-08-15 with a
    complete lifecycle service and passing tests **against rows the tests
    created**; in the product `templates_service.resolve_for` refused *"this
    tenant has no bill template … and no fallback"* for every tenant, and
    BR-BIL-026 makes the pin non-optional, so every bill run refused at issue on
    every deployment. Nothing in this repository had ever asked whether a
    REQUIRED per-tenant row has any way of coming into existence — G13 catches
    code unreachable from CODE, and this was code unreachable from DATA. G26 is
    the gate that now asks.

    An unwired billing leaves the tenant with no template, provisioning still
    commits, and the gap surfaces at issue where BR-BIL-025 refuses with the
    rule's own sentence rather than a guessed pin — **and G26 fails the build**,
    which is the difference between this seam and one whose absence is merely
    reported.

    `on_date` is BR-TEN-043's business date and is the CALLER's: it lands on
    `bill_template_versions.published_on` and there is no clock in billing.

  apps.notifications.services.seed_notice_templates(actor, on_date) -> dict | None
    **DEF-163 — the rows without which NO TENANT CAN SEND A NOTICE.** The
    platform-authored notice bodies (`dunning` and `receipt`, both quoted
    verbatim from A13) and their published versions, seeded into notifications'
    own tables at provisioning, inside the open transaction. OPTIONAL and
    idempotent, insert-missing — the same contract `seed_bill_templates` and
    `seed_chart_of_accounts` hold, and a re-run is a repair run that never
    overwrites a body somebody edited.

    Until 2026-08-16 this seam did not exist and nothing else created the rows.
    `notification_templates` / `notification_template_versions` landed on
    2026-08-15 with a complete register → publish → archive lifecycle and
    passing tests **against rows the tests created**; in the product
    `template_service.resolve` refused *"no published 'dunning' template
    resolves for category 'default' in language 'default'"* for every class on
    every tenant, so every dunning letter and every disconnect notice was
    REFUSED at render rather than queued. DEF-123's shape, one module along —
    and G26 could not see it, because its discovery clause keyed on the OTHER
    module's phrasing (that is now widened; see `g26_required_rows.py`).

    ⚠ **THE RESULT REPORTS TWO HALVES AND BOTH MATTER.** `seeded` names what
    landed; `absent` names every class this platform has NO body for, with its
    reason and its OQ — the disconnect notice (OQ-243: A19 §2 gives three tier
    bodies and a variant holds one), the payment-plan agreement (OQ-244), and
    the email/SMS/contract/plan-notice catalogues (OQ-206/OQ-207). A caller that
    printed only the first half would report a full library over a tenant that
    still cannot send a disconnection notice.

    An unwired notifications leaves the tenant with no notice templates,
    provisioning still commits, and the gap surfaces at generation where
    `template_service.resolve` refuses with the rule's own sentence rather than
    an invented body.

  apps.notifications.services.queue_staff_alert(...) -> dict
    **DEF-3422 — THE CONTRACT WAS WRITTEN ON NEITHER SIDE, WHICH IS WHY IT WAS
    NEVER BUILT.** C-15 (PO 2026-08-17, ruling 15: *"soft: flag on the S62
    checklist + alert support, tenant still opens"*) gives the completeness
    check three limbs, and the third is an alert to the people who look after
    the utility. `sample_data.completeness_check` resolved this name from the
    day it was written and got `None` every time; the audit row it wrote said
    so honestly — *"not delivered — apps.notifications.services publishes no
    staff-alert seam"* — and nothing else in the repo said the seam was owed.
    DEF-251 recorded this exact failure shape in the other direction (the
    contract written on the callee and on no caller, so no gate could see it);
    this entry is the caller's half.

    Takes the run's own facts and NOTHING a clerk cannot read: `actor` (the
    person or job that raised it), `operation` (a human phrase, never a module
    name or a reason code — B14 rule 32), `operation_id` (the run's own id, so
    a retry says it once — rule 6), `total_count`, `failed_count`, and
    `finished_at` (a PARAMETER, never a clock read — BR-TEN-043).

    OPTIONAL, and the whole point of C-15 is what happens when it is missing:
    an unwired notifications leaves the tenant open, the setup screen still
    naming every part that did not load, and the audit row still recording that
    nobody was told. The alert is the third limb, never the first.

  apps.ledger.services.account_is_live(account_id) -> bool
    Is that id a LIVE account of THIS tenant's chart? REQUIRED on the GL
    override path (PO 2026-08-11: *"allow tenant user to override it"*): the
    cross-module FK constrains existence, never ownership, so without this a
    tenant could point a service at another tenant's account. Refuses loudly
    while unwired rather than accepting an unvalidated pointer — the unsafe
    option must be the one you type (hard-won law 3).

  apps.metering.services.uom_used_by_count(uom_code) -> int
    The meters.unit half of the UoM used-by definition (BR-TEN-029); the
    tenant_services half is tenancy-owned and counted locally.

  apps.billing.services.reason_code_used_by_count(code) -> int
  apps.payments.services.payment_method_used_by_count(code) -> int
    BR-TEN-029 used-by for the two reference lists tenancy HOSTS but does not
    own (see the ReasonCode/PaymentMethod model docstrings). Reason codes are
    referenced by adjustments/correction cases (BR-BIL-014), payment methods
    by payments (BR-PAY-012/026) — none of those tables exists yet, so the
    honest count is 0 BY CONSTRUCTION, exactly like uom_used_by_count. The
    consequence is stated once here so nobody reads it as a bug: while these
    return 0, BR-TEN-030 (code frozen once used) and BR-TEN-034 (a used row
    cannot be deleted) cannot bite for these two lists — but BR-TEN-036 still
    does, so no SEEDED row is deletable in the meantime.
"""

from collections.abc import Callable
from importlib import import_module
from typing import Any


class SeamNotWired(RuntimeError):
    """A REQUIRED cross-module service function is not authored yet.

    Raised only where no honest fallback exists (owner-user creation, replay
    ownership check). Surfaces as SYS-INTERNAL through the BE-02 envelope —
    loud by design: proceeding would mint a half-seeded tenant (BR-TEN-001).
    """


def resolve(module: str, function: str) -> Callable[..., Any] | None:
    """The owning module's service callable, or None while not yet authored.

    Resolution is getattr-at-call-time so the moment a lane lands its
    function, every seam call here starts using it — no re-wiring step.
    """
    try:
        services = import_module(f"apps.{module}.services")
    except ImportError:
        return None
    fn = getattr(services, function, None)
    return fn if callable(fn) else None


def require(module: str, function: str) -> Callable[..., Any]:
    fn = resolve(module, function)
    if fn is None:
        raise SeamNotWired(
            f"apps.{module}.services.{function} is not wired yet — "
            f"see the seam contract in apps/tenancy/seams.py"
        )
    return fn


# ── identity ────────────────────────────────────────────────────────────────
def provision_owner(**kwargs: Any) -> Any:
    """REQUIRED: owner user + System Admin membership in the caller's txn."""
    return require("identity", "provision_owner")(**kwargs)


def start_owner_session(**kwargs: Any) -> str | None:
    """None while unwired — provisioning commits, the owner just signs in."""
    fn = resolve("identity", "start_owner_session")
    return fn(**kwargs) if fn is not None else None


def owner_email_for(tenant_id: Any) -> str | None:
    """REQUIRED on the replay path (BR-TEN-010)."""
    return require("identity", "owner_email_for")(tenant_id)


def member_count() -> int | None:
    """None while unwired — the checklist item falls back to its manual mark."""
    fn = resolve("identity", "member_count")
    return fn() if fn is not None else None


def seed_security_policy(actor: Any = None) -> dict[str, Any] | None:
    """None while unwired — the tenant then has no `security_policies` row and
    `identity.selectors.security_policy_values` serves the ratified BR-IDN-025/
    026 column defaults exactly as it did before, so nobody's effective policy
    moves either way.

    **CR-011 item 8 · the PO delegated this one outright** (*"you decide"*), and
    the decision is written up on the implementer — `apps.identity.services.
    seed_security_policy` — because that is where the next agent will look for
    it. In one line: an unwritten row makes a tenant's password rule a PYTHON
    CONSTANT, so a deploy that moved the ratified minimum would change every
    un-opened tenant's policy with no author and no audit row. The row pins it.

    Same shape and same reasoning as `seed_notification_settings` above
    (CR-010 item 7): write it at provisioning, keep the read-side fallback as
    the repair path for tenants that already exist."""
    fn = resolve("identity", "seed_security_policy")
    return fn(actor) if fn is not None else None


# ── reference-data content owners (BR-TEN-013/031) ──────────────────────────
def seed_reference_list(
    owner_module: str, list_code: str, entries: list[dict[str, Any]], fixture_version: str
) -> int | None:
    """None while unwired — the list is honestly SKIPPED and reported."""
    fn = resolve(owner_module, "seed_reference_list")
    if fn is None:
        return None
    return fn(list_code, entries, fixture_version)


def reference_seed_omissions(
    owner_module: str, list_code: str, entries: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Entries the owner will NOT create, and why. [] while unwired — an owner
    that cannot seed at all has no per-entry story to tell; its whole list is
    already accounted for by UNSEEDABLE_REFERENCE_LISTS."""
    fn = resolve(owner_module, "reference_seed_omissions")
    if fn is None:
        return []
    return list(fn(list_code, entries))


# ── ledger: the chart of accounts + the service GL attributes ───────────────
def seed_chart_of_accounts(actor: Any = None) -> dict[str, Any] | None:
    """None while unwired — provisioning commits with an empty chart, and the
    absence surfaces at issue (BR-BIL-010 refuses an unmapped line) rather than
    as a guessed account. See the seam contract above."""
    fn = resolve("ledger", "seed_chart_of_accounts")
    return fn(actor) if fn is not None else None


def ensure_service_revenue_accounts(
    service_code: str, actor: Any = None
) -> tuple[str | None, str | None]:
    """(None, None) while unwired, and for a service no chart line names — the
    caller stores the NULLs. Nothing here invents a GL code."""
    fn = resolve("ledger", "ensure_service_revenue_accounts")
    if fn is None:
        return None, None
    usage, base = fn(service_code, actor)
    return usage, base


def seed_bill_templates(actor: Any = None, *, on_date: Any) -> dict[str, Any] | None:
    """None while unwired — provisioning commits with no bill template, and the
    absence surfaces at issue (BR-BIL-025 refuses without a pin) rather than as
    an invented one. **DEF-123 · see the seam contract above:** for one day this
    was the state of EVERY tenant on EVERY deployment and no gate noticed, which
    is what G26 required-rows now exists to catch."""
    fn = resolve("billing", "seed_bill_templates")
    return fn(actor=actor, on_date=on_date) if fn is not None else None


# ── notifications: the notice templates a tenant sends letters from ─────────
def seed_notification_settings(actor: Any = None) -> dict[str, Any] | None:
    """None while unwired — the dispatch-settings row and the SET-12 rule rows
    then materialise on first read exactly as before (dispatch_config._row's
    and rule_service._ensure_rules' get_or_create), so an unwired deployment
    loses nothing but the day-zero rows. CR-010 item 7.

    **BOTH HALVES OF THE SENTENCE, since DEF-258.** The requirement reads *"the
    NotificationSettings row is to be WRITTEN at provisioning … and the SET-12
    rule rows with it"* and only the first half landed on 2026-08-17: measured
    live, the dispatch row carried the provisioning timestamp and the fifteen
    rule rows carried one twenty hours later, written when a lane opened the
    screen. One seam still, because it is one sentence about one screen."""
    fn = resolve("notifications", "seed_notification_settings")
    return fn(actor) if fn is not None else None


def seed_read_validation_settings(actor: Any = None) -> dict[str, Any] | None:
    """None while unwired — the tenant then has no read-validation row and the
    threshold rules report `not_evaluated` exactly as they did before.

    **DEF-251 · the seam that was documented in the OTHER module.**
    `apps.metering.services.ensure_read_validation_settings` described itself
    as provisioning's entry point — *"Tenancy owns provisioning, so it calls
    this"* — and no such call existed anywhere in the product. The contract was
    written on the callee and never on the caller, so no gate could see the
    gap: the only two callers in the repository were test files, and the live
    database held **zero rows**. Naming it here is what makes the wiring
    checkable (G20 reads this file), which is the difference between a seam and
    a sentence in a docstring."""
    fn = resolve("metering", "seed_read_validation_settings")
    return fn(actor) if fn is not None else None


def seed_notice_templates(actor: Any = None, *, on_date: Any) -> dict[str, Any] | None:
    """None while unwired — provisioning commits with no notice templates, and
    the absence surfaces at generation (`template_service.resolve` refuses
    without a published body) rather than as an invented letter. **DEF-163 · see
    the seam contract above:** until 2026-08-16 that was the state of EVERY
    tenant on EVERY deployment, so no utility had ever been able to send a
    dunning letter or a disconnection notice."""
    fn = resolve("notifications", "seed_notice_templates")
    return fn(actor, on_date=on_date) if fn is not None else None


def queue_staff_alert(**alert: Any) -> dict[str, Any] | None:
    """None while unwired — C-15's third limb is the alert, and the first two
    (the named lines on the setup screen and the `sample.seed_incomplete` audit
    row) are delivered unconditionally either way. DEF-3422.

    The keyword contract is in the module docstring above; it is spelled there
    rather than here so both halves of the seam are readable in one place.
    """
    fn = resolve("notifications", "queue_staff_alert")
    return fn(**alert) if fn is not None else None


def ledger_account_id_for_designation(designation: str) -> str | None:
    """The account id carrying a GL DESIGNATION, or None while unwired.

    CR-040 task A2 (PO ruling 2026-08-27 closing OQ-490, verbatim: *"(a)
    Undeposited funds is the answer for every tender"*). Provisioning uses it
    to point every seeded tender at `undeposited_funds` — the account the
    posting path already falls back to when the pointer is NULL, so the
    BEHAVIOUR does not move and what moves is that the value becomes STATED.

    **None, never a guess, on three different facts** — the ledger module is
    not authored, the chart has no row with that designation, or the tenant has
    no chart at all. The caller writes NOTHING in that case and reports it: a
    tender left unmapped keeps today's fallback, and inventing an id here would
    point cash at an account nobody chose.
    """
    fn = resolve("ledger", "gl_account_id_for_designation")
    if fn is None:
        return None
    return fn(designation)


def ledger_default_gl_account_id_for_reason(code: str) -> str | None:
    """The account an ADJUSTMENT REASON starts pointing at — CR-066 table 2.

    PO 2026-09-02, verbatim: *"Table 2 — the five adjustment reasons - these are
    all good - please apply these."*

    ⚠ **AND THE PO WAS TOLD, IN THE SAME MESSAGE, THAT IT CHANGES NOTHING
    TODAY.** Nothing in this product posts an adjustment through a reason code —
    a credit reverses whatever account the original bill credited — so the five
    accounts collect nothing until something reads
    `reason_codes.default_gl_account_id`. It is correct to have and it is NOT
    what unblocks a bill; no caller may report it as such.

    None while the ledger is unwired or the tenant's chart has no such row, for
    exactly the reasons `ledger_account_id_for_designation` states one function
    up: the reason stays unmapped, which is the lawful state it has been in
    since the column existed.
    """
    fn = resolve("ledger", "default_gl_account_id_for_reason_code")
    if fn is None:
        return None
    return fn(code)


def rating_apply_default_gl_accounts(actor: Any = None) -> dict[str, Any] | None:
    """Ask RATING to point its own seeded charge codes and discounts at the
    accounts CR-066's tables name. OPTIONAL seam — None while unwired.

    ⚠ **TENANCY NEVER WRITES `charges` OR `discounts`** (BR-TEN-013). Both are
    rating's tables; this asks rating to do it, in rating's own service layer,
    inside the caller's transaction — the same posture `seed_reference_list`
    has taken since the day it was written.

    **CALL IT AFTER THE CHART AND AFTER THE SERVICES.** The mapping points at
    rows `seed_chart_of_accounts` has just planted, and a BASE charge code
    resolves through `tenant_services.revenue_account`, which
    `_enable_signup_services` writes. Either one missing and the sweep finds no
    account and writes nothing — which is safe, and is also a tenant that still
    cannot issue a bill carrying a fee.
    """
    fn = resolve("rating", "apply_default_gl_accounts")
    if fn is None:
        return None
    return fn(actor)


def ledger_account_is_live(account_id: Any) -> bool:
    """REQUIRED on the GL override path — see the seam contract above.

    Raises SeamNotWired rather than answering False, because False would read as
    "that account does not exist" and refuse a tenant's perfectly good pointer
    with a message about their own chart.
    """
    return bool(require("ledger", "account_is_live")(account_id))


# ── live counts (BR-TEN-026/029) ────────────────────────────────────────────
def rate_schedule_count(**kwargs: Any) -> int | None:
    fn = resolve("rating", "rate_schedule_count")
    return fn(**kwargs) if fn is not None else None


def tax_pricing_gap() -> dict[str, int] | None:
    """DEF-254 — {"jurisdictions": N, "priced": M} from rating, or None while
    unwired. `None` and `{"jurisdictions": 0, ...}` are different facts and the
    caller must not collapse them: the first is *rating has not published this
    read*, the second is *this tenant has no authorities*, and only the second
    is something a person can act on."""
    fn = resolve("rating", "tax_pricing_gap")
    return fn() if fn is not None else None


def active_account_count(service_code: str) -> int | None:
    fn = resolve("customers", "active_account_count")
    return fn(service_code) if fn is not None else None


def active_account_counts() -> dict[str, int] | None:
    """`active_account_count` for every service in one pass (`DEF-TEN-8731`).
    None while customers is unwired, exactly as the singular answers None."""
    fn = resolve("customers", "active_account_counts")
    return dict(fn()) if fn is not None else None


def uom_used_by_count(uom_code: str) -> int:
    """0 while unwired: no metering tables exist, so no meter references it."""
    fn = resolve("metering", "uom_used_by_count")
    return int(fn(uom_code)) if fn is not None else 0


def reason_code_used_by_count(code: str) -> int:
    """0 while unwired: billing stores no adjustment/correction rows yet."""
    fn = resolve("billing", "reason_code_used_by_count")
    return int(fn(code)) if fn is not None else 0


def payment_method_used_by_count(code: str) -> int:
    """0 while unwired: payments stores no payment rows yet."""
    fn = resolve("payments", "payment_method_used_by_count")
    return int(fn(code)) if fn is not None else 0


# ── currency-lock probe (BR-TEN-042) ────────────────────────────────────────
def financial_records_exist() -> bool:
    """True the moment ANY wired financial module reports a record."""
    for module in ("billing", "payments"):
        fn = resolve(module, "financial_records_exist")
        if fn is not None and fn():
            return True
    return False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03 lead story of the W0 tenancy feature lane; AMENDMENT co-packet US-TEN-009@178c282)
# generated: 2026-08-09 by story-coder v1 (W0 tenancy provisioning + settings lane) · AMENDED 2026-08-15 by story-coder (tenancy/identity lane — the five US-TEN-019 SAMPLE-DATA contracts, named one module at a time so G20 harvests all five rather than four hiding behind an `apps.<owner>.…` placeholder) · AMENDED 2026-08-09 by story-coder (reference-data gap lane — used-by seams for the two hosted lists) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder (DEF-016/017 reference-data lane — the optional reference_seed_omissions seam + the seed_reference_list owner list) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane — seeded_revenue_account_ids becomes ensure_service_revenue_accounts, which MINTS; ledger_account_is_live added for the tenant's GL override) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-251: the `seed_read_validation_settings` seam, named on the CALLER's side so G20 can see it — the contract had only ever existed as a sentence in metering's own docstring)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select, same bar the baseline passes) black✔ pytest tests/test_us_ten_*: 86 passed / 2 skipped (logo lane · identity-seam skip-until-wired) / 2 isolation→G5✔ · suite 335 passed, 7 skipped, 20 deselected✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [DEF-016/017 reference-data lane 2026-08-10] ruff✔(--select E4,E7,E9,F on apps/ — the bar the baseline passes; the repo-wide `ruff check .` default-rule run has 194 pre-existing findings under the newer ruff 0.15.8 in this container, none in this lane's files) black✔(--target-version py312 on this lane's files; 8 apps/ files are pre-existing reformat candidates under black 26.3.1, none of them this lane's) · suite `pytest tests -m "not golden and not isolation"` 895 passed / 9 skipped (875 was the baseline in this tree when the lane started) · `-m isolation` 14 passed / 30 skipped (unchanged) · run_gates 13-PASS/0-FAIL/1-SKIP✔ · no migration in this lane (no schema change) · RED-then-GREEN proved for both defects: removing rating's seam turns the DEF-016 guard red naming ['charge_codes','tax_jurisdictions']; removing the six SEED_LIST_OWNERS rows turns the DEF-017 guards red naming all six
# exceptions: [2026-08-15] the five `seed_sample_records`/`seed_sample_reads` contracts are UNAUTHORED and their precondition is a COLUMN, not a function: BR-TEN-057's `is_sample` does not exist on any of the tables it names, all of which belong to metering/assets/customers/rating. Each is PARKED in 10-scripts/gates/seam_known_gaps.txt with an `absent=` guard naming the exact column, so G20 goes RED the minute one arrives — the arrival signal BR-TEN-057 needs and nothing else was watching for · every neighbor function above is a DOCUMENTED SEAM, not yet authored by its lane — callers fall back or refuse loudly as documented; integration tests are skip-until-wired (recorded per test) · [gap lane 2026-08-09] reason_code/payment_method used-by return 0 while billing/payments are unwired, so BR-TEN-030 and BR-TEN-034 cannot bite for those two cards yet (BR-TEN-036 still protects the seeded rows) — REPORTED, same honest posture meter_types carried before BR-AST-044 · [path-tenancy lane 2026-08-10] start_owner_session added to the identity seam contract — OPTIONAL, so an unwired identity leaves provisioning working and simply hands back no session · [DEF-016/017 lane 2026-08-10] rating and metering now AUTHOR seed_reference_list, so charge_codes/tax_jurisdictions and the four asset catalogs stop skipping; customers still authors none, and that skip is now required to carry its reason in tenancy's UNSEEDABLE_REFERENCE_LISTS · reference_seed_omissions is OPTIONAL and read-only — an owner that offers none simply reports nothing extra
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
