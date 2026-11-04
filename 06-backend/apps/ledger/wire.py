# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (S36 Revenue & AR on the wire) · US-LED-008 (S56 trial
#           balance on the wire) · US-LED-009 (S59 account ledger) ·
#           US-LED-010 (S60 by-premises) · US-LED-013 (S56 journal list) ·
#           US-LED-014 (S41 dual-basis remittance)
#           Screens: S36 · S41 · S56 · S59 · S60
# Rules:    CLAUDE.md rule 2 (money is NUMERIC(18,6) + CHAR(3) and never a
#           float — on the wire it is the exact decimal STRING beside its
#           currency) · BR-REP-001 (every money group labels its date basis) ·
#           BR-REP-002 (a read-model figure is Σ over journal-line dimensions;
#           this file re-derives NOTHING) · BR-LED-016 (the S36 strip) ·
#           BR-LED-009 (the trial balance) · BR-LED-010 (the account ledger) ·
#           BR-LED-011 (by-premises) · BR-LED-012 (the journal list) ·
#           BR-LED-013 (remittance: billed · collected · remitted ·
#           outstanding) · BR-TEN-022 (periods are COMPUTED from fiscal
#           settings and never stored — which is why `written_off_ytd` has a
#           window the CALLER states)
# Tests:    06-backend/tests/test_us_led_ledger_api.py
# Impacts:  apps/ledger/api.py + apps/reports/api.py (the only two callers) ·
#           06-backend/openapi/schema.json (this file decides the response
#           shapes the committed snapshot records — BE-11 TC05)
# ───────────────────────────────────────────────────────
"""`apps/ledger/reporting.py`'s results, as JSON — and NOTHING else.

THIS FILE DOES NO ARITHMETIC. It contains no `+`, no `-`, no ratio and no
comparison of one money value with another. Every figure it emits arrived from
`apps.ledger.reporting`, which is the ONE derivation of every number a finance
screen shows (BR-REP-002), is on the G7 human-owned list, and is not this
lane's to move. What happens here is narrower and entirely mechanical:

  * a `Decimal` becomes its exact decimal STRING at the column's six places
    (CLAUDE.md rule 2 — money is never a float and never a JSON number, and
    `apps/billing/selectors._decimal_str` is the precedent this copies);
  * a `date` / `datetime` becomes ISO-8601;
  * a frozen dataclass row becomes a dict under its own field names;
  * a gap tuple becomes a list of objects a screen can render.

**WHY A SEPARATE MODULE RATHER THAN CODE IN `api.py`.** Two endpoint files
serve these read models — `apps/ledger/api.py` (S36 · S41 · S56) and
`apps/reports/api.py` (S59 · S60, through `GET /reports/{key}`, because the
ledger owns those two report STORIES while the reports module owns the report
CENTRE they are viewed in; 04-docs/05-modules/12-reports/01-overview.md settles
that split). Two copies of "how a Decimal reaches the wire" is DEF-014's shape:
they agree the day they are written and disagree the first time one is fixed.

════════════════════════════════════════════════════════════════════════════
A `None` FIGURE STAYS `None`, AND ITS REASON TRAVELS WITH IT
════════════════════════════════════════════════════════════════════════════
`reporting.py` returns four named figures as `None` on purpose — the collection
percentage (BR-REP-009 needs payments' period attribution), DSO (BR-REP-011
needs twelve months a young tenant does not have), the aging buckets (a journal
line carries no due date) and the collected tax basis (an allocation carries no
line class — OQ-129). Each one is `None` beside an `unavailable` entry naming
the code, the rule and, where a neighbouring module would have to publish a
read, that read in full.

**Nothing here substitutes a number for one of them**, and nothing here drops
the reason on the way out. `collection_pct: null` with no explanation is a
screen that looks broken; `collection_pct: 80.62` would be a DIFFERENT ratio
wearing the ruled one's name. The pair — the null and the reason — is the whole
contract, so `unavailable` is serialized on every result that carries one.

════════════════════════════════════════════════════════════════════════════
CURRENCY — DERIVED FROM THE BOOKS SINCE 2026-08-15 (DEF-081)
════════════════════════════════════════════════════════════════════════════
This section used to say *"WHERE THE CHAR(3) COMES FROM, SINCE THE READ MODEL
PUBLISHES NONE"*, and it went on: *"That is a label, not a derivation … a
caller may post USD and CAD into one tenant's books, and `reporting.py` would
sum them without noticing. Nothing in this lane can see that happen. REPORTED
as a defect candidate."* The report became **DEF-081** and the defect is fixed.
The paragraph is kept in the past tense rather than deleted, because a file that
quietly stops describing its own former hole is hard-won law 1 inside a money
path.

What is true now, and both halves live in `reporting.py`:

  * **no Σ crosses two currencies.** Every summing read asks `_one_currency`
    over exactly the lines it is about to add and REFUSES (`MixedCurrencyBook`,
    catalog `BIZ-STATE` → 409) when they disagree, so a mixed total cannot
    reach this file to be labelled at all;
  * **every result publishes its own `currency`**, derived from the entries
    summed. `apps/ledger/api._currency_of` passes THAT in, falling back to the
    tenant's declared code only when the window posted nothing — a 0.00 is the
    same 0.00 in any currency, so the fallback cannot mislabel a real figure.

A journal-entry row is the exact case rather than the derived one: an entry
carries a single CHAR(3), so the row serves its own.

This file still touches no ORM: the code is passed IN by the endpoint, as it
always was. What changed is where the endpoint got it.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: The storage precision of `NUMERIC(18,6)` (DB-3), NOT a money rounding.
#: B4's rounding law is half-up to 2dp at finalization/display and lives in
#: `core/money.py`; quantizing here would be a second rounding site in a money
#: path, so this only pins the string form of what is already stored.
SIX_PLACES = Decimal("0.000001")


def money(value: Decimal | None) -> str | None:
    """A NUMERIC(18,6) value as its exact decimal STRING ("247.870000").

    `None` in, `None` out — and that is load-bearing rather than defensive.
    Every `None` reaching this function is one of `reporting.py`'s four named
    unavailable figures, and turning one into "0.000000" would put a confident
    zero where a finance officer needs to read "the books cannot say".
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_UP))


def day(value: Any) -> str | None:
    """An ISO calendar date, or None. Dates are the BOOK date (BR-REP-001's
    posting basis) everywhere in this module's inputs."""
    return None if value is None else value.isoformat()


def moment(value: Any) -> str | None:
    """An ISO timestamp, or None — `journal_entries.posted_at`, the wall-clock
    moment, which is deliberately never the period filter (see
    `reporting._posted_lines`)."""
    return None if value is None else value.isoformat()


def gap(entry: dict[str, Any]) -> dict[str, Any]:
    """One `unavailable` entry — the shape `apps/billing/posting_seam.py`
    established and `reporting.py` reuses: a machine `code`, the `br_ref` it
    comes from, the `detail` in prose a person can act on, and `wanted_reads`
    naming the read that would close it BY NAME so the day it exists the gap
    closes with no edit on either side.

    `wanted_reads` becomes a list because a JSON tuple is a list. A screen that
    renders only `detail` is still correct — the other three are for the next
    agent.

    ⚠ **THIS SAID *"nothing else changes, and no field is dropped"* UNTIL
    2026-09-24 AND IT DROPPED EVERY FIELD BEYOND THE FOUR IT NAMES
    (`DEF-LED-6521`).** It serialises a NAMED set, which is the right posture —
    an `unavailable[]` entry is a contract and a passthrough would let any read
    model put anything on it — but the sentence claimed the opposite, and a
    real key was lost behind it: `reporting.journal_entry_list` has carried
    `entry_ids` on its `posted_entries_without_a_je_number` gap since the gap
    was written, and **not one of those ids has ever reached a client.**
    Hard-won law 1: a comment claiming a guarantee is not the guarantee, and
    nothing here asserted it.

    **`entry_count` IS CARRIED AND `entry_ids` IS STILL NOT, DELIBERATELY.** A
    screen can state *"168 entries carry no number"* — a FACT, six words, B14
    rule 33 — and nothing renders the ids. Serving a list nothing consumes is
    hard-won law 2, and at the top of T5 that list is 40,000 UUIDs beside fifty
    rows (`NFR-3`). The ids stay on the read model for a caller that wants them,
    bounded by `reporting.GAP_ID_SAMPLE`.
    """
    served = {
        "code": entry["code"],
        "br_ref": entry["br_ref"],
        "detail": entry["detail"],
        "wanted_reads": list(entry.get("wanted_reads") or ()),
    }
    if "entry_count" in entry:
        served["entry_count"] = entry["entry_count"]
    return served


def gaps(entries: Any) -> list[dict[str, Any]]:
    return [gap(entry) for entry in (entries or ())]


def period(window: dict[str, Any] | None) -> dict[str, str | None]:
    """`{"start": …, "end": …}` as ISO dates. An open end of the window stays
    `null` — `GET /ledger/trial-balance` with no `from` means *everything the
    books have ever held up to `to`*, which is what a cumulative AR control
    needs, and a fabricated start date would misdescribe it."""
    window = window or {}
    return {"start": day(window.get("start")), "end": day(window.get("end"))}


def _row(record: Any) -> dict[str, Any]:
    """A frozen `reporting.py` dataclass as a plain dict, field for field."""
    return asdict(record) if is_dataclass(record) else dict(record)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-008 — S56 trial balance
# ═══════════════════════════════════════════════════════════════════════════
def trial_balance_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """LE-1's table and its footer, unaltered.

    `balanced` and `difference` are served EXACTLY as the read model computed
    them, including when they say the books do not foot. US-LED-008 TC-5:
    *"The screen cannot render it as balanced — discrepancy surfaces via the
    US-LED-004 red flag; no client-side 'rebalancing' exists."* An API layer
    that filtered an unbalanced period, or omitted `difference` when it was
    zero, would be that rebalancing wearing a serializer's clothes.

    ⚠ **AND `balanced` HAS A THIRD VALUE SINCE CR-060 C24: `null`.** A table
    narrowed to one property cannot foot — balance is a property of an ENTRY and
    the filter takes a subset of each entry's lines — so the read model answers
    `null` and puts the reason on `unavailable`. It is passed through untouched
    for the same reason `false` is: coercing it to `false` would report a
    posting-service bypass on a screen that is working perfectly, and coercing
    it to `true` would claim a proof nobody performed.

    Both presentations ride along, as `reporting.trial_balance` produces them:
    `debit`/`credit` are the account's NET on one side (what a trial balance
    IS, and what LE-1 prints — *"1200 AR | 152.32"*), `gross_debit`/
    `gross_credit` the un-netted sides, which are the only way to see that a
    same-account transfer wrote two rows rather than none.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "period": period(result["period"]),
        "rows": [
            {
                "account_id": row["account_id"],
                "code": row["code"],
                # CR-196-BRC10 — the code before its latest change, or None.
                "former_code": row.get("former_code"),
                "name": row["name"],
                "type": row["type"],
                "debit": money(row["debit"]),
                "credit": money(row["credit"]),
                "gross_debit": money(row["gross_debit"]),
                "gross_credit": money(row["gross_credit"]),
                # CR-060 C4 — the position either side of the movement. Both are
                # SIGNED net-debit figures, so a liability account carries a
                # negative one; `MoneyCell` renders that, and folding them onto
                # two more one-sided columns would double the table's width to
                # say the same thing.
                "opening": money(row["opening"]),
                "closing": money(row["closing"]),
            }
            for row in result["rows"]
        ],
        "total_debit": money(result["total_debit"]),
        "total_credit": money(result["total_credit"]),
        # CR-060 C4 — Σ opening + (total_debit − total_credit) = Σ closing. On a
        # balanced book both read 0.00, and that is the point of showing them:
        # a footer that did NOT come out square would mean last month did not.
        "total_opening": money(result["total_opening"]),
        "total_closing": money(result["total_closing"]),
        "difference": money(result["difference"]),
        # ⚠ CR-060 C24 — served EXACTLY as computed, `None` included. A narrowed
        # table answers `null` here, and the temptation this comment exists to
        # refuse is `result["balanced"] or False`: that would turn "this is not
        # a question we can answer" into BR-LED-007's posting-service bypass,
        # which is the same class of lie as the client-side rebalancing the
        # docstring above forbids. DEF-127 — unknown is not the negative answer.
        "balanced": result["balanced"],
        "premises_id": result.get("premises_id"),
        "unavailable": list(result.get("unavailable", ())),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-007 — S36 Revenue & AR
# ═══════════════════════════════════════════════════════════════════════════
#: The API layer's own `unavailable` entry, used when the caller did not state
#: the fiscal year the *Written off YTD* KPI is measured over. It is the ONE
#: gap this lane adds to a `reporting.py` result, and it exists because the
#: alternative is a lie: `revenue_and_ar(ytd_start=None)` sums write-offs from
#: the beginning of the books, and serving THAT under the name
#: `written_off_ytd` states a year-to-date figure that is not one.
WRITTEN_OFF_YTD_WINDOW_UNSTATED = {
    "code": "written_off_ytd_window_was_not_stated_by_the_caller",
    "br_ref": "BR-TEN-022 · BR-REP-001 · BR-LED-016",
    "detail": "the *Written off YTD* KPI needs the first day of the tenant's fiscal year, and "
    "BR-TEN-022 makes periods COMPUTED from fiscal settings and never stored — so no row in "
    "this database holds it and neither the read model nor this endpoint may guess one. "
    "Without `ytd_start`, `reporting.revenue_and_ar` sums write-offs from the beginning of "
    "the books; that number is real but it is ALL-TIME, and serving it under a year-to-date "
    "name would be a false statement about money rather than a missing one. Pass "
    "`ytd_start=YYYY-MM-DD` (S8's Regional tab holds fy_start_month / fy_start_day, "
    "GET /settings/regional) and the KPI fills in.",
    "wanted_reads": (
        "apps.tenancy.selectors.fiscal_year_start_on_or_before(day: date) -> date | None"
        "  # would let the server derive the window from BR-TEN-022 settings, "
        "with no clock (G6) and no guess",
    ),
}


def revenue_ar_dict(
    result: dict[str, Any], *, currency: str | None, ytd_window_stated: bool
) -> dict[str, Any]:
    """S36's KPI strip and panels — every figure as the books stated it.

    THE FOUR NULLS ARE THE POINT. `collection_pct`, `dso` and `aging` come out
    of the read model as `None` with their reasons already in `unavailable`,
    and they are copied straight through. US-LED-007 §7 works the ruled
    percentage to **72.49%** (401.37 ÷ 553.69) and the books can only offer
    446.37 ÷ 553.69 = **80.62%** — a different ratio, computed off a column
    that answers a different question, so it is not offered at all.

    `written_off_ytd` is the fifth, and it is this LAYER's refusal rather than
    the read model's: see `WRITTEN_OFF_YTD_WINDOW_UNSTATED`.
    """
    kpis = result["kpis"]
    unavailable = gaps(result["unavailable"])
    if not ytd_window_stated:
        unavailable.append(gap(WRITTEN_OFF_YTD_WINDOW_UNSTATED))
    return {
        "basis": result["basis"],
        "currency": currency,
        "period": period(result["period"]),
        "kpis": {
            "billed": money(kpis["billed"]),
            "collected": money(kpis["collected"]),
            "collected_from_cash": money(kpis["collected_from_cash"]),
            "collected_from_applied_deposits": money(kpis["collected_from_applied_deposits"]),
            "collection_pct": kpis["collection_pct"],
            "still_owed": money(kpis["still_owed"]),
            "accounts_owing": kpis["accounts_owing"],
            "dso": kpis["dso"],
            "written_off_ytd": (money(kpis["written_off_ytd"]) if ytd_window_stated else None),
        },
        "revenue_by_service": [
            {
                "service_id": row["service_id"],
                "service_code": row["service_code"],
                "usage": money(row["usage"]),
                "base_and_fees": money(row["base_and_fees"]),
                "total_billed": money(row["total_billed"]),
                # ⚠ DEF-176 — THESE TWO KEYS ARE THE FIX, AND THEY WERE MISSING
                # ALTOGETHER. `reporting.ServiceRevenueRow`'s docstring says
                # *"`tax` and `collected` are None with a reason on the result"*
                # and the dataclass carries no such fields, so this serializer
                # emitted a row with five members while `endpoints.ts` declared
                # seven. That is hard-won law 1 in its purest form: a comment
                # claiming a guarantee is not the guarantee.
                #
                # What it cost: S36 branches on `row.tax === null` to render the
                # column's reason instead of a figure. An ABSENT key is not
                # `null`, so the branch was false, `undefined` reached
                # `MoneyCell`, and DEF-151's refusal threw — taking the WHOLE
                # Finance route down with React Router's error boundary. A
                # column that should have read "—" killed the page.
                #
                # They are served EXPLICITLY as null rather than omitted, because
                # the two facts are different: *"the books cannot split this"* is
                # a statement (`per_service_tax_and_collected_columns` on
                # `unavailable` says why), and *"this endpoint forgot"* is not.
                # BR-LED-002's remittance table sets the precedent directly —
                # *"the COLUMN IS STILL SERVED, as null"*.
                "tax": None,
                "collected": None,
            }
            for row in (_row(record) for record in result["revenue_by_service"])
        ],
        "aging": result["aging"],
        "cash": cash_dict(result["cash"], currency=currency),
        "adjustments": adjustments_dict(result["adjustments"], currency=currency),
        "tie_out": {
            "ar_control": money(result["tie_out"]["ar_control"]),
            "computed_by": result["tie_out"]["computed_by"],
        },
        "unavailable": unavailable,
    }


def cash_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """Realised and undeposited cash, as two members with NO third adding them.

    PO ruling 2026-08-11 closing OQ-143, verbatim: *"Cash is received but
    undeposted in such case payment will say csah but ledger will say
    undeposited - until bank record and reconcilaition confirm it it is not
    realised."* The read model returns the ruling's own sentence in `note`; it
    is carried to the wire so the screen renders the reason rather than
    restating it, and so a client cannot quietly add 150.00 + 292.87 back into
    LE-1's old single "1000 Cash 442.87" row.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "realised": money(result["realised"]),
        "undeposited": money(result["undeposited"]),
        "note": result["note"],
    }


def adjustments_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """S36's *Adjustments & credits* panel.

    `late_fees_applied` and `pending_approval` are `None` from the read model —
    4200 Late-fee revenue carries no designation (the PO ruled ELEVEN and
    reserved nothing, OQ-110) and a pending adjustment has not reached the
    books at all. Both stay null with their reasons in `unavailable`.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "credits_issued": money(result["credits_issued"]),
        "debits_posted": money(result["debits_posted"]),
        "late_fees_applied": money(result["late_fees_applied"]),
        "net": money(result["net"]),
        "pending_approval": result["pending_approval"],
        "unavailable": gaps(result["unavailable"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-014 — S41 dual-basis remittance
# ═══════════════════════════════════════════════════════════════════════════
def remittance_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """BR-LED-013's four columns per authority, with the fourth honestly empty.

    ⚠ **`collected` AND `outstanding_collected` CARRY FIGURES SINCE 2026-09-02**
    (CR-060 C19 / task T7d). This paragraph read *"are `None` on every row and
    on the totals, because BR-LED-002's collected basis is tax inside cleared
    payments via allocation and an `allocations` row carries no line class
    (OQ-129)"*, and that was true for as long as it was true.
    `allocation_classes` (payments/0015) records what every payment met inside
    every bill, so the column is produced — and BR-LED-794 splits one bill's
    collected tax across the authorities THAT BILL charged, in proportion to
    what each was billed on it.

    They are still `None` — never 0.00 — when payments publishes no such read at
    all, which is the old behaviour kept as the honest fallback. **The COLUMN IS
    SERVED EITHER WAY.** BR-LED-002 says BOTH bases are always computed, and
    dropping the key would let a screen render a single-basis table that
    satisfies no rule and looks finished — the exact thing the A1 addendum
    retired the prototype's collected-only table for.

    **`allocated_without_breakdown` IS THE FLOOR, IN MONEY**, and it is on the
    totals rather than in a caveat: allocations written before 2026-09-02 carry
    no breakdown and cannot be backfilled (it lived only in the pruned audit
    payload), and a credit application or release never runs the class walk. A
    return filed on the collected column UNDER-remits by at most that figure.

    `remitting_basis` is null per authority for the same class of reason: r13
    #3 places the setting on `tax_remittances`, that table does not exist, and
    LE-3 has State on COLLECTED while County is on BILLED — so a default would
    be wrong for one of them in the first month it ran.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "period": period(result["period"]),
        "rows": [
            {
                "account_id": row["account_id"],
                "code": row["code"],
                "name": row["name"],
                "billed": money(row["billed"]),
                "collected": money(row["collected"]),
                "remitted": money(row["remitted"]),
                "outstanding_billed": money(row["outstanding_billed"]),
                "outstanding_collected": money(row["outstanding_collected"]),
                "remitting_basis": row["remitting_basis"],
                "bases": list(row["bases"]),
                # ── OQ-1190, PO ruling 2026-08-31 ──────────────────────────
                # *"(a) Add a per-authority subtotal to the bill and the
                # finance screens"*. The same authority's money as the BILLS
                # charged it, split on `invoice_lines.tax_id` and named the way
                # rating names it, beside the books' own account-keyed figure.
                # `billed_from_bills` is null — NEVER zero — when billing could
                # not answer: on a screen a return is filed from, a zero reads
                # as *"this authority is owed nothing"*.
                "authority_name": row["authority_name"],
                "billed_from_bills": money(row["billed_from_bills"]),
                "bill_line_count": row["bill_line_count"],
                "bill_count": row["bill_count"],
                "billed_delta": money(row["billed_delta"]),
                # THE VERDICT IS THE SERVER'S. `money()` writes six places, so a
                # screen testing `delta == "0.00"` would read false on every
                # agreeing row.
                "bills_agree": row["bills_agree"],
                "problems": list(row["problems"]),
            }
            for row in (_row(record) for record in result["rows"])
        ],
        "totals": {
            "billed": money(result["totals"]["billed"]),
            "collected": money(result["totals"]["collected"]),
            "remitted": money(result["totals"]["remitted"]),
            "outstanding_billed": money(result["totals"].get("outstanding_billed")),
            # OQ-1190 — null unless EVERY row carried a bill-side figure. A
            # partial sum under a column heading reads as the whole and is not.
            "billed_from_bills": money(result["totals"].get("billed_from_bills")),
            # CR-060 C19 / task T7d — the collected basis's own outstanding, and
            # the money the breakdown could not classify. `money()` serves both
            # as null when they are, which is the read's own distinction between
            # "nothing was collected" and "we cannot say".
            "outstanding_collected": money(result["totals"].get("outstanding_collected")),
            "allocated_without_breakdown": money(
                result["totals"].get("allocated_without_breakdown")
            ),
            "allocations_without_breakdown": result["totals"].get(
                "allocations_without_breakdown"
            ),
        },
        "tie_out": {"tax_payable_gl": money((result.get("tie_out") or {}).get("tax_payable_gl"))},
        "unavailable": gaps(result["unavailable"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — S56 journal-entry list
# ═══════════════════════════════════════════════════════════════════════════
def journal_entry_row(record: Any, *, currency: str | None) -> dict[str, Any]:
    """One S56 row — EP-LED-04's capability matrix, minus the two columns the
    books cannot fill.

    `je_number` is the matrix's own first column and it now has a source —
    BR-LED-021, PO 2026-08-12 (OQ-176), *"Approve a JE- series"*. It is **null
    on a draft by ruling** (*"a draft has NO number"*), so a screen renders the
    `entry_id` only until the entry posts. A POSTED row with a null number means
    the tenant has no `journal_entry` number series and the list says so in
    `unavailable` — a number is never faked. `source_mapped=False` means
    BR-REP-008's vocabulary has no word for this entry's source and the raw
    `source_type` is showing through, which is a visible defect by design:
    *nothing invisible*.

    BOTH reversal links travel. r13 #2 gives the pair two, and US-LED-013 TC-2
    renders both directions — JE-104 as *reversed*, JE-105 as *the reversal,
    linked* — so one column cannot answer both questions.

    **`currency` IS THE ENTRY'S OWN (DEF-081), and this is the one row in the
    module where that is exact rather than derived.** An entry carries a single
    CHAR(3) — a mixed-currency entry cannot balance — so a row's debit and
    credit are unambiguously in it. The `currency` PARAMETER is now only the
    fallback for a row that somehow carries none, and it is what makes this list
    the surface on which a mixed book (which every Σ in `reporting.py` refuses)
    can actually be diagnosed: the foreign entries are visible, by code, in the
    list a finance officer is sent to.
    """
    row = _row(record)
    return {
        "entry_id": row["entry_id"],
        "je_number": row["number"],
        "entry_date": day(row["entry_date"]),
        "type": row["type"],
        "status": row["status"],
        "memo": row["memo"],
        "source_type": row["source_type"],
        "source_label": row["source_label"],
        "source_mapped": row["source_mapped"],
        # Record links (PO 2026-10-19): the record the entry was posted from,
        # beside `source_type`, so the Source cell can open a bill, payment or
        # refund. An address ingredient only — never printed (B14 rule 31).
        "source_id": row.get("source_id"),
        "currency": row.get("currency") or currency,
        "debit": money(row["debit"]),
        "credit": money(row["credit"]),
        "balanced": row["balanced"],
        "reversal_of_entry_id": row["reversal_of_entry_id"],
        "reversed_by_entry_id": row["reversed_by_entry_id"],
        "auto_reverse_entry_id": row["auto_reverse_entry_id"],
        "posted_at": moment(row["posted_at"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# S56's DETAIL — one entry, its lines, and that the two sides agree
# ═══════════════════════════════════════════════════════════════════════════
def journal_line_row(record: Any) -> dict[str, Any]:
    """One line, with BR-LED-001's five dimensions as (id, label) pairs.

    ⚠ **EVERY DIMENSION CARRIES BOTH, AND THE SCREEN RENDERS THE LABEL** —
    B14 rule 31, *no database id is ever the visible value of a field*. The id
    is here so a screen can LINK on it, never so it can print it; the sibling
    defect `DET-LED-6661` is a UUID that reached a memo exactly this way.

    **A LABEL OF `null` WITH AN ID SET IS NOT THE SAME AS AN ABSENT
    DIMENSION.** The first is a name this product could not read; the second is
    a dimension the line does not carry — `service` is meaningless on a cash
    line and BR-LED-001 requires each one only *where it applies*. Two distinct
    facts, two distinct shapes on the wire.

    `debit` and `credit` are two keys and never one signed amount, the same
    discipline `account_ledger_dict` keeps and the same one `journal_lines.side`
    enforces in the database: there is exactly one way to express a credit.
    Money is a decimal STRING to 2 places (CLAUDE.md rule 2), never a float.
    """
    row = _row(record)
    is_debit = row["side"] == "debit"
    return {
        "line_id": row["line_id"],
        "account_code": row["account_code"],
        "account_name": row["account_name"],
        "side": row["side"],
        "debit": money(row["amount"]) if is_debit else None,
        "credit": None if is_debit else money(row["amount"]),
        "service": _dimension(row["service_id"], row["service_label"]),
        "account": _dimension(row["account_id"], row["account_label"]),
        "premises": _dimension(row["premises_id"], row["premises_label"]),
        "unit": _dimension(row["unit_id"], row["unit_label"]),
        "tax_authority": _dimension(row["tax_authority_id"], row["tax_authority_label"]),
    }


def _dimension(value: Any, label: Any) -> dict[str, Any] | None:
    """`null` when the line does not carry this dimension at all.

    `{"id": …, "label": null}` when it carries one this product could not name.
    A screen must be able to tell those apart: the first is lawful and
    ordinary, the second is something to look into.
    """
    if not value:
        return None
    return {"id": str(value), "label": label}


def journal_entry_detail_dict(
    result: dict[str, Any], *, currency: str | None
) -> dict[str, Any]:
    """11b §2.10 `GET /ledger/journal-entries/{id}` — the body.

    The header reuses `journal_entry_row` exactly, so the detail and the list
    cannot drift into describing one entry two ways — including `je_number`,
    which is **null on an opening balance, on a draft and on a posted entry
    whose tenant has no series row**. Nothing composes a number here; hard rule
    4 means an invented one could never be withdrawn.

    `debit`, `credit` and `balanced` on the header are over the WHOLE entry and
    not over the page of lines beside them — see `reporting.journal_entry_detail`
    for why that distinction is the one this body cannot get wrong.

    **There is no write of any kind on this shape.** No version token, no
    `updated_at`, no editable field: a posted entry is immutable for ever and
    the one correction is reverse + repost, which writes two new entries.
    """
    return {
        "entry": journal_entry_row(result["entry"], currency=currency),
        "lines": [journal_line_row(record) for record in result["lines"]],
        "line_total": result["line_total"],
        "unavailable": gaps(result["unavailable"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-009 — S59 account ledger
# ═══════════════════════════════════════════════════════════════════════════
def account_ledger_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """US-LED-009's dated rows, running balance and footer.

    `charge` and `payment` are two columns and never one signed amount — the
    discipline `journal_lines.side` enforces, carried to the wire so a reader
    never has to work out what a minus sign meant. The running balance is the
    story's own formula (`r_n = r_{n−1} + charge_n − payment_n`), computed once
    in the read model and copied here.

    `vocabulary` rides along because BR-REP-006 says a filter enumerates the
    LIVE vocabulary and never a hardcoded list: the S59 Type column and any
    Type filter read the same ten words the report was built from.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "account_id": result["account_id"],
        "period": period(result["period"]),
        "opening_balance": money(result["opening_balance"]),
        "rows": [
            {
                "entry_date": day(row["entry_date"]),
                "type": row["type"],
                "type_mapped": row["type_mapped"],
                "reference": row["reference"],
                "description": row["description"],
                "charge": money(row["charge"]),
                "payment": money(row["payment"]),
                "running_balance": money(row["running_balance"]),
                "entry_id": row["entry_id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
            }
            for row in (_row(record) for record in result["rows"])
        ],
        "totals": {
            "charges": money(result["totals"]["charges"]),
            "payments": money(result["totals"]["payments"]),
            "closing_balance": money(result["totals"]["closing_balance"]),
        },
        "vocabulary": list(result.get("vocabulary") or ()),
        "unavailable": gaps(result["unavailable"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-010 — S60 by-premises summary
# ═══════════════════════════════════════════════════════════════════════════
def by_premises_dict(result: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """US-LED-010 — LE-6's rows, since the dimension landed on 2026-08-16.

    ⚠ **THIS DOCSTRING USED TO SAY THE REPORT COULD NOT BE BUILT** (*"`available`
    is `false` and `rows` is empty because `premises_id` is NULL on every
    journal line"*). US-LED-002 stamps the chain at posting now, so the rows are
    real: **500 Main St 247.87 · Oak Grove 16.42 · Marina Bay 289.40**. The
    refusal path is NOT deleted — a period whose entries predate the dimension
    still answers `available:false` with the money it cannot attribute, and that
    is the only shape a screen may render an empty table from.

    Three columns are served NULL/empty on purpose rather than computed here.
    `units` and `services` per premises are metering's facts and no report
    endpoint publishes them; `collection_pct` has the same numerator problem as
    the S36 KPI (BR-REP-009 needs which bill the cash met, which the books do
    not hold). The S60 table renders a dash for each, which is what an absent
    figure looks like — never `collected ÷ billed` computed on the way out,
    which would be a different ratio wearing the ruled one's name.
    """
    return {
        "basis": result["basis"],
        "currency": currency,
        "period": period(result["period"]),
        "available": result["available"],
        "rows": [
            {
                "premises_id": record.premises_id,
                "premises_name": record.name,
                "units": None,
                "services": [],
                "billed": money(record.billed),
                "collected": money(record.collected),
                "owed": money(record.owed),
                "collection_pct": None,
            }
            for record in result["rows"]
        ],
        "kpis": {
            "premises": result["kpis"]["premises"],
            "billed": money(result["kpis"]["billed"]),
            "collected": money(result["kpis"]["collected"]),
            "owed": money(result["kpis"]["owed"]),
        },
        "unattributed_billed": money(result["unattributed_billed"]),
        "unattributed_collected": money(result["unattributed_collected"]),
        "unavailable": gaps(result["unavailable"]),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e419f62 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md — US-LED-007/008/009/010 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md — US-LED-013 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md — US-LED-014 — · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.10 + the §2.10b body contract this lane WROTE; co-packets US-LED-008/009/010/013/014, same five sources)
# generated: 2026-08-11 by story-coder (W5 ledger read-API lane — the serialization half, shared by the two endpoint files so "how a Decimal reaches the wire" has one definition)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_us_led_ledger_api.py (RED-PROVED FIRST — verbatim failures in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it)
# exceptions: (1) **CLOSED 2026-08-15 (DEF-081).** This read: *"`currency` is the TENANT's declared CHAR(3) …, NOT a Σ-derived one — `reporting.py` publishes no currency … so a mixed-currency book would be summed silently by the read model; REPORTED as a defect candidate, not patched here (reporting.py is G7 human-owned)"*. It was a defect candidate and it became DEF-081. Both halves are now fixed IN `reporting.py`: every Σ REFUSES lines carrying more than one currency (`MixedCurrencyBook`, catalog BIZ-STATE → 409), and every result publishes the `currency` its figures ARE, derived from the entries summed. `apps/ledger/api._currency_of` reads that and falls back to the declared code only for a window that posted nothing. A journal-entry row carries the ENTRY's own code, which is exact · (2) `written_off_ytd` is served NULL, with a named reason, whenever the caller did not state `ytd_start` — the read model's all-time write-off total is a real number that is not a year-to-date one, and this is the only `unavailable` entry this lane ADDS to a reporting.py result · (3) this module does no arithmetic at all: no figure is combined, netted, rounded to 2dp or compared with another, so a money bug cannot originate here — the quantize is the COLUMN's six places (DB-3), never B4's finalization rounding
# amended:   2026-08-15 by story-coder (DEF-112 lane) — NO CODE CHANGED. The checklist claimed `E=deferred(no-frontend-half — features/ledger and .../reports are a README each)`; both directories hold screens now (S36 · S41 · S56 · S59 · S60), and every serializer in this file has a rendering caller. `apps/ledger/finance_api.py` reuses `money`, `day`, `moment`, `gaps` and `remittance_dict` from here rather than minting a second way for a Decimal to reach the wire.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
