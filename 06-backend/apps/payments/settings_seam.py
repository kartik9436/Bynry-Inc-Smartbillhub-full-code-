# ── Trace ──────────────────────────────────────────────
# Epics:    EP-PAY-06 (bank reconciliation — the auto-match tolerance is a
#           FINANCE SETTING and this module is the only place it is read) ·
#           EP-PAY-04 (the collection ladder — its intervals, its BALANCE
#           FLOOR and its partial-payment pause percentage are all tenant
#           settings, PO 2026-08-12)
#           Screens: S71 (Settings → Finance controls, where a tenant KEEPS the
#           value; this module only reads it) · S38 · S70 (Settings →
#           Collections & notices, where the ladder values live)
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's test cases";
#           this file ships one cross-module read, not a story. Same precedent
#           as apps/billing/settings_seam.py and apps/billing/tenancy_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-PAY-019 (auto-match on amount + date ±3 days — "the tolerance is
#           a finance setting", r12 #10) · BR-MET-020's config-over-constant
#           principle (a seeded default lives in the DATABASE, never in Python)
# Tests:    06-backend/tests/test_us_pay_020_023_bank_rec.py ·
#           06-backend/tests/test_us_pay_014_ladder.py
# Impacts:  apps/payments/reconciliation.auto_match (its only caller) ·
#           apps/tenancy/settings_families.FINANCE_CONTROLS (where the ratified
#           default 3 lives, as a seeded Param)
# ───────────────────────────────────────────────────────
"""payments → tenancy SEAM: the bank-match date tolerance, correctly typed.

One value, read in one place. `bank_match_date_tolerance_days` is BR-PAY-019's
*"date ±3 days (finance setting)"*, and it already exists as a seeded `Param` on
the S71 Finance-controls page (`apps.tenancy.settings_families`, default **3**).

WHY A SEAM AT ALL, given `settings_family("finance-controls")` is one call away —
the same two reasons `apps/billing/settings_seam.py` gives, and the second is the
one that would silently change a reconciliation:

  * **TYPE.** The settings document is stored as JSON; an integer that arrives as
    a string breaks a `timedelta` comparison at the moment a clerk is looking at
    a statement. One conversion, in one place.
  * **NO SECOND COPY OF A DEFAULT.** A caller writing
    `values.get("bank_match_date_tolerance_days", 3)` would create a SECOND
    default, and the day finance moved the ratified one the two would disagree
    silently — the tenant's screen saying ±1 while the matcher used ±3, matching
    deposits the tenant's own policy says are not the same day's money. So a
    missing key REFUSES.

REFUSES rather than falling back, in both directions (hard-won law 3): tenancy
publishing no `settings_family` is not "±3 days", and an unreadable value is not
"±3 days" either. A matcher that runs on an invented tolerance ties batches to
bank lines a tenant never authorised, and every one of those ties ends in a
LOCKED reconciled batch.

NOTHING HERE DECIDES ANYTHING. It reads one value and types it; whether two dates
are within it is `reconciliation.py`'s business, where BR-PAY-019 is cited.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from zoneinfo import ZoneInfo

from apps.payments.exceptions import PaymentRuleError

#: The tenancy read this seam depends on, named once so the contract is
#: greppable from both sides of the boundary (the `billing/settings_seam.py`
#: precedent, which names the same two strings).
SETTINGS_READ_MODULE = "tenancy"
SETTINGS_READ_ATTRIBUTE = "settings_family"
#: The S71 rule page the value lives on (`settings_families.FAMILIES`).
FINANCE_CONTROLS = "finance-controls"

KEY_MATCH_TOLERANCE_DAYS = "bank_match_date_tolerance_days"
#: CR-008 #7 (PO 2026-08-17, *"Okay. We can take it as threshold from user"*).
#: The AMOUNT half of BR-PAY-019's auto-match, seeded **0** — which is exactly
#: the penny-exact `==` this module has always used.
KEY_MATCH_TOLERANCE_AMOUNT = "bank_match_amount_tolerance"
#: CR-008 ruling 2 (2026-08-17). The MANUAL write-off approval threshold,
#: seeded **0.00** = every write-off needs an approver, which is what
#: `apps/payments/writeoffs.py` did before this key existed. NOT
#: `write_off_threshold_amount`, which is BR-BIL-013's automatic small-balance
#: clear-out at a final bill — see the Param comments in settings_families.py.
KEY_WRITE_OFF_APPROVAL_THRESHOLD = "write_off_approval_threshold_amount"
#: CR-059 CS-35 (2026-09-02). A manual CREDIT or ADJUSTMENT recorded on an
#: account above this amount needs the System-Admin role, *"matching
#: write-offs"* — CS-35's own words. Seeded **0.00**, so every one needs an
#: Admin until a utility types a figure and is seen doing it.
#:
#: ⚠ A THIRD MONEY THRESHOLD ON THE SAME PAGE. It is neither of the two above
#: it: `write_off_threshold_amount` is billing's automatic small-balance
#: clear-out, `write_off_approval_threshold_amount` is the manual collections
#: write-off. Reading one for another gives away money under a policy nobody
#: set, which is why all three are named in one comment in
#: `apps/tenancy/settings_families.py` as well as here.
KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD = "credit_adjustment_approval_threshold_amount"

#: The S70 rule page the collection ladder's values live on
#: (`settings_families.COLLECTIONS`).
COLLECTIONS = "collections"

#: BR-PAY-017's intervals — SEEDED AND LIVE today (reminder due+3, tiers 10/5,
#: final 48h).
KEY_REMINDER_DAYS_AFTER_DUE = "reminder_days_after_due"
KEY_NOTICE_TIER_DAYS = "notice_tier_days"
KEY_FINAL_NOTICE_HOURS = "final_notice_hours"

#: ⚠ THE TWO KEYS BELOW DO NOT EXIST IN `apps.tenancy.settings_families` YET.
#: Both were RULED by the PO on 2026-08-12 and neither has storage:
#:
#:   `ladder_balance_floor_amount`      OQ-137 (the floor governs the WHOLE
#:       ladder, not only the late fee — a $2.40 residue buys no $8.00 certified
#:       letter) + OQ-157 (*"per utility - uyiliyy can define it using
#:       settings"*, $25.00 the seeded default). Today the figure lives ONLY as
#:       the default argument of `apps/billing/late_fee.assess_late_fee`.
#:   `partial_payment_pause_percent`    OQ-136 (*"partial payment is okay it
#:       should be aleast 25% or 50% of outstanding; you ahve to allow user to
#:       set this limit in configuration or setting section, decide the place"*).
#:       Placement was delegated to Eng and DECIDED: Settings → Configure, beside
#:       the collections settings — which is this family, S70.
#:
#: `apps/tenancy/settings_families.py` belongs to another lane this session, so
#: the two `Param(...)` lines are REPORTED with their exact text rather than
#: written here (they are in the lane report). Until they land these two readers
#: REFUSE, and `ladder.py` takes both figures as arguments so the ruled
#: behaviour is built and asserted meanwhile — the same posture BR-BIL-001's own
#: `balance_floor=` default takes, and the reason OQ-157's registry row gives
#: for it: *"making it a tenant setting later is a caller change and not a
#: rewrite"*.
KEY_LADDER_BALANCE_FLOOR = "ladder_balance_floor_amount"
KEY_PARTIAL_PAUSE_PERCENT = "partial_payment_pause_percent"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one."""
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
    (hard rule 1). This module issues no query of its own.
    """
    read = _resolve(SETTINGS_READ_MODULE, SETTINGS_READ_ATTRIBUTE)
    if read is None:
        raise PaymentRuleError(
            f"apps.{SETTINGS_READ_MODULE}.selectors.{SETTINGS_READ_ATTRIBUTE} is not published, "
            "so the tenant's bank-match tolerance cannot be read. This does NOT fall back to "
            "±3 days: an unreachable setting is not a setting, and every batch matched under an "
            "invented tolerance ends up RECONCILED AND LOCKED (BR-PAY-004).",
            br_ref="BR-PAY-019",
        )
    return dict(read(FINANCE_CONTROLS))


def match_tolerance_days() -> int:
    """BR-PAY-019's auto-match window, in days. Seeded default 3 (r12 #10).

    Read (never assumed) because the rule itself says *finance setting*: a
    tenant who tightened it to ±1 has decided that a bank line two days later is
    NOT the same day's money, and a hardcoded 3 would quietly overrule them.
    """
    values = finance_controls()
    if KEY_MATCH_TOLERANCE_DAYS not in values:
        raise PaymentRuleError(
            f"the tenant's finance-controls settings carry no {KEY_MATCH_TOLERANCE_DAYS!r}. The "
            "ratified default (3) lives in apps.tenancy.settings_families as a seeded Param and "
            "is merged in by tenancy's own read — a default substituted HERE would be a second "
            "copy of it, free to drift from the number on the tenant's own screen.",
            br_ref="BR-PAY-019",
        )
    raw = values[KEY_MATCH_TOLERANCE_DAYS]
    try:
        days = int(raw)
    except (TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_MATCH_TOLERANCE_DAYS} is {raw!r}, which is not a whole number of "
            "days. Auto-matching is refused rather than run against a window nobody can read "
            "(BR-PAY-019).",
            br_ref="BR-PAY-019",
        ) from exc
    if days < 0:
        raise PaymentRuleError(
            f"the tenant's {KEY_MATCH_TOLERANCE_DAYS} is {days}, and a negative tolerance is not "
            "a window at all — it would match nothing, silently, and every batch would land as a "
            "hand-worked exception (BR-PAY-019).",
            br_ref="BR-PAY-019",
        )
    return days


def match_amount_tolerance() -> Decimal:
    """How far a bank line's AMOUNT may sit from a deposit batch's total and
    still auto-match (CR-008 #7, PO 2026-08-17). Seeded **0**.

    ⚠ **A ZERO HERE IS NOT A MISSING VALUE — IT IS THE PRODUCT'S HISTORY.**
    Until this key existed, `reconciliation.auto_match` compared
    `recorded_total == line.amount`, and `abs(a − b) <= 0` is that same
    comparison. So a tenant who never touches the setting keeps penny-exact
    matching, and the day one types 0.05 they have decided — visibly, on their
    own screen, with an audit row — that three cents of bank fee is still the
    same money.

    Same refusals as `match_tolerance_days`, and for the same reason: a matcher
    running on an invented window ties batches a tenant never authorised, and
    every one of those ties ends RECONCILED AND LOCKED (BR-PAY-004). Money is
    `Decimal` end to end (CLAUDE.md rule 2) — the string the settings document
    holds is parsed, never floated.
    """
    values = finance_controls()
    if KEY_MATCH_TOLERANCE_AMOUNT not in values:
        raise PaymentRuleError(
            f"the tenant's finance-controls settings carry no {KEY_MATCH_TOLERANCE_AMOUNT!r}. "
            "The ratified default (0 — penny-exact, today's behaviour) lives in "
            "apps.tenancy.settings_families as a seeded Param and is merged in by tenancy's own "
            "read. A default substituted HERE would be a second copy of a finance setting, free "
            "to drift from the number on the tenant's own screen (BR-PAY-019, CR-008 #7).",
            br_ref="BR-PAY-019",
        )
    raw = values[KEY_MATCH_TOLERANCE_AMOUNT]
    try:
        tolerance = Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_MATCH_TOLERANCE_AMOUNT} is {raw!r}, which is not a money figure. "
            "Auto-matching is refused rather than run against a window nobody can read "
            "(BR-PAY-019).",
            br_ref="BR-PAY-019",
        ) from exc
    if tolerance < 0:
        raise PaymentRuleError(
            f"the tenant's {KEY_MATCH_TOLERANCE_AMOUNT} is {tolerance}, and a negative amount "
            "tolerance would match nothing at all — not even the exact ties this product has "
            "always matched (BR-PAY-019).",
            br_ref="BR-PAY-019",
        )
    return tolerance


def write_off_approval_threshold() -> Decimal:
    """The manual write-off amount at or below which no approver is required
    (CR-008 ruling 2, 2026-08-17). Seeded **0.00**.

    ⚠ **NOT `write_off_threshold_amount`.** That one is BR-BIL-013's automatic
    small-balance write-off at a FINAL bill ($5, capped $50) and nothing about
    approval. The two sat one line apart on the same screen under nearly the
    same name, which is how a utility ends up certain they set one when they
    set the other — `apps/payments/writeoffs.py` says in its own words that
    *"the two must not be confused in a bad-debt report"*.

    **0.00 IS TODAY'S BEHAVIOUR, EXACTLY.** `request_write_off` refuses an
    amount that is not > 0, so at a threshold of 0 no write-off can ever be at
    or below it and every one keeps needing the System-Admin approval
    BR-PAY-020 requires. A utility that wants the convenience types a figure
    and is seen doing it.
    """
    values = finance_controls()
    if KEY_WRITE_OFF_APPROVAL_THRESHOLD not in values:
        raise PaymentRuleError(
            f"the tenant's finance-controls settings carry no "
            f"{KEY_WRITE_OFF_APPROVAL_THRESHOLD!r}. The ratified default (0.00 — every manual "
            "write-off needs an approver) lives in apps.tenancy.settings_families and is merged "
            "in by tenancy's own read. Refused rather than defaulted here: a threshold invented "
            "in this module would decide, invisibly, that somebody's bad debt needed no "
            "approval (BR-PAY-020, CR-008 ruling 2).",
            br_ref="BR-PAY-020",
        )
    raw = values[KEY_WRITE_OFF_APPROVAL_THRESHOLD]
    try:
        threshold = Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_WRITE_OFF_APPROVAL_THRESHOLD} is {raw!r}, which is not a money "
            "figure. Money is NUMERIC(18,6) and never a float (CLAUDE.md rule 2); the write-off "
            "is refused rather than measured against a threshold nobody can read.",
            br_ref="BR-PAY-020",
        ) from exc
    if threshold < 0:
        raise PaymentRuleError(
            f"the tenant's {KEY_WRITE_OFF_APPROVAL_THRESHOLD} is {threshold}. A negative "
            "approval threshold is not a policy — every write-off is above it, which is the "
            "same as 0 but written in a way nobody can read (BR-PAY-020).",
            br_ref="BR-PAY-020",
        )
    return threshold


def credit_adjustment_approval_threshold() -> Decimal:
    """The manual credit/adjustment amount at or below which any clerk may
    record one (CR-059 CS-35, 2026-09-02). Seeded **0.00**.

    **0.00 IS THE STRICT END, NOT THE LOOSE ONE, AND THAT IS DELIBERATE.**
    `record_payment` refuses an amount that is not > 0, so at a threshold of 0
    no credit can ever be at or below it and every one needs the System-Admin
    role. A utility that wants a clerk to be able to give away $10 without
    fetching an admin types 10 on Settings → Accounting → Finance controls and
    is seen doing it — hard-won law 3, the unsafe option must be the one you
    type. It also preserves today's behaviour exactly, because before CS-35
    there was no way to record a credit row at all.

    ⚠ **NOT EITHER WRITE-OFF THRESHOLD.** Three money figures now live on that
    one page and they govern three different acts; `settings_families.py` names
    all three in one comment for exactly this reason. Refused rather than
    defaulted here for the reason the write-off reader gives: a threshold
    invented in this module would decide, invisibly, that somebody's giveaway
    needed no approval.
    """
    values = finance_controls()
    if KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD not in values:
        raise PaymentRuleError(
            f"the tenant's finance-controls settings carry no "
            f"{KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD!r}. The default (0.00 — every manual "
            "credit or adjustment needs a System Admin) lives in apps.tenancy."
            "settings_families and is merged in by tenancy's own read. Refused rather than "
            "defaulted here: a threshold invented in this module would let a credit be "
            "recorded under an approval policy nobody set — see this function's own docstring.",
            br_ref="BR-PAY-020",
        )
    raw = values[KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD]
    try:
        threshold = Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD} is {raw!r}, which is not "
            "a money figure. Money is NUMERIC(18,6) and never a float (CLAUDE.md rule 2); the "
            "credit is refused rather than measured against a threshold nobody can read.",
            br_ref="BR-PAY-020",
        ) from exc
    if threshold < 0:
        raise PaymentRuleError(
            f"the tenant's {KEY_CREDIT_ADJUSTMENT_APPROVAL_THRESHOLD} is {threshold}. A "
            "negative approval threshold is not a policy — every credit is above it, which is "
            "the same as 0 but written in a way nobody can read — see this function's own docstring.",
            br_ref="BR-PAY-020",
        )
    return threshold


# ── the collection ladder's settings (BR-PAY-017 / BR-PAY-016) ─────────────


#: `CR-060` T15 — the switch that decides which account a write-off charges.
ALLOWANCE_ENABLED_KEY = "allowance_for_doubtful_accounts_enabled"


def allowance_for_doubtful_accounts_enabled() -> bool:
    """Whether THIS tenant books an allowance for doubtful accounts.

    **`CR-060` T15, PO ruling 2026-09-03** (*"Why I recommended deferring it.
    Three reasons: let's do this"* — the argument for deferring, quoted back and
    chosen against).

    **FALSE is today's behaviour and the seeded default** (hard-won law 3 — the
    unsafe option must be the one you type). A write-off then posts
    `DR 6900 Bad debt / CR 1200 AR`, which is BR-PAY-020 exactly as signed, and
    nothing about it moves for a utility that never opens this page.

    TRUE means the expense was already taken at the month-end estimate
    (`DR 6900 / CR 1290`), so the write-off consumes the allowance instead:
    `DR 1290 / CR 1200`. **Never both** — that is bad debt expensed twice, which
    is `DEF-3380`'s shape one module over.

    ⚠ **AN UNREACHABLE SETTING IS NOT A SETTING AND THIS DOES NOT DEFAULT.**
    `finance_controls` above raises when tenancy publishes nothing, and this
    lets that refusal through rather than answering False: reading the policy as
    OFF because tenancy could not be asked would charge `6900` for a utility
    that has already provided for the debt, and hard rule 4 leaves no path to
    move a posted entry.
    """
    return bool(finance_controls().get(ALLOWANCE_ENABLED_KEY, False))


def collections() -> dict[str, Any]:
    """The S70 page's current parameter set for THIS tenant.

    Same shape and same refusal as `finance_controls`: tenancy's own read is
    what applies the tenant scope, and an unpublished read is not a default.
    """
    read = _resolve(SETTINGS_READ_MODULE, SETTINGS_READ_ATTRIBUTE)
    if read is None:
        raise PaymentRuleError(
            f"apps.{SETTINGS_READ_MODULE}.selectors.{SETTINGS_READ_ATTRIBUTE} is not published, "
            "so this tenant's collection-ladder settings cannot be read. The ladder does NOT "
            "fall back to the BR-PAY-017 defaults: an unreachable setting is not a setting, and "
            "every step it takes reaches a real customer with a real disconnection date.",
            br_ref="BR-PAY-017",
        )
    return dict(read(COLLECTIONS))


def _collections_value(key: str) -> Any:
    values = collections()
    if key not in values:
        raise PaymentRuleError(
            f"the tenant's collections settings carry no {key!r}. This is not a missing value "
            "with a safe default — it is a value the Product Owner RULED on 2026-08-12 and that "
            "no screen can yet hold: `apps.tenancy.settings_families.COLLECTIONS` has no such "
            "`Param`, so nothing stores it. The ladder REFUSES rather than chasing customers "
            "under a threshold nobody chose. The exact Param line is in the payments lane "
            "report; adding it is tenancy's act, not this module's.",
            br_ref="BR-PAY-017",
        )
    return values[key]


def reminder_days_after_due() -> int:
    """BR-PAY-017's *"due+3 reminder"*, seeded default 3."""
    raw = _collections_value(KEY_REMINDER_DAYS_AFTER_DUE)
    return _whole(raw, KEY_REMINDER_DAYS_AFTER_DUE)


def notice_tier_days() -> tuple[int, ...]:
    """BR-PAY-017's disconnect tiers in days, seeded [10, 5].

    Tenancy's own cross-check already refuses a non-descending list (each tier
    must fire nearer disconnection than the one before), so this reader converts
    and does not re-validate — two implementations of one rule eventually
    disagree.
    """
    raw = _collections_value(KEY_NOTICE_TIER_DAYS)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise PaymentRuleError(
            f"the tenant's {KEY_NOTICE_TIER_DAYS} is {raw!r}, which is not a list of days. The "
            "ladder is refused rather than run on a shape nobody can read (BR-PAY-017).",
            br_ref="BR-PAY-017",
        )
    return tuple(_whole(value, KEY_NOTICE_TIER_DAYS) for value in raw)


def final_notice_hours() -> int:
    """BR-PAY-017's *"48h certified final"*, seeded default 48."""
    return _whole(_collections_value(KEY_FINAL_NOTICE_HOURS), KEY_FINAL_NOTICE_HOURS)


def ladder_balance_floor() -> Decimal:
    """The balance below which NO ladder step runs (PO 2026-08-12, OQ-137/157).

    ⚠ REFUSES TODAY — see `KEY_LADDER_BALANCE_FLOOR`. The ruled figure is
    **$25.00** as a per-utility SEEDED DEFAULT, and `ladder.py` carries it as an
    argument so the ruling is built and asserted while the Param is owed.
    """
    raw = _collections_value(KEY_LADDER_BALANCE_FLOOR)
    try:
        return Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_LADDER_BALANCE_FLOOR} is {raw!r}, which is not a money figure. "
            "Money is NUMERIC(18,6) and never a float (CLAUDE.md rule 2); the ladder is refused "
            "rather than run against a floor nobody can read.",
            br_ref="BR-PAY-017",
        ) from exc


def partial_pause_percent() -> Decimal:
    """What share of the outstanding balance a partial payment must meet to
    pause the ladder (PO 2026-08-12, OQ-136).

    ⚠ REFUSES TODAY — see `KEY_PARTIAL_PAUSE_PERCENT`. The PO named 25% and 50%
    *as examples, not as the value*, so nothing here seeds one: choosing between
    them would be answering a question the PO deliberately handed to each
    utility.
    """
    raw = _collections_value(KEY_PARTIAL_PAUSE_PERCENT)
    try:
        return Decimal(str(raw))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {KEY_PARTIAL_PAUSE_PERCENT} is {raw!r}, which is not a percentage. "
            "The ladder is refused rather than run against a threshold nobody can read "
            "(BR-PAY-016 as amended 2026-08-12).",
            br_ref="BR-PAY-016",
        ) from exc


def _whole(raw: Any, key: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"the tenant's {key} is {raw!r}, which is not a whole number of days. The ladder is "
            "refused rather than run against an interval nobody can read (BR-PAY-017).",
            br_ref="BR-PAY-017",
        ) from exc
    if value < 0:
        raise PaymentRuleError(
            f"the tenant's {key} is {value}, and a negative interval is not a schedule — it "
            "would fire every step at once, on the first day (BR-PAY-017).",
            br_ref="BR-PAY-017",
        )
    return value


def tenant_currency() -> str:
    """The tenant's CHAR(3) currency — the other half of every money figure.

    **DEF-099.** `GET /outstandings` and `GET /payments/summary` served every
    amount with no currency at all, and CLAUDE.md rule 2 is a PAIR: money is
    `NUMERIC(18,6)` **and** a `CHAR(3)` code. Half a rule on the wire is not the
    rule. The screen was reduced to fetching a third endpoint purely to find out
    what money it was rendering, and the alternative it rejected — assuming
    `USD` — prints a confidently wrong symbol on a Canadian tenant's books.

    Read through the seam by NAME rather than importing tenancy (B1), and
    REFUSED rather than defaulted when tenancy cannot answer. A default here
    would be the same guess one layer down, made where nobody can see it.

    BR-TEN-042 locks a tenant's currency once a financial record exists, which
    is what makes one code per response correct: a body cannot span two.
    """
    read = _resolve("tenancy", "regional_settings")
    code = (read() or {}).get("currency") if callable(read) else None
    if not code or len(str(code)) != 3:
        raise PaymentRuleError(
            "the tenant's currency could not be read, so no money figure may be served: "
            "CLAUDE.md rule 2 is NUMERIC(18,6) *and* CHAR(3), and an amount with no "
            "currency is half a fact. Refused rather than defaulted to USD, which would "
            "print a wrong symbol on a tenant that does not bill in dollars.",
            br_ref="BR-TEN-042",
        )
    return str(code).upper()


#: The tenancy read the WRITE half of BR-TEN-081 depends on, named once so the
#: contract is greppable from both sides of the boundary.
TIMEZONE_READ_ATTRIBUTE = "tenant_timezone"


def tenant_timezone() -> ZoneInfo:
    """The utility's OWN clock — what a typed calendar date means (BR-TEN-081).

    **DEF-094, and the danger was in the READING rather than the code.** The PO
    ruled on 2026-08-12 (OQ-153 CLOSED) that a date a clerk types means
    **midnight in the UTILITY's own timezone**. DEF-082 built the read half:
    `tenant_today()` reads the tenant's zone, proved by moving the answer across
    a date boundary — frozen at **2026-08-22T04:30:00Z**, a utility on
    `America/Chicago` answers **2026-08-21** while UTC has already rolled over.
    **The write half was untouched.** `apps/payments/api._moment` went on
    anchoring a bare `YYYY-MM-DD` at midnight **UTC**, so a Houston clerk typing
    *22 August* stored `2026-08-22T00:00:00Z` and every screen — reading through
    the half that WAS fixed — showed **21 August**. Anyone seeing "DEF-082
    fixed" would reasonably conclude the rule was honoured, and be wrong.

    **RESOLVED BY NAME, never re-derived.** It returns tenancy's OWN
    `tenant_timezone()`, which is the same function `tenant_today()` reads, so
    the day a payment is STORED under and the day it is DISPLAYED under cannot
    drift apart again — a second copy of the fallback rule here would be this
    defect rebuilt.

    **REFUSES when the seam cannot answer, and that is not the same as a tenant
    with no zone.** Two different situations, and only one is a failure:

      * tenancy publishes no `tenant_timezone` — the seam is UNWIRED. It cannot
        answer, so it says so. Storing UTC here would silently re-create the
        exact one-day shift this closes, in the one place nobody would look.
      * tenancy answers, and the tenant simply has not chosen a zone — tenancy
        answers **UTC**, which is what every screen in the product renders that
        tenant's dates in. Storing UTC then is CORRECT: the day the clerk sees
        equals the day that was stored, which is the property BR-TEN-081 is
        actually about.
    """
    read = _resolve("tenancy", TIMEZONE_READ_ATTRIBUTE)
    if read is None:
        raise PaymentRuleError(
            f"apps.tenancy.selectors.{TIMEZONE_READ_ATTRIBUTE} is not published, so the "
            "utility's own clock cannot be read and a date a clerk TYPED cannot be anchored "
            "(BR-TEN-081, PO 2026-08-12 closing OQ-153). This does NOT fall back to midnight "
            "UTC: that IS the defect (DEF-094) — a Houston clerk typing 22 August would store "
            "2026-08-22T00:00:00Z and every screen would show 21 August, because the READ half "
            "of this rule already reads the tenant's zone. A one-day shift on a posting date is "
            "a late fee charged to a customer who paid on time (BR-PAY-021) and a deposit batch "
            "on the wrong drawer day (BR-PAY-025).",
            br_ref="BR-TEN-081",
        )
    zone = read()
    if not isinstance(zone, ZoneInfo):
        raise PaymentRuleError(
            f"apps.tenancy.selectors.{TIMEZONE_READ_ATTRIBUTE} answered {zone!r}, which is not a "
            "ZoneInfo. The anchor is refused rather than guessed: see the refusal above for what "
            "a guessed zone costs (BR-TEN-081).",
            br_ref="BR-TEN-081",
        )
    return zone


#: Tenancy's own instant, named once so the contract is greppable from both
#: sides of the boundary — the same shape `TIMEZONE_READ_ATTRIBUTE` has.
NOW_READ_ATTRIBUTE = "tenant_now"


def tenant_now() -> datetime:
    """This instant on the UTILITY's clock, read from tenancy and never here.

    ⚠ **GATE G6 BANS `timezone.now()` EVERYWHERE UNDER `/payments/`, INCLUDING
    THIS FILE** (BR-TEN-043, the event-time law). That is not an obstacle being
    worked around: a clock read inside a money path decides a business day in
    the SERVER's timezone, which is the whole defect BR-TEN-081 exists for. So
    the clock stays in `apps.tenancy.selectors`, beside `tenant_today()` and
    `tenant_timezone()` — one clock, one zone, one place — and this resolves it
    BY NAME exactly as `tenant_timezone` above does.

    Its one caller is `counters_api._required_moment`, which bounds a counter
    moment to the utility's own business day (PO ruling 2026-09-23, *"(b)
    Backdate within the same day"*). It VALIDATES what a person typed; it is
    never stamped into storage, because the moment still comes from the person.

    **REFUSES when the seam is unwired**, for the same reason its sibling does:
    a bound that silently stops being applied is worse than no bound, because
    the screen goes on showing the field as though the rule were live.
    """
    read = _resolve("tenancy", NOW_READ_ATTRIBUTE)
    if read is None:
        raise PaymentRuleError(
            f"apps.tenancy.selectors.{NOW_READ_ATTRIBUTE} is not published, so the utility's "
            "own clock cannot be read and a counter moment cannot be checked against the "
            "utility's own business day (PO ruling 2026-09-23). This does NOT fall back to the "
            "server's clock: a server in another zone would refuse a perfectly good 08:55 and "
            "accept yesterday's, which is the rule inverted rather than relaxed.",
            br_ref="BR-TEN-043",
        )
    moment = read()
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise PaymentRuleError(
            f"apps.tenancy.selectors.{NOW_READ_ATTRIBUTE} answered {moment!r}, which is not an "
            "offset-bearing datetime. Refused rather than guessed: a naive instant compared "
            "against an anchored one is a comparison between two different days.",
            br_ref="BR-TEN-043",
        )
    return moment



# ── CR-161-BRC10 W5 · the utility's own payment fields, at entry ────────────
def validate_entry_answers(submitted: Any, *, screen: str | None) -> dict[str, Any]:
    """The tenant's payment field definitions applied to what a cashier typed.

    tenancy's published value validator (`services`) is the ONE validator every
    owning module calls (US-SHL-015): unknown keys refused, options enforced,
    types checked, and a required field blocks only the screen it is placed on
    as Input (`screen`, BR-TEN-052 as amended). It returns the cleaned blob and
    writes nothing.

    REFUSES when tenancy publishes no validator — an unresolved seam must never
    let a client's blob into a jsonb column unchecked (the DEF-075 shape).
    `custom_values.capture` is the only caller.
    """
    validate = _resolve("tenancy", "validate_custom_data_for", "services")
    if validate is None:  # pragma: no cover - tenancy always publishes it
        raise PaymentRuleError(
            "This utility's payment fields cannot be checked right now, so the "
            "payment was not recorded."
        )
    return validate("payments", submitted, screen=screen)

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-021@b6e4c19 (the five EP-PAY-06 sources — B2 §2 + Addendum r12 #10 · EP-PAY-06-deposits-bank-rec.md US-PAY-021 · 08-payments/02-business-rules.md BR-PAY-019 · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a cross-module read) E=deferred(no-frontend-half; the S71 card that WRITES this value is tenancy's and already ships) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_020_023_bank_rec.py (TC-2's ±1 variant drives the setting, not a constant)
# exceptions: (LADDER lane 2026-08-15) TWO KEYS THIS FILE READS DO NOT EXIST
#         YET — `ladder_balance_floor_amount` (OQ-137/OQ-157) and
#         `partial_payment_pause_percent` (OQ-136). Both were RULED on
#         2026-08-12 and `apps/tenancy/settings_families.py` belongs to
#         another lane this session, so the two `Param(...)` lines are
#         REPORTED verbatim in the lane report rather than written here. The
#         readers REFUSE meanwhile and `ladder.py` takes both figures as
#         arguments, which is BR-BIL-001's own precedent for the same $25.00
#         · NO local default, deliberately — a missing key REFUSES. The
#         ratified 3 lives once, in apps.tenancy.settings_families, and is merged
#         in by tenancy's own read; a `.get(key, 3)` here would be a second copy
#         of a finance setting, free to drift from the tenant's own screen
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
