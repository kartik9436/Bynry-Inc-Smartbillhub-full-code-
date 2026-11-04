# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check: every check on every account)
# Rules:    BR-BIL-1052 (every check on every account; per-account savepoint;
#           any error blocks only that account) · BR-BIL-1053 (payments at
#           Check) · BR-BIL-1025 (nothing to bill is not a problem) · CLAUDE.md
#           rule 3 · decision log 2026-09-30 *"A PROBLEM NEVER STOPS THE
#           CHECKING"* and *"THE ALTERNATIVE FOR EVERY STEP THAT USED TO STOP
#           AN ACCOUNT"*
# Plan:     15-bulk-bill-run-build-plan.md B7, B8, B11, B12, B21
# Tests:    06-backend/tests/test_bbr_check_engine.py ·
#           10-scripts/bbr_check_engine_pg_proof.py (PostgreSQL 16, law 14)
# ───────────────────────────────────────────────────────
"""The bulk bill run's CHECK — every check, on every account, every problem kept.

PO ruling 2026-09-30, verbatim: *"please start and ensure between step 1 and 2
for given account you runs allc heck sand dont stop at first problem"*.

WHAT CHANGED FROM THE PREPARE LOOP IT REPLACES
----------------------------------------------
`runs._prepare_run` used to stop an account at its FIRST problem: a dispute
hold `continue`d, the first `GatherProblem` `continue`d, so a clerk fixed one
problem and met the next on re-check (`DEF-BIL-8205`). A plain
`BillingRuleError` — a reading with no unit — ended the WHOLE pass
(`DEF-BIL-8206`, `8207`). Here:

  * **every check runs on every account**, each wrapped so that its failure is
    RECORDED as a finding and the next check still runs;
  * **each service is checked on its own** — when the gather refuses one
    service it is gathered again without it, so a second service's refusal is
    found in the same pass;
  * **each account runs inside its own savepoint, and each check inside its
    own nested one** (hard-won law 14): on PostgreSQL a failed statement
    aborts the whole transaction, and without the savepoint every later check
    — and every later ACCOUNT — would raise `InFailedSqlTransaction`. SQLite
    has no such state, so the default suite cannot show this; the proof is
    `10-scripts/bbr_check_engine_pg_proof.py`, run red with the savepoint
    removed. **Do not "simplify" the `transaction.atomic()` calls away.**
  * **an unexpected error blocks only that account**, under
    `check_failed_unexpectedly`, with a SUPPORT REFERENCE (`SBH-XXXXXXXX`)
    that is also in the log beside the traceback; the exception's own text
    never reaches a clerk.

THE PER-ACCOUNT CHECK ORDER
---------------------------
  C1 disputed reading (a TAG, never the end of the account — PO 2026-09-30)
  C2 readings (every covered unit; a unitless reading takes its meter's
     recorded unit with a warning, or blocks that service)
  C3 gather — account level, then each service on its own
  C4 mid-period split (only when C3 gathered cleanly)
  C5 decisions (missing read, base-only, continuity, not-in-service)
  C6 warnings on the gathered data (base $0.00, no agreements)
  C7 payment facts (payments' own seam, asked once per 500 accounts; level
     pay off track from billing's own budget rows, DEF-BIL-8241)
  C8 deposit not paid (the customers row already in hand)

An account is BLOCKED when any finding's severity is `blocks`, QUIET when the
gather found nothing to bill (BR-BIL-1025) and nothing blocks, READY otherwise.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.billing import bill_warnings, check_taxonomy, gather, midperiod, runs
from apps.billing.exceptions import BillingRuleError
from core import jobs as core_jobs

logger = logging.getLogger("smartbillhub.billing")

STATUS_READY = "ready"
STATUS_BLOCKED = "blocked"
STATUS_QUIET = "quiet"
STATUS_DECISION = "decision"
#: A READY account the clerk left out of this run (BR-BIL-1054). Never saved —
#: computed at read time from the account's live `left_out` decision, like
#: every other answer (`check_store._status`).
STATUS_LEFT_OUT = "left_out"

#: Gather refusals that name ONE service and leave the rest billable: the
#: account is gathered without it, and the clerk's accepted suggestion bills
#: the others (PO 2026-09-30, *"No price for a service — bill the other
#: services, hold that one"*).
NARROWABLE = frozenset({"plan_has_no_tariff_for_service"})

#: Decisions whose every choice keeps the account off THIS run's bills, so the
#: legacy lists keep them BLOCKED exactly as before: a disputed reading —
#: *"Hold until resolved"* (the default) or *"Bill on an estimate"*, whose
#: estimate this product cannot yet take at Check — is still BR-MET-024's hold.
#: The Check shows it as a decision (a tag, never the end of the checks).
NEVER_BILLED_UNTIL_RESOLVED = frozenset({"account_held_by_disputed_read"})

#: Accounts per payments-seam call (and per progress tick in the job). The
#: same figure `runs.ACCOUNT_CHUNK` streams the accounts in.
CHUNK = runs.ACCOUNT_CHUNK

#: The draft-warning key a unit taken from the meter rides on, so the DRAFT
#: says it too (bill_warnings' `{key, params}` shape).
UNIT_FROM_METER_KEY = "billing.run.warn.unitTakenFromMeter"


def new_support_ref() -> str:
    """`SBH-` + 8 hex characters: short enough to read down a phone line."""
    return "SBH-" + uuid.uuid4().hex[:8].upper()


@dataclass(frozen=True)
class Finding:
    """One problem on one account, under ONE tag."""

    code: str
    detail: str
    account_id: str | None = None
    account_no: str | None = None
    unit_id: str | None = None
    service_code: str | None = None
    params: dict[str, Any] | None = None
    support_ref: str | None = None
    message_key: str | None = None
    clerk_detail: str | None = None
    #: Where the finding came from: `decisions` (runs._decisions_for — the
    #: legacy S31.3 decision rows), `payments`, or `check`.
    origin: str = "check"
    #: Which CATEGORY of the registry recorded it (`CATEGORY_*`), so a partial
    #: re-check replaces exactly that category's saved rows (DEF-BIL-8286).
    step: str | None = None

    @property
    def tag(self) -> check_taxonomy.Tag:
        return check_taxonomy.classify(self.code)

    @property
    def severity(self) -> str | None:
        return self.tag.severity

    @property
    def category(self) -> str:
        return self.tag.category

    def as_problem(self) -> runs.AccountProblem:
        return runs.AccountProblem(
            reason=self.code,
            detail=self.detail,
            account_id=self.account_id,
            account_no=self.account_no,
            unit_id=self.unit_id,
            service_code=self.service_code,
            message_key=self.message_key,
            clerk_detail=self.clerk_detail,
            message_params=self.params or None,
        )

    def as_dict(self) -> dict[str, Any]:
        tag = self.tag
        return {
            "code": self.code,
            "category": tag.category,
            "severity": tag.severity,
            "fix": tag.fix,
            "label_key": tag.label_key,
            "service_code": self.service_code,
            "detail": self.clerk_detail or self.detail,
            "message_key": self.message_key,
            "params": dict(self.params or {}),
            "support_ref": self.support_ref,
        }


@dataclass
class AccountCheck:
    account_id: str
    account_no: str
    unit_id: str | None
    findings: list[Finding] = field(default_factory=list)
    data: Any = None
    unmeasured: tuple[str, ...] = ()
    quiet: bool = False
    plan_id: str | None = None
    covered_unit_ids: tuple[str, ...] = ()
    #: None for a full pass; for a partial one (DEF-BIL-8286) the categories it
    #: re-ran — the store keeps every other category's saved findings.
    rerun: frozenset[str] | None = None
    #: `accounts.kind` (regular / master) — the Ready list's filter and Sign
    #: off's *Who is billed* split (changes rows 37, 41).
    account_kind: str | None = None
    #: DEF-BIL-8491 — WHEN THIS ANSWER'S INPUTS WERE READ: the batch's read
    #: time (taken before its first read), or the moment `check_account` began
    #: when no batch is open. The store saves it as `checked_at`, so anything
    #: an owning module records after the read is newer than the stamp and the
    #: staleness sweep re-checks it.
    inputs_read_at: Any = None

    @property
    def status(self) -> str:
        """For the LEGACY lists (`PreparedRun`): blocked when anything blocks
        or when nothing could be gathered to bill from; quiet; else ready.
        The Check's own four-way status (ready / decision / blocked / quiet)
        is `check_status`, which knows the answers already given."""
        if any(f.severity == check_taxonomy.BLOCKS for f in self.findings):
            return STATUS_BLOCKED
        if self.quiet:
            return STATUS_QUIET
        if self.data is None or any(f.code in NEVER_BILLED_UNTIL_RESOLVED for f in self.findings):
            return STATUS_BLOCKED
        return STATUS_READY

    def first_blocking(self) -> Finding:
        for f in self.findings:
            if f.severity == check_taxonomy.BLOCKS:
                return f
        for f in self.findings:
            if f.code in NEVER_BILLED_UNTIL_RESOLVED:
                return f
        # Nothing BLOCKS, but nothing could be gathered to bill from: the
        # decision that stands in the way is the reason (e.g. no plan).
        return next(f for f in self.findings if f.severity == check_taxonomy.DECISION)

    def check_status(self, answered: set[str] | None = None) -> str:
        """ready / decision / blocked / quiet — *"An account is Ready when
        every problem on it is a warning or has an accepted decision; one
        blocked problem sends it to Not in this run."* `answered` is the set
        of cases this account has an answer for (its own or its tag's)."""
        # DEF-BIL-10200 — `decisions.DEFAULT_ANSWERS` (a late fee bills unless
        # waived) answers its case when nobody did.
        from apps.billing import decisions

        answered = set(answered or set()) | set(decisions.DEFAULT_ANSWERS)
        if any(f.severity == check_taxonomy.BLOCKS for f in self.findings):
            return STATUS_BLOCKED
        if self.quiet:
            return STATUS_QUIET
        if any(
            f.severity == check_taxonomy.DECISION and f.code not in answered for f in self.findings
        ):
            return STATUS_DECISION
        return STATUS_READY

    def quiet_problem(self) -> runs.AccountProblem:
        return runs.AccountProblem(
            reason=runs.RUN_NOTHING_TO_BILL,
            detail=(
                f"account {self.account_no} covers no unit and its address holds no "
                "unoccupied unit to charge for, so there is nothing to bill it for this "
                "period. That is the correct state for an owner's account at an address "
                "he occupies himself, and it produces no document (BR-BIL-1024)."
            ),
            account_id=self.account_id,
            account_no=self.account_no,
            unit_id=None,
        )

    def decision_problems(self) -> list[runs.AccountProblem]:
        """The legacy `PreparedRun.decisions` rows: `_decisions_for`'s own, plus
        the payment DECISIONS (BR-BIL-1053)."""
        return [
            f.as_problem()
            for f in self.findings
            if f.origin == "decisions" or f.severity == check_taxonomy.DECISION
        ]

    def warning_problems(self) -> list[runs.AccountProblem]:
        return [
            f.as_problem()
            for f in self.findings
            if f.severity == check_taxonomy.WARNING and f.origin != "decisions"
        ]


@dataclass
class CheckContext:
    """What every account in one pass shares — resolved once."""

    period_start: date
    period_end: date
    price_date: date
    cycle_days: int
    scope_services: tuple[str, ...] | None
    payment_window: tuple[date | None, date | None] | None
    dispute_holds: Any
    service_universe: tuple[str, ...]
    payment_facts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    unavailable: tuple[dict[str, str], ...] = ()
    #: The tenant's budget settings for *Level pay off track* (DEF-BIL-8241),
    #: read ONCE per pass; None when they cannot be read, which is declared on
    #: `unavailable` rather than read as *no drift anywhere*.
    level_pay: dict[str, Any] | None = None
    #: DEF-BIL-8491 — the open batch's read time; None outside `batches`.
    read_at: Any = None
    #: 🔒 DEF-BIL-10200 — the batch's late-fee facts (`late_fee_run`), read
    #: with the payment facts; None when the pass asks no payments.
    late_fees: Any = None

    @classmethod
    def for_pass(
        cls,
        *,
        period_start: date,
        period_end: date,
        price_date: date,
        cycle_days: int,
        scope_services: tuple[str, ...] | None,
        payment_window: tuple[date | None, date | None] | None,
    ) -> "CheckContext":
        codes = gather._resolve("tenancy", "service_ids_by_code")
        try:
            universe = tuple(sorted((codes() or {}).keys())) if codes else ()
        except Exception:  # noqa: BLE001 — the retry loop degrades, never breaks
            universe = ()
        unavailable: tuple[dict[str, str], ...] = ()
        level_pay: dict[str, Any] | None = None
        if payment_window is not None:
            from apps.billing import check_payments_seam, level_pay_check

            unavailable = check_payments_seam.unavailable_facts()
            level_pay = level_pay_check.settings()
            if level_pay is None:
                unavailable += (dict(level_pay_check.SETTINGS_UNREADABLE),)
        return cls(
            period_start=period_start,
            period_end=period_end,
            price_date=price_date,
            cycle_days=cycle_days,
            scope_services=scope_services,
            payment_window=payment_window,
            # BR-MET-024 — resolved ONCE: an unpublished seam is a property of
            # the deployment (and still HOLDS every account, `_dispute_hold_for`).
            dispute_holds=runs._resolve("metering", "dispute_holds_for_unit"),
            service_universe=universe,
            unavailable=unavailable,
            level_pay=level_pay,
        )

    def load_payment_facts(self, accounts: list[Any]) -> None:
        """Ask payments ONCE for this chunk (B12). A payments module that does
        not answer is a utility-wide stop — it would otherwise read as *no
        payment problems anywhere*, which is the silent zero DEF-046 taught."""
        self.payment_facts = {}
        if self.payment_window is None or not accounts:
            return
        from apps.billing import check_payments_seam

        bill_date, due_date = self.payment_window
        try:
            self.payment_facts = check_payments_seam.payment_facts_for_accounts(
                [a.id for a in accounts],
                period_end=self.period_end,
                bill_date=bill_date,
                due_date=due_date,
            )
        except BillingRuleError:
            raise
        except Exception as broken:  # noqa: BLE001 — B21
            core_jobs.reraise_if_time_limit(broken)
            raise runs.UtilityWideStop.from_error(runs.MODULE_PAYMENTS, broken) from broken
        # DEF-BIL-8241 — *Level pay off track* is BILLING's own fact (its
        # budget status and issued bills), so it is read here and not through
        # the payments seam, and it joins the chunk's facts AFTER payments' own
        # so the Payments & balances category raises it with them.
        if self.level_pay is not None:
            from apps.billing import level_pay_check

            for account_id, code, params in level_pay_check.level_pay_off_track(
                [a.id for a in accounts], config=self.level_pay
            ):
                self.payment_facts.setdefault(str(account_id), []).append(
                    {"code": code, "params": params}
                )
        self.load_late_fees(accounts)

    def load_late_fees(self, accounts: list[Any]) -> None:
        """🔒 DEF-BIL-10200 — the batch's late-fee facts, read ONCE (billing's
        own bills, payments' receipts and live plans). As of the run's BILL
        DATE: the date this run's bills carry and the day it looks from. A
        payments module that cannot say what met the bills is DECLARED on
        `unavailable`, never read as *nothing overdue anywhere*."""
        self.late_fees = None
        bill_date = self.payment_window[0] if self.payment_window else None
        if bill_date is None or not accounts:
            return
        from apps.billing import late_fee_run

        self.late_fees = late_fee_run.load_inputs(
            [a.id for a in accounts],
            as_of=bill_date,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        if self.late_fees.unavailable and late_fee_run.RECEIPTS_UNAVAILABLE not in self.unavailable:
            self.unavailable += (dict(late_fee_run.RECEIPTS_UNAVAILABLE),)


    def batches(
        self, accounts: Iterable[Any], *, payments: bool = True, size: int | None = None
    ) -> Iterator[list[Any]]:
        """B27 — the accounts in batches of `CHUNK` (500), each batch READ ONCE.

        For every batch, in this order and before its first account is checked:

          1. the READ TIME is taken (`read_at`, DEF-BIL-8491) — every result of
             the batch is saved stamped with it, so a payment, reading, meter or
             plan recorded after it is newer than the stamp and the sweep
             re-checks that account;
          2. a batch memo is opened (`core.batch_reads`) for this tenant, so a
             read every account asks identically — a tax row, a rate tier, a
             charge code — is asked once, and each account's repeated
             questions are asked once;
          3. payments are asked ONCE for the batch (B12, unchanged) when the
             pass asks payments at all;
          4. the owning modules answer the batch's OWN rows in one query set
             each (`_load_batch`): meters, readings, service points, agreements,
             previous bills.

        The memo is closed when the batch ends — by the next batch, by the
        loop finishing, or by an exception — and never outlives the pass (the
        `seam_batch` ruling: a memo inside one computation, never a stored
        answer). Payments not answering is still a UTILITY-WIDE stop (B21,
        unchanged); an own-rows loader that fails is skipped (`_load_batch`).
        """
        from core import batch_reads

        for chunk in chunks(accounts, size or CHUNK):
            with batch_reads.batch() as opened:
                self.read_at = opened.read_at
                try:
                    if payments:
                        self.load_payment_facts(chunk)
                    _load_batch(self, chunk)
                    yield chunk
                finally:
                    self.read_at = None


def _load_batch(ctx: CheckContext, accounts: list[Any]) -> None:
    """Ask each OWNING module for this batch's own rows, one query set each.

    Every loader is the owning module's own batch read; it primes the batch
    memo with exactly the answers its per-account read would give, so the
    checks read the same facts they always read (`test_b27_batch_reads`
    compares the two on a mixed seed).

    ⚠ **A LOADER THAT FAILS IS SKIPPED, NOT A STOP, AND THAT IS WHAT KEEPS THE
    BEHAVIOUR IDENTICAL.** A loader only saves statements: with nothing primed,
    each account's own read asks the database exactly as before and, if the
    fault is real, records it on THAT account as the per-account pass always
    did. Each loader runs in its own savepoint (hard-won law 14) so a failed
    statement cannot poison the batch's transaction, and the failure is
    logged, because a loader that silently never primes is a slow pass that
    looks like a fast one."""
    if not accounts:
        return
    from apps.billing import batch_seams

    batch_seams.load(accounts, ctx)


def chunks(accounts: Iterable[Any], size: int = CHUNK) -> Iterator[list[Any]]:
    batch: list[Any] = []
    for account in accounts:
        batch.append(account)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# ── the guard every check runs inside ───────────────────────────────────────
class _Guard:
    """Runs one check; records its failure as a finding; never lets it escape.

    ⚠ `transaction.atomic()` here is a SAVEPOINT and it is the only thing that
    lets the NEXT check run on PostgreSQL after this one's statement failed
    (law 14). A `UtilityWideStop` is the one thing that does escape: it is not
    this account's problem.
    """

    def __init__(self, check: AccountCheck) -> None:
        self.check = check

    def finding(self, code: str, detail: str, **extra: Any) -> Finding:
        found = Finding(
            code=code,
            detail=detail,
            account_id=self.check.account_id,
            account_no=self.check.account_no,
            unit_id=self.check.unit_id,
            **extra,
        )
        self.check.findings.append(found)
        return found

    def from_problem(self, problem: gather.GatherProblem) -> Finding:
        return self.finding(
            problem.reason,
            str(problem),
            service_code=problem.service_code,
            message_key=getattr(problem, "message_key", None),
            clerk_detail=getattr(problem, "clerk_detail", None),
            params=getattr(problem, "message_params", None) or None,
        )

    def run(self, fn: Any, *, catch_gather: bool = True) -> tuple[bool, Any]:
        try:
            with transaction.atomic():
                return True, fn()
        except runs.UtilityWideStop:
            raise
        except gather.GatherProblem as problem:
            if not catch_gather:
                raise
            self.from_problem(problem)
        except BillingRuleError as refusal:
            self.finding(check_taxonomy.CHECK_REFUSED, str(refusal))
        except Exception as broken:  # noqa: BLE001 — BR-BIL-1052: never the run
            core_jobs.reraise_if_time_limit(broken)
            ref = new_support_ref()
            logger.exception(
                "bill run check: account %s failed unexpectedly — ref %s",
                self.check.account_no,
                ref,
            )
            self.finding(
                check_taxonomy.CHECK_FAILED,
                f"account {self.check.account_no} could not be checked. Support reference {ref}.",
                support_ref=ref,
                message_key="billing.check.failed",
                params={"support_ref": ref},
            )
        return False, None


def check_account(
    account: Any,
    context: CheckContext,
    *,
    covered_unit_ids: tuple[str, ...] | None = None,
    categories: Iterable[str] | None = None,
    was_quiet: bool = False,
) -> AccountCheck:
    """Every check, on ONE account, inside its own savepoint. Never raises for
    an account's own problem; only `runs.UtilityWideStop` escapes.

    `categories` (DEF-BIL-8286) re-runs only those categories and everything
    downstream of them; the answer then carries only their findings and
    `rerun` says which, so the store merges rather than replaces. None — every
    caller before the registry — is the full pass, unchanged."""
    rerun = None if categories is None else downstream(categories)
    if rerun is not None and rerun >= ALL_CATEGORIES:
        rerun = None
    check = AccountCheck(
        account_id=str(account.id),
        account_no=account.account_no,
        unit_id=str(account.unit_id) if getattr(account, "unit_id", None) else None,
        covered_unit_ids=tuple(covered_unit_ids or ()),
        rerun=rerun,
        account_kind=getattr(account, "kind", None),
        # DEF-BIL-8491 — taken BEFORE the first read of this account.
        inputs_read_at=context.read_at or timezone.now(),
    )
    guard = _Guard(check)
    # Changes row 44 — inside this pass a missing meter multiplier is put to the
    # clerk (`runs.METER_HAS_NO_MULTIPLIER`) rather than refused as a block.
    in_check = runs.open_check_pass()
    try:
        with transaction.atomic():
            _run_categories(
                _Pass(account=account, ctx=context, check=check, guard=guard), rerun, was_quiet
            )
    except runs.UtilityWideStop:
        raise
    except Exception as broken:  # noqa: BLE001 — the account savepoint itself
        core_jobs.reraise_if_time_limit(broken)
        ref = new_support_ref()
        logger.exception("bill run check: account %s aborted — ref %s", check.account_no, ref)
        guard.finding(
            check_taxonomy.CHECK_FAILED,
            f"account {check.account_no} could not be checked. Support reference {ref}.",
            support_ref=ref,
            message_key="billing.check.failed",
            params={"support_ref": ref},
        )
        # The aborted category's own name is unknown here; on a partial pass the
        # failure belongs to the first category re-run, so the store replaces it
        # on the next re-check of that category.
        first = next((c.name for c in REGISTRY if rerun is None or c.name in rerun), None)
        check.findings[-1] = replace(check.findings[-1], step=first)
        check.data = None
    finally:
        runs.close_check_pass(in_check)
    return check


def _account_period_start(account: Any, ctx: CheckContext) -> date:
    """🔒 WHERE THIS ACCOUNT'S BILL STARTS — PO rulings 2026-09-30, fixed-charge
    cases 3 and 4 (`07-billing/16-check-decisions-next-bill.md` §2).

      * **Overlap** (case 4, *"A Start this account's bill the day after its
        last bill"*): the account's last issued bill already covers the start
        of this period, so its bill starts the day after — last bill to Sep 30,
        run Sep 15 – Oct 14 → Oct 1–14 — and B4.3's frozen `service_days /
        cycle_days` factor prorates the base ($8 × 14/30 = $3.73). Nothing
        new computes money; the days simply stop being counted twice.
      * **Held** (case 3, *"The next bill starts the day after that account's
        last bill, - 1 base charge only"*): the account was HELD or left for a
        later cycle in a run inside the gap, so its bill starts the day after
        its last bill (Sep 1 – Oct 31) and bills all usage since. ONE base:
        `gather._service_days` already caps the count at the cycle's days.

    Any OTHER gap is left exactly as it was — the calendar is genuinely
    ambiguous there (a service switched off, a cycle that moved) and the PO's
    2026-09-14 ruling makes it a clerk's question (`billing_continuity`). A
    last bill that covers the WHOLE period is not shortened either: there is
    nothing left to bill, and the overlap is put to the clerk with Hold only.
    """
    window = runs.last_issued_window(account.id)
    if window is None:
        return ctx.period_start
    anchor = runs.anchor_from(window[1], period_start=ctx.period_start)
    after_last = window[1] + runs.ONE_DAY
    if anchor.state == runs.CONTINUITY_OVERLAP and after_last <= ctx.period_end:
        return after_last
    if anchor.state == runs.CONTINUITY_GAP and runs.held_in(
        account.id, first_day=after_last, before=ctx.period_start
    ):
        return after_last
    return ctx.period_start


# ══════════════════════════════════════════════════════════════════════════
# THE CATEGORY REGISTRY (DEF-BIL-8286, 2026-09-30)
# ══════════════════════════════════════════════════════════════════════════
# Until this registry the whole per-account pass was ONE 230-line function,
# `_check_all`, so no single category could be called on its own — not by a
# Fix / Re-check that touched one fact, not by the Check report, not by the
# one-time bill. It is now five functions over one shared `_Pass`, run in a
# FIXED order by the loop in `_run_categories`. The order and every line of
# behaviour are the ones `_check_all` had (proved by every `test_bbr_*` test,
# unchanged): account → services → decisions → warnings → payments.
#
# WHAT "DOWNSTREAM" MEANS HERE. Each category names the categories whose
# OUTPUT it reads (`after`). A fix re-runs the category it touched and every
# category downstream of it; the categories UPSTREAM of those are run again
# only to rebuild their output (the readings a gather needs, the gathered data
# a decision reads) and their findings are thrown away, because the store
# keeps the ones it already has. Worked:
#
#   * a payment posted → `payments` only. No reading is read, nothing is
#     gathered — the one payments-seam query per chunk, instead of the ~137 ms
#     gather per account a full re-check costs;
#   * a plan chosen, a size set → `services` + `decisions` + `warnings`
#     (`account` rebuilt as input), `payments` NOT re-run;
#   * a reading corrected → `account` and everything that reads it.
#
# A QUIET account (BR-BIL-1025 — nothing to bill) runs nothing after
# `services`, exactly as `_check_all`'s early `return` did; a partial pass that
# does not re-run `services` keeps the quiet it was saved with (`was_quiet`).

CATEGORY_ACCOUNT = "account"
CATEGORY_SERVICES = "services"
CATEGORY_DECISIONS = "decisions"
CATEGORY_WARNINGS = "warnings"
CATEGORY_PAYMENTS = "payments"


@dataclass
class _Pass:
    """What one account's categories hand each other within one pass."""

    account: Any
    ctx: CheckContext
    check: AccountCheck
    guard: _Guard
    readings: tuple[Any, ...] = ()
    unmeasured: tuple[str, ...] = ()
    readings_ok: bool = False
    taken: list[dict[str, Any]] = field(default_factory=list)
    data: Any = None
    refused: list[Finding] = field(default_factory=list)
    #: Set by `services` when the account is QUIET — nothing after it runs.
    stopped: bool = False


def _check_account_level(p: _Pass) -> None:
    """ACCOUNT — the account's own period start, a disputed reading (C1), and
    its readings (C2), with a unitless reading put to the clerk as a decision."""
    account, check, guard = p.account, p.check, p.guard
    # The account's OWN period start (fixed-charge cases 3 and 4). Every check
    # below reads the period off `ctx`, so a shifted start is one replacement.
    ok, start = guard.run(lambda: _account_period_start(account, p.ctx))
    if ok and start != p.ctx.period_start:
        p.ctx = replace(p.ctx, period_start=start)
    ctx = p.ctx

    # C1 — a disputed reading is a TAG and never the end of the account's
    # checks (PO 2026-09-30, item 1).
    def disputes() -> None:
        held = runs._dispute_hold_for(
            ctx.dispute_holds, account, unit_ids=check.covered_unit_ids or None
        )
        if held is not None:
            guard.finding(held.reason, held.detail, service_code=held.service_code)

    guard.run(disputes)

    # C2 — readings, with the unit-from-meter collector open (PO 2026-09-30,
    # item 2). A refused reading leaves `readings` empty and C3 still runs.
    readings: tuple[Any, ...] = ()
    unmeasured: tuple[str, ...] = ()
    token = runs.open_unit_from_meter()
    try:
        ok, answer = guard.run(
            lambda: runs.readings_for_account(
                account,
                period_start=ctx.period_start,
                period_end=ctx.period_end,
                scope_services=ctx.scope_services,
                anchor_to_last_billed=True,
            )
        )
        taken = runs.taken_units()
    finally:
        runs.close_unit_from_meter(token)
    p.readings_ok = ok
    if ok:
        readings, unmeasured = answer
    else:
        # The readings were refused (an anchor or a unit problem), and the
        # account will not be billed from this pass. The plan and tariff checks
        # below still need to know WHICH meters stand on each service — gathered
        # with no readings at all, R3 reports *"the unit has no meter"*, a false
        # blocker. So they get metering's own figures, un-anchored, as a PROBE:
        # never billed (`readings_ok` stays False), never a finding of its own.
        # 🔒 DEF-BIL-9076 — un-anchored, a rollover inside the period now
        # HOLDS a reading (the question the anchor asks in the billed pass).
        # The probe bills nothing and only needs the meters, so it passes the
        # rollover rather than turning the anchored refusal above into a false
        # *"the unit has no meter"*; the finding that stops the bill is the
        # anchored pass's own.
        probe_token = runs.open_answers(
            {**(runs._ANSWERS.get() or {}), ("*", "", runs.POSSIBLE_ROLLOVER): runs.ANSWER_ACCEPT}
        )
        try:
            with transaction.atomic():
                readings, _probe_unmeasured = runs.readings_for_account(
                    account,
                    period_start=ctx.period_start,
                    period_end=ctx.period_end,
                    scope_services=ctx.scope_services,
                    anchor_to_last_billed=False,
                )
        except Exception:  # noqa: BLE001 — a probe that fails leaves ()
            readings = ()
        finally:
            runs.close_answers(probe_token)
    for row in taken:
        # PO 2026-09-30 (rows 45–46): a DECISION with the meter's unit as the
        # SUGGESTION — the pass carries it so every other check can run, and
        # `decisions.apply_decisions` bills nobody on it until it is accepted.
        check.findings.append(
            Finding(
                code=check_taxonomy.READ_HAS_NO_UNIT,
                detail=(
                    f"account {check.account_no}: the {row['service_code']} reading has no "
                    f"unit; its meter records {row['unit']}."
                ),
                account_id=check.account_id,
                account_no=check.account_no,
                unit_id=check.unit_id,
                service_code=row["service_code"],
                params={
                    "found": {"meter_unit": row["unit"]},
                    "suggested": {"unit": row["unit"]},
                },
                message_key="billing.check.suggest.meterUnit",
                origin="decisions",
            )
        )
    check.unmeasured = unmeasured
    p.readings, p.unmeasured, p.taken = readings, unmeasured, list(taken)


def _check_services(p: _Pass) -> None:
    """SERVICES — the unit's plan, the gather (account level, then each service
    on its own, C3), nothing-to-bill (BR-BIL-1025), and the mid-period split
    (C4). Sets what this account would bill (`check.data`)."""
    account, ctx, check, guard = p.account, p.ctx, p.check, p.guard

    # The unit's plan, recorded even when the gather refuses — it is what the
    # staleness sweep matches a Plans & Rates change against (OQ-843, option
    # C: *"re-check an account when its plan … changes"*).
    def plan_of_unit() -> None:
        unit_row = gather._resolve("metering", "unit_row")
        unit_id = check.unit_id or (check.covered_unit_ids[0] if check.covered_unit_ids else None)
        if unit_row is not None and unit_id:
            plan = getattr(unit_row(unit_id), "rate_plan_id", None)
            check.plan_id = str(plan) if plan else None

    guard.run(plan_of_unit)

    # C3 — gather: account level, then each service on its own.
    used = runs.open_multiplier_one_used()
    try:
        data, refused = _gather_every_service(account, ctx, check, guard, p.readings)
        multiplier_one = runs.multiplier_one_used()
    finally:
        runs.close_multiplier_one_used(used)
    # Changes row 44 — a clerk's *Bill with multiplier 1* lets the gather
    # through, and the decision stays on the account, ANSWERED, so a Re-check
    # never loses it (the tag, the report and Calculate all still see it).
    for service in multiplier_one:
        check.findings.append(
            Finding(
                code=runs.METER_HAS_NO_MULTIPLIER,
                detail=f"account {check.account_no}: {service} meter has no multiplier.",
                account_id=check.account_id,
                account_no=check.account_no,
                unit_id=check.unit_id,
                service_code=service,
                params={"service_code": service},
                origin="decisions",
            )
        )
    p.refused = refused
    if refused and _nothing_to_bill(account, check, refused):
        # BR-BIL-1025 — examined and QUIET, not a fault. The refusals that
        # classifier explains are withdrawn; anything else stays.
        check.findings = [f for f in check.findings if f not in refused]
        check.quiet = True
        p.stopped = True
        return

    if data is not None and p.readings_ok and all(f.code in NARROWABLE for f in refused):
        # C4 — BR-RAT-114's split, attached exactly where the old loop did.
        # PO 2026-09-30 (rows 44–46): a price or plan change inside the period
        # is a DECISION — suggestion: the whole period at the PERIOD-END
        # version (what `data` was gathered at, `ctx.price_date`); or split at
        # the change (BR-RAT-114's segments, when they can be priced); or Hold.
        before = len(check.findings)
        ok, split = guard.run(
            lambda: midperiod.gather_split(
                account,
                period_start=ctx.period_start,
                period_end=ctx.period_end,
                cycle_days=ctx.cycle_days,
                scope_services=ctx.scope_services,
            ),
            catch_gather=True,
        )
        refusal = check.findings[before:]
        if ok and split:
            data = replace(data, split_segments=split)
        if (ok and split) or (
            not ok and refusal and refusal[-1].code != check_taxonomy.CHECK_FAILED
        ):
            # A split that could not be priced leaves only the suggestion and
            # Hold; its own refusal is replaced by the decision it now is.
            if not ok:
                check.findings = check.findings[:before]
            check.findings.append(
                Finding(
                    code=check_taxonomy.PRICE_CHANGED_MID_PERIOD,
                    detail=(
                        f"account {check.account_no}: a price or plan changes inside "
                        f"{ctx.period_start} – {ctx.period_end}."
                    ),
                    account_id=check.account_id,
                    account_no=check.account_no,
                    unit_id=check.unit_id,
                    params={
                        "found": {"segments": len(split or ()), "split_priceable": bool(ok)},
                        "suggested": {"price_date": ctx.price_date.isoformat()},
                    },
                    message_key="billing.check.suggest.periodEndPrice",
                    origin="decisions",
                )
            )
        elif not ok:
            data = None

    if data is not None and p.taken:
        data = replace(
            data,
            warnings=bill_warnings.merged(
                getattr(data, "warnings", ()) or (),
                tuple(
                    {
                        "key": UNIT_FROM_METER_KEY,
                        "params": {"service_code": r["service_code"], "unit": r["unit"]},
                    }
                    for r in p.taken
                ),
            ),
        )
    if data is not None:
        check.plan_id = str(getattr(data, "rate_plan_id", "") or "") or check.plan_id
    # A narrowed gather that followed a NON-narrowable refusal exists only to
    # find the account's OTHER decisions and warnings; it is never billed from.
    # Kept when every refusal was a NARROWABLE one (bill the other services);
    # any other refusal leaves nothing to bill from.
    p.data = data
    billable = p.readings_ok and all(f.code in NARROWABLE for f in refused)
    check.data = data if billable else None


def _check_decisions(p: _Pass) -> None:
    """DECISIONS — C5, the legacy S31.3 decision rows from the gathered data."""
    check = p.check
    if p.data is None:
        return
    data, unmeasured = p.data, p.unmeasured
    ok, rows = p.guard.run(lambda: runs._decisions_for(data, unmeasured))
    for problem in rows or ():
        check.findings.append(
            Finding(
                code=problem.reason,
                detail=problem.detail,
                account_id=check.account_id,
                account_no=check.account_no,
                unit_id=check.unit_id,
                service_code=problem.service_code,
                origin="decisions",
                # DEF-BIL-8472 — a decision's facts (a continuity row's state)
                # are saved with it, so the served row can offer its own answers.
                params=dict(getattr(problem, "message_params", None) or {}),
            )
        )


def _check_warnings(p: _Pass) -> None:
    """WARNINGS — C6, the warnings the drafts carry, on the findings too
    (DEF-BIL-8210)."""
    check = p.check
    if p.data is None:
        return
    for warning in runs.account_warnings(p.data):
        code = check_taxonomy.warning_code(warning)
        if code == check_taxonomy.READ_HAS_NO_UNIT:
            continue  # already recorded from C2, as a decision
        params = dict(warning.get("params") or {})
        p.guard.finding(
            code,
            f"account {check.account_no}: {code.replace('_', ' ')}.",
            service_code=params.get("service_code") or params.get("service"),
            message_key=warning.get("key"),
            params=params,
        )


def _check_payments(p: _Pass) -> None:
    """PAYMENTS & BALANCES — C7 (the chunk's one payments-seam answer,
    BR-BIL-1053) and C8 (a deposit assessed and not taken)."""
    account, check, guard = p.account, p.check, p.guard
    for fact in p.ctx.payment_facts.get(check.account_id, ()):
        check.findings.append(
            Finding(
                code=fact["code"],
                detail=f"account {check.account_no}: {fact['code'].replace('_', ' ')}.",
                account_id=check.account_id,
                account_no=check.account_no,
                unit_id=check.unit_id,
                params=dict(fact.get("params") or {}),
                origin="payments",
            )
        )

    # C8 — a deposit assessed and not taken (customers' own two columns).
    def deposit() -> None:
        assessed = _decimal(getattr(account, "deposit_assessed", None))
        taken_amount = _decimal(getattr(account, "deposit_on_file", None)) or Decimal("0")
        if assessed is not None and assessed > taken_amount:
            guard.finding(
                check_taxonomy.PAY_DEPOSIT_NOT_PAID,
                f"account {check.account_no}: a deposit of {assessed} was assessed and "
                f"{taken_amount} has been taken.",
                params={"assessed": str(assessed), "taken": str(taken_amount)},
            )

    guard.run(deposit)

    # 🔒 DEF-BIL-10200 — the late fee the bill run adds (decision log
    # 2026-10-17). ONE finding per account per run, carrying the figure; the
    # clerk's only answer is Waive, per account (BR-BIL-003), and an
    # unanswered one bills (`decisions.DEFAULT_ANSWERS`).
    def late() -> None:
        inputs = p.ctx.late_fees
        plan_id = getattr(p.data, "rate_plan_id", None) or check.plan_id
        if inputs is None or not plan_id:
            return
        from apps.billing import late_fee, late_fee_run

        try:
            found = late_fee_run.assess_account(
                inputs,
                check.account_id,
                rate_plan_id=plan_id,
                customer_class=gather._customer_class(account),
            )
        except (late_fee.LateFeePlanUnreadable, late_fee.LateFeeClassNotPriced) as refused:
            raise BillingRuleError(str(refused)) from refused
        if found is None:
            return
        guard.finding(
            late_fee_run.LATE_FEE_CASE,
            f"account {check.account_no}: a late fee of {found.amount} on "
            f"{found.overdue} overdue.",
            message_key=late_fee_run.FOUND_KEY,
            params=found.params(),
            origin="payments",
        )

    guard.run(late)


@dataclass(frozen=True)
class CheckCategory:
    """One category of checks: its name, its function, and the categories
    whose OUTPUT it reads."""

    name: str
    run: Any
    after: tuple[str, ...] = ()


#: THE ORDER IS THE BEHAVIOUR — the loop runs these top to bottom, and it is
#: the order `_check_all` ran them in.
REGISTRY: tuple[CheckCategory, ...] = (
    CheckCategory(CATEGORY_ACCOUNT, _check_account_level),
    CheckCategory(CATEGORY_SERVICES, _check_services, after=(CATEGORY_ACCOUNT,)),
    CheckCategory(CATEGORY_DECISIONS, _check_decisions, after=(CATEGORY_SERVICES,)),
    CheckCategory(CATEGORY_WARNINGS, _check_warnings, after=(CATEGORY_SERVICES,)),
    CheckCategory(CATEGORY_PAYMENTS, _check_payments),
)
CATEGORIES: dict[str, CheckCategory] = {c.name: c for c in REGISTRY}
ALL_CATEGORIES: frozenset[str] = frozenset(CATEGORIES)


def downstream(names: Iterable[str]) -> frozenset[str]:
    """`names` and every category that reads (transitively) from one of them."""
    names = tuple(names)
    unknown = set(names) - set(CATEGORIES)
    if unknown:
        raise ValueError(f"unknown check categories: {sorted(unknown)}")
    out = set(names)
    grew = True
    while grew:
        grew = False
        for c in REGISTRY:
            if c.name not in out and any(a in out for a in c.after):
                out.add(c.name)
                grew = True
    return frozenset(out)


def upstream(names: Iterable[str]) -> frozenset[str]:
    """Every category whose output `names` needs, transitively (not `names`)."""
    names = tuple(names)
    need: set[str] = set()
    stack = [a for n in names for a in CATEGORIES[n].after]
    while stack:
        one = stack.pop()
        if one not in need:
            need.add(one)
            stack.extend(CATEGORIES[one].after)
    return frozenset(need - set(names))


def _stamp(check: AccountCheck, start: int, name: str) -> None:
    """Mark every finding a category recorded with that category's name, so a
    later partial re-check replaces exactly those rows (`check_store`).

    A category only ever APPENDS findings or withdraws ones IT recorded (quiet
    withdraws its own refusals, a split replaces its own), so everything before
    `start` is untouched and everything from `start` on is this category's."""
    for i in range(start, len(check.findings)):
        if check.findings[i].step is None:
            check.findings[i] = replace(check.findings[i], step=name)


def _run_categories(p: _Pass, rerun: frozenset[str] | None, was_quiet: bool) -> None:
    """Run the registry in order. `rerun=None` is a full pass. Otherwise run
    `rerun` (already closed downstream) and, as INPUT only, what it reads."""
    wanted = ALL_CATEGORIES if rerun is None else rerun | upstream(rerun)
    if rerun is not None and CATEGORY_SERVICES not in wanted and was_quiet:
        # Nothing to bill last time and `services` is not asked again: still
        # quiet, and nothing after `services` runs — the full pass's rule.
        p.check.quiet = True
        return
    for category in REGISTRY:
        if p.stopped:
            break
        if category.name not in wanted:
            continue
        begin = len(p.check.findings)
        category.run(p)
        _stamp(p.check, begin, category.name)
    if rerun is not None:
        p.check.findings = [f for f in p.check.findings if f.step in rerun]


def run_category(
    name: str,
    account: Any,
    context: CheckContext,
    *,
    check: AccountCheck | None = None,
    covered_unit_ids: tuple[str, ...] | None = None,
) -> AccountCheck:
    """Run ONE category on ONE account, on its own, and answer its findings.

    For a caller that needs one kind of check and nothing else — the Check
    report, a one-time bill, a test. A category that reads another's output
    (`decisions` reads `services`) sees an empty input when called alone and
    raises nothing: arranging the input is the caller's. Each check inside it
    still runs in its own savepoint (`_Guard.run`); only
    `runs.UtilityWideStop` escapes, as in `check_account`.
    """
    category = CATEGORIES[name]
    if check is None:
        check = AccountCheck(
            account_id=str(account.id),
            account_no=account.account_no,
            unit_id=str(account.unit_id) if getattr(account, "unit_id", None) else None,
            covered_unit_ids=tuple(covered_unit_ids or ()),
        )
    p = _Pass(account=account, ctx=context, check=check, guard=_Guard(check))
    begin = len(check.findings)
    category.run(p)
    _stamp(check, begin, name)
    return check


def _nothing_to_bill(account: Any, check: AccountCheck, refused: list[Finding]) -> bool:
    """BR-BIL-1025 — the gather refused because there is NOTHING to charge.

    Only when no OTHER check found a blocking problem (a dispute on a unit the
    account covers is still a fault), and asked through the one classifier the
    old loop used, `gather.nothing_to_bill`. A classifier that cannot answer is
    answered *no*: silence is never the fallback for a refusal.
    """
    others = [f for f in check.findings if f not in refused and f.severity == check_taxonomy.BLOCKS]
    if others:
        return False
    try:
        with transaction.atomic():
            return bool(gather.nothing_to_bill(account))
    except Exception:  # noqa: BLE001 — see the docstring
        return False


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _gather_every_service(
    account: Any,
    ctx: CheckContext,
    check: AccountCheck,
    guard: _Guard,
    readings: tuple[Any, ...],
) -> tuple[Any, list[Finding]]:
    """`gather_account`, and again without each service it refuses.

    Answers `(data, refused_findings)`. `data` is the last successful gather —
    the full account when nothing refused, otherwise a NARROWED one used only
    to find the account's other decisions and warnings (the account is
    blocked, so it is never billed from it). An ACCOUNT-level refusal (no
    service named) ends the loop: nothing narrower can be gathered.
    """
    refused: list[Finding] = []
    failed: set[str] = set()
    scope = ctx.scope_services
    universe = tuple(ctx.service_universe) or tuple(
        sorted({r.service_code for r in readings if getattr(r, "service_code", None)})
    )
    data = None
    for _attempt in range(len(universe) + 2):
        before = len(check.findings)
        ok, answer = guard.run(
            lambda scope=scope: gather.gather_account(
                account=account,
                service_date=ctx.price_date,
                period_start=ctx.period_start,
                period_end=ctx.period_end,
                cycle_days=ctx.cycle_days,
                readings=readings,
                scope_services=scope,
            )
        )
        if ok:
            data = answer
            break
        new = check.findings[before:]
        refused.extend(new)
        last = new[-1] if new else None
        service = getattr(last, "service_code", None)
        if last is None or last.code not in _PER_SERVICE_RETRY or not service:
            break
        if service in failed:
            break
        failed.add(service)
        base = scope if scope is not None else universe
        scope = tuple(code for code in base if code not in failed)
        if not scope:
            break
    return data, refused


#: The refusals that belong to ONE service, so the rest of the account can be
#: gathered without it. An unexpected error is never retried: it names no
#: service and a second attempt would only repeat it.
_PER_SERVICE_RETRY = frozenset(
    code
    for code, tag in check_taxonomy.TAGS.items()
    if tag.severity in (check_taxonomy.BLOCKS, check_taxonomy.DECISION)
    and code not in (check_taxonomy.CHECK_FAILED, check_taxonomy.CHECK_REFUSED)
)


__all__ = [
    "ALL_CATEGORIES",
    "CATEGORIES",
    "CATEGORY_ACCOUNT",
    "CATEGORY_DECISIONS",
    "CATEGORY_PAYMENTS",
    "CATEGORY_SERVICES",
    "CATEGORY_WARNINGS",
    "REGISTRY",
    "AccountCheck",
    "CheckCategory",
    "CheckContext",
    "Finding",
    "STATUS_BLOCKED",
    "STATUS_QUIET",
    "STATUS_READY",
    "check_account",
    "chunks",
    "downstream",
    "new_support_ref",
    "run_category",
    "upstream",
]
