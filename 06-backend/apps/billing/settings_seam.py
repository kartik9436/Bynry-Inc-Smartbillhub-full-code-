# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-03 (bill types — three of them are bounded by a tenant
#           setting, and none of the three may carry its own copy of one)
#           Screens: S71 (Settings → Finance controls, where a tenant KEEPS
#           these values; this module only reads them)
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's test cases";
#           this file ships one cross-module read, not a story. Same precedent
#           as apps/billing/tenancy_seam.py and apps/billing/late_fee.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-BIL-018 (back-bill window capped by tenant setting, default 12
#           months; theft cases EXEMPT — OQ-071 CLOSED) · BR-BIL-013
#           (small-balance write-off threshold, default $5, tenant-config
#           0–50, both directions — OQ-070 CLOSED) · BR-BIL-014 (the approval
#           gate; v1 = ALL need System Admin approval — OQ-072 CLOSED) ·
#           CLAUDE.md rule 2 (money is Decimal, never float)
# Tests:    06-backend/tests/test_us_bil_013_backbill.py ·
#           06-backend/tests/test_us_bil_011_final_bill.py
# Impacts:  apps/billing/backbill.py (the cap + the theft exemption) ·
#           apps/billing/final_bill.py (the write-off threshold)
# ───────────────────────────────────────────────────────
"""billing → tenancy SEAM: the S71 Finance-controls values, correctly typed.

Serves US-BIL-011 and US-BIL-013 without shipping either.

WHY IT EXISTS AT ALL, given `settings_family("finance-controls")` is one call
away. Two reasons, and the second is the one that would cost money:

  * **TYPE.** The settings document stores decimals as STRINGS (tenancy's own
    contract: "flat document, decimals as strings"), so `write_off_threshold`
    arrives as `"5"`. Comparing a `Decimal` remainder against `"5"` raises in
    Python 3 — but `abs(remainder) <= "5"` is not the only way a caller reaches
    for it, and `float("5")` is a hard-rule-2 violation the moment someone
    "fixes" the TypeError. One conversion, in one place, to `Decimal`.
  * **NO SECOND COPY OF A DEFAULT.** The ratified defaults (12 months, $5,
    "all") live in `apps.tenancy.settings_families` as seeded `Param` rows and
    are what `settings_family` merges in when a tenant has stored nothing. A
    caller that wrote `settings.get("back_bill_cap_months", 12)` would create a
    SECOND default, and the day finance moved the ratified one the two would
    disagree silently — the tenant's screen saying 18 while the guard enforced
    12. So every read below refuses on a missing key rather than defaulting.
    Hard-won law 1: a constant repeated is a guarantee nobody is keeping.

REFUSES rather than falling back, in both directions (hard-won law 3 — the
unsafe option must be the one you type):

  * tenancy publishes no `settings_family` → `BillingConfigError`. An
    unreachable cap is not a 12-month cap; back-billing 30 months of history to
    a customer because a seam was absent is precisely the consumer-protection
    failure BR-BIL-018 exists to prevent.
  * the family answers without the key → `BillingConfigError` naming the key.

NOTHING HERE DECIDES ANYTHING. It reads four values and types them. Whether
the cap applies (theft), how a span is measured in months, and which settlement
path a remainder takes are their own modules' business, stated where the rules
are cited.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from importlib import import_module
from typing import Any

from apps.billing.exceptions import BillingConfigError

#: The tenancy read this seam depends on, named once so the contract is
#: greppable from both sides of the boundary (the tenancy_seam.py precedent).
SETTINGS_READ_MODULE = "tenancy"
SETTINGS_READ_ATTRIBUTE = "settings_family"
#: The S71 rule page these four values live on (`settings_families.FAMILIES`).
FINANCE_CONTROLS = "finance-controls"
#: The S66 rule page the bill run's standing answers live on (BR-BIL-1040,
#: `DEF-BIL-5255`) — the value screen 16's DEFAULTS group opens each control on.
BILLING_DEFAULTS = "billing-defaults"
#: The S69 rule page BR-BIL-017's budget parameters live on — eligibility
#: months, level rounding, re-level drift % and cadence, settle-up month and
#: the ±30% override bound. Read by `apps/billing/budget_service.py`.
BUDGET_BILLING = "budget-billing"

KEY_BACK_BILL_CAP_MONTHS = "back_bill_cap_months"
KEY_BACK_BILL_THEFT_EXEMPT = "back_bill_theft_exempt"
KEY_WRITE_OFF_THRESHOLD = "write_off_threshold_amount"
KEY_CORRECTION_APPROVAL_MODE = "correction_approval_mode"
#: BR-BIL-1040 — the three S66 parameters screen 16's DEFAULTS group opens on,
#: keyed by the CASE KIND they answer (`decisions.CHOICES_BY_CASE`'s own words).
#: The mapping lives here rather than in `runs.py` so the run-creation path
#: never spells a settings key, which is the same reason `_value` refuses on a
#: missing key instead of defaulting.
RUN_CASE_DEFAULT_KEYS: dict[str, str] = {
    "missing_read": "run_default_missing_read",
    "high_usage": "run_default_high_usage",
    "days_threshold": "run_default_days_threshold",
}


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr-at-call-time, the same idiom `apps/billing/gather.py` and
    `apps/billing/tenancy_seam.py` use — no import binds billing to tenancy's
    internals, and the day a lane lands its function every seam call starts
    using it with no re-wiring step (hard-won law 2).
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def finance_controls() -> dict[str, Any]:
    """The S71 page's current parameter set for THIS tenant, as tenancy stores it.

    Tenant scoping is not added here and cannot be lost here: the values come
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE
    (CLAUDE.md hard rule 1). This module issues no query of its own.
    """
    read = _resolve(SETTINGS_READ_MODULE, SETTINGS_READ_ATTRIBUTE)
    if read is None:
        raise BillingConfigError(
            f"apps.{SETTINGS_READ_MODULE}.selectors.{SETTINGS_READ_ATTRIBUTE} is not "
            "published, so the tenant's finance controls cannot be read. This does NOT "
            "fall back to the seeded defaults: an unreachable back-bill cap is not a "
            "12-month cap (BR-BIL-018), and an unreachable write-off threshold is not "
            "$5 (BR-BIL-013). Both would let a bill through that the tenant's own "
            "settings forbid."
        )
    return dict(read(FINANCE_CONTROLS))


def budget_billing() -> dict[str, Any]:
    """The S69 page's budget parameters for THIS tenant (BR-BIL-017/021).

    Same posture as `finance_controls` and for the same reason: it REFUSES
    rather than falling back to the seeded defaults. An unreachable
    `eligibility_months` is not twelve and an unreachable `override_bound_pct`
    is not thirty — either substitution would enrol an account, or move what it
    pays every month, against settings nobody could read.

    Tenant scoping is tenancy's own read's (RLS FORCE, CLAUDE.md rule 1); this
    module issues no query.
    """
    read = _resolve(SETTINGS_READ_MODULE, SETTINGS_READ_ATTRIBUTE)
    if read is None:
        raise BillingConfigError(
            f"apps.{SETTINGS_READ_MODULE}.selectors.{SETTINGS_READ_ATTRIBUTE} is not "
            "published, so the tenant's budget-billing parameters cannot be read. "
            "Budget billing decides what a customer pays every month for a year "
            "(BR-BIL-017); it is refused rather than run on assumed settings."
        )
    return dict(read(BUDGET_BILLING))


def billing_defaults() -> dict[str, Any]:
    """The S66 page's parameters for THIS tenant (BR-BIL-1040 among them).

    Same posture as `finance_controls` and `budget_billing`, and for the same
    reason: it REFUSES rather than falling back. A run whose defaults could not
    be read is not a run with no defaults — it would silently bill the accounts
    a clerk asked to hold.
    """
    read = _resolve(SETTINGS_READ_MODULE, SETTINGS_READ_ATTRIBUTE)
    if read is None:
        raise BillingConfigError(
            f"apps.{SETTINGS_READ_MODULE}.selectors.{SETTINGS_READ_ATTRIBUTE} is not "
            "published, so the tenant's billing defaults cannot be read. The bill run's "
            "standing answers (BR-BIL-1040) decide whether an account with no reading is "
            "estimated or held, so the run is refused rather than created against "
            "defaults nobody could read."
        )
    return dict(read(BILLING_DEFAULTS))


def run_case_defaults() -> dict[str, str]:
    """BR-BIL-1040 — what screen 16's three DEFAULTS controls OPEN on.

    `{case_kind: choice}`, for exactly the three cases the drawing draws. The
    values are the tenant's, merged by tenancy's own read with the ratified
    seeded defaults; **nothing here supplies a fallback**, for the reason
    `_value` gives below — a default substituted in billing would be a second
    copy of a figure the tenant's own Settings screen shows, free to drift.

    ⚠ It answers what the CONTROL opens on, never what a RUN did.
    `bill_runs.case_defaults` is the run's own record and is written once, at
    creation: a tenant who edits this page tomorrow must not change what a run
    already in flight decided (the hazard BR-BIL-026 freezes a template
    against).
    """
    values = billing_defaults()
    resolved: dict[str, str] = {}
    for case_kind, key in RUN_CASE_DEFAULT_KEYS.items():
        if key not in values:
            raise BillingConfigError(
                f"the tenant's billing-defaults settings carry no {key!r}. The ratified "
                "default lives in apps.tenancy.settings_families as a seeded Param and "
                "is merged in by tenancy's own read — a default substituted HERE would "
                "be a second copy of it, free to drift from the one the tenant's screen "
                "shows (BR-BIL-1040)."
            )
        resolved[case_kind] = str(values[key])
    return resolved


def _value(key: str) -> Any:
    values = finance_controls()
    if key not in values:
        raise BillingConfigError(
            f"the tenant's finance-controls settings carry no {key!r}. The ratified "
            "default lives in apps.tenancy.settings_families as a seeded Param and is "
            "merged in by tenancy's own read — a default substituted HERE would be a "
            "second copy of a finance-signed figure, free to drift from the one the "
            "tenant's screen shows."
        )
    return values[key]


def back_bill_cap_months() -> int:
    """BR-BIL-018's window cap, in months. Seeded default 12 (OQ-071 CLOSED)."""
    raw = _value(KEY_BACK_BILL_CAP_MONTHS)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise BillingConfigError(
            f"the tenant's {KEY_BACK_BILL_CAP_MONTHS} is {raw!r}, which is not a whole "
            "number of months. The back-bill window is refused rather than measured "
            "against a value nobody can read (BR-BIL-018)."
        ) from exc


def back_bill_theft_exempt() -> bool:
    """BR-BIL-018 / OQ-071: are theft cases exempt from the window cap?

    A tenant setting and not a constant, even though the ruling's answer is
    "yes": the closure made it configurable and a hardcoded `True` here would
    silently ignore a tenant that turned it off.
    """
    return bool(_value(KEY_BACK_BILL_THEFT_EXEMPT))


def write_off_threshold() -> Decimal:
    """BR-BIL-013's small-balance threshold as a `Decimal` (rule 2), never float.

    Stored as a string by tenancy (decimals-as-strings). $5 seeded default,
    tenant-config 0–50, and it applies in BOTH directions — a $3.20 credit and
    a $3.20 debit both write off (US-BIL-011 TC-5).
    """
    raw = _value(KEY_WRITE_OFF_THRESHOLD)
    try:
        return raw if isinstance(raw, Decimal) else Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BillingConfigError(
            f"the tenant's {KEY_WRITE_OFF_THRESHOLD} is {raw!r}, which is not a money "
            "amount. A settlement is refused rather than compared against a threshold "
            "that cannot be read (BR-BIL-013)."
        ) from exc


def correction_approval_mode() -> str:
    """BR-BIL-014 / OQ-072: v1 is `"all"` — every correction needs Admin approval.

    Read (rather than assumed) because BR-BIL-018 shares this gate: a back-bill
    and a penalty bill are approval-gated by the SAME rule the corrections
    workflow uses, and the mode is where a v2 threshold would land.
    """
    return str(_value(KEY_CORRECTION_APPROVAL_MODE))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-013@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane — US-BIL-011..014)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a cross-module read) E=deferred(no-frontend-half; the S71 card that WRITES these values is tenancy's and already ships) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_013_backbill.py · tests/test_us_bil_011_final_bill.py
# exceptions: (1) NO local defaults, deliberately — a missing key REFUSES. The
#         ratified 12 / $5 / "all" live once, in apps.tenancy.settings_families,
#         and are merged in by tenancy's own read. A `.get(key, 12)` here would
#         be a second copy of a finance-signed figure.
#         (2) `write_off_threshold` returns Decimal because tenancy stores
#         decimals as STRINGS; the conversion exists here so no caller reaches
#         for `float()` when a comparison raises (hard rule 2, and G6 greps for
#         it).
#         (3a) AMENDED 2026-08-11 (budget-billing lane): `budget_billing()`
#         serves the S69 family the same way — read, never defaulted. Its keys
#         include `drop_off_missed_payments`, which NOTHING reads any more: the
#         PO's ruling of 2026-08-11 ("nodrop we chase for payments until write
#         off") SUPERSEDES BR-BIL-017's drop-off. Dead configuration, REPORTED
#         as DEF-063 rather than removed from tenancy's lane.
#         (3) This module reads FOUR values and decides nothing. Whether the cap
#         applies to a theft case, how a window's months are counted and which
#         settlement path a remainder takes belong to the modules that cite
#         those rules.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
