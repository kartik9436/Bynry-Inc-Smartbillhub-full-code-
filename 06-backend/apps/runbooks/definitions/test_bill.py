# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-004 (EP-RBS-02) — CR-075 wave F task F2: runbook 23, the
#           Test bill. Screens: RBS-004-R23 (drawn, figure 43) ·
#           RBS-006-R23 (NOT drawn in the source — composed in task F1)
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports — no bill number is
#           consumed because there is no writer to consume one) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read — here, every LINE of the bill) · BR-RBS-011 (a refusal names
#           its fix route) · BR-RBS-013 (no action may edit an issued invoice)
#           · BR-RBS-019 · BR-RBS-021 (twelve blocks, closed) · BR-RBS-023
#           · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money 4
#           stored / 2 displayed) · hard rule 3 (a consumption carries its unit)
#           · hard rule 4 (financial immutability) · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_004_test_bill.py ·
#           06-backend/tests/test_us_rbs_004_pg.py (TC-RBS-004.3 and TC-RBS-7
#           on real PostgreSQL — SKIPPED, never passed, on SQLite)
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/billing_seam.py · seams/rating_seam.py ·
#           apps/billing/runs.py (`price_account`, extracted for this) ·
#           apps/billing/midperiod.py (`price_split_account`, the same)
# ───────────────────────────────────────────────────────
"""Runbook 23 — **Test bill**: price one account and write nothing.

*"As a billing clerk, and as an implementer before go-live, I want to price one
account exactly as the bill run would and see every line explained — so that I
can answer 'what would this customer's bill be' without issuing anything."*

Four steps, all READ:

    1  load the account, unit, plan and reads as the bill run would see them
    2  price through the REAL ENGINE — the same code path as the run
    3  explain every line: base, each block, taxes, fees, prorations, in words
    4  compare with the last issued bill, line by line, difference per line

It produces **either** a complete priced bill with every line explained **or ONE
refusal sentence naming the service and the date.** No bill number is consumed
and nothing is written.

═════════════════════════════════════════════════════════════════════════════
STEP 2 IS THE WHOLE STORY, AND IT IS NOW TRUE BY CONSTRUCTION RATHER THAN BY
ASSERTION
═════════════════════════════════════════════════════════════════════════════
`US-RBS-004` states the danger in its own words: *"A test bill that
re-implements pricing is worse than no test bill: it would be green while the
real run refused, and the utility would go live on a demonstration that proved
nothing."*

Before this wave the only way to get from an ACCOUNT to a PRICED LINE was
`billing.runs.calculate_account`, which ends in stage 6 — a draft invoice, a
consumed bill number (`BR-BIL-063`) and a row a Check may not write. So wave F
**extracted the pure half** into `billing.runs.price_account`, and
`calculate_account` is now literally that call followed by stage 6.
`assemble_document`'s own docstring had already drawn the line in exactly that
place — *"Stages 1–5 are pure and produce numbers. This one is where those
numbers become a row"*.

**The consequence is the point:** there is now ONE implementation of the five
pricing stages, and the difference between a test bill and a real bill is
whether stage 6 runs. `TC-RBS-004.3` still asserts the identity to four
decimals — because a test that can only fail when somebody reintroduces a
second path is exactly the test worth having, and it was first proved RED
against a deliberately planted second implementation.

⚠ **FOUR DECIMALS, NOT TWO.** Money is stored to 4 and DISPLAYED at 2 (hard
rule 2). The comparison happens on the stored `Decimal`; a comparison at two
would let a `$0.0025 / kWh` divergence hide, and the screen still shows two.

═════════════════════════════════════════════════════════════════════════════
THE JUDGMENTS THIS LANE MADE, WHICH THE DOCUMENTS DID NOT SETTLE
═════════════════════════════════════════════════════════════════════════════
The Product Owner asked for these to be surfaced rather than assumed — *"if you
have questions on Runbook you should ask instead of assuming"* — and each is
written where a reader of the CODE will meet it, not only in a report. They are
decisions, not questions: each is cheap to reverse and none of them touches a
signed figure.

**J1 · WHAT "EXPLAINED" MEANS FOR A LINE.** One sentence per line, in the
clerk's own words, built from facts the line already carries — its quantity,
its unit, its unit price — plus the tax rate for a tax line. It is NOT the
engine's own message: those quote rule ids and B14 rule 32 keeps a rule id off
a screen. Where a line carries no quantity and no rate (a flat fee), the
sentence says what KIND of charge it is rather than inventing arithmetic.

**J2 · A REFUSAL SHOWS NOTHING ELSE.** `US-RBS-004` says *"**ONE** refusal
sentence"*. So when the account cannot be priced, the report is the Sentence
block and an empty Records table with its fix route, and there is **no KPI strip
and no comparison** — not a strip of em dashes beside the stop. The services
that WOULD have priced are not listed either: the bill refused as a whole, and
half a bill is the thing this runbook exists to prevent a clerk believing.

**J3 · A ZERO-AMOUNT LINE IS DRAWN.** `$0.00` for sewer is a fact the engine
produced and a clerk asking *"why is sewer nothing this month"* is asking about
that row. Dropping it would make the bill on this screen a different bill from
the one the run produces, which breaks the runbook's only promise. It is drawn
with its explanation like any other.

**J4 · THE COMPARISON IS AN OUTER JOIN ON THE LINE'S WORDING.** `TC-RBS-004.4`
says a line present in one and not the other is SHOWN, not dropped — *"an inner
join silently hides new and removed lines"*, which are the two rows a clerk is
actually looking for. Matching is on the line's DESCRIPTION, because that is the
only key the two sides share: a priced line has no id (it was never written) and
an issued line's `service_id` is NULL on taxes and fees. Where a description
changed between the two bills the row appears twice, once on each side — that is
honest and visible, where a fuzzy match would be neither.

**J5 · A SECOND RUN IS NOT BOUNDED.** `OQ-RBS-1737` closed on 2026-09-06: the
duplicate check moved from the record to the RUN, and re-running is bounded in
time with the frequency a parameter, 24 hours its default. **A test bill is
re-run constantly by design** — that is what it is for — so it declares no
frequency bound and its *Run again* is never disabled. Nothing in the engine
bounds a re-run today in any case (no code composes a key or reads a frequency),
so this is a statement of intent for the wave that builds it, made here rather
than left for that wave to guess.

**J6 · NO `downloads` BLOCK.** The two result files stream
`runbook_run_records`, and **nothing writes a record row yet** — `close_run`
freezes the report and writes no records. A download button over an empty file
is a dead control on a live screen (hard-won law 2's 2026-09-05 mirror). The
coverage table's *"every runbook except 4, 6 and 13"* is followed everywhere it
can be honoured; runbook 4 is the closest analogue this catalogue has and
carries no download either. When a wave persists record rows this gains one.

**J7 · NO `verdict` BLOCK.** A leading verdict becomes the page head's
sub-line and the `sentence` block would then say the same thing twice, which is
the description budget B14 rule 32 exists to protect. The outcome of a test bill
is a bill or a stop, and `sentence` is the block whose stated job is *"a stop, a
find, read this aloud"*.

**J8 · THE PERIOD DEFAULTS TO THE LAST WHOLE CALENDAR MONTH.** The card says
*"A cycle, or as at a date"* and settles neither. A window parameter with no
value cannot run, so the default is the month that has ended — the period a
clerk answering *"what would this bill be"* almost always means — and it is a
parameter they can change.

**J9 · THE WINDOW CARRIES AN `as_at`, AND THE SCREEN SAYS WHICH DATE PRICED THE
RUN. THIS ONE WAS FOUND BY RUNNING IT, NOT BY READING.** `BR-RAT-007` prices on
the SERVICE DATE, and for a real cycle run **that is the bill day, not the last
day of the period**. On the seeded utility the July bills carry
`service_date = 2026-08-02` and a water rate change falls between the two dates
— `$4.00 / kgal` in force to 31 July, `$4.24` from 1 August. Re-pricing July at
the period end therefore answers **$158.10** on account `AC-2026-00001` where
the customer was billed **$160.52**, and the first run of the walkthrough
reported all twelve sampled accounts disagreeing with their own issued bills.

**Neither figure is wrong. They are two different questions**, and the whole
cost is that nothing on the screen said which one had been asked. So: the
`period` parameter accepts `as_at`, it defaults to the period end, and the KPI
strip carries a fourth tile — *Priced as at* — because a clerk who cannot see
that date cannot explain the gap and would file a defect against a bill that is
correct. The card's own scope row already said this in five words — *"A cycle,
or as at a date"* — and it took a real run to notice which half had been
built.

═════════════════════════════════════════════════════════════════════════════
WHAT THIS RUNBOOK CANNOT DO, AND WHY THAT IS THE DESIGN
═════════════════════════════════════════════════════════════════════════════
It is a **Check**, so `RunbookDefinition` refuses it at CONSTRUCTION if it ever
declares a port (`BR-RBS-002`), and `Step(writes=True)` is refused the same way.
The capability is ABSENT rather than unused: there is no writer to consume a
bill number, no path to `assemble_document`, and `TC-RBS-004.1` asserts
`billing`'s number series is untouched over a real run on real PostgreSQL.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    DOMAIN_ACCOUNT,
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    PARAM_WINDOW,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, rating_seam

# ── the four steps, by key, and the labels the setup sheet draws ──────────
#
# `RBS-004-R23` region 3 draws these four rows with this copy. The build sheet
# is the acceptance check and these strings are its words, not a paraphrase.
STEP_LOAD = "load"
STEP_PRICE = "price"
STEP_EXPLAIN = "explain"
STEP_COMPARE = "compare"

STEP_LABELS: dict[str, str] = {
    STEP_LOAD: "Load the account, unit, plan and reads",
    STEP_PRICE: "Price through the real engine",
    STEP_EXPLAIN: "Explain every line",
    STEP_COMPARE: "Compare with the last bill",
}

#: The clerk-facing word for each line kind. `rating`'s own kinds travel across
#: the seam unrenamed (`assemble_document.LINE_KINDS` says why: renaming across
#: a seam would make a bill's lines disagree with the engine that priced them),
#: so the translation to words happens HERE, at the screen's edge, and nowhere
#: earlier. B14 rule 32: no internal code in clerk-facing copy.
KIND_WORDS: dict[str, str] = {
    "usage": "Usage",
    "base": "Base charge",
    "tax": "Tax",
    "fee": "Fee",
    "minimum_adjustment": "Minimum bill",
    "deposit": "Deposit",
    "discount": "Discount",
}

#: Which chip a line sits under on the Records table. Three chips and not seven:
#: a clerk asks *what am I charging, what is tax, what is everything else*, and
#: seven chips over a seven-line bill is a filter bar longer than the table.
CHIP_ALL = "all"
CHIP_CHARGES = "charges"
CHIP_TAXES = "taxes"
CHIP_OTHER = "other"
_CHIP_OF_KIND: dict[str, str] = {
    "usage": CHIP_CHARGES,
    "base": CHIP_CHARGES,
    "minimum_adjustment": CHIP_CHARGES,
    "tax": CHIP_TAXES,
    "fee": CHIP_OTHER,
    "deposit": CHIP_OTHER,
    "discount": CHIP_OTHER,
}

#: ⚠ **THE REFUSAL SENTENCES, AND THE SIX-WORD CAP IS THE RULE THEY OBEY.**
#: B14 rule 33 — *a refusal sentence caps at five or six words* — and
#: `US-RBS-004`'s own `TC-RBS-004.2`: *"One refusal sentence naming the service
#: and the date, six words or fewer where it is a refusal"*.
#:
#: **THE DECISION IS THE ENGINE'S; THE WORDS ARE THIS MODULE'S**, and the
#: distinction is the one a reader should not have to reconstruct. The engine
#: names the reason CODE and the SERVICE (`GatherProblem.reason`,
#: `.service_code`) and this module renders them. Carrying the engine's own
#: sentence to the screen instead is impossible under B14 rule 32: those
#: sentences quote `BR-BIL-015`, `BR-RAT-090` and `BR-CUS-1010` by name, and a
#: rule id may not reach a clerk. The engine's full sentence still travels in
#: the run's record, unrendered.
#:
#: `{service}` is filled with the service the engine named and `{month}` with
#: the period's own month. A reason with no template falls through to the last
#: line, which still names both and still fits.
#:
#: ⚠ **THE COLON FORM IS NOT A STYLE CHOICE — IT IS WHAT MAKES SIX WORDS
#: REACHABLE, AND THE FIRST DRAFT DID NOT.** *"Sewer has no read for August."*
#: is six words and fits; the SAME sentence for the eleventh service is *"Storm
#: water has no read for August."* — **seven** — and two of the eleven service
#: codes are two words (`storm_water`, `thermal_heat`). A rule checked against
#: one service passes over the two that break it, which is why the test asserts
#: every reason against every service rather than the one a fixture reaches.
_REFUSAL_SENTENCE: dict[str, str] = {
    "missing_read_undecided_at_calculate": "{service}: no {month} read.",
    "unmetered_asset_count_undetermined": "{service}: assets not counted yet.",
    "installed_capacity_undetermined": "{service}: equipment size not recorded.",
    "account_has_no_unit": "This account is on no unit.",
    "unit_has_no_plan": "This unit has no plan.",
    "plan_not_published": "This unit's plan is not published.",
    "rating_refused_to_price": "{service}: not priced for {month}.",
    "ruled_path_refused": "{service}: not priced for {month}.",
    "account_held_by_disputed_read": "{service}: {month} read disputed.",
    "account_held_for_this_period": "Account held for {month}.",
    "account_not_billable_in_this_mode": "This account is not billable.",
    "account_has_nothing_to_bill": "Nothing to bill for {month}.",
    "account_not_found": "This account is not here.",
    # ── the gather's own reason codes, added after a real run met them ─────
    # ⚠ `plan_has_no_tariff_for_service` and `ruled_path_refused` are the two
    # this fixture actually produces, and the first one was reaching the
    # FALLBACK until the walkthrough showed it on screen. A fallback that reads
    # well is still a fallback: it says *no bill* where the fact is *no price*,
    # and those send a clerk to two different screens.
    "plan_has_no_tariff_for_service": "{service}: no {month} price.",
    "tariff_has_no_version_in_force_at_service_date": "{service}: no price for {month}.",
    "connection_size_unresolved_for_sized_schedule": "{service}: connection size not recorded.",
    "no_charge_applies_to_this_customer_type": "{service}: no charge applies here.",
    "unit_service_priced_nowhere": "{service}: priced on no plan.",
    "premises_jurisdiction_unstated": "This address has no tax area.",
    "tenant_currency_unresolved": "This utility has no currency.",
    "master_coverage_unresolved": "This account covers no units.",
    "cut_covers_some_services_and_not_others": "Part of this period is unpriced.",
    "unit_has_no_billable_account": "This unit has no account.",
    "metering_has_not_published_reads": "No reads are available yet.",
}
_REFUSAL_FALLBACK = "{service}: no bill for {month}."

#: ⚠ **THE FIX ROUTE, `BR-RBS-011`: a refusal names where to go.** These are
#: ADDRESSES relative to the tenant, resolved by the screen — never a key a
#: reader assembles, which is what `DEF-CWP-3925` cost. The empty state's helper
#: says the same thing in words, because the Records block's empty state carries
#: a helper and not a link.
_FIX_ROUTE: dict[str, tuple[str, str]] = {
    "missing_read_undecided_at_calculate": ("Add a read", "/meter-reads"),
    "unmetered_asset_count_undetermined": ("Count the assets on this unit", "/assets"),
    "installed_capacity_undetermined": ("Record each asset's size", "/assets"),
    "account_has_no_unit": ("Put this account on a unit", "/accounts"),
    "unit_has_no_plan": ("Give this unit a plan", "/units"),
    "plan_not_published": ("Publish the plan", "/plans"),
    "account_held_by_disputed_read": ("Clear the disputed read", "/meter-reads"),
    "account_held_for_this_period": ("Open the pending queue", "/billing/pending"),
    "plan_has_no_tariff_for_service": ("Add a rate schedule to the plan", "/plans"),
    "tariff_has_no_version_in_force_at_service_date": ("Activate a rate version", "/rate-schedules"),
    "connection_size_unresolved_for_sized_schedule": ("Record the connection size", "/assets"),
    "no_charge_applies_to_this_customer_type": ("Add a charge for this type", "/charges"),
    "unit_service_priced_nowhere": ("Price this service on a plan", "/plans"),
    "premises_jurisdiction_unstated": ("Set the tax area on the premises", "/premises"),
    "tenant_currency_unresolved": ("Set the currency in Settings", "/settings"),
    "master_coverage_unresolved": ("Attach the units this account covers", "/accounts"),
    "cut_covers_some_services_and_not_others": ("Open Plans & Rates", "/plans"),
    "unit_has_no_billable_account": ("Put an account on this unit", "/accounts"),
    "metering_has_not_published_reads": ("Open Meter Reads", "/meter-reads"),
    "account_not_found": ("Open Accounts", "/accounts"),
}
_FIX_ROUTE_FALLBACK = ("Open Plans & Rates", "/plans")


# ── the four steps ────────────────────────────────────────────────────────
#
# ⚠ **ALL FOUR ARE `set` MODE AND THE PINNED SET IS ONE ACCOUNT** — the shape
# `configuration_check` already uses for its ten. A `set` step runs ONCE over
# the pinned set and its answer lands in `ctx.set_results[key]`, which is the
# only channel a later step can read an earlier one through; four `per_record`
# steps over one subject would have no way to hand step 2's priced lines to
# step 3. The mode is passed explicitly on every step because `Step.mode` has
# no default (`BR-RBS-023`) and a helper that supplied one would put the
# default back one layer up.


def step_load(ctx, subjects) -> dict[str, Any]:
    """Step 1 — the account, its unit and plan, and the window being priced.

    ⚠ **IT READS WHAT THE RUN WOULD READ AND STOPS THERE.** The account's own
    row comes through `customers_seam`; everything the PRICE depends on — the
    unit, the plan, the tariff versions in force, the readings — is gathered by
    `billing.single.prepare_single_bill` inside step 2, because that is the one
    place the run gathers them and a second gather here would be a second answer
    to *"what would the run see"*.

    So this step's job is the SCOPE, and its output is what the run was asked
    about rather than what it found.
    """
    subject = subjects[0] if subjects else None
    period_start, period_end, service_date = _window(ctx)
    account = customers_seam.account_facts(subject.subject_id) if subject else None
    return {
        "account_id": None if subject is None else subject.subject_id,
        "account_no": (account or {}).get("account_no"),
        "account_label": (account or {}).get("label") or (subject.label if subject else ""),
        "period_start": period_start,
        "period_end": period_end,
        # ⚠ **THE DATE THAT DECIDES THE PRICE** (`BR-RAT-007`, judgment J9), and
        # it is NOT always the period end — a cycle run prices on its bill day.
        # It is carried here and drawn on the screen for that reason.
        "service_date": service_date,
        "found": account is not None,
    }


def step_price(ctx, subjects) -> dict[str, Any]:
    """Step 2 — **the rating engine's own path**, through billing's own gather.

    One call, `billing_seam.price_account_as_the_run_would`, which is
    `prepare_single_bill` followed by `runs.price_account` — the run's phase 1
    and its stages 1–5, unmodified. Nothing here assembles a `price_bill` call,
    chooses a tariff, applies a proration or decides which refusals matter:
    every one of those is the engine's, and copying any of them is the failure
    `US-RBS-004` is written to prevent.

    ⚠ **A REFUSAL IS AN OUTCOME, NOT AN ERROR** (PO ruling 2026-09-06: *"in
    absence of API conenctions you will not find anything and you can stop the
    job saying APi or conenct not available; that is a valid case and state for
    us"*). The account that cannot be priced STOPS and says which service and
    why, and that sentence is the goal this runbook was built for as much as
    the priced bill is.
    """
    loaded = dict(ctx.set_results.get(STEP_LOAD) or {})
    if not loaded.get("account_id"):
        return {
            "priced": None,
            "refusal": {
                "reason": "account_not_found",
                "service_code": None,
                "detail": "",
                "silent": False,
            },
        }
    return billing_seam.price_account_as_the_run_would(
        account_id=loaded["account_id"],
        period_start=loaded["period_start"],
        period_end=loaded["period_end"],
        service_date=loaded["service_date"],
    )


def step_explain(ctx, subjects) -> dict[str, Any]:
    """Step 3 — one sentence per line, in words a clerk can read (`BR-RBS-010`).

    Built from what each line already carries. A usage line knows its quantity,
    its unit and its unit price, so it explains itself; a tax line knows only
    which tax it is, so the rate comes from `rating_seam.tax_facts` — the module
    that owns `taxes`.

    ⚠ **NOTHING HERE RECOMPUTES A LINE.** `quantity × unit_price` is
    deliberately not asserted against `amount`: B4 rounds per line
    (`BR-RAT-003`) and a proration may sit between them, so a sentence that
    multiplied would eventually contradict the number beside it. The sentence
    states the INPUTS the engine used; the amount is the engine's.
    """
    priced = (ctx.set_results.get(STEP_PRICE) or {}).get("priced")
    if not priced:
        return {"lines": [], "taxes": {}}

    taxes = rating_seam.tax_facts([line.get("tax_id") for line in priced["lines"]])
    explained = []
    for index, line in enumerate(priced["lines"], start=1):
        explained.append(
            {
                "seq": index,
                "kind": line["kind"],
                "kind_word": KIND_WORDS.get(line["kind"], "Charge"),
                "chip": _CHIP_OF_KIND.get(line["kind"], CHIP_OTHER),
                "description": line["description"],
                "service": _service_word(line.get("service")),
                "quantity": line.get("quantity"),
                "unit": line.get("unit"),
                "unit_price": line.get("unit_price"),
                "amount": line["amount"],
                "why": _why(line, taxes),
            }
        )
    return {"lines": explained, "taxes": taxes}


def step_compare(ctx, subjects) -> dict[str, Any]:
    """Step 4 — against the last ISSUED bill, line by line, outer joined.

    ⚠ **AN OUTER JOIN, AND `TC-RBS-004.4` IS ABOUT EXACTLY THIS.** A line on one
    side only is the interesting row — a new charge, a fee that stopped — and an
    inner join hides both. Every description from either side appears, with an
    em dash where that side has none.

    ⚠ **THE MATCH KEY IS THE DESCRIPTION.** It is the only key the two sides
    share: a priced line has no id because it was never written, and an issued
    line's `service_id` is NULL on every tax and fee row. Where the wording
    changed between the bills the line shows twice, once on each side — visible
    and honest, where a fuzzy match would be neither.
    """
    loaded = dict(ctx.set_results.get(STEP_LOAD) or {})
    priced = (ctx.set_results.get(STEP_PRICE) or {}).get("priced")
    if not priced or not loaded.get("account_id"):
        return {"available": False, "reason": "not_priced", "rows": []}
    if str(ctx.params.get("compare_with") or "last_issued_bill") != "last_issued_bill":
        return {"available": False, "reason": "not_requested", "rows": []}

    previous = billing_seam.last_issued_bill(
        loaded["account_id"], before=loaded["period_start"]
    )
    if previous is None:
        return {"available": False, "reason": "no_issued_bill", "rows": []}

    mine: dict[str, Decimal] = {}
    order: list[str] = []
    for line in priced["lines"]:
        key = line["description"]
        if key not in mine:
            order.append(key)
        mine[key] = mine.get(key, Decimal("0")) + _decimal(line["amount"])

    theirs: dict[str, Decimal] = {}
    for line in previous["lines"]:
        key = line["description"]
        if key not in mine and key not in theirs:
            order.append(key)
        theirs[key] = theirs.get(key, Decimal("0")) + _decimal(line["amount"])

    rows = []
    for key in order:
        left = mine.get(key)
        right = theirs.get(key)
        rows.append(
            {
                "description": key,
                "this_run": left,
                "last_bill": right,
                "difference": (left or Decimal("0")) - (right or Decimal("0")),
                "ties": left is not None and right is not None and left == right,
                "only_here": right is None,
                "only_there": left is None,
            }
        )
    rows.append(
        {
            "description": "Total",
            "this_run": _decimal(priced["total"]),
            "last_bill": _decimal(previous["total"]),
            "difference": _decimal(priced["total"]) - _decimal(previous["total"]),
            "ties": _decimal(priced["total"]) == _decimal(previous["total"]),
            "only_here": False,
            "only_there": False,
            "total": True,
        }
    )
    return {
        "available": True,
        "reason": "",
        "period_start": previous["period_start"],
        "period_end": previous["period_end"],
        "currency": previous["currency"],
        "rows": rows,
    }


# ── the sentences ─────────────────────────────────────────────────────────


def _why(line: dict[str, Any], taxes: dict[str, dict[str, Any]]) -> str:
    """One sentence saying what produced this amount. `BR-RBS-010`, judgment J1.

    ⚠ **HARD RULE 3 IS LOAD-BEARING IN HERE.** A quantity is never spoken
    without its unit — *"5,000 gal"*, never *"5,000"* — so a line that carries a
    quantity and no unit says nothing about the quantity at all rather than
    naming a bare number a reader would have to guess the unit of.
    """
    kind = line["kind"]
    quantity = line.get("quantity")
    unit = line.get("unit")
    price = line.get("unit_price")

    if kind == "tax":
        fact = taxes.get(str(line.get("tax_id") or ""))
        if fact and fact.get("rate_display"):
            return f"{fact['rate_display']} of the charges this authority taxes."
        return "Tax on the charges this authority taxes."

    if kind == "base":
        service = _service_word(line.get("service"))
        return f"Fixed charge for {service}." if service else "Fixed charge for this service."

    if kind == "minimum_adjustment":
        return "Topped up to this plan's minimum bill."

    if kind == "discount":
        return "A reduction this account is enrolled in."

    if kind == "fee":
        return "A charge code applied to this bill."

    if kind == "deposit":
        return "A deposit applied to this bill."

    # usage, and anything a later engine adds: say what was measured and at what
    # price, and say only what the line actually carries.
    if quantity is not None and unit and price is not None:
        return f"{_quantity(quantity)} {unit} at {_rate(price)} a {unit}."
    if quantity is not None and unit:
        return f"{_quantity(quantity)} {unit} measured in this period."
    if price is not None and unit:
        return f"Priced at {_rate(price)} a {unit}."
    return "Priced by this account's rate plan."


def refusal_sentence(refusal: dict[str, Any], period_end) -> str:
    """The ONE sentence a stopped test bill shows. Six words or fewer.

    B14 rule 33 and `TC-RBS-004.2`. See `_REFUSAL_SENTENCE` for why the words
    are this module's and the decision is the engine's.
    """
    reason = str(refusal.get("reason") or "")
    service = _service_word(refusal.get("service_code")) or _NO_SERVICE_SUBJECT
    month = _month_word(period_end)
    template = _REFUSAL_SENTENCE.get(reason, _REFUSAL_FALLBACK)
    return template.format(service=service, month=month)


def fix_route(refusal: dict[str, Any]) -> tuple[str, str]:
    """Where a clerk goes to make this bill possible — `BR-RBS-011`.

    Every refusal has one. A failure with no route is a defect in the runbook,
    which is why the fallback is a real screen rather than an empty string.
    """
    return _FIX_ROUTE.get(str(refusal.get("reason") or ""), _FIX_ROUTE_FALLBACK)


# ── small helpers ─────────────────────────────────────────────────────────


def _service_word(code: Any) -> str:
    """A service CODE rendered as a word. B14 rule 32 — no internal code on screen.

    The codes are already words (`water`, `storm_water`, `fire`), so this is a
    presentation of them rather than a lookup; a lookup through `tenancy` would
    be a tenth read seam for a capital letter.
    """
    if not code:
        return ""
    return str(code).replace("_", " ").strip().capitalize()


#: What a refusal calls the subject when the engine named no service — an
#: account-level stop rather than a service-level one. Two words, so the
#: six-word cap still holds on every template that interpolates it.
_NO_SERVICE_SUBJECT = "This bill"


def _month_word(day) -> str:
    """*August* — the month a refusal names. `BR-TEN-043`: from the period, never a clock."""
    if not isinstance(day, date):
        return "this period"
    return calendar.month_name[day.month]


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _quantity(value: Any) -> str:
    """A measured quantity, grouped, with trailing zeros trimmed.

    ⚠ **NOT MONEY AND NOT ROUNDED TO TWO.** A consumption is not a currency
    amount: `7,240 gal` and `0.5 kW` are both real, and quantizing to two
    decimals would round a small interval reading away. Hard rule 3's partner —
    the unit travels beside this, always.
    """
    number = _decimal(value).normalize()
    if number == number.to_integral_value():
        return f"{int(number):,}"
    return f"{number:,f}"


def _rate(value: Any) -> str:
    """A tariff RATE at FOUR decimals, zeros kept (`OQ-620`, PO 2026-08-27).

    Deliberately not money's two: `$0.0025 / kWh` prints `$0.00` at two decimals
    and would read as free beside a real charge. The currency symbol is the
    screen's; this is the number.
    """
    return f"{_decimal(value).quantize(Decimal('0.0001')):,}"


def _money_value(amount: Any, currency: str) -> dict[str, Any]:
    """A `money` report cell — **the STORED figure at four decimals**.

    Hard rule 2: stored to 4, displayed at 2, and DISPLAY is `MoneyCell`'s job
    in the browser. Quantizing here would make the frozen report a rounded
    record and `TC-RBS-004.3`'s four-decimal comparison unrunnable against it.
    """
    return {
        "kind": "money",
        "amount": str(_decimal(amount).quantize(Decimal("0.0001"))),
        "currency": currency or "USD",
    }


def _window(ctx) -> tuple[date, date, date]:
    """The period being priced AND the date it is priced ON — judgments J8 and J9.

    A `period` parameter arrives as `{"start": …, "end": …, "as_at": …}` or as a
    pair; with neither, the default is the last WHOLE calendar month, which is
    the period a clerk asking *"what would this bill be"* almost always means.

    ⚠ **`as_at` IS THE CARD'S OWN SECOND HALF AND IT DECIDES THE PRICE**
    (judgment J9). `RB-123`'s scope row reads *"Period: A cycle, or **as at a
    date**"*, and `BR-RAT-007` prices on the SERVICE DATE — which for a real
    cycle run is the BILL DAY, not the last day of the period. On the seeded
    utility those are 2026-08-02 and 2026-07-31, and a water rate change falls
    between them: re-pricing July at the period end picks the version in force
    to 2026-07-31 (`$4.00 / kgal`) where the issued bill used the one in force
    on 2026-08-02 (`$4.24 / kgal`), and the same account comes back **$158.10
    against the $160.52 the customer was actually billed**.

    Neither figure is wrong — they are two different questions — but a clerk
    comparing them without knowing which date each used would file a defect
    against the bill. So the date is a PARAMETER, it defaults to the period end,
    and **the screen states which date priced the run** rather than leaving a
    reader to infer it.

    ⚠ **NO CLOCK DECIDES A PRICE.** `BR-TEN-043` / `G6`: today is read only to
    CHOOSE a default window a person then sees and can change; every figure
    inside the run is priced on the service date this returns.
    """
    raw = ctx.params.get("period")
    start, end, as_at = _parse_window(raw)
    if start is None or end is None:
        from django.utils import timezone

        today = timezone.localdate()
        end = today.replace(day=1) - _one_day()
        start = end.replace(day=1)
    return start, end, as_at or end


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


def _parse_window(raw: Any) -> tuple[date | None, date | None, date | None]:
    """`(start, end, as_at)`. `as_at` is `None` unless the caller stated one."""
    if isinstance(raw, dict):
        return (
            _as_date(raw.get("start")),
            _as_date(raw.get("end")),
            _as_date(raw.get("as_at")),
        )
    if isinstance(raw, (list, tuple)) and len(raw) in (2, 3):
        parts = [_as_date(value) for value in raw] + [None]
        return parts[0], parts[1], parts[2]
    return None, None, None


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# ── the report — four of the twelve blocks, composed at close ─────────────


def report(view) -> list[Block]:
    """`KPIs · Sentence · Records · Reconciled`, against `wireframes/RBS-006-R23`.

    Composed at CLOSE from what the run produced and frozen (`BR-RBS-020`). Four
    blocks in the priced state and two in the refused one; judgments J2, J6 and
    J7 say why those and not others, and the build sheet carries the same
    reasoning for a reader who never opens this file.
    """
    loaded = dict(view.set_results.get(STEP_LOAD) or {})
    step2 = dict(view.set_results.get(STEP_PRICE) or {})
    priced = step2.get("priced")
    refusal = step2.get("refusal")

    if not priced:
        return _refused_report(loaded, refusal or {})
    return _priced_report(view, loaded, priced)


def _refused_report(loaded: dict[str, Any], refusal: dict[str, Any]) -> list[Block]:
    """The stop. ONE sentence and where to go — judgment J2.

    ⚠ **`silent` IS A DIFFERENT OUTCOME AND WEARS A DIFFERENT TONE.**
    `BR-BIL-1025`: an account the run examined and found nothing to charge for is
    the CORRECT state for an owner-occupier's account, not a fault. Drawing it in
    danger red would send a clerk looking for a problem that is not there, so it
    is `warning` and the words say *nothing to bill* rather than *stopped*.
    """
    silent = bool(refusal.get("silent"))
    sentence = refusal_sentence(refusal, loaded.get("period_end"))
    label, route = fix_route(refusal)
    return [
        Block(
            block="sentence",
            payload={
                "tone": "warning" if silent else "danger",
                "label": "Nothing to bill" if silent else "Stopped",
                "text": sentence,
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "line", "label": "Line"},
                    {"key": "service", "label": "Service"},
                    {"key": "quantity", "label": "Quantity", "numeric": True},
                    {"key": "rate", "label": "Rate", "numeric": True},
                    {"key": "amount", "label": "Amount", "numeric": True},
                    {"key": "why", "label": "Why this amount"},
                ],
                "rows": [],
                "total": 0,
                "empty": {
                    "title": "Nothing was priced.",
                    # `BR-RBS-011` — the route in words. The Records block's empty
                    # state carries a helper, not a link, so the words have to
                    # carry the destination.
                    "helper": f"{label}, then run this again.",
                },
            },
        ),
    ]


def _priced_report(view, loaded: dict[str, Any], priced: dict[str, Any]) -> list[Block]:
    explained = list((view.set_results.get(STEP_EXPLAIN) or {}).get("lines") or [])
    comparison = dict(view.set_results.get(STEP_COMPARE) or {})
    currency = priced.get("currency") or "USD"
    services = sorted({row["service"] for row in explained if row.get("service")})

    blocks = [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "total",
                        "label": "Total",
                        "value": _money_value(priced.get("total"), currency),
                        # ⚠ **`priced`, NOT `posting` — `DEF-RBS-4350`.** The
                        # strip used to label this total **Posting date**, two
                        # inches above this runbook's own sentence block saying
                        # *"Nothing was written and no bill number was used"*.
                        # `BR-REP-001` maps billing-side numbers to the posting
                        # date and cash-side to the clearing date, and a figure
                        # that was worked out and never entered in the books is
                        # neither — a third kind the rule never had to name,
                        # because nothing produced one until this runbook.
                        "basis": "priced",
                    },
                    {
                        "id": "lines",
                        "label": "Lines",
                        "value": {"kind": "text", "text": str(len(explained))},
                    },
                    {
                        "id": "services",
                        "label": "Services",
                        "value": {"kind": "text", "text": str(len(services))},
                    },
                    # ⚠ **THE FOURTH TILE IS THE DATE THAT DECIDED THE PRICE, AND
                    # IT EARNS ITS PLACE** (judgment J9). `BR-RAT-007` prices on
                    # the SERVICE date, which for a cycle run is the bill day
                    # rather than the period end — on the seeded utility, 2 August
                    # against 31 July, with a water rate change between them. A
                    # clerk comparing this screen with a bill and seeing $158.10
                    # against $160.52 has no way to explain the gap without it,
                    # and would file a defect against a bill that is correct.
                    {
                        "id": "priced_as_at",
                        "label": "Priced as at",
                        "value": {
                            "kind": "date",
                            "value": _iso(loaded.get("service_date")),
                        },
                    },
                ]
            },
        ),
        Block(
            block="sentence",
            payload={
                "tone": "success",
                "label": "Read this aloud",
                "text": (
                    f"This account would owe {_display(priced.get('total'), currency)} "
                    f"for {_period_words(loaded)}. "
                    "Nothing was written and no bill number was used."
                ),
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "line", "label": "Line"},
                    {"key": "service", "label": "Service"},
                    {"key": "quantity", "label": "Quantity", "numeric": True},
                    {"key": "rate", "label": "Rate", "numeric": True},
                    {"key": "amount", "label": "Amount", "numeric": True},
                    {"key": "why", "label": "Why this amount"},
                ],
                "rows": [_line_row(row, currency) for row in explained],
                "total": len(explained),
                "chips": _chips(explained),
                # A priced bill with no lines is `BR-BIL-1024`'s *"no lines, no
                # document"* — the run reached the end and there was nothing to
                # charge. It is a real answer and it reads as one.
                "empty": {
                    "title": "This account has nothing to charge.",
                    "helper": "Every service priced to nothing for this period.",
                },
            },
        ),
    ]

    if comparison.get("available"):
        blocks.append(
            Block(
                block="reconciled",
                payload={
                    "heading": "Against the last issued bill",
                    "columns": [
                        {"key": "line", "label": "Line"},
                        {"key": "this_run", "label": "This run", "numeric": True},
                        {"key": "last_bill", "label": "Last issued bill", "numeric": True},
                        {"key": "difference", "label": "Difference", "numeric": True},
                    ],
                    "rows": [
                        _comparison_row(index, row, currency)
                        for index, row in enumerate(comparison.get("rows") or [], start=1)
                    ],
                    "tiesLabel": "Same",
                },
            )
        )
    return blocks


def _line_row(row: dict[str, Any], currency: str) -> dict[str, Any]:
    """One priced line as a report row.

    ⚠ **`id` IS NEVER RENDERED** (B14 rule 31). These lines have no database id
    at all — nothing was written — so the key is the line's position, which is
    both stable within a frozen report and meaningless outside it.

    ⚠ **`meta` CARRIES WHAT NO COLUMN DRAWS.** `kind` and the chip are facts the
    findings reader and `TC-RBS-14`'s scan need and a clerk does not; a renderer
    walks `columns`, so nothing here can reach a screen by accident.
    """
    quantity = row.get("quantity")
    unit = row.get("unit")
    price = row.get("unit_price")
    return {
        "id": f"line-{row['seq']}",
        "cells": {
            "line": {"kind": "text", "text": row["description"]},
            "service": {"kind": "text", "text": row.get("service") or "—"},
            # Hard rule 3 — a quantity travels with its unit or it does not
            # travel. A line with a quantity and no unit draws the em dash
            # rather than a bare number nobody can interpret.
            "quantity": (
                {"kind": "unit", "quantity": _quantity(quantity), "unit": unit}
                if quantity is not None and unit
                else {"kind": "text", "text": "—"}
            ),
            # The `rate` cell kind and never `money`: 6 stored, FOUR shown,
            # zeros kept (`OQ-620`) — `$0.0084` reads `$0.00` at two decimals.
            "rate": (
                {"kind": "rate", "rate": _rate(price), "currency": currency}
                if price is not None
                else {"kind": "text", "text": "—"}
            ),
            "amount": _money_value(row["amount"], currency),
            "why": {"kind": "text", "text": row["why"]},
        },
        "meta": {"kind": row["kind"], "chip": row["chip"]},
    }


def _comparison_row(index: int, row: dict[str, Any], currency: str) -> dict[str, Any]:
    """One outer-joined comparison row — judgment J4, `TC-RBS-004.4`.

    A side with no line draws an em dash, and a row that ties draws the `Same`
    pill rather than an empty difference cell: an empty cell reads as *not
    checked*, which is the opposite of what a comparison is saying.
    """
    return {
        "id": f"cmp-{index}",
        "cells": {
            "line": {"kind": "text", "text": row["description"]},
            "this_run": (
                _money_value(row["this_run"], currency)
                if row.get("this_run") is not None
                else {"kind": "text", "text": "—"}
            ),
            "last_bill": (
                _money_value(row["last_bill"], currency)
                if row.get("last_bill") is not None
                else {"kind": "text", "text": "—"}
            ),
            "difference": (
                {"kind": "pill", "label": "Same", "tone": "neutral"}
                if row.get("ties")
                else _money_value(row["difference"], currency)
            ),
        },
        "meta": {
            "only_here": "yes" if row.get("only_here") else "no",
            "only_there": "yes" if row.get("only_there") else "no",
        },
    }


def _chips(explained: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = {CHIP_CHARGES: 0, CHIP_TAXES: 0, CHIP_OTHER: 0}
    for row in explained:
        counts[row["chip"]] = counts.get(row["chip"], 0) + 1
    chips = [{"id": CHIP_ALL, "label": "All", "count": len(explained)}]
    for chip, label in ((CHIP_CHARGES, "Charges"), (CHIP_TAXES, "Taxes"), (CHIP_OTHER, "Other")):
        if counts[chip]:
            chips.append({"id": chip, "label": label, "count": counts[chip]})
    return chips


def _display(amount: Any, currency: str) -> str:
    """Money as a clerk reads it — TWO decimals (hard rule 2), inside a sentence.

    This is the one place in this module that rounds, and it rounds because it is
    DISPLAY: the sentence block carries prose, not a `money` cell the renderer
    could format. Every FIGURE in the report is carried at four.
    """
    symbol = "$" if (currency or "USD") == "USD" else f"{currency} "
    return f"{symbol}{_decimal(amount).quantize(Decimal('0.01')):,}"


def _iso(value: Any) -> str:
    """A date as the `date` cell carries it — the tenant's ZONE and FORMAT are
    the shell's, never the payload's (`BR-SHL-023`, `DEF-SHL-3964`)."""
    return value.isoformat() if isinstance(value, date) else ""


def _period_words(loaded: dict[str, Any]) -> str:
    start = loaded.get("period_start")
    end = loaded.get("period_end")
    if not isinstance(start, date) or not isinstance(end, date):
        return "this period"
    if start.month == end.month and start.year == end.year:
        return f"{start.day}–{end.day} {calendar.month_name[end.month]}"
    return f"{start.isoformat()} to {end.isoformat()}"


# ── scope ─────────────────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **ONE account**, the one a clerk picked (`BR-RBS-009`).

    `RBS-004-R23` region 1 draws *Account: 🔍 one account* as a VALUE — the
    account is chosen before the run starts and the scope panel shows it rather
    than offering a picker on the result screen.

    An empty list is a lawful answer and the report says so in the ordinary
    refusal shape: a run with nothing to walk must not look like a clean bill.
    """
    account_id = ctx.params.get("account")
    if not account_id:
        return []
    facts = customers_seam.account_facts(account_id)
    if facts is None:
        return []
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(account_id),
            # ⚠ B14 rule 31 — the LABEL is what a reader sees and it is never
            # the id. `SubjectRef.label` is what the result files write into
            # their Subject column, so an unlabelled subject is an unusable row.
            label=facts.get("label") or facts.get("account_no") or "",
        )
    ]


def _step(key: str, run) -> Step:
    """One step, `set` mode, labelled from the table the setup sheet also draws.

    ⚠ **`mode` IS PASSED EXPLICITLY AND THIS HELPER DOES NOT MAKE IT A
    DEFAULT.** `Step.mode` has no default on purpose (`BR-RBS-023`); a helper
    that supplied one would move the default up one layer rather than remove it.
    All four steps here genuinely run once over a pinned set of one, and a step
    that needed the other mode would be built with `Step(...)` directly.
    """
    return Step(key=key, label=STEP_LABELS[key], mode=MODE_SET, run=run)


RUNBOOK = RunbookDefinition(
    key="test_bill",
    name="Test bill",
    kind=models.KIND_CHECK,
    category="billing",
    subject_type="account",
    unit_of_work="account-period",
    # ⚠ MANUAL AND NOTHING ELSE. PO ruling 2026-09-06: a person starts this —
    # a clerk picks an account and presses Run. A schedule over one account
    # would be a report nobody asked for, every day, for ever.
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Billing", "Plans & Rates"),
    parameters=(
        Parameter(
            name="account",
            type=PARAM_REF_OBJECT,
            label="Account",
            required=True,
            # ⚠ **THE DOMAIN, ADDED IN WAVE `T` (`BR-RBS-042` clause 2), AND
            # THIS INPUT HAD NONE SINCE THE DAY IT WAS WRITTEN.** A `ref:object`
            # with no domain is a picker over nothing: the setup screen could
            # draw the control and had no list to put in it, and nothing went
            # red because a picker that offers nothing renders perfectly.
            # `contract.Parameter` now refuses one at construction.
            #
            # ⚠ **AND IT IS THE UNBOUNDED DOMAIN.** A utility at the top of T5
            # has 40,000 accounts, so the picker reads
            # `GET /runbooks/test-bill/domains/account`, which slices in SQL
            # (`NFR-3`). It is deliberately NOT `multi`: *all* of it would be a
            # test bill against every account, which is a different runbook.
            domain=DOMAIN_ACCOUNT,
        ),
        Parameter(
            name="period",
            type=PARAM_WINDOW,
            label="Period",
            required=True,
        ),
        Parameter(
            name="compare_with",
            type=PARAM_ENUM,
            label="Compare with",
            required=True,
            default="last_issued_bill",
            choices=("last_issued_bill", "nothing"),
        ),
        Parameter(
            name="show",
            type=PARAM_ENUM,
            label="Show",
            required=True,
            default="every_line_explained",
            # ⚠ ONE CHOICE, AND THE CARD OFFERS ONE. `RB-123`'s parameter table
            # says *Show: Every line, explained* and names no second value. A
            # dropdown of one is honest; inventing *Totals only* to fill it
            # would be this lane deciding a product question nobody asked.
            choices=("every_line_explained",),
        ),
        Parameter(
            name="rounding",
            type=PARAM_REF_SETTING,
            label="Rounding",
            # ⚠ READ-ONLY AND SETTINGS-OWNED (`RBR-03`, `RB-021`, and the build
            # sheet's dashed control with *Open settings →*). Policy lives in
            # Settings and is never duplicated onto a card: two rounding rules
            # is how a utility ends up unable to say which one priced a bill.
            setting_key="money.rounding",
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        _step(STEP_LOAD, step_load),
        _step(STEP_PRICE, step_price),
        _step(STEP_EXPLAIN, step_explain),
        _step(STEP_COMPARE, step_compare),
    ),
    # ⚠ **`ports` IS ABSENT AND THAT IS THE RULE, NOT AN OVERSIGHT**
    # (`BR-RBS-002`). A Check is CONSTRUCTED without action ports: the
    # capability is gone rather than unused, so no bill number can be consumed
    # and no invoice, line or journal entry can be touched (hard rule 4).
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-004 (EP-RBS-02; CR-075 wave F tasks F1–F4)
# generated: 2026-09-06 by the CR-075 wave F build lane
# checklist: A✔ B✔ C✔ D=n/a(no new endpoint — the eight GET routes of wave D serve this runbook unchanged) E=n/a(no frontend code — RB-020's claim: runbook 23 is one Python module, and the result renderer draws the four blocks it composes) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, invents no rating math and posts no ledger line — it CALLS the engine's own path)
# gates: pytest tests/test_us_rbs_004_test_bill.py · pytest tests/test_us_rbs_004_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · 10-scripts/render-checks/rbs-f-test-bill.mjs
# exceptions: (1) no `downloads` block — the result files stream runbook_run_records and nothing writes one yet (judgment J6); (2) no `verdict` block (J7); (3) the pricing call lives in the BILLING seam, not the rating seam as 10-execution-plan.md F2 words it — the account→line chain is billing's, and both seams are already register rows (billing_seam.py records the divergence in full)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
