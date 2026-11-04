# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data) · US-BIL-001/004/005
#           (the five-phase bill run this drives)   Screens: S30, S31 · S8
#           (Sample data panel, BR-TEN-069)
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 (the sample set reaches money) ·
#           BR-TEN-063 (idempotent, audited) · BR-TEN-066 (removal is
#           partial-and-named) · BR-BIL-005 (one run per cycle+period) ·
#           BR-BIL-023 (issue all remaining drafts) · BR-BIL-051/052 (the five
#           phases; a break never stops the run) · BR-BIL-058 (the release
#           gate's five facts) · BR-BIL-070 (the bill date is the clerk's) ·
#           CLAUDE.md hard rule 4 (an issued bill is append-only)
# Tests:    06-backend/tests/test_us_ten_019_sample_records.py
# Impacts:  apps/tenancy/sample_data.py (the orchestrator resolves the seam) ·
#           apps/payments (pays these bills)
# ───────────────────────────────────────────────────────
"""billing's half of the sample set: JUNE billed, JULY ready-to-run (DEF-153).

⚠ THE 2026-08-16 SPEC QUOTE BELOW IS SUPERSEDED — CR-010 Part-10.4, 2026-08-17
--------------------------------------------------------------------------------
This docstring used to open "June and July, BILLED", quoting the fixture spec
of 2026-08-16 (*"June and July BILLED and mostly PAID, June closed"*). The
Product Owner amended it on 2026-08-17, verbatim: *"do 1 month billed na dkeep
other month ready"* — so the fixture now issues **JUNE only, mostly paid**, and
leaves **JULY READY-TO-RUN**: its reads staged and committed by metering's
block, nothing billed, so the trial's FIRST bill run is July on prepared data.
The spec's §3 table carries the same stamp in the same commit, and
`core.sample_fixture.PERIODS` is where the flip lives — `july.billed = False` —
so this module needed no period list of its own to change.

BR-TEN-056 CLAUSE 1 IS AMENDED, AND THIS FILE IS THE AMENDMENT
----------------------------------------------------------------
BR-TEN-056 (PO 2026-08-10) said the sample set *"stops at reads — sample data
NEVER reaches `invoices`, `invoice_lines`, `payments` or `journal_entries`"*,
for a good reason: those rows are append-only (hard rule 4), so a sample row
there can never be removed.

The Product Owner ruled otherwise on 2026-08-16, verbatim: *"if we are able to
seed the data refernece as well as transaction data, then we can test the
application end to end and see what are the issues; thiswill be human
checking"* — and the fixture spec ruled the same day states it as a table:
**June and July BILLED and mostly PAID, June closed.** A product nobody can
evaluate by using it is the failure that outranks a demo nobody can fully clear.

**THE OLD RULE'S REASONING IS NOT WRONG, IT IS PRICED.** Removal becomes
PARTIAL: everything free goes, the bills and payments stay and are REPORTED BY
NAME on the Sample data panel. That is BR-TEN-066's own shape applied to the one
case its author did not have to consider, and it is written into
`04-docs/05-modules/01-tenancy/02-business-rules.md`, dated, with both quotes.

JULY AND AUGUST ARE NOT BILLED HERE AND MUST NOT BE
-----------------------------------------------------
Spec §3's reasoning, now covering two months: *"A fixture that arrives with
everything done leaves nothing to evaluate."* `_periods_to_bill()` is the
periods marked `billed` in the fixture — **June alone** since the 2026-08-17
amendment — while July and August are read, committed and waiting. Anyone
tempted to "finish the job" by billing July or August is removing the
acceptance test twice over.

THE RUN IS DRIVEN THROUGH ALL FIVE PHASES, EXACTLY AS S31 DRIVES THEM
-----------------------------------------------------------------------
create → prepare → apply the clerk's decisions → calculate → **the release gate**
→ issue. Not one of them is skipped and the gate is not bypassed: BR-BIL-058's
five facts are recorded as a real `bill_run_releases` row, because *"forged POST
straight to issue with no release record"* is a refusal the product makes and a
fixture that went round it would be seeding bills the product would not have
issued.

⚠ DEF-154 WAS VISIBLE ON EVERY BILL THIS WROTE, AND IS FIXED. The base charge
is a PLAN attribute — $8.00 water, $18.00 trash on the seeded plans — and the
engine used to read it from the rate SCHEDULE, where it is zero, so every
seeded bill printed a $0.00 base. The fix (billing-9 lane, 2026-08-16:
`apps/billing/gather._base_charge_for` reads the plan's own figure) closed it
— ⚠ **and THAT source has since moved TWICE and this sentence is kept with its
dates rather than rewritten**: `BR-RAT-088` (2026-08-20) made the CHARGE CODE
the owner, and `DEF-BIL-7170` (PO 2026-09-28, *"we will never take default
value from plan $8.0 - that is retired"*) took the plan's column off the money
path altogether. What has not moved is the defect this paragraph is about: a
base read from the wrong object prints a figure nobody typed;
the sentence is kept, corrected, because this fixture is where the defect was
VISIBLE and where a regression would show first (hard-won law 1: a docstring
describing a state the product has left gets corrected, not deleted).
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import decisions, models, release, runs, selectors, templates_service
from core import audit
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _billed_periods() -> tuple[dict[str, Any], ...]:
    """Every period the fixture declares as billed, in fixture order.

    The fixture is the only place that decides how many cycles a demo carries
    (CR-040 task C9 made that two). This function does not know or care which
    ones they are — a third would need no change here, and neither seam below
    would have to be edited to find it.
    """
    return tuple(period for period in fixture.PERIODS if period["billed"])


def _periods_to_bill() -> tuple[dict[str, Any], ...]:
    """**THE FIRST CYCLE ONLY** — CR-040 task C8.

    This used to return every billed period, which was one period, so the
    distinction did not exist. It exists now and it is the whole point of the
    split: the money cases the PO ordered between the two runs — the payments,
    the credit, the refund and the overcharge correction — are written by
    blocks that run BETWEEN this seam and `seed_sample_second_cycle` below.
    """
    return _billed_periods()[:1]


def _second_cycle_periods() -> tuple[dict[str, Any], ...]:
    """**EVERYTHING AFTER THE FIRST** — CR-040 task C8.

    A slice rather than an index, so a fixture that ever declares three billed
    periods bills the third here instead of dropping it silently. Empty is a
    lawful answer: a fixture with one billed period leaves this seam with
    nothing to do, and the block reports that honestly rather than failing.
    """
    return _billed_periods()[1:]


def _instant(day: Any) -> datetime:
    """An offset-bearing instant the CALLER named.

    G6 bans a wall clock from every money path, and the reason is not tidiness:
    `issued_at` lands on an immutable invoice. The fixture's own bill date is
    the moment, so a tenant seeded today and a tenant seeded next month carry
    the same dates on the same bills.
    """
    return datetime.combine(day, time(9, 0), tzinfo=dt_timezone.utc)


def _sample_cycle_id() -> Any | None:
    """The sample cycle, through metering's published read (B1)."""
    from apps.billing.runs import _resolve

    cycles_list = _resolve("metering", "cycles_list")
    if cycles_list is None:
        return None
    from apps.metering import sample_data as metering_sample

    # ⚠ ASKED, NOT COMPARED (W5-T1). This read `row["code"] ==
    # metering_sample.SAMPLE_CYCLE_CODE`, and that constant no longer exists:
    # the sample cycle's code is allocated from the CY- number series now (D5),
    # so it differs on every tenant. Metering owns the recogniser and this asks
    # it, which is one place for the answer instead of two files agreeing about
    # a string until one of them stops.
    row = metering_sample.sample_cycle_row(list(cycles_list()))
    return None if row is None else row["id"]


def _template_pin() -> tuple[Any, int] | None:
    """BR-BIL-026's pin — RESOLVED through billing's own resolver, never
    invented. A tenant with no bill template cannot issue (DEF-123), and this
    reports that rather than minting a uuid."""
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            resolved = templates_service.resolve_for(consumer_category=None)
    except Exception as exc:  # noqa: BLE001 — reported by the caller, by name
        logger.info("sample data: no bill template to pin (%s)", type(exc).__name__)
        return None
    if resolved is None:
        return None
    template, version = resolved
    return template.id, version.version_no


def _decide_the_unmetered_services(actor: Any, run: Any, prepared: Any) -> None:
    """⚠ DEF-161 — HALF CLOSED 2026-08-16, AND THE OTHER HALF IS **OQ-246**.

    **SEWER NO LONGER REACHES THIS FUNCTION AND MUST NOT.** A
    `percent_of_service` tariff prices no consumption of its own — BR-RAT-015
    (CONFIRMED): sewer is a *"% of water usage-charge dollars"* — so the run no
    longer raises a missing read for it, `calculate_account` no longer refuses
    the account, and the sewer line PRICES, in the engine's second pass, off the
    water usage it is a percentage of. On the seeded reference bill that is
    **40% × $39.50 = $15.80** (B5 GT-17 ❄️). If this loop ever records a
    decision for sewer again, something has undone that and the bills have
    silently lost a charge.

    **TRASH STILL REACHES IT, AND THAT IS THE OPEN QUESTION.** Trash is a flat
    monthly charge on a service point with no meter, and **no signed rule says
    what a service point with no meter means for a tariff that DOES price
    consumption**. The fixture must not choose one (spec rule 7), so **OQ-246**
    asks the Product Owner and this fixture keeps doing what the product does
    today: records a REAL decision a clerk can take, through the real service,
    with the reason in the audit trail.

    ── the original note, still true for the case that remains ────────────────

    **What the product does today:** the run asks for a meter read for EVERY
    service on the plan, including services that are not metered by design.
    Silver Creek's trash is a flat monthly charge with no meter, and its sewer
    is 40% of the water usage charge with no meter — neither will ever have a
    read — and both come back `no_meter`, which `calculate_account` treats as an
    *unresolved missing read* and refuses the whole account for.

    **The consequence, measured on a booted stack:** a plan carrying any
    non-metered service CANNOT BE BILLED AT ALL. 48 accounts × 2 services = 96
    refusals on a 48-account run, and the only decision that unblocks one —
    `bill_without_service` — REMOVES that service from the bill, so the $18
    trash charge and the sewer percentage can never reach a customer.

    **What this seeder does, and why it is not a workaround:** it records
    `bill_without_service`, which is a REAL choice the product offers a clerk,
    through `record_bulk`, which is the real bulk-decision service, with a
    reason naming DEF-161 in the audit trail. So the June and July bills exist
    and carry their water lines, and the ABSENCE of the sewer and trash lines is
    visible on every one of them — which is exactly what a fixture is for. The
    alternative, recording an `estimate` of zero, would fabricate a meter
    reading for a meter that does not exist, and that is a lie in an audit trail
    that a customer could one day be shown.
    """
    from apps.billing import tenancy_seam

    service_ids = tenancy_seam.service_ids_by_code() or {}
    recorded = 0
    for problem in getattr(prepared, "decisions", ()):  # phase 1's decision list
        if problem.reason != "missing_read" or not problem.service_code:
            continue
        if problem.service_code == "water":
            # Water IS metered. A missing water read is a real exception and is
            # left for a human — never decided by a fixture.
            continue
        decisions.record_decision(
            bill_run=run,
            account_id=problem.account_id,
            case="missing_read",
            choice=decisions.CHOICE_BILL_WITHOUT_SERVICE,
            # ⚠ PER SERVICE, one call each, and NOT through `record_bulk`.
            # `record_bulk` takes no `service_id`, so two per-service decisions
            # for one account collapse into one row and the second SUPERSEDES
            # the first — measured here: 96 calls produced 48 stored decisions
            # and every account still broke. That is the second half of DEF-161
            # and it is a real limit on the S31 decisions screen's bulk action,
            # not a quirk of this fixture.
            service_id=service_ids.get(problem.service_code),
            reason=(
                f"sample data: {problem.service_code} is not metered on this plan and "
                "never will be, so there is no read to wait for. Recorded rather than "
                "assumed — see DEF-161: the run treats an unmetered service as a "
                "missing read, and this choice is the only one that lets the bill "
                "through. It also removes the line, which is why the seeded bills "
                "carry no sewer or trash charge"
            ),
            decided_by=getattr(actor, "id", None),
        )
        recorded += 1
    if recorded:
        logger.info("sample data: recorded %s unmetered-service decisions", recorded)


def _decide_the_busy_day_money(actor: Any, run: Any, prepared: Any) -> None:
    """`DEF-BIL-8755` — the busy day's money goes on the NEXT bill, as the
    canonical calendar already puts it.

    On the anchor calendar the second run bills on the **2nd** and the busy
    day's takings (`fixture.BUSY_DAY`) land on the **8th**: after the bill, so
    they are next month's *payments received* and no Check finding is raised.
    A utility signing up on the 1st or 2nd of a month gets a calendar clamped
    to today (`core.sample_fixture.build_calendar`, DEF-LED-6640): the run
    bills TODAY and the busy day IS today, so those payments sit between the
    period's end and the bill date — the Check's *Paid after cut-off* window
    (BR-PAY-021) — and 45 of 49 accounts waited on a decision nobody answered.
    Measured on a sign-up dated 1 October 2026: **5 of 49** second-cycle bills.

    So the fixture records the choice its own calendar already made —
    *Apply next bill* — through the real decision service, with the reason in
    the trail, exactly as `_decide_the_unmetered_services` does. It applies
    only where the Check raised the case, so on any other day it writes
    nothing. *Apply to this bill* would be the OTHER story: money that, on the
    anchor calendar, arrived six days after the bill printed.
    """
    recorded = 0
    for problem in getattr(prepared, "decisions", ()) or ():
        if problem.reason != "paid_after_cutoff" or not problem.account_id:
            continue
        decisions.record_decision(
            bill_run=run,
            account_id=problem.account_id,
            case="paid_after_cutoff",
            choice=decisions.CHOICE_APPLY_NEXT_BILL,
            reason=(
                "sample data: taken on the demo's busy day, which the sample calendar "
                "puts after this bill went out — so it belongs on the next bill"
            ),
            decided_by=getattr(actor, "id", None),
        )
        recorded += 1
    if recorded:
        logger.info("sample data: recorded %s busy-day payment decisions", recorded)


def _issue_blockers() -> tuple[str, ...]:
    """What is known, BEFORE the run, to stop every bill issuing.

    Today there is exactly one and it cost DEF-166: a tax authority with no
    2200-series liability account. BR-BIL-010 / BR-BIL-069 refuse to stamp that
    bill's tax line, so EVERY bill carrying that authority breaks and the run
    stays in draft. Asked of RATING, which owns `taxes`, through its own
    published read — billing never queries another module's tables (B1).
    """
    try:
        from apps.rating import sample_data as rating_sample
    except Exception:  # noqa: BLE001 — rating absent is not billing's to explain
        return ()
    unmapped = getattr(rating_sample, "unmapped_tax_authorities", None)
    if unmapped is None:
        return ()
    return tuple(unmapped())


def _bill_one_period(actor: Any, period: dict[str, Any], cycle_id: Any) -> int:
    """One period, through all five phases. Returns bills ISSUED.

    ⚠ AMENDED 2026-08-16 — DEF-166. It used to end with
    `invoice_queryset().filter(bill_run=run).count()`, defended in its own
    comment as *"COUNTED FROM THE ROWS, not from the result object … a count
    read off the database cannot drift from what the database holds"*. That
    reasoning is right about DRIFT and blind to FAILURE: the query counted every
    invoice on the run, DRAFTS included, so `release_run` could decline to issue
    a single bill and the block still reported 95. Measured on a live Postgres:
    `invoices` = `draft | 95`, `bill_runs` = `draft | 2`, panel line "OK".
    The count is still read off the rows — and now off the rows that ISSUED,
    which is what the block claims.
    """
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            run = runs.create_run(
                cycle_id=cycle_id,
                period_start=period["start"],
                period_end=period["end"],
                bill_date=period["bill_on"],
                # `run_by` takes a USER ID, a `users` row or an actor, and
                # `create_run` resolves all three through
                # `core.audit.actor_user_id` now (DEF-BIL-5090). ⚠ **THIS LINE
                # WAS THE FIRST SIGHTING OF THAT DEFECT AND IT WAS FIXED HERE
                # INSTEAD OF AT THE ROOT** — the same `"namespace(id=…,
                # role=…)" is not a valid UUID` was measured on this call,
                # worked around at this one call site, and went on to stop
                # every cut in the product. The actor is passed whole again.
                run_by=actor,
                actor=actor,
            )
    except runs.DuplicateRun as replay:
        # BR-BIL-005 / BR-TEN-063: this period has already been billed for this
        # tenant. A replay changes no count and issues nothing.
        # `DuplicateRun.original` is the row that already exists — BR-BIL-005
        # carries the ROW rather than a sentence so a caller can go on with it.
        run = replay.original
        if selectors.invoice_queryset().filter(bill_run=run).exists():
            return 0

    prepared = selectors.prepared_for(run)
    _decide_the_unmetered_services(actor, run, prepared)
    _decide_the_busy_day_money(actor, run, prepared)
    prepared = selectors.prepared_for(run)
    prepared = decisions.apply_decisions(prepared, bill_run=run)
    runs.calculate_run(prepared, bill_run=run)

    drafts = selectors.invoice_queryset().filter(bill_run=run, status="draft").count()

    pin = _template_pin()
    if pin is None:
        raise fixture.BlockCannotRun(
            f"{period['key']} calculated {drafts} bill(s) and could NOT issue them: this "
            "tenant has no bill template, and a bill issued with no template pinned can "
            "never record what rendered it (BR-BIL-026, DEF-123). Add a bill template on "
            "Settings > Bill templates and load the sample data again."
        )

    release_row = release.pending_releases(run).first()
    if release_row is None and release.completed_releases(run).first() is None:
        # BR-BIL-058 — the five facts, recorded as a real authorisation row.
        # The gate is not bypassed: a fixture that forged its way past it would
        # be seeding bills this product would have refused to issue.
        release_row = release.authorise_release(
            bill_run=run,
            summary=release.summary_for(run),
            confirmations=release.Confirmations(
                compliance=True,
                email_mandate=True,
                sms_mandate=True,
                autopay_mandate=True,
                final=True,
            ),
            confirmed_by=getattr(actor, "id", None),
            confirmed_at=_instant(period["bill_on"]),
            actor=actor,
        )
    if release_row is None:
        raise fixture.BlockCannotRun(
            f"{period['key']} calculated {drafts} bill(s) and could NOT issue them: the "
            "release gate recorded no authorisation row, so BR-BIL-058's five facts were "
            "never confirmed and the run has nothing to release against."
        )

    outcome = release.release_run(
        bill_run=run,
        release_row=release_row,
        released_at=_instant(period["bill_on"]),
        issued_at=_instant(period["bill_on"]),
        template_id=pin[0],
        template_version=pin[1],
        invoice_ids=None,
        actor=actor,
    )
    # `IssuedRun.issued` is a tuple of the bills that went out; `broken` names
    # the ones that did not, each with its reason.
    broken = tuple(getattr(getattr(outcome, "issued", outcome), "broken", ()) or ())
    # COUNTED FROM THE ROWS — and from the rows that ISSUED. Reading the count
    # off the database still cannot drift from what the database holds; adding
    # `status="issued"` is what makes it also unable to hide a failure.
    issued = int(
        selectors.invoice_queryset().filter(bill_run=run, status="issued").count()
    )
    if broken:
        # ⚠ DEF-166's ONE SIGNAL WENT TO A LOG NOBODY OPENS. `broken` was read,
        # formatted and sent to `logger.info` — and the panel printed OK. The
        # reasons are now carried on the exception a HUMAN reads. A fixture that
        # cannot produce the bills it specifies is a broken fixture, so this
        # refuses rather than reporting a short count as a success; the block's
        # transaction rolls back and the tenant is not left half-billed.
        detail = "; ".join(
            str(getattr(item, "detail", item))[:400] for item in broken[:2]
        )
        raise fixture.BlockCannotRun(
            f"{period['key']}: {issued} bill(s) issued and {len(broken)} could NOT — "
            f"{detail}"
        )
    if not issued:
        raise fixture.BlockCannotRun(
            f"{period['key']} calculated {drafts} bill(s) and issued NONE, with no break "
            "reported. Nothing is reported as loaded: a draft is not a bill a customer "
            "was ever sent."
        )
    return issued


def _preconditions(actor: Any) -> Any:
    """The cycle id, or a refusal naming what is missing — CR-040 task C8.

    ⚠ **EXTRACTED, NOT REWRITTEN.** Every sentence below stood inside
    `seed_sample_records` and each was put there by a defect: the cycle check by
    the reads-must-load-first ordering, the actor check because BR-BIL-058's
    fifth fact is WHO said go, and the tax-authority check by DEF-166, whose
    actual cause was a setup fact that was knowable before 95 bills were
    calculated and was discovered after.

    They are extracted because there are now TWO billing blocks, and a guard
    that protects only the first one is worse than no guard: the second cycle
    would run into exactly the deep refusals these sentences exist to explain.
    """
    cycle_id = _sample_cycle_id()
    if cycle_id is None:
        raise fixture.BlockCannotRun(
            "no bill run was attempted: metering has not seeded the sample billing "
            "cycle, so there is no cycle to bill. The Meter reads block above has to "
            "load first."
        )
    if getattr(actor, "id", None) is None:
        # BR-BIL-058's fifth fact is WHO said go, and `missing_confirmations`
        # refuses a release whose `confirmed_by` is null — correctly: a bill run
        # authorised by nobody is not authorised. Said HERE, before 95 bills are
        # calculated, because the deep refusal reads as a billing fault and this
        # is an attribution one.
        raise fixture.BlockCannotRun(
            "no bill can be released: this sample load has no attributable user, and "
            "BR-BIL-058's release gate records WHO authorised the run. Run it as a "
            "signed-in user (the Sample data panel on Settings does exactly that), or "
            "give the tenant an owner the load can resolve."
        )
    blockers = _issue_blockers()
    if blockers:
        # ⚠ NAMED BEFORE THE RUN, not discovered 95 bills later. This is
        # DEF-166's actual cause and it is a SETUP fact, knowable up front.
        named = ", ".join(sorted(blockers))
        raise fixture.BlockCannotRun(
            f"no bill can issue on this tenant. {len(blockers)} tax authority(ies) have "
            f"no 2200-series liability account — {named} — so BR-BIL-010/BR-BIL-069 "
            "refuse to stamp their tax line and EVERY bill breaks at issue. Map each one "
            "to a liability account on Settings > Taxes & fees, then load the sample data "
            "again. Nothing was billed."
        )
    return cycle_id


def _run_cycles(actor: Any, periods: tuple[dict[str, Any], ...]) -> int:
    """Bill each period given, returning bills ISSUED — CR-040 task C8."""
    cycle_id = _preconditions(actor)
    issued = 0
    problems: list[str] = []
    for period in periods:
        try:
            # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
            # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
            # (this block runs inside tenancy's per-module `atomic`), so without it the
            # work already done is lost at COMMIT. NOT tidiness — do not remove.
            with transaction.atomic():
                issued += _bill_one_period(actor, period, cycle_id)
        except fixture.BlockCannotRun as blocked:
            problems.append(str(blocked))
        except Exception as exc:  # noqa: BLE001 — the reason travels, not just the type
            logger.exception("sample data: billing %s failed", period["key"])
            problems.append(f"{period['key']}: {type(exc).__name__}: {exc}")
    if problems:
        # A PERIOD THAT DID NOT BILL IS A FAILED BLOCK, even when the other one
        # did (DEF-166). Reporting "OK, 48 rows" over a July that never issued
        # is the same green line over a real failure that this defect was.
        raise fixture.BlockCannotRun(" | ".join(problems))
    return issued


def seed_sample_records(actor: Any) -> int:
    """**CYCLE ONE.** June issued; the rest wait for the blocks after it.

    Idempotent (BR-TEN-063): `create_run` is keyed on (cycle, period) by
    BR-BIL-005, so a replay finds the existing run and issues nothing — the
    guarantee lives in the idempotency key rather than in a flag here.

    ⚠ **THIS SEAM USED TO BILL EVERY BILLED PERIOD, AND THERE WAS ONLY ONE.**
    CR-040 task C8 split it, because the PO's ordering puts money between the
    runs: *"first you will run first billing, then you will create payment
    record, refunds, credit over charges records, add meter reading for second
    month and then again run the billing"*. A single block billing both cycles
    back to back would produce the same ROWS and a different HISTORY — the
    second cycle would bill an estate that had never been paid, never been
    refunded and never been corrected, which is precisely the thing the second
    cycle exists to show.
    """
    return _run_cycles(actor, _periods_to_bill())


def seed_sample_second_cycle(actor: Any) -> int:
    """**CYCLE TWO** — CR-040 task C8, and the block order is the deliverable.

    It runs AFTER payments, so the estate it bills already carries June's
    collections, its credit balance, its refund and its overcharge correction.
    Same five phases, same doors, same idempotency key — the only difference is
    WHEN, and when is the whole requirement.

    **Empty is lawful and is reported, not raised.** A fixture that declares one
    billed period leaves this seam with nothing to bill; that is a fixture
    stating a shape, not a failure to seed. `_run_cycles` over an empty tuple
    returns 0 and the panel says the block wrote nothing.
    """
    return _run_cycles(actor, _second_cycle_periods())


def sample_invoice_ids() -> dict[str, list[str]]:
    """`{period_key: [invoice_id]}` for payments, so it never has to guess which
    bills the fixture issued. A published READ — payments does not query
    billing's tables."""
    out: dict[str, list[str]] = {}
    # ⚠ **EVERY billed period, not just the first cycle's** (CR-040 task C8).
    # Payments runs BETWEEN the two billing blocks, so at the moment it calls
    # this the second cycle has not run and its period answers `[]` — which is
    # correct rather than missing. Iterating the first cycle alone would make
    # this read permanently blind to cycle two for any later caller.
    for period in _billed_periods():
        rows = selectors.invoice_queryset().filter(
            bill_run__period_start=period["start"], bill_run__period_end=period["end"]
        )
        out[period["key"]] = [str(row.pk) for row in rows]
    return out


# ── CR-040 task D13 · the overcharge, corrected (spec §4 case 15) ───────────
# 🔒 HUMAN-REVIEW-PENDING — this block credits an issued bill in full and
# re-issues it for a different amount, which moves a customer's balance. Row in
# 12-governance/09-human-review-ledger.md.
def seed_sample_correction(actor: Any) -> int:
    """THE OVERCHARGE SEAM — `open_case` → `approve` → `execute`, class R.

    PO 2026-08-27: *"overcharge cases, creit cases"*. The corrections engine
    (EP-BIL-04, `correction_models.py`, `bulk_corrections.py`,
    `document_correction.py`) has existed since 2026-08-12 and **no fixture has
    ever driven it**, so the S30 case screen, the approval gate, the credit
    note and the rebill were all reachable only from a test.

    ⚠ **`BILLERR` IS NOT THE REASON THIS USES, AND CR-040's OWN STEP 3 SAID IT
    WAS.** That is corrected in the CR itself and restated here because it is
    exactly the kind of thing a reader assumes: **there are TWO unrelated reason
    vocabularies.** `BILLERR — Billing error correction` is a tenancy
    `reason_codes` row, which this engine never consults. The engine carries its
    own in `apps/billing/correction_reasons.py` — `wrong_read`,
    `wrong_rate_plan`, `charge_billed_in_error` … — each mapped to a correction
    CLASS, and BR-BIL-041 makes the operator pick the REASON while the system
    DERIVES the mechanism. So the fixture names `wrong_read`, class R, and
    **nothing here passes a mechanism**: `build_impact` refuses a caller that
    supplies one.

    ⚠ **THE READ IS CORRECTED FIRST, THROUGH METERING'S OWN DOOR, AND THAT IS
    THE WHOLE MECHANISM.** A class-R restatement RE-PRICES the bill from
    today's inputs (`corrections.recompute`) — it does not accept a delta from
    anyone. So a correction with nothing changed underneath it computes a delta
    of **exactly zero** and is refused by BR-BIL-043's neighbour as a case that
    changes nothing. `apps.metering.services.correct_billed_read` is
    BR-MET-053's ONLY door for a BILLED read: it supersedes the reading, writes
    the `read_corrections` linkage naming this invoice, and leaves the invoice
    untouched — the money half is this module's, which is the line this
    function then walks.

    ⚠ **AND JULY IS BILLED HIGHER BY THE SAME QUANTITY, WHICH IS CORRECT
    ARITHMETIC RATHER THAN A SIDE EFFECT.** A register read too high in June is
    corrected DOWN, and July's consumption is the delta FROM that corrected
    figure — so the customer is credited in June and billed the same units in
    July. That is what a real re-read does, and the second cycle running after
    this block is what makes it visible.

    Idempotent (BR-TEN-063): a case already exists for this invoice's chain, so
    a replay finds it and writes nothing. BR-BIL-048's partial unique index is
    the arbiter — one open case per chain — and the read correction is refused
    a second time because the original is no longer the lineage head.

    Returns the number of cases EXECUTED — 0 on a replay.
    """
    from apps.billing import bulk_corrections, correction_models, metering_seam

    spec = fixture.OVERCHARGE
    account_id = _account_for_unit(spec["unit_index"])
    if account_id is None:
        raise fixture.BlockCannotRun(
            "no correction was made: the sample accounts are not seeded, so the account whose "
            "June bill was over-read does not exist. The Accounts block above has to load first."
        )
    # ⚠ **THE REPLAY CHECK IS PER ACCOUNT, NOT PER INVOICE, AND THE DIFFERENCE
    # IS A BUG THIS LANE SHIPPED AND FIXED.** Executing a restatement moves the
    # original to `corrected` and issues a REBILL — a new invoice, on its own
    # `bill_type="rebill"` run carrying the SAME period. So on the second pass
    # the invoice lookup no longer finds the bill that was corrected (it is not
    # `issued` any more) and finds the REBILL instead, which no case has ever
    # touched. An invoice-keyed check answers "no" and the block corrects the
    # correction. Asking about the ACCOUNT is the question that stays true on
    # both passes (BR-TEN-063).
    if correction_models.CorrectionCaseBill.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id
    ).exists():
        return 0  # BR-TEN-063 — a replay corrects nothing twice
    invoice = _first_cycle_invoice_for_unit(spec["unit_index"])
    if invoice is None:
        raise fixture.BlockCannotRun(
            "no correction was made: the account that should carry an over-read June bill has "
            "no ISSUED bill. The first Bills block above is what issues it — fix that block "
            "and load again. A correction cannot exist before the bill it corrects."
        )

    read_ids = metering_seam.read_ids_on(invoice)
    if not read_ids:
        raise fixture.BlockCannotRun(
            "no correction was made: this bill's frozen snapshot names no meter read, so there "
            "is no reading to correct and a class-R restatement would re-price to the very same "
            "total. Refused rather than seeding a correction of $0.00, which is a case that "
            "changes nothing and would be refused downstream anyway (BR-BIL-043's neighbour)."
        )
    corrected = _correct_the_over_read(
        actor, read_id=read_ids[0], invoice=invoice, over_read_by=spec["over_read_by"], spec=spec
    )
    if corrected is None:
        raise fixture.BlockCannotRun(
            "no correction was made: `apps.metering.services.correct_billed_read` is not "
            "published, so the reading behind this bill cannot be superseded. Billing may not "
            "write `meter_reads` (B1 / BR-TEN-013) and does not. Without the read fix the "
            "money fix would re-price to the same total — BR-MET-053's own sentence, 'read fix "
            "and money fix travel together', read as a refusal rather than as a comment."
        )

    pin = _template_pin()
    if pin is None:
        raise fixture.BlockCannotRun(
            "no correction was made: a rebill pins a bill-template version (BR-BIL-026) and "
            "this tenant has none to pin. That is DEF-123's shape — fix the template seed "
            "rather than defaulting the pin, because a bill silently reprinted on a superseded "
            "layout is the failure hard-won law 3 is about."
        )
    template_id, template_version = pin

    case = bulk_corrections.open_case(
        reason_codes=(spec["reason_code"],),
        scope_kind=correction_models.SCOPE_SINGLE,
        scope={"invoice_ids": [str(invoice.pk)], "note": spec["note"]},
        invoices=(invoice,),
        actor=actor,
        as_of=spec["opened_on"],
    )
    bulk_corrections.approve(
        case,
        approver=actor,
        on_date=spec["approved_on"],
        preview_hash=case.preview_hash,
    )
    result = bulk_corrections.execute(
        case,
        issued_at=_instant(spec["executed_on"]),
        on_date=spec["executed_on"],
        template_id=template_id,
        template_version=template_version,
        actor=actor,
    )
    if result.failed:
        raise fixture.BlockCannotRun(
            "the correction case was opened and approved and its execution FAILED: "
            + " | ".join(reason for _invoice_id, reason in result.failed)
        )
    return len(result.succeeded)


def _account_for_unit(unit_index: int) -> Any:
    """The seeded account on a unit, through customers' published read (B1).

    `sample_account_ids()` is customers' own answer to *"which account is which
    awkward case"* — its docstring says so — and it is ASKED rather than
    inferred from a sort position.
    """
    try:
        # DEF-2795 · CLAUDE.md law 14 — a SAVEPOINT, so this `except` really can
        # continue. On PostgreSQL the failed statement aborts the WHOLE transaction
        # (this block runs inside tenancy's per-module `atomic`), so without it the
        # work already done is lost at COMMIT. NOT tidiness — do not remove.
        with transaction.atomic():
            from apps.customers import sample_data as customers_sample

            return customers_sample.sample_account_ids().get(unit_index)
    except Exception:  # noqa: BLE001 — the caller's refusal is honest, not silent
        logger.info("sample data: customers publishes no sample_account_ids map")
        return None


def _first_cycle_invoice_for_unit(unit_index: int) -> Any:
    """The FIRST cycle's issued bill for a seeded unit, or None.

    The first cycle deliberately, not the latest: a correction is written
    BETWEEN the two runs (task D14), so at the moment this block runs the
    second cycle does not exist yet — and naming the period rather than taking
    `.latest()` means this keeps meaning the same thing the day a third is
    added.
    """
    account_id = _account_for_unit(unit_index)
    if account_id is None:
        return None
    periods = _periods_to_bill()
    if not periods:
        return None
    return (
        models.Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            status__in=(models.INVOICE_ISSUED, models.INVOICE_PAID),
            bill_run__period_start=periods[0]["start"],
            bill_run__period_end=periods[0]["end"],
        )
        # A REBILL carries the SAME period on its own run (`execute_restatement`
        # creates one with `bill_type="rebill"`), so without this the lookup
        # would hand a replay the artifact of the correction it already made.
        # Excluded here as well as guarded above, because two ways of being
        # wrong about the same fact is one too many.
        .exclude(bill_run__bill_type="rebill")
        .order_by("created_at")
        .first()
    )


def _correct_the_over_read(
    actor: Any, *, read_id: Any, invoice: Any, over_read_by: Any, spec: dict[str, Any]
) -> Any:
    """Supersede the June reading through METERING's own service. None if unwired.

    BR-TEN-013: a cross-module write goes through the OWNING module's own
    service function and never through its ORM. `correct_billed_read` is that
    function and BR-MET-053 makes it the only door for a read a bill has
    already priced — it supersedes the reading, writes the `read_corrections`
    row naming this invoice, and touches no invoice at all.

    The new value is the stored register MINUS the fixture's over-read quantity,
    read back off the row rather than typed: the register value is the meter's,
    not the fixture's, and subtracting a QUANTITY from it keeps hard rule 3
    honest — a reading carries its unit and this never invents one.
    """
    from importlib import import_module

    try:
        metering_services = import_module("apps.metering.services")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    correct = getattr(metering_services, "correct_billed_read", None)
    if not callable(correct):
        return None
    read = _read_row_for(read_id)
    if read is None:
        return None
    current = Decimal(str(read["current_value"]))
    return correct(
        actor,
        read_id,
        {
            "reason": spec["note"],
            "value": str(current - Decimal(str(over_read_by))),
            "invoice_id": str(invoice.pk),
        },
    )


def _read_row_for(read_id: Any) -> dict[str, Any] | None:
    """One read, through metering's published selector (B1) — never its ORM.

    `read_chain` is the published read that answers for a single reading;
    billing has no selector of its own for `meter_reads` and must not grow one
    (B1 / G6). The chain is the lineage oldest-first, so the entry matching the
    id asked for is the one this bill priced.
    """
    from importlib import import_module

    try:
        metering_selectors = import_module("apps.metering.selectors")
    except ImportError:  # pragma: no cover
        return None
    chain = getattr(metering_selectors, "read_chain", None)
    if not callable(chain):
        return None
    for entry in chain(read_id):
        if str(entry.get("id")) == str(read_id):
            return entry
    return None


def remove_sample_records() -> dict[str, Any]:
    """BR-TEN-066 — and here the answer is "none, and here is exactly why".

    **An issued invoice is never deleted.** CLAUDE.md hard rule 4: *"no
    UPDATE/DELETE on issued invoices, invoice lines, payments, journal entries —
    corrections are new rows"*, and the database enforces it with triggers. So
    this returns `removed: 0` and NAMES what stays, which is BR-TEN-066's own
    instruction — *"remove what is free, report the rest BY NAME"* — rather than
    an empty success a utility would read as "the demo is gone".

    That is the price of BR-TEN-056's 2026-08-16 amendment, and it is stated on
    the Sample data panel so nobody discovers it. **A utility that wants a
    genuinely clean tenant creates a new one** — which is the Product Owner's own
    route: *"I dont have to do this - Drop and recreate the database; I can
    create a new Tenant and test it"*.
    """
    from apps.billing import correction_models

    invoices = selectors.invoice_queryset().count()
    # ⚠ CR-040 D13 — NAMED, because the correction is the newest thing here
    # that removal cannot touch and an unnamed retained row is exactly what
    # BR-TEN-066 exists to prevent. A correction's ARTIFACTS are an issued
    # credit note and an issued rebill, so deleting the case would leave two
    # bills nothing explains.
    cases = correction_models.CorrectionCase.objects.filter(tenant_id=_tenant_id()).count()
    if not invoices and not cases:
        return {"removed": 0, "retained": []}
    retained = []
    if invoices:
        retained.append(
            {
                "label": f"{invoices} issued bill(s) and their lines",
                "reason": (
                    "an issued bill, its lines, its payments and its journal entries can "
                    "never be changed or deleted — corrections are new rows (CLAUDE.md "
                    "hard rule 4, enforced by database triggers). The demo's bills stay. "
                    "For a genuinely empty tenant, create a new one"
                ),
            }
        )
    if cases:
        retained.append(
            {
                "label": f"{cases} correction case(s) and the credit notes and rebills they issued",
                "reason": (
                    "a correction case is the RECORD of why two issued bills exist — a credit "
                    "note reversing the original and a rebill for the corrected amount. Both "
                    "are append-only (hard rule 4), so removing the case would leave two "
                    "bills with nothing explaining them, which is worse than leaving all three"
                ),
            }
        )
    return {"removed": 0, "retained": retained}


def sample_record_count() -> int:
    """Bills the sample load issued. Counted from the RUNS the fixture created,
    so a bill the operator ran themselves is never counted as the demo's."""
    starts = [period["start"] for period in _periods_to_bill()]
    return int(
        selectors.invoice_queryset()
        .filter(bill_run__period_start__in=starts, status="issued")
        .count()
    )


def _unused() -> Any:  # pragma: no cover - keeps the models import honest
    return models


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane)
# checklist: A✔ B✔ C✔ D=deferred(the S8 Sample data panel serves this through tenancy's endpoints) E=deferred(same panel) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: BR-TEN-056 clause 1 is AMENDED (PO 2026-08-16 supersedes PO 2026-08-10) — the sample set now reaches invoices, and the rule doc carries the amendment with both quotes · the PRICE is stated rather than discovered: removal of issued bills is IMPOSSIBLE by hard rule 4, so `remove_sample_records` returns 0 and NAMES what stays · JULY AND AUGUST ARE DELIBERATELY NOT BILLED (CR-010 Part-10.4, PO 2026-08-17: "do 1 month billed na dkeep other month ready") — July is READY-TO-RUN with committed reads and is the Product Owner's own acceptance test; billing it here would delete the test · DEF-154 made every seeded bill print a $0.00 base charge until its fix; the figure is seeded where the RULE puts it (the plan) and the defect was not papered over
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
