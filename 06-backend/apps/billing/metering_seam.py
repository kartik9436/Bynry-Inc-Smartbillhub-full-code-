# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the moment a draft becomes an immutable bill) ·
#           US-MET-016 (EP-MET-04 supersede & correction — the BILLED read and
#           its J6 correction linkage)
#           Screens: S31 step 6 · S29 (the read drawer that offers the two
#           correction paths) · S31.2
# Rules:    BR-MET-053 (a BILLED read is corrected ONLY through the correction
#           flow — read fix and money fix travel together) · BR-MET-016 (billing
#           prices LINEAGE HEADS) · BR-BIL-055 (a break never blocks the run) ·
#           BR-BIL-030 (what a bill priced is frozen into the bill) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (an issued bill is
#           immutable) · B1 (no cross-module import; no cross-module ORM write)
# Tests:    06-backend/tests/test_def_098_billed_read_lock.py
# Impacts:  apps/billing/issue.issue_invoice (calls this inside the issue
#           transaction) · apps/metering/services.mark_read_billed (resolved BY
#           NAME) · apps/metering/services.correct_billed_read (the path this
#           unlocks) · apps/billing/stages/assemble_document (freezes the ids
#           this reads back)
# ───────────────────────────────────────────────────────
"""billing → metering SEAM: the BILLED lock, applied at issue.

🔒 HUMAN-REVIEW-PENDING — this runs INSIDE `issue.issue_invoice`'s transaction,
at the moment a discardable draft becomes an immutable financial record
(CLAUDE.md rule 4). AI-authored 2026-08-15 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md.

HUMAN-OWNED — added 2026-08-31 when the PO's ruling put this file on
10-scripts/gates/human_owned.txt ("groups one, two, three and four ... That is
56 files"). The guard list requires both markers; this file carried only
HUMAN-REVIEW-PENDING, which is exactly why G53 could not see it (DEF-2790).

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE.** Editing
that guard list is a process event, so the line is REPORTED for the PO batch
rather than self-granted — the posture `payments_seam.py`, `posting_seam.py`
and `delivery_seam.py` all took before it.

╔══════════════════════════════════════════════════════════════════════════╗
║  DEF-098 — THE DIAGNOSIS THAT MATTERS, BECAUSE THE FIRST ONE WAS WRONG   ║
╚══════════════════════════════════════════════════════════════════════════╝
`apps/metering/services.mark_read_billed` was published FOR BILLING TO CALL and
**nothing called it**, so a read that HAD been billed still read as `committed`.
A clerk correcting it therefore took the plain supersede path and **no
correction linkage was recorded** — precisely the failure US-MET-016 exists to
prevent, and the reason `correct_billed_read` exists at all.

The metering lane reported this as *"one call in the issue path"*. **It was
not**, and the difference is why this file exists. Measured, file by file, on
2026-08-15:

  1. `apps/metering/selectors.billing_reads_for_unit` DOES publish `read_id` on
     every row — the identity exists and crosses the seam;
  2. `apps/billing/runs._readings_for` built `ServiceReading` from those rows
     and **did not copy it**;
  3. `ServiceReading` had no `read_id` field at all;
  4. the string `read_id` appeared **nowhere** in `apps/billing/`;
  5. `issue_invoice(invoice, *, issued_at, template_id, …)` receives only the
     Invoice — by issue time the readings are gone entirely.

So the identity was thrown away at billing's own contract boundary and could
not be recovered where the lock must be applied. Closing it is a multi-file
contract change on the money path: `read_id` onto `ServiceReading` and
`MeasuredService`, copied in `runs`, carried through stage 2, **frozen into the
bill's own snapshot by stage 6** — which is the only surface that survives to
issue — and read back here.

────────────────────────────────────────────────────────────────────────────
WHY THE SNAPSHOT AND NOT A RUN-SCOPED MAP
────────────────────────────────────────────────────────────────────────────
A map handed from `issue_run` to `issue_invoice` would work for a bill run and
for nothing else: `issue_invoice` is also reached by the single-bill path, by a
resumed batch and by a re-issue, and each would need its own map to be built and
passed. A prop that only some callers pass is the dead-UI defect wearing server
clothes (hard-won law 2). **The bill itself knows what it priced** — BR-BIL-030
freezes exactly that — so the id is read off the row that is being issued and
every caller gets it for free.

It also survives a restart, which a map does not: a run interrupted between
pricing and issue re-enters with the drafts still holding their snapshots.

────────────────────────────────────────────────────────────────────────────
WHAT THIS SEAM DOES NOT DO
────────────────────────────────────────────────────────────────────────────
  * **It never writes `meter_reads`.** `mark_read_billed` is metering's own
    function and is resolved BY NAME at call time (`import_module`, `getattr`),
    so there is no `import apps.metering` anywhere here (B1, gate G6).
  * **It never breaks a run.** An unpublished seam, a snapshot with no service
    list, an id metering refuses — each comes back on the result as a named
    problem and the bill issues (BR-BIL-055). A bill that failed to go out
    because a LOCK could not be applied would be a worse outcome than the lock
    being missing: the lock protects a later correction, the bill is the money.
  * **It never invents an id.** A service that priced nothing names no read and
    is skipped. A service-point id is not a read id and is never substituted.
  * **It never reports a number it did not achieve.** `locked` counts rows
    metering actually moved; `already_billed` counts the ones it refused
    because they were locked already (a re-issue), and the two are separate
    because collapsing them would make a replay look like fresh work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.db import transaction

METERING_MODULE = "metering"
MARK_READ_BILLED = "mark_read_billed"  # (read_id, invoice_id) -> bool

#: BR-MET-106's stored monthly grain, as metering already serves it to the
#: account screen (`GET /accounts/{id}/usage`, the S21 Usage tab). Resolved by
#: NAME for the same reason `mark_read_billed` is: billing imports no metering
#: module (B1, gate G6).
USAGE_READS_MODULE = "monthly_usage_reads"
USAGE_PAYLOAD = "usage_payload"  # (account_id, *, months, today) -> dict

#: A19 §1.7's block is TWELVE months. `usage_payload` clamps to the vocabulary
#: r10's own filter offers (12 or 24) and 12 is its default; it is stated here
#: rather than left to that default so the bill's window is a fact of THIS
#: module and cannot move when a screen's filter gains an option.
USAGE_HISTORY_MONTHS = 12


@dataclass(frozen=True)
class ReadLockOutcome:
    """Which of a bill's reads carry BR-MET-053's BILLED lock, after issue.

    `read_ids` is what the bill's own snapshot named, so a caller can see the
    denominator rather than infer it from a count.
    """

    read_ids: tuple[str, ...] = ()
    locked: int = 0
    already_billed: int = 0
    problems: tuple[dict[str, Any], ...] = ()

    @property
    def ran(self) -> bool:
        """True when the seam resolved and every named read was answered.

        NOT "locked > 0": a re-issue locks nothing and has run perfectly.
        """
        return not self.problems


def read_ids_on(invoice: Any) -> tuple[str, ...]:
    """The reads this bill was priced from, off its own frozen snapshot.

    `bill_payload["services"]` is stage 6's list and each entry carries the
    `read_id` that produced its quantity (`assemble_document._snapshot_payload`).
    A service that measured nothing carries None and is not returned — there is
    no read to lock, and a None in this tuple would be handed to metering as an
    id.

    Deduplicated and ORDER-STABLE: two services could in principle name the
    same read, and marking it twice is harmless (`mark_read_billed` is
    idempotent) but would double-count `locked` and make a one-read bill report
    two.
    """
    payload = getattr(invoice, "bill_payload", None) or {}
    services = payload.get("services") if isinstance(payload, dict) else None
    if not isinstance(services, list):
        return ()
    seen: dict[str, None] = {}
    for entry in services:
        if not isinstance(entry, dict):
            continue
        read_id = entry.get("read_id")
        if read_id:
            seen.setdefault(str(read_id), None)
        # 🔒 DEF-BIL-9075 — every reading a chained quantity was summed from;
        # the bill charged for each, so each is locked (BR-MET-053).
        for chained in entry.get("chain_read_ids") or ():
            if chained:
                seen.setdefault(str(chained), None)
        # 🔒 DEF-BIL-8244 — a meter swapped inside the period priced the OLD
        # meter's final reading too; it is locked with the new meter's.
        for part in entry.get("meter_parts") or ():
            if isinstance(part, dict) and part.get("read_id"):
                seen.setdefault(str(part["read_id"]), None)
    return tuple(seen)


@dataclass(frozen=True)
class UsageHistoryOutcome:
    """A19 §1.7's twelve-month block, as the bill will freeze it (CR-052 t8).

    `block` is metering's own `usage_payload` — the SAME payload the account
    screen draws — or None when it could not be read. `problem` names why, and
    a caller stamps the block when there is one and reports the problem when
    there is not: a bill whose usage history is missing still issues
    (BR-BIL-055), it simply prints no chart.
    """

    block: dict[str, Any] | None = None
    problem: dict[str, Any] | None = None


def usage_history_for(
    account_id: Any, *, as_of: Any, months: int = USAGE_HISTORY_MONTHS
) -> UsageHistoryOutcome:
    """The account's last twelve stored months of usage, for freezing at issue.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  WHY BILLING ASKS FOR THIS AT ISSUE INSTEAD OF THE DOCUMENT JOINING  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `documents.py` has carried a named absence since it was written —
    `usage_history_not_available`: *"the 12-month usage graph is optional in
    A19 and needs eleven periods this bill's snapshot does not carry. Reading
    them from `meter_reads` would be the live join BR-BIL-030 forbids, so the
    block is omitted rather than filled."* Both halves of that sentence are
    right, and this function is what makes them stop being a dead end: the
    eleven earlier periods are **stamped into the snapshot**, so the render
    stays a pure function of the frozen bill and a reprint in 2033 shows the
    twelve months as they stood on the bill date rather than as they stand
    then.

    ⚠ **IT IS THE STORED GRAIN AND NOT A RECOMPUTE.** BR-MET-106 stores one row
    per (account, service, calendar month) and restates it — never edits it —
    when a read is superseded, and `monthly_usage_reads.usage_payload` is the
    read model already serving `GET /accounts/{id}/usage`. Billing asks for
    that same answer BY NAME. Deriving a second one here would be billing
    computing a metering figure, and the two would disagree the first time a
    late read restated a month.

    `as_of` is the bill's own period end, a PARAMETER and never a clock read
    (BR-TEN-043): a June bill re-issued in September must carry June's twelve
    months. It is passed to metering as `today`, which is that read model's
    name for the last month on the axis.

    NOTHING RAISES. A deployment whose metering lane has not landed, or an
    account metering refuses, comes back as a named problem and the bill issues
    without the block — exactly as `mark_reads_billed` above behaves and for
    the same reason: the chart is a courtesy, the bill is the money.
    """
    try:
        reads = import_module(f"apps.{METERING_MODULE}.{USAGE_READS_MODULE}")
    except ImportError:  # pragma: no cover - the app package always imports
        reads = None
    payload_for = getattr(reads, USAGE_PAYLOAD, None) if reads else None
    if not callable(payload_for):
        return UsageHistoryOutcome(
            problem={
                "code": "usage_history_seam_unpublished",
                "br_ref": "A19 §1.7 · BR-MET-106",
                "detail": f"apps.{METERING_MODULE}.{USAGE_READS_MODULE}.{USAGE_PAYLOAD} is "
                "not published, so the twelve-month usage block could not be frozen into "
                "this bill and the document prints no chart. Billing may not read "
                "`meter_reads` (B1) and does not; nothing is recomputed here.",
            }
        )
    try:
        # ⚠ **THE SAVEPOINT IS NOT TIDINESS — IT IS THE ONLY THING THAT MAKES
        # THIS `except` WORK ON POSTGRESQL (CLAUDE.md hard-won law 14).**
        # This function runs INSIDE `issue_invoice`'s transaction. On PostgreSQL
        # a failed statement ABORTS the whole transaction, so catching a
        # database error here and carrying on would leave every later statement
        # — including the `invoice.save()` two lines below, the GL stamps, the
        # posting handoff and the audit row — raising `InFailedSqlTransaction`,
        # and the bill would be LOST rather than issued without its chart. A
        # nested `atomic()` is a SAVEPOINT: the rollback to it un-aborts the
        # transaction, which is the whole point.
        #
        # **DO NOT "SIMPLIFY" THIS AWAY.** `config/settings/test.py` hardcodes
        # in-memory SQLite, which has no aborted-transaction state at all, so
        # the version without this block passes the entire suite, green, on
        # every machine, and fails the first time metering refuses a real
        # account in production.
        with transaction.atomic():
            block = payload_for(account_id, months=months, today=as_of)
    except Exception as refused:  # noqa: BLE001 - metering's refusal must not lose a bill
        return UsageHistoryOutcome(
            problem={
                "code": "usage_history_unreadable",
                "br_ref": "A19 §1.7 · BR-MET-106",
                "detail": "metering could not answer this account's monthly usage "
                f"({type(refused).__name__}), so the twelve-month block is absent from "
                "this bill's frozen snapshot and the document prints no chart. The bill "
                "itself is unaffected and is issued (BR-BIL-055).",
            }
        )
    if not isinstance(block, dict):  # pragma: no cover - defensive
        return UsageHistoryOutcome(
            problem={
                "code": "usage_history_unreadable",
                "br_ref": "A19 §1.7 · BR-MET-106",
                "detail": "metering's usage read model answered something other than a "
                "payload, so nothing was frozen onto this bill.",
            }
        )
    return UsageHistoryOutcome(block=block)


@dataclass(frozen=True)
class UsageBasisOutcome:
    """What this account's OWN metered history says about ONE service — DEF-2859.

    ⚠ **EVERY FIGURE HERE IS METERING'S, ASKED FOR BY NAME. BILLING AVERAGES
    NOTHING.** `usage_payload` already computes an average month, a highest and
    a lowest per service over BR-MET-106's stored monthly grain — it is what the
    account screen's Usage tab draws — and this picks those three values out of
    that answer. **Averaging the stored months here instead would be a SECOND
    arithmetic living beside BR-MET-026's signed one**, and the two would
    disagree the first time a late read restated a month. Picking a value out of
    a served payload is not a derivation; computing one would be.

    **WHAT IT IS FOR, and what it is deliberately NOT.** It is the starting
    figure the estimate window offers a clerk, and the range an absurd typed
    figure is questioned against (`12-governance/02-decision-log.md`,
    2026-08-31). It is **not** BR-BIL-029's guardrail: that one compares a
    PRODUCED DRAFT against a trailing average and stays blocked on the billing
    history `decisions.UNSUPPORTED_CASES` names. A later lane must not read this
    as having closed it.

    **A QUANTITY IS NEVER SERVED WITHOUT ITS UNIT** (CLAUDE.md rule 3). A window
    whose present months disagree about the unit has no summable figure at all —
    metering says so itself, with `absent_reason: mixed_units_across_months` —
    and this answers empty rather than picking one.

    `months` is how many months carried a reading behind the average, so a
    screen can say what the figure is an average OF rather than implying twelve.
    """

    quantity: str | None = None
    unit: str | None = None
    high: str | None = None
    low: str | None = None
    months: int = 0
    problem: dict[str, Any] | None = None

    @property
    def known(self) -> bool:
        """True only when there is a figure AND the unit it is measured in."""
        return self.quantity is not None and bool(self.unit)


def _figure(metric: Any, unit: str | None) -> str | None:
    """One metric's value, or None — and None whenever its unit is not `unit`.

    The unit check is not defensive tidiness: `peak` and `low` carry their own
    unit, and comparing a figure in kgal against a high in gallons would put a
    question in front of a clerk that is arithmetic nonsense.
    """
    if not isinstance(metric, dict):
        return None
    value = metric.get("value")
    if value is None or metric.get("unit") != unit:
        return None
    return str(value)


def usage_basis_for(account_id: Any, service_code: str, *, as_of: Any) -> UsageBasisOutcome:
    """This account's average, highest and lowest month for ONE service.

    Reads through `usage_history_for` rather than resolving the seam a second
    time, so there is ONE place that knows metering's module name, one savepoint
    posture, and one set of refusal sentences (hard-won law 5's reasoning
    applied to a seam instead of a file).

    NOTHING RAISES. An account metering has no stored months for comes back
    empty and the estimate window simply opens blank, which is the honest state:
    an account we know nothing about is one where a suggested figure would be an
    invention.
    """
    outcome = usage_history_for(account_id, as_of=as_of)
    if outcome.block is None:
        return UsageBasisOutcome(problem=outcome.problem)
    series = outcome.block.get("series")
    if not isinstance(series, list):
        return UsageBasisOutcome()
    for entry in series:
        if not isinstance(entry, dict):
            continue
        service = entry.get("service")
        if not isinstance(service, dict) or service.get("code") != service_code:
            continue
        metrics = entry.get("metrics")
        if not isinstance(metrics, dict):
            return UsageBasisOutcome()
        average = metrics.get("avg_per_month")
        if not isinstance(average, dict):
            return UsageBasisOutcome()
        unit = average.get("unit")
        quantity = _figure(average, unit)
        if quantity is None or not unit:
            # A figure with no unit, or a window whose months disagree about it.
            # Rule 3: neither is served, and the absence is the answer.
            return UsageBasisOutcome()
        months = average.get("months_counted")
        return UsageBasisOutcome(
            quantity=quantity,
            unit=str(unit),
            high=_figure(metrics.get("peak"), unit),
            low=_figure(metrics.get("low"), unit),
            months=int(months) if isinstance(months, int) else 0,
        )
    return UsageBasisOutcome()


def mark_reads_billed(invoice: Any, *, actor: Any = None) -> ReadLockOutcome:
    """Apply BR-MET-053's BILLED lock to every read this bill priced.

    CALLED FROM INSIDE `issue_invoice`'s transaction, after the status moves,
    for the same reason the posting handoff and the delivery rows are: the lock
    names an invoice that EXISTS. A read locked against a draft that then broke
    on a GL stamp would be a read a clerk could no longer correct in the ordinary
    way, for a bill nobody ever received.

    **IDEMPOTENT BECAUSE METERING'S FUNCTION IS.** `mark_read_billed` filters on
    `lifecycle="committed"` and `superseded_by_id IS NULL` and answers False
    otherwise, so a re-issue cannot double-lock, and a SUPERSEDED row is refused
    — billing prices lineage heads (BR-MET-016/053), and locking a closed
    version would lock the wrong number.

    Every failure is REPORTED and none raises: BR-BIL-055 says a break never
    blocks the run, and the bill is the money while the lock protects a later
    correction. `actor` is accepted and deliberately not forwarded — metering's
    signature is `(read_id, invoice_id)` and inventing a third argument here
    would be this file writing another module's contract.
    """
    read_ids = read_ids_on(invoice)
    if not read_ids:
        # NOT an error and NOT silence. A base-only bill, a bill for services
        # with no meter, and a bill whose snapshot predates DEF-098 all land
        # here, and the third one is the case worth naming: a draft priced
        # before this field existed carries no ids, so its reads keep the
        # `committed` lifecycle and its corrections take the plain supersede
        # path. Re-run the draft to get the lock.
        return ReadLockOutcome(
            problems=(
                {
                    "code": "no_read_ids_on_bill",
                    "br_ref": "BR-MET-053",
                    "detail": "this bill's frozen snapshot names no meter read, so no BILLED "
                    "lock was applied and a later correction of any read behind it will take "
                    "the plain supersede path with no J6 linkage. Expected for a base-only "
                    "bill or a service with no meter; on a metered bill it means the draft "
                    "was priced before `read_id` was carried through the pipeline (DEF-098) "
                    "and re-running the draft is what fixes it.",
                },
            ),
        )

    try:
        metering_services = import_module(f"apps.{METERING_MODULE}.services")
    except ImportError:  # pragma: no cover - the app package always imports
        metering_services = None
    mark = getattr(metering_services, MARK_READ_BILLED, None) if metering_services else None
    if not callable(mark):
        return ReadLockOutcome(
            read_ids=read_ids,
            problems=(
                {
                    "code": "read_billed_lock_not_applied",
                    "br_ref": "BR-MET-053",
                    "detail": f"apps.{METERING_MODULE}.services.{MARK_READ_BILLED} is not "
                    "published, so the reads this bill priced keep the `committed` lifecycle. "
                    "Billing may not write `meter_reads` (B1 / DB-16) and does not. The "
                    "consequence is stated rather than left to be discovered: a clerk "
                    "correcting one of these reads takes the plain supersede path and NO "
                    "correction linkage is recorded (US-MET-016 / BR-MET-053).",
                },
            ),
        )

    locked = 0
    already = 0
    refused: list[str] = []
    for read_id in read_ids:
        try:
            # ⚠ SAVEPOINT, for the reason `usage_history_for` above states in
            # full: this loop runs inside `issue_invoice`'s transaction, and on
            # PostgreSQL a caught database error leaves the transaction ABORTED
            # so that everything after it fails — the exact shape CLAUDE.md
            # hard-won law 14 was written from, and it was here before this
            # comment was (DEF-2444, found by the CR-052 lane while adding the
            # second catch-and-continue to this file). `mark_read_billed`
            # UPDATEs `meter_reads`, so a refusal here is a real database error
            # and not only a Python one.
            with transaction.atomic():
                moved = bool(mark(read_id, invoice.pk))
        except Exception:  # noqa: BLE001 - metering's refusal must not lose a bill
            refused.append(read_id)
            continue
        if moved:
            locked += 1
        else:
            already += 1

    problems: list[dict[str, Any]] = []
    if refused:
        problems.append(
            {
                "code": "read_billed_lock_refused",
                "br_ref": "BR-MET-053",
                "detail": "metering refused the BILLED lock for "
                f"{len(refused)} of this bill's {len(read_ids)} read(s), so those reads keep "
                "the `committed` lifecycle and a later correction of one of them takes the "
                "plain supersede path with no J6 linkage. The bill itself is unaffected and "
                "is issued (BR-BIL-055) — the lock protects a future correction, the bill is "
                "the money.",
            }
        )
    return ReadLockOutcome(
        read_ids=read_ids,
        locked=locked,
        already_billed=already,
        problems=tuple(problems),
    )


RECORD_BILLED_ESTIMATE = "record_billed_estimate"


@dataclass(frozen=True)
class EstimateOutcome:
    """The clerk estimates this bill saved into Meter Reads at issue."""

    recorded: int = 0
    read_ids: tuple[str, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()


def record_billed_estimates(invoice: Any, *, actor: Any = None) -> EstimateOutcome:
    """🔒 DEF-BIL-8280 — each CLERK estimate this bill charged, saved into
    Meter Reads through metering's own service, at ISSUE and never at draft.

    PO direction 2026-09-30 (`07-billing/16-check-decisions-next-bill.md`): a
    clerk's estimate from a Check decision writes no read, so the next bill
    counted the same usage again (Aug 1,000 · Sep estimate 5 · Oct 1,012 → Oct
    billed 12, should bill 7). Saved as an ESTIMATED reading on that meter at
    the period's end, metering's true-up (BR-MET-029) subtracts it from the
    next real reading. The entries come off the bill's OWN frozen snapshot
    (`services[].estimate`, written only for a clerk's estimate). Inside the
    issue transaction, each call in its own savepoint (law 14); every failure
    is REPORTED and the bill issues (BR-BIL-055). Billing writes no metering
    table — `record_billed_estimate` is metering's.
    """
    payload = getattr(invoice, "bill_payload", None) or {}
    services = payload.get("services") if isinstance(payload, dict) else None
    wanted = [
        entry
        for entry in (services or ())
        if isinstance(entry, dict) and entry.get("estimate") and not entry.get("read_id")
    ]
    if isinstance(payload, dict) and payload.get("mid_period_split"):
        # 🔒 `DEF-BIL-10098` (2026-10-13, J-FIX-TWENTY S19) — A BILL CUT AT A
        # MID-PERIOD PRICE CHANGE (BR-RAT-114) marks each part's DAY-WEIGHTED
        # SHARE of a real reading `estimate` with no `read_id`, and the part
        # that ends on the reading carries the `read_id`. Saving the shares put
        # a "billed" estimate of one part's share on the period's last day
        # (E-5002: 746.667 of a measured 1,600 kWh), which the next re-price
        # and the next true-up then read as the usage. The same shape
        # `DEF-BIL-8564` closed for catch-up bills; a service with no real
        # reading at all (a clerk's own estimate) is still saved.
        measured = {
            entry.get("code")
            for entry in (services or ())
            if isinstance(entry, dict) and entry.get("read_id")
        }
        wanted = [entry for entry in wanted if entry.get("code") not in measured]
    if isinstance(payload, dict) and payload.get("bill_type") in ("backbill", "penalty"):
        # 🔒 `DEF-BIL-8564` (2026-09-30, J74 case 6) — A CATCH-UP OR PENALTY
        # SAVES ONLY THE STRETCHES NO READING MEASURED. Its `services` list
        # marks every DAY-WEIGHTED SHARE of a real reading `estimated` with no
        # `read_id` too, and saving those would put a second, estimated usage
        # on a stretch the real reading already covers — the next true-up
        # would subtract the same water twice. (Until this fix every such row
        # was attempted at the bill's LAST day and refused by the unique
        # (meter, day) key beside the real reading, so nothing was saved —
        # including the one kind that should be: the meter's own estimate for
        # a stretch no reading measured, `back_bill.estimates[].unmeasured`.)
        # Each is saved on ITS stretch's last day, not the bill's.
        back = payload.get("back_bill") or {}
        wanted = [
            {
                "code": row.get("service_code"),
                "asset_id": row.get("asset_id"),
                "estimate": {"amount": row.get("quantity"), "unit": row.get("unit")},
                "read_on": row.get("period_end"),
            }
            for row in (back.get("estimates") or ())
            if isinstance(row, dict) and row.get("unmeasured")
        ]
    if not wanted:
        return EstimateOutcome()
    try:
        metering_services = import_module(f"apps.{METERING_MODULE}.services")
    except ImportError:  # pragma: no cover - the app package always imports
        metering_services = None
    record = getattr(metering_services, RECORD_BILLED_ESTIMATE, None) if metering_services else None
    account = getattr(invoice, "account", None)
    unit_id = getattr(account, "unit_id", None)
    if not callable(record) or unit_id is None:
        return EstimateOutcome(
            problems=(
                {
                    "code": "billed_estimate_not_saved",
                    "br_ref": "BR-MET-029",
                    "detail": "this bill charged a clerk's estimate and it could not be saved "
                    "into Meter Reads (no metering service, or the account names no unit), so "
                    "the next real reading will not be trued up against it.",
                },
            )
        )
    recorded = 0
    read_ids: list[str] = []
    problems: list[dict[str, Any]] = []
    for entry in wanted:
        estimate = entry["estimate"]
        try:
            with transaction.atomic():
                answer = record(
                    unit_id=unit_id,
                    service_code=entry.get("code"),
                    asset_id=entry.get("asset_id"),
                    read_on=(
                        date.fromisoformat(entry["read_on"])
                        if entry.get("read_on")
                        else invoice.period_end
                    ),
                    consumption=estimate.get("amount"),
                    unit=estimate.get("unit"),
                    invoice_id=invoice.pk,
                    bill_run_id=getattr(invoice, "bill_run_id", None),
                    decided_by_id=getattr(actor, "id", None),
                    actor=actor,
                )
        except Exception:  # noqa: BLE001 - metering's refusal must not lose a bill
            answer = {"recorded": False, "problem": "refused"}
        if answer.get("read_id"):
            read_ids.append(str(answer["read_id"]))
        if answer.get("recorded"):
            recorded += 1
        elif answer.get("problem"):
            problems.append(
                {
                    "code": "billed_estimate_not_saved",
                    "br_ref": "BR-MET-029",
                    "service_code": entry.get("code"),
                    "detail": f"metering answered {answer['problem']!r}",
                }
            )
    return EstimateOutcome(recorded=recorded, read_ids=tuple(read_ids), problems=tuple(problems))


# ── E11 wave 3 — two READS the bulk run's screens draw (2026-10-01) ─────────
#
# Neither writes anything and neither is on the money path; both live here
# because this file is billing's one door into Meter Reads (metering + assets,
# B2 r4), and both resolve BY NAME so billing imports neither module (B1, G6).


def _published(module: str, kind: str, name: str) -> Any:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - the app packages always import
        return None
    found = getattr(target, name, None)
    return found if callable(found) else None


def meter_numbers_for_units(unit_ids: Any) -> dict[str, dict[str, list[str]]]:
    """`{unit_id: {service_code: [meter number, …]}}` for ONE PAGE of Check
    rows — `DEF-BIL-8701`, D1 11–14's *"Water · W-10442"*.

    Two reads whatever the page size (NFR-3): metering's service points for
    every unit on the page (`service_points_for_units`, one query), then the
    in-service meters' NUMBERS on those points (`assets.meter_numbers_for_points`,
    one query per 900 points). The number is the business identifier on the
    meter's face, never a database id (B14 rule 31).

    `{}` when either read is unpublished or fails — the row then shows the
    service alone, which is what it showed before. Nothing raises: a meter
    number is a courtesy on a row whose decision does not depend on it.
    """
    units = [str(unit_id) for unit_id in (unit_ids or ()) if unit_id]
    if not units:
        return {}
    points_for = _published(METERING_MODULE, "selectors", "service_points_for_units")
    numbers_for = _published("assets", "selectors", "meter_numbers_for_points")
    if points_for is None or numbers_for is None:
        return {}
    try:
        with transaction.atomic():
            points = points_for(units) or {}
            numbers = numbers_for([p["id"] for rows in points.values() for p in rows]) or {}
    except Exception:  # noqa: BLE001 — a missing meter number never breaks a row
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for unit_id, rows in points.items():
        for point in rows:
            found = numbers.get(str(point["id"]))
            if found and point.get("service"):
                out.setdefault(str(unit_id), {}).setdefault(point["service"], []).extend(found)
    return out


@dataclass(frozen=True)
class RunReadLock:
    """`DEF-BIL-8685` — the BILLED lock across a sent run's bills, as Meter
    Reads answers it. `state` is `locked` (every named read carries it),
    `partly`, `open` (none does) or `none` (the bills named no read)."""

    reads: int
    locked: int

    @property
    def state(self) -> str:
        if self.reads == 0:
            return "none"
        if self.locked >= self.reads:
            return "locked"
        return "partly" if self.locked > 0 else "open"

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state, "reads": self.reads, "locked": self.locked}


def read_lock_for_bills(bills: Any) -> RunReadLock | None:
    """The reads a set of ISSUED bills priced (`read_ids_on`, off each bill's
    own frozen snapshot), and how many of them metering holds BILLED
    (`selectors.read_lock_counts`). D1 35's *"Meter reads: Locked"*.

    `bills` yields `bill_payload` dicts or objects carrying one. None when
    metering does not publish the count or it fails — the Sent card then
    omits the line rather than claiming a lock nobody checked.
    """
    if _published(METERING_MODULE, "selectors", "read_lock_counts") is None:
        return None
    read_ids: dict[str, None] = {}
    for bill in bills:
        holder = bill if hasattr(bill, "bill_payload") else _PayloadOnly(bill)
        for read_id in read_ids_on(holder):
            read_ids.setdefault(read_id, None)
    return read_lock_for_read_ids(list(read_ids))


def read_lock_for_read_ids(read_ids: list[str]) -> RunReadLock | None:
    """`read_lock_for_bills` for read ids already taken off the bills — the
    caller that extracts them in SQL (`DEF-BIL-8758`). Same answer, same None."""
    count = _published(METERING_MODULE, "selectors", "read_lock_counts")
    if count is None:
        return None
    if not read_ids:
        return RunReadLock(reads=0, locked=0)
    try:
        with transaction.atomic():
            answer = count(list(read_ids)) or {}
    except Exception:  # noqa: BLE001 — reported as absent, never as a lock
        return None
    return RunReadLock(reads=int(answer.get("reads") or 0), locked=int(answer.get("locked") or 0))


@dataclass(frozen=True)
class _PayloadOnly:
    bill_payload: Any


# ── `CR-180-BRC10` B5 · THE CORRECTED READING, SAVED TO METER READS ─────────
#
# 🔒 HUMAN-REVIEW-PENDING. Fix a bill's *wrong reading* row types the value
# the meter should have read. The PREVIEW prices it without writing it (the
# one-time bill's overlay option, `runs.KEYED_WINS_OVER_COMMITTED`); APPROVE
# AND ISSUE saves it here, then re-prices from what Meter Reads now holds — so
# the new bill names, and its issue locks, the corrected reading (J-FIX-TWENTY:
# *"the corrected reading saved and locked on issue"*).
#
# **METERING OWNS THE WRITE AND THE RULE.** `correct_billed_read` is BR-MET-053's
# ONLY door for a billed read — *"read fix and money fix travel together"*: the
# read is superseded (a new lineage head, the original closed and still
# visible) and a `read_corrections` row names the bill. Billing finds WHICH read
# (off the bill's own frozen snapshot) and calls the door by NAME; it imports no
# metering module (B1, G6) and writes no metering row.

METERING_CORRECT_BILLED = "correct_billed_read"
METERING_SUPERSEDE = "supersede_read"


def read_on_bill_for_meter(invoice: Any, asset_id: Any) -> str | None:
    """The read this bill was priced from on meter `asset_id`, or None.

    Off the bill's frozen snapshot (`read_ids_on`), narrowed to the meter by a
    READ of metering's row through the app registry — the identity-only read
    `single_correction._actor` makes of identity, for the same reason: billing
    may not import another module's models, and a read id alone does not say
    which meter it is."""
    from django.apps import apps as django_apps

    ids = read_ids_on(invoice)
    if not ids or not asset_id:
        return None
    read_model = django_apps.get_model(METERING_MODULE, "MeterRead")
    found = (
        read_model.objects.filter(
            tenant_id=getattr(invoice, "tenant_id", None),
            # `id`, not `pk`: `meter_reads` is partitioned and its primary key
            # is COMPOSITE, so `pk__in` wants tuples (Django refuses a list).
            id__in=list(ids),
            asset_id=str(asset_id),
            superseded_by_id__isnull=True,
        )
        .order_by("-read_at")
        .values_list("id", flat=True)
        .first()
    )
    return None if found is None else str(found)


def meter_reads_state(meter_no: str, read_ids: Any) -> tuple[bool, bool]:
    """`(ever_read, one_of_these_is_its)` for the meter numbered `meter_no`.

    `DEF-BIL-10129` — the move-out estimate must say *"Already read"* only of
    a reading taken on THIS meter. A billing reading is one row per SERVICE
    POINT, so a read id alone does not say which meter it came from; this asks
    metering's row, the identity-only read `read_on_bill_for_meter` makes and
    for the same reason (billing may not import metering's models), scoped to
    the current tenant (hard rule 1). Superseded rows are never counted.
    """
    from django.apps import apps as django_apps

    if not meter_no:
        return (False, False)
    from core import tenancy as core_tenancy

    read_model = django_apps.get_model(METERING_MODULE, "MeterRead")
    on_meter = read_model.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        asset__asset_no=meter_no,
        superseded_by_id__isnull=True,
    )
    ids = [str(read_id) for read_id in (read_ids or ()) if read_id]
    # `id`, not `pk` — `meter_reads` is partitioned with a composite key.
    return (on_meter.exists(), bool(ids) and on_meter.filter(id__in=ids).exists())


def save_corrected_reading(
    invoice: Any, *, asset_id: Any, value: Any, reason: str, actor: Any
) -> dict[str, Any]:
    """Save the corrected reading for this bill's meter. RAISES on refusal.

    Unlike the issue-time lock above, this one RAISES: it runs inside ONE
    bill's correction transaction (BR-BIL-047), and a reading that could not be
    saved must stop that bill — re-pricing on the old reading would issue a
    bill that is not the one approved. A metering refusal arrives in metering's
    vocabulary and leaves in billing's, so the case loop records it against
    this bill and carries on (no batch rollback).

    The billed door first; a read still unbilled (a bill issued before
    BR-MET-053's lock was wired) takes metering's plain supersede, which is the
    route metering itself sends an unbilled read down.
    """
    from apps.billing.exceptions import BillingRuleError
    from core import errors

    read_id = read_on_bill_for_meter(invoice, asset_id)
    if read_id is None:
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} was not priced from "
            f"a reading of meter {asset_id}, so there is no reading on it to correct.",
            br_ref="BR-MET-053",
            message_key="billing.correction.notOnThisBill",
        )
    billed = _published(METERING_MODULE, "services", METERING_CORRECT_BILLED)
    plain = _published(METERING_MODULE, "services", METERING_SUPERSEDE)
    if billed is None or plain is None:
        raise BillingRuleError(
            f"apps.{METERING_MODULE}.services publishes no {METERING_CORRECT_BILLED} / "
            f"{METERING_SUPERSEDE}, so the corrected reading cannot be saved to Meter Reads "
            "and the bill is not re-priced on a value nothing records.",
            br_ref="BR-MET-053",
        )
    payload = {"value": str(value), "reason": reason, "invoice_id": str(invoice.pk)}
    try:
        try:
            return billed(actor, read_id, payload)
        except errors.BizError as refusal:
            if getattr(refusal, "message_key", None) != "metering.read.not_billed":
                raise
            return plain(actor, read_id, {"value": str(value), "reason": reason})
    except (errors.BizError, errors.ValidationError, errors.AuthError) as refusal:
        raise BillingRuleError(
            f"Meter Reads refused the corrected reading {value} for bill "
            f"{getattr(invoice, 'invoice_no', None) or invoice.pk}: "
            f"{getattr(refusal, 'message_key', None) or refusal}",
            br_ref="BR-MET-053",
        ) from refusal


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-016@f5c9fdb (sha1[:7] of the three sources this defect fix was authored
#         from, concatenated in order: 04-docs/05-modules/04-metering/02-business-rules.md
#         BR-MET-053/016 · 04-docs/05-modules/04-metering/06-epics/EP-MET-04-read-validation.md
#         US-MET-016 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-030/055.
#         Co-packet US-BIL-005, same three sources. Raised as DEF-098 in
#         12-governance/10-defect-log.csv)
# generated: 2026-08-15 by the seams lane (DEF-098)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_def_098_billed_read_lock.py — RED-PROVED by
#         reverting the issue-time call and watching a billed read take the
#         PLAIN SUPERSEDE path with no linkage row, which IS the defect
# exceptions: (1) the read ids are read off the BILL's frozen snapshot rather
#         than passed down from the run — `issue_invoice` receives only the
#         Invoice, and a map only some callers pass is hard-won law 2 in server
#         clothes (2) `actor` is accepted and NOT forwarded: metering's
#         signature is (read_id, invoice_id) and adding an argument here would
#         be billing writing metering's contract (3) NOTHING RAISES — every
#         failure rides the outcome and the bill issues (BR-BIL-055)
#         (4) a draft priced BEFORE this field existed carries no ids and says
#         so by name (`no_read_ids_on_bill`) rather than reporting a silent zero
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
