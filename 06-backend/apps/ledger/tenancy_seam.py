# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-02 (chart of accounts & GL mapping — the ledger derives its
#           service roll-up from attributes it does not own)
#           Screens: S56 · S8 (Settings → Services, where a tenant keeps the
#           row this module only READS)
#           NOTE: no US-ID is cited here ON PURPOSE — G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs", and this file ships
#           one cross-module read, not a story. Same precedent as
#           apps/billing/tenancy_seam.py and apps/billing/rating_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-BIL-010 (service → revenue GL, with an OPTIONAL usage/base
#           split) · CLAUDE.md rule 1 (tenant scoping — inherited from
#           tenancy's own read, never re-implemented here)
# Tests:    06-backend/tests/test_us_led_005_gl_designations.py
# Impacts:  apps/ledger/selectors.py (its `revenue_account_*_for_service`
#           reads sit on top of this)
# ───────────────────────────────────────────────────────
"""ledger → tenancy SEAM: a utility service's GL attributes.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this seam is how the ledger learns which
revenue bucket a service's money lands in, so a wrong answer here is a
misposting. AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

B1/BR-TEN-013: the ledger never touches tenancy's ORM. `tenant_services` is a
tenancy table (S8 Services card) and stays one — this module resolves tenancy's
published read AT CALL TIME, the same idiom `apps/billing/tenancy_seam.py` uses
for the holiday calendar, so no import binds the ledger to tenancy's internals.

WHY THE LEDGER NEEDS A TENANCY READ AT ALL — it is worth stating, because the
PO ruling that created this seam could be misread as putting everything in one
module. The PO closed OQ-106 with *"using attributes on accounts and Utility
services - we can derive how it sum up at Ledger."* Two attribute homes, one
derivation: the ledger owns `ledger_accounts.designation`, the tenant's utility
service owns `revenue_account` / `base_revenue_account`, and the ROLL-UP —
"which account does this service's revenue land in" — is derived by the ledger
from both. Ownership of the map is the ledger's; ownership of the TABLE a
service's attribute sits on is tenancy's, because `tenant_services` was
tenancy's before any of this and a service's GL account is an attribute of the
service exactly as `primary_uom` is.

WHY IT REFUSES INSTEAD OF ANSWERING `None` when tenancy has published no read:
"this service has no revenue account configured" and "the ledger cannot see
tenancy" are different facts with the same shape, and conflating them turns a
wiring failure into a silently unmapped bill line. A bill line's
`gl_account_id` freezes at issue and can never be repaired, so the unsafe
answer must be the one nobody can get by accident (hard-won law 3). A service
that genuinely has no account configured comes back from a WIRED seam as
`{"revenue_account_id": None, ...}` and means it.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

#: The tenancy reads this seam depends on:
#:   * `service_gl_attributes(service_code)` — the S8 row's GL half for the
#:     CURRENT tenant (or None when the tenant has not enabled the service).
#:   * `enabled_service_codes()` — WHICH services this tenant sells, which
#:     since the PO's OQ-115 ruling (2026-08-11) decides which per-service
#:     revenue accounts the chart seed creates at all.
#: Named once so the contract is greppable from BOTH sides.
SERVICE_ATTRIBUTES_MODULE = "tenancy"
SERVICE_ATTRIBUTES_ATTRIBUTE = "service_gl_attributes"
ENABLED_SERVICES_ATTRIBUTE = "enabled_service_codes"
#: CR-060 C10 / T11 — the WRITE half of the mapping, published by tenancy on
#: its SERVICES module rather than its selectors, because a write is a
#: service-layer act (B8/LAW 0) and resolving it from `selectors` would put
#: a writer where every other name here is a read.
SERVICE_GL_WRITE_MODULE = "services"
SERVICE_GL_WRITE_ATTRIBUTE = "set_service_gl_accounts"


class LedgerSeamNotWired(RuntimeError):
    """Tenancy has not published the read the ledger's roll-up is derived from.

    Loud on purpose — see the module docstring. Never caught here and turned
    into an empty answer.
    """


def _resolve(attribute: str) -> Any:
    try:
        selectors = import_module(f"apps.{SERVICE_ATTRIBUTES_MODULE}.selectors")
    except ImportError:
        return None
    fn = getattr(selectors, attribute, None)
    return fn if callable(fn) else None


def _require(attribute: str, consequence: str) -> Any:
    fn = _resolve(attribute)
    if fn is None:
        raise LedgerSeamNotWired(
            f"apps.{SERVICE_ATTRIBUTES_MODULE}.selectors.{attribute} is not published, so "
            f"{consequence} The ledger derives its service roll-up from attributes tenancy owns "
            "(PO ruling 2026-08-11, OQ-106 closed); nothing is guessed and no line is stamped."
        )
    return fn


def _resolve_writer(attribute: str) -> Any:
    """The same call-time resolution as `_resolve`, against tenancy's SERVICES.

    Written as its own function rather than a parameter on `_resolve` so that a
    reader of this file can see at a glance that exactly ONE name here is a
    writer, and which one.
    """
    try:
        services = import_module(f"apps.{SERVICE_ATTRIBUTES_MODULE}.{SERVICE_GL_WRITE_MODULE}")
    except ImportError:
        return None
    fn = getattr(services, attribute, None)
    return fn if callable(fn) else None


def set_service_gl_accounts(actor: Any, service_code: str, changes: dict[str, Any]) -> Any:
    """**ASK TENANCY TO WRITE ITS OWN HALF OF THE MAP — `CR-060` C10 / T11.**

    C10 in terms: *"An orchestrating service in the tenancy module that the
    mapping screen calls — one screen, one save, several owners underneath —
    NOT a cross-module write."* This is the seam that makes the second half of
    that sentence true. `tenant_services.revenue_account_id` is a TENANCY
    column; the ledger asks for it to change and never reaches the ORM itself,
    exactly as `service_gl_attributes` above asks to READ it (B1 / BR-TEN-013).

    ⚠ **IT RUNS INSIDE THE CALLER'S TRANSACTION AND OPENS NONE OF ITS OWN.**
    The orchestrating save is all-or-nothing (C10's own proof: *"a partial
    failure writes NOTHING"*), so this must be able to take the whole save down
    with it. A `transaction.atomic()` anywhere on this path would be a SAVEPOINT
    that survives the outer rollback for the half it wraps.

    ⚠ **IT REFUSES RATHER THAN ANSWERING WHEN TENANCY PUBLISHES NO WRITER**, for
    the reason this module's docstring already gives about reads: an unwired
    seam and "nothing to change" have the same shape, and a mapping save that
    silently wrote half the map would leave a tenant looking at a screen that
    says it saved.
    """
    fn = _resolve_writer(SERVICE_GL_WRITE_ATTRIBUTE)
    if fn is None:
        raise LedgerSeamNotWired(
            f"apps.{SERVICE_ATTRIBUTES_MODULE}.{SERVICE_GL_WRITE_MODULE}."
            f"{SERVICE_GL_WRITE_ATTRIBUTE} is not published, so a service's revenue account "
            "cannot be changed from the one mapping screen (CR-060 C10). The ledger does not "
            "write `tenant_services` and will not start; nothing is saved."
        )
    return fn(actor, service_code, changes)


def service_gl_attributes(service_code: str) -> dict[str, str | None] | None:
    """`{"revenue_account_id", "base_revenue_account_id"}` for a service.

    `None` means the tenant has no `tenant_services` row for that code — the
    service is not enabled here, which is a different answer from "enabled with
    nothing mapped" and is kept different on purpose.
    """
    fn = _require(
        SERVICE_ATTRIBUTES_ATTRIBUTE,
        "no service can resolve its revenue account (BR-BIL-010).",
    )
    return fn(service_code)


def enabled_service_codes() -> tuple[str, ...]:
    """The services this tenant actually sells, in the catalog's own order.

    The PO's OQ-115 ruling — *"every Utility may not have all the services"* —
    made this the input to the chart seed: a tenant is seeded the revenue
    accounts of the services it sells and no others. So this seam is not a
    convenience read; the wrong answer here seeds the wrong chart.

    It REFUSES rather than answering `()` when tenancy publishes nothing, for
    the reason the module docstring gives: "this tenant sells nothing" and "the
    ledger cannot see tenancy" have the same shape, and an empty tuple would
    quietly seed a chart with no revenue accounts in it at all.
    """
    fn = _require(
        ENABLED_SERVICES_ATTRIBUTE,
        "the chart seed cannot tell which services this tenant sells, and would seed a chart "
        "with no revenue account in it (PO ruling 2026-08-11, OQ-115).",
    )
    return tuple(fn())


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C2 / task T7 — the two reads the unbilled-revenue accrual needs
# ═══════════════════════════════════════════════════════════════════════════
#: `{code: id}` for the platform catalog, published by tenancy FOR BILLING and
#: read here for the same reason billing reads it: BR-LED-001's service
#: dimension is a `services` FK, the ledger holds the CODE, and B1 forbids
#: reaching into tenancy's ORM for the translation.
SERVICE_IDS_ATTRIBUTE = "service_ids_by_code"

#: CLAUDE.md rule 2's `CHAR(3)` half. `posting.PostingRequest.currency` has no
#: default on purpose — *"a defaulted currency is how a CAD tenant's books
#: quietly become USD"* — so the accrual reads the tenant's declared code the
#: same way `apps/ledger/finance_api._tenant_currency` and `apps/ledger/api`
#: already do, through tenancy's own published `regional_settings()`.
REGIONAL_SETTINGS_ATTRIBUTE = "regional_settings"


def service_id_for_code(service_code: str) -> str | None:
    """The catalog id behind a service code, or None when the catalog has none.

    `None` is honest and is NOT an error: a line whose service cannot be named
    is posted WITHOUT the dimension rather than not posted at all, because
    BR-LED-001 requires the five optional dimensions *where they apply* and the
    money is real either way. The caller reports the absence; it never invents
    an id.
    """
    fn = _resolve(SERVICE_IDS_ATTRIBUTE)
    if fn is None:  # pragma: no cover — tenancy publishes it for billing
        return None
    return (fn() or {}).get(service_code)


#: The rule page `apps/ledger/allowance.py` reads its policy off. Named here,
#: beside the read, so a slug typo is one edit away from the call that uses it.
FINANCE_CONTROLS_SLUG = "finance-controls"

#: Tenancy's published read for one rule page. The SAME name
#: `apps/payments/settings_seam.py` resolves, deliberately: two modules reading
#: one page through two different callables is how they come to disagree about
#: what a tenant set.
SETTINGS_FAMILY_ATTRIBUTE = "settings_family"


def settings_family(slug: str) -> dict[str, Any]:
    """One rule page's current parameter set for THIS tenant.

    **`CR-060` T15.** The allowance for doubtful accounts is a POLICY a utility
    switches on and four rates only that utility can set, so the ledger has to
    be able to read the S71 Finance-controls page.

    Tenant scoping is not added here and cannot be lost here: the values come
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE
    (hard rule 1). This module issues no query and imports no tenancy module —
    the callable is resolved by NAME (BR-TEN-013).

    ⚠ **AN UNREACHABLE SETTING IS NOT A SETTING, AND THIS REFUSES RATHER THAN
    DEFAULTING.** `apps/payments/settings_seam.finance_controls` says the same
    thing in its own words about a bank-match tolerance, and the stake here is
    higher: a policy read as OFF because tenancy was unreachable would post a
    write-off to `6900` for a utility that books an allowance, and hard rule 4
    leaves no path to move that entry afterwards.
    """
    fn = _require(
        SETTINGS_FAMILY_ATTRIBUTE,
        f"the {slug} page cannot be read. An unreachable setting is not a setting: reading a "
        "policy as OFF because tenancy could not be asked would post money to an account "
        "nobody chose, and no UPDATE reaches a posted journal entry (CLAUDE.md hard rule 4).",
    )
    return dict(fn(slug))


# ── `CR-142-BRC07` `P6.11` wave 3 · THE FISCAL CALENDAR R43 IS A ROW OF ──────
#
#: Tenancy's computed current-period card (`BR-TEN-022`). It is COMPUTED from
#: the fiscal-year fields and never stored, and it returns **None** for a tenant
#: that has not set a fiscal year start — a real state, which R43 reports as a
#: named absence rather than as twelve calendar months it invented.
CURRENT_PERIOD_ATTRIBUTE = "current_period"

#: `BR-REP-034`'s typed per-tenant monthly target. **DARK** — `apps/reports/
#: dashboard_seams.monthly_revenue_target` records the same contract and the
#: same four questions the PO's signature does not cover. Every tenant that
#: exists today is in the untyped state, so R43's TARGET column and its
#: REVENUE VS TARGET tile degrade to the figure alone, which is the ruling
#: rather than a stub.
REVENUE_TARGET_ATTRIBUTE = "monthly_revenue_target"

#: `BR-REP-022` — the DSO target lives on the S71 Finance-controls rule page and
#: seeds at **15 days**.
FINANCE_CONTROLS_FAMILY = "finance-controls"
DSO_TARGET_PARAM = "dso_target_days"


def current_period(reference_date: Any = None) -> dict[str, Any] | None:
    """The fiscal period containing `reference_date`, or None.

    ⚠ **`reference_date` IS AN ARGUMENT AND NEVER A CLOCK HERE** (`BR-TEN-043`).
    R43 walks BACKWARDS through twelve of these by asking for the day before
    each period's start, so passing nothing would make every step ask about
    today and the report would be twelve copies of one period.

    `None` means this tenant has set no fiscal year start. That is a real state
    and it is published as an absence, never as twelve calendar months: a trend
    pack keyed on a calendar the utility does not keep its books by would be a
    confident wrong answer, which `BR-REP-024` exists to prevent.
    """
    fn = _resolve(CURRENT_PERIOD_ATTRIBUTE)
    if fn is None:  # pragma: no cover — tenancy publishes it
        return None
    return fn(reference_date=reference_date)


#: The TENANT's own today (`BR-TEN-043`). Read at the boundary and only when
#: the caller supplied no date — never inside an arithmetic path, and never
#: this process's clock.
TENANT_TODAY_ATTRIBUTE = "tenant_today"


def tenant_today() -> Any | None:
    """This tenant's today, in its own zone, or None when tenancy is unreachable.

    ⚠ **THE BOUNDARY, AND ONLY THE BOUNDARY** (`BR-TEN-043`). A report reads it
    ONCE, when its caller named no date, and passes the answer down; anything
    below takes the date as an argument. `G6` greps for a clock in a money path
    and this is the one place a report may have one.
    """
    fn = _resolve(TENANT_TODAY_ATTRIBUTE)
    return fn() if fn is not None else None


def monthly_revenue_target() -> Any | None:
    """`BR-REP-034`'s typed target, or None. **DARK on every tenant today.**

    The PO ruled option B on 2026-08-18 and ruled the untyped fallback in the
    same breath — *"With no target typed, the tile degrades to … the figure
    alone, no sub-line"*. That is not a stub: it is the state this deployment is
    in and the state R43's TARGET column is proved in FIRST.
    """
    fn = _resolve(REVENUE_TARGET_ATTRIBUTE)
    return fn() if fn is not None else None


def dso_target_days() -> int | None:
    """`BR-REP-022`'s tenant setting — default **15** — or None if unreadable.

    Unlike `settings_family` above this does NOT raise when tenancy cannot be
    asked, and the difference is the stake: that read decides where money is
    posted, and hard rule 4 leaves no path to move a posted entry afterwards.
    This one decides whether a TILE prints *target 15* under a number. An
    absent target is a missing sub-line; an absent allowance policy is a
    misposted write-off.
    """
    fn = _resolve(SETTINGS_FAMILY_ATTRIBUTE)
    if fn is None:  # pragma: no cover — tenancy publishes it
        return None
    value = dict(fn(FINANCE_CONTROLS_FAMILY) or {}).get(DSO_TARGET_PARAM)
    return None if value is None else int(value)


def tenant_currency() -> str | None:
    """This tenant's declared `CHAR(3)`, or None when nothing is declared."""
    fn = _resolve(REGIONAL_SETTINGS_ATTRIBUTE)
    if fn is None:  # pragma: no cover — tenancy publishes it
        return None
    return (fn() or {}).get("currency")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (co-sources: 12-governance/02-decision-log.md 2026-08-11 "OQ-106 IS CLOSED" — the two attribute homes and the derived roll-up — and "STORM WATER AND THERMAL HEAT GET REVENUE ACCOUNTS" (OQ-115) — which services a tenant sells)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane: enabled_service_codes, the read that decides which revenue accounts the seed creates)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see 06-backend/tests/test_us_led_005_gl_designations.py
# exceptions: this seam READS ONLY — the write path for these attributes is
#         tenancy's own `update_tenant_service` (which since the PO's OQ-115
#         ruling of 2026-08-11 lets a tenant re-point a service at an account of
#         their own) and the provisioning seed, because a cross-module write is
#         forbidden (B1) and the GL mapping SCREEN the PO placed *"in settings"*
#         is a frontend story in another lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
