# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-002 (service chips ⊆ tenant-enabled, S10 step 2) · US-RAT-004
#           (service tags on the schedule cards) · US-RAT-005 (UoM gate at
#           activation, S11 step 1) · US-RAT-008 (charge-code service scope) ·
#           US-RAT-009 (applies-to services) · US-RAT-001 (status pill "today")
#           Screens: S9–S13
# Rules:    BR-RAT-024 (services ⊆ the 10-service catalog ∩ tenant-enabled) ·
#           BR-RAT-038 (UoM gate: billed unit or a conversion factor, never a
#           silent conversion) · BR-RAT-035 (charge-code audit-lock counts the
#           invoice-line references billing owns) · BR-TEN-043 (event-time law:
#           "today" is the tenant's, read at display time only)
# Tests:    06-backend/tests/test_us_rat_schedules.py (UoM gate + service gate) ·
#           test_us_rat_plans.py (disabled-service refusal)
# Impacts:  apps/rating/services.py + selectors.py (every cross-module read) ·
#           apps.tenancy (Service · TenantService · tenant_today) · apps.billing
#           (invoice-line references — unwired in W1)
# ───────────────────────────────────────────────────────
"""rating → other-module SEAMS: every cross-module read this module makes.

B1/B8: rating NEVER touches another module's ORM through a direct model
import, and it never writes another module's tables. Everything rating needs
from a neighbour is one of the documented callables below.

Eng dispositions recorded here (not silently resolved):
- The platform service catalog (`services`) and per-tenant enablement
  (`tenant_services`, incl. the r6.4 billed-UoM gate columns) are READ through
  `django.apps.get_model` because tenancy exposes no selector returning the
  catalog row id or the UoM-gate columns — the same disposition identity took
  for its BR-IDN-012 reference count (apps/identity/selectors.py). Read-only,
  tenant-filtered, never a write.
- `tenant_today()` goes through tenancy's own selector (the owning module's
  read path) — rating never computes wall-clock time itself (BR-TEN-043; the
  G6 grep forbids it in money paths for exactly this reason).
- Invoice-line references (BR-RAT-035 audit-lock half) and the plan's
  never-billed half (US-RAT-001 TC-5) live in BILLING. This paragraph used to
  read *"billing has no tables in W1: unwired == 0 BY CONSTRUCTION, so the
  fallback is honest rather than a guess"* — true when written, **false from
  the day billing grew `invoices` and `invoice_lines`, and nobody re-read it**.
  That is DEF-079, and it let a rate plan that HAD been billed be permanently
  deleted. Both counters are published now, and both fallbacks report `None`
  for *"could not answer"* rather than `0` for *"no references"*; their callers
  fail CLOSED on a None. Corrected rather than left standing (hard-won law 1).
"""

from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError

from core import tenancy as core_tenancy


def _tenant_id() -> UUID | None:
    return core_tenancy.current_tenant_id()


# ── tenancy: the 10-service platform catalog (r5 #1, BR-RAT-024) ────────────
def service_catalog_row(service_code: str) -> dict[str, Any] | None:
    """{id, code, name} of an ACTIVE catalog service, or None when unknown."""
    service_model = django_apps.get_model("tenancy", "Service")
    row = service_model.objects.filter(code=service_code, active=True).first()
    if row is None:
        return None
    return {"id": row.id, "code": row.code, "name": row.name}


def service_is_enabled(service_code: str) -> bool:
    tenant_service = django_apps.get_model("tenancy", "TenantService")
    return tenant_service.objects.filter(
        tenant_id=_tenant_id(), service__code=service_code, enabled=True
    ).exists()


def enabled_service_codes() -> tuple[str, ...]:
    """Every service THIS TENANT has switched on, in the platform catalogue's
    own order (BR-RAT-024, BR-TEN-025).

    `service_is_enabled` above answers the same question one code at a time and
    is what the seeder asks when it already knows which service it means. This
    answers the other direction — *what does this utility sell?* — which is the
    question `sample_data.enabled_services_no_published_plan_prices` has to ask
    before it can say which of them no plan prices (`DEF-1250`).

    ⚠ **DERIVED FROM THE TENANT'S OWN ROWS, NEVER FROM A LITERAL LIST OF THE
    TEN.** A hard-coded enumeration here would be the failure `G47` exists to
    catch — `BR-RAT-024` moved from six services to ten on 2026-08-16 and the
    lists that named them individually are still being found. The catalogue's
    `sort` is the order every screen already uses.
    """
    tenant_service = django_apps.get_model("tenancy", "TenantService")
    return tuple(
        str(code)
        for code in tenant_service.objects.filter(tenant_id=_tenant_id(), enabled=True)
        .order_by("service__sort", "service__code")
        .values_list("service__code", flat=True)
    )


# ── tenancy: the BR-RAT-038 UoM gate (r6.4 tenant_services columns) ─────────
def billed_uom(service_code: str) -> dict[str, Any]:
    """{billed_uom, primary_uom, conversion_factor} for the tenant's service.

    All three may be None while the Settings tab has not been filled in — the
    caller decides what that means (BR-RAT-038 blocks rating, never converts).
    """
    tenant_service = django_apps.get_model("tenancy", "TenantService")
    row = (
        tenant_service.objects.filter(tenant_id=_tenant_id(), service__code=service_code)
        .select_related("billed_uom", "primary_uom")
        .first()
    )
    if row is None:
        return {"billed_uom": None, "primary_uom": None, "conversion_factor": None}
    factor: Decimal | None = row.conversion_factor
    return {
        "billed_uom": row.billed_uom.code if row.billed_uom else None,
        "primary_uom": row.primary_uom.code if row.primary_uom else None,
        "conversion_factor": factor,
    }


def service_bills_from_a_register(service_code: str) -> bool:
    """**Does this tenant bill this service from a METER READING? — `BR-TEN-1180`.**

    `DEF-3201`. The `BR-RAT-038` gate compares a rate schedule's unit against the
    unit the meter reads, and the PO's ruling of 2026-09-02 scopes it in its own
    words — *"the same principle is applied to all **METER** services"*. A
    service that reads no register has no reading, so there is nothing for a
    schedule's unit to be compared against: that is a CATEGORY ERROR, not a
    mismatch, and the two must not print the same sentence.

    ⚠ **THE ANSWER IS THE TENANT'S OWN DECLARATION, NEVER A LIST THIS MODULE
    KEEPS.** `tenant_services.billing_basis` holds the PO's three ruled values —
    `metered` · `share` (of another service) · `capacity` — and migration
    `tenancy/0030` seeded all ten from `SERVICE_DEFAULT_UOMS`: electric, water,
    gas and thermal/heat `metered`; sewer `share` (`BR-RAT-015` ❄️, a percentage
    of the water usage charge); trash, storm water, solar, broadband and battery
    `capacity` (`BR-MET-104`/`BR-MET-108`, `BR-TEN-170`). **The first draft of
    this fix carried that classification as a frozenset in `rating.selectors`,
    which would have been the second hand-kept copy of a declaration the
    database already holds** — the thing `G47`'s own reasoning calls *"the
    fifteenth copy, and it would go green on the day the seed changed
    underneath it"*. Reading the column instead means an eleventh catalogue
    service is classified by its own seed, and a utility that declares its own
    basis on S8 is honoured.

    ⚠ **A MISSING ROW ANSWERS `True`, AND THAT IS THE SAFE DIRECTION (hard-won
    law 3).** `tenancy.selectors.service_row` reads an absent row as `metered`
    for the same reason the boolean before it defaulted True: a tenant that has
    declared NOTHING has not declared *"no register"*. Wrong-and-gated shows a
    person a warning they can act on; wrong-and-ungated shows nobody anything,
    and the gas case this gate exists for — a `ccf` tariff over a `therm`
    register, roughly **4% over on every gas line, `$1.72` a month on one
    meter** — is exactly what goes quiet.

    ⚠ **B1: rating never re-decides what a basis MEANS.** The vocabulary is
    tenancy's (`BR-TEN-1180`) and the value is read through this door; a rating
    file comparing against a hand-typed `"metered"` would be a second statement
    of somebody else's enum, which goes silently wrong the day tenancy renames
    one — the branch stops matching, the gate reports satisfied, and no test
    that does not exercise that exact pair can tell (`DEF-2872`'s shape).
    """
    tenancy_models = import_module("apps.tenancy.models")
    tenant_service = django_apps.get_model("tenancy", "TenantService")
    row = (
        tenant_service.objects.filter(tenant_id=_tenant_id(), service__code=service_code)
        .only("billing_basis")
        .first()
    )
    if row is None:
        return True
    return bool(row.billing_basis == tenancy_models.BILLING_BASIS_METERED)


# ── the estate plan's four inputs — DEF-2397 ────────────────────────────────
#
# ⚠ **THE THREE BELOW ARE `apps/metering/seams.py`'s, RESTATED HERE AND NOT
# IMPORTED, AND THE REASON IS B1 RATHER THAN TIDINESS.** `apps/rating/sample_
# data` has to ask `core.sample_fixture.estate_plan` the SAME four questions
# metering and assets ask it, or the three modules shape three different
# estates for one tenant — which is `DEF-2397` exactly: metering built an
# electric estate and rating priced water. Each module reaches tenancy through
# its OWN seam file (B1: a module never imports another module's seams), and
# the AGREEMENT comes from `estate_plan` being pure and deterministic on its
# inputs, not from a shared import. `tenancy.selectors` is the one source
# underneath all three.


def service_default_uoms() -> dict[str, str | None]:
    """`{code: primary UoM}` for every ENABLED service, in ONE query.

    Mirrors `apps.metering.seams.service_default_uoms` — see the block above for
    why it is restated rather than imported. `None` for a service the tenant
    declares no unit for is the honest answer and `estate_plan` REFUSES that
    service by name; there is no fallback here and there must not be one
    (CLAUDE.md rule 3).
    """
    tenancy_selectors = import_module("apps.tenancy.selectors")
    return dict(tenancy_selectors.service_default_uoms())


def service_billed_uoms() -> dict[str, dict[str, Any]]:
    """`{code: {"billed_uom", "conversion_factor"}}` for every ENABLED service.

    `BR-MET-143`'s register→billed gate as the TENANT holds it. NULLs are the
    ordinary answer, meaning *"the register's own unit is billed"*, never
    *"refuse"*. Mirrors `apps.metering.seams.service_billed_uoms`.
    """
    tenancy_selectors = import_module("apps.tenancy.selectors")
    return dict(tenancy_selectors.service_billed_uoms())


def unit_reconciliation(reading_unit: str | None, pricing_unit: str | None) -> dict[str, Any]:
    """`BR-MET-143`'s match / scale / dimension verdict for a pair of units.

    ⚠ **THE RULE IS METERING'S AND MUST HAVE EXACTLY ONE IMPLEMENTATION**
    (`apps.metering.register_units.reconciliation`). This is the door rating
    uses to reach it, the same way `apps.assets.seams.unit_reconciliation` is
    assets'. Rating must not re-decide scale-versus-dimension: two answers to
    that question is how a meter gets planted at ×1 on a pair no factor can
    reconcile.
    """
    register_units = import_module("apps.metering.register_units")
    return register_units.reconciliation(reading_unit, pricing_unit).as_dict()


def unit_reconciliation_kinds() -> dict[str, str]:
    """The four VALUES `unit_reconciliation`'s `kind` can hold, from metering.

    ⚠ **SO NO CALLER IN THIS MODULE WRITES THE LITERAL `"dimension"`.** The
    verdict strings belong to `BR-MET-143` and metering owns them; a rating file
    comparing against a hand-typed copy is a second statement of somebody else's
    enum, and it goes silently wrong the day metering renames one — the branch
    stops matching, the gate reports SATISFIED, and no test that does not
    exercise that exact pair can tell (`DEF-2872`'s shape: the damage is in the
    branch not taken). Read through the same door as the verdict itself.
    """
    register_units = import_module("apps.metering.register_units")
    return {
        "match": register_units.MATCH,
        "scale": register_units.SCALE,
        "dimension": register_units.DIMENSION,
        "unknown_dimension": register_units.UNKNOWN_DIMENSION,
    }


# ── tenancy: display-time "today" (BR-TEN-043) ──────────────────────────────
def tenant_today() -> date:
    tenancy_selectors = import_module("apps.tenancy.selectors")
    return tenancy_selectors.tenant_today()


# ── tenancy: the Billing-defaults grace (BR-BIL-008 / BR-BIL-002) ───────────
#: The S66 screen's own seeded defaults (`settings_families.BILLING_DEFAULTS`).
LATE_GRACE_DEFAULT_DAYS = 5
LATE_GRACE_DEFAULT_MODE = "calendar"


def late_grace_default() -> tuple[int, str]:
    """🔒 The utility's Settings → Billing defaults grace, `(days, mode)`.

    PO ruling 2026-10-06 11 (a): *"The Settings default stays as the starting
    value for new codes."* It is also what a penalty code with NO grace of its
    own is assessed on (a code minted on Settings after `rating/0066`). Read
    off tenancy's typed columns, as the Billing-defaults page writes them; an
    unset column is the page's own seeded default, never a different figure.
    """
    settings_model = django_apps.get_model("tenancy", "TenantSettings")
    row = (
        settings_model.objects.filter(tenant_id=_tenant_id())
        .values("late_grace_days", "late_grace_mode")
        .first()
    )
    days = row["late_grace_days"] if row and row["late_grace_days"] is not None else None
    mode = row["late_grace_mode"] if row and row["late_grace_mode"] else None
    return (
        LATE_GRACE_DEFAULT_DAYS if days is None else int(days),
        mode or LATE_GRACE_DEFAULT_MODE,
    )


# ── ledger: is this GL account the tenant's, and still live? (BR-BIL-069) ───
class LedgerSeamNotWired(RuntimeError):
    """The ledger has not published the read this module's validation needs.

    Loud on purpose (see `ledger_account_is_live`); never caught here and turned
    into a permissive answer. Mirrors `apps.ledger.tenancy_seam.LedgerSeamNotWired`,
    which the ledger raises for the same reason in the other direction.
    """


def ledger_mint_tax_authority_account(name: str, actor: Any = None) -> Any | None:
    """Ask the LEDGER to mint this authority's own 2200-series payable account.

      apps.ledger.services.create_tax_authority_account(*, code=None, name, actor)
          -> LedgerAccount

    B5 line 74 ❄️ (*"2200-series Tax payable per authority — tenant authorities
    mint their own"*) and BR-BIL-069 (PO 2026-08-11): each authority is owed
    into its OWN account, and the CODE is generated by the product rather than
    typed (PO 2026-08-12, OQ-147).

    **Why a seam and not a seed.** `apps/ledger/chart.py` deliberately carries no
    2200 row, because seeding one would invent a tax authority no tenant created
    (BR-TEN-037). This function is called only when something is CREATING an
    authority and therefore knows its name — which is exactly the moment the
    ruling says an account may be minted.

    Returns None while the ledger publishes nothing; the caller then leaves the
    mapping empty and the absence surfaces at issue, by name (BR-BIL-010), which
    is what the run already does today.
    """
    try:
        ledger_services = import_module("apps.ledger.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(ledger_services, "create_tax_authority_account", None)
    if not callable(fn):
        return None
    return fn(name=name, actor=actor)


def ledger_default_gl_account_id_for_charge(
    code: str, *, service: Any = None, is_base: bool = False
) -> Any | None:
    """Where a seeded charge code STARTS posting, asked of the LEDGER — CR-066.

      apps.ledger.services.default_gl_account_id_for_charge_code(
          code, *, service=None, is_base=False) -> str | None

    ⚠ **AN UNWIRED LEDGER ANSWERS `None` HERE, AND THAT IS THE SAFE ANSWER
    RATHER THAN A CONVENIENT ONE.** `ledger_account_is_live` refuses instead of
    answering, because "every account is fine" would let a mapping be stored
    that no chart can honour. This question is the other shape: `None` means *we
    could not name a default*, the code keeps the NULL it already had, and the
    Accounting screen reports the gap exactly as it does today. Nothing is
    guessed and nothing a tenant set is touched.
    """
    try:
        ledger_services = import_module("apps.ledger.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(ledger_services, "default_gl_account_id_for_charge_code", None)
    if not callable(fn):
        return None
    return fn(code, service=service, is_base=is_base)


def ledger_default_gl_account_id_for_discount() -> Any | None:
    """Where a discount STARTS posting, asked of the LEDGER — CR-066 table 3.

      apps.ledger.services.default_gl_account_id_for_discount() -> str | None

    `None` while the ledger publishes nothing, for the reason one function up.
    """
    try:
        ledger_services = import_module("apps.ledger.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(ledger_services, "default_gl_account_id_for_discount", None)
    if not callable(fn):
        return None
    return fn()


def ledger_discount_default_account_code() -> str | None:
    """The chart CODE a discount starts at — `4760` — read from the LEDGER.

    Read rather than restated so this module carries no account number of its
    own. CR-061 moved that row from `4300` to `4760` on 2026-09-01; a copy here
    would have made that a two-file change and one of the two would have been
    missed, which is the failure `chart.py`'s own law is written against.
    """
    try:
        chart = import_module("apps.ledger.chart")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    return getattr(chart, "DISCOUNT_DEFAULT_ACCOUNT", None)


def ledger_account_is_live(account_id: Any) -> bool:
    """Ownership AND liveness of a ledger account, asked of the LEDGER.

    The validation behind a tenant's tax → liability-account mapping (PO ruling
    2026-08-11 closing OQ-116: *"allow Use to manage it since every utility may
    not have every account"*). `taxes.liability_gl_account_id` is a deferred FK
    (B11 F-3) and therefore not even an FK constraint — but the point stands
    either way and is the same one tenancy's `_apply_service_gl_accounts` makes
    for the identical check on `tenant_services`: **an FK proves the row exists;
    it never proves the row is THIS tenant's**, and a crafted id would otherwise
    point one utility's tax at another utility's chart, in a money path. It also
    answers False for an account the tenant has deactivated (IS-1) — tax must
    not be mapped onto a row their own trial balance treats as retired.

    Asked through the ledger's SERVICE layer, which is how a neighbouring module
    reaches another module (B1 / BR-TEN-013), never through its ORM.

    **REFUSES rather than answering True when the ledger publishes no such
    read.** "Every account is fine" is the one answer that must never be a
    fallback: it would let a mapping be stored that no chart can honour, and the
    line carrying it is stamped and frozen at issue. `False` would be the other
    wrong answer — it would tell a clerk their own account does not exist. So
    the caller is told the check could not run, loudly, and stores nothing.
    """
    try:
        ledger_services = import_module("apps.ledger.services")
    except ImportError:  # pragma: no cover - the app package always imports
        ledger_services = None
    fn = getattr(ledger_services, "account_is_live", None) if ledger_services else None
    if not callable(fn):
        raise LedgerSeamNotWired(
            "apps.ledger.services.account_is_live is not published, so a tax's liability "
            "account cannot be validated as this tenant's and still live (BR-BIL-069, PO "
            "ruling 2026-08-11). Nothing is stored on an unchecked answer: the mapping "
            "decides which 2200-series account an authority's money is credited to, and "
            "the stamp that uses it freezes with the bill."
        )
    return bool(fn(account_id))


def ledger_account_display(account_id: Any) -> dict[str, str] | None:
    """This tenant's CODE and NAME for a GL account — for a SCREEN, never a gate.

    PO ruling 2026-09-17, verbatim: *"dont show uuiD- shoe actual 3 of gL code
    4000 , 4010 something liek this and its name - you might have to pull it
    from GL code mapping we have it - **if GL code is not map then dont show
    it**"*. B14 rule 31 says the same thing as a rule: no database id is ever
    the visible value of a field.

    ⚠ **IT DEGRADES; IT DOES NOT RAISE — AND THAT IS A DELIBERATE DIFFERENCE
    FROM `ledger_account_is_live` TWENTY LINES UP, WHICH IS RIGHT TO RAISE.**
    Read them together before "fixing" this one into consistency with its
    neighbour. That one validates a MAPPING that is stamped and frozen onto a
    bill, so *"the check could not run"* must stop the write — answering True
    would store a mapping no chart can honour. **This one renders a table
    cell.** Raising here would turn an unwired ledger into a 500 on the whole
    Charges step of the plan wizard, over a column whose ruled empty state is
    *show nothing*.

    **THREE WAYS TO GET NOTHING, AND ALL THREE RENDER THE SAME NOTHING**, which
    is the ruling rather than a simplification: the id is NULL (no account is
    mapped) · the ledger cannot resolve it (deactivated, or not this tenant's —
    `account_is_live`'s own reasoning) · the ledger publishes no such read at
    all. No placeholder, no dash that reads like a value, and never the id.
    """
    try:
        ledger_services = import_module("apps.ledger.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(ledger_services, "account_display", None)
    if not callable(fn):
        return None
    try:
        row = fn(account_id)
    except Exception:  # pragma: no cover - a display read may never take a screen down
        return None
    if not isinstance(row, dict):
        return None
    code, name = row.get("code"), row.get("name")
    if not code:
        return None
    return {"code": str(code), "name": str(name or "")}


# ── billing: invoice-line references (BR-RAT-035 audit-lock half) ───────────
#
# ⚠ **BOTH OF THESE ANSWERED `0` WHILE UNWIRED, AND BOTH DOCSTRINGS SAID THAT
# WAS HONEST "BY CONSTRUCTION" BECAUSE BILLING HAD NO TABLES. THAT WAS DEF-079.**
# The sentence was true when it was written and false from the day billing grew
# `invoices` and `invoice_lines`, and nothing re-reads a sentence like that
# (hard-won law 1). The 0 was consumed as a FACT by two guards, and the sharper
# one — `services.delete_plan` — therefore let **a rate plan that HAD been
# billed be permanently deleted**, taking its rate schedules and every charge,
# deposit, penalty and tax rule with it.
#
# The counters are published now (`apps.billing.selectors.plan_invoice_count` /
# `charge_line_count`, re-exported through `apps.billing.services`), so the
# guards bite. **The FALLBACK is fixed as well, and that is the durable half**:
# these return `None` for *"billing could not answer"*, never `0` for *"there
# are no references"*. DEF-079's own prevention column states the law —
# *"a fallback is only honest while the owning module holds no such fact, and
# NOBODY re-reads that sentence, so the honest fallback is the one that reports
# it could not answer, never the one that answers 0."* Their callers FAIL CLOSED
# on a None: they refuse the delete rather than performing it unverified.


def invoice_line_references(charge_id: Any) -> int | None:
    """Invoice lines naming this charge code — BR-RAT-035's audit-lock half.

    **None means BILLING COULD NOT ANSWER**, never "no references". The caller
    treats an unanswerable count as a LOCK (`services.delete_charge`), because
    the alternative is deleting a code that live bills cite and leaving those
    rows — which hard rule 4 forbids anyone from going back and fixing —
    pointing at a code that no longer exists.
    """
    try:
        billing_services = import_module("apps.billing.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(billing_services, "charge_line_count", None)
    return int(fn(charge_id)) if callable(fn) else None


def charge_usage_last_month(charge_id: Any) -> dict[str, Any] | None:
    """`CR-156-BRC10` · CHG-01's tiles — bills, lines and money this code put
    on SENT bills last calendar month, from billing. **None means billing
    could not answer**, the posture `invoice_line_references` takes: a screen
    then shows nothing rather than a confident `0`."""
    try:
        billing_selectors = import_module("apps.billing.selectors")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(billing_selectors, "charge_usage_last_month", None)
    return fn(charge_id, tenant_today()) if callable(fn) else None


def tariff_version_issued_bills(tariff_version_id: Any) -> int | None:
    """DEF-RAT-5715 — ISSUED bills already priced by this version, from billing.

    **None means BILLING COULD NOT ANSWER**, never "no bills" — the same
    distinction `invoice_line_references` was corrected into making, and for the
    same reason DEF-079 cost: a fallback of `0` reads as *"nobody has been
    billed"*, which is the one sentence an operator must not be told wrongly
    before they correct a price.

    The caller shows the figure and does NOT gate on it. A correction is lawful
    whether or not bills exist — that is the whole of BR-RAT-104 — so an
    unanswerable count must not become a refusal; it becomes an honest *"we
    could not work this out"* on the screen.
    """
    try:
        billing_services = import_module("apps.billing.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    fn = getattr(billing_services, "tariff_version_issued_bill_count", None)
    return int(fn(tariff_version_id)) if callable(fn) else None


def plan_invoice_references(rate_plan_id: Any) -> int | None:
    """The "never billed" half of US-RAT-001 TC-5's hard-delete rule.

    The rule is *accounts = 0 AND never billed*, and this answers the second
    half. **None means BILLING COULD NOT ANSWER** — `services.delete_plan`
    refuses on it, which is the only safe direction: `units.rate_plan_id` is
    `on_delete=PROTECT` so a plan LIVE on a unit is safe either way, but a
    RETIRED plan that has been billed is not, and invoices deliberately SNAPSHOT
    rather than reference a plan, so nothing else in the database refuses.
    """
    try:
        billing_services = import_module("apps.billing.services")
    except ImportError:  # pragma: no cover
        return None
    fn = getattr(billing_services, "plan_invoice_count", None)
    return int(fn(rate_plan_id)) if callable(fn) else None


# ── billing: the last already-billed day on a unit (PO ruling 2026-08-11) ────
def last_issued_bill_for_unit(unit_id: Any) -> dict[str, Any]:
    """The furthest-billed ISSUED bill covering this unit, through billing's
    own read surface — `apps.billing.selectors.last_issued_bill_for_unit`.

    The PO ruled on 2026-08-11 that a plan change dated behind an issued bill
    is PERMITTED with a reason recorded (option B of block / warn-and-allow /
    allow silently), so `record_unit_plan_assignment` has to know whether it is
    behind one. Rating cannot ask `invoices` — that is billing's table — so it
    asks by name here.

    RETURNS `{"wired": bool, "bill": dict | None}` rather than a bare row, and
    the two-key shape is the whole point: `None` alone cannot distinguish "this
    unit has never been billed" from "billing publishes no such read". The
    first means the guard ran and found nothing; the second means the guard did
    not run. Collapsing them would let an unwired neighbour read as a clean
    bill of health — which is the exact failure customers' move-out guard
    writes a warning about, and hard-won law 1 in one line.
    """
    try:
        billing_selectors = import_module("apps.billing.selectors")
    except ImportError:  # pragma: no cover - the app package always imports
        return {"wired": False, "bill": None}
    fn = getattr(billing_selectors, "last_issued_bill_for_unit", None)
    if not callable(fn):
        return {"wired": False, "bill": None}
    return {"wired": True, "bill": fn(unit_id)}


def active_asset_count(unit_id: Any, service_code: str, as_of: date) -> dict[str, Any]:
    """BR-RAT-090's quantity, through assets' own read surface.

    CR-019, and the reason it is a seam rather than a query: assets are B2 r4's
    table and rating may not touch it. `apps.assets.selectors.billable_asset_count`
    owns the three predicates (on this unit on this date, in service, for this
    service) and this asks for the answer by name.

    RETURNS `{"wired": bool, "count": int | None}`, the same two-key shape as
    `last_issued_bill_for_unit`, and for the same reason stated there: a bare
    `0` cannot distinguish **"this unit has no carts"** from **"the read does
    not exist"**. BR-RAT-090 refuses on the second and bills on the first, so
    collapsing them would bill a three-cart household `$0.00` the day this
    module was moved or renamed — on a document that looks entirely normal.
    """
    try:
        assets_selectors = import_module("apps.assets.selectors")
    except ImportError:  # pragma: no cover - the app package always imports
        return {"wired": False, "count": None}
    fn = getattr(assets_selectors, "billable_asset_count", None)
    if not callable(fn):
        return {"wired": False, "count": None}
    return {"wired": True, "count": int(fn(unit_id, service_code, as_of))}


# ── customers: the codes THIS TENANT may actually pick (BR-CUS-094a) ────────
def _account_types_are_tenant_scoped(model: Any) -> bool:
    """Does `account_types` carry a tenant column YET? Asked of the MODEL.

    ⚠ **THIS EXISTS SO THIS LANE AND THE TABLE-OWNERSHIP LANE CANNOT COLLIDE.**
    BR-CUS-094a is being built on two fronts: one lane makes `account_types`
    tenant-owned, and this one makes its consumers read ROWS instead of a
    constant. Reading rows is correct either way, and the only thing that
    differs is whether the read must be tenant-filtered. Asking the model rather
    than assuming means neither lane has to land first, and no merge of the two
    produces a window where this file is wrong.

    It is also hard rule 1 insurance in the direction that matters: the moment
    the column lands, an UNFILTERED read starts returning another tenant's rows.
    """
    return any(f.attname == "tenant_id" for f in model._meta.concrete_fields)


# ── customers: the PLATFORM account-type id for a code (DEF-452) ────────────
def account_type_id_by_code(code: str) -> Any | None:
    """`residential` -> the `account_types` row id, or None. Read-only. DEF-452.

    ⚠ **THE PARAGRAPH THAT STOOD HERE SAID THIS READ WAS *DELIBERATELY NOT
    TENANT-SCOPED*, AND THE PO RULING OF 2026-09-17 ENDED THAT (`DEF-RAT-5654`,
    filed by the account-types lane against this exact function).** It read:
    *"`account_types` is a PLATFORM table … so `_tenant_id()` has nothing to
    filter on here, and adding a filter would match zero rows rather than fail
    loudly"*. Every word of that was TRUE while the table was a platform
    catalogue, and it is what makes this dangerous now: the moment the table
    becomes tenant-owned, an unfiltered `.first()` starts returning **another
    utility's row id**, and that id is then written onto a plan. It is hard rule
    1, and it fails in the silent direction — a plausible uuid, no error.

    **So the filter is applied ONLY where there is a column to apply it to**,
    asked of the model rather than assumed, which is what keeps this correct on
    both sides of the sibling lane's migration and means neither lane has to
    land first. Where the table is still platform-wide, this behaves exactly as
    the old paragraph described.

    **WHY A SEAM AND NOT AN IMPORT.** `rating` already MIRRORS these four codes
    as `TAX_CUSTOMER_CLASSES`, with a test asserting the mirror equals the live
    catalog — mirrored rather than imported *"for the reason B2 §2 gives: rating
    does not read customers' storage"*. That reasoning is about the VOCABULARY.
    An **id** cannot be mirrored: it is a uuid minted at migration time, so the
    only honest way to put one on a plan is to ask the module that owns the row.
    That is exactly what a seam is for, and it stays read-only.

    Returns None rather than raising when the code is unknown, so a caller can
    decide whether a missing class is a refusal or a blank — the seeder treats
    it as a refusal, because a sample plan with no class is DEF-452 itself.
    """
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    row = qs.filter(code=code, active=True).values("id").first()
    return row["id"] if row else None


def account_type_code_by_id(account_type_id: Any) -> str | None:
    """The `account_types` row id -> its code, or None. Read-only.

    `CR-120-BRC06`. The MIRROR of `account_type_id_by_code` above, added for
    one caller: `services._guard_bound_base_charge_code` holds a rate
    schedule's `account_type_id` (a uuid) and has to compare it against a
    charge code's `applies_to_customer_classes`, which is a JSON list of CODE
    STRINGS. **Two keys for one fact is the repo's own recorded hazard** —
    `ChargeCodeAmount.customer_class`'s docstring spells out why it keys by
    code where `plan_deposit_rules` keys by id, and says the resolver decides.
    This is the id->code hop that lets the gate ask the resolver's question in
    the resolver's own vocabulary rather than inventing a second one.

    ⚠ **TENANT-SCOPED ON THE SAME CONDITION AND FOR THE SAME REASON AS ITS
    MIRROR** (`DEF-RAT-5654`, PO ruling 2026-09-17): the filter is applied only
    where there is a column to apply it to, asked of the MODEL rather than
    assumed, so this is correct on both sides of the account-types migration
    and neither lane has to land first. An unfiltered read here would answer
    with another utility's code once the table is tenant-owned — hard rule 1,
    failing in the silent direction.

    **Returns None rather than raising**, so the caller decides. The gate
    treats None as *this schedule states no class*, which is the permissive
    direction and the correct one: a schedule with no class prices every class,
    so there is no intersection to refuse.
    """
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    row = qs.filter(pk=account_type_id).values("code").first()
    return str(row["code"]) if row else None


# ── customers: the PLATFORM consumer-category VOCABULARY (DEF-738) ──────────
def account_type_codes() -> tuple[str, ...]:
    """The consumer-category vocabulary **AS RULED**, in BR-CUS-094's own order.

    ⚠ **THIS IS NO LONGER THE LIST A TAX MAY BE RESTRICTED TO — READ
    `selectable_account_type_codes()` FOR THAT (BR-CUS-094a, PO 2026-09-17).**
    The PO ruled that *"utility can get their own account types"*, so the seven
    below stopped being the vocabulary and became the SEED. What a tenant may
    actually pick is what its ROWS say, and that is the other function.

    ⚠ **AND THIS ONE GOES ON READING THE DECLARED CONSTANTS ON PURPOSE.** It is
    the *ruling* half of a two-way comparison: `tests/test_def_273_tax_
    conditions.py::test_def273_the_class_vocabulary_mirrors_the_platform_
    account_types` and `test_br_cus_094a…::test_the_seeded_rows_still_match_
    the_ruling` check the SEEDED ROWS against it. Derive this from rows and both
    compare the rows with themselves — a tautology, and a check that cannot go
    red is worse than none (`DEF-182`). **Do not "simplify" this into a query.**

    ── WHY THIS SEAM EXISTS AT ALL, WHICH IS DEF-738 ──────────────────────────
    Until 2026-08-30 rating kept the vocabulary as a hand-typed four-tuple,
    correct the day it was written and stale from the day BR-CUS-094 (PO
    2026-08-24) expanded the signed list to seven and marked `government`
    legacy. The consequence was a money one and it failed CLOSED, which is why
    no run ever broke: **no tax could be restricted to an Agricultural,
    Institutional, Municipal or Builder-developer customer** — rating refused
    the code outright, so the tax was never stored and the customer the utility
    wrote it for was charged nothing by a rate that looked configured.

    A mirror with a test asserting it matches is what we had. It had been RED
    for two days and nobody read it (`test_def_273_tax_conditions.py`). So the
    fix is not a wider copy — there is no copy.

    ── WHY THE MODEL'S DECLARED CONSTANTS AND NOT A QUERY ────────────────────
    `AccountType.SEVEN_CATEGORIES` + `LEGACY_CODES` are the vocabulary AS
    RULED; the rows migration 0003/0019 seed are that vocabulary AS SEEDED.
    Reading the constants rather than the table buys three things:

      1 · **The live-table guard stays capable of failing.** Derive from the
          rows and `test_def273_the_class_vocabulary_mirrors_the_platform_
          account_types` becomes a tautology — a check that cannot go red is
          worse than none (DEF-182). Deriving from the constants keeps it
          asking a real question: *does the seed match the ruling?*
      2 · **No query in a validator** that runs once per field, per fixture row.
      3 · **No database at import time**, and no dependence on a tenant context
          the platform table does not have.

    ⚠ **`government` IS IN THIS LIST AND THAT IS DELIBERATE.** BR-CUS-094 makes
    the legacy code unselectable on a NEW RECORD's own category and otherwise
    *"still a valid FK, still filterable, still priceable"*. A tax restriction
    is a filter over accounts, and accounts still carry the code — dropping it
    would invalidate every restriction already stored against it, which is a
    silent re-pointing the ruling forbids by name.

    ⚠ **B2 §2, and why this is not the cross-module read that rule forbids.**
    `account_types` is a PLATFORM table with no `tenant_id` and no RLS policy,
    and this reads a CLASS ATTRIBUTE of the model that owns it — no storage is
    touched at all. It goes through `django.apps.get_model` for the same reason
    the seam above it does: rating never imports another module's models
    directly, so the coupling is one documented callable rather than an import
    graph. Read-only, never a write.
    """
    model = django_apps.get_model("customers", "AccountType")
    return tuple(code for code, _name in model.SEVEN_CATEGORIES) + tuple(model.LEGACY_CODES)


def selectable_account_type_codes() -> tuple[str, ...]:
    """The consumer-category codes **THIS TENANT HOLDS** — rows, not constants.

    Read-only. This is the list a tax, and through the same validator a charge
    code, may be RESTRICTED to. `BR-CUS-094a` (PO 2026-09-17), verbatim:
    *"utility can get their own account types"*, plus *"we have to ensure it is
    not hard coded"*.

    ── THE THREE OUTCOMES, EACH DELIBERATE ───────────────────────────────────
    This is `metering._resolve_unit_type`'s shape (`BR-MET-084`), copied rather
    than reinvented because it is already the house pattern and already tested:

      · the tenant HAS rows → **its own active codes**, in the ruling's order
        first and the tenant's own additions after, because a screen renders in
        this order and sorting would put Agricultural above Residential in a
        list the PO drew;
      · a row the tenant DEACTIVATED is **not** in the list and the fallback
        does **not** resurrect it (`BR-TEN-034` — a deactivated lookup row stops
        being pickable, and a fallback that handed it back would make
        deactivation a no-op);
      · **no rows at all** → the ruled vocabulary, so a deployment whose seed
        migration has not run keeps working instead of refusing every class.

    ── WHAT THIS DOES **NOT** DO, AND IT IS A MONEY STATEMENT ─────────────────
    It re-points no stored row. `charges.applies_to_customer_classes` and
    `taxes.applies_to_customer_classes` keep the exact lists they were stored
    with, `[]` still means every class, and an unknown code is still REFUSED
    rather than dropped (`DEF-273`'s ruled direction — a silently-vanished
    restriction leaves an object the utility believes is scoped applying to
    everybody). Widening the set of codes a restriction MAY NAME moves no cent.

    ⚠ **`government` IS HERE EVEN THOUGH IT IS LEGACY, AND THAT IS THE RULING.**
    `BR-CUS-094` keeps a legacy code *"still a valid FK, still filterable, still
    priceable"*: a tax restriction is a filter over accounts, and accounts still
    carry the code. Dropping it would invalidate every restriction already
    stored against it. `legacy` closes the PICKER on a new account's own
    category; it does not close this list.

    ── COST, MEASURED RATHER THAN ASSUMED ────────────────────────────────────
    The seam this replaces read constants precisely to keep a query out of a
    per-row validator. This is ONE indexed read of an eight-row table per write
    request, and the one place it sat inside a LOOP — the reference-fixture
    seeder in `services._seed_tax_jurisdictions` — now hoists it above the loop.
    No database is touched at import time: this is a function, evaluated when it
    is called, exactly as the constants version was not.

    ⚠ **A TENANT THAT HAS DEACTIVATED EVERY ROW GETS AN EMPTY TUPLE, AND THAT IS
    THE RULE RATHER THAN A HOLE.** Seeded rows are `is_system` — deactivatable,
    never deletable — so the state is reachable. Falling back to the ruled
    vocabulary there would resurrect the very rows the tenant retired, which is
    exactly what `BR-TEN-034` forbids and what `_resolve_unit_type` is careful
    about. An empty list refuses every restriction, which fails CLOSED: a
    utility with no customer classes cannot narrow a charge to one, and the
    field error says so rather than a rate silently applying to everybody.
    """
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    held = {row.code: row.active for row in qs.only("code", "active")}
    if not held:
        return account_type_codes()
    ruled = account_type_codes()
    ordered = [code for code in ruled if held.get(code)]
    ordered += sorted(code for code, active in held.items() if active and code not in ruled)
    return tuple(ordered)


# ── customers: does this account exist, for a tax exemption? (DEF-383) ──────
def account_exists(account_id: Any) -> bool:
    """Is this id an account OF THIS TENANT? Read-only, through customers.

    `tax_exemption_certificates.account_id` is a DEFERRED-FK uuid (B2 §2 keeps
    `accounts` in customers and rating may not add an FK to it), which means the
    column will accept any well-formed uuid — including one belonging to another
    tenant, or to nothing at all. A certificate stored against a nonexistent
    account looks like a live exemption for ever and matches no bill: a silent
    no-op that fails in the safe direction and is therefore invisible.

    So the id is checked when it is PICKED, which is CR-008 second-set ruling 3
    applied one table over (*"a mapping is validated when it is picked, not only
    when a bill runs"*) — the same posture `_validated_gl_account` takes for a
    ledger pointer.

    Answers **False** for a malformed id rather than raising: the caller turns
    it into a field error on `account_id`, which is where an operator can see
    it, and a `ValidationError` from deep inside a seam would surface as a 500.

    ── THE ENG DISPOSITION, RECORDED ─────────────────────────────────────────
    Read through `django.apps.get_model`, the SAME disposition this module
    records at the top for tenancy's `Service`/`TenantService`: customers
    publishes `account_row`, which takes a MODEL INSTANCE and builds a whole S17
    row with the ledger's and billing's answers joined in — several cross-module
    reads to answer "does this id exist". There is no published existence check.
    Read-only, tenant-filtered, never a write. A published
    `customers.selectors.account_exists` would be better and is named in the
    lane's write-back rather than added to another module's file by this lane.
    """
    if account_id in (None, ""):
        return False
    account_model = django_apps.get_model("customers", "Account")
    try:
        return account_model.objects.filter(tenant_id=_tenant_id(), pk=account_id).exists()
    except (ValueError, ValidationError):
        return False  # not a uuid at all — a field error, not a 500


# ── metering: the premises a tax scope is measured against (DEF-380) ────────
def premises_geography_rows(limit: int | None = None) -> list[dict[str, Any]]:
    """Every premises of this tenant, reduced to the FOUR facts a tax scope can
    be evaluated against — plus enough to name one on screen.

    ── WHY THIS SEAM EXISTS AT ALL ───────────────────────────────────────────
    CR-013 part 4, TAX-02 step 1, verbatim: *"Shows the matched premise count so
    a wrong boundary is visible before rates are entered"*, and step 4:
    *"read-back with matched premise count and sample line"*. That safeguard had
    no source (DEF-380): `premises_in_scope` answers ONE premises at a time and
    was reachable only from the bill run, so the wizard could state the absence
    and nothing else. r10 carries the figure it protects — *"61 outside-city
    accounts exempt"*.

    ── WHY IT RETURNS FACTS AND NOT A COUNT ──────────────────────────────────
    Because the RULE must have exactly one implementation. `premises_in_scope`
    is what decides whether a premises attracts a tax on a real bill; if this
    seam returned a count computed from a WHERE clause, the wizard's promise and
    the bill would be two implementations of one rule, and they would disagree
    the first time either changed. So the seam hands back the facts and
    `selectors.matched_premises` runs the same predicate the engine runs. At the
    product's own scale — under 3,000 connections, CLAUDE.md line 1 — that is a
    few thousand small rows, and correctness is worth more than the WHERE.

    ── THE ENG DISPOSITION, RECORDED ─────────────────────────────────────────
    `premises` is METERING's table (B2 §2) and metering publishes no selector
    that answers this: `premises_list` is a paginated screen read with sorting,
    filters and a rollup, and `premises_detail` answers one row. So the row is
    read through `django.apps.get_model` — the SAME disposition this module
    already records for tenancy's `Service`/`TenantService` at the top of this
    file. Read-only, tenant-filtered, never a write. A published metering
    selector would be better and is named in the lane's write-back rather than
    smuggled into another module's file by this lane.

    `inside_city_limits` is read through `.values()` with a `try` around the
    column name for the reason `gather._premises_geography` gives beside its own
    `getattr`: BR-RAT-101 landed the column on 2026-08-21, and a deployment
    whose metering migration has not run yet must degrade to the recorded city
    name rather than raise inside a wizard step.
    """
    premises_model = django_apps.get_model("metering", "Premises")
    fields = ["id", "premise_no", "address_line", "city", "state", "postal_code"]
    qs = premises_model.objects.filter(tenant_id=_tenant_id()).order_by("premise_no", "id")
    try:
        rows = list(qs.values(*fields, "inside_city_limits")[: limit or 100_000])
    except Exception:  # pragma: no cover — pre-BR-RAT-101 schema only
        rows = list(qs.values(*fields)[: limit or 100_000])
    return [{key: row[key] for key in row} for row in rows]



# ── customers + metering: WHO and WHAT SERVICE each premises has (PRB-05) ───
def premises_reach_facts() -> dict[str, dict[str, tuple[str, ...]]]:
    """Per premises: the customer CLASSES billed there and the SERVICES metered
    there — `{premises_id: {"customer_classes": (...), "services": (...)}}`.

    ── WHY THIS EXISTS, AND WHY IT IS A SECOND SEAM RATHER THAN MORE COLUMNS ──
    `premises_geography_rows` answers *where is this premises*. `tax_applies_to`
    asks three questions of a bill and geography is only the third; the other
    two — *which customer class* and *which services* — are facts about the
    ACCOUNT and the SERVICE POINTS at that address, in two other modules'
    tables. They are fetched separately because the geography read is already
    cited by `gather` and by `test_cr013_p4_tax_model`, and because a count that
    states no class and no service restriction must not pay for either query
    (`selectors.matched_premises` skips this call entirely in that case).

    ── WHY BOTH ARE SETS AND NOT SINGLE VALUES ───────────────────────────────
    `tax_applies_to` describes ONE BILL: one customer class, the services on
    that bill. A PREMISES is not one bill — a duplex can hold a residential
    tenant and a commercial one, and a house can be metered for electric and
    water. The question this seam feeds is *"does this tax reach ANY bill at
    this address"*, so the caller tries each class it finds and passes every
    service at once, exactly as a bill for that address would carry them.

    ── WHAT AN EMPTY ANSWER MEANS, AND IT IS NOT "NO RESTRICTION" ────────────
    A premises with no account has NO customer class, and `tax_applies_to` then
    refuses a class-restricted tax (DEF-273's fail-safe: under-charging is
    recoverable in the next cycle, over-charging a customer who is exempt is a
    refund and a support cycle). The caller must therefore pass `None` rather
    than skip the gate — which is what "reaches nobody" honestly means for a
    vacant address under a Commercial-only tax.

    ⚠ **EVERY ACCOUNT COUNTS, WHATEVER ITS STATUS.** A closed account's premises
    is still an address this tax would reach the day somebody moves in, and this
    read exists to check a BOUNDARY before a rate is typed rather than to bill
    anybody. Narrowing it to active accounts would make the safeguard shrink
    every time a tenant moved out, which is not a boundary fault and is exactly
    the false alarm the count is supposed to avoid.

    ⚠ **AN ACCOUNT REACHES ITS PREMISES BY EITHER ROAD.** A `regular` account
    names a unit and the unit names the premises; a `master` account (BR-CUS-068)
    names `premises_id` directly and may name no unit at all. Reading only the
    unit road would lose every landlord's own account, which is precisely the
    account a franchise fee on Commercial customers is about.

    Read-only, tenant-scoped, never a write — the same disposition this module
    records for every other cross-module read above (B1/B8).
    """
    facts: dict[str, dict[str, set[str]]] = {}

    def bucket(premises_id: Any) -> dict[str, set[str]] | None:
        if premises_id is None:
            return None
        return facts.setdefault(
            str(premises_id), {"customer_classes": set(), "services": set()}
        )

    account_model = django_apps.get_model("customers", "Account")
    for via_unit, via_premises, code in account_model.objects.filter(
        tenant_id=_tenant_id()
    ).values_list("unit__premises_id", "premises_id", "account_type__code"):
        row = bucket(via_unit if via_unit is not None else via_premises)
        if row is not None and code:
            row["customer_classes"].add(str(code).strip())

    service_point = django_apps.get_model("metering", "ServicePoint")
    for premises_id, code in service_point.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True
    ).values_list("unit__premises_id", "service__code"):
        row = bucket(premises_id)
        if row is not None and code:
            row["services"].add(str(code).strip())

    return {
        premises_id: {
            # Sorted so a sample line and a failure message are stable between
            # requests — IS-2's stable-order law applied to a fact, not a cell.
            "customer_classes": tuple(sorted(row["customer_classes"])),
            "services": tuple(sorted(row["services"])),
        }
        for premises_id, row in facts.items()
    }


# ── identity: a user id → the name a person recognises (DEF-367) ────────────
def user_display_names(user_ids: list[Any]) -> dict[str, str]:
    """`{user_id: full_name}` for one page of rows. DEF-367.

    ⚠ **THE CONVENTION IS COPIED, NOT INVENTED.** `apps/audit/selectors.py`
    already answers this exact question for the audit trail — one tenant-scoped
    read of `identity.User.full_name` for a whole page, and a served
    `{"id", "name"}` pair per row so a name that cannot be resolved is a stated
    absence rather than a blank. A rate schedule's *"who filed this"* is the
    same question about the same table, so it gets the same shape and the same
    read; a second convention for one fact is how two screens start disagreeing
    about a person's name.

    **Batched deliberately.** A filings table draws every version of a schedule,
    and a per-row resolve is a query per row — the shape `actor_names` was
    written to avoid.

    Users are PER-TENANT rows (BR-IDN-029), so the lookup is tenant-scoped like
    every other read in this module. Read-only, and never a write: identity owns
    the table (B1/B8).

    An id with no row answers with NO KEY, not with an empty string — BR-IDN-030
    keeps user rows, but a version outlives any row and the caller must be able
    to tell "this person is gone" from "this person is called ''".
    """
    wanted = {str(user_id) for user_id in user_ids if user_id is not None}
    if not wanted:
        return {}
    user_model = django_apps.get_model("identity", "User")
    rows = user_model.objects.filter(tenant_id=_tenant_id(), id__in=wanted).values_list(
        "id", "full_name"
    )
    return {str(user_id): full_name for user_id, full_name in rows if full_name}


# ── metering: what each of these units last USED (DEF-434) ─────────────────
def recent_consumption_by_unit(service_code: str, unit_ids: list[Any]) -> dict[str, Any]:
    """The most recent metered consumption per unit, for ONE service.

    **Why rating asks for this at all.** BR-RAT-091 clause 2 gates a rate change
    on its *"worst-case bill change"*, and a bill change cannot be computed
    without a quantity to price. CR-013 part 1 makes the impact analysis
    MANDATORY on RAT-03 step 4 and names four figures; three of them are a
    function of what the tenant's accounts actually consume (`DEF-434`).

    RETURNS `{"wired": bool, "rows": {unit_id: {"amount", "unit", "read_at"}}}`
    — the same two-key shape as `last_issued_bill_for_unit` and
    `active_asset_count` above, and for the identical reason stated there: an
    empty `rows` cannot distinguish **"these units have never been read"** from
    **"this read does not exist"**, and the second must never be reported as a
    measured zero. A rate change whose impact reads `0.00%` because metering
    moved is the exact failure that shape exists to stop.

    ⚠ **A UNIT WITH NO READ IS ABSENT FROM `rows`, NEVER PRESENT AT ZERO.**
    CLAUDE.md hard rule 3 in its other direction: a quantity we do not have is
    not a quantity of nothing. The caller counts those units as affected and
    UNPRICED, which is what keeps the worst case from being dragged toward zero
    by every account that has not been metered yet.

    ⚠ **THE ENG DISPOSITION, RECORDED** — the same one this module's header
    already records for tenancy's `Service`/`TenantService` and customers'
    `Account`: `metering` publishes no selector answering *"what did this unit
    last consume"* (`apps/billing` gets its readings passed IN by the run, and
    `apps/metering/selectors.py` has no such read), so the row is read through
    `django.apps.get_model`. Read-only, tenant-filtered, never a write. A
    published `metering.selectors.recent_consumption_by_unit` would be better
    and is named in this lane's write-back rather than added to another module's
    file by this lane.

    The join is `MeterRead.asset → assets.Asset.service_point →
    metering.ServicePoint(unit, service)`, which is the only path from a read to
    the service it measures. Reads with a NULL consumption are excluded rather
    than defaulted — BR-MET-028 writes an estimate with no `current_value`, and
    an estimate that has not produced a consumption has produced nothing.
    """
    wanted = [str(unit_id) for unit_id in unit_ids if unit_id is not None]
    if not wanted:
        return {"wired": True, "rows": {}}
    try:
        read_model = django_apps.get_model("metering", "MeterRead")
    except LookupError:  # pragma: no cover - the app package always registers
        return {"wired": False, "rows": {}}
    try:
        rows = list(
            read_model.objects.filter(
                tenant_id=_tenant_id(),
                asset__service_point__unit_id__in=wanted,
                asset__service_point__service__code=service_code,
                consumption__isnull=False,
            )
            .order_by("-read_at")
            .values_list("asset__service_point__unit_id", "consumption", "unit", "read_at")
        )
    except Exception:  # pragma: no cover - a schema without the join is UNWIRED
        return {"wired": False, "rows": {}}
    latest: dict[str, dict[str, Any]] = {}
    for unit_id, consumption, uom, read_at in rows:
        key = str(unit_id)
        # Ordered newest-first, so the FIRST row seen for a unit is its latest.
        if key in latest:
            continue
        # Hard rule 3: a quantity with no unit is not a quantity. Skipped rather
        # than defaulted to the schedule's billed unit — that guess is exactly
        # what BR-RAT-038's UoM gate exists to refuse.
        if not uom:
            continue
        latest[key] = {"amount": Decimal(str(consumption)), "unit": uom, "read_at": read_at}
    return {"wired": True, "rows": latest}


# ── billing: WHICH of the two stored base charges a bill charges (DEF-434) ──
def base_charge_for(
    service_code: str,
    *,
    customer_class: str | None = None,
    size_class: str | None = None,
    named_code: str | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

    ⚠ **THIS FUNCTION IS A MONEY PATH AND `human_owned.txt` MATCHES NO GLOB
    AGAINST THIS FILE**, so `G7` reports CONFORM over it. That is the FOURTH
    time that exact escape has happened here — `issue.py`, `decisions.py` and
    `read_analysis.py` each record it in `human_owned.txt` in the same words,
    *"the file already carried HUMAN-REVIEW-PENDING and a ledger row and no
    glob here matched it"*. **Adding the glob is a process event and the PO's
    call, never a lane's** (that list's own rule: who watches the watchers), so
    it is put to them in the ledger instead of taken here.

    DEF-154's precedence, asked of the module that owns it.

    ⚠ **AND SINCE 2026-08-31 IT IS BR-RAT-088's PRECEDENCE (`DEF-2823`).** The
    CHARGE CODE owns the base; the plan and the schedule are read only to catch
    a migration artefact. The third figure is resolved HERE — from this
    module's own `selectors.base_charge_from_charge_code` — and handed to
    billing's function, so the impact analysis and the bill run go on reading
    ONE implementation of the precedence. Re-deriving it would put a second
    copy of a money decision in a second module, which is the whole reason this
    seam exists.

    `customer_class` and `size_class` are the two narrowing facts the base code
    takes (BR-RAT-108's class scoping, and the per-size table). An impact
    analysis that does not hold them passes neither, and gets the same answer a
    tenant with one unscoped, flat base code would get — which is every tenant
    this product provisions today.

    ── `named_code` · WHAT THE RATE SCHEDULE SAID (`BR-RAT-1025`) ────────────
    ⚠ **THIS PARAMETER IS `DEF-RAT-6960`, AND THE DEFECT WAS THAT IT DID NOT
    EXIST.** The paragraph below says this seam is here so an impact figure
    cannot differ from the bill. That claim held only while BOTH ignored the
    schedule's binding; `DEF-RAT-5782` made the bill honour it on 2026-09-27
    and left this door behind, so the two surfaces that read the base through
    here — the rate-change impact analysis and the customer portal's standing
    charge — began refusing, or quoting, a base the bill charges. **A comment
    claiming a guarantee is not the guarantee (hard-won law 1); this argument
    is only true if the binding travels.**

    **`None` MEANS THE SCHEDULE NAMED NOTHING**, which is every version
    written before `rating/0037`, and it is byte-identical to the call this
    seam made yesterday — so nothing moves on a tenant that has bound nothing.
    ⚠ **SUPERSEDED 2026-10-06 (`DEF-RAT-9832`, PO ruling):** `None` no longer
    reaches a pooled code — it answers `$0.00`, exactly as the bill does.

    ⚠ **IT IS PASSED UNCONDITIONALLY AND IS NEVER DEGRADED**, the posture
    `billing.gather._base_charge_code_for` takes and for the same reason:
    dropping the binding prices the INFERRED code under a schedule naming
    another, and what the screen then shows is a figure nobody will be billed.
    A named code that cannot answer REFUSES, here as it does on the bill, so
    the three surfaces fail together rather than one refusing while another
    quietly shows an inferred figure.

    ⚠ **THE CALLER HANDS DOWN ITS OWN VERSION'S BINDING AND NEVER LOOKS ONE
    UP.** `selectors.named_base_charge_code` is the one narrowing; a second
    hand-written copy of it is how two doors start disagreeing about what the
    binding IS, which is this defect's own shape one level down.

    RETURNS `{"wired": bool, "amount": Decimal | None, "refusal": str | None}`.

    ⚠ **WHY THIS IS A SEAM AND NOT FOUR LINES OF `if`.** The impact analysis has
    to price the SAME bill a bill run would produce, and *"a second
    implementation of pricing is how two screens start disagreeing about a
    figure"*. The base charge is where that has already happened once: DEF-154
    is the defect where **every bill this product produced charged `$0.00` for
    base** because billing read the schedule's column while the signed source
    (BR-RAT-012 / BR-RAT-027) is the PLAN's. Re-deriving the precedence here
    would put a second copy of that decision in a second module, and its two
    REFUSALS — a base stated nowhere (DEF-277: *"blank base = size not served"*)
    and a base stated twice and disagreeing (OQ-238) — would be copied with it.

    An impact figure that includes a base a bill would REFUSE to charge is not
    an impact figure; it is a number nobody will ever be billed. So the refusal
    travels back as a REASON and the account is counted as affected and
    **unpriced**, never priced at a base we invented for it.

    Called by name across the seam like every other read in this module. It
    resolves a PRIVATE function (`apps.billing.gather._base_charge_for`) because
    billing publishes no public one — recorded here rather than worked around,
    and named in this lane's write-back the same way `account_exists` names the
    missing `customers.selectors.account_exists`.
    """
    try:
        gather = import_module("apps.billing.gather")
    except ImportError:  # pragma: no cover - the app package always imports
        return {"wired": False, "amount": None, "refusal": None}
    fn = getattr(gather, "_base_charge_for", None)
    if not callable(fn):
        return {"wired": False, "amount": None, "refusal": None}
    from apps.rating import selectors  # local: this module is imported by selectors

    code = selectors.base_charge_from_charge_code(
        service_code,
        customer_class=customer_class,
        size_class=size_class,
        named_code=named_code,
        # CR-156-BRC10 — the price row in force on the day asked (today when
        # the caller names none).
        on_date=on_date,
    )
    if code.get("refusal_reason") == selectors.BASE_NOT_NAMED:
        # `DEF-RAT-9832` (PO 2026-10-06) — the schedule names no base code, so
        # the bill charges `$0.00` for it; this seam states the same `$0.00`
        # (billing's own function, `code_base=None`), never a code from the pool.
        return {"wired": True, "amount": fn(service_code, code_base=None), "refusal": None}
    if code["refusal"]:
        # Rating's OWN refusal, carried as the reason. The account is affected
        # and UNPRICED — never priced at a base we invented for it.
        return {"wired": True, "amount": None, "refusal": "BaseChargeCodeUnresolved"}
    try:
        # ⚠ **NO `code_label=` — IT WAS REMOVED FROM BILLING'S FUNCTION ON
        # 2026-09-24 AND THIS CALL WENT ON PASSING IT FOR THREE DAYS
        # (`DEF-RAT-7000`).** `DEF-CUS-6550` cut a 63-word refusal to ten
        # under B14 rule 33, which left `code_label` reading nothing, and
        # `gather._base_charge_for` dropped the parameter — correctly. **This
        # caller was not moved with it**, so every call where the charge code
        # ANSWERS raised `TypeError: _base_charge_for() got an unexpected
        # keyword argument 'code_label'` — which the `except` below then
        # reported as an ordinary refusal named `TypeError`.
        #
        # ⚠ **THE `except Exception` IS WHY NOBODY SAW IT, AND IT IS KEPT
        # ANYWAY.** It exists to carry billing's own named refusal back rather
        # than swallowing it, and it did its job; what it cannot do is tell a
        # REFUSAL from a BROKEN CALL, so a signature change downstream read on
        # every screen as *we cannot work this out* over a bill that was being
        # produced perfectly well. Every tenant with an `is_base` charge code
        # was affected — which is every tenant this product provisions — and
        # `tsc`, every gate and the whole suite were green over it, because
        # the nine cases that DID go red were read as an impact-analysis
        # fault (`DEF-RAT-6980`) rather than as this.
        #
        # **The durable repair is the test, not the comment**: the seam is now
        # exercised on a configuration where the code answers, so a caller and
        # a callee that stop agreeing about a signature go red by name.
        # ⚠ **AND IT HAPPENED AGAIN ONE WEEK LATER, WHICH IS WHY THE
        # PARAGRAPH ABOVE IS WORTH ITS LENGTH (`DEF-BIL-7170`, 2026-09-28).**
        # The PO retired the plan's and the rate schedule's base figures —
        # *"we will never take default value from plan $8.0 - that is
        # retired"* — so `_base_charge_for` lost `plan_base` and
        # `schedule_base` and took `code_base` as KEYWORD-ONLY. A caller left
        # passing three positionals would have handed the PLAN's figure in as
        # the charge code's, and `except Exception` would once more have
        # reported a broken call as an ordinary refusal. **This seam's own two
        # parameters went with them**, so there is nothing left here to pass
        # by mistake.
        return {
            "wired": True,
            "amount": fn(service_code, code_base=code["amount"]),
            "refusal": None,
        }
    except Exception as problem:  # billing's own named refusal, carried not swallowed
        return {"wired": True, "amount": None, "refusal": type(problem).__name__}


# ── tenancy: the tenant's own configured connection sizes (DEF-2190) ────────
def configured_size_class_codes() -> tuple[str, ...]:
    """The ACTIVE `service_size_classes` codes this tenant has configured.

    `charge_code_amounts.size_class` is `service_size_classes.code` as TEXT,
    and the reason the model gives for that is the reason this read exists:
    *"a size Settings RETIRES must not vanish from a schedule that already
    priced it"*. So the code cannot be an FK — and without SOME check a charge
    code can be priced against a size string nothing will ever look up, which
    bills nothing and says nothing. That is DEF-2190's second half.

    The list is `apps.tenancy.models.MeterSizeClass` — the hosted table keeps
    the OLD name (DEF-970) while `list_code` is `service_size_classes`
    (BR-TEN-170) — and it is the SAME rows `/lookups/service_size_classes`
    publishes, which is what the connection-size control on AST-05 and the
    rate-schedule size matrix both read. One source, so a size that saves on a
    charge code is a size a meter can actually be.

    ⚠ **ACTIVE ROWS ONLY, AND THE CALLER MUST UNION IT WITH WHAT IS ALREADY
    STORED.** Deactivating a size on S8 must not make a charge code that
    already priced that size unsaveable — that is the retire-survival rule
    above, read backwards. `_validate_size_amounts` does exactly that.

    Read-only, tenant-filtered, through `django.apps.get_model` — the same
    disposition this module records for the service catalog: tenancy exposes no
    selector that returns a bare code list.
    """
    tenant_id = _tenant_id()
    if tenant_id is None:
        return ()
    model = django_apps.get_model("tenancy", "MeterSizeClass")
    return tuple(
        str(code)
        for code in model.objects.filter(tenant_id=tenant_id, active=True)
        .order_by("code")
        .values_list("code", flat=True)
    )


# ── customers: the ONE seeded account behind a unit number (CR-062 add. J2) ──
def sample_account_id_for_unit(unit_no: str) -> Any | None:
    """The id of the SAMPLE account occupying this unit number, or `None`.

    ⚠ **THIS EXISTS FOR ONE ENROLMENT AND IT IS DELIBERATELY THAT NARROW.**
    `CR-062` addendum J2 seeds the first account enrolment this fixture has ever
    carried — the Municipal discount on the one seeded government building — and
    an enrolment is written by `discount_services.enrol_account`, which is
    rating's own service, against an account id, which is customers' fact. So
    the WRITE stays in rating (`B1` / `BR-TEN-013`) and only the LOOKUP crosses.

    **Read-only, tenant-filtered, `is_sample` only.** The `is_sample` filter is
    not tidiness: it is what stops this seam from ever handing a REAL customer's
    account to a subsidy seeder. A fixture that discounted a live account would
    be exactly the *available-versus-granted* failure `BR-RAT-069` exists to
    prevent, one table further along.

    ── THE ENG DISPOSITION, RECORDED ─────────────────────────────────────────
    Read through `django.apps.get_model`, the SAME disposition `account_exists`
    above records and for the same reason: customers publishes `account_row`,
    which builds a whole S17 row with the ledger's and billing's answers joined
    in, and there is no published *"which account is on this unit"* read. A
    published `customers.selectors.sample_account_for_unit` would be better and
    is named in this lane's write-back rather than added to another module's
    file by this lane.
    """
    tenant_id = _tenant_id()
    if tenant_id is None or not unit_no:
        return None
    account_model = django_apps.get_model("customers", "Account")
    row = (
        account_model.objects.filter(
            tenant_id=tenant_id, is_sample=True, unit__unit_no=str(unit_no)
        )
        .values("id")
        .first()
    )
    return row["id"] if row else None


# ── metering + customers: what one page of a plan's units IS (PRB-21) ───────
def plan_unit_facts(unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`{unit_id: {label, unit_no, premises_address, premises_city, services,
    account_no, account_closed}}` for ONE PAGE of a plan's units.

    ── WHY THIS SEAM EXISTS ──────────────────────────────────────────────────
    `CR-087` D5 / `PRB-21`, the PO of 2026-09-08: *"second tab can be units"*.
    The plan showed a count of 74 with no way to see what was in it, and nothing
    said whether 74 meant units, accounts or customers. Rating already counts
    unit→plan assignments — that is where 74 comes from — and no read returned
    them.

    ── WHY IT TAKES A PAGE AND NOT A PLAN ────────────────────────────────────
    Because `NFR-3` is the deliverable rather than the background. The caller
    pages the ASSIGNMENTS in SQL and hands this the ids it is actually going to
    draw, so a tenant with 40,000 units never materialises 40,000 rows to render
    fifty. A seam that took a plan id would have to decide the paging itself, in
    a second place, and the two would drift.

    ── THE ADDRESS IS WALKED, NEVER STORED HERE ──────────────────────────────
    CLAUDE.md hard rule 8: an address lives on `premises` and NOWHERE else, and
    every other entity — a unit included — derives it by walking. A unit refines
    a premises by LABEL, so `label` and `premises_address` are two different
    facts and both travel; nothing here composes a second address.

    ── THE VACANT UNIT IS THE ROW THIS TAB EXISTS FOR ────────────────────────
    A plan attaches to a UNIT, not to an account, so a unit with no account is
    still on the plan and its base charges still reach the OWNER's bill. The
    fact is served as `account_no: None`, and the SCREEN says what that means —
    a clerk who reads a dash concludes nothing is billed, which is the opposite
    of the truth. A CLOSED account is served with its number and
    `account_closed: True` rather than as a blank, because "closed" and "never
    had one" are different facts about a bill.

    ── THE ENG DISPOSITION, RECORDED ────────────────────────────────────────
    `units`, `premises` and `service_points` are METERING's tables and
    `accounts` is CUSTOMERS' (B2 §2); neither module publishes a selector that
    answers this question, so the rows are read through `django.apps.get_model`
    — the SAME disposition `premises_geography_rows` records above and the same
    one this file already records for tenancy's catalogue. **Read-only,
    tenant-filtered, never a write.** A published selector on either side would
    be better and is named in this lane's write-back rather than smuggled into
    another module's file.
    """
    ids = [one for one in unit_ids if one is not None]
    if not ids:
        return {}
    tenant_id = _tenant_id()
    unit_model = django_apps.get_model("metering", "Unit")
    units = unit_model.objects.filter(tenant_id=tenant_id, id__in=ids).values(
        "id", "label", "unit_no", "premises_id", "premises__address_line", "premises__city"
    )
    facts: dict[str, dict[str, Any]] = {
        str(row["id"]): {
            "label": row["label"],
            "unit_no": row["unit_no"],
            # The PREMISES' own columns, walked. Not copied to the unit.
            "premises_address": row["premises__address_line"],
            "premises_city": row["premises__city"],
            # `DEF-RAT-9353` — the premises' reference, so the Units tab can
            # LINK it (ruling 13). Keyed by, never shown (B14 rule 31).
            "premises_id": row["premises_id"],
            "services": [],
            "account_no": None,
            "account_closed": False,
            "customer_name": None,
            "account_id": None,
        }
        for row in units
    }

    point_model = django_apps.get_model("metering", "ServicePoint")
    points = (
        point_model.objects.filter(
            tenant_id=tenant_id, unit_id__in=ids, deleted_at__isnull=True
        )
        .select_related("service")
        .values("unit_id", "service__code", "service__sort")
        .order_by("service__sort", "service__code")
    )
    for row in points:
        entry = facts.get(str(row["unit_id"]))
        # A service CODE, so the screen draws the badge the product already
        # ships. The letter is never derived from the name — six of the eleven
        # services collide on their initial.
        if entry is not None and row["service__code"] not in entry["services"]:
            entry["services"].append(row["service__code"])

    account_model = django_apps.get_model("customers", "Account")
    accounts = (
        account_model.objects.filter(tenant_id=tenant_id, unit_id__in=ids)
        .select_related("status")
        .values("id", "unit_id", "account_no", "status__behavior_class", "created_at")
        .order_by("unit_id", "-created_at")
    )
    # The account a row names: the newest OPEN one, else the newest closed one
    # (`DEF-RAT-9361` — an older open account must not hide behind a newer
    # closed one, or the row and the filter disagree again). Bounded by the page.
    chosen: dict[str, dict[str, Any]] = {}
    for row in accounts:
        key = str(row["unit_id"])
        held = chosen.get(key)
        is_open = row["status__behavior_class"] != ACCOUNT_CLOSED_CLASS
        if held is None or (is_open and held["status__behavior_class"] == ACCOUNT_CLOSED_CLASS):
            chosen[key] = row
    for key, row in chosen.items():
        entry = facts.get(key)
        if entry is None:
            continue
        entry["account_no"] = row["account_no"]
        # BR-CUS-055's behaviour class, not the tenant's LABEL for it: a utility
        # may call the terminal status anything and billing keys off the class.
        entry["account_closed"] = row["status__behavior_class"] == ACCOUNT_CLOSED_CLASS
        entry["_account_id"] = row["id"]
        # `DEF-RAT-9353` — kept as well as popped below: the Units tab LINKS the
        # account (never shows this; B14 rule 31).
        entry["account_id"] = row["id"]
    # `CR-167-BRC10` §7.3 — the Units tab's Customer column: the first customer
    # linked to the unit's newest account, by name (never an id).
    link_model = django_apps.get_model("customers", "CustomerAccount")
    wanted = {entry.pop("_account_id"): key for key, entry in facts.items() if "_account_id" in entry}
    if wanted:
        for link in (
            link_model.objects.filter(tenant_id=tenant_id, account_id__in=list(wanted))
            .order_by("account_id", "id")
            .values("account_id", "customer__display_name")
        ):
            key = wanted.get(link["account_id"])
            if key is not None and facts[key]["customer_name"] is None:
                facts[key]["customer_name"] = link["customer__display_name"]
    return facts


# ── CR-157-BRC10 wave B — three reads the rebuilt rate-schedule screens need ─
# Each read-only, tenant-filtered, through `django.apps.get_model` — the SAME
# disposition `plan_unit_facts` and `account_type_code_by_id` record above: the
# owning module publishes no selector answering exactly this, and a published
# one would be better and is named in this lane's write-back rather than added
# to another module's file.


def account_type_names_by_code() -> dict[str, str]:
    """`{account_types.code: name}` for every class this tenant can name — the
    words a charge code's class-priced row is printed in (`CR-167-BRC10`)."""
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    return {str(row["code"]): str(row["name"]) for row in qs.values("code", "name")}


def customer_class_options() -> list[dict[str, str]]:
    """Every customer class a plan can name, `[{id, name}]`, by name — the
    New/Edit form's tick dropdown (ruling 4). Read-only, tenant-scoped on the
    same condition as `account_type_names`."""
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    if any(field.name == "active" for field in model._meta.get_fields()):
        qs = qs.filter(active=True)
    return [
        {"id": str(row["id"]), "name": str(row["name"])}
        for row in qs.order_by("name").values("id", "name")
    ]


def service_revenue_gl_account_id(service_code: str) -> Any | None:
    """The ledger's revenue account for a service — the *GL 4110* under each
    service on the plan screens when the plan line names none. Through the
    ledger's published selector; `None` when it cannot answer."""
    try:
        reader = getattr(import_module("apps.ledger.selectors"), "revenue_account_id_for_service")
    except (ImportError, AttributeError):  # pragma: no cover
        return None
    try:
        return reader(service_code)
    except Exception:  # noqa: BLE001 — a display read never stops a screen
        return None


def occupied_unit_ids_subquery() -> Any:
    """The ids of units with an account that is not closed — a QUERYSET used as
    a SQL sub-select by the plan's Units tab filter (`CR-167-BRC10` J11), so
    the page, the count and the CSV come from one query (`NFR-3`). Customers'
    table, read-only, tenant-filtered."""
    account_model = django_apps.get_model("customers", "Account")
    return (
        account_model.objects.filter(tenant_id=_tenant_id(), unit_id__isnull=False)
        .exclude(status__behavior_class=ACCOUNT_CLOSED_CLASS)
        .values("unit_id")
    )


#: `DEF-RAT-9361` — THE ONE DEFINITION OF *OCCUPIED* on a plan's Units tab: a
#: unit is occupied when it has an account whose status is not of this
#: behaviour class. The filter (`occupied_unit_ids_subquery`, a SQL sub-select)
#: and the row (`plan_unit_facts` → `selectors.plan_unit_rows`'s `vacant`) both
#: read it; they used to differ — the row called a unit occupied when it had
#: ANY account, so with *Vacant* on, a unit whose only account was closed was
#: listed under a row reading *Occupied*.
ACCOUNT_CLOSED_CLASS = "terminal"


def account_type_names(account_type_ids: list[Any]) -> dict[str, str]:
    """`{account_type_id: name}` for the ids given — the customer class a
    screen PRINTS (B14 rule 31: never the id). Tenant-scoped on the same
    condition as `account_type_code_by_id`. One query for the batch; an id the
    tenant cannot name is simply absent, and the caller draws the absence."""
    ids = list(dict.fromkeys(str(one) for one in account_type_ids if one))
    if not ids:
        return {}
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=_tenant_id())
    return {str(row["id"]): str(row["name"]) for row in qs.filter(pk__in=ids).values("id", "name")}


def size_class_names(codes: list[str]) -> dict[str, str]:
    """`{size_class code: name}` from this tenant's `service_size_classes`
    (`tenancy.MeterSizeClass`) — inactive rows included, because a size
    Settings retired must not lose its NAME on a schedule that still prices it
    (`configured_size_class_codes`' retire-survival rule). A code with no row
    is absent and the caller prints the code."""
    wanted = [code for code in dict.fromkeys(codes) if code]
    tenant_id = _tenant_id()
    if not wanted or tenant_id is None:
        return {}
    model = django_apps.get_model("tenancy", "MeterSizeClass")
    return {
        str(row["code"]): str(row["name"])
        for row in model.objects.filter(tenant_id=tenant_id, code__in=wanted).values(
            "code", "name"
        )
    }


def unit_counts_by_size_class(
    unit_ids: list[Any], service_code: str, as_of: date
) -> dict[str | None, int]:
    """`{size_class: units}` — of these units, how many have an IN-SERVICE
    asset of this service of each size on `as_of`. The Rates tab's *Units*
    column (`09-view-W-RES-rates.png`: 5/8" 829 · 3/4" 266 …).

    **`assets.selectors.billable_asset_size_classes`' THREE PREDICATES**, asked
    for a set of units at once instead of one: on the unit ON THAT DATE (the
    dated `AssetAssignment`), IN SERVICE by the stage's `behavior_class`, FOR
    THIS SERVICE through the asset's service point — so the column counts the
    same population billing sizes from. A unit is counted once per size it has
    (two 2" lines on one unit are one unit on 2"). `None` collects assets whose
    size nobody recorded (`BR-AST-500`), and it is reported, never dropped.

    One grouped query whatever the number of units (`NFR-3`); nothing caps it
    (`NFR-5`).
    """
    ids = [one for one in unit_ids if one is not None]
    tenant_id = _tenant_id()
    if not ids or tenant_id is None:
        return {}
    from django.db.models import Count, Q

    model = django_apps.get_model("assets", "AssetAssignment")
    rows = (
        model.objects.filter(
            tenant_id=tenant_id,
            unit_id__in=ids,
            from_date__lte=as_of,
            asset__status__behavior_class="in_service",
            asset__service_point__service__code=service_code,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=as_of))
        # `DEF-MET-9037` (PO 2026-10-02) — the population billing sizes from
        # holds no read device, so neither does this column.
        .exclude(asset__type__category__in=("meters", "sub_meters"))
        .values("asset__size_class")
        .annotate(n=Count("unit_id", distinct=True))
    )
    out: dict[str | None, int] = {}
    for row in rows:
        text = str(row["asset__size_class"]).strip() if row["asset__size_class"] else ""
        key = text or None
        out[key] = out.get(key, 0) + int(row["n"])
    return out


def open_account_counts_by_unit(unit_ids: list[Any]) -> dict[str, int] | None:
    """`DEF-RAT-8752` (3) — `{unit_id: open accounts on it}` for these units,
    read through customers' OWN published queryset (`account_queryset`, B1).

    The charge-code Plans tab draws an ACCOUNTS column (image 20). A plan is
    assigned to a UNIT; the accounts on those units are customers' rows. An
    account whose status is of the TERMINAL class (closed) is not counted —
    read off the status's class, never its label, as `payments.runbook_reads`
    does. One grouped query for the whole page. `None` when customers publishes
    no such read, so the screen draws *—* rather than a confident 0."""
    from django.db.models import Count

    ids = [str(one) for one in unit_ids if one]
    if not ids:
        return {}
    try:
        account_queryset = import_module("apps.customers.selectors").account_queryset
    except (ImportError, AttributeError):  # pragma: no cover - customers always publishes it
        return None
    rows = (
        account_queryset()
        .filter(unit_id__in=ids)
        .exclude(status__behavior_class="terminal")
        .values("unit_id")
        .annotate(n=Count("id"))
    )
    return {str(row["unit_id"]): int(row["n"]) for row in rows}



# ── audit: one tax's own trail (CR-165-BRC10 round 2 · §9 `GET /taxes/{id}/audit`) ──
def tax_audit_queryset(entity_ids: list[Any]) -> Any:
    """Every `audit_log` row written for these tax rows, newest first.

    ⚠ **NO SECOND READER OF `audit_log`.** The query is
    `apps.audit.selectors.audit_queryset` — the one definition of an audit
    query (its two-year window floor, its tenant scope) — narrowed to
    `entity_type = 'tax'` and to the rows of ONE tax chain. Rows age out on the
    retention schedule (hard rule 4, `OQ-1340`): a short trail is a true answer.
    """
    audit = import_module("apps.audit.selectors")
    ids = [str(one) for one in entity_ids if one]
    return (
        audit.audit_queryset(_tenant_id())
        .filter(entity_type="tax", entity_id__in=ids)
        .order_by("-created_at", "-id")
    )


def audit_actor_payloads(rows: list[Any]) -> list[Any]:
    """The audit module's own actor shape for each row (`_actor_payload`:
    `{id, name}` for a person, `{kind, name, version}` for an automation, null
    for an unnamed system job), batched for the page."""
    audit = import_module("apps.audit.selectors")
    names = audit.actor_names(_tenant_id(), [row.actor_user_id for row in rows])
    return [audit._actor_payload(row, names) for row in rows]


# ── CR-166-BRC10 round 2 · the discounts redesign's cross-module reads ──────
#
# Each READ-ONLY and tenant-filtered. Accounts are read through customers' OWN
# published `account_queryset` (B1) wherever a queryset is enough, which is the
# posture `open_account_counts_by_unit` and `apps.payments.autopay.is_enrolled`
# already take; the customer NAME needs the `customer_accounts` link, which
# customers publishes no read for, so that one goes through `get_model` — the
# disposition `plan_unit_facts` records above, for the same reason.


def tenant_currency() -> str | None:
    """The utility's own currency (`Tenant.currency`, BR-TEN-021 forward-only).

    `CR-166` §9 / PO 2026-10-03: *"Currency - it is default of utility - user
    cannot change it"*. Rating had no read of it (`CR-166` §6 b), so a version
    stored whatever was typed — the walk saved CAD on a USD utility. Read
    through tenancy's own Regional settings, exactly as `customers.seams.
    tenant_currency` does, so the two cannot disagree.
    """
    tenancy_selectors = import_module("apps.tenancy.selectors")
    code = tenancy_selectors.regional_settings().get("currency")
    return str(code).upper() if code else None


def _account_queryset() -> Any:
    return import_module("apps.customers.selectors").account_queryset()


def account_unit_id(account_id: Any) -> Any | None:
    """The unit an account names, or None (a master account names none)."""
    row = _account_queryset().filter(pk=account_id).values("unit_id").first()
    return row["unit_id"] if row else None


def account_deposit_size_class(account_id: Any) -> str | None:
    """🔒 HUMAN-REVIEW-PENDING — the size the clerk PICKED on the Deposit step
    because no meter was fitted (`accounts.deposit_size_class`), or None.
    `DEF-CUS-9521`, PO 2026-10-04 verbatim: *"(c) Let the clerk pick the size
    on the Deposit step."* Read by `selectors.deposit_rule_for` when billing
    asks by account, so the first bill prices the deposit at the size the
    counter took. A recorded meter size still wins over it."""
    row = _account_queryset().filter(pk=account_id).values("deposit_size_class").first()
    size = row["deposit_size_class"] if row else None
    return (str(size).strip() or None) if size else None


def connection_size_for(unit_id: Any, service_code: str) -> str | None:
    """🔒 HUMAN-REVIEW-PENDING — this unit's recorded connection size for one
    service, or None. `OQ-RAT-12786` (CLOSED 2026-10-03, PO verbatim: *"(a)
    Class or size: the deposit table gets a size column, like charge codes
    have."*): a deposit priced by size asks the size of the service its code
    names. Answered by `metering.selectors.connection_size_for` — the SAME
    seam billing's R3 sizes a base from (`billing.gather._connection_size_for`),
    so a deposit and a base can never read two different sizes for one
    connection. `None` is *no size recorded* (or no connection), never a guess.
    """
    if unit_id is None or not service_code:
        return None
    fn = getattr(import_module("apps.metering.selectors"), "connection_size_for", None)
    if fn is None:
        return None
    size = fn(unit_id, service_code)
    return (str(size).strip() or None) if size else None


def account_search_ids(term: str) -> Any:
    """Accounts whose number, holder's name or premises address contains
    `term` — a SUBQUERY of ids (`CR-166` §9 Accounts tab search). The address
    is walked to the premises (hard rule 8); the name through the holder link."""
    from django.db.models import Q

    link = django_apps.get_model("customers", "CustomerAccount")
    holders = link.objects.filter(
        tenant_id=_tenant_id(), customer__display_name__icontains=term
    ).values("account_id")
    # `accounts.premises_id` is a DEFERRED FK (a plain uuid, BR-CUS-1010), so a
    # master account's premises is matched through metering's own table.
    premises = (
        django_apps.get_model("metering", "Premises")
        .objects.filter(tenant_id=_tenant_id(), address_line__icontains=term)
        .values("id")
    )
    return (
        _account_queryset()
        .filter(
            Q(account_no__icontains=term)
            | Q(unit__premises__address_line__icontains=term)
            | Q(premises_id__in=premises)
            | Q(id__in=holders)
        )
        .values("id")
    )


def account_number_subquery(outer: str = "account_id") -> Any:
    """The account number for an outer row's account id — sortable in SQL."""
    from django.db.models import OuterRef, Subquery

    return Subquery(_account_queryset().filter(pk=OuterRef(outer)).values("account_no")[:1])


def discount_account_facts(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`{account_id: {account_number, customer_name, premises_address, unit_id}}`
    for ONE PAGE of the Accounts tab. Two queries, whatever the page size.

    The address is the PREMISES' own (hard rule 8): the unit's premises, or the
    account's own premises for a master account that names no unit."""
    ids = [str(one) for one in account_ids if one]
    if not ids:
        return {}
    rows = (
        _account_queryset()
        .filter(pk__in=ids)
        .values("id", "account_no", "unit_id", "unit__premises__address_line", "premises_id")
    )
    rows = list(rows)
    # A master account names no unit; its premises is a deferred FK (a plain
    # uuid), so its address is read from metering's own table, one query.
    master_premises = {
        str(row["id"]): row["address_line"]
        for row in django_apps.get_model("metering", "Premises")
        .objects.filter(
            tenant_id=_tenant_id(),
            id__in=[r["premises_id"] for r in rows if r["premises_id"] and not r["unit_id"]],
        )
        .values("id", "address_line")
    }
    facts: dict[str, dict[str, Any]] = {
        str(row["id"]): {
            "account_number": row["account_no"],
            "customer_name": None,
            "premises_address": row["unit__premises__address_line"]
            or master_premises.get(str(row["premises_id"])),
            "unit_id": str(row["unit_id"]) if row["unit_id"] else None,
        }
        for row in rows
    }
    link = django_apps.get_model("customers", "CustomerAccount")
    for row in (
        link.objects.filter(tenant_id=_tenant_id(), account_id__in=ids)
        .order_by("account_id", "created_at", "id")
        .values("account_id", "customer__display_name")
    ):
        entry = facts.get(str(row["account_id"]))
        if entry is not None and entry["customer_name"] is None:
            entry["customer_name"] = row["customer__display_name"]
    # `DEF-RAT-9308` — an account with no `customer_accounts` row (every
    # account made before BR-CUS-054, the sample utility's among them) is named
    # by its PRIMARY CONTACT: the customers module's own rule, the one the
    # Accounts list reads, asked once for the unnamed rest of the page.
    unnamed = [key for key, entry in facts.items() if entry["customer_name"] is None]
    if unnamed:
        names = import_module("apps.customers.selectors").primary_contact_names_for(unnamed)
        for key in unnamed:
            facts[key]["customer_name"] = names.get(key)
    return facts


def accounts_meeting(unit_ids_subquery: Any, check_key: str, *, include_pending: bool = False) -> Any:
    """Open accounts on these units meeting ONE system check (ruling 3) — a
    SUBQUERY of ids, never materialised here (NFR-3).

    * `everyone` — every open account on the units;
    * `autopay` — the customer's ELECTION **and not** the cash-only sanction:
      the pair `apps.payments.autopay.is_enrolled` reads (DEF-070), so a
      customer the NSF rule took off autopay does not keep an autopay discount;
    * `paperless` — `accounts.paperless` (BR-CUS-028);
    * `government` — account type `municipal`, or the legacy `government`.

    An account whose status is of the TERMINAL class (closed) never qualifies,
    and a NON-BILLABLE one (pending activation) does not either — read off the
    status's class, never its label (BR-CUS-055).

    `include_pending` (`DEF-RAT-9833`, PO ruling 4 of 2026-10-06) counts a
    NON-BILLABLE account too — only for Autopay/Paperless, where a clerk's add
    or a setting switched On must hold for the next bill even when the move-in
    has not started yet. A closed account never qualifies either way.
    """
    excluded = ("terminal",) if include_pending else ("terminal", "non_billable")
    qs = (
        _account_queryset()
        .filter(unit_id__in=unit_ids_subquery)
        .exclude(status__behavior_class__in=excluded)
    )
    if check_key == "autopay":
        qs = qs.filter(autopay=True, cash_only_no_autopay=False)
    elif check_key == "paperless":
        qs = qs.filter(paperless=True)
    elif check_key == "government":
        qs = qs.filter(account_type__code__in=("municipal", "government"))
    elif check_key != "everyone":
        return qs.none().values("id")
    return qs.values("id")


def account_ids_on_units(unit_ids_subquery: Any) -> Any:
    """Every account (any status) naming one of these units — a SUBQUERY of
    ids. Used to end the enrolments of a discount taken off a plan: an
    enrolment is ended whatever the account's status, because the plan no
    longer carries the discount for anybody on it."""
    return _account_queryset().filter(unit_id__in=unit_ids_subquery).values("id")


def account_numbers(account_ids: list[Any]) -> dict[str, str]:
    """`{account_id: account number}` — the NAMES an audit row shows."""
    ids = [str(one) for one in account_ids if one]
    if not ids:
        return {}
    return {
        str(row["id"]): row["account_no"]
        for row in _account_queryset().filter(pk__in=ids).values("id", "account_no")
    }


def discount_audit_queryset(entity_filter: Any) -> Any:
    """Every `audit_log` row matching `entity_filter` (a `Q` over `entity_type`
    / `entity_id`), newest first — the audit module's ONE query, narrowed
    (`tax_audit_queryset`'s shape). Rows age out on retention (hard rule 4)."""
    audit = import_module("apps.audit.selectors")
    return audit.audit_queryset(_tenant_id()).filter(entity_filter).order_by("-created_at", "-id")


def rating_audit_queryset(entity_filter: Any) -> Any:
    """`DEF-RAT-10032` — the audit rows Plans & Rates > History lists beside
    `rate_change_log` (taxes and discounts), and the partner rows it pairs a new
    version with. The audit module's ONE query, narrowed — unordered, because
    History orders the UNION it joins (`selectors.history_list_queryset`)."""
    audit = import_module("apps.audit.selectors")
    return audit.audit_queryset(_tenant_id()).filter(entity_filter)



# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-002@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
# generated: 2026-08-09 by story-coder v1 (W1 rating feature lane — services/selectors/API); AMENDED 2026-08-11 by story-coder (plan-assignment backdating lane — `last_issued_bill_for_unit`, the read the PO's option-B ruling needs) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `ledger_account_is_live` — the ownership+liveness read behind a tenant's tax→account mapping)
# checklist: A✔ B✔ C✔ D=deferred(no-endpoint-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ pytest tests/test_us_rat_*: 85 passed / 14 skipped (11 isolation halves → G5, 3 owned elsewhere — each with a stated reason)✔ · full suite -m 'not golden and not isolation': 564 passed / 0 failed / 9 skipped✔ (365 baseline + the concurrent metering/assets lanes + this one; two transient cross-lane failures seen mid-run in tests/test_us_aud_001_store.py were the assets lane's shared-fixture ordering and cleared on their side — never reachable from test_us_rat_*, which sorts after test_us_aud_*) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: tenancy Service/TenantService read via django_apps.get_model (no owning-module selector exposes the catalog id or the r6.4 UoM-gate columns) — Eng disposition, docstring · [2026-08-15 seams lane, DEF-079] the two CHARGE/PLAN billing seams NO LONGER RETURN 0 WHEN UNWIRED and their 'unwired == no references BY CONSTRUCTION' note is DELETED as false — billing has published `plan_invoice_count` and `charge_line_count` since 2026-08-12, and while the old fallback stood a rate plan that HAD been billed was permanently deletable. Both now answer None for 'billing could not answer' and both delete guards FAIL CLOSED on it, naming which half was unanswerable in the refusal · `last_issued_bill_for_unit` is WIRED (2026-08-11: billing has an `invoices` table) and deliberately returns {"wired", "bill"} instead of a bare row, because None alone cannot tell "never billed" from "the read does not exist"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
