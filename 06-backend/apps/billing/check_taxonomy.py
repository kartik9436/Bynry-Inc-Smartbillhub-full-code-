# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check — problems by CATEGORY → TAG)
#           Screen: S31.2 (the redrawn Check step, images 09–23 of
#           05-prototype/bulk-bill-run-2026-09-30/)
# Rules:    BR-BIL-1052 (every check on every account; every problem under its
#           own tag) · BR-BIL-1053 (Payments & balances is a Check category) ·
#           BR-BIL-015 (a decision is a human's) · BR-BIL-1025 (nothing to bill
#           is not a problem)
# Plan:     15-bulk-bill-run-build-plan.md B10 · DEF-BIL-8209
# Tests:    06-backend/tests/test_bbr_check_engine.py (taxonomy cases)
# ───────────────────────────────────────────────────────
"""Every finding code the Check can raise → category · tag · severity · fix screen.

ONE MAP, OWNED HERE, AND IT IS CODE-ONLY. The Check screen draws nine
categories on its left rail and one tag per code under them (changes row 36;
the drawing, image 10). Before this module a code reached the screen as a bare
string and the screen kept its own reason→label table, which is how ten codes
came to have no clerk label at all (`DEF-BIL-8209`) — the fallback *"Held back
— the line below says why"* was all a clerk saw for them.

WHAT EACH ENTRY SAYS
--------------------
  * **category** — one of `CATEGORIES`, in the drawing's order. NINE, not eight:
    changes row 36 names eight and row 38 adds *Payments & balances*; the
    decision log of 2026-09-30 records the count (judgment 4).
  * **severity** — `blocks` (the account is not billed until it is fixed),
    `decision` (the account CAN be billed; a person answers first) or `warning`
    (it bills anyway; somebody should know). `None` on exactly one code,
    `account_has_nothing_to_bill`: BR-BIL-1025 says it is the CORRECT state and
    must never reach the problems list, so it has a label (Not in this run shows
    it) and no severity.
  * **fix** — where the fix happens: a screen that OWNS the fact (Meter Reads,
    Accounts, Plans & Rates, Assets, Premises, Payments, Settings), `check` when
    the answer is given on the Check step itself, or `support` when nothing a
    clerk can do clears it.
  * **label** — the catalogue key the screen translates, present in all eleven
    catalogues. Existing `billing.run.reason.*` keys are REUSED rather than
    re-minted: the shipped screens already read them, and two keys for one
    code is two sentences that will drift.

⚠ **A CODE THE ENGINE RAISES THAT IS NOT HERE IS A DEFECT, NOT A DEFAULT.**
`classify` answers an `UNMAPPED` entry rather than raising, because a Check
that crashed on a new code would stop the whole pass over one missing line —
the exact failure BR-BIL-1052 forbids — but the test suite enumerates every
constant the engine raises and fails on one missing here.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── the nine categories, in the drawing's order ─────────────────────────────
CAT_PAYMENTS = "payments_balances"
CAT_READINGS = "readings"
CAT_METER_HISTORY = "meter_history"
CAT_PLANS = "plans_rates"
CAT_ACCOUNTS = "accounts_units"
CAT_MASTER = "master_accounts"
CAT_ASSETS = "assets_connections"
CAT_PERIOD = "billing_period"
CAT_SETUP = "setup"
CATEGORIES: tuple[str, ...] = (
    CAT_PAYMENTS,
    CAT_READINGS,
    CAT_METER_HISTORY,
    CAT_PLANS,
    CAT_ACCOUNTS,
    CAT_MASTER,
    CAT_ASSETS,
    CAT_PERIOD,
    CAT_SETUP,
)

# ── severities ──────────────────────────────────────────────────────────────
BLOCKS = "blocks"
DECISION = "decision"
WARNING = "warning"
SEVERITIES: tuple[str, ...] = (BLOCKS, DECISION, WARNING)

# ── where the fix happens ───────────────────────────────────────────────────
FIX_METER_READS = "meter_reads"
FIX_ACCOUNTS = "accounts"
FIX_PLANS = "plans_rates"
FIX_ASSETS = "assets"
FIX_PREMISES = "premises"
FIX_PAYMENTS = "payments"
FIX_SETTINGS = "settings"
FIX_CHECK = "check"
FIX_SUPPORT = "support"

# ── codes minted by the Check engine itself (`check_engine.py`) ─────────────
#: A reading arrived with a quantity and no unit and its METER records one:
#: a DECISION whose suggestion is the meter's unit (PO 2026-09-30, rows 45–46).
#: Until 2026-09-30 a unitless reading was a plain `BillingRuleError` that
#: ended the WHOLE pass (`DEF-BIL-8207`).
READ_HAS_NO_UNIT = "reading_has_no_unit"
#: The reading AND its meter record no unit: nothing to suggest, so that
#: service stays blocked (rule 3). `runs.READ_HAS_NO_UNIT` raises this one.
READ_AND_METER_HAVE_NO_UNIT = "reading_and_meter_have_no_unit"
#: Former AUTO cases with no code of their own before (changes row 46).
POSSIBLE_ROLLOVER = "possible_rollover"
#: DEF-BIL-8244 — its Accept is applied (decisions.APPLIED_CHOICES): both parts bill.
METER_SWAPPED = "meter_swapped"
PRICE_CHANGED_MID_PERIOD = "price_changed_mid_period"
#: A rule refused this account with no reason code of its own — a plain
#: `BillingRuleError` from anywhere below the Check. Blocks the account; the
#: sentence is the refusal's own.
CHECK_REFUSED = "check_refused"
#: Anything else went wrong on this account. Blocks the account, carries a
#: SUPPORT REFERENCE, and the next account is checked (changes rows 21, 24).
CHECK_FAILED = "check_failed_unexpectedly"

# ── warnings the drafts already carry (bill_warnings.py / contracts.py) ─────
WARN_BASE_NOT_SET = "base_not_set"
#: PO ruling 2026-10-01 — a capacity service's base code has no price for an
#: asset's size: that size's base bills $0.00 and the account is BILLED. A
#: warning on Check, Sign off and Send, never a reason to leave the account
#: out, and no sign-off tick (PO 2026-10-01, option A).
WARN_BASE_SIZE_NOT_PRICED = "base_size_not_priced"
WARN_NO_AGREEMENTS = "no_service_agreements"
#: PO ruling 2026-10-01 on `DEF-RAT-8004` (option A) — a legacy overlap left
#: two versions of one rate schedule in force on the service date; the newest
#: priced (`BR-RAT-1055`). A warning on Check, Sign off and Send; no sign-off
#: tick; the account bills.
WARN_SCHEDULE_VERSIONS_OVERLAP = "schedule_versions_overlap"
#: PO ruling 2026-10-01 (*"A METER WITH NO RECORDED SIZE GETS NO MINIMUM, AND
#: THE BILL-RUN CHECK FLAGS IT"*, option A) — a connection on a schedule with
#: per-size minimums has a meter with no recorded size, so no minimum was
#: applied. A warning; no sign-off tick; the bill still goes out.
WARN_METER_SIZE_NOT_RECORDED = "meter_size_not_recorded"
#: PO ruling 2026-09-30 (decision log *"A PROBLEM NEVER STOPS THE CHECKING"*,
#: item 2): a reading stored without a unit took the unit recorded on its
#: meter. Bills anyway; the clerk sees it.
WARN_UNIT_FROM_METER = READ_HAS_NO_UNIT
#: warning dict `key` → finding code. The dict shape `{key, params}` is the
#: drafts' own (bill_warnings.py); the Check files each under ONE code.
WARNING_CODE_BY_KEY: dict[str, str] = {
    "billing.oneTime.warn.baseNotSet": WARN_BASE_NOT_SET,
    "billing.oneTime.warn.baseSizeNotPriced": WARN_BASE_SIZE_NOT_PRICED,
    "billing.oneTime.warn.noAgreements": WARN_NO_AGREEMENTS,
    "billing.run.warn.scheduleVersionsOverlap": WARN_SCHEDULE_VERSIONS_OVERLAP,
    "billing.run.warn.meterSizeNotRecorded": WARN_METER_SIZE_NOT_RECORDED,
    "billing.run.warn.unitTakenFromMeter": WARN_UNIT_FROM_METER,
}

# ── Payments & balances (BR-BIL-1053) ───────────────────────────────────────
PAY_AFTER_CUTOFF = "paid_after_cutoff"
PAY_UNMATCHED = "unmatched_payment"
PAY_BOUNCED = "bounced_payment_not_reversed"
PAY_INSTALMENT_DUE = "plan_instalment_due"
PAY_LEVEL_OFF_TRACK = "level_pay_off_track"
PAY_CREDIT_COVERS = "credit_covers_bill"
PAY_CARD_EXPIRING = "autopay_card_expiring"
PAY_DEPOSIT_NOT_PAID = "deposit_not_paid"
PAY_IN_COLLECTIONS = "in_collections"
PAYMENT_CODES: tuple[str, ...] = (
    PAY_AFTER_CUTOFF,
    PAY_UNMATCHED,
    PAY_BOUNCED,
    PAY_INSTALMENT_DUE,
    PAY_LEVEL_OFF_TRACK,
    PAY_CREDIT_COVERS,
    PAY_CARD_EXPIRING,
    PAY_DEPOSIT_NOT_PAID,
    PAY_IN_COLLECTIONS,
)

REASON_KEY = "billing.run.reason.{code}"
CATEGORY_KEY = "billing.check.category.{category}"


@dataclass(frozen=True)
class Tag:
    code: str
    category: str
    severity: str | None
    fix: str

    @property
    def label_key(self) -> str:
        return REASON_KEY.format(code=self.code)

    @property
    def suggests(self) -> bool:
        return self.code in SUGGESTS

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "fix": self.fix,
            "fix_action": dict(FIX_ACTIONS.get(self.fix, {})),
            "inline_fix": dict(INLINE_FIXES.get(self.code, {})) or None,
            "suggests": self.suggests,
            "label_key": self.label_key,
        }


def _t(code: str, category: str, severity: str | None, fix: str) -> Tag:
    return Tag(code=code, category=category, severity=severity, fix=fix)


#: THE MAP. Grouped by category in the drawing's order; within a category,
#: blocking first, then decisions, then warnings.
#:
#: ⚠ **THE SEVERITIES ARE THE PO'S RATIFIED TABLE OF 2026-09-30, NOT A GUESS**
#: (decision log *"THE ALTERNATIVE FOR EVERY STEP THAT USED TO STOP AN
#: ACCOUNT"*, amended the same day by *"NO CHECK FIXES ANYTHING BY ITSELF"* and
#: *"THE FOUR KINDS OF PROBLEM"*; changes rows 44–46):
#:   * DECISION — a sensible answer exists but can change the bill: the clerk
#:     chooses (answer for all, per row, or for a selection; default first).
#:     The seven former "auto" cases are decisions whose first choice is the
#:     product's SUGGESTION (`SUGGESTS`), pre-selected, with Hold beside it.
#:   * BLOCKS — no safe answer (a rule forbids guessing, or a question is open
#:     with the PO): only that account (or service) waits; every other check
#:     still runs.
#:   * WARNING — nothing to decide; the account still goes to Ready.
#:   * UTILITY-WIDE — not a tag at all: `runs.UtilityWideStop` (Meter Reads
#:     not answering, currency not set).
TAGS: dict[str, Tag] = {
    tag.code: tag
    for tag in (
        # ── Payments & balances (BR-BIL-1053) ───────────────────────────────
        _t(PAY_BOUNCED, CAT_PAYMENTS, DECISION, FIX_PAYMENTS),
        _t(PAY_AFTER_CUTOFF, CAT_PAYMENTS, DECISION, FIX_CHECK),
        _t(PAY_UNMATCHED, CAT_PAYMENTS, DECISION, FIX_PAYMENTS),
        _t(PAY_INSTALMENT_DUE, CAT_PAYMENTS, DECISION, FIX_CHECK),
        _t("late_fee", CAT_PAYMENTS, DECISION, FIX_CHECK),
        # DEF-BIL-8241 (2026-09-30): a WARNING, not a decision — coordinator
        # judgment under BR-BIL-017, decision log *"THE FOUR PAYMENT CHECKS
        # WITH NO DATA BEHIND THEM ARE BUILT"*: *"the Check raises it as a
        # warning so the clerk sees it before billing, and never re-levels by
        # itself"*. Its old choices (keep / reset) are gone with it: *reset*
        # was a re-level, which the Check may not do.
        _t(PAY_LEVEL_OFF_TRACK, CAT_PAYMENTS, WARNING, FIX_PAYMENTS),
        _t(PAY_CREDIT_COVERS, CAT_PAYMENTS, WARNING, FIX_PAYMENTS),
        _t(PAY_CARD_EXPIRING, CAT_PAYMENTS, WARNING, FIX_PAYMENTS),
        _t(PAY_DEPOSIT_NOT_PAID, CAT_PAYMENTS, WARNING, FIX_ACCOUNTS),
        _t(PAY_IN_COLLECTIONS, CAT_PAYMENTS, WARNING, FIX_PAYMENTS),
        # ── Readings ────────────────────────────────────────────────────────
        # Stays blocked: the reading AND its meter record no unit (rule 3).
        _t(READ_AND_METER_HAVE_NO_UNIT, CAT_READINGS, BLOCKS, FIX_METER_READS),
        _t("metering_has_not_published_reads", CAT_READINGS, BLOCKS, FIX_SUPPORT),
        _t("missing_read_undecided_at_calculate", CAT_READINGS, BLOCKS, FIX_CHECK),
        # Decisions — the ratified table (disputed: Hold / Estimate).
        _t("account_held_by_disputed_read", CAT_READINGS, DECISION, FIX_METER_READS),
        # Former AUTO → decision with a suggestion (changes rows 45–46).
        _t(READ_HAS_NO_UNIT, CAT_READINGS, DECISION, FIX_METER_READS),
        _t(POSSIBLE_ROLLOVER, CAT_READINGS, DECISION, FIX_METER_READS),
        _t("missing_read", CAT_READINGS, DECISION, FIX_CHECK),
        _t("estimated_read", CAT_READINGS, DECISION, FIX_CHECK),
        _t("high_usage", CAT_READINGS, DECISION, FIX_CHECK),
        _t("low_usage", CAT_READINGS, DECISION, FIX_CHECK),
        _t("no_usage", CAT_READINGS, DECISION, FIX_CHECK),
        # ── Meter history ───────────────────────────────────────────────────
        # Ratified decisions: went down (not a rollover) Estimate/Hold · swap
        # with a reading missing Estimate/Hold · TOU unmatched flat/Hold · no
        # multiplier HOLD (default) / Bill with 1.
        _t("anchor_register_went_backwards", CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        _t("anchor_meter_exchanged", CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        _t("anchor_tou_windows_unanchorable", CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        _t("anchor_multiplier_unstated", CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        # Changes row 44, built 2026-10-01 — a meter never read has no
        # multiplier; the ruled path used to BLOCK it as `ruled_path_refused`.
        # Its own tag (row 46): Hold (default) / Bill with multiplier 1.
        _t("meter_has_no_multiplier", CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        _t(METER_SWAPPED, CAT_METER_HISTORY, DECISION, FIX_METER_READS),
        _t("meter_factor", CAT_METER_HISTORY, DECISION, FIX_CHECK),
        _t("replacement", CAT_METER_HISTORY, DECISION, FIX_CHECK),
        _t("true_up", CAT_METER_HISTORY, DECISION, FIX_CHECK),
        # ── Plans & rates ───────────────────────────────────────────────────
        # Stays blocked: pricing refused on a SETUP CONFLICT (that service).
        _t("ruled_path_refused", CAT_PLANS, BLOCKS, FIX_PLANS),
        _t("rating_refused_to_price", CAT_PLANS, BLOCKS, FIX_PLANS),
        _t("unit_service_priced_nowhere", CAT_PLANS, BLOCKS, FIX_PLANS),
        # Stays blocked: no plan on the unit — PO 2026-10-01, *"we ahve to
        # show the warning that no plan on unit, please fi the plan first"*
        # (BR-BIL-1063). No customer-type default plan exists (OQ-RAT-12782
        # closed, BR-RAT-1047), so nothing can bill it until the plan is set —
        # on the row (`check_fixes.FIX_SET_PLAN`), then Re-check.
        _t("unit_has_no_plan", CAT_PLANS, BLOCKS, FIX_ACCOUNTS),
        # Ratified decision: no price in force on the date → latest earlier
        # version / Hold.
        _t("tariff_has_no_version_in_force_at_service_date", CAT_PLANS, DECISION, FIX_PLANS),
        # Former AUTO → decision with a suggestion.
        _t("plan_not_published", CAT_PLANS, DECISION, FIX_PLANS),
        _t("plan_has_no_tariff_for_service", CAT_PLANS, DECISION, FIX_PLANS),
        _t("no_charge_applies_to_this_customer_type", CAT_PLANS, DECISION, FIX_PLANS),
        _t("extra_charge", CAT_PLANS, DECISION, FIX_CHECK),
        _t("overcharge", CAT_PLANS, DECISION, FIX_CHECK),
        _t(WARN_BASE_NOT_SET, CAT_PLANS, WARNING, FIX_PLANS),
        _t(WARN_BASE_SIZE_NOT_PRICED, CAT_PLANS, WARNING, FIX_PLANS),
        _t(WARN_SCHEDULE_VERSIONS_OVERLAP, CAT_PLANS, WARNING, FIX_PLANS),
        # ── Accounts & units ────────────────────────────────────────────────
        # Stays blocked: no unit (fix on the row by picking one).
        _t("account_has_no_unit", CAT_ACCOUNTS, BLOCKS, FIX_ACCOUNTS),
        # Ratified decision: city limits unknown → HOLD (default) / inside / outside.
        _t("premises_jurisdiction_unstated", CAT_ACCOUNTS, DECISION, FIX_PREMISES),
        _t("base_only_billing", CAT_ACCOUNTS, DECISION, FIX_CHECK),
        _t(WARN_NO_AGREEMENTS, CAT_ACCOUNTS, WARNING, FIX_ACCOUNTS),
        # BR-BIL-1025 amended 2026-09-30 (*"only warning- i agree"*): a UNIT
        # fact, shown on Scope and in Not in this run — never an account tag.
        _t("unit_has_no_billable_account", CAT_ACCOUNTS, WARNING, FIX_ACCOUNTS),
        # BR-BIL-1025: the CORRECT state. Labelled, never a problem.
        _t("account_has_nothing_to_bill", CAT_ACCOUNTS, None, FIX_ACCOUNTS),
        # ── Master accounts (stay blocked — OQ-334 / OQ-335 open) ───────────
        _t("master_coverage_unresolved", CAT_MASTER, BLOCKS, FIX_ACCOUNTS),
        _t("master_coverage_spans_two_plans", CAT_MASTER, BLOCKS, FIX_ACCOUNTS),
        _t("master_coverage_repeats_a_service", CAT_MASTER, BLOCKS, FIX_ACCOUNTS),
        _t("master_unbilled_units_unpriceable", CAT_MASTER, BLOCKS, FIX_PLANS),
        _t("unbilled_unit_service_state_unreadable", CAT_MASTER, BLOCKS, FIX_ASSETS),
        # ── Assets & connections ────────────────────────────────────────────
        # Stays blocked: no size (size sets the price; no default).
        _t("connection_size_unresolved_for_sized_schedule", CAT_ASSETS, BLOCKS, FIX_ASSETS),
        _t("unmetered_asset_count_undetermined", CAT_ASSETS, BLOCKS, FIX_ASSETS),
        _t("installed_capacity_undetermined", CAT_ASSETS, BLOCKS, FIX_ASSETS),
        _t(WARN_METER_SIZE_NOT_RECORDED, CAT_ASSETS, WARNING, FIX_ASSETS),
        _t("cut_covers_some_services_and_not_others", CAT_ASSETS, BLOCKS, FIX_ASSETS),
        # PO 2026-09-30, *"sane no line - and use 0"*: no line, bills anyway.
        _t("service_not_connected", CAT_ASSETS, WARNING, FIX_ASSETS),
        _t("plan_service_not_connected", CAT_ASSETS, WARNING, FIX_ASSETS),
        # ── Billing period ──────────────────────────────────────────────────
        _t(PRICE_CHANGED_MID_PERIOD, CAT_PERIOD, DECISION, FIX_CHECK),
        _t("billing_continuity", CAT_PERIOD, DECISION, FIX_CHECK),
        _t("days_threshold", CAT_PERIOD, DECISION, FIX_CHECK),
        # ── Setup ───────────────────────────────────────────────────────────
        # Currency not set is UTILITY-WIDE (`runs.UtilityWideStop`); the code
        # keeps a tag so a legacy row still has a label.
        _t("tenant_currency_unresolved", CAT_SETUP, BLOCKS, FIX_SETTINGS),
        _t("cycle_has_no_service_points", CAT_SETUP, BLOCKS, FIX_SETTINGS),
        _t(CHECK_REFUSED, CAT_SETUP, BLOCKS, FIX_SUPPORT),
        _t(CHECK_FAILED, CAT_SETUP, BLOCKS, FIX_SUPPORT),
    )
}

#: The seven former AUTO cases (changes rows 45–46): each is a DECISION whose
#: first choice is the product's suggestion, pre-selected, with Hold beside
#: it. Nothing is applied to a bill until a clerk accepts it.
SUGGESTS: frozenset[str] = frozenset(
    {
        READ_HAS_NO_UNIT,
        POSSIBLE_ROLLOVER,
        METER_SWAPPED,
        "plan_not_published",
        "plan_has_no_tariff_for_service",
        "no_charge_applies_to_this_customer_type",
        PRICE_CHANGED_MID_PERIOD,
    }
)

#: Where each fix happens, for the screen (changes row 46: *"a FIX for the
#: underlying record — on the row where the fact belongs to this account, or a
#: link to the owning screen and then Re-check"*). `inline` names the OWNING
#: module's API the screen calls; billing writes none of them, and the saved
#: result is re-checked by `check_staleness` when that module's record moves.
FIX_ACTIONS: dict[str, dict[str, str]] = {
    FIX_METER_READS: {"kind": "link", "module": "meter_reads", "screen": "reads"},
    FIX_ACCOUNTS: {"kind": "link", "module": "customers", "screen": "accounts"},
    FIX_PLANS: {"kind": "link", "module": "rating", "screen": "plans"},
    FIX_ASSETS: {"kind": "link", "module": "assets", "screen": "assets"},
    FIX_PREMISES: {"kind": "link", "module": "metering", "screen": "premises"},
    FIX_PAYMENTS: {"kind": "link", "module": "payments", "screen": "payments"},
    FIX_SETTINGS: {"kind": "link", "module": "tenancy", "screen": "settings"},
    FIX_CHECK: {"kind": "decide", "module": "billing", "screen": "check"},
    FIX_SUPPORT: {"kind": "support", "module": "support", "screen": "support"},
}
#: The codes whose fact the clerk can supply ON THE ROW (changes row 46; PO
#: 2026-09-30: *Accept suggestion* is THIS BILL ONLY, a decision row — the
#: record itself changes only through an explicit **Fix**, written by the
#: OWNING module and audited there, after which the staleness sweep re-checks
#: the account). `kind` is `correct` (a superseding reading — a committed read
#: is immutable, BR-MET-053), `record` (a missing reading) or `set` (a field on
#: the owning record). ⚠ **No endpoint is named here on purpose:** billing
#: calls none of them, and the screen half (plan B14) is where the owning
#: module's route is wired — a path typed here would be a claim nothing checks.
INLINE_FIXES: dict[str, dict[str, str]] = {
    READ_HAS_NO_UNIT: {"module": "meter_reads", "kind": "correct", "field": "unit"},
    POSSIBLE_ROLLOVER: {"module": "meter_reads", "kind": "correct", "field": "value"},
    METER_SWAPPED: {"module": "meter_reads", "kind": "record", "field": "value"},
    "account_has_no_unit": {"module": "customers", "kind": "set", "field": "unit_id"},
    "connection_size_unresolved_for_sized_schedule": {
        "module": "assets",
        "kind": "set",
        "field": "size_class",
    },
}

#: What `classify` answers for a code nobody mapped. Setup · blocks · support:
#: an unknown problem is not billed on a guess, and the label the screen shows
#: is the shipped fallback. The test suite fails on any engine code that lands
#: here, so this is reached only by a code minted after this map was written.
UNMAPPED = Tag(code="unmapped", category=CAT_SETUP, severity=BLOCKS, fix=FIX_SUPPORT)


def classify(code: str) -> Tag:
    """The tag for one finding code — never raises (see the module docstring)."""
    return TAGS.get(code) or Tag(
        code=code, category=UNMAPPED.category, severity=UNMAPPED.severity, fix=UNMAPPED.fix
    )


def severity_of(code: str) -> str | None:
    return classify(code).severity


def is_blocking(code: str) -> bool:
    return severity_of(code) == BLOCKS


def warning_code(warning: dict) -> str:
    """The finding code for one draft warning `{key, params}`."""
    key = str((warning or {}).get("key") or "")
    return WARNING_CODE_BY_KEY.get(key, key.rsplit(".", 1)[-1] or "unmapped")


def categories_payload() -> list[dict[str, object]]:
    """The left rail's skeleton: nine categories, each with its tags in order."""
    out: list[dict[str, object]] = []
    for category in CATEGORIES:
        out.append(
            {
                "category": category,
                "label_key": CATEGORY_KEY.format(category=category),
                "tags": [tag.as_dict() for tag in TAGS.values() if tag.category == category],
            }
        )
    return out


__all__ = [
    "BLOCKS",
    "CATEGORIES",
    "CHECK_FAILED",
    "CHECK_REFUSED",
    "DECISION",
    "PAYMENT_CODES",
    "READ_HAS_NO_UNIT",
    "SEVERITIES",
    "TAGS",
    "Tag",
    "WARNING",
    "categories_payload",
    "classify",
    "is_blocking",
    "severity_of",
    "warning_code",
]
