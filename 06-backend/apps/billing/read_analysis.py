# ── Trace ──────────────────────────────────────────────
# Story:    CR-038 W8 (11-change-requests.md — "Bill-run read analysis
#           (Estimated · High · Low · Days · Factor · Replacements · True-up $)
#           — 2 of 8 prototype tabs served") · US-BIL-003 (S31.3 — the case
#           tables the dispositions land in)   Screens: S31.3 (r10 BIL-02.2)
# Rules:    BR-MET-121 (the BILL RUN is the authoritative days judgment — PO
#           2026-08-26, verbatim: "when you run bill cycle you pull the reading
#           and at that time we have to decide whether it is for 90 days or
#           whrther it for 30 days or 15 days ; and if there is an issue with
#           reading days we flag it") · BR-MET-022/056 (outcomes are
#           self-describing; a consumer renders STORED verdicts and re-derives
#           nothing) · BR-MET-020 (no threshold is ever hardcoded) ·
#           BR-MET-026..029 + BR-BIL-006 / GT-9 / WE-13 ❄ (estimation and the
#           true-up: register arithmetic at the next actual, current-period
#           rates, on that bill) · BR-BIL-015/061 + PO 2026-08-26 re-affirmed
#           ("keep the rule — speed comes from the bulk button, not from
#           decisions nobody made; an auditor asking 'who chose to estimate
#           M-4412?' gets a name") — recommendations render as SUGGESTIONS,
#           never pre-selected · BR-BIL-060 (bulk on every case surface) ·
#           BR-SHL-023 (one money path — the client never sums) · CLAUDE.md
#           rules 2 and 3
# Tests:    06-backend/tests/test_cr038_w8_read_analysis.py
# Impacts:  apps/billing/selectors.exceptions_dict (serves these rows) ·
#           apps/billing/decisions.py (records the dispositions; HOLDING_CHOICES
#           carries the two named pricing boundaries) · apps/metering/selectors
#           .read_analysis_for_unit + .cycle_expected_span_days (the seams)
# ───────────────────────────────────────────────────────
"""The run's read analysis — the prototype's eight read categories, served.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — **the true-up branch prices money.**
`_true_up_row` calls rating's published `price_period` to state what the
trued-up quantity is worth on THIS bill, so this module touches rating math's
output and belongs on the review ledger. Everything else here renders STORED
metering facts and writes nothing.

WHAT THIS MODULE IS. r10 BIL-02.2's Meter-reads step draws nine read tabs —
All · Missing · Estimated · High · Low · Days threshold · Meter factor, and
CR-038 W8 adds Replacements · True-up — and the built run served two of the
cases (Missing as BR-BIL-015's decision, Disputed as BR-MET-024's hold). The
facts behind the other categories already live on every committed read
(`rule_outcomes` travel from staged row to committed read for exactly this),
so this module ASKS metering for them and shapes them into S31.3 case rows.

THREE POSTURES, EACH LOAD-BEARING:

1. **Stored verdicts, never recomputed** (BR-MET-022/056). A High row shows
   this month, their average, the ratio and the threshold — all read off the
   outcome the validation engine stored at commit. Re-deriving any of it here
   would be a second implementation that drifts the day a threshold changes.

2. **The days judgment is the RUN's** (BR-MET-121). The import-time
   `days_threshold` verdict is a WARNING judged against tenant bounds that are
   monthly-shaped (seeded 25–35 / 20–45). The run knows something the import
   does not: WHICH CYCLE is being billed. So where the cycle's own expected
   span (metering's `cycle_expected_span_days`, derived from its frequency)
   sits INSIDE the tenant's flag bounds, those bounds were built for this
   cycle and the stored verdict governs; where it sits OUTSIDE them (a
   quarterly cycle against monthly bounds), the bounds do not describe this
   cycle and the run compares the span each read prices against the cycle's
   own span — a FACT, not a threshold, which is why BR-MET-121 can say "a
   quarterly cycle therefore needs no special bounds". Nothing numeric is
   minted here. ⚠ REPORTED residue: a signed tolerance for near-miss spans on
   non-monthly cycles does not exist, so on those cycles a one-day jitter row
   appears with its figures and a human clicks (or bulk-applies) bill-as-is.

3. **Suggestions are chips, never selections** (PO 2026-08-26, reaffirming
   BR-BIL-015/061). `suggested` is served ONLY where a signed rule points one
   way — BR-MET-027's forced field visit after two consecutive estimates,
   BR-MET-121's own prorate/wait pairing, BR-BIL-006's true-up-on-this-bill —
   and the screen renders it as a visible "Suggested:" chip beside an
   undecided row. No row is ever born decided; every disposition records its
   actor through `decisions.record_decision`.

THE MONEY (true-up), AND ITS EXACT EXTENT. WE-13 ❄ is the signed mechanics:
*"true-up qty 95−42 = 53 ccf billed Aug at Aug rates = $60.95. Register
arithmetic — no reversal of the July bill."* The committed actual read's
stored consumption IS the trued-up quantity (metering's `_post_row` applies
BR-MET-029 at commit and `trues_up_read_ids` names the estimates corrected),
so the ordinary pipeline pricing this run's readings IS the money
application — idempotent because stage 6 replaces drafts (BR-BIL-023), audited
because issue audits (rule 7), one money path (BR-SHL-023). What this module
adds is the STATED WORTH on the row: the usage line(s) rating's own
`price_period` emits for the trued quantity at the run's service date. The
figure comes from the engine's lines and nowhere else; a refusal serves the
quantity with the refusal named, never a guessed amount.
⚠ NAMED BOUNDARY, not built: issuing a STANDALONE CREDIT from a run decision.
No signed rule routes a true-up through a credit note (WE-13 forbids reversal;
the correction machinery corrects issued invoices), so the offered choices are
`apply_next_bill` and `hold` — and an over-estimated lineage whose trued
quantity is NEGATIVE will surface as a pricing break with rating's own
refusal, which is honest and REPORTED rather than papered over.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.billing import decisions, gather, rating_seam
from apps.billing.contracts import AccountBillingData

#: The case names this module raises — `models.DECISION_CASES` values, and the
#: S31.3 tab ids (one vocabulary end to end, like the finding tabs).
CASE_ESTIMATED = "estimated_read"
CASE_HIGH = "high_usage"
CASE_LOW = "low_usage"
CASE_DAYS = "days_threshold"
CASE_FACTOR = "meter_factor"
CASE_REPLACEMENT = "replacement"
CASE_TRUE_UP = "true_up"

READ_ANALYSIS_CASES: tuple[str, ...] = (
    CASE_ESTIMATED,
    CASE_HIGH,
    CASE_LOW,
    CASE_DAYS,
    CASE_FACTOR,
    CASE_REPLACEMENT,
    CASE_TRUE_UP,
)

#: How the days row was judged — served on the row so the screen (and an
#: auditor) can see WHICH law produced the flag. Two values, per the module
#: docstring's posture 2.
JUDGED_BY_TENANT_BOUNDS = "tenant_bounds"
JUDGED_BY_CYCLE_SPAN = "cycle_span"


@dataclass(frozen=True)
class AnalysisResult:
    """What `analysis_rows` answers: the case rows, and the seams it could not
    reach — each gap NAMED, because "no rows" and "could not look" are
    different facts and only one of them is safe to read as good news
    (the `_dispute_hold_for` posture, one surface later)."""

    rows: tuple[dict[str, Any], ...] = ()
    gaps: tuple[dict[str, str], ...] = ()


def _decimal(value: Any) -> Decimal | None:
    """A seam string back to Decimal, or None. Never a float (rule 2)."""
    return None if value in (None, "") else Decimal(str(value))


def _outcome(read: dict[str, Any], rule: str) -> dict[str, Any] | None:
    """The STORED outcome for one rule on one read (BR-MET-022 self-describing
    shape: {rule, severity, detail}). None when the engine never stored one."""
    for entry in read.get("rule_outcomes") or ():
        if entry.get("rule") == rule:
            return entry
    return None


def _priced_read(reads: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The head the PRICING seam would use — the LATEST in the period, and only
    when the run can actually bill it.

    `read_analysis_for_unit` serves heads oldest-first on the same
    total-measuring registers `billing_reads_for_unit` prices from, so the last
    entry is the read whose figures reach the bill. The analysis judges THAT
    read; an earlier re-read superseded-in-effect by a later one is not the
    number being billed.

    ⚠ **AND AN UNBILLABLE LATEST HEAD MEANS THERE IS NO PRICED READ (DEF-790).**
    Group-rule flags now travel onto the committed read, so a TOU meter whose
    windows do not sum commits with `status='tou_sum_sanity'` and sits in
    metering's `UNBILLABLE_READ_STATUSES`. The pricing seam takes the latest
    head — it does NOT fall back to an earlier billable one — finds it
    unbillable and reports `READ_ABSENT_FLAGGED`, which the run raises as its
    `missing_read` case with BR-BIL-015's three choices. That read therefore
    already has a surface and an owner, and offering `bill_as_is` on a second
    surface would record a decision the run cannot honour: the clerk chooses,
    the account still does not bill, and the audit trail says a human picked
    something the machine ignored. `billable` is metering's own stored answer
    (hard-won law 5 — the derivation, not a second spelling of the status list).
    """
    if not reads:
        return None
    latest = reads[-1]
    return latest if latest.get("billable", True) else None


def analysis_rows(prepared: Any, *, cycle_id: Any) -> AnalysisResult:
    """The read-analysis case rows for one prepared run. READS ONLY — writes
    nothing, prices nothing except the true-up worth through rating's own
    published engine, decides nothing (every row's `chosen` starts empty).

    Walks `prepared.ready` — the accounts the run will PRICE. A blocked
    account's reads are not about to become money, and its block already names
    its problem on the findings tabs.
    """
    read_analysis = gather._resolve("metering", "read_analysis_for_unit")
    if read_analysis is None:
        return AnalysisResult(
            gaps=(
                {
                    "code": "metering_read_analysis_unpublished",
                    "detail": (
                        "metering has not published read_analysis_for_unit, so the run "
                        "cannot see the stored flags on this period's reads. The seven "
                        "read-analysis categories are not served — which is stated here "
                        "rather than rendered as seven clean tabs, because 'nothing "
                        "flagged' and 'could not look' are different facts."
                    ),
                },
            )
        )

    expected_days, span_gap = _expected_span(cycle_id, prepared.period_start)
    gaps: list[dict[str, str]] = [span_gap] if span_gap is not None else []
    rows: list[dict[str, Any]] = []

    coverage: dict[str, tuple[str, ...]] = getattr(prepared, "coverage", {}) or {}
    for data in prepared.ready:
        seen: set[str] = set()
        # The units this account's ONE bill covers — resolved by prepare_run's
        # own loop (BR-CUS-068 / DEF-571 discipline) and carried on the run.
        for unit_id in coverage.get(data.account_id, ()):
            try:
                service_rows = read_analysis(
                    unit_id,
                    period_start=prepared.period_start,
                    period_end=prepared.period_end,
                    service_codes=(
                        list(prepared.scope_services)
                        if prepared.scope_services is not None
                        else None
                    ),
                )
            except Exception:  # noqa: BLE001 — one unreadable unit must not hide the run
                gaps.append(
                    {
                        "code": "read_analysis_unavailable_for_unit",
                        "detail": f"metering could not answer the read analysis for unit {unit_id}.",
                    }
                )
                continue
            for service_row in service_rows:
                code = service_row.get("service_code")
                if not code or code in seen:
                    # Anchor-first dedupe, the `readings_for_account` discipline:
                    # a BR-CUS-068 master account meets each service once.
                    continue
                seen.add(code)
                rows.extend(
                    _rows_for_service(
                        data,
                        service_row,
                        expected_days=expected_days,
                        service_date=prepared.service_date,
                    )
                )

    return AnalysisResult(rows=tuple(rows), gaps=tuple(gaps))


def _expected_span(cycle_id: Any, period_start: Any) -> tuple[int | None, dict[str, str] | None]:
    """The cycle's own expected span (BR-MET-121), or None WITH the gap named."""
    expected_for = gather._resolve("metering", "cycle_expected_span_days")
    if expected_for is None:
        return None, {
            "code": "cycle_expected_span_unpublished",
            "detail": (
                "metering has not published cycle_expected_span_days, so the Days tab "
                "falls back to each read's stored tenant-bounds verdict and says so "
                "per row (BR-MET-121's run-level judgment needs the cycle's own span)."
            ),
        }
    try:
        return expected_for(cycle_id, period_start=period_start), None
    except Exception:  # noqa: BLE001 — an unanswerable cycle is a named gap, not a crash
        return None, {
            "code": "cycle_expected_span_unavailable",
            "detail": f"metering could not answer the expected span for cycle {cycle_id}.",
        }


def _rows_for_service(
    data: AccountBillingData,
    service_row: dict[str, Any],
    *,
    expected_days: int | None,
    service_date: Any,
) -> list[dict[str, Any]]:
    reads = list(service_row.get("reads") or ())
    if not reads:
        return []
    out: list[dict[str, Any]] = []
    priced = _priced_read(reads)

    estimated = _estimated_row(data, service_row, reads)
    if estimated is not None:
        out.append(estimated)
    for case, rule in ((CASE_HIGH, "high"), (CASE_LOW, "low")):
        row = _stored_flag_row(data, service_row, priced, case=case, rule=rule)
        if row is not None:
            out.append(row)
    days = _days_row(data, service_row, priced, expected_days=expected_days)
    if days is not None:
        out.append(days)
    factor = _factor_row(data, service_row, priced)
    if factor is not None:
        out.append(factor)
    replacement = _replacement_row(data, service_row, reads)
    if replacement is not None:
        out.append(replacement)
    true_up = _true_up_row(data, service_row, reads, service_date=service_date)
    if true_up is not None:
        out.append(true_up)
    return out


def _base_row(data: AccountBillingData, service_row: dict[str, Any], case: str) -> dict[str, Any]:
    """The S31.3 case-row envelope every category shares. `chosen` is joined by
    the selector against recorded decisions; it is ABSENT here so this module
    cannot even accidentally serve a row born decided."""
    service_id = service_row.get("service_id")
    return {
        "id": decisions.case_row_id(case, data.account_id, service_id),
        "case": case,
        "account_id": data.account_id,
        "account_no": data.account_no,
        "customer_name": None,
        "service_code": service_row.get("service_code"),
        "service_id": service_id,
        "choices": list(decisions.CHOICES_BY_CASE.get(case, ())),
        "amount": None,
        "currency": None,
        "quantity": None,
        "unit": None,
        "suggested": None,
        "facts": {},
    }


def _estimated_row(
    data: AccountBillingData, service_row: dict[str, Any], reads: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Task 1 — accounts whose period reads include ESTIMATES (BR-MET-026..028).

    The row is about the LATEST estimated head — the figure that would bill.
    `consecutive_estimate_no` is the stored counter US-MET-014 keeps;
    BR-MET-027's law is *"max 2 consecutive estimates then forced field
    visit"*, which is the ONE signed rule that produces a suggestion here: at
    two or more, `replace_with_actual` (the field-visit path) is suggested —
    as a chip, never a selection.
    """
    # DEF-790: `estimated` and the unbillable statuses are different columns'
    # answers and BR-MET-021 gives one primary status per read, so this filter
    # is belt-and-braces — an estimate the run cannot bill is the `missing_read`
    # surface's row, not a keep/replace question.
    estimates = [read for read in reads if read.get("estimated") and read.get("billable", True)]
    if not estimates:
        return None
    latest = estimates[-1]
    row = _base_row(data, service_row, CASE_ESTIMATED)
    consecutive = latest.get("consecutive_estimate_no")
    row["quantity"] = latest.get("consumption")
    row["unit"] = latest.get("unit")
    row["facts"] = {
        "meter": latest.get("meter"),
        "read_at": latest.get("read_at"),
        "estimation_method": latest.get("estimation_method"),
        "consecutive_estimate_no": consecutive,
    }
    # ⚠ r10's Estimated select draws "Keep | Override"; `replace_with_actual`
    # is the field-visit half of "Override" and the TYPED-QUANTITY half is NOT
    # offered — no signed rule lets a keystroke replace a committed read's
    # consumption mid-run, and BR-MET-029's true-up reads the register.
    # REPORTED (see the trailer).
    if consecutive is not None and int(consecutive) >= 2:
        row["suggested"] = decisions.CHOICE_REPLACE_WITH_ACTUAL
    row["detail"] = (
        f"account {data.account_no}: {service_row.get('service_code')} bills an ESTIMATE "
        f"({latest.get('consumption')} {latest.get('unit')}"
        f"{', ' + str(latest.get('estimation_method')) if latest.get('estimation_method') else ''}"
        + (f", consecutive estimate #{consecutive}" if consecutive is not None else "")
        + "). Keep it — an estimate is a lawful, labeled bill input (BR-MET-028/029) — or "
        "replace it with an actual read: the account then waits in the pending queue for "
        "the field visit / entered read, and nothing here invents a reading."
    )
    return row


def _stored_flag_row(
    data: AccountBillingData,
    service_row: dict[str, Any],
    priced: dict[str, Any] | None,
    *,
    case: str,
    rule: str,
) -> dict[str, Any] | None:
    """Tasks 2 — High and Low, rendered from the STORED outcome on the priced
    head: this month, their average, the ratio, and the threshold it was judged
    against, exactly as the engine wrote them (BR-MET-022/056). Nothing is
    recomputed; a read the engine did not flag raises no row here."""
    if priced is None:
        return None
    outcome = _outcome(priced, rule)
    if outcome is None or outcome.get("severity") != "warning":
        return None
    detail = outcome.get("detail") or {}
    row = _base_row(data, service_row, case)
    row["quantity"] = detail.get("consumption") or priced.get("consumption")
    row["unit"] = detail.get("unit") or priced.get("unit")
    row["facts"] = {
        "meter": priced.get("meter"),
        "read_at": priced.get("read_at"),
        "this_period": detail.get("consumption"),
        "trailing_average": detail.get("trailing_average"),
        "trailing_reads": detail.get("trailing_reads"),
        "ratio_pct": detail.get("ratio_pct"),
        "threshold_pct": detail.get("threshold_pct"),
        # High only (OQ-002's AND-half); absent on low, absent = not stored.
        "absolute_floor": detail.get("absolute_floor"),
        "absolute_floor_unit": detail.get("absolute_floor_unit"),
    }
    # ⚠ r10's High select also draws "Cap at 2×"; it is NOT offered. A cap is a
    # threshold (BR-MET-020: never invented here) applied as a quantity edit
    # (B4 signs no rule that rewrites a measured consumption). REPORTED.
    direction = "above" if case == CASE_HIGH else "below"
    row["detail"] = (
        f"account {data.account_no}: {service_row.get('service_code')} measured "
        f"{detail.get('consumption')} {detail.get('unit')} against a trailing average of "
        f"{detail.get('trailing_average')} {detail.get('unit')} — {detail.get('ratio_pct')}% , "
        f"{direction} the tenant's {detail.get('threshold_pct')}% threshold (stored verdict, "
        "BR-MET-020/022 — the run recomputes nothing). Bill it as it stands, or hold the "
        "account out while someone looks."
    )
    return row


def _days_row(
    data: AccountBillingData,
    service_row: dict[str, Any],
    priced: dict[str, Any] | None,
    *,
    expected_days: int | None,
) -> dict[str, Any] | None:
    """Task 3 — **BR-MET-121's home.** The run judges the SPAN IT PRICES.

    See the module docstring's posture 2 for the two-branch judgment. The row
    always carries all three figures a clerk needs — the span this read prices
    (`days_since_prior`, stored), the cycle's own expected span, and the stored
    tenant-bounds verdict — plus WHICH branch judged it (`judged_by`), so the
    audit trail can say not only what was flagged but under which law.

    The suggestion pairing is the ruling's own: a span LONGER than the cycle's
    suggests prorate-to-N-days, SHORTER suggests wait-for-next-cycle (the r10
    rows draw exactly this pair: 52 days → "Prorate to 31 days", 18 days →
    "Wait for next cycle"). Chips, never selections.
    """
    if priced is None:
        return None
    days = priced.get("days_since_prior")
    if days is None:
        # A first read has no span. BR-BIL-062's reasoning: a brand-new
        # customer's first cycle is not a days problem.
        return None
    days = int(days)
    outcome = _outcome(priced, "days_threshold")
    stored_warned = outcome is not None and outcome.get("severity") == "warning"
    stored_detail = (outcome or {}).get("detail") or {}
    flag_bounds = stored_detail.get("flag_bounds")

    bounds_fit_cycle = (
        expected_days is not None
        and isinstance(flag_bounds, (list, tuple))
        and len(flag_bounds) == 2
        and flag_bounds[0] is not None
        and flag_bounds[1] is not None
        and int(flag_bounds[0]) <= expected_days <= int(flag_bounds[1])
    )
    if expected_days is None or bounds_fit_cycle:
        judged_by = JUDGED_BY_TENANT_BOUNDS
        flagged = stored_warned
    else:
        judged_by = JUDGED_BY_CYCLE_SPAN
        flagged = days != expected_days
    if not flagged:
        return None

    row = _base_row(data, service_row, CASE_DAYS)
    row["quantity"] = priced.get("consumption")
    row["unit"] = priced.get("unit")
    row["facts"] = {
        "meter": priced.get("meter"),
        "read_at": priced.get("read_at"),
        "days": days,
        "expected_days": expected_days,
        "judged_by": judged_by,
        "flag_bounds": flag_bounds,
        "hard_bounds": stored_detail.get("hard_bounds"),
        "stored_severity": (outcome or {}).get("severity"),
    }
    if expected_days is not None and days > expected_days:
        row["suggested"] = decisions.CHOICE_PRORATE_TO_CYCLE_DAYS
    elif expected_days is not None and days < expected_days:
        row["suggested"] = decisions.CHOICE_WAIT_NEXT_CYCLE
    expected_text = (
        f"the cycle being billed expects {expected_days} days"
        if expected_days is not None
        else "the cycle's own expected span is unavailable, so the stored tenant-bounds "
        "verdict is shown"
    )
    row["detail"] = (
        f"account {data.account_no}: the {service_row.get('service_code')} reading prices a "
        f"span of {days} days and {expected_text} (BR-MET-121 — the bill run is the "
        "authoritative days judgment). Prorate to the cycle's days, wait for the next "
        "cycle, or bill the span as it stands — nothing is assumed."
    )
    return row


def _factor_row(
    data: AccountBillingData,
    service_row: dict[str, Any],
    priced: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Task 4 — the meter factor, confirmed by a human where it scales money.

    INCLUSION IS A FACT, NOT A THRESHOLD: every priced head whose stored
    multiplier is not ×1 appears, because a factor multiplies the whole bill
    and `factor_flag` — the VEE rule that would judge it — is UNRATIFIED
    (`validation.UNRATIFIED_RULES`: no signed threshold exists, BR-MET-020
    forbids inventing one, so the engine stores `not_evaluated`). The row shows
    the stored math the way S29 does (BR-MET-056): configured factor, raw
    register read, computed usage. `confirm_factor` records the human's ×N.
    """
    if priced is None:
        return None
    multiplier = _decimal(priced.get("multiplier"))
    if multiplier is None or multiplier == Decimal("1"):
        return None
    outcome = _outcome(priced, "factor_flag")
    row = _base_row(data, service_row, CASE_FACTOR)
    row["quantity"] = priced.get("consumption")
    row["unit"] = priced.get("unit")
    row["facts"] = {
        "meter": priced.get("meter"),
        "read_at": priced.get("read_at"),
        "multiplier": priced.get("multiplier"),
        "prior_value": priced.get("prior_value"),
        "current_value": priced.get("current_value"),
        "computed": priced.get("consumption"),
        # Honest about the rule's state: not_evaluated / threshold_not_ratified
        # where the engine stored that, absent where it stored nothing.
        "factor_rule_severity": (outcome or {}).get("severity"),
        "factor_rule_reason": ((outcome or {}).get("detail") or {}).get("reason"),
    }
    # ⚠ r10 draws a third option here — "Change to ×1" — and it is NOT offered:
    # rewriting a meter's configured multiplier is metering's write against the
    # asset, not a disposition of this run. `investigate` holds the account
    # while someone fixes the configuration, which is the same outcome without
    # the run reaching into another module's table. REPORTED (see the trailer).
    row["detail"] = (
        f"account {data.account_no}: meter {priced.get('meter')} prices through a "
        f"configured factor of ×{priced.get('multiplier')} — raw read "
        f"{priced.get('current_value')}, computed {priced.get('consumption')} "
        f"{priced.get('unit')} (stored math, BR-MET-056). Confirm the factor, or hold "
        "the account out while someone checks the meter's configuration."
    )
    return row


def _replacement_row(
    data: AccountBillingData, service_row: dict[str, Any], reads: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Task 5 — a MID-CYCLE SWAP: this period's heads sit on more than one
    asset of the same service point (assets' selector keeps retired meters for
    exactly this — *"a meter replaced mid-cycle still produced the reads that
    half the period is billed on"*).

    ⚠ **THE SWAP IS INFERRED, NOT READ.** `assets.Asset.replaced_by_asset` is
    the authoritative link and NO SEAM PUBLISHES IT — `asset_ids_for_service_
    point` answers ids, `read_analysis_for_unit` carries no replacement fact,
    and billing may not query another module's table (B2 §2). So two assets
    with heads in one period on one service point is the only signal available,
    and a service point that legitimately carries two live meters would raise
    this row too. The FIGURES are all stored and all true either way — two
    meters, their two readings, the total where the units agree — so the row
    misnames the SITUATION at worst, never the numbers. REPORTED: the fix is a
    published replacement link, which is a seam this lane may not mint.

    The segments and their total are QUANTITIES from stored consumptions —
    the chain already totals, in the sense that each segment's register
    arithmetic is done and Σ(segments) is the period's usage; no money is
    computed here. Units that disagree serve NO total (the OQ-358 posture —
    kWh and kgal are never added). ⚠ The PRICING of both segments is a named
    boundary: `billing_reads_for_unit` prices the single latest head, so the
    `prorate_both_segments` choice holds the account there (see
    `decisions.HOLDING_CHOICES`) and the gap is REPORTED, never bridged with
    invented math.
    """
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for read in reads:
        # DEF-790 again: a segment the run cannot bill is not a segment of the
        # period's usage. Summing it would state a chain total the bill will
        # never carry, and the flagged read is already answered on the
        # `missing_read` surface.
        if not read.get("billable", True):
            continue
        by_asset.setdefault(str(read.get("asset_id")), []).append(read)
    if len(by_asset) < 2:
        return None
    # Segment order = each asset's LAST head, by read time; the final asset is
    # the meter that will price (the latest head overall).
    segments = sorted(
        (entries[-1] for entries in by_asset.values()),
        key=lambda read: (read.get("read_at") or "", read.get("read_id") or ""),
    )
    units = {segment.get("unit") for segment in segments if segment.get("unit")}
    quantities = [_decimal(segment.get("consumption")) for segment in segments]
    total = (
        str(sum(quantity for quantity in quantities if quantity is not None))
        if len(units) == 1 and all(quantity is not None for quantity in quantities)
        else None
    )
    old, new = segments[0], segments[-1]
    row = _base_row(data, service_row, CASE_REPLACEMENT)
    row["quantity"] = total
    row["unit"] = next(iter(units)) if len(units) == 1 else None
    row["facts"] = {
        "old_meter": old.get("meter"),
        "old_final_quantity": old.get("consumption"),
        "old_read_at": old.get("read_at"),
        "new_meter": new.get("meter"),
        "new_start_quantity": new.get("consumption"),
        "new_read_at": new.get("read_at"),
        "segment_count": len(segments),
        "segments_total": total,
        "unit": row["unit"],
    }
    row["detail"] = (
        f"account {data.account_no}: {service_row.get('service_code')} changed meters "
        f"inside this period — {old.get('meter')} closed at {old.get('consumption')} "
        f"{old.get('unit')} ({old.get('read_at')}) and {new.get('meter')} started, reading "
        f"{new.get('consumption')} {new.get('unit')} ({new.get('read_at')}). Price both "
        "segments (the account holds at that boundary until the pricing side exists), "
        "bill the new meter's segment as the run gathers it, or hold the account out "
        "while someone looks."
    )
    return row


def _true_up_row(
    data: AccountBillingData,
    service_row: dict[str, Any],
    reads: list[dict[str, Any]],
    *,
    service_date: Any,
) -> dict[str, Any] | None:
    """Task 6 🔒 — the true-up, with its WORTH stated by rating's own engine.

    A read carrying `trues_up_read_ids` is BR-MET-029's next actual: its stored
    consumption is already the register-arithmetic result (actual span minus
    the estimates billed — the `true_up` outcome's `register_delta` and
    `estimated_total` are the working, stored at commit). Billing that read
    through this run IS the signed money application (WE-13 ❄, current-period
    rates, no reversal). This row makes the application VISIBLE and RECORDED:

      * `quantity` — the trued-up quantity that will bill (stored).
      * `amount`/`currency` — what rating's published `price_period` says the
        usage line(s) for that quantity come to at this run's service date,
        with THIS account's gathered tariff. The engine's own line amounts,
        summed server-side over its usage lines only (BR-SHL-023 — the client
        never sums; a refusal serves the quantity with the refusal named).
      * `suggested` = apply_next_bill — BR-BIL-006's own sentence ("true-up …
        at next actual, current-period rates") is the one rule that points.
    """
    # DEF-790: a trued-up read the run cannot bill states no money here. The
    # worth below is what THIS bill carries, and a flagged head carries nothing
    # — its own `missing_read` row is where a human answers for it.
    trued = [read for read in reads if read.get("trues_up_read_ids") and read.get("billable", True)]
    if not trued:
        return None
    latest = trued[-1]
    outcome_detail = (_outcome(latest, "true_up") or {}).get("detail") or {}
    row = _base_row(data, service_row, CASE_TRUE_UP)
    row["quantity"] = latest.get("consumption")
    row["unit"] = latest.get("unit")
    row["suggested"] = decisions.CHOICE_APPLY_NEXT_BILL
    row["facts"] = {
        "meter": latest.get("meter"),
        "read_at": latest.get("read_at"),
        "trued_quantity": latest.get("consumption"),
        "register_delta": outcome_detail.get("register_delta"),
        "estimated_total": outcome_detail.get("estimated_total"),
        "corrects_count": len(latest.get("trues_up_read_ids") or ()),
    }
    amount, currency, pricing_gap = _true_up_worth(data, service_row, latest, service_date)
    row["amount"] = amount
    row["currency"] = currency
    if pricing_gap is not None:
        row["facts"]["pricing_gap"] = pricing_gap
    row["detail"] = (
        f"account {data.account_no}: the {service_row.get('service_code')} reading trues up "
        f"{row['facts']['corrects_count']} estimated read(s) — the span actually measured "
        f"{outcome_detail.get('register_delta') or '—'} {latest.get('unit')}, the estimates "
        f"already billed {outcome_detail.get('estimated_total') or '—'} {latest.get('unit')}, "
        f"so THIS bill carries {latest.get('consumption')} {latest.get('unit')} at "
        "current-period rates (BR-MET-029 / WE-13 — register arithmetic, no reversal of the "
        "estimated bill). Apply it on this bill, or hold the account out."
    )
    return row


def _true_up_worth(
    data: AccountBillingData,
    service_row: dict[str, Any],
    read: dict[str, Any],
    service_date: Any,
) -> tuple[str | None, str | None, str | None]:
    """(amount, currency, gap) — the engine's answer, or None WITH the gap named.

    🔒 The one money computation in this module, and it is a CALL, not math:
    `rating_seam.price_period` with the account's gathered TariffConfig, the
    trued quantity, and the run's own period — the same inputs phase 2 prices
    with, so the stated worth and the drafted bill cannot disagree about the
    usage line. Pure, no writes, no clock (the service date is the run's).
    """
    quantity = _decimal(read.get("consumption"))
    unit = read.get("unit")
    if quantity is None or not unit:
        return None, None, "the trued-up read carries no priceable quantity"
    tariff = next(
        (entry for entry in data.tariffs if entry.service == service_row.get("service_code")),
        None,
    )
    if tariff is None:
        return (
            None,
            None,
            (
                "no gathered tariff for this service — the run's own gather already "
                "names the pricing problem on its findings"
            ),
        )
    try:
        priced = rating_seam.price_period(
            tariff=tariff,
            consumption=rating_seam.Quantity(amount=quantity, unit=unit),
            period=rating_seam.BillingPeriod(
                cycle_days=data.cycle_days,
                service_days=data.service_days,
                start=data.period_start,
                end=data.period_end,
            ),
            account=rating_seam.AccountContext(currency=data.currency, tax_exempt=data.tax_exempt),
        )
    except rating_seam.PricingRefused as refusal:
        return None, None, str(refusal)
    except NotImplementedError as absent:
        return None, None, str(absent)
    usage_lines = priced.lines_of("usage")
    if not usage_lines:
        return None, None, "the engine priced no usage line for this quantity"
    # The ENGINE's own usage lines, summed for display — never the client's
    # (BR-SHL-023), never this module's arithmetic over anything else.
    total = sum((line.amount for line in usage_lines), Decimal("0"))
    return str(total), priced.currency, None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-003@d18c07d (hash = sha256/7 of the source epic,
#         EP-BIL-01-bill-run.md, the `exceptions_dict` story this module's rows
#         ride) · CR-038 W8 (12-governance/11-change-requests.md Amendment 2 —
#         the six W8 tasks · 04-metering/02-business-rules.md BR-MET-120..129,
#         file hash a195ac8 · r10 BIL-02.2's reads tabs · decision sheet 15,
#         2026-08-26: the no-default rule stands, suggestions are chips)
# generated: 2026-08-26 by the CR-038 W8 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
#         ⚠ The marks live on ONE line because G3 reads a single
#         `checklist:` line and silently scores a wrapped one as MISSING its
#         continuation letters — this trailer failed the gate as
#         `checklist missing letters E,F,G,H` while carrying all eight.
#         D — served through the existing GET /billing/runs/{id}/exceptions
#         and POST .../{case_id}/resolve; no new route. E — the S31.3 tabs in
#         BillRunWizard.
# gates: ruff✔ black✔ · tests/test_cr038_w8_read_analysis.py
# exceptions: (1) 🔒 HUMAN-REVIEW-PENDING — `_true_up_worth` prices money
#         through rating's published engine; its row belongs in
#         12-governance/09-human-review-ledger.md (the lane may not write that
#         register; the row is the session owner's).
#         (2) TWO NAMED PRICING BOUNDARIES, held rather than bridged:
#         usage-proration-to-N-days (no signed rule scales a consumption) and
#         both-segments swap pricing (the pricing seam prices one head). The
#         dispositions RECORD; `decisions.HOLDING_CHOICES` holds the account at
#         the boundary; both are REPORTED.
#         (3) The days judgment's two branches are stated in `_days_row` and in
#         the module docstring; the REPORTED residue is the missing signed
#         tolerance for near-miss spans on non-monthly cycles.
#         (4) A NEGATIVE trued-up quantity (estimates over-billed the span) is
#         not specially handled: it prices — or refuses — through the same
#         engine as phase 2, and B5 gives no worked figure for the negative
#         direction, so nothing here asserts one (GT-9's own posture).
#         (5) THE REPLACEMENT ROW INFERS the swap from two assets holding
#         heads in one period, because `assets.Asset.replaced_by_asset` reaches
#         no seam. See `_replacement_row` — the figures are stored either way;
#         only the WORD "changed meters" is an inference. REPORTED.
#         (6) THREE r10 DISPOSITIONS ARE NOT OFFERED, and each is a rule that
#         does not exist rather than a screen that forgot. r10 BIL-02.2 draws
#         them in its `Fix` selects; the S31.3 tables draw everything else it
#         does. **Estimated · "Override"** — a clerk-typed replacement quantity
#         for an estimate. The machinery exists (`record_decision` takes an
#         `amount`+`unit` for BR-BIL-015's `estimate`), but no signed rule says
#         a typed number may replace a COMMITTED read's consumption mid-run, and
#         BR-MET-029's true-up assumes the register, not a keystroke.
#         **High · "Cap at 2×"** — capping a measured quantity at a multiple of
#         the trailing average. That is a threshold AND a quantity edit;
#         BR-MET-020 forbids inventing the first and B4 signs no rule for the
#         second. **Meter factor · "Change to ×1"** — rewriting the meter's
#         configured multiplier, which is a METERING write (the asset's
#         configuration), not a bill-run disposition; the run's honest move is
#         `investigate`, which holds the account while someone fixes the meter.
#         All three are REPORTED for the PO, not silently dropped and not
#         invented here.
#         (7) DEF-790's carried group-rule flags: an UNBILLABLE head (now
#         including `tou_sum_sanity`) raises NO analysis row in any of the seven
#         cases. The pricing seam refuses it, the run already raises its
#         `missing_read` case for it, and a second surface would record a
#         disposition the run cannot honour. TC-14 pins it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
